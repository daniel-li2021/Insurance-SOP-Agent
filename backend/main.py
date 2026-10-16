import os
import secrets
import time
import asyncio
from pathlib import Path
from typing import Literal
from uuid import UUID
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import Field
from .controller import Controller
from .fixtures import Fixtures, ROOT
from .interpreter import LiveInterpreter, ScriptedInterpreter, ModelFailure
from .models import StrictModel
from .store import Store, Conflict, Limited


class TurnRequest(StrictModel):
    request_id: UUID
    version: int = Field(ge=0)
    text: str = Field(min_length=1, max_length=4000)


class ActionRequest(StrictModel):
    request_id: UUID
    version: int = Field(ge=0)
    action: Literal['preview', 'send', 'skip']
    summary_id: UUID | None = None


def create_app(directory: Path | None = None, interpreter=None, clock=time.time):
    load_dotenv(ROOT / '.env')
    mode = os.getenv('MODEL_MODE', 'live' if os.getenv('OPENAI_API_KEY') else 'scripted')
    if mode not in ('live', 'scripted'): raise ValueError('MODEL_MODE must be live or scripted')
    if interpreter is None:
        if mode == 'live':
            if not os.getenv('OPENAI_API_KEY'): raise ValueError('Live mode requires OPENAI_API_KEY')
            interpreter = LiveInterpreter(os.environ['OPENAI_API_KEY'], os.getenv('OPENAI_MODEL', 'gpt-6.1-sol'))
        else:
            interpreter = ScriptedInterpreter()
    production = os.getenv('APP_ENV') == 'production'
    origins = set(os.getenv('ALLOWED_ORIGINS', 'http://localhost:8000,http://127.0.0.1:8000,http://localhost:5173,http://127.0.0.1:5173').split(','))
    if production and not os.getenv('ALLOWED_ORIGINS'): raise ValueError('Set explicit ALLOWED_ORIGINS in production')
    store = Store(directory or Path(os.getenv('DATA_DIR', ROOT / 'data')), os.getenv('SESSION_ENCRYPTION_KEY'))
    controller = Controller(Fixtures())
    app = FastAPI(title='ClaimFlow', docs_url=None if production else '/api/docs', redoc_url=None)
    app.state.store, app.state.controller, app.state.interpreter = store, controller, interpreter
    model_slots = asyncio.Semaphore(2)

    @app.middleware('http')
    async def guard(request: Request, call_next):
        if request.url.path.startswith('/api/'):
            if request.method != 'GET':
                origin = request.headers.get('origin')
                if origin and origin not in origins:
                    return JSONResponse({'detail':'Request origin is not allowed.'}, status_code=403)
                if request.headers.get('sec-fetch-site') == 'cross-site':
                    return JSONResponse({'detail':'Cross-site request rejected.'}, status_code=403)
            length = request.headers.get('content-length', '0')
            if not length.isdigit() or int(length) > 12000:
                return JSONResponse({'detail':'Request body too large.'}, status_code=413)
            # Reading before parsing also bounds chunked requests without Content-Length.
            body = bytearray()
            async for chunk in request.stream():
                body.extend(chunk)
                if len(body) > 12000:
                    return JSONResponse({'detail':'Request body too large.'}, status_code=413)
            request._body = bytes(body)
        response = await call_next(request)
        response.headers['Cache-Control'] = 'no-store' if request.url.path.startswith('/api/') else 'no-cache'
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['Referrer-Policy'] = 'no-referrer'
        response.headers['Content-Security-Policy'] = "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'self'; form-action 'self'"
        return response

    @app.exception_handler(Conflict)
    async def conflict_handler(request, exc): return JSONResponse({'detail': str(exc)}, status_code=409)

    @app.exception_handler(Limited)
    async def limited_handler(request, exc): return JSONResponse({'detail': str(exc)}, status_code=429, headers={'Retry-After':'60'})

    @app.exception_handler(KeyError)
    async def session_handler(request, exc): return JSONResponse({'detail':'Session expired. Start a new session.'}, status_code=401)

    @app.exception_handler(PermissionError)
    async def permission_handler(request, exc): return JSONResponse({'detail':'This action requires valid authorization.'}, status_code=403)

    @app.exception_handler(ValueError)
    async def value_handler(request, exc): return JSONResponse({'detail':str(exc)}, status_code=409)

    def client_key(request):
        # Never trust an arbitrary X-Forwarded-For supplied by a public client.
        return request.client.host if request.client else 'local'

    def session(request: Request, mutation=False):
        cookie = request.cookies.get('claimflow_session')
        if not cookie: raise HTTPException(401, 'Start a session to continue.')
        state, csrf = store.load(cookie, clock())
        if mutation and not secrets.compare_digest(request.headers.get('x-csrf-token', ''), csrf):
            raise HTTPException(403, 'Session security check failed. Refresh the page.')
        controller.expire(state, clock())
        return cookie, state, csrf

    def view(state, csrf):
        return {**controller.view(state, clock()), 'csrf':csrf}

    @app.get('/api/health')
    def health():
        return {'status':'ok','model':interpreter.name,'mode':'scripted' if interpreter.name == 'scripted' else 'live', 'fixture_version':controller.f.version}

    @app.get('/api/demo-starter')
    def demo_starter():
        p = controller.f.person('P9')
        return {'opening':f'My name is {p.name}, policy {p.policy_number}. I’m calling about my denied healthcare claim from January. My DOB is {p.dob}, and my SSN last four is {p.id_last4}.',
                'description':'Margaret is calling about a denied healthcare claim. Start with her supplied synthetic details, then ask about documents, next steps, or the recorded payment amounts.'}

    @app.post('/api/session')
    def start(request: Request, response: Response):
        store.limit('new:' + client_key(request), 12, 3600, clock())
        old = request.cookies.get('claimflow_session')
        if old: store.remove(old)
        cookie, csrf, state = store.create(clock())
        state.model = interpreter.name
        # Welcome is returned by the product UI; stored turns are exclusively user interactions.
        response.set_cookie('claimflow_session', cookie, httponly=True, secure=production, samesite='strict', max_age=86400)
        return view(state, csrf)

    @app.get('/api/session')
    def resume(request: Request):
        _, state, csrf = session(request)
        state.model = interpreter.name
        return view(state, csrf)

    @app.post('/api/turn')
    async def turn(payload: TurnRequest, request: Request):
        cookie, _, csrf = session(request, True)
        if not payload.text.strip(): raise HTTPException(422, 'Enter a message.')
        fingerprint = store.fingerprint(payload.text)
        state, lease = store.acquire(cookie, str(payload.request_id), payload.version, fingerprint, clock())
        if lease is None: return view(state, csrf)
        try:
            controller.expire(state, clock())
            if state.turns >= 40: raise Limited('This demo session has reached its turn limit. Start a new session.')
            if state.verification_attempts >= 6 and not state.party_id:
                raise Limited('Identity attempt limit reached. Contact member support or start a new synthetic scenario later.')
            store.limit('turn:' + client_key(request), 30, 600, clock())
            state.model = interpreter.name
            if model_slots.locked():
                raise Limited('The language service is busy. Please retry in a moment.')
            if interpreter.name != 'scripted':
                store.reserve_tokens(12000, int(os.getenv('DAILY_TOKEN_LIMIT', '200000')), clock())
            try:
                async with model_slots:
                    interpreted, usage = await asyncio.wait_for(interpreter.interpret(payload.text, state), timeout=30)
            except (ModelFailure, TimeoutError):
                # Do not persist the raw failed input or advance workflow state.
                raise HTTPException(503, 'The language service is unavailable. Your session is safe; retry your message.') from None
            if interpreter.name != 'scripted': store.settle_tokens(12000, usage['tokens'], clock())
            state.event('INTERPRETED', f'{usage["latency_ms"]} ms · {usage["tokens"]} tokens · structured interpretation; policy decided by code.', clock())
            controller.answer(state, payload.text, interpreted, clock(), str(payload.request_id))
            store.commit(cookie, lease, str(payload.request_id), fingerprint, state, clock())
            return view(state, csrf)
        finally:
            store.release(cookie, lease)

    @app.post('/api/action')
    def action(payload: ActionRequest, request: Request):
        cookie, _, csrf = session(request, True)
        store.limit('action:' + client_key(request), 60, 600, clock())
        fingerprint = store.fingerprint(f'{payload.action}:{payload.summary_id}')
        state, lease = store.acquire(cookie, str(payload.request_id), payload.version, fingerprint, clock())
        if lease is None: return view(state, csrf)
        try:
            now = clock()
            controller.expire(state, now)
            controller.f.authorize(state, now)
            if payload.action == 'preview':
                claim = controller.f.claim(state, state.case_id, now) if state.case_id else None
                if not claim: raise ValueError('Select an authorized claim before reviewing a summary.')
                controller.preview(state, claim, '', now)
            else:
                controller.email(state, str(payload.summary_id), payload.action, now)
            store.commit(cookie, lease, str(payload.request_id), fingerprint, state, now)
            return view(state, csrf)
        finally:
            store.release(cookie, lease)

    @app.get('/api/evaluations')
    def scenarios():
        from .evaluation import scenario_catalog
        return scenario_catalog()

    @app.post('/api/evaluations/{scenario_id}')
    def evaluate(scenario_id: str, request: Request):
        session(request, True)
        store.limit('eval:' + client_key(request), 40, 600, clock())
        from .evaluation import run_scenario
        try: return run_scenario(scenario_id)
        except KeyError: raise HTTPException(404, 'Unknown scenario') from None

    dist = ROOT / 'frontend/dist'
    if dist.is_dir():
        app.mount('/assets', StaticFiles(directory=dist / 'assets'), name='assets')

    @app.get('/')
    def frontend():
        if not (dist / 'index.html').is_file():
            return JSONResponse({'detail':'Build the frontend with npm run build in frontend/.'}, status_code=503)
        return FileResponse(dist / 'index.html')

    return app

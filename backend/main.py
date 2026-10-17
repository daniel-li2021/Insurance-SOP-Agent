import os
import secrets
import time
import asyncio
from pathlib import Path
from typing import Literal
from uuid import UUID
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import Field, model_validator
from .controller import Controller
from .fixtures import Fixtures, ROOT
from .interpreter import LiveInterpreter, ScriptedInterpreter, ModelFailure
from .models import Candidate, Interpretation, StrictModel, Session
from .settings import Settings, SettingsRequest
from .providers import validate_selection
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


class VerificationField(StrictModel):
    field: Literal['name', 'dob', 'phone', 'email', 'id_last4']
    value: str = Field(min_length=1, max_length=160)
    identifier_type: Literal['ssn_last4', 'national_id_last4', 'unspecified'] = 'unspecified'


class VerificationRequest(StrictModel):
    request_id: UUID
    version: int = Field(ge=0)
    fields: list[VerificationField] = Field(min_length=3, max_length=3)

    @model_validator(mode='after')
    def distinct_fields(self):
        if len({f.field for f in self.fields}) != 3 or any(not f.value.strip() for f in self.fields):
            raise ValueError('Choose three distinct approved fields.')
        return self


def create_app(directory: Path | None = None, interpreter=None, clock=time.time):
    load_dotenv(ROOT / '.env')
    production = os.getenv('APP_ENV') == 'production'
    mode = os.getenv('MODEL_MODE', 'live' if os.getenv('OPENAI_API_KEY') else 'scripted')
    if mode not in ('live', 'scripted'): raise ValueError('MODEL_MODE must be live or scripted')
    if interpreter is None:
        if mode == 'live' and not production:
            if not os.getenv('OPENAI_API_KEY'): raise ValueError('Live mode requires OPENAI_API_KEY')
            model = os.getenv('OPENAI_MODEL', 'gpt-6.1-sol')
            validate_selection('openai', model)
            interpreter = LiveInterpreter(os.environ['OPENAI_API_KEY'], model)
        else:
            interpreter = ScriptedInterpreter()
    origins = set(os.getenv('ALLOWED_ORIGINS', 'http://localhost:8000,http://127.0.0.1:8000,http://localhost:5173,http://127.0.0.1:5173').split(','))
    if production and not os.getenv('ALLOWED_ORIGINS'): raise ValueError('Set explicit ALLOWED_ORIGINS in production')
    store = Store(directory or Path(os.getenv('DATA_DIR', ROOT / 'data')), os.getenv('SESSION_ENCRYPTION_KEY'))
    controller = Controller(Fixtures())
    app = FastAPI(title='ClaimFlow', docs_url=None if production else '/api/docs', redoc_url=None)
    app.state.store, app.state.controller, app.state.interpreter = store, controller, interpreter
    model_slots = asyncio.Semaphore(2)
    settings = Settings(interpreter, allow_local=not production)
    app.state.settings = settings

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

    @app.exception_handler(RequestValidationError)
    async def validation_handler(request, exc):
        # FastAPI's default echoes rejected input, which can contain a BYOK secret.
        return JSONResponse({'detail': 'Invalid request. Check required fields and supported values.'}, status_code=422)

    @app.exception_handler(Conflict)
    async def conflict_handler(request, exc): return JSONResponse({'detail': str(exc)}, status_code=409)

    @app.exception_handler(Limited)
    async def limited_handler(request, exc): return JSONResponse({'detail': str(exc)}, status_code=429, headers={'Retry-After':str(exc.retry_after)})

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
        selected = state.model_settings or settings.default
        return {**controller.view(state, clock()), 'csrf':csrf, 'model': selected.model,
                'model_connection': {'ready': selected.credential_source != 'byok' or bool(selected.api_key),
                                     'retain_for_new_sessions': selected.retain_for_new_sessions}}

    async def interpret(selected, text, state):
        if model_slots.locked(): raise Limited('The language service is busy. Please retry in a moment.')
        live = selected.name != 'scripted'
        reserved_at = clock()
        if live: store.reserve_tokens(12000, int(os.getenv('DAILY_TOKEN_LIMIT', '200000')), reserved_at)
        try:
            async with model_slots:
                result, usage = await asyncio.wait_for(selected.interpret(text, state), timeout=30)
            if live: store.settle_tokens(12000, usage['tokens'], reserved_at)
            return result, usage
        finally:
            if selected is not interpreter and isinstance(selected, LiveInterpreter):
                await selected.client.close()

    @app.get('/api/settings')
    def model_settings(request: Request):
        _, state, _ = session(request)
        return settings.public(state)

    @app.post('/api/settings')
    async def update_settings(payload: SettingsRequest, request: Request):
        cookie, _, csrf = session(request, True)
        fingerprint = store.fingerprint('settings:' + payload.model_dump_json())
        # SecretStr intentionally masks JSON output, so bind the actual key via HMAC too.
        if payload.api_key: fingerprint = store.fingerprint(fingerprint + payload.api_key.get_secret_value())
        state, lease = store.acquire(cookie, str(payload.request_id), payload.version, fingerprint, clock())
        if lease is None: return {'session': view(state, csrf), 'settings': settings.public(state)}
        try:
            store.limit('settings:' + client_key(request), 10, 600, clock())
            candidate = settings.candidate(payload)
            probe = Session(model=candidate.model, model_settings=candidate)
            selected = settings.interpreter(probe)
            try:
                await interpret(selected, 'Connection check. No claim or identity request.', Session())
            except (ModelFailure, TimeoutError) as error:
                detail = str(error) if isinstance(error, ModelFailure) else 'Connection timed out. Please retry.'
                raise HTTPException(503, detail) from None
            candidate.validated_at = clock()
            # A validated switch resets workflow/consent; anti-abuse counters remain.
            fresh = Session(version=state.version, turns=state.turns,
                            verification_attempts=state.verification_attempts,
                            model=candidate.model, model_settings=candidate)
            fresh.event('MODEL_CHANGED', 'Model connection validated. Fresh identity verification required.', clock())
            store.commit(cookie, lease, str(payload.request_id), fingerprint, fresh, clock())
            return {'session': view(fresh, csrf), 'settings': settings.public(fresh)}
        finally:
            store.release(cookie, lease)

    @app.get('/api/health')
    def health():
        return {'status':'ok','model':interpreter.name,'mode':'scripted' if interpreter.name == 'scripted' else 'live', 'fixture_version':controller.f.version}

    @app.get('/api/demo-starter')
    def demo_starter():
        p = controller.f.person('P9')
        opening = f'My name is {p.name}, policy {p.policy_number}. I’m calling about my denied healthcare claim from January. My DOB is {p.dob}, and my SSN last four is {p.id_last4}.'
        description = 'Start with Margaret’s synthetic details, then ask about documents, next steps, or the recorded payment amounts.'
        return {'opening': opening, 'description': description,
                'verification_details': {'name': p.name, 'dob': p.dob, 'phone': p.phone}, 'scenarios': [
            {'id': 'standard', 'name': 'Standard Claim', 'description': description, 'opening': opening},
            {'id': 'frustrated', 'name': 'Frustrated Caller', 'description': 'Try empathy and the privacy gate first. Then provide the synthetic identity details below to continue.',
             'opening': 'I already told you who I am. This is ridiculous. Just tell me why my healthcare claim from January was denied.'},
            {'id': 'ambiguous', 'name': 'Ambiguous Claim', 'description': 'Verify identity, then choose between two January healthcare claims. The agent should ask before selecting.',
             'opening': f'My name is {p.name}, DOB {p.dob}, SSN last four {p.id_last4}. What is the status of my January healthcare claim?'},
        ]}

    @app.post('/api/session')
    def start(request: Request, response: Response):
        old = request.cookies.get('claimflow_session')
        fresh = Session(model=interpreter.name)
        if old:
            try:
                previous, _ = store.load(old, clock())
                selected = previous.model_settings
                if selected and selected.credential_source == 'byok':
                    retained = selected.model_copy(deep=True)
                    if not retained.retain_for_new_sessions:
                        retained.api_key = None
                        retained.validated_at = None
                    fresh.model_settings = retained
                    fresh.model = retained.model
            except KeyError:
                pass
        cookie, csrf, state = store.create(clock(), fresh)
        if old: store.remove(old)
        # Welcome is returned by the product UI; stored turns are exclusively user interactions.
        response.set_cookie('claimflow_session', cookie, httponly=True, secure=production, samesite='strict', max_age=86400)
        return view(state, csrf)

    @app.get('/api/session')
    def resume(request: Request):
        _, state, csrf = session(request)
        return view(state, csrf)

    @app.post('/api/turn')
    async def turn(payload: TurnRequest, request: Request):
        return await process_turn(payload, request)

    @app.post('/api/verify')
    async def verification(payload: VerificationRequest, request: Request):
        return await process_turn(payload, request)

    async def process_turn(payload: TurnRequest | VerificationRequest, request: Request):
        cookie, _, csrf = session(request, True)
        form = isinstance(payload, VerificationRequest)
        text = '\n'.join(f'{f.field}: {f.value}' for f in payload.fields) if form else payload.text
        if not text.strip(): raise HTTPException(422, 'Enter a message.')
        fingerprint = store.fingerprint('verify:' + payload.model_dump_json(exclude={'version', 'request_id'}) if form else text)
        state, lease = store.acquire(cookie, str(payload.request_id), payload.version, fingerprint, clock())
        if lease is None: return view(state, csrf)
        try:
            controller.expire(state, clock())
            if form and (state.phase != 'VERIFY_ID' or state.assistance_paused):
                raise ValueError('The verification form is no longer active. Continue from the current conversation.')
            if state.assistance_paused and not form and not controller.wants_human(text) and text.strip(' .!').casefold() not in (
                    'return to chatbot', 'resume chat', 'continue with chatbot'):
                raise ValueError('Chat is paused. Select Return to chatbot to resume your saved conversation. This message was not submitted.')
            pause_control = not form and (state.assistance_paused or controller.wants_human(text))
            if state.turns >= 40: raise Limited('This demo session has reached its turn limit. Start a new session.')
            if state.verification_attempts >= 6 and not state.party_id and not pause_control:
                raise Limited('Identity attempt limit reached. Contact member support or start a new synthetic scenario later.')
            store.limit('turn:' + client_key(request), 30, 600, clock())
            if form:
                subject = 'policyholder' if state.representative else 'caller'
                interpreted = Interpretation(identity=[Candidate(**f.model_dump(), source=f.value, subject=subject) for f in payload.fields], correction=True)
                state.event('VERIFICATION_FORM_SUBMITTED', 'Three distinct caller-supplied fields; existing identity rules decide authorization. Selected fields explicitly corrected.', clock())
            elif pause_control:
                # Human-request recovery must work even when a provider is unavailable.
                interpreted, _ = await ScriptedInterpreter().interpret(text, state)
                interpreted.action = 'human' if controller.wants_human(text) else 'continue'
                state.event('ASSISTANCE_CONTROL', 'Pause/return handled without model inference or claim access.', clock())
            else:
                selected = settings.interpreter(state)
                state.model = selected.name
                try:
                    interpreted, usage = await interpret(selected, text, state)
                except (ModelFailure, TimeoutError):
                    # Do not persist the raw failed input or advance workflow state.
                    raise HTTPException(503, 'The language service is unavailable. Your session is safe; retry your message.') from None
                state.event('INTERPRETED', f'{usage["latency_ms"]} ms · {usage["tokens"]} tokens · structured interpretation; policy decided by code.', clock())
            controller.answer(state, text, interpreted, clock(), str(payload.request_id))
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

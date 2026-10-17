"""Opt-in five-call synthetic relevance acceptance; no retries or private input output."""
import asyncio
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from dotenv import load_dotenv
from backend.controller import Controller
from backend.fixtures import Fixtures
from backend.interpreter import LiveInterpreter, ModelFailure, PROMPT_VERSION
from backend.models import Session

NOW = datetime(2026, 10, 17, tzinfo=timezone.utc).timestamp()


async def evaluate():
    c = Controller(Fixtures())
    p = c.f.person('P9')
    adapter = LiveInterpreter(os.environ['OPENAI_API_KEY'], 'gpt-6.1-sol')
    state = Session(model=adapter.name)
    cases = [
        ('denial', f'My name is {p.name}, DOB {p.dob}, SSN last four {p.id_last4}. Why was my January 2026 healthcare claim denied?',
         lambda text: 'pathology report' in text and 'office note' in text and 'has passed' in text),
        ('focused-alternative', "I can't get the pathology report. Is there another option?",
         lambda text: 'replacement copy' in text and 'office note' not in text and 'March 18' not in text and 'not confirmation' in text),
        ('document-pronoun', 'What format should that be in?',
         lambda text: 'pathology report' in text.lower() and 'office note' not in text and 'March 18' not in text),
        ('payment', 'How much money will I get?',
         lambda text: '$0.00' in text and '$1,450.00' in text and 'not a promised payout' in text and 'appeal' not in text and 'pathology' not in text),
        ('late-appeal', 'Can I still appeal after the deadline?',
         lambda text: 'has passed' in text and 'No appeal or transfer' in text and 'pathology' not in text and 'less than a week' not in text),
    ]
    rows = []
    try:
        for name, text, check in cases:
            assert len(rows) < 5  # Hard cap: 5 calls, 60,000 reserved tokens, no retries.
            try:
                interpretation, usage = await asyncio.wait_for(adapter.interpret(text, state), 30)
                c.answer(state, text, interpretation, NOW, name)
                answer = state.messages[-1].text
                rows.append({'scenario': name, 'passed': state.case_id == 'CL-2048' and check(answer) and len(answer.split()) < 160,
                             'topics': interpretation.topics, 'documents': interpretation.documents,
                             'response': answer, 'words': len(answer.split()), **usage})
                print(name, 'PASS' if rows[-1]['passed'] else 'FAIL', flush=True)
            except (ModelFailure, TimeoutError):
                rows.append({'scenario': name, 'passed': False, 'error': 'ModelFailure'})
                break
        if state.case_id:
            c.preview(state, c.f.claim(state, state.case_id, NOW), '', NOW)
        preview_safe = bool(state.summary and state.summary.status == 'offered' and not any(e.code == 'EMAIL_SIMULATED' for e in state.events))
        return {'model': adapter.name, 'prompt_version': PROMPT_VERSION, 'fixture_version': c.f.version,
                'controller_clock': NOW, 'calls': len(rows), 'reserved_token_cap': 60000,
                'actual_tokens': sum(r.get('tokens', 0) for r in rows),
                'passed': len(rows) == 5 and all(r['passed'] for r in rows) and preview_safe,
                'preview_without_send': preview_safe, 'results': rows,
                'limitations': 'One synthetic five-turn conversation on GPT-6.1 Sol. Does not establish general quality, reliability, other model acceptance or production insurer behavior.'}
    finally:
        await adapter.client.close()


if __name__ == '__main__':
    load_dotenv(Path(__file__).resolve().parents[1] / '.env')
    if not os.getenv('OPENAI_API_KEY'): raise SystemExit('No configured OpenAI key')
    result = asyncio.run(evaluate())
    output = Path('data/post-uat-live.json')
    output.parent.mkdir(exist_ok=True)
    output.write_text(json.dumps(result, indent=2) + '\n')
    print('Sanitized report:', output)
    raise SystemExit(0 if result['passed'] else 1)

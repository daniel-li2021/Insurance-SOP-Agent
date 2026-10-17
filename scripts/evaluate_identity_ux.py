"""Opt-in five-call identity UX acceptance, no retries and no raw inputs in output."""
import json
import os
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from dotenv import load_dotenv
from fastapi.testclient import TestClient
from backend.identity import supported
from backend.interpreter import LiveInterpreter, PROMPT_VERSION
from backend.main import create_app


class Probe(LiveInterpreter):
    observations: list

    async def interpret(self, text, state):
        proposal, usage = await super().interpret(text, state)
        self.observations.append({'fields': [{'field': c.field, 'subject': c.subject,
                                             'source_supported': supported(c, text)} for c in proposal.identity],
                                  'representative': proposal.representative, **usage})
        return proposal, usage


def evaluate():
    load_dotenv(Path(__file__).resolve().parents[1] / '.env')
    adapter = Probe(os.environ['OPENAI_API_KEY'], os.getenv('OPENAI_MODEL', 'gpt-6.1-sol'))
    adapter.observations = []
    now = datetime.now(timezone.utc)
    cases = [
        ('structured', True, 'name: Margaret Chen dob: 1985-03-15 phone: 650-521-2836', True),
        ('natural-us-date', True, "I'm Margaret Chen. My date of birth is 03/15/1985 and my phone is +1 (650) 521-2836.", True),
        ('accumulated-name', True, 'My name is Margaret Chen.', False),
        ('accumulated-dob-phone', False, 'My DOB is March 15th,1985; phone 650 521 2836.', True),
        ('ambiguous-dob', True, 'name: Margaret Chen; DOB 03/04/1985; phone 6505212836; SSN ending in 4472', False),
    ]
    rows = []
    with tempfile.TemporaryDirectory(prefix='claimflow-identity-live-') as directory:
        app = create_app(Path(directory), adapter)
        with TestClient(app) as client:
            for label, fresh, text, expected in cases:
                assert len(rows) < 5  # Five calls / 60,000 reserved tokens maximum; no retry.
                if fresh:
                    state = client.post('/api/session').json()
                    client.headers['x-csrf-token'] = state['csrf']
                response = client.post('/api/turn', json={'request_id': str(uuid4()), 'version': state['version'], 'text': text})
                if response.status_code != 200:
                    rows.append({'scenario': label, 'passed': False, 'http_status': response.status_code})
                    break
                state = response.json()
                passed = state['verified'] is expected
                if not expected:
                    passed &= not any(e['code'] == 'CLAIMS_READ' for e in state['events'])
                    passed &= state['verification']['fields'] == []
                rows.append({'scenario': label, 'passed': passed, 'verified': state['verified'],
                             'representative': state['verification']['representative'],
                             'events': [e['code'] for e in state['events']], **adapter.observations[-1]})
                print(label, 'PASS' if passed else 'FAIL', flush=True)
    return {'checked_at': now.isoformat(), 'model': adapter.name, 'prompt_version': PROMPT_VERSION,
            'fixture_version': app.state.controller.f.version, 'calls': len(rows), 'reserved_token_cap': 60000,
            'actual_tokens': sum(row.get('tokens', 0) for row in rows),
            'passed': len(rows) == 5 and all(row['passed'] for row in rows), 'results': rows,
            'baseline': {'prompt_version': 'claimflow-extract-v3', 'calls': 2, 'actual_tokens': 2516,
                         'fresh_structured_verified': True, 'fresh_natural_verified': True,
                         'form_verified_without_model': True},
            'limitations': 'Five synthetic OpenAI turns through the HTTP path; not broad identity/model reliability. Baseline is a separate two-call pre-edit observation. No real customer data, claim mutations or delivery.'}


if __name__ == '__main__':
    result = evaluate()
    output = Path('data/identity-ux-live.json')
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2) + '\n')
    print('Sanitized report:', output)
    raise SystemExit(0 if result['passed'] else 1)

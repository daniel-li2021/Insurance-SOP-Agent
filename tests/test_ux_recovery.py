"""Focused synthetic UX/security regressions. No live model calls."""
import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from backend.controller import Controller
from backend.fixtures import Fixtures
from backend.interpreter import INSTRUCTIONS, LiveInterpreter, ScriptedInterpreter
from backend.main import create_app
from backend.models import Candidate, Interpretation, Session
from tests.test_api import client, send
from tests.test_controller import NOW, verified


def form(client, fields=None, **overrides):
    s = client.get('/api/session').json()
    return client.post('/api/verify', json={
        'version': s['version'], 'request_id': str(uuid4()),
        'fields': fields if fields is not None else [
            {'field': 'name', 'value': 'Margaret Chen'},
            {'field': 'dob', 'value': '1985-03-15'},
            {'field': 'phone', 'value': Fixtures().person('P9').phone}], **overrides})


def test_form_uses_existing_gate_audit_redaction_and_idempotency(client):
    send(client, 'Why was my denied January healthcare claim denied?')
    request_id = str(uuid4())
    first = form(client, request_id=request_id).json()
    assert first['verified'] and first['case_id'] == 'CL-2048'
    assert first['verification']['count'] == 3
    assert any(e['code'] == 'VERIFICATION_FORM_SUBMITTED' for e in first['events'])
    assert first['messages'][-2]['text'] == 'name: [name provided]\ndob: [dob provided]\nphone: [phone provided]'
    for value in ('Margaret Chen', '1985-03-15', Fixtures().person('P9').phone):
        assert value not in str(first)
    assert form(client, request_id=request_id).json()['version'] == first['version']
    assert form(client).status_code == 409


@pytest.mark.parametrize('fields', [
    [{'field': 'name', 'value': 'Margaret Chen'}] * 3,
    [{'field': 'name', 'value': 'Margaret Chen'}, {'field': 'dob', 'value': '1985-03-15'}],
    [{'field': 'policy_number', 'value': 'POL-9921'}] * 3,
    [{'field': 'name', 'value': ' '}]*3,
])
def test_form_requires_exactly_three_distinct_approved_fields(client, fields):
    assert form(client, fields).status_code == 422
    assert not client.get('/api/session').json()['verified']


def test_form_mixed_identity_generic_failure_then_explicit_correction(client):
    fields = [{'field': 'name', 'value': 'Margaret Chen'}, {'field': 'dob', 'value': '1985-03-15'},
              {'field': 'email', 'value': Fixtures().person('P7').email}]
    result = form(client, fields).json()
    assert not result['verified'] and result['verification']['count'] == 0
    assert result['verification']['fields'] == [] and not result['choices']
    assert not any(e['code'] == 'CLAIMS_READ' for e in result['events'])
    fields[-1]['value'] = Fixtures().person('P9').email
    assert form(client, fields).json()['verified']


def test_form_dob_correction_answers_original_pending_payment(client):
    assert not send(client, 'What is the payment for CL-2048?').json()['verified']
    fields = [{'field': 'name', 'value': 'Margaret Chen'}, {'field': 'dob', 'value': '1985-03-16'},
              {'field': 'phone', 'value': Fixtures().person('P9').phone}]
    wrong = form(client, fields).json()
    assert not wrong['verified'] and not any(e['code'] == 'CLAIMS_READ' for e in wrong['events'])
    fields[1]['value'] = '1985-03-15'
    result = form(client, fields).json()
    assert result['verified'] and result['case_id'] == 'CL-2048'
    assert 'finalized insurer payment for CL-2048 is $0.00' in result['messages'][-1]['text']


def test_form_preserves_representative_authorization_and_limits(client):
    send(client, 'I am calling on behalf of my mother.')
    result = form(client).json()
    assert result['verification']['representative'] and not result['verified']
    assert any(e['code'] == 'REPRESENTATIVE_BLOCKED' for e in result['events'])
    for _ in range(5): form(client)
    assert form(client).status_code == 429


def test_form_csrf_stale_version_and_unknown_keys(client):
    client.headers['x-csrf-token'] = 'stale'
    assert form(client).status_code == 403
    client.headers['x-csrf-token'] = client.get('/api/session').json()['csrf']
    send(client, 'Hello')
    assert form(client, version=0).status_code == 409
    assert form(client, grant={'approved': True}).status_code == 422


def test_form_avoids_model_calls_and_requires_correct_identifier_type(tmp_path):
    class Unavailable(ScriptedInterpreter):
        async def interpret(self, *args):
            raise AssertionError('Form must not call any model')
    with TestClient(create_app(tmp_path, Unavailable(), clock=lambda: NOW)) as c:
        s = c.post('/api/session').json()
        c.headers['x-csrf-token'] = s['csrf']
        p = Fixtures().person('P13')
        fields = [{'field': 'name', 'value': p.name}, {'field': 'email', 'value': p.email},
                  {'field': 'id_last4', 'value': p.id_last4, 'identifier_type': 'ssn_last4'}]
        assert not form(c, fields).json()['verified']
        fields[-1]['identifier_type'] = 'national_id_last4'
        assert form(c, fields).json()['verified']
        assert send(c, 'transfer me').json()['assistance_paused']
        assert send(c, 'yes').status_code == 409
        assert not send(c, 'Return to chatbot').json()['assistance_paused']


def test_human_recovery_after_identity_lockout_does_not_call_model(client):
    for _ in range(6): send(client, 'My name is Someone Else.')
    assert send(client, 'What is the payment?').status_code == 429
    for text in ('transfer me', 'okay transfer me'):
        result = send(client, text)
        assert result.status_code == 200 and result.json()['assistance_paused']
    assert send(client, 'yes').status_code == 409
    result = send(client, 'Return to chatbot').json()
    assert not result['assistance_paused'] and not result['verified']
    assert not any(e['code'] == 'CLAIMS_READ' for e in result['events'])
    assert send(client, 'My name is Margaret Chen.').status_code == 429


@pytest.mark.parametrize('opening', [
    'my name is margaret chen, my DOB is 1985-03-15 and my phone is {phone}.',
    'I’m Margaret Chen. My date of birth is March 15, 1985 and my phone is {phone}.',
    "I'm Margaret Chen; DOB Mar 15, 1985; telephone {phone}.",
    'Full name: Margaret Chen; DOB 1985-03-15; phone {phone}.',
])
def test_natural_name_dob_phone_scripted(opening):
    c, s = Controller(Fixtures()), Session()
    text = opening.format(phone=c.f.person('P9').phone)
    i, _ = asyncio.run(ScriptedInterpreter().interpret(text, s))
    assert {x.field for x in i.identity} == {'name', 'dob', 'phone'}
    c.answer(s, text, i, NOW, 'natural')
    assert s.party_id == 'P9'


def test_live_extraction_contract_accepts_normalization_but_not_invented_values():
    async def run():
        c, s = Controller(Fixtures()), Session()
        phone = c.f.person('P9').phone
        text = f'my name is margaret chen, my DOB is March 15, 1985 and my phone is {phone}.'
        proposal = Interpretation(identity=[Candidate(field=k, value=v, source=source) for k, v, source in [
            ('name', 'margaret chen', 'margaret chen'), ('dob', '1985-03-15', 'March 15, 1985'), ('phone', phone, phone)]])
        adapter = LiveInterpreter('mock-key')
        await adapter.client.close()
        parse = AsyncMock(return_value=SimpleNamespace(output_parsed=proposal, usage=SimpleNamespace(total_tokens=50)))
        adapter.client = SimpleNamespace(responses=SimpleNamespace(parse=parse))
        i, _ = await adapter.interpret(text, s)
        c.answer(s, text, i, NOW, 'live-contract')
        assert s.party_id == 'P9'
        assert 'SSN is optional' in parse.call_args.kwargs['instructions'] == INSTRUCTIONS
        forged = proposal.model_copy(deep=True)
        forged.identity[-1].source = 'not supplied'
        fresh = Session()
        c.answer(fresh, text, forged, NOW, 'forged')
        assert not fresh.party_id
    asyncio.run(run())


def test_numeric_dob_clarification_and_refusal_recovery(client):
    result = send(client, 'My name is Margaret Chen, DOB 03/04/1985.').json()
    assert not result['verified'] and 'YYYY-MM-DD' in result['messages'][-1]['text']
    result = send(client, 'I don’t want to share my SSN.').json()
    assert 'Full name + DOB' in result['messages'][-1]['text']
    assert 'SSN details' in result['messages'][-1]['text'] and not result['verified']
    result = send(client, 'Hello').json()
    assert 'ambiguous or contradictory' in result['messages'][-1]['text']
    assert 'approved ID last four' not in result['messages'][-1]['text']


@pytest.mark.parametrize('authorized', [False, True])
def test_human_pause_acknowledged_once_preserves_context_until_explicit_return(authorized):
    c = Controller(Fixtures())
    s = verified(c) if authorized else Session(hints={'month': 1})
    if authorized:
        c.preview(s, c.f.claim(s, s.case_id, NOW), '', NOW)
    summary = s.summary
    before = (s.party_id, s.case_id, s.hints.copy())
    for n, text in enumerate(['transfer me', 'yes', 'okay transfer me', 'What is the payment?', 'no AI please']):
        i, _ = asyncio.run(ScriptedInterpreter().interpret(text, s))
        c.answer(s, text, i, NOW + n, str(n))
    assert s.assistance_paused and s.human_offered
    assert sum(e.code == 'HUMAN_ASSISTANCE_REQUESTED' for e in s.events) == 1
    assert sum('Chat assistance is paused' in m.text for m in s.messages) == 1
    assert (s.party_id, s.case_id, s.hints) == before
    assert s.summary is summary and not any(e.code == 'EMAIL_SIMULATED' for e in s.events)
    assert s.turns == (6 if authorized else 5)
    c.answer(s, 'Return to chatbot', Interpretation(), NOW + 6, 'resume')
    assert not s.assistance_paused and (s.party_id, s.case_id, s.hints) == before
    assert s.events[-1].code == 'CHAT_RESUMED'


def test_session_rate_limit_preserves_current_session_and_has_real_retry_window(tmp_path):
    now = [NOW + 1]
    app = create_app(tmp_path, ScriptedInterpreter(), clock=lambda: now[0])
    with TestClient(app) as c:
        for _ in range(12): assert c.post('/api/session').status_code == 200
        before = c.get('/api/session').json()
        response = c.post('/api/session')
        assert response.status_code == 429
        assert '12 per hour' in response.json()['detail'] and 'Refreshing will not reset' in response.json()['detail']
        assert int(response.headers['retry-after']) == 3599
        assert c.get('/api/session').json()['csrf'] == before['csrf']
        now[0] += 3600
        assert c.post('/api/session').status_code == 200
        now[0] += 86401
        assert c.get('/api/session').status_code == 401


def test_stale_tab_csrf_and_version_are_reproducible(client):
    before = client.get('/api/session').json()
    fresh = client.post('/api/session').json()
    assert form(client).status_code == 403
    client.headers['x-csrf-token'] = fresh['csrf']
    send(client, 'Hello')
    assert form(client, version=before['version']).status_code == 409

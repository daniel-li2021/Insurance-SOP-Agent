"""Independent review regressions: authorization, disclosure, and summary lifetime."""
from uuid import uuid4
import asyncio

import pytest
from fastapi.testclient import TestClient

from backend.controller import Controller
from backend.fixtures import Fixtures
from backend.interpreter import ScriptedInterpreter
from backend.main import create_app
from backend.models import Interpretation, Session
from tests.test_controller import NOW, identity, verified
from tests.test_api import send


def test_failed_identity_does_not_reveal_partial_matches():
    c = Controller(Fixtures())
    views = []
    for name in ('Margaret Chen', 'Someone Else'):
        s = c.answer(Session(), name, Interpretation(identity=identity(name=name)), NOW, 'a')
        v = c.view(s, NOW)
        views.append((v['verification'], v['messages'][-1]['text'], v['events'], v['unresolved']))
    assert views[0] == views[1]
    assert views[0][0]['count'] == 0


def test_redaction_is_independent_of_fixture_membership():
    c = Controller(Fixtures())
    assert c.redact('My name is Margaret Chen;', Interpretation()) == c.redact('My name is Someone Else;', Interpretation())
    # Unlabelled strings must not be transformed based on whether a fixture contains them.
    for value in ('4472', '9180', '1234'):
        assert c.redact(value, Interpretation()) == value
    value = 'DOB March 15, 1985, national ID 4472, policy POL-9921'
    redacted = c.redact(value, Interpretation())
    assert not any(pii in redacted for pii in ('March 15, 1985', '4472', 'POL-9921'))


@pytest.mark.parametrize('followup', [Interpretation(topics=['payment']), Interpretation(case_id='CL-2011', topics=['status'])])
def test_sent_summary_invalidated_by_further_conversation(followup):
    c = Controller(Fixtures())
    s = verified(c)
    c.preview(s, c.f.claim(s, s.case_id, NOW), '', NOW)
    old = s.summary.id
    c.email(s, old, 'send', NOW + 1)
    c.answer(s, 'Discuss the claim again', followup, NOW + 2, 'b')
    assert s.summary is None
    with pytest.raises(ValueError):
        c.email(s, old, 'send', NOW + 3)
    assert sum(e.code == 'EMAIL_SIMULATED' for e in s.events) == 1
    c.preview(s, c.f.claim(s, s.case_id, NOW + 3), '', NOW + 3)
    assert s.summary.id != old and s.summary.status == 'offered' and s.summary.receipt is None


def test_policyholder_subject_cannot_be_treated_as_caller():
    c = Controller(Fixtures())
    candidates = [x.model_copy(update={'subject': 'policyholder'}) for x in identity(
        name='Margaret Chen', dob='1985-03-15', id_last4='4472')]
    s = c.answer(Session(), 'My wife is Margaret Chen, born 1985-03-15, ID 4472',
                 Interpretation(identity=candidates, intent='status_inquiry'), NOW, 'a')
    assert s.representative and not s.party_id
    assert not any(e.code == 'CLAIMS_READ' for e in s.events)


def test_expiry_does_not_reuse_old_claim_hints_for_another_identity():
    c = Controller(Fixtures())
    s = verified(c)
    c.expire(s, NOW + 901)
    assert not s.hints and s.intent == 'none'
    c.answer(s, 'Ava Lopez 1990-08-21 9180', Interpretation(identity=identity(
        name='Ava Lopez', dob='1990-08-21', id_last4='9180')), NOW + 902, 'b')
    assert s.party_id == 'P7' and s.phase == 'RESOLVE_INTENT'
    assert 'CL-2048' not in str(c.view(s, NOW + 902))


def test_view_honors_representative_grant_scope():
    c = Controller(Fixtures())
    s = verified(c)
    s.representative = True
    s.grant = {'principal_verified': True, 'party_id': 'P9', 'expires_at': NOW + 800, 'scopes': []}
    view = c.view(s, NOW)
    assert not view['verified'] and not view['case_id']
    assert not any(m['protected'] for m in view['messages'])


def test_claim_deadline_is_not_a_birth_date_correction():
    c = Controller(Fixtures())
    s = verified(c)
    text = 'The appeal deadline was March 18, 2026. What can I do now?'
    interpreted, _ = asyncio.run(ScriptedInterpreter().interpret(text, s))
    c.answer(s, text, interpreted, NOW + 1, 'b')
    assert not interpreted.identity
    assert s.party_id == 'P9' and s.case_id == 'CL-2048'
    assert 'has passed' in s.messages[-1].text


@pytest.mark.parametrize('text', [
    'My claim date is March 18, 2026; my DOB is 1985-03-15.',
    '1985-03-15',
    'Actually 1985-03-15',
])
def test_scripted_birth_date_keeps_explicit_and_short_identity_answers(text):
    s = Session()
    s.identity = {'dob': identity(dob='1985-03-16')[0]}
    interpreted, _ = asyncio.run(ScriptedInterpreter().interpret(text, s))
    assert [(c.field, c.value) for c in interpreted.identity] == [('dob', '1985-03-15')]


def test_identity_lockout_and_client_limits_survive_reset(tmp_path):
    with TestClient(create_app(tmp_path, ScriptedInterpreter(), clock=lambda: NOW)) as client:
        s = client.post('/api/session').json()
        client.headers['x-csrf-token'] = s['csrf']
        for _ in range(6):
            assert send(client, 'My name is Someone Else.').status_code == 200
        assert send(client, 'My name is Margaret Chen.').status_code == 429
        s = client.post('/api/session').json()
        client.headers['x-csrf-token'] = s['csrf']
        # Reset renews the per-session allowance, but not the client turn bucket.
        for _ in range(24):
            assert send(client, 'Hello').status_code == 200
        assert send(client, 'Hello').status_code == 429
        assert client.post('/api/session', headers={'x-forwarded-for': '198.51.100.4'}).status_code == 200
        # Changing a forwarded header cannot clear the transport-address limit.
        client.headers['x-csrf-token'] = client.get('/api/session').json()['csrf']
        assert send(client, 'Hello').status_code == 429


def test_expired_duplicate_never_replays_private_snapshot(tmp_path):
    now = [NOW]
    app = create_app(tmp_path, ScriptedInterpreter(), clock=lambda: now[0])
    with TestClient(app) as client:
        s = client.post('/api/session').json()
        client.headers['x-csrf-token'] = s['csrf']
        body = {'text': 'My name is Margaret Chen, DOB 1985-03-15, SSN last four 4472. My denied healthcare claim from January.',
                'version': 0, 'request_id': str(uuid4())}
        assert client.post('/api/turn', json=body).json()['verified']
        now[0] += 901
        replay = client.post('/api/turn', json=body).json()
        assert not replay['verified'] and replay['summary'] is None
        assert not any(m['protected'] for m in replay['messages'])
        assert 'CL-2048' not in str(replay)
        now[0] += 86401
        assert client.get('/api/session').status_code == 401
        assert client.post('/api/turn', json=body).status_code == 401

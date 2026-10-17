"""Focused regressions for caller-role changes and third-party identity."""
import asyncio
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from backend.controller import Controller
from backend.fixtures import Fixtures
from backend.interpreter import ScriptedInterpreter
from backend.main import create_app
from backend.models import Interpretation, Session
from tests.test_controller import NOW, verified
from tests.test_api import send


@pytest.mark.parametrize('already_paused', [False, True])
def test_role_change_revokes_access_before_pause_control(already_paused):
    controller = Controller(Fixtures())
    state = verified(controller)
    controller.preview(state, controller.f.claim(state, state.case_id, NOW), '', NOW)
    summary_id = state.summary.id
    state.assistance_paused = already_paused
    controller.answer(state, "I'm David, her son. I want a human.",
                      Interpretation(action='human', representative=True), NOW + 1, 'role-change')
    view = controller.view(state, NOW + 1)
    assert state.representative and view['assistance_paused']
    assert not view['verified'] and view['summary'] is None
    assert 'CL-2048' not in str(view)
    assert not any(message['protected'] for message in view['messages'])
    with pytest.raises(PermissionError):
        controller.email(state, summary_id, 'send', NOW + 2)


@pytest.mark.parametrize('opening', [
    'I am helping my friend. Her full name is Margaret Chen',
    'I am calling for my client. Full name is Margaret Chen',
    'His full name is Margaret Chen',
])
def test_explicit_third_party_identity_cannot_open_claims(opening):
    controller = Controller(Fixtures())
    state = Session()
    text = opening + ', DOB 1985-03-15, SSN last four 4472. What is the status of denied healthcare claim from January?'
    interpreted, _ = asyncio.run(ScriptedInterpreter().interpret(text, state))
    controller.answer(state, text, interpreted, NOW, 'third-party')
    assert state.representative and not state.party_id
    assert not any(event.code == 'CLAIMS_READ' for event in state.events)
    assert 'CL-2048' not in str(controller.view(state, NOW))


def test_incidental_friend_mention_does_not_revoke_self_service():
    controller = Controller(Fixtures())
    state = verified(controller)
    controller.answer(state, 'My friend suggested I ask about the payment.',
                      Interpretation(topics=['payment']), NOW + 1, 'self-service')
    assert state.party_id == 'P9' and not state.representative


@pytest.mark.parametrize('already_paused', [False, True])
def test_conflicting_identity_revokes_access_during_assistance_pause(already_paused):
    controller = Controller(Fixtures())
    state = verified(controller)
    controller.preview(state, controller.f.claim(state, state.case_id, NOW), '', NOW)
    summary_id = state.summary.id
    state.assistance_paused = already_paused
    # Literal extraction must protect this boundary even if the model omits identity.
    controller.answer(state, 'My name is Ma Tian. I want a human.',
                      Interpretation(action='human'), NOW + 1, 'identity-change')
    view = controller.view(state, NOW + 1)
    assert view['assistance_paused'] and not view['verified']
    assert view['summary'] is None and 'CL-2048' not in str(view)
    with pytest.raises(PermissionError):
        controller.email(state, summary_id, 'send', NOW + 2)


def test_http_pause_role_change_revokes_summary_and_send(tmp_path):
    with TestClient(create_app(tmp_path, ScriptedInterpreter(), clock=lambda: NOW)) as client:
        state = client.post('/api/session').json()
        client.headers['x-csrf-token'] = state['csrf']
        state = send(client, client.get('/api/demo-starter').json()['opening']).json()
        state = client.post('/api/action', json={
            'action': 'preview', 'version': state['version'], 'request_id': str(uuid4()),
        }).json()
        summary_id = state['summary']['id']
        response = send(client, "I'm David, her son. I want a human.")
        assert response.status_code == 200
        state = response.json()
        assert not state['verified'] and state['summary'] is None
        assert state['verification']['representative'] and state['assistance_paused']
        assert 'CL-2048' not in str(state)
        assert client.post('/api/action', json={
            'action': 'send', 'summary_id': summary_id,
            'version': state['version'], 'request_id': str(uuid4()),
        }).status_code == 403

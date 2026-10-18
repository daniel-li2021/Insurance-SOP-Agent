"""Caller-role and explicit identifier-type regressions; synthetic, offline only."""
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from backend.controller import Controller
from backend.fixtures import Fixtures
from backend.interpreter import ScriptedInterpreter
from backend.main import create_app
from backend.models import Candidate, Interpretation, Session
from tests.test_api import send
from tests.test_controller import NOW


@pytest.mark.parametrize('role', [
    'I am representing Margaret Chen.',
    'I am the policyholder’s attorney.',
    'I am her representative.',
    'I am a representative.',
])
def test_explicit_caller_role_cannot_use_policyholder_identity(tmp_path, role):
    with TestClient(create_app(tmp_path, ScriptedInterpreter(), clock=lambda: NOW)) as client:
        state = client.post('/api/session').json()
        client.headers['x-csrf-token'] = state['csrf']
        state = send(client, role + ' Full name is Margaret Chen, DOB 1985-03-15, '
                     'SSN last four 4472. What is the status of denied healthcare claim from January?').json()
        assert state['verification']['representative'] and not state['verified']
        assert state['case_id'] is None and state['summary'] is None
        assert not any(e['code'] == 'CLAIMS_READ' for e in state['events'])
        assert 'CL-2048' not in str(state)


@pytest.mark.parametrize('label', ['national ID last four', 'national ID’s last 4 digits',
                                  'last four of my national ID'])
def test_explicit_national_id_cannot_match_ssn_fixture(tmp_path, label):
    with TestClient(create_app(tmp_path, ScriptedInterpreter(), clock=lambda: NOW)) as client:
        state = client.post('/api/session').json()
        client.headers['x-csrf-token'] = state['csrf']
        state = send(client, f'My name is Margaret Chen, DOB 1985-03-15, {label} 4472. '
                     'What is the status of denied healthcare claim from January?').json()
        assert not state['verified'] and state['case_id'] is None
        assert not any(e['code'] == 'CLAIMS_READ' for e in state['events'])


@pytest.mark.parametrize('model_type', ['unspecified', 'ssn_last4'])
@pytest.mark.parametrize('label', ['national ID', 'national ID last four'])
def test_model_cannot_erase_or_contradict_literal_id_type(model_type, label):
    controller, state = Controller(Fixtures()), Session()
    text = f'My name is Margaret Chen, DOB 1985-03-15, {label} 4472.'
    interpreted = Interpretation(identity=[Candidate(field='id_last4', value='4472', source='4472',
                                                    identifier_type=model_type)])
    controller.answer(state, text, interpreted, NOW, str(uuid4()))
    assert not state.party_id
    assert not any(e.code == 'CLAIMS_READ' for e in state.events)
    if model_type == 'unspecified':
        assert state.identity['id_last4'].identifier_type == 'national_id_last4'
    else:
        assert 'id_last4' in state.conflicts


@pytest.mark.parametrize('identity_text', [
    'My name is Margaret Chen, DOB 1985-03-15, SSN last four 4472.',
    'My name is Margaret Chen, DOB 1985-03-15, last four 4472.',
    'My name is Yaven Li, email yawen.li@example.com, national ID last four 5317.',
])
def test_matching_id_types_and_unspecified_last_four_still_verify(identity_text):
    controller, state = Controller(Fixtures()), Session()
    controller.answer(state, identity_text, Interpretation(), NOW, str(uuid4()))
    assert state.party_id


def test_changing_explicit_id_type_requires_a_correction_even_with_same_digits():
    controller, state = Controller(Fixtures()), Session()
    controller.answer(state, 'My name is Margaret Chen, DOB 1985-03-15, national ID last four 4472.',
                      Interpretation(), NOW, 'national-id')
    assert not state.party_id
    controller.answer(state, 'last four 4472.', Interpretation(), NOW + 1, 'unspecified-id')
    assert not state.party_id and state.identity['id_last4'].identifier_type == 'national_id_last4'
    controller.answer(state, 'SSN last four 4472.', Interpretation(), NOW + 1, 'ssn')
    assert not state.party_id and 'id_last4' in state.conflicts
    controller.answer(state, 'Actually SSN last four 4472.', Interpretation(correction=True), NOW + 2, 'corrected')
    assert state.party_id == 'P9' and not state.conflicts

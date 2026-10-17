"""Literal normalization, role isolation, and grounding regressions; no paid calls."""
import asyncio
from uuid import uuid4

import pytest

from backend.controller import Controller
from backend.fixtures import Fixtures
from backend.identity import normalize, supported
from backend.interpreter import ScriptedInterpreter
from backend.models import Candidate, Interpretation, Session
from tests.test_api import client, send
from tests.test_controller import NOW
from tests.test_ux_recovery import form


@pytest.mark.parametrize('dob', ['1985-03-15', '1985/03/15', '03/15/1985', '3-15-1985',
                                  '03.15.1985', 'March 15,1985', 'March 15th, 1985',
                                  'Mar. 15, 1985', '15 March 1985'])
@pytest.mark.parametrize('introduction', ['name: Margaret Chen', 'My name is Margaret Chen', "I'm Margaret Chen"])
def test_common_formats_verify_without_model_dependency(dob, introduction):
    c, s = Controller(Fixtures()), Session()
    text = f'{introduction}; DOB: {dob}; phone: +1 (650) 521-2836'
    c.answer(s, text, Interpretation(), NOW, 'literal')
    assert s.party_id == 'P9'
    assert all(value not in str(c.view(s, NOW)) for value in ('Margaret Chen', dob, '521-2836'))


@pytest.mark.parametrize('phone', ['6505212836', '650-521-2836', '(650) 521 2836',
                                    '+16505212836', '+1 650 521 2836', '1-650-521-2836'])
def test_phone_formats(phone):
    assert normalize('phone', phone) == normalize('phone', Fixtures().person('P9').phone)


@pytest.mark.parametrize('value', ['03/04/1985', '04/03/1985', '02/30/1985', '15/03/1985'])
def test_numeric_date_ambiguity_or_invalidity_cannot_be_normalized_by_model(value):
    assert normalize('dob', value) == 'invalid-date'
    assert not supported(Candidate(field='dob', value='1985-03-15', source=value), value)
    c, s = Controller(Fixtures()), Session()
    text = f'name: Margaret Chen; DOB {value}; phone 6505212836; SSN ending in 4472'
    c.answer(s, text, Interpretation(), NOW, 'ambiguous')
    assert not s.party_id and 'dob' in s.conflicts
    assert not any(e.code == 'CLAIMS_READ' for e in s.events)
    c.answer(s, 'Actually DOB March 15, 1985', Interpretation(correction=True), NOW, 'corrected')
    assert s.party_id == 'P9'


def test_accumulated_email_id_and_contradictions(client):
    for text in ['My name is Margaret Chen', 'My email is   MARGARET@EMAIL.COM  ', 'SSN ending in 4472']:
        response = send(client, text).json()
    assert response['verified']
    assert all(value not in str(response) for value in ('4472', 'MARGARET@EMAIL.COM', 'Margaret Chen'))
    response = send(client, 'Actually phone 6505212836 or 2025550000').json()
    assert not response['verified'] and 'contradictory' in response['messages'][-1]['text']
    response = send(client, 'Actually phone 6505212836').json()
    assert response['verified']


def test_literal_extraction_cannot_hide_a_model_contradiction():
    c, s = Controller(Fixtures()), Session()
    text = 'name: Margaret Chen; DOB 1985-03-15; phone 6505212836 or 2025550000'
    i = Interpretation(identity=[Candidate(field='phone', value='6505212836', source='6505212836')], correction=True)
    c.answer(s, text, i, NOW, 'conflict')
    assert not s.party_id and s.conflicts == ['phone']


def test_no_fuzzy_name_or_phone_matching(client):
    assert not form(client, [{'field':'name','value':'Margret Chen'}, {'field':'dob','value':'1985-03-15'},
                             {'field':'phone','value':'6505212836'}]).json()['verified']
    assert not form(client, [{'field':'name','value':'Margaret Chen'}, {'field':'dob','value':'1985-03-15'},
                             {'field':'phone','value':'6505212836 ext 123'}]).json()['verified']


def test_representative_mode_is_sticky_and_new_session_is_self_service(client):
    assert send(client, 'I am calling on behalf of my mother.').json()['verification']['representative']
    response = form(client).json()
    assert not response['verified'] and response['verification']['representative']
    assert 'Representative Mode remains active' in response['messages'][-1]['text']
    assert not any(e['code'] == 'CLAIMS_READ' for e in response['events'])
    fresh = client.post('/api/session').json()
    client.headers['x-csrf-token'] = fresh['csrf']
    assert not fresh['verification']['representative'] and not fresh['messages']
    assert form(client).json()['verified']


def test_pause_rejects_submission_without_consuming_state_and_resumes(client):
    form(client)
    paused = send(client, 'transfer me').json()
    response = send(client, 'What is the payment?')
    assert response.status_code == 409 and 'Return to chatbot' in response.json()['detail']
    assert client.get('/api/session').json() == paused
    resumed = send(client, 'Return to chatbot').json()
    assert resumed['verified'] and not resumed['assistance_paused']


def test_demo_details_are_fixture_backed_and_do_not_authorize(client):
    p = Fixtures().person('P9')
    before = client.get('/api/session').json()
    demo = client.get('/api/demo-starter').json()
    assert demo['verification_details'] == {'name':p.name, 'dob':str(p.dob), 'phone':p.phone}
    assert not before['verified'] and before == client.get('/api/session').json()


def test_grounded_responses_keep_message_and_audit_references(client):
    response = send(client, 'name: Margaret Chen; DOB 1985-03-15; phone 6505212836. What documents are needed for CL-2048?').json()
    refs = response['messages'][-1]['references']
    assert any('claims.json#CL-2048' == r for r in refs)
    assert any(r.startswith('required_document_guideline.json') for r in refs)
    assert next(e['references'] for e in reversed(response['events']) if e['code'] == 'GROUNDED_RESPONSE') == refs

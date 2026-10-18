"""Confirmed conversational recovery and summary regressions; no model calls."""
import asyncio

import pytest

from backend.controller import Controller
from backend.fixtures import Fixtures
from backend.interpreter import ScriptedInterpreter, human_requested
from backend.models import Interpretation, Session
from tests.test_controller import NOW, identity, verified


def turn(controller, session, text):
    proposal, _ = asyncio.run(ScriptedInterpreter().interpret(text, session))
    controller.answer(session, text, proposal, NOW + session.turns, str(session.turns))
    return proposal


@pytest.mark.parametrize('text', [
    'I do not want a human. Please explain payment.',
    "I don't want to speak with a human representative. What is the payment?",
    'Do not transfer me. Please explain payment.',
    'What can a human representative do about the payment?',
    'I want to know whether human review is possible.',
    'I would not like to speak to a human.',
])
def test_declining_or_discussing_humans_does_not_pause_chat(text):
    controller = Controller(Fixtures())
    session = verified(controller)
    proposal = turn(controller, session, text)
    assert proposal.action != 'human' and not proposal.representative
    assert not session.assistance_paused and session.party_id == 'P9'
    assert not session.representative


@pytest.mark.parametrize('text', [
    'human please', 'I need a human', 'Please transfer me',
    'I would like to speak to an agent', 'Can I talk with a person?',
    'Can I talk to a customer service representative?',
    'no AI please', 'Stop this chatbot', 'I do not want to talk to AI',
    "I don't want a human, but I need an agent.",
])
def test_positive_human_and_stop_ai_requests_still_pause(text):
    assert human_requested(text)
    controller = Controller(Fixtures())
    session = verified(controller)
    turn(controller, session, text)
    assert session.assistance_paused


def test_human_representative_pause_and_return_preserve_self_service():
    controller = Controller(Fixtures())
    session = verified(controller)
    turn(controller, session, 'Please transfer me to a human representative.')
    assert session.assistance_paused and session.party_id == 'P9'
    assert not session.representative
    turn(controller, session, 'Return to chatbot')
    turn(controller, session, 'What is the payment?')
    assert not session.assistance_paused and session.party_id == 'P9'
    assert '$0.00' in session.messages[-1].text


def test_controller_does_not_override_continue_for_declined_human():
    controller = Controller(Fixtures())
    session = verified(controller)
    controller.answer(session, 'I do not want a human. Explain payment.',
                      Interpretation(topics=['payment']), NOW + 1, 'payment')
    assert not session.assistance_paused and '$0.00' in session.messages[-1].text


def test_exhausted_document_summary_survives_other_claim_and_serialization():
    controller = Controller(Fixtures())
    session = verified(controller)
    turn(controller, session, 'The hospital and doctor cannot provide the pathology report. I have no alternatives.')
    assert 'manual options' in session.messages[-1].text
    turn(controller, session, 'What is the payment for CL-2011?')
    session = Session.model_validate_json(session.model_dump_json())
    turn(controller, session, 'Summary please')
    denied, closed = session.summary.cases
    assert denied.case_id == 'CL-2048' and 'You reported' in denied.next_steps
    assert 'manual options' in denied.next_steps and 'replacement' not in denied.next_steps
    assert closed.case_id == 'CL-2011' and 'manual options' not in closed.next_steps
    assert not any(event.code == 'EMAIL_SIMULATED' for event in session.events)


def test_early_document_exhaustion_is_included_in_immediate_summary():
    controller, session = Controller(Fixtures()), Session()
    controller.answer(session, 'Margaret Chen denied healthcare January; no alternatives.',
                      Interpretation(identity=identity(name='Margaret Chen'), intent='denial_question',
                                     case_type='healthcare', month=1, status='denied',
                                     alternatives_exhausted=True), NOW, 'early')
    controller.answer(session, 'DOB 1985-03-15, SSN last four 4472. Summary please.',
                      Interpretation(identity=identity(dob='1985-03-15', id_last4='4472'), action='wrap_up'),
                      NOW + 1, 'verify-summary')
    assert session.summary and 'manual options' in session.summary.cases[0].next_steps
    assert 'replacement' not in session.summary.cases[0].next_steps


@pytest.mark.parametrize('boundary', ['expiry', 'identity'])
def test_exhausted_document_memory_clears_with_authorization(boundary):
    controller = Controller(Fixtures())
    session = verified(controller)
    turn(controller, session, 'The hospital cannot provide the pathology report. I have no alternatives.')
    assert session.exhausted_document_cases == ['CL-2048']
    if boundary == 'expiry':
        controller.expire(session, NOW + 901)
    else:
        controller.answer(session, 'Actually DOB 1985-03-16',
                          Interpretation(identity=identity(dob='1985-03-16'), correction=True),
                          NOW + 2, 'recheck')
    assert not session.party_id and not session.exhausted_document_cases

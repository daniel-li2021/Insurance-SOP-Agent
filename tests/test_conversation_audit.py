"""Risk review regressions for early context and summaries spanning claims."""
import pytest

from backend.controller import Controller
from backend.fixtures import Fixtures
from backend.models import Interpretation, Session
from tests.test_controller import NOW, identity, verified


def answer(controller, session, text, **fields):
    return controller.answer(session, text, Interpretation(**fields), NOW + session.turns, str(session.turns))


def test_document_alternatives_exhausted_before_verification_are_remembered():
    controller, session = Controller(Fixtures()), Session()
    answer(controller, session,
           'My name is Margaret Chen. My denied healthcare claim is from January. '
           'The hospital cannot provide the pathology report and I have no alternatives.',
           identity=identity(name='Margaret Chen'), intent='document_submission',
           case_type='healthcare', month=1, status='denied', topics=['alternatives'],
           documents=['pathology report'], alternatives_exhausted=True)
    assert not session.party_id and not any(e.code == 'CLAIMS_READ' for e in session.events)
    answer(controller, session, 'DOB 1985-03-15, SSN last four 4472',
           identity=identity(dob='1985-03-15', id_last4='4472'))
    assert session.case_id == 'CL-2048'
    response = session.messages[-1].text
    assert 'manual options' in response and response.count('human claims representative') == 1
    assert 'replacement copy' not in response
    # Early context is consumed once, not imposed on every later question.
    answer(controller, session, 'I found the pathology report. What format should it be?',
           topics=['format'], documents=['pathology report'])
    assert 'complete and fully readable' in session.messages[-1].text
    assert 'manual options' not in session.messages[-1].text


def test_revisiting_claim_preserves_its_unresolved_receipt_question():
    controller = Controller(Fixtures())
    session = verified(controller)
    answer(controller, session, 'Can you confirm receipt of the documents?', topics=['receipt'])
    answer(controller, session, 'What is payment for CL-2011?', case_id='CL-2011', topics=['payment'])
    answer(controller, session, 'What is payment for CL-2048?', case_id='CL-2048', topics=['payment'])
    answer(controller, session, 'Summary please', action='wrap_up')
    denied, closed = session.summary.cases
    assert denied.case_id == 'CL-2048' and denied.unresolved == 'Document receipt has not been confirmed.'
    assert closed.case_id == 'CL-2011' and closed.unresolved == ''
    assert not any(event.code == 'EMAIL_SIMULATED' for event in session.events)


def test_case_switch_and_wrap_up_include_requested_current_claim():
    controller = Controller(Fixtures())
    session = verified(controller)
    answer(controller, session, 'Please summarize CL-2011', case_id='CL-2011', action='wrap_up')
    assert session.case_id == 'CL-2011'
    assert [case.case_id for case in session.summary.cases] == ['CL-2048', 'CL-2011']
    assert session.summary.cases[1].payment == '$780.00'
    assert session.summary.status == 'offered'
    assert not any(event.code == 'EMAIL_SIMULATED' for event in session.events)


@pytest.mark.parametrize('boundary', ['expiry', 'identity', 'case'])
def test_pending_document_exhaustion_cannot_cross_reset_boundaries(boundary):
    controller = Controller(Fixtures())
    session = verified(controller)
    session.pending_alternatives_exhausted = True
    if boundary == 'expiry':
        controller.expire(session, NOW + 901)
    elif boundary == 'identity':
        answer(controller, session, 'Actually DOB 1985-03-16',
               identity=identity(dob='1985-03-16'), correction=True)
    else:
        answer(controller, session, 'What is payment for CL-2011?', case_id='CL-2011', topics=['payment'])
        assert 'manual options' not in session.messages[-1].text
    assert not session.pending_alternatives_exhausted

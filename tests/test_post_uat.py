"""Post-UAT relevance and summary safety contracts, without model calls."""
import asyncio
from backend.controller import Controller
from backend.fixtures import Fixtures
from backend.interpreter import ScriptedInterpreter, safe_context
from backend.models import Interpretation
from tests.test_controller import NOW, verified


def turn(c, s, text):
    i, _ = asyncio.run(ScriptedInterpreter().interpret(text, s))
    c.answer(s, text, i, NOW + s.turns, str(s.turns))
    return s.messages[-1].text


def test_focused_followups_and_no_old_topic_carryover():
    c = Controller(Fixtures())
    s = verified(c)
    answer = turn(c, s, "I can't get the pathology report. Is there another option?")
    assert 'replacement copy' in answer and 'not confirmation' in answer
    assert 'office note' not in answer and 'March 18' not in answer
    assert len(s.messages[-1].references) == 2
    answer = turn(c, s, 'How much money will I get?')
    assert '$0.00' in answer and '$1,450.00' in answer and 'not a promised payout' in answer
    assert 'appeal' not in answer and 'office note' not in answer and 'fee-schedule' not in answer
    answer = turn(c, s, 'Can I still appeal after the deadline?')
    assert 'has passed' in answer and 'No appeal or transfer' in answer
    assert 'pathology' not in answer and 'less than a week' not in answer
    assert 'created' not in answer


def test_document_pronoun_context_and_detailed_payment():
    c = Controller(Fixtures())
    s = verified(c)
    turn(c, s, 'What format for the pathology report?')
    assert safe_context(s)['recent_document_focus'] == ['pathology report']
    answer = turn(c, s, "What if I can't get it?")
    assert 'replacement copy' in answer and 'office note' not in answer
    answer = turn(c, s, 'Give me all amounts and payment details')
    assert 'Expected reimbursement' in answer and 'fee-schedule' in answer.lower()


def test_empathy_does_not_repeat_on_consecutive_turns():
    c = Controller(Fixtures())
    s = verified(c)
    first = turn(c, s, 'I am worried. How much money will I get?')
    second = turn(c, s, 'Still worried. Can I still appeal after the deadline?')
    assert 'It makes sense' in first and 'It makes sense' not in second


def test_structured_summary_is_per_claim_and_preview_does_not_send():
    c = Controller(Fixtures())
    s = verified(c)
    c.preview(s, c.f.claim(s, s.case_id, NOW), '', NOW)
    old = s.summary.id
    assert not any(e.code == 'EMAIL_SIMULATED' for e in s.events)
    turn(c, s, 'Please discuss CL-2011. What is the payment?')
    assert s.summary is None
    c.preview(s, c.f.claim(s, s.case_id, NOW), '', NOW)
    assert s.summary.id != old and s.summary.status == 'offered'
    denied, closed = s.summary.cases
    assert denied.case_id == 'CL-2048' and denied.payment == '$0.00' and denied.deadline_passed
    assert closed.case_id == 'CL-2011' and closed.payment == '$780.00' and closed.denial_reason is None
    assert closed.appeal_deadline is None and not any(e.code == 'EMAIL_SIMULATED' for e in s.events)
    assert 'Document receipt' in denied.unresolved and len(s.summary.text.split()) < 200

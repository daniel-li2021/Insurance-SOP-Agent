"""Post-UAT relevance and summary safety contracts, without model calls."""
import asyncio
from backend.controller import Controller
from backend.fixtures import Fixtures
from backend.interpreter import ScriptedInterpreter, safe_context
from backend.models import Interpretation, Session
from tests.test_controller import NOW, identity, verified
import pytest


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
    assert any('document_alternative_guidance' in ref for ref in s.messages[-1].references)
    assert not any(e.code == 'EMAIL_SIMULATED' for e in s.events)
    turn(c, s, 'Please discuss CL-2011. What is the payment?')
    assert s.summary is None
    c.preview(s, c.f.claim(s, s.case_id, NOW), '', NOW)
    assert s.summary.id != old and s.summary.status == 'offered'
    denied, closed = s.summary.cases
    assert denied.denial_reason == 'Missing pathology report and treating provider office note.'
    assert denied.case_id == 'CL-2048' and denied.payment == '$0.00' and denied.deadline_passed
    assert closed.case_id == 'CL-2011' and closed.payment == '$780.00' and closed.denial_reason is None
    assert closed.appeal_deadline is None and not any(e.code == 'EMAIL_SIMULATED' for e in s.events)
    assert denied.unresolved == closed.unresolved == ''
    assert 'Still unresolved' not in s.summary.text and len(s.summary.text.split()) < 200


def test_summary_unresolved_only_adds_an_unanswered_receipt_question():
    c = Controller(Fixtures())
    s = verified(c)
    turn(c, s, 'Can you confirm receipt of the documents?')
    c.preview(s, c.f.claim(s, s.case_id, NOW), '', NOW)
    assert s.summary.cases[0].unresolved == 'Document receipt has not been confirmed.'
    assert s.summary.text.count('Still unresolved:') == 1
    assert s.summary.text.count('synthetic summary') == 1


def test_exhausted_documents_give_one_caller_facing_manual_review_referral():
    c = Controller(Fixtures())
    s = verified(c)
    alternatives = turn(c, s, "I can't get the pathology report. Is there another option?")
    assert alternatives.count('replacement copy') == 1
    assert 'human representative' not in alternatives
    answer = c.explain(c.f.claim(s, s.case_id, NOW), ['alternatives', 'appeal'], NOW,
                       exhausted=True, documents=['pathology report'])[0]
    assert answer.count('human claims representative') == 1
    assert 'manual options' in answer and 'has passed' in answer
    assert 'replacement copy' not in answer and 'If the caller' not in answer
    assert 'not confirmation' in answer and 'cannot transfer' in answer
    answer = turn(c, s, 'The hospital and doctor cannot provide the pathology report.')
    assert answer.count('human claims representative') == 1 and 'manual options' in answer
    assert 'replacement copy' not in answer and 'If the caller' not in answer


@pytest.mark.parametrize('topics', [[], ['payment']])
@pytest.mark.parametrize('replace_all_fields', [False, True])
def test_payment_question_survives_wrong_dob_and_correction(topics, replace_all_fields):
    c, s = Controller(Fixtures()), Session()
    c.answer(s, 'What is the payment for CL-2048?', Interpretation(
        intent='payment_question', case_id='CL-2048', topics=topics), NOW, 'question')
    c.answer(s, 'Margaret Chen 1985-03-16 4472', Interpretation(identity=identity(
        name='Margaret Chen', dob='1985-03-16', id_last4='4472')), NOW + 1, 'wrong-dob')
    assert not s.party_id and s.pending_topics == ['payment']
    assert not any(e.code == 'CLAIMS_READ' for e in s.events)
    values = dict(name='Margaret Chen', dob='1985-03-15', id_last4='4472') if replace_all_fields else dict(dob='1985-03-15')
    text = 'Actually ' + ' '.join(values.values())
    c.answer(s, text, Interpretation(identity=identity(**values), correction=True,
                                    topics=['denial']), NOW + 2, 'correction')
    assert s.party_id == 'P9' and s.case_id == 'CL-2048'
    answer = s.messages[-1].text
    assert 'finalized insurer payment for CL-2048 is $0.00' in answer
    assert '$1,450.00' in answer and 'not a promised payout' in answer
    assert not s.pending_topics
    assert s.discussed == ['denial', 'payment']
    followup = turn(c, s, 'Can I still appeal after the deadline?')
    assert 'finalized insurer payment' not in followup


def test_identity_recheck_and_expiry_still_discard_previous_protected_context():
    c = Controller(Fixtures())
    s = verified(c)
    c.preview(s, c.f.claim(s, s.case_id, NOW), '', NOW)
    c.answer(s, 'Actually DOB 1985-03-16', Interpretation(
        identity=identity(dob='1985-03-16'), correction=True), NOW + 1, 'recheck')
    assert not s.party_id and not s.case_id and not s.summary
    assert not s.hints and not s.pending_topics and not s.discussed_by_case
    assert not any(m['protected'] for m in c.view(s, NOW + 1)['messages'])
    s = verified(c)
    s.pending_topics = ['payment']
    c.expire(s, NOW + 901)
    assert not s.party_id and not s.pending_topics and not s.hints

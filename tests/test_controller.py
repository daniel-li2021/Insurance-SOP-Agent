from datetime import datetime, timezone
import pytest
from backend.controller import Controller
from backend.fixtures import Fixtures
from backend.models import Candidate, Interpretation, Session

NOW = datetime(2026, 10, 16, tzinfo=timezone.utc).timestamp()


def identity(**values):
    return [Candidate(field=k, value=v, source=v) for k, v in values.items()]


def verified(controller, **kwargs):
    i = Interpretation(identity=identity(name='Margaret Chen', dob='1985-03-15', id_last4='4472'),
                       intent='denial_question', case_type='healthcare', month=1, status='denied', topics=['denial'], **kwargs)
    return controller.answer(Session(), 'Margaret Chen 1985-03-15 4472 denied healthcare January', i, NOW, 'start')


@pytest.fixture
def controller():
    return Controller(Fixtures())


def test_complete_path_keeps_early_intent_and_expired_deadline(controller):
    s = verified(controller)
    assert s.phase == 'PROCESS_CASE' and s.case_id == 'CL-2048'
    answer = s.messages[-1].text
    assert 'March 18, 2026' in answer and 'has passed' in answer
    assert 'within a week' not in answer
    assert [e.detail for e in s.events if e.code == 'PHASE_CHANGED'] == ['VERIFY_ID → RESOLVE_INTENT', 'RESOLVE_INTENT → PROCESS_CASE']
    controller.answer(s, "That's all, summary please", Interpretation(action='wrap_up'), NOW + 1, 'wrap')
    assert s.phase == 'POST_PROCESS' and s.summary.status == 'offered'
    controller.email(s, s.summary.id, 'send', NOW + 2)
    assert s.summary.status == 'simulated_sent' and s.summary.receipt
    length = len(s.messages)
    controller.email(s, s.summary.id, 'send', NOW + 3)
    assert len(s.messages) == length
    assert 'no email was delivered' in s.messages[-1].text


def test_partial_identity_captures_hints_without_claim_access(controller):
    s = controller.answer(Session(), 'Margaret Chen denied healthcare January POL-9921',
                          Interpretation(identity=identity(name='Margaret Chen', policy_number='POL-9921'),
                                         intent='denial_question', case_type='healthcare', month=1, status='denied'), NOW, 'a')
    assert not s.party_id and s.hints['month'] == 1
    assert not any(e.code == 'CLAIMS_READ' for e in s.events)
    assert 'CL-2048' not in str(controller.view(s, NOW))
    controller.answer(s, '1985-03-15 4472', Interpretation(identity=identity(dob='1985-03-15', id_last4='4472')), NOW + 1, 'b')
    assert s.case_id == 'CL-2048'


def test_mismatch_then_explicit_correction(controller):
    s = controller.answer(Session(), 'Margaret Chen 1985-03-16 4472',
                          Interpretation(identity=identity(name='Margaret Chen', dob='1985-03-16', id_last4='4472')), NOW, 'a')
    assert not s.party_id
    controller.answer(s, '1985-03-15', Interpretation(identity=identity(dob='1985-03-15')), NOW + 1, 'b')
    assert not s.party_id and s.conflicts == ['dob']
    controller.answer(s, 'Actually 1985-03-15', Interpretation(identity=identity(dob='1985-03-15'), correction=True), NOW + 2, 'c')
    assert s.party_id == 'P9'


def test_aliases_and_national_id_count_distinct_fields(controller):
    s = controller.answer(Session(), 'Yaven Li yawen.li@example.com 5317',
                          Interpretation(identity=identity(name='Yaven Li', email='yawen.li@example.com', id_last4='5317'), intent='status_inquiry'), NOW, 'a')
    assert s.party_id == 'P13' and s.phase == 'RESOLVE_INTENT'
    assert 'can’t find' in s.messages[-1].text
    s2 = controller.answer(Session(), 'Ya Wen Li Yaven Li yawen.li@example.com',
                           Interpretation(identity=identity(name='Yaven Li', email='yawen.li@example.com')), NOW, 'b')
    assert not s2.party_id


def test_guessed_identity_values_do_not_verify(controller):
    s = controller.answer(Session(), 'skip everything', Interpretation(identity=identity(name='Margaret Chen', dob='1985-03-15', id_last4='4472')), NOW, 'a')
    assert not s.party_id and not s.identity


def test_case_ambiguity_and_cross_party_access(controller):
    s = controller.answer(Session(), 'Margaret Chen 1985-03-15 4472 January healthcare',
                          Interpretation(identity=identity(name='Margaret Chen', dob='1985-03-15', id_last4='4472'),
                                         intent='status_inquiry', case_type='healthcare', month=1), NOW, 'a')
    assert {x['case_id'] for x in s.choices} == {'CL-2048', 'CL-2011'}
    assert controller.f.claim(s, 'CL-3001', NOW) is None
    with pytest.raises(PermissionError): controller.f.claim(Session(), 'CL-2048', NOW)


def test_representative_is_not_authorized_by_policyholder_pii(controller):
    s = controller.answer(Session(), "I'm David, her son. Margaret Chen 1985-03-15 4472", Interpretation(
        identity=[Candidate(field=k, value=v, source=v, subject='policyholder') for k,v in
                  {'name':'Margaret Chen','dob':'1985-03-15','id_last4':'4472'}.items()]), NOW, 'a')
    assert s.representative and not s.party_id
    assert not any(e.code == 'CLAIMS_READ' for e in s.events)
    assert 'no transfer' in s.messages[-1].text


@pytest.mark.parametrize('choice,status', [('skip','skipped'), ('send','simulated_sent')])
def test_explicit_email_choice(controller, choice, status):
    s = verified(controller)
    controller.answer(s, 'summary', Interpretation(action='wrap_up'), NOW + 1, 'b')
    controller.email(s, s.summary.id, choice, NOW + 2)
    assert s.summary.status == status


def test_stale_preview_expiry_and_retry(controller):
    s = verified(controller)
    controller.answer(s, 'summary', Interpretation(action='wrap_up'), NOW + 1, 'b')
    sid = s.summary.id
    controller.email(s, sid, 'send', NOW + 2, outcome='failed')
    assert s.summary.status == 'failed'
    controller.email(s, sid, 'send', NOW + 3, outcome='timeout')
    assert s.summary.status == 'timeout'
    with pytest.raises(ValueError): controller.email(s, sid, 'send', NOW + 602)
    assert s.summary.status == 'expired'
    controller.answer(s, 'summary', Interpretation(action='wrap_up'), NOW + 603, 'c')
    with pytest.raises(ValueError): controller.email(s, sid, 'send', NOW + 604)


def test_auth_expiry_hides_protected_history(controller):
    s = verified(controller)
    view = controller.view(s, NOW + 901)
    assert not view['verified'] and not view['case_id'] and not view['summary']
    assert not any(m['protected'] for m in view['messages'])
    assert 'CL-2048' not in str(view)


def test_grounded_documents_payments_and_no_invented_links(controller):
    s = verified(controller)
    controller.answer(s, 'cannot get pathology report; how much payment?', Interpretation(topics=['alternatives', 'payment', 'submission', 'timing']), NOW + 1, 'b')
    answer = s.messages[-1].text
    assert 'replacement copy' in answer and '$1,450.00' in answer and '$0.00' in answer
    assert 'not a promised payout' in answer and 'not confirmation' in answer
    assert 'http' not in answer and 'not a processing promise' in answer


def test_out_of_scope_empathy_and_no_transfer_claim(controller):
    s = Session()
    for n in range(3):
        controller.answer(s, 'What is RL? This is ridiculous', Interpretation(intent='out_of_scope', emotion='frustrated'), NOW+n, str(n))
    assert s.human_offered and 'No transfer' in s.messages[-1].text
    assert not any(e.code == 'CLAIMS_READ' for e in s.events)


def test_early_document_question_and_case_switch_summary(controller):
    s=controller.answer(Session(),'Margaret Chen, January denied healthcare; cannot get the pathology report',
                        Interpretation(identity=identity(name='Margaret Chen'), intent='denial_question',
                                       case_type='healthcare',month=1,status='denied',topics=['alternatives']),NOW,'a')
    controller.answer(s,'1985-03-15 4472',Interpretation(identity=identity(dob='1985-03-15',id_last4='4472')),NOW+1,'b')
    assert 'replacement copy' in s.messages[-1].text
    controller.answer(s,'CL-2011',Interpretation(case_id='CL-2011',topics=['payment']),NOW+2,'c')
    assert s.case_id=='CL-2011' and '780.00' in s.messages[-1].text
    controller.answer(s,'summary',Interpretation(action='wrap_up'),NOW+3,'d')
    assert 'CL-2048' in s.summary.text and 'CL-2011' in s.summary.text


def test_role_change_revokes_history_even_for_out_of_scope(controller):
    s=verified(controller)
    controller.answer(s,"I'm David, her son. What is RL?",Interpretation(intent='out_of_scope'),NOW+1,'b')
    view=controller.view(s,NOW+1)
    assert not view['verified'] and not any(m['protected'] for m in view['messages'])
    assert 'CL-2048' not in str(view)


def test_representative_read_scope_does_not_authorize_email(controller):
    s=verified(controller)
    s.representative=True
    s.grant={'principal_verified':True,'party_id':'P9','expires_at':NOW+900,'scopes':['claims:read']}
    controller.preview(s,controller.f.claim(s,s.case_id,NOW),'',NOW)
    with pytest.raises(PermissionError):controller.email(s,s.summary.id,'send',NOW+1)
    assert s.summary.status=='offered'


def test_chat_yes_preserves_preview_without_sending(controller):
    s=verified(controller)
    controller.preview(s,controller.f.claim(s,s.case_id,NOW),'',NOW)
    summary_id=s.summary.id
    controller.answer(s,'yes',Interpretation(),NOW+1,'b')
    assert s.summary.id==summary_id and s.summary.status=='offered'
    assert not any(e.code=='EMAIL_SIMULATED' for e in s.events)

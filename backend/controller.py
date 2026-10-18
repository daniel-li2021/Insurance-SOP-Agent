"""Deterministic SOP. No model-generated facts, grants, or sensitive actions."""
import hashlib
import re
import uuid
from datetime import datetime, timezone
from .fixtures import Claim, Fixtures
from .identity import DATE, extract_identity, merge_identity, normalize, representative_signal, supported, verify
from .interpreter import human_requested
from .models import Interpretation, Message, Session, Summary, SummaryCase

AUTH_SECONDS = 900
CONSENT_SECONDS = 600
DOCUMENT_KEYS = {'pathology report': 'original pathology report', 'office note': 'treating provider office note'}
EMPAT = {
    'frustrated': 'I hear how frustrating this has been. Let’s take it one step at a time.',
    'anxious': 'It makes sense to want a clear answer. I’ll help you understand what the record says and what you can do next.',
    'confused': 'There’s a lot to untangle here. Let’s make the next step clear.',
    'refusing': 'You can choose which details to share. We can use other approved identity fields, or you can seek help from a human representative.',
}


class Controller:
    def __init__(self, fixtures: Fixtures):
        self.f = fixtures

    @staticmethod
    def wants_human(text: str) -> bool:
        return human_requested(text)

    def expire(self, s: Session, now: float):
        grant = s.grant or {}
        grant_invalid = s.representative and not (
            grant.get('principal_verified') and grant.get('party_id') == s.party_id and
            grant.get('expires_at', 0) > now and 'claims:read' in grant.get('scopes', []))
        if s.party_id and (s.auth_until <= now or grant_invalid):
            s.party_id = None
            s.auth_until = 0
            s.case_id = None
            s.choices = []
            s.identity = {}
            s.matched = []
            s.conflicts = []
            s.summary = None
            s.messages = [m for m in s.messages if not m.protected]
            s.discussed = []
            s.discussed_by_case = {}
            s.exhausted_document_cases = []
            s.context_notes = []
            s.pending_topics = []
            s.pending_documents = []
            s.pending_alternatives_exhausted = False
            s.hints = {}
            s.intent = 'none'
            s.unresolved = []
            s.grant = None
            s.transition('VERIFY_ID', now)
            s.event('AUTH_EXPIRED', 'Please verify again before viewing protected records.', now)
        if s.summary and s.summary.status in ('offered', 'failed', 'timeout') and s.summary.expires_at <= now:
            s.summary.status = 'expired'
            s.event('CONSENT_EXPIRED', 'No email action was taken.', now)

    def redact(self, text: str, interpretation: Interpretation) -> str:
        for c in interpretation.identity + extract_identity(text, Session()):
            if c.source:
                text = re.sub(re.escape(c.source), f'[{c.field} provided]', text, flags=re.I)
        # Redaction does not depend solely on successful model extraction.
        # Never use fixture membership to decide what to redact: that is another lookup oracle.
        text = re.sub(r'(\b(?:my name is|full name(?: is|:)|name is)\s+)[^,;.!?\n]+', r'\1[name provided]', text, flags=re.I)
        text = re.sub(r'[\w.+-]+@[\w.-]+\.[a-zA-Z]{2,}', '[email provided]', text)
        text = re.sub(DATE, '[date provided]', text, flags=re.I)
        text = re.sub(r'\b(?:January|February|March|April|May|June|July|August|September|October|November|December) \d{1,2},? \d{4}\b', '[date provided]', text, flags=re.I)
        text = re.sub(r'(?<!\d)(?:\+?1[ -]?)?\(?\d{3}\)?[ .-]?\d{3}[ .-]?\d{4}(?!\d)', '[phone provided]', text)
        text = re.sub(r'\b\d{3}-\d{2}-\d{4}\b', '[SSN provided]', text)
        text = re.sub(r'((?:last\s*(?:four|4)(?:\s+digits)?|ssn|national[- ]?id)\s*(?:is|are|:)?\s*)\d{4}\b', r'\1[redacted]', text, flags=re.I)
        text = re.sub(r'\bPOL-\d+\b', '[policy number provided]', text, flags=re.I)
        return text

    def answer(self, s: Session, text: str, i: Interpretation, now: float, message_id: str) -> Session:
        self.expire(s, now)
        # Supplement all providers with literal spans; conflicting proposals still fail closed.
        literal = extract_identity(text, s, i.correction)
        proposed_fields = {c.field for c in i.identity}
        i = i.model_copy(update={'identity': i.identity + [c for c in literal if c.field not in proposed_fields]})
        s.turns += 1
        # Caller-role changes must revoke incompatible access even when chat is paused.
        rep_signal = representative_signal(text)
        rep_signal |= any(c.subject == 'policyholder' and supported(c, text) for c in i.identity)
        if i.representative or rep_signal:
            s.representative = True
            self.expire(s, now)
        # Pause before identity/claim/consent processing; acknowledgments cannot restart it.
        human_request = i.action == 'human' or self.wants_human(text)
        if (human_request or s.assistance_paused) and s.party_id and i.identity:
            # Pausing cannot preserve access after a conflicting caller identity.
            proposed = s.model_copy(deep=True)
            merge_identity(proposed, i.identity, text, message_id, i.correction)
            party, _ = verify(proposed, self.f)
            if party != s.party_id:
                s.auth_until = 0
                self.expire(s, now)
        if human_request or s.assistance_paused:
            s.messages.append(Message(id=message_id, role='user', text=self.redact(text, i), protected=bool(s.party_id)))
            if s.assistance_paused and not human_request and text.strip(' .!').casefold() in (
                    'return to chatbot', 'resume chat', 'continue with chatbot'):
                s.assistance_paused = False
                s.event('CHAT_RESUMED', 'Caller voluntarily returned to chat assistance.', now)
                return self.reply(s, '', 'We can continue from your saved conversation. What would you like help with?', now)
            if not s.assistance_paused:
                s.assistance_paused = True
                s.human_offered = True
                s.event('HUMAN_ASSISTANCE_REQUESTED', 'Chat paused. Demo cannot transfer or create a support request.', now)
                return self.reply(s, '', 'I understand you’d like a human representative. This demo cannot make a real transfer or create a support request. Please contact your insurer’s official member support directly. Chat assistance is paused; you can return whenever you choose.', now)
            if not human_request:
                s.event('CHAT_PAUSED', 'Message not processed; explicit return required.', now)
                return self.reply(s, '', 'Chat is paused. Select “Return to chatbot” to resume your saved conversation. No transfer or ticket has been created.', now)
            return s
        if (s.phase == 'POST_PROCESS' and s.summary and s.summary.status in ('offered','failed','timeout')
                and text.strip().casefold() in ('yes','send','send it','skip')):
            s.messages.append(Message(id=message_id, role='user', text=text, protected=True))
            s.event('EXPLICIT_DECISION_REQUIRED', 'A chat acknowledgment is not email consent.', now)
            return self.reply(s, '', 'Please use Send simulated email or Skip on the current preview. Your chat message alone does not authorize a send.', now)
        was_authorized = bool(s.party_id)
        s.summary = None
        if s.phase == 'POST_PROCESS':
            s.transition('PROCESS_CASE' if s.case_id else 'RESOLVE_INTENT', now)
        merge_identity(s, i.identity, text, message_id, i.correction)
        if i.identity:
            s.verification_attempts += 1
            party, matches = verify(s, self.f)
            s.matched = matches
            if s.party_id and party != s.party_id:
                s.party_id = None
                s.auth_until = 0
                s.case_id = None
                s.choices = []
                s.summary = None
                s.messages = [m for m in s.messages if not m.protected]
                s.discussed = []
                s.discussed_by_case = {}
                s.exhausted_document_cases = []
                s.context_notes = []
                s.pending_topics = []
                s.pending_documents = []
                s.pending_alternatives_exhausted = False
                s.hints = {}
                s.transition('VERIFY_ID', now)
                s.event('IDENTITY_RECHECK', 'Changed identity requires renewed authorization.', now)
            if party:
                s.party_id = party
                s.auth_until = now + AUTH_SECONDS
            s.event('IDENTITY_EVALUATED', 'Identity verified.' if party else 'Verification incomplete; no partial match results disclosed.', now)
        previous_emotion = s.emotion
        s.emotion = i.emotion
        if i.intent not in ('none', 'out_of_scope'):
            s.intent = i.intent
        if i.new_case or (s.case_id and i.case_id and i.case_id != s.case_id):
            s.case_id = None
            s.choices = []
            s.hints = {}
            s.discussed = []
            s.pending_topics = []
            s.pending_documents = []
            s.pending_alternatives_exhausted = False
            s.context_notes = []
            if s.party_id: s.transition('RESOLVE_INTENT', now)
        # A payment intent is itself a question, even if the model omits topics.
        requested_topics = i.topics or (['payment'] if i.intent == 'payment_question' else [])
        if s.phase in ('VERIFY_ID', 'RESOLVE_INTENT'):
            s.pending_topics = list(dict.fromkeys(s.pending_topics + requested_topics))
            s.pending_documents = list(dict.fromkeys(s.pending_documents + i.documents))
            s.pending_alternatives_exhausted |= i.alternatives_exhausted
        if i.emotion != 'neutral' or i.alternatives_exhausted or i.topics:
            s.context_notes.append({'message_id':message_id, 'emotion':i.emotion,
                                    'topics':i.topics,'documents':i.documents,'alternatives_exhausted':i.alternatives_exhausted,
                                    'kind':'caller_report'})
        for key in ('case_id', 'case_type', 'month', 'year', 'status'):
            value = getattr(i, key)
            if value is not None:
                s.hints[key] = value
        if any(getattr(i, k) is not None for k in ('case_id', 'case_type', 'month', 'year', 'status')):
            s.event('CONTEXT_CAPTURED', 'Caller-provided claim hints retained without confirming claim facts.', now)
        s.messages.append(Message(id=message_id, role='user', text=self.redact(text, i), protected=was_authorized))
        prefix = EMPAT.get(i.emotion, '') if i.emotion != previous_emotion else ''
        # Verification result is not sufficient proof of a representative's authority.
        if s.representative:
            try:
                self.f.authorize(s, now)
            except PermissionError:
                s.party_id = None
                s.auth_until = 0
                s.case_id = None
                s.choices = []
                s.summary = None
                s.messages = [m for m in s.messages if not m.protected]
                s.transition('VERIFY_ID', now)
                s.human_offered = True
                s.event('REPRESENTATIVE_BLOCKED', 'Relationship is not identity proof or authorization.', now)
                return self.reply(s, prefix, 'I understand you’re helping someone else. Being a relative or knowing their details does not authorize access. I need verified representative identity and a policyholder authorization covering this claim. The supplied demo records do not provide those proofs. Representative Mode remains active for this session, even if you later provide your own details. Please contact the insurer’s member support to establish authorization; no transfer has occurred. To act for yourself, choose “Start fresh self-service session.”', now)
        if i.intent == 'out_of_scope':
            s.scope_streak += 1
            s.event('OUT_OF_SCOPE', 'Request limited to insurance claim support.', now)
            msg = 'I can help with identity verification, your insurance claims, and next steps. Let’s return to your claim.'
            if s.scope_streak >= 3:
                s.human_offered = True
                msg += ' If you need something else, a human support representative may be a better fit. No transfer has been made.'
            return self.reply(s, prefix, msg, now)
        s.scope_streak = 0
        if not s.party_id or s.auth_until <= now:
            s.transition('VERIFY_ID', now)
            if s.verification_attempts >= 6:
                s.human_offered = True
                return self.reply(s, prefix, 'I’m unable to verify these details. Please contact member support for help with identity verification. Claim access remains locked; no transfer has occurred.', now)
            refusal = bool(re.search(r'\b(?:ssn|social security|last four|last 4)\b', text, re.I)) and (
                i.emotion == 'refusing' or bool(re.search(r'refus|won[’\']t|don[’\']t|do not|not (?:sharing|comfortable)|rather not|without', text, re.I)))
            if refusal:
                prefix = '' if i.emotion == 'refusing' else prefix
                msg = 'You don’t need to share SSN details. Full name + DOB (YYYY-MM-DD) + phone is accepted, or choose any three distinct approved fields including email. All three must match the same policyholder. You can use chat or the optional verification form.'
            elif 'dob' in s.conflicts and any(c.field == 'dob' and normalize('dob', c.source) == 'invalid-date' for c in i.identity):
                msg = 'Please enter your birth date as YYYY-MM-DD (for example, 1985-03-15) to avoid numeric-date ambiguity. Verification remains incomplete.'
            elif s.conflicts:
                msg = 'Some supplied details are ambiguous or contradictory. Please explicitly correct them in chat, or replace them using the optional form. Verification remains incomplete; individual matches stay private.'
            elif s.verification_prompted:
                msg = 'Verification is still incomplete. You can provide or explicitly correct your chosen details in chat, or use the optional form. I cannot reveal which details match.'
            else:
                msg = 'To protect claim information, I need three distinct matching identity fields. Verification is not complete. Please share full name, DOB (YYYY-MM-DD), phone, email, or SSN / approved ID last four. A policy number does not count. I cannot reveal which details match. You can also use the optional verification form.'
            s.verification_prompted = True
            s.unresolved = ['Complete identity verification']
            if s.hints and not any(e.code == 'VERIFICATION_REQUESTED' for e in s.events):
                msg += ' I’ve kept your claim question for after verification.'
            s.event('VERIFICATION_REQUESTED', 'Verification incomplete; no partial match results disclosed.', now)
            return self.reply(s, prefix, msg, now)
        s.auth_until = now + AUTH_SECONDS
        if s.phase == 'VERIFY_ID':
            s.transition('RESOLVE_INTENT', now)
            prefix = '\n\n'.join(x for x in (prefix, 'Your identity is verified. I can now look at your claim records.') if x)
        s.unresolved = []
        if s.phase == 'RESOLVE_INTENT' or not s.case_id:
            all_claims = self.f.claims(s, now)
            matches = list(all_claims)
            h = s.hints
            if h.get('case_id'):
                matches = [c for c in matches if c.case_id == h['case_id']]
            else:
                for k in ('case_type', 'status'):
                    if h.get(k): matches = [c for c in matches if getattr(c, k) == h[k]]
                if h.get('month'): matches = [c for c in matches if c.created_at.month == h['month']]
                if h.get('year'): matches = [c for c in matches if c.created_at.year == h['year']]
            if not matches:
                s.event('CASE_NOT_FOUND', 'No matching authorized claim.', now)
                s.unresolved = ['Identify another claim or ask member support']
                return self.reply(s, prefix, 'I can’t find a matching claim in your authorized demo records. Please check the claim reference or date. Member support can help investigate records that are missing here.', now)
            if len(matches) != 1 or s.intent == 'none':
                s.choices = [{'case_id': c.case_id, 'case_type': c.case_type, 'created_at': str(c.created_at), 'status': c.status} for c in matches]
                s.unresolved = ['Choose a claim and question']
                s.event('CASE_CLARIFICATION', 'Multiple candidates or an unresolved question require clarification.', now)
                msg = 'Which claim would you like to discuss, and what would you like to know?\n\n' + '\n'.join(f'{c.case_id} · {c.case_type} · created {c.created_at} · {c.status}' for c in matches)
                return self.reply(s, prefix, msg, now, ['claims.json'])
            s.case_id = matches[0].case_id
            s.discussed = list(s.discussed_by_case.get(s.case_id, []))
            s.choices = []
            s.event('CASE_RESOLVED', 'Caller context matched one authorized case.', now, [f'claims.json#{s.case_id}'])
            s.transition('PROCESS_CASE', now)
        claim = self.f.claim(s, s.case_id, now)
        if claim is None:
            s.case_id = None
            s.transition('RESOLVE_INTENT', now)
            return self.reply(s, prefix, 'This claim is unavailable in your authorized records. Please check the reference or ask member support.', now)
        s.case_status = claim.status
        exhausted = i.alternatives_exhausted or s.pending_alternatives_exhausted
        if exhausted and s.case_id not in s.exhausted_document_cases:
            s.exhausted_document_cases.append(s.case_id)
        if i.action == 'wrap_up':
            return self.preview(s, claim, prefix, now)
        if text.strip().casefold() in ('yes', 'send', 'send it', 'skip'):
            return self.reply(s, prefix, 'To wrap up, choose “Review summary.” You can then explicitly choose Send simulated email or Skip. A chat message alone does not authorize sending.', now)
        topics = list(dict.fromkeys(requested_topics + s.pending_topics)) or ['status']
        body, refs = self.explain(claim, topics, now, exhausted,
                                  documents=i.documents or s.pending_documents,
                                  first=not s.discussed, detailed=i.detailed)
        s.pending_topics = []
        s.pending_documents = []
        s.pending_alternatives_exhausted = False
        s.discussed = list(dict.fromkeys(s.discussed + topics))
        s.discussed_by_case[s.case_id] = list(s.discussed)
        if exhausted or (claim.appeal_deadline and claim.appeal_deadline < datetime.fromtimestamp(now, timezone.utc).date()):
            s.human_offered = True
        s.event('GROUNDED_RESPONSE', 'Response rendered from authorized facts and supplied guidance.', now, refs)
        return self.reply(s, prefix, body, now, refs)

    def reply(self, s: Session, prefix: str, body: str, now: float, refs: list[str] | None = None):
        s.messages.append(Message(id=str(uuid.uuid4()), role='assistant', text='\n\n'.join(x for x in (prefix, body) if x),
                                  protected=bool(s.party_id), references=refs or []))
        return s

    def explain(self, c: Claim, topics: list[str], now: float, exhausted: bool = False,
                documents: list[str] | None = None, first: bool = True, detailed: bool = False) -> tuple[str, list[str]]:
        refs = [f'claims.json#{c.case_id}']
        parts = []
        g = self.f.guidance
        needs = ', '.join(c.documents_needed)
        expired = c.appeal_deadline and c.appeal_deadline < datetime.fromtimestamp(now, timezone.utc).date()
        if detailed or 'status' in topics:
            parts.append(f'{c.case_id} · {c.case_type.capitalize()} claim\nRecorded status: {c.status}.')
        if c.denial_reason and (detailed or any(t in topics for t in ('status', 'denial'))):
            parts.append(f'Your claim {c.case_id} was denied because {c.denial_reason}.')
        if 'payment' in topics or detailed:
            parts.append(f'The recorded finalized insurer payment for {c.case_id} is ${c.net_pay:,.2f}.\n\nThe allowed maximum is ${c.allowed_max_amount:,.2f}, not a promised payout. The claim is currently recorded as {c.status}.')
            if detailed:
                parts.append(f'Expected reimbursement: ${c.expected_reimbursement_amount:,.2f}. Fee-schedule amount (net fee): ${c.net_fee:,.2f}. The fee-schedule amount does not establish what you owe. I have made no payment decision.')
            refs.append('claim_schema.json#field_descriptions')
        if c.documents_needed and ('documents' in topics or detailed) and not documents:
            parts.append('Requested documents: ' + needs + '.')
        if c.documents_needed and not exhausted and (detailed or any(t in topics for t in ('documents', 'alternatives', 'format'))):
            # Model-proposed names can only narrow the authorized record's requirements.
            focused = [d for d in c.documents_needed if any(d.casefold() in name.casefold() for name in documents or [])]
            for doc in focused or c.documents_needed:
                key = DOCUMENT_KEYS.get(doc, doc)
                group = 'document_alternative_guidance' if 'alternatives' in topics else 'document_guidance'
                entry = g[group].get(key, g.get('document_alternative_guidance', {}).get('default') if group == 'document_alternative_guidance' else g['default_guidance'])
                guidance = entry['en']
                # The fixture's final conditional referral is covered once below, when exhausted.
                if group == 'document_alternative_guidance' and 'human' in guidance:
                    guidance = guidance.rsplit(' If ', 1)[0]
                parts.append(f'{doc.capitalize()}: {guidance}')
                refs.append(f'required_document_guideline.json#{group}/{key if key in g[group] else "default"}')
            if 'alternatives' in topics:
                parts.append('These are options for review, not confirmation that a substitute will be accepted or the denial reversed.')
        if c.documents_needed and 'submission' in topics:
            parts.append(g['default_guidance']['en'])
            if c.case_type in g['case_type_guidance']: parts.append(g['case_type_guidance'][c.case_type]['en'])
            parts.append('No verified portal URL, mailing address, or fax number is supplied in this demo. Use your insurer’s existing member portal or ask member support. I have not submitted documents.')
            refs.append('required_document_guideline.json#default_guidance')
        if c.documents_needed and 'timing' in topics:
            if not expired:
                template = next(x['en'] for x in g['claim_followup_guidance'] if x['topic'] == 'processing_time_after_submission')
                parts.append(template.format(case_id=c.case_id, documents=needs, average_processing_time_after_submission=g['claim_followup_settings']['average_processing_time_after_submission']['en']))
            else:
                parts.append('The general guidance gives an average of usually less than a week after missing files are received. Because this appeal deadline has passed, that is not a processing promise for this case; member support must confirm whether further review is available.')
            refs.append('required_document_guideline.json#claim_followup_settings')
        if 'receipt' in topics:
            parts.append('I cannot confirm receipt or attachment of documents in this demo. The guidance notes an intake delay; if the record stays unchanged after a few business days, ask member support to check the attachments.')
            refs.append('required_document_guideline.json#claim_followup_guidance/receipt_confirmation')
        if c.appeal_deadline and (detailed or 'appeal' in topics or 'timing' in topics or (first and any(t in topics for t in ('status', 'denial', 'documents', 'alternatives')))):
            formatted = c.appeal_deadline.strftime('%B %d, %Y').replace(' 0', ' ')
            if expired:
                referral = '' if exhausted else ' Contact a human claims representative to review any remaining options. No appeal or transfer has been initiated.'
                parts.append(f'The recorded appeal deadline was {formatted}, and it has passed. I can’t confirm whether a late appeal or reopening is available.' + referral)
            else:
                parts.append(f'The recorded appeal deadline is {formatted}. Member support can confirm applicable submission requirements; I cannot extend this date.')
        if exhausted:
            parts.append('Since those document options are unavailable, please contact a human claims representative to review manual options. This is not confirmation that a substitute will be accepted, the denial reversed, or an appeal reopened. No appeal or transfer has been initiated; this demo cannot transfer you.')
            refs.append('required_document_guideline.json#claim_followup_settings/human_review_after_document_alternatives_exhausted')
        if not parts: parts.append(f'The recorded status of {c.case_id} is {c.status}. What would you like to know?')
        return '\n\n'.join(parts), list(dict.fromkeys(refs))

    def preview(self, s: Session, c: Claim, prefix: str, now: float):
        s.transition('POST_PROCESS', now)
        cases, refs = [], []
        for case_id in dict.fromkeys([*s.discussed_by_case, c.case_id]):
            claim = self.f.claim(s, case_id, now)
            if claim:
                expired = bool(claim.appeal_deadline and claim.appeal_deadline < datetime.fromtimestamp(now, timezone.utc).date())
                reason = ('Missing ' + ' and '.join('treating provider office note' if d == 'office note' else d for d in claim.documents_needed) + '.') if claim.denial_reason and claim.documents_needed else claim.denial_reason
                next_steps = ('Ask the provider about replacement documents. Contact a human claims representative to confirm whether further review is possible.' if claim.documents_needed else 'Contact member support if you have questions about this recorded outcome.')
                if claim.documents_needed and case_id in s.exhausted_document_cases:
                    next_steps = 'You reported that document options were unavailable. Contact a human claims representative to review manual options and confirm whether further review is possible.'
                cases.append(SummaryCase(case_id=claim.case_id, case_type=claim.case_type.capitalize(),
                    status=claim.status.capitalize(), denial_reason=reason,
                    payment=f'${claim.net_pay:,.2f}', allowed_maximum=f'${claim.allowed_max_amount:,.2f}',
                    appeal_deadline=claim.appeal_deadline.strftime('%B %d, %Y').replace(' 0', ' ') if claim.appeal_deadline else None,
                    deadline_passed=expired, next_steps=next_steps,
                    unresolved='Document receipt has not been confirmed.' if claim.documents_needed and 'receipt' in s.discussed_by_case.get(case_id, []) else ''))
                refs.append(f'claims.json#{claim.case_id}')
                if claim.documents_needed:
                    refs.extend(f'required_document_guideline.json#document_alternative_guidance/{DOCUMENT_KEYS.get(d, d) if DOCUMENT_KEYS.get(d, d) in self.f.guidance["document_alternative_guidance"] else "default"}' for d in claim.documents_needed)
        sections = []
        for item in cases:
            fields = [f'{item.case_id} · {item.case_type}', f'Status: {item.status}']
            if item.denial_reason: fields.append('Reason for denial: ' + item.denial_reason)
            fields.append(f'Payment: {item.payment} (recorded finalized insurer payment). Allowed maximum: {item.allowed_maximum}, not a promised payout.')
            if item.appeal_deadline: fields.append(f'Appeal deadline: {item.appeal_deadline}' + (' — Passed' if item.deadline_passed else ''))
            fields.append('Next steps: ' + item.next_steps)
            if item.unresolved:
                fields.append('Still unresolved: ' + item.unresolved)
            sections.append('\n\n'.join(fields))
        body = '\n\n——\n\n'.join(sections) + '\n\nThis is a synthetic summary. No appeal, payment, document submission, or email delivery has occurred.'
        person = self.f.person(s.party_id)
        name, domain = person.email.split('@')
        masked = name[0] + '•••@' + domain
        s.summary = Summary(id=str(uuid.uuid4()), text=body, cases=cases, recipient=masked, expires_at=now + CONSENT_SECONDS)
        refs = list(dict.fromkeys(refs))
        s.event('SUMMARY_OFFERED', 'Preview ready; explicit Send or Skip required. Consent expires in 10 minutes.', now, refs)
        return self.reply(s, prefix, 'Your summary is ready below. Review it, then choose Send simulated email or Skip. Nothing is sent automatically.', now, refs)

    def email(self, s: Session, summary_id: str, choice: str, now: float, outcome: str = 'success'):
        self.expire(s, now)
        self.f.authorize(s, now)
        summary = s.summary
        if s.phase != 'POST_PROCESS' or not summary or summary.id != summary_id:
            raise ValueError('This preview is no longer current. Review a fresh summary.')
        if summary.status == 'simulated_sent':
            return s
        if summary.status in ('skipped', 'expired'):
            raise ValueError('This offer is no longer active. Review a fresh summary.')
        if choice == 'skip':
            summary.status = 'skipped'
            s.event('EMAIL_SKIPPED', 'Customer explicitly chose Skip. No email action taken.', now)
            return self.reply(s, '', 'Skipped. Your summary remains available in this session. No email was sent.', now)
        if s.representative and 'summary:email_policyholder' not in (s.grant or {}).get('scopes', []):
            raise PermissionError('Representative grant does not cover this action')
        if outcome in ('failed', 'timeout'):
            summary.status = outcome
            s.event('EMAIL_' + outcome.upper(), 'Simulation did not record a delivery. Explicit retry is available until consent expires.', now)
            return self.reply(s, '', 'The email simulation ' + ('timed out' if outcome == 'timeout' else 'failed') + '. No email was delivered. You can retry this same preview or Skip.', now)
        summary.status = 'simulated_sent'
        summary.receipt = hashlib.sha256((summary.id + summary.recipient + summary.text).encode()).hexdigest()[:16]
        s.event('EMAIL_SIMULATED', 'Explicit consent accepted for this preview and on-file recipient; unique simulated receipt recorded.', now)
        return self.reply(s, '', 'Simulation recorded; no email was delivered. The summary was addressed to your on-file email in this simulated action.', now)

    def view(self, s: Session, now: float) -> dict:
        self.expire(s, now)
        authorized = bool(s.party_id and s.auth_until > now)
        return {'version': s.version, 'phase': s.phase, 'verified': authorized,
                'verification': {'count': 3 if authorized else 0, 'required': 3,
                                 'fields': s.matched if authorized else [], 'representative': s.representative},
                'intent': s.intent, 'case_id': s.case_id if authorized else None,
                'case_status': s.case_status if authorized and s.case_id else None,
                'choices': s.choices if authorized else [], 'emotion': s.emotion,
                'human_offered': s.human_offered, 'assistance_paused': s.assistance_paused, 'unresolved': s.unresolved,
                'messages': [m.model_dump() for m in s.messages if authorized or not m.protected],
                'events': [{**e.model_dump(exclude={'party_id'}), **({'detail': 'Identity evaluated; partial match results are private.'}
                            if e.code == 'IDENTITY_EVALUATED' else {})}
                           for e in s.events if not e.references or (authorized and e.party_id == s.party_id)],
                'summary': s.summary.model_dump() if authorized and s.summary and s.phase == 'POST_PROCESS' else None,
                'model': s.model, 'fixture_version': self.f.version,
                'auth_expires_at': s.auth_until if authorized else None, 'server_time': now}

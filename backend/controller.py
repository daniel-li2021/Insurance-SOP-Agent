"""Deterministic SOP. No model-generated facts, grants, or sensitive actions."""
import hashlib
import re
import uuid
from datetime import datetime, timezone
from .fixtures import Claim, Fixtures
from .identity import merge_identity, verify
from .models import Interpretation, Message, Session, Summary

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

    def expire(self, s: Session, now: float):
        grant_expired = s.representative and s.grant and s.grant.get('expires_at', 0) <= now
        if s.party_id and (s.auth_until <= now or grant_expired):
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
            s.context_notes = []
            s.pending_topics = []
            s.transition('VERIFY_ID', now)
            s.event('AUTH_EXPIRED', 'Please verify again before viewing protected records.', now)
        if s.summary and s.summary.status in ('offered', 'failed', 'timeout') and s.summary.expires_at <= now:
            s.summary.status = 'expired'
            s.event('CONSENT_EXPIRED', 'No email action was taken.', now)

    def redact(self, text: str, interpretation: Interpretation) -> str:
        for c in interpretation.identity:
            if c.source:
                text = re.sub(re.escape(c.source), f'[{c.field} provided]', text, flags=re.I)
        # Redaction does not depend solely on successful model extraction.
        for p in self.f.people:
            for value in [p.name, *p.name_aliases, p.email, *p.email_aliases, str(p.dob), p.phone, p.id_last4]:
                text = re.sub(re.escape(value), '[identity detail]', text, flags=re.I)
        text = re.sub(r'[\w.+-]+@[\w.-]+\.[a-zA-Z]{2,}', '[email provided]', text)
        text = re.sub(r'\b\d{4}-\d{2}-\d{2}\b|\b\d{1,2}/\d{1,2}/\d{4}\b', '[date provided]', text)
        text = re.sub(r'(?<!\d)(?:\+?1[ -]?)?\(?\d{3}\)?[ .-]?\d{3}[ .-]?\d{4}(?!\d)', '[phone provided]', text)
        text = re.sub(r'((?:last four|last 4|ssn)\s*(?:is|:)?\s*)\d{4}\b', r'\1[redacted]', text, flags=re.I)
        return text

    def answer(self, s: Session, text: str, i: Interpretation, now: float, message_id: str) -> Session:
        self.expire(s, now)
        s.turns += 1
        if (s.phase == 'POST_PROCESS' and s.summary and s.summary.status in ('offered','failed','timeout')
                and text.strip().casefold() in ('yes','send','send it','skip')):
            s.messages.append(Message(id=message_id, role='user', text=text, protected=True))
            s.event('EXPLICIT_DECISION_REQUIRED', 'A chat acknowledgment is not email consent.', now)
            return self.reply(s, '', 'Please use Send simulated email or Skip on the current preview. Your chat message alone does not authorize a send.', now)
        was_authorized = bool(s.party_id)
        # Caller role is sticky. A model omission cannot turn a relative into a policyholder.
        rep_signal = bool(re.search(r'on behalf|my (?:mother|mom|father|dad)|her son|as (?:a |her )?representative|i.m david', text, re.I))
        if i.representative or rep_signal:
            s.representative = True
        if s.summary and s.summary.status != 'simulated_sent':
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
                s.context_notes = []
                s.pending_topics = []
                s.hints = {}
                s.transition('VERIFY_ID', now)
                s.event('IDENTITY_RECHECK', 'Changed identity requires renewed authorization.', now)
            if party:
                s.party_id = party
                s.auth_until = now + AUTH_SECONDS
            s.event('IDENTITY_EVALUATED', f'{min(len(matches), 3)} of 3 distinct fields matched; policy numbers do not count.', now)
        s.emotion = i.emotion
        if i.intent not in ('none', 'out_of_scope'):
            s.intent = i.intent
        if i.new_case or (s.case_id and i.case_id and i.case_id != s.case_id):
            s.case_id = None
            s.choices = []
            s.hints = {}
            s.discussed = []
            s.pending_topics = []
            s.context_notes = []
            if s.party_id: s.transition('RESOLVE_INTENT', now)
        if s.phase in ('VERIFY_ID', 'RESOLVE_INTENT') and i.topics:
            s.pending_topics = list(dict.fromkeys(s.pending_topics + i.topics))
        if i.emotion != 'neutral' or i.alternatives_exhausted or i.topics:
            s.context_notes.append({'message_id':message_id, 'emotion':i.emotion,
                                    'topics':i.topics,'alternatives_exhausted':i.alternatives_exhausted,
                                    'kind':'caller_report'})
        for key in ('case_id', 'case_type', 'month', 'year', 'status'):
            value = getattr(i, key)
            if value is not None:
                s.hints[key] = value
        if any(getattr(i, k) is not None for k in ('case_id', 'case_type', 'month', 'year', 'status')):
            s.event('CONTEXT_CAPTURED', 'Caller-provided claim hints retained without confirming claim facts.', now)
        s.messages.append(Message(id=message_id, role='user', text=self.redact(text, i), protected=was_authorized))
        prefix = EMPAT.get(i.emotion, '')
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
                return self.reply(s, prefix, 'I understand you’re helping someone else. Being a relative or knowing their details does not authorize access. I need verified representative identity and a policyholder authorization covering this claim. The supplied demo records do not provide those proofs. Please contact the insurer’s member support to establish authorization; no transfer has occurred.', now)
        if i.action == 'human':
            s.human_offered = True
            return self.reply(s, prefix, 'I can suggest asking your insurer’s member support for a human claims representative. This demo cannot transfer you or create a support request. You can continue here if you prefer.', now)
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
            missing = [x for x in ('name', 'dob', 'phone', 'email', 'id_last4') if x not in s.identity]
            labels = {'name': 'full name', 'dob': 'date of birth (YYYY-MM-DD)', 'phone': 'phone number', 'email': 'email', 'id_last4': 'SSN or approved national-ID last four'}
            if s.verification_attempts >= 6:
                s.human_offered = True
                return self.reply(s, prefix, 'I’m unable to verify these details. Please contact member support for help with identity verification. Claim access remains locked; no transfer has occurred.', now)
            if s.conflicts or (len(s.identity) >= 3 and len(s.matched) < len([k for k in s.identity if k != 'policy_number'])):
                msg = 'The details provided don’t yet establish a consistent match. Please clarify or explicitly correct a detail, or provide a different approved field. I cannot reveal the expected values.'
                s.unresolved = ['Clarify identity details']
            else:
                needed = max(1, 3 - len(s.matched))
                msg = f'To protect claim information, I need three distinct matching identity fields. Please provide {needed} more: ' + ', '.join(labels[x] for x in missing) + '. A policy number can locate a record but does not count toward verification.'
                s.unresolved = ['Complete identity verification']
            if s.hints: msg += ' I’ve kept your claim question for after verification.'
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
            s.choices = []
            s.event('CASE_RESOLVED', 'Caller context matched one authorized case.', now, [f'claims.json#{s.case_id}'])
            s.transition('PROCESS_CASE', now)
        claim = self.f.claim(s, s.case_id, now)
        if claim is None:
            s.case_id = None
            s.transition('RESOLVE_INTENT', now)
            return self.reply(s, prefix, 'This claim is unavailable in your authorized records. Please check the reference or ask member support.', now)
        if i.action == 'wrap_up':
            return self.preview(s, claim, prefix, now)
        if text.strip().casefold() in ('yes', 'send', 'send it', 'skip'):
            return self.reply(s, prefix, 'To wrap up, choose “Review summary.” You can then explicitly choose Send simulated email or Skip. A chat message alone does not authorize sending.', now)
        topics = list(dict.fromkeys(i.topics + s.pending_topics)) or ['status']
        exhausted = i.alternatives_exhausted or any(n.get('alternatives_exhausted') for n in s.context_notes)
        body, refs = self.explain(claim, topics, now, exhausted)
        s.pending_topics = []
        s.discussed = list(dict.fromkeys(s.discussed + topics))
        s.discussed_by_case[s.case_id] = list(s.discussed)
        if i.alternatives_exhausted or (claim.appeal_deadline and claim.appeal_deadline < datetime.fromtimestamp(now, timezone.utc).date()):
            s.human_offered = True
        s.event('GROUNDED_RESPONSE', 'Response rendered from authorized facts and supplied guidance.', now, refs)
        return self.reply(s, prefix, body, now, refs)

    def reply(self, s: Session, prefix: str, body: str, now: float, refs: list[str] | None = None):
        s.messages.append(Message(id=str(uuid.uuid4()), role='assistant', text='\n\n'.join(x for x in (prefix, body) if x),
                                  protected=bool(s.party_id), references=refs or []))
        return s

    def explain(self, c: Claim, topics: list[str], now: float, exhausted: bool = False) -> tuple[str, list[str]]:
        refs = [f'claims.json#{c.case_id}']
        parts = [f'{c.case_id} · {c.case_type.capitalize()} claim · created {c.created_at}\nRecorded status: {c.status}.']
        g = self.f.guidance
        needs = ', '.join(c.documents_needed)
        expired = c.appeal_deadline and c.appeal_deadline < datetime.fromtimestamp(now, timezone.utc).date()
        if c.denial_reason and any(t in topics for t in ('status', 'denial', 'documents')):
            parts.append(f'The recorded denial reason is that {c.denial_reason}.')
        if 'payment' in topics:
            parts.append(f'Expected reimbursement: ${c.expected_reimbursement_amount:,.2f}.\nAllowed maximum: ${c.allowed_max_amount:,.2f}.\nFinalized insurer payment: ${c.net_pay:,.2f}.\nFee-schedule amount (net fee): ${c.net_fee:,.2f}.\nThe allowed maximum is not a promised payout. The fee-schedule amount does not establish what you owe. These are recorded amounts; I have made no payment decision.')
            refs.append('claim_schema.json#field_descriptions')
        if c.documents_needed and any(t in topics for t in ('denial', 'documents', 'alternatives', 'format')):
            parts.append('Requested documents: ' + needs + '.')
        if c.documents_needed and any(t in topics for t in ('documents', 'alternatives', 'format')):
            for doc in c.documents_needed:
                key = DOCUMENT_KEYS.get(doc, doc)
                group = 'document_alternative_guidance' if 'alternatives' in topics else 'document_guidance'
                entry = g[group].get(key, g.get('document_alternative_guidance', {}).get('default') if group == 'document_alternative_guidance' else g['default_guidance'])
                parts.append(f'{doc.capitalize()}: {entry["en"]}')
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
        if c.appeal_deadline:
            formatted = c.appeal_deadline.strftime('%B %d, %Y').replace(' 0', ' ')
            if expired:
                parts.append(f'The recorded appeal deadline was {formatted}, and it has passed. Please ask a human claims representative to review what options remain. I cannot promise a late appeal, reopening, or reimbursement. No transfer or appeal has been made.')
            else:
                parts.append(f'The recorded appeal deadline is {formatted}. Member support can confirm applicable submission requirements; I cannot extend this date.')
        if exhausted:
            parts.append(g['claim_followup_settings']['human_review_after_document_alternatives_exhausted']['en'] + ' This demo cannot transfer you.')
            refs.append('required_document_guideline.json#claim_followup_settings/human_review_after_document_alternatives_exhausted')
        return '\n\n'.join(parts), list(dict.fromkeys(refs))

    def preview(self, s: Session, c: Claim, prefix: str, now: float):
        s.transition('POST_PROCESS', now)
        sections, refs = [], []
        for case_id, topics in (s.discussed_by_case or {c.case_id:s.discussed}).items():
            discussed_claim = self.f.claim(s, case_id, now)
            if discussed_claim:
                body, evidence = self.explain(discussed_claim, list(dict.fromkeys(['status'] + topics)), now)
                sections.append(body)
                refs.extend(evidence)
        body = 'Discussion summary\n\n' + '\n\n——\n\n'.join(sections)
        refs = list(dict.fromkeys(refs))
        if s.unresolved: body += '\n\nStill to resolve: ' + '; '.join(s.unresolved)
        person = self.f.person(s.party_id)
        name, domain = person.email.split('@')
        masked = name[0] + '•••@' + domain
        s.summary = Summary(id=str(uuid.uuid4()), text=body, recipient=masked, expires_at=now + CONSENT_SECONDS)
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
                'verification': {'count': min(len(s.matched), 3), 'required': 3,
                                 'fields': s.matched if authorized else [], 'representative': s.representative},
                'intent': s.intent, 'case_id': s.case_id if authorized else None,
                'choices': s.choices if authorized else [], 'emotion': s.emotion,
                'human_offered': s.human_offered, 'unresolved': s.unresolved,
                'messages': [m.model_dump() for m in s.messages if authorized or not m.protected],
                'events': [e.model_dump() for e in s.events if authorized or not e.references],
                'summary': s.summary.model_dump() if authorized and s.summary else None,
                'model': s.model, 'fixture_version': self.f.version,
                'auth_expires_at': s.auth_until if authorized else None, 'server_time': now}

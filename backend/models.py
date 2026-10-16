"""Validated, deliberately separate interpretation and controller state."""
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field

Phase = Literal['VERIFY_ID', 'RESOLVE_INTENT', 'PROCESS_CASE', 'POST_PROCESS']
IdentityField = Literal['name', 'dob', 'phone', 'email', 'id_last4', 'policy_number']
Topic = Literal['status', 'denial', 'documents', 'alternatives', 'submission', 'timing', 'format', 'receipt', 'payment']


class StrictModel(BaseModel):
    model_config = ConfigDict(extra='forbid')


class Candidate(StrictModel):
    field: IdentityField
    value: str = Field(min_length=1, max_length=160)
    source: str = Field(min_length=1, max_length=240)
    subject: Literal['caller', 'policyholder'] = 'caller'
    identifier_type: Literal['ssn_last4', 'national_id_last4', 'unspecified'] = 'unspecified'


class Interpretation(StrictModel):
    identity: list[Candidate] = Field(default_factory=list, max_length=12)
    representative: bool = False
    correction: bool = False
    intent: Literal['none', 'status_inquiry', 'denial_question', 'document_submission', 'payment_question', 'next_steps', 'general_claim_question', 'out_of_scope'] = 'none'
    case_id: str | None = None
    case_type: Literal['healthcare', 'dental', 'auto'] | None = None
    month: int | None = Field(default=None, ge=1, le=12)
    year: int | None = Field(default=None, ge=1900, le=2100)
    status: Literal['denied', 'closed', 'open'] | None = None
    topics: list[Topic] = Field(default_factory=list, max_length=9)
    emotion: Literal['neutral', 'frustrated', 'anxious', 'confused', 'refusing'] = 'neutral'
    action: Literal['continue', 'wrap_up', 'human'] = 'continue'
    new_case: bool = False
    alternatives_exhausted: bool = False


class Message(StrictModel):
    id: str
    role: Literal['user', 'assistant']
    text: str
    protected: bool = False
    references: list[str] = Field(default_factory=list)


class Event(StrictModel):
    sequence: int
    code: str
    phase: Phase
    at: float
    detail: str
    references: list[str] = Field(default_factory=list)


class Summary(StrictModel):
    id: str
    text: str
    recipient: str
    expires_at: float
    status: Literal['offered', 'skipped', 'expired', 'failed', 'timeout', 'simulated_sent'] = 'offered'
    receipt: str | None = None


class Session(StrictModel):
    version: int = 0
    phase: Phase = 'VERIFY_ID'
    identity: dict[str, Candidate] = Field(default_factory=dict)
    provenance: list[dict] = Field(default_factory=list)
    conflicts: list[str] = Field(default_factory=list)
    matched: list[str] = Field(default_factory=list)
    party_id: str | None = None
    auth_until: float = 0
    representative: bool = False
    # Only the evaluator can create this assertion; never accepted from chat/HTTP input.
    grant: dict | None = None
    intent: str = 'none'
    hints: dict = Field(default_factory=dict)
    case_id: str | None = None
    choices: list[dict] = Field(default_factory=list)
    emotion: str = 'neutral'
    unresolved: list[str] = Field(default_factory=list)
    discussed: list[str] = Field(default_factory=list)
    discussed_by_case: dict[str, list[str]] = Field(default_factory=dict)
    pending_topics: list[Topic] = Field(default_factory=list)
    context_notes: list[dict] = Field(default_factory=list)
    scope_streak: int = 0
    verification_attempts: int = 0
    human_offered: bool = False
    messages: list[Message] = Field(default_factory=list)
    events: list[Event] = Field(default_factory=list)
    summary: Summary | None = None
    turns: int = 0
    model: str = 'scripted'

    def event(self, code: str, detail: str, now: float, refs: list[str] | None = None):
        self.events.append(Event(sequence=len(self.events) + 1, code=code, detail=detail,
                                 phase=self.phase, at=now, references=refs or []))

    def transition(self, phase: Phase, now: float):
        if phase != self.phase:
            old = self.phase
            self.phase = phase
            self.event('PHASE_CHANGED', f'{old} → {phase}', now)

"""Fixture validation and the only session-facing claim access boundary."""
import hashlib
import json
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field
from .models import Session

ROOT = Path(__file__).resolve().parents[1]


class Policyholder(BaseModel):
    model_config = ConfigDict(extra='forbid')
    party_id: str
    name: str
    policy_number: str
    dob: date
    id_type: Literal['ssn_last4', 'national_id_last4']
    id_last4: str = Field(pattern=r'^\d{4}$')
    phone: str
    email: str
    name_aliases: list[str] = Field(default_factory=list)
    phone_aliases: list[str] = Field(default_factory=list)
    email_aliases: list[str] = Field(default_factory=list)


class Claim(BaseModel):
    model_config = ConfigDict(extra='forbid')
    case_id: str
    party_id: str
    case_type: Literal['healthcare', 'dental', 'auto']
    created_at: date
    status: Literal['open', 'closed', 'denied']
    summary: str
    denial_reason: str | None = None
    documents_needed: list[str] = Field(default_factory=list)
    appeal_deadline: date | None = None
    expected_reimbursement_amount: Decimal = Field(ge=0)
    allowed_max_amount: Decimal = Field(ge=0)
    net_pay: Decimal = Field(ge=0)
    net_fee: Decimal = Field(ge=0)


class Fixtures:
    def __init__(self, directory: Path = ROOT / 'docs/fixtures'):
        raw = {p.stem: p.read_bytes() for p in sorted(directory.glob('*.json'))}
        required = {'policyholders', 'claims', 'claim_schema', 'representatives', 'consent_scenarios', 'required_document_guideline'}
        if set(raw) != required:
            raise ValueError('Expected exactly the six supplied fixtures')
        data = {k: json.loads(v) for k, v in raw.items()}
        self.version = hashlib.sha256(b''.join(raw.values())).hexdigest()[:12]
        self.people = [Policyholder.model_validate(x) for x in data['policyholders']]
        self._claims = [Claim.model_validate(x) for x in data['claims']]
        parties = {x.party_id for x in self.people}
        if len(parties) != len(self.people) or len({x.case_id for x in self._claims}) != len(self._claims):
            raise ValueError('Duplicate fixture identifiers')
        if any(x.party_id not in parties for x in self._claims):
            raise ValueError('Unknown claim owner')
        self.representatives = data['representatives']
        if any(x['buyer_party_id'] not in parties for x in self.representatives):
            raise ValueError('Unknown representative relationship')
        self.guidance = data['required_document_guideline']
        self.schema = data['claim_schema']
        self.consent_sequences = data['consent_scenarios']

    def person(self, party_id: str) -> Policyholder:
        return next(x for x in self.people if x.party_id == party_id)

    def authorize(self, state: Session, now: float):
        if not state.party_id or state.auth_until <= now or len(state.matched) < 3 or state.conflicts:
            state.event('ACCESS_DENIED', 'A valid identity and authorization are required.', now)
            raise PermissionError('Authorization required')
        if state.representative:
            g = state.grant or {}
            if not (g.get('principal_verified') and g.get('party_id') == state.party_id and
                    g.get('expires_at', 0) > now and 'claims:read' in g.get('scopes', [])):
                state.event('ACCESS_DENIED', 'Representative identity or scoped grant is missing.', now)
                raise PermissionError('Authorization required')

    def claims(self, state: Session, now: float) -> list[Claim]:
        self.authorize(state, now)
        state.event('CLAIMS_READ', 'Read limited to the authorized policyholder.', now, ['claims.json'])
        return [c for c in self._claims if c.party_id == state.party_id]

    def claim(self, state: Session, case_id: str, now: float) -> Claim | None:
        return next((c for c in self.claims(state, now) if c.case_id == case_id), None)

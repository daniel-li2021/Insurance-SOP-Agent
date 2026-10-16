import re
from datetime import datetime
from .fixtures import Fixtures
from .models import Candidate, Session


def normalize(field: str, value: str) -> str:
    value = value.strip()
    if field == 'dob':
        for fmt in ('%Y-%m-%d', '%B %d, %Y', '%B %d %Y', '%b %d, %Y', '%b %d %Y'):
            try:
                return datetime.strptime(value, fmt).date().isoformat()
            except ValueError:
                pass
        return 'invalid-date'
    if field == 'phone':
        digits = re.sub(r'\D', '', value)
        return '1' + digits if len(digits) == 10 else digits
    if field == 'id_last4':
        return re.sub(r'\s', '', value)
    return ' '.join(value.casefold().split())


def supported(candidate: Candidate, text: str) -> bool:
    # Values must be supported by this turn, never by the model's knowledge of a person.
    return (candidate.source.casefold() in text.casefold() and
            normalize(candidate.field, candidate.value) == normalize(candidate.field, candidate.source) and
            normalize(candidate.field, candidate.value) != 'invalid-date')


def merge_identity(state: Session, candidates: list[Candidate], text: str, message_id: str, correction: bool):
    for c in candidates:
        if not supported(c, text):
            continue
        if state.representative and c.subject == 'caller':
            continue
        old = state.identity.get(c.field)
        different = old and normalize(c.field, old.value) != normalize(c.field, c.value)
        if different and not correction:
            if c.field not in state.conflicts:
                state.conflicts.append(c.field)
        else:
            state.conflicts = [x for x in state.conflicts if x != c.field]
            state.identity[c.field] = c
        state.provenance.append({'field': c.field, 'message_id': message_id,
                                 'kind': 'correction' if different and correction else 'user_claim'})


def verify(state: Session, fixtures: Fixtures) -> tuple[str | None, list[str]]:
    results = []
    for p in fixtures.people:
        matches = []
        contradiction = False
        for field, c in state.identity.items():
            if field == 'policy_number':
                contradiction |= normalize(field, c.value) != normalize(field, p.policy_number)
                continue
            expected = [str(getattr(p, field))] + getattr(p, field + '_aliases', [])
            ok = normalize(field, c.value) in [normalize(field, v) for v in expected]
            if field == 'id_last4' and c.identifier_type not in ('unspecified', p.id_type):
                ok = False
            if ok:
                matches.append(field)
            else:
                contradiction = True
        results.append((p.party_id, matches, contradiction))
    eligible = [(pid, matched) for pid, matched, conflict in results if len(matched) >= 3 and not conflict and not state.conflicts]
    if len(eligible) == 1:
        return eligible[0]
    # Failed attempts must not reveal proximity to any stored identity.
    return None, []

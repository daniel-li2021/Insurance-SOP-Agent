import re
from datetime import datetime
from .fixtures import Fixtures
from .models import Candidate, Session


MONTH = r'(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:t(?:ember)?|tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)'
DATE = (rf'\b(?:\d{{4}}[-/.]\d{{1,2}}[-/.]\d{{1,2}}|\d{{1,2}}[-/.]\d{{1,2}}[-/.]\d{{4}}|'
        rf'{MONTH}\.?\s+\d{{1,2}}(?:st|nd|rd|th)?(?:\s*,\s*|\s+)\d{{4}}|'
        rf'\d{{1,2}}(?:st|nd|rd|th)?\s+{MONTH}\.?(?:\s*,\s*|\s+)\d{{4}})\b')
PHONE = r'(?<![\d\w])(?:\+?\d{1,3}[ .-]?)?\(?\d{3}\)?[ .-]?\d{3}[ .-]?\d{4}(?![\d\w])'


def representative_signal(text: str) -> bool:
    return bool(re.search(
        r'on behalf|my (?:mother|mom|father|dad|wife|husband|spouse|partner|daughter|son|sister|brother|aunt|uncle|grandmother|grandfather)\b|'
        r'her son|as (?:a |her )?representative|i.m david|'
        r'\bi(?: am|[’\']m)\s+representing\b|'
        r'\bi(?: am|[’\']m)\s+(?:(?:a|an)\s+)?(?:authorized\s+)?representative\b|'
        r'\b(?:i(?: am|[’\']m)|as)\s+(?:the\s+)?(?:her|his|their|(?:policyholder|claimant|insured|patient)[’\']s)\s+'
        r'(?:authorized\s+)?(?:representative|attorney|lawyer|guardian|caregiver|doctor|nurse)\b|'
        r'\b(?:helping|assisting|calling for) (?:my|a|the) (?:friend|client|patient)\b|'
        r'\b(?:her|his|their) (?:(?:full )?name\s*(?:is|:)|dob\b|date of birth\b)',
        text, re.I))


def normalize(field: str, value: str) -> str:
    value = value.strip()
    if field == 'dob':
        clean = re.sub(r'(?<=\d)(st|nd|rd|th)\b', '', value, flags=re.I)
        clean = re.sub(r'(?<=[A-Za-z])\.', '', clean)
        clean = re.sub(r'\s*,\s*', ' ', clean)
        clean = ' '.join(clean.split())
        numeric = re.fullmatch(r'(\d{1,2})[-/.](\d{1,2})[-/.](\d{4})', clean)
        if numeric:
            month, day, year = map(int, numeric.groups())
            # US dates with two plausible, different month/day orders need clarification.
            if month != day and month <= 12 and day <= 12:
                return 'invalid-date'
            clean = f'{year:04}-{month:02}-{day:02}'
        elif re.fullmatch(r'\d{4}[-/.]\d{1,2}[-/.]\d{1,2}', clean):
            clean = re.sub(r'[/\.]', '-', clean)
        for fmt in ('%Y-%m-%d', '%B %d %Y', '%b %d %Y', '%d %B %Y', '%d %b %Y'):
            try:
                return datetime.strptime(clean, fmt).date().isoformat()
            except ValueError:
                pass
        return 'invalid-date'
    if field == 'phone':
        if not re.fullmatch(r'\+?[\d ().-]+', value):
            return 'invalid-phone'
        digits = re.sub(r'\D', '', value)
        if len(digits) == 10:
            return '1' + digits
        return digits if len(digits) == 11 and digits.startswith('1') else 'invalid-phone'
    if field == 'id_last4':
        return value if re.fullmatch(r'\d{4}', value) else 'invalid-id'
    if field == 'email':
        return value.casefold()
    return ' '.join(value.casefold().split())


def extract_identity(text: str, state: Session, correction: bool = False) -> list[Candidate]:
    """Literal caller spans only; no fixture lookup, inference, or fuzzy matching."""
    subject = 'policyholder' if state.representative else 'caller'
    boundary = r"(?=\s*[,;.!?\n]|$|\s+(?i:and|policy|dob|phone|telephone|email|ssn|with|calling|my|born)\b)"
    named = r"[^\W\d_][\w’'-]*(?:[ \t]+[^\W\d_][\w’'-]*){1,3}?"
    introduced = r"[A-Z][\w’'-]*(?:[ \t]+[A-Z][\w’'-]*){1,3}?"
    patterns = {
        'email': r'[\w.+-]+@[\w.-]+\.[a-zA-Z]{2,}',
        'phone': PHONE,
        'policy_number': r'\bPOL-\d+\b',
        'id_last4': r'(?:(?:ssn|national[- ]?id)(?:[’\']s)?(?:\s+last\s*(?:four|4)(?:\s+digits)?)?|'
                    r'last\s*(?:four|4)(?:\s+digits)?(?:\s+of\s+(?:my\s+)?(?:ssn|national[- ]?id))?)'
                    r'\s*(?:(?:is|are|:|ending(?:\s+in)?|ends in)\s*)?(\d{4})\b',
        'name': rf"(?:(?i:my (?:full )?name is|(?:full )?name\s*(?:is|:))\s+({named})|\bI(?: am|[’']m)\s+({introduced})){boundary}",
        'dob': DATE,
    }
    result = []
    for field, pattern in patterns.items():
        for match in re.finditer(pattern, text, 0 if field == 'name' else re.I):
            if field == 'dob' and not (
                re.search(r'\b(?:dob|date of birth|birth date|birthday|born)\s*(?:is|was|on|:|=)?\s*$', text[:match.start()], re.I)
                or (not state.party_id and text.strip(' .') == match.group())
                or (correction and 'dob' in state.identity and text[:match.start()].strip().casefold() in
                    ('actually', 'correction', 'sorry', 'i meant') and not text[match.end():].strip(' .'))
            ):
                continue
            value = next(g for g in match.groups() if g is not None) if field in ('name', 'id_last4') else match.group()
            kind = 'unspecified'
            if field == 'id_last4':
                kind = 'national_id_last4' if 'national' in match.group().casefold() else 'ssn_last4' if 'ssn' in match.group().casefold() else 'unspecified'
            result.append(Candidate(field=field, value=value, source=value, subject=subject, identifier_type=kind))
    return result


def supported(candidate: Candidate, text: str) -> bool:
    # Values must be supported by this turn, never by the model's knowledge of a person.
    return (candidate.source.casefold() in text.casefold() and
            normalize(candidate.field, candidate.value) == normalize(candidate.field, candidate.source) and
            not normalize(candidate.field, candidate.value).startswith('invalid-'))


def merge_identity(state: Session, candidates: list[Candidate], text: str, message_id: str, correction: bool):
    # Multiple different values in one turn remain contradictory even on a correction turn.
    literal = extract_identity(text, state, correction)
    by_field = {}
    for c in candidates + literal:
        if c.source.casefold() in text.casefold():
            by_field.setdefault(c.field, set()).add(normalize(c.field, c.source))
    blocked = {field for field, values in by_field.items()
               if len(values) > 1 or any(v.startswith('invalid-') for v in values)}
    id_types = {c.identifier_type for c in candidates + literal
                if c.field == 'id_last4' and c.identifier_type != 'unspecified' and supported(c, text)}
    if len(id_types) > 1:
        blocked.add('id_last4')
    for field in blocked:
        if field not in state.conflicts:
            state.conflicts.append(field)
    for c in candidates:
        if c.field in blocked or not supported(c, text):
            continue
        if c.field == 'id_last4' and c.identifier_type == 'unspecified' and len(id_types) == 1:
            # Explicit caller wording cannot be weakened by a model's omitted ID type.
            c = c.model_copy(update={'identifier_type': next(iter(id_types))})
        if state.representative and c.subject == 'caller':
            continue
        old = state.identity.get(c.field)
        if c.field == 'id_last4' and old and c.identifier_type == 'unspecified':
            c = c.model_copy(update={'identifier_type': old.identifier_type})
        different = old and (normalize(c.field, old.value) != normalize(c.field, c.value) or
                             (c.field == 'id_last4' and old.identifier_type != 'unspecified' and
                              c.identifier_type != 'unspecified' and old.identifier_type != c.identifier_type))
        if (different or c.field in state.conflicts) and not correction:
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

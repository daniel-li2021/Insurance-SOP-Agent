"""Provider configuration, independently usable without the SOP controller."""
import os
from uuid import UUID
from typing import Literal
from pydantic import Field, SecretStr, field_validator
from .models import ModelSettings, Session, StrictModel
from .providers import CATALOG, MODEL_DETAILS, make_interpreter, validate_selection

class SettingsRequest(StrictModel):
    request_id: UUID
    version: int = Field(ge=0)
    provider: Literal['openai', 'anthropic', 'gemini', 'scripted']
    model: str = Field(min_length=1, max_length=80)
    credential_source: Literal['demo', 'byok'] = 'demo'
    api_key: SecretStr | None = Field(default=None, min_length=1, max_length=512)
    retain_for_new_sessions: bool = False

    @field_validator('api_key')
    @classmethod
    def safe_key(cls, value):
        if value is not None and any(ord(c)<33 or ord(c)>126 for c in value.get_secret_value()):
            raise ValueError('Use a key without spaces or control characters.')
        return value

class Settings:
    def __init__(self, default_interpreter, allow_local: bool = True):
        self.allow_local = allow_local
        self.default_interpreter = default_interpreter
        self.keys = {p: os.getenv(row['env'], '') if allow_local else '' for p, row in CATALOG.items()}
        provider = 'scripted' if default_interpreter.name == 'scripted' else 'openai'
        self.default = ModelSettings(provider=provider, model=default_interpreter.name)

    def public(self, state: Session):
        selected = state.model_settings or self.default
        return {'current': selected.model_dump(exclude={'api_key'}),
                'default': self.default.model_dump(exclude={'api_key'}),
                'local_credentials_allowed': self.allow_local, 'providers': [
            {'id': p, 'label': row['label'], 'models': row['models'], 'key_url': row['key_url'],
             'demo_configured': bool(self.keys[p]) or p=='scripted', 'validation': row['validation'],
             'model_details': {model: dict(zip(('label', 'description', 'validation'), MODEL_DETAILS[model])) for model in row['models']}}
            for p, row in CATALOG.items()]}

    def candidate(self, payload: SettingsRequest):
        validate_selection(payload.provider, payload.model)
        key = payload.api_key.get_secret_value() if payload.api_key else None
        if payload.provider == 'scripted':
            if key or payload.credential_source != 'demo': raise ValueError('Offline mode does not use credentials.')
        elif payload.credential_source == 'byok':
            if not key: raise ValueError('Enter a provider key to validate this connection.')
        elif not self.allow_local:
            raise ValueError('Public mode requires Bring Your Own Key or Offline Demo.')
        elif key:
            raise ValueError('Choose Bring Your Own Key when supplying a key.')
        elif not self.keys[payload.provider]:
            raise ValueError('No demo key is configured for this provider. Choose Bring Your Own Key.')
        if payload.retain_for_new_sessions and payload.credential_source != 'byok':
            raise ValueError('Only a Bring Your Own Key connection can be retained.')
        return ModelSettings(provider=payload.provider, model=payload.model,
                             credential_source=payload.credential_source, api_key=key,
                             retain_for_new_sessions=payload.retain_for_new_sessions)

    def interpreter(self, state: Session):
        if state.model_settings is None: return self.default_interpreter
        s = state.model_settings
        if s.credential_source == 'byok' and not s.api_key:
            raise ValueError('Missing key — no API call. Open Model settings to enter a key or choose Offline Demo.')
        if not self.allow_local and s.provider != 'scripted' and s.credential_source != 'byok':
            raise ValueError('Public mode requires Bring Your Own Key or Offline Demo.')
        return make_interpreter(s.provider, s.model, s.api_key if s.credential_source=='byok' else self.keys[s.provider])

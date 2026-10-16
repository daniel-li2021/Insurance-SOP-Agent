"""Provider configuration, independently usable without the SOP controller."""
import os
from uuid import UUID
from typing import Literal
from pydantic import Field, SecretStr, field_validator
from .models import ModelSettings, Session, StrictModel
from .providers import CATALOG, make_interpreter, validate_selection

class SettingsRequest(StrictModel):
    request_id: UUID
    version: int = Field(ge=0)
    provider: Literal['openai', 'anthropic', 'gemini', 'scripted']
    model: str = Field(min_length=1, max_length=80)
    credential_source: Literal['demo', 'byok'] = 'demo'
    api_key: SecretStr | None = Field(default=None, min_length=1, max_length=512)

    @field_validator('api_key')
    @classmethod
    def safe_key(cls, value):
        if value is not None and any(ord(c)<33 or ord(c)>126 for c in value.get_secret_value()):
            raise ValueError('Use a key without spaces or control characters.')
        return value

class Settings:
    def __init__(self, default_interpreter):
        self.default_interpreter = default_interpreter
        self.keys = {p: os.getenv(row['env'], '') for p, row in CATALOG.items()}
        provider = 'scripted' if default_interpreter.name == 'scripted' else 'openai'
        self.default = ModelSettings(provider=provider, model=default_interpreter.name)

    def public(self, state: Session):
        selected = state.model_settings or self.default
        return {'current': selected.model_dump(exclude={'api_key'}), 'providers': [
            {'id': p, 'label': row['label'], 'models': row['models'], 'key_url': row['key_url'],
             'demo_configured': bool(self.keys[p]) or p=='scripted', 'validation': row['validation']}
            for p, row in CATALOG.items()]}

    def candidate(self, payload: SettingsRequest):
        validate_selection(payload.provider, payload.model)
        key = payload.api_key.get_secret_value() if payload.api_key else None
        if payload.provider == 'scripted':
            if key or payload.credential_source != 'demo': raise ValueError('Offline mode does not use credentials.')
        elif payload.credential_source == 'byok':
            if not key: raise ValueError('Enter a provider key to validate this connection.')
        elif key:
            raise ValueError('Choose Bring Your Own Key when supplying a key.')
        elif not self.keys[payload.provider]:
            raise ValueError('No demo key is configured for this provider. Choose Bring Your Own Key.')
        return ModelSettings(provider=payload.provider, model=payload.model,
                             credential_source=payload.credential_source, api_key=key)

    def interpreter(self, state: Session):
        if state.model_settings is None: return self.default_interpreter
        s = state.model_settings
        return make_interpreter(s.provider, s.model, s.api_key if s.credential_source=='byok' else self.keys[s.provider])

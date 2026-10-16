"""Small native provider boundary: fixed hosts, curated models, one validated schema."""
import json
import time
from typing import Protocol
import httpx
from pydantic import BaseModel, Field, SecretStr
from .interpreter import INSTRUCTIONS, LiveInterpreter, ModelFailure, ScriptedInterpreter, safe_context
from .models import Interpretation, Session

CATALOG = {
    'openai': {'label': 'OpenAI', 'models': ['gpt-6.1-sol'], 'env': 'OPENAI_API_KEY',
               'key_url': 'https://platform.openai.com/api-keys', 'validation': 'Live acceptance checked'},
    'anthropic': {'label': 'Anthropic Claude', 'models': ['claude-sonnet-5-5'], 'env': 'ANTHROPIC_API_KEY',
                  'key_url': 'https://platform.claude.com/settings/keys', 'validation': 'Contract checked; live acceptance pending'},
    'gemini': {'label': 'Google Gemini', 'models': ['gemini-3.8-flash'], 'env': 'GEMINI_API_KEY',
               'key_url': 'https://aistudio.google.com/apikey', 'validation': 'Contract checked; live acceptance pending'},
    'scripted': {'label': 'Offline', 'models': ['scripted'], 'env': '', 'key_url': '', 'validation': 'Deterministic parser; limited language support'},
}

class Interpreter(Protocol):
    name: str
    async def interpret(self, text: str, state: Session) -> tuple[Interpretation, dict]: ...

class Usage(BaseModel):
    tokens: int = Field(ge=1, le=12000)


def validate_selection(provider: str, model: str):
    if provider not in CATALOG or model not in CATALOG[provider]['models']:
        raise ValueError('Choose a supported provider and model.')


def provider_schema():
    # Claude omits these decoder constraints; Pydantic still enforces all of them.
    def clean(value):
        if isinstance(value, list): return [clean(v) for v in value]
        if not isinstance(value, dict): return value
        constraints = {k: v for k, v in value.items() if k in ('minimum', 'maximum', 'minLength', 'maxLength', 'maxItems', 'minItems')}
        out = {k: clean(v) for k, v in value.items() if k not in (*constraints, 'default', 'title')}
        if constraints: out['description'] = out.get('description', '') + ' Constraints: ' + json.dumps(constraints)
        return out
    return clean(Interpretation.model_json_schema())


class NativeInterpreter:
    def __init__(self, provider: str, model: str, key: str):
        validate_selection(provider, model)
        self.provider, self.name = provider, model
        self._key = SecretStr(key)

    async def interpret(self, text: str, state: Session):
        started = time.monotonic()
        content = f'Safe context: {safe_context(state)}\nCaller message: {text}'
        schema = provider_schema()
        if self.provider == 'anthropic':
            url = 'https://api.anthropic.com/v1/messages'
            headers = {'x-api-key': self._key.get_secret_value(), 'anthropic-version': '2023-06-01'}
            body = {'model': self.name, 'max_tokens': 2200, 'system': INSTRUCTIONS,
                    'messages': [{'role': 'user', 'content': content}],
                    'output_config': {'format': {'type': 'json_schema', 'schema': schema}}}
        else:
            url = f'https://generativelanguage.googleapis.com/v1beta/models/{self.name}:generateContent'
            headers = {'x-goog-api-key': self._key.get_secret_value()}
            body = {'systemInstruction': {'parts': [{'text': INSTRUCTIONS}]},
                    'contents': [{'role': 'user', 'parts': [{'text': content}]}],
                    'generationConfig': {'maxOutputTokens': 2200,
                                         'responseFormat': {'text': {'mimeType': 'application/json', 'schema': schema}}}}
        try:
            async with httpx.AsyncClient(timeout=25, follow_redirects=False) as client:
                response = await client.post(url, headers=headers, json=body)
            if response.status_code != 200:
                raise ModelFailure(provider_error(response.status_code))
            data = response.json()
            if self.provider == 'anthropic':
                if data['stop_reason'] != 'end_turn': raise ValueError('Incomplete output')
                blocks = data['content']
                if len(blocks) != 1 or blocks[0]['type'] != 'text': raise ValueError('Unexpected content')
                output = blocks[0]['text']
                usage = data['usage']
                tokens = sum(usage.get(k, 0) for k in ('input_tokens', 'output_tokens', 'cache_creation_input_tokens', 'cache_read_input_tokens'))
            else:
                candidate = data['candidates'][0]
                if candidate['finishReason'] != 'STOP': raise ValueError('Incomplete output')
                parts = candidate['content']['parts']
                output = ''.join(p['text'] for p in parts if not p.get('thought'))
                tokens = data['usageMetadata']['totalTokenCount']
            parsed = Interpretation.model_validate_json(output, strict=True)
            return parsed, {'tokens': Usage(tokens=tokens).tokens, 'latency_ms': round((time.monotonic()-started)*1000)}
        except ModelFailure:
            raise
        except Exception:
            raise ModelFailure('Invalid or unavailable structured interpretation. Retry or choose another model.') from None


def provider_error(status: int):
    if status in (401, 403): return 'The provider rejected these credentials or model access. Check the key and permissions.'
    if status == 429: return 'The provider quota or rate limit was reached. Check billing or retry later.'
    if status in (400, 404): return 'The provider could not accept this model request. Check model access or choose another provider.'
    return 'The provider is unavailable. Please retry later.'


def make_interpreter(provider: str, model: str, key: str | None = None) -> Interpreter:
    validate_selection(provider, model)
    if provider == 'scripted': return ScriptedInterpreter()
    if not key: raise ValueError('No demo key is configured for this provider. Choose Bring Your Own Key.')
    if provider == 'openai': return LiveInterpreter(key, model)
    return NativeInterpreter(provider, model, key)

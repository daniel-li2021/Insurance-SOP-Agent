import asyncio
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock
import httpx
import pytest
from backend.interpreter import LiveInterpreter, ModelFailure, safe_context
from backend.models import Interpretation, ModelSettings, Session
from backend.providers import NativeInterpreter, CATALOG, make_interpreter, provider_schema


@pytest.mark.parametrize('provider', ['anthropic', 'gemini'])
@pytest.mark.parametrize('failure', ['', 'malformed', 'schema', 'refusal', 'usage', '401', '429', 'redirect', 'timeout'])
def test_native_contract(monkeypatch, provider, failure):
    key = 'private-contract-key'
    output = Interpretation(emotion='anxious', topics=['alternatives']).model_dump_json()
    if failure == 'malformed': output = 'not json'
    if failure == 'schema': output = json.dumps({'month':13, 'party_id':'P9'})
    def handler(request):
        assert request.url.scheme=='https' and key not in str(request.url)
        body=json.loads(request.content)
        assert 'tools' not in body and 'api_key' not in request.content.decode()
        if provider=='anthropic':
            assert request.url.host=='api.anthropic.com' and request.headers['x-api-key']==key
            assert body['output_config']['format']['schema']==provider_schema()
            data={'stop_reason':'refusal' if failure=='refusal' else 'end_turn',
                  'content':[{'type':'text','text':output}], 'usage':{'input_tokens':20,'output_tokens':30}}
        else:
            assert request.url.host=='generativelanguage.googleapis.com' and request.headers['x-goog-api-key']==key
            assert body['generationConfig']['responseFormat']['text']['schema']==provider_schema()
            data={'candidates':[{'finishReason':'SAFETY' if failure=='refusal' else 'STOP','content':{'parts':[{'text':output}]}}],
                  'usageMetadata':{'totalTokenCount':50}}
        if failure=='usage':
            data['usage' if provider=='anthropic' else 'usageMetadata']={}
        if failure=='timeout': raise httpx.ReadTimeout('secret '+key)
        if failure in ('401','429','redirect'):
            return httpx.Response(302 if failure=='redirect' else int(failure), json={'error':key},headers={'location':'https://attacker.example'})
        return httpx.Response(200,json=data)
    original=httpx.AsyncClient
    monkeypatch.setattr(httpx,'AsyncClient',lambda **kw: original(transport=httpx.MockTransport(handler),**kw))
    adapter=NativeInterpreter(provider,CATALOG[provider]['models'][0],key)
    if failure:
        with pytest.raises(ModelFailure) as exc: asyncio.run(adapter.interpret('I am worried',Session()))
        assert key not in str(exc.value)
    else:
        parsed,usage=asyncio.run(adapter.interpret('I am worried',Session()))
        assert parsed.emotion=='anxious' and usage['tokens']==50


def test_openai_contract():
    async def run():
        adapter=LiveInterpreter('private-contract-key')
        await adapter.client.close()
        parse=AsyncMock(return_value=SimpleNamespace(output_parsed=Interpretation(topics=['documents']),usage=SimpleNamespace(total_tokens=60)))
        adapter.client=SimpleNamespace(responses=SimpleNamespace(parse=parse))
        parsed,usage=await adapter.interpret('Documents?',Session())
        assert parsed.topics==['documents'] and usage['tokens']==60
        args=parse.call_args.kwargs
        assert args['text_format'] is Interpretation and args['store'] is False
        assert args['max_output_tokens']==2200 and args['reasoning']=={'effort':'low'} and 'tools' not in args
        parse.return_value=SimpleNamespace(output_parsed=None)
        with pytest.raises(ModelFailure): await adapter.interpret('x',Session())
    asyncio.run(run())


def test_catalog_and_context_do_not_accept_arbitrary_models_or_secrets():
    with pytest.raises(ValueError): make_interpreter('gemini','https://attacker.example','secret')
    with pytest.raises(ValueError): make_interpreter('openai','untested-model','secret')
    state=Session(model_settings=ModelSettings(provider='openai',model='gpt-6.1-sol',credential_source='byok',api_key='private-contract-key'))
    assert 'private-contract-key' not in str(safe_context(state))
    def check(node):
        if isinstance(node,dict):
            assert not {'maximum','maxLength','maxItems','default'} & node.keys()
            for value in node.values(): check(value)
        elif isinstance(node,list):
            for value in node: check(value)
    check(provider_schema())

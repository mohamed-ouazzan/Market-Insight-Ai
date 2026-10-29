"""Résultat LLM explicite ; ni secrets, ni messages d'erreur du fournisseur affichés."""
from dataclasses import dataclass
import json
import os
import requests
from dotenv import load_dotenv
from pathlib import Path

load_dotenv(Path(__file__).with_name('.env'), encoding='utf-8-sig')


@dataclass
class LLMResult:
    status: str
    payload: object = None
    code: str | None = None


def _get_api_key():
    return os.getenv('LLM_API_KEY') or os.getenv('OPENAI_API_KEY')


def llm_available():
    return bool(_get_api_key())


def llm_configuration():
    provider = (os.getenv('LLM_PROVIDER') or 'openai').lower()
    return dict(configured=bool(_get_api_key()), provider=provider if provider in {'openai', 'openai_compatible'} else 'non pris en charge',
                model_configured=bool(os.getenv('OPENAI_MODEL')), structure='blocs et coordonnées PDF', visual=False)


def call_llm_json_result(prompt, model=None):
    if not _get_api_key():
        return LLMResult('not_configured')
    provider = (os.getenv('LLM_PROVIDER') or 'openai').lower()
    if provider not in {'openai', 'openai_compatible'}:
        return LLMResult('unsupported_provider')
    endpoint = os.getenv('OPENAI_BASE_URL') or ('https://api.openai.com/v1/chat/completions' if provider == 'openai' else None)
    if not endpoint:
        return LLMResult('invalid_configuration')
    try:
        response = requests.post(endpoint, headers={'Authorization': 'Bearer ' + _get_api_key(), 'Content-Type': 'application/json'},
            json={'model': model or os.getenv('OPENAI_MODEL') or 'gpt-4o-mini', 'messages': [{'role': 'user', 'content': prompt}], 'temperature': 0.1}, timeout=(10,60))
        if not response.ok:
            return LLMResult('http_error', code=str(response.status_code))
        try:
            content = response.json()['choices'][0]['message']['content']
        except (ValueError, KeyError, IndexError, TypeError):
            return LLMResult('invalid_response')
        try:
            payload = json.loads(content)
        except (ValueError, TypeError):
            return LLMResult('invalid_json')
        if not isinstance(payload, list):
            return LLMResult('invalid_response')
        return LLMResult('empty' if not payload else 'success', payload)
    except requests.Timeout:
        return LLMResult('timeout')
    except requests.RequestException:
        return LLMResult('transport_error')


def call_llm_json(prompt, model=None):
    result = call_llm_json_result(prompt, model)
    return result.payload if result.status in {'success', 'empty'} else None

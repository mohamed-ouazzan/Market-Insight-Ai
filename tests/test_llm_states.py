import pytest
import requests
from llm_client import LLMResult,call_llm_json_result
from extract_offers_ai import extract_offers_with_metadata,OFFER_FIELDS


def test_valid_empty_answer_never_triggers_fallback(monkeypatch):
    monkeypatch.setattr('extract_offers_ai.call_llm_json_result',lambda _:LLMResult('empty',[]))
    result=extract_offers_with_metadata({1:'Fibre 200 Mbps\n700 DH TTC /mois'})
    assert result.offers==[] and result.mode=='LLM'
    assert result.diagnostics[0]['llm']=='réponse valide sans offre'


@pytest.mark.parametrize('status',['not_configured','timeout','transport_error','invalid_json','http_error','unsupported_provider'])
def test_technical_failure_is_visible_and_can_fall_back(monkeypatch,status):
    monkeypatch.setattr('extract_offers_ai.call_llm_json_result',lambda _:LLMResult(status))
    result=extract_offers_with_metadata({1:'Fibre 200 Mbps\n700 DH TTC /mois'})
    assert len(result.offers)==1 and result.mode=='Règles de secours'
    assert result.diagnostics[0]['llm']!='réponse valide sans offre'


def test_page_number_is_program_owned(monkeypatch):
    text='Fibre 200 Mbps\n700 DH TTC /mois'
    item={k:None for k in OFFER_FIELDS}
    item.update(nom_offre='Fibre 200',technologie='Fibre',debit_mbps=200,prix_mensuel_ttc=700,
                page_source=999,extrait_source=text)
    monkeypatch.setattr('extract_offers_ai.call_llm_json_result',lambda _:LLMResult('success',[item]))
    result=extract_offers_with_metadata({7:text})
    assert result.offers[0]['page_source']==7 and result.mode=='LLM'


def test_adsl_migration_does_not_remove_fibre_offer(monkeypatch):
    monkeypatch.setattr('extract_offers_ai.call_llm_json_result',lambda _:LLMResult('not_configured'))
    result=extract_offers_with_metadata({1:'Fibre 200 Mbps\n700 DH TTC /mois\nMigration ADSL vers Fibre possible.'})
    assert len(result.offers)==1
    assert not extract_offers_with_metadata({1:'Offre ADSL 20 Mbps\n100 DH TTC /mois\nMigration vers la Fibre possible.'},use_llm=False).offers


def test_no_api_key_is_explicit(monkeypatch):
    monkeypatch.delenv('LLM_API_KEY',raising=False);monkeypatch.delenv('OPENAI_API_KEY',raising=False)
    assert call_llm_json_result('test').status=='not_configured'


def test_network_error_does_not_expose_secret(monkeypatch,capsys):
    monkeypatch.setenv('LLM_API_KEY','secret-test-do-not-display')
    monkeypatch.setenv('LLM_PROVIDER','openai')
    def broken(*args,**kwargs):raise requests.ConnectionError('secret-test-do-not-display')
    monkeypatch.setattr('llm_client.requests.post',broken)
    result=call_llm_json_result('test')
    assert result.status=='transport_error'
    assert 'secret-test' not in str(result) and 'secret-test' not in capsys.readouterr().out


def test_partial_image_page_has_ocr_diagnostic():
    from extract_pdf import SourcePages
    pages=SourcePages({1:'Fibre'},layout={1:dict(needs_ocr=True,images=1,lines=[],tables=[],width=100,height=100,words=[])})
    result=extract_offers_with_metadata(pages,use_llm=False)
    assert any('OCR' in note for note in result.diagnostics[0]['attention'])

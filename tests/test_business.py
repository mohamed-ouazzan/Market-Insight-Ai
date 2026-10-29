import pytest
from analyse_offers import _prepare_offers_frame, analyse_dataframe, compute_missed_tiers, create_price_chart
from extract_offers_ai import validate_offer, OFFER_FIELDS, extract_offers_with_metadata
from generate_report import build_report
from catalogue_storage import catalogue_name


def test_same_speed_and_competing_operators_only(offer):
    rows = [offer, {**offer, 'id_offre': 2, 'prix_mensuel_ttc': 600},
            {**offer, 'id_offre': 3, 'operateur': 'Orange', 'prix_mensuel_ttc': 500},
            {**offer, 'id_offre': 4, 'operateur': 'inwi', 'debit_mbps': 100, 'prix_mensuel_ttc': 250}]
    df = analyse_dataframe(_prepare_offers_frame(rows))
    assert df.loc[0, 'prix_median_market'] == 600
    assert df.loc[0, 'rang_operateur'] == 2
    assert df.loc[2, 'rang_operateur'] == 1
    assert df.loc[3, 'rang_operateur'] != df.loc[3, 'rang_operateur']  # NaN, pas de concurrent au palier
    assert compute_missed_tiers('Maroc Telecom', frame=df) == [100]


def test_single_offer_no_market_conclusion(offer):
    df = analyse_dataframe(_prepare_offers_frame([offer]))
    assert df.prix_par_100_mbps.iloc[0] == 350
    assert df.rang_operateur.isna().all()
    assert create_price_chart(df) is None
    md, html = build_report(df, 'Maroc Telecom')
    assert 'Une seule offre validée' in md
    assert '2025' in md and 'test.pdf' in md
    assert 'Routeur distinct' in html


def test_missing_and_zero_are_not_confused(offer):
    df = analyse_dataframe(_prepare_offers_frame([{**offer, 'debit_mbps': None, 'prix_mensuel_ttc': None}]))
    assert df.prix_par_100_mbps.isna().all()
    assert 'Non précisé' in build_report(df, 'Orange')[0]


def test_quote_and_pydantic_after_editing(offer):
    data = {key: offer[key] for key in OFFER_FIELDS}
    assert validate_offer(data, {1: offer['extrait_source']})['debit_mbps'] == 200
    with pytest.raises(ValueError):
        validate_offer({**data, 'page_source': 2}, {1: offer['extrait_source']})
    with pytest.raises(ValueError):
        validate_offer({**data, 'prix_mensuel_ttc': -5}, {1: offer['extrait_source']})
    with pytest.raises(ValueError):
        validate_offer({**data, 'extrait_source': 'invention'}, {1: offer['extrait_source']})


def test_fallback_is_labeled_and_avoids_volume(monkeypatch):
    from llm_client import LLMResult
    monkeypatch.setattr('extract_offers_ai.call_llm_json_result', lambda _: LLMResult('not_configured'))
    text = 'Fibre 200 Mbps\n700 DH TTC /mois\nRouteur 200 DH TTC'
    result = extract_offers_with_metadata({1: text})
    assert result.mode == 'Règles de secours'
    assert result.offers[0]['debit_mbps'] == 200
    assert result.offers[0]['frais_installation_ttc'] is None
    assert not extract_offers_with_metadata({1: 'Fibre 100 Go\n300 DH TTC /mois'}).offers


def test_llm_invalid_quote_falls_back(monkeypatch, offer):
    from llm_client import LLMResult
    data = {k: offer[k] for k in OFFER_FIELDS}
    monkeypatch.setattr('extract_offers_ai.call_llm_json_result', lambda _: LLMResult('success', [{**data, 'extrait_source': 'inventé'}]))
    result = extract_offers_with_metadata({1: offer['extrait_source']})
    assert result.rejected == 1
    assert result.mode == 'Règles de secours'


def test_report_escapes_source_html(offer):
    df = analyse_dataframe(_prepare_offers_frame([{**offer, 'nom_offre': '<script>alert(1)</script>'}]))
    md, html = build_report(df, 'Orange')
    assert '<script>' not in html and '<script>' not in md


def test_file_fingerprint_survives_rename():
    assert catalogue_name('A.pdf', b'PDF').split('__')[1] == catalogue_name('B.pdf', b'PDF').split('__')[1]


def test_save_requires_page_proof_before_sql(monkeypatch, offer):
    from save_offers import save_offers_from_preview
    monkeypatch.setattr('save_offers.get_connection', lambda: pytest.fail('Ne doit pas accéder à SQL'))
    with pytest.raises(ValueError):
        save_offers_from_preview([{k: offer[k] for k in OFFER_FIELDS}], 'test.pdf', 'Orange', pages={1: 'Autre texte'})

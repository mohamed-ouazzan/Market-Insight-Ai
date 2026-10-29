import pytest
from provenance import separate_records,is_synthetic
from analyse_offers import _prepare_offers_frame
from analyse_offers import analyse_dataframe,ORIGIN,REAL,SIMULATED,create_price_chart
from generate_report import build_report
from analyst_repository import review_offer


def test_demo_is_excluded_even_with_real_operator_name(offer):
    demo={**offer,'nom_offre':'DEMO50 Offre 1','edition':'DEMO - Donnees simulees'}
    real,synthetic=separate_records([offer,demo])
    assert real==[offer] and synthetic==[demo]
    assert len(_prepare_offers_frame([offer,demo]))==1


def test_synthetic_offer_cannot_be_published(monkeypatch,offer):
    demo={**offer,'extrait_source':'Offre fictive générée par SQL'}
    monkeypatch.setattr('analyst_repository.get_connection',lambda:pytest.fail('Aucune écriture attendue'))
    with pytest.raises(ValueError):
        review_offer(1,demo,demo,validate=True,pages={1:demo['extrait_source']})


def test_medians_and_ranks_do_not_mix_real_and_simulated_prices(offer):
    rows=[offer,{**offer,'operateur':'Orange','id_offre':2,'nom_offre':'DEMO50 Orange','prix_mensuel_ttc':100},
          {**offer,'operateur':'inwi','id_offre':3,'nom_offre':'DEMO50 inwi','prix_mensuel_ttc':200}]
    df=analyse_dataframe(_prepare_offers_frame(rows,dataset='all'))
    real=df[df[ORIGIN]==REAL]
    demo=df[df[ORIGIN]==SIMULATED]
    assert real.prix_median_market.isna().all() and real.rang_operateur.isna().all()
    assert demo.prix_median_market.tolist()==[150,150]
    assert demo.rang_operateur.tolist()==[1,2]
    chart=create_price_chart(df)
    assert 'simulations' in chart.layout.title.text
    assert {trace.name for trace in chart.data}=={'Orange','inwi'}


def test_real_and_simulated_reports_are_separate_and_labeled(offer):
    demo={**offer,'nom_offre':'DEMO50 Orange','operateur':'Orange'}
    df=analyse_dataframe(_prepare_offers_frame([offer,demo],dataset='all'))
    with pytest.raises(ValueError):build_report(df,'Orange')
    with pytest.raises(ValueError):build_report(df,'Orange',dataset='simulated')
    md,html=build_report(df[df[ORIGIN]==SIMULATED],'Orange',dataset='simulated')
    assert 'TARIFS FICTIFS' in md and 'TARIFS FICTIFS' in html
    assert 'Aucun tarif officiel' in md
    real_md,real_html=build_report(df[df[ORIGIN]==REAL],'Orange')
    assert 'DEMO50' not in real_md and '<h1>Market Insight AI</h1>' in real_html

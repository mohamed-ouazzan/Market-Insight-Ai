import pytest
from pathlib import Path
from streamlit.testing.v1 import AppTest
import analyst_repository as repo
import db_connection
from extract_offers_ai import OFFER_FIELDS
from ui_common import offer_frame


@pytest.fixture
def app(monkeypatch, offer):
    monkeypatch.setattr(repo, 'read_counts', lambda: dict(catalogues=3, validees=1, en_attente=0))
    monkeypatch.setattr(repo, 'read_operators', lambda: [dict(id_operateur=1, nom='Maroc Telecom')])
    monkeypatch.setattr(repo, 'read_pending', lambda: [])
    monkeypatch.setattr(repo, 'read_catalogues', lambda: [])
    monkeypatch.setattr(db_connection, 'read_valid_offers', lambda limit=None: [offer])
    return AppTest.from_file(Path(__file__).resolve().parents[1] / 'app.py', default_timeout=20).run()


def test_three_pages_and_single_offer(app):
    assert not app.exception
    assert [metric.value for metric in app.metric] == ['3', '1', '0']
    app.switch_page('pages/1_Espace_Client.py').run()
    assert not app.exception
    assert any('Une seule offre validée' in item.value for item in app.info)
    assert len(app.get('plotly_chart')) == 0
    assert 'Opérateur' in app.dataframe[0].value.columns
    app.multiselect[0].set_value([]).run()
    assert not app.exception
    assert any('Aucune offre ne correspond' in item.value for item in app.info)
    app.switch_page('pages/2_Espace_Analyste.py').run()
    assert not app.exception
    assert any('Aucune offre en attente' in item.value for item in app.info)


def test_database_unavailable_is_not_empty(monkeypatch, app):
    def unavailable(*args, **kwargs):
        raise RuntimeError('sensitive configuration must not be exposed')
    monkeypatch.setattr(db_connection, 'read_valid_offers', unavailable)
    app.switch_page('pages/1_Espace_Client.py').run()
    assert not app.exception
    assert 'Connexion à la base indisponible' in app.error[0].value
    assert 'sensitive' not in app.error[0].value
    monkeypatch.setattr(repo, 'read_counts', unavailable)
    app.switch_page('pages/0_Accueil.py').run()
    assert not app.exception and len(app.metric) == 0


def test_empty_validated_view(monkeypatch, app):
    monkeypatch.setattr(db_connection, 'read_valid_offers', lambda limit=None: [])
    app.switch_page('pages/1_Espace_Client.py').run()
    assert not app.exception
    assert any('Aucune offre Fibre B2C validée' in item.value for item in app.info)


def test_multiple_operators_filters_and_editions(monkeypatch, app, offer):
    monkeypatch.setattr(db_connection, 'read_valid_offers', lambda limit=None: [offer,
        {**offer, 'id_offre': 2, 'operateur': 'Orange', 'prix_mensuel_ttc': 500, 'edition': '2023'}])
    app.switch_page('pages/1_Espace_Client.py').run()
    assert not app.exception
    assert len(app.get('plotly_chart')) == 3
    assert any('éditions' in item.value for item in app.warning)
    app.multiselect[1].set_value(['2025']).run()
    assert not app.exception and len(app.get('plotly_chart')) == 0


def test_import_draft_persists_across_pages(app, offer):
    app.session_state['import_draft'] = dict(pages={1: offer['extrait_source']}, operator='Maroc Telecom',
        edition='2025', url=None, name='test.pdf', original='test.pdf', mode='Règles de secours', rejected=0)
    app.session_state['import_revision'] = 1
    app.session_state['preview_1'] = offer_frame([{k: offer[k] for k in OFFER_FIELDS}])
    app.switch_page('pages/2_Espace_Analyste.py').run()
    assert not app.exception
    app.session_state['editor_preview_1'] = dict(edited_rows={0: {'prix_mensuel_ttc': 650}}, added_rows=[], deleted_rows=[])
    app.run()
    assert app.session_state['preview_1'].iloc[0].prix_mensuel_ttc == 650
    app.switch_page('pages/0_Accueil.py').run()
    app.switch_page('pages/2_Espace_Analyste.py').run()
    assert not app.exception
    assert app.session_state['preview_1'].iloc[0].prix_mensuel_ttc == 650


def test_human_validation_is_explicit(monkeypatch, app, offer):
    monkeypatch.setattr(repo, 'read_pending', lambda: [{**offer, 'id_catalogue': 1}])
    monkeypatch.setattr('catalogue_storage.source_pages', lambda _: {1: offer['extrait_source']})
    calls = []
    monkeypatch.setattr(repo, 'review_offer', lambda *args, **kwargs: calls.append(kwargs))
    app.switch_page('pages/2_Espace_Analyste.py').run()
    assert not app.exception
    button = next(b for b in app.button if b.label == 'Valider et publier dans l’étude')
    assert button.disabled and not calls
    app.checkbox[0].check().run()
    next(b for b in app.button if b.label == 'Valider et publier dans l’étude').click().run()
    assert not app.exception and calls[0]['validate'] is True


def test_empty_home_and_analyst_unavailable(monkeypatch,app):
    monkeypatch.setattr(repo,'read_counts',lambda:dict(catalogues=0,validees=0,en_attente=0))
    app.switch_page('pages/0_Accueil.py').run()
    assert not app.exception and [m.value for m in app.metric]==['0','0','0']
    def unavailable():raise RuntimeError('configuration sensible')
    monkeypatch.setattr(repo,'read_operators',unavailable)
    app.switch_page('pages/2_Espace_Analyste.py').run()
    assert not app.exception and any('Connexion à la base indisponible' in e.value for e in app.error)


def test_demo_data_does_not_create_a_competitive_chart(monkeypatch,app,offer):
    monkeypatch.setattr(db_connection,'read_valid_offers',lambda limit=None:[offer,
        {**offer,'id_offre':2,'operateur':'Orange','nom_offre':'DEMO50 - Fibre 200','edition':'DEMO - Donnees simulees'}])
    app.switch_page('pages/1_Espace_Client.py').run()
    assert not app.exception and len(app.get('plotly_chart'))==0
    assert len(app.dataframe[0].value)==2
    assert any('pas des tarifs officiels' in w.value for w in app.warning)
    next(w for w in app.selectbox if w.label=='Données à afficher').select('Catalogues réels uniquement').run()
    assert len(app.dataframe[0].value)==1


def test_all_three_sql_operators_selected_and_client_does_not_filter_competitors(monkeypatch,app,offer):
    rows=[offer]+[{**offer,'id_offre':i,'operateur':op,'nom_offre':f'DEMO50 {op}',
                   'edition':'DEMO - Donnees simulees','prix_mensuel_ttc':price}
                  for i,op,price in [(2,'Maroc Telecom',400),(3,'Orange',450),(4,'inwi',500)]]
    monkeypatch.setattr(db_connection,'read_valid_offers',lambda limit=None:rows)
    app.switch_page('pages/1_Espace_Client.py').run()
    assert not app.exception
    operators=next(w for w in app.multiselect if w.label=='Opérateurs comparés')
    assert operators.options==['Maroc Telecom','Orange','inwi']
    assert operators.value==operators.options
    assert len(app.dataframe[0].value)==4
    next(w for w in app.selectbox if w.label=='Votre opérateur').select('Orange').run()
    assert not app.exception and len(app.dataframe[0].value)==4
    assert set(app.dataframe[0].value['Opérateur'])=={'Maroc Telecom','Orange','inwi'}
    assert 'Origine des données' in app.dataframe[0].value.columns
    assert len(app.get('plotly_chart'))==3  # Comparaison simulée, jamais avec l'offre réelle.


def test_operator_choices_follow_new_sql_data_and_are_not_hardcoded(monkeypatch,app,offer):
    rows=[offer]
    monkeypatch.setattr(db_connection,'read_valid_offers',lambda limit=None:rows)
    app.switch_page('pages/1_Espace_Client.py').run()
    next(w for w in app.multiselect if w.label=='Opérateurs comparés').set_value([]).run()
    rows.append({**offer,'id_offre':2,'operateur':'Nouvel opérateur SQL'})
    next(b for b in app.button if b.label=='Actualiser les offres').click().run()
    assert not app.exception
    compared=next(w for w in app.multiselect if w.label=='Opérateurs comparés')
    assert compared.value==['Maroc Telecom','Nouvel opérateur SQL']
    assert next(w for w in app.selectbox if w.label=='Votre opérateur').options==compared.options


def test_simulated_scope_never_imports_real_rows(monkeypatch,app,offer):
    rows=[offer,{**offer,'id_offre':2,'operateur':'Orange','nom_offre':'DEMO50 Orange'}]
    monkeypatch.setattr(db_connection,'read_valid_offers',lambda limit=None:rows)
    app.switch_page('pages/1_Espace_Client.py').run()
    next(w for w in app.selectbox if w.label=='Données à afficher').select('Offres de test simulées uniquement').run()
    assert not app.exception
    assert next(w for w in app.multiselect if w.label=='Opérateurs comparés').value==['Orange']
    assert app.dataframe[0].value['Origine des données'].str.contains('fictifs').all()

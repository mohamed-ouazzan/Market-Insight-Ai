"""Test explicite de la vraie base ; toute écriture est annulée en fin de test."""
import os
import uuid
import pytest


@pytest.mark.skipif(os.getenv('RUN_SQL_INTEGRATION') != '1', reason='Test SQL local facultatif')
def test_import_duplicate_validate_reject_rolled_back(monkeypatch):
    import db_connection
    import save_offers
    import analyst_repository as repo
    from catalogue_storage import catalogue_name
    from extract_offers_ai import OFFER_FIELDS

    real = db_connection.get_connection()

    class TransactionOnly:
        def cursor(self):
            return real.cursor()

        def commit(self):
            pass  # La transaction englobante restera ouverte.

        def rollback(self):
            pass  # L'annulation réelle est garantie par finally.

        def close(self):
            pass

    proxy = TransactionOnly()
    for module in (db_connection, save_offers, repo):
        monkeypatch.setattr(module, 'get_connection', lambda: proxy)
    token = uuid.uuid4().hex
    text = f'Fibre QA {token} 200 Mbps : 700 DH TTC /mois'
    data = dict(nom_offre='QA ' + token, technologie='Fibre', debit_mbps=200,
                prix_mensuel_ttc=700, engagement_mois=None, frais_installation_ttc=None,
                appels_inclus=None, conditions_offre=None, page_source=1, extrait_source=text)
    content = token.encode()
    try:
        operator = repo.read_operators()[0]['nom']
        name = catalogue_name('QA.pdf', content)
        result = save_offers.save_offers_from_preview([data, {**data, 'nom_offre': 'QA rejet ' + token}],
                                                     name, operator, pages={1: text})
        assert result['saved_count'] == 2
        addition = save_offers.save_offers_from_preview([{**data, 'nom_offre': 'QA ajout ' + token}],
                                                       name, operator, pages={1: text})
        assert addition['saved_count'] == 1
        duplicate = save_offers.save_offers_from_preview([data], catalogue_name('renomme.pdf', content),
                                                        operator, pages={1: text})
        assert duplicate['already_exists'] and duplicate['saved_count'] == 0
        rows = [r for r in repo.read_pending() if token in r['nom_offre']]
        assert len(rows) == 3
        row = rows[0]
        assert all(r['id_offre'] != row['id_offre'] for r in db_connection.read_valid_offers())
        repo.review_offer(row['id_offre'], row, {k: row[k] for k in OFFER_FIELDS}, validate=True, pages={1: text})
        assert any(r['id_offre'] == row['id_offre'] for r in db_connection.read_valid_offers())
        row = rows[1]
        repo.review_offer(row['id_offre'], row, reject=True)
        assert not any(r['id_offre'] == row['id_offre'] for r in repo.read_pending())
    finally:
        real.rollback()
        real.close()


@pytest.mark.skipif(os.getenv('RUN_SQL_INTEGRATION') != '1', reason='Test SQL local facultatif')
def test_three_real_pdf_imports_incrementally_and_roll_back(monkeypatch):
    from pathlib import Path
    import db_connection
    import save_offers
    import analyst_repository as repo
    from extract_pdf import extract_pdf_pages
    from extract_offers_ai import extract_offers_with_metadata,OFFER_FIELDS
    from catalogue_storage import catalogue_name
    from analyse_offers import _prepare_offers_frame

    real=db_connection.get_connection()
    class TransactionOnly:
        def cursor(self):return real.cursor()
        def commit(self):pass
        def rollback(self):pass
        def close(self):pass
    proxy=TransactionOnly()
    for module in (db_connection,save_offers,repo):monkeypatch.setattr(module,'get_connection',lambda:proxy)
    data=Path(__file__).resolve().parents[1]/'Data'
    sources=[('Maroc Telecom',next(data.glob('*Avril*pdf')),'Avril 2026'),
             ('Orange',data/'catalogue_orange.pdf','Juin 2023'),('inwi',data/'catalogue_inwi.pdf',None)]
    try:
        for operator,path,edition in sources:
            pages=extract_pdf_pages(path)
            offers=extract_offers_with_metadata(pages,use_llm=False).offers
            name=catalogue_name(path.name,path.read_bytes())
            first=save_offers.save_offers_from_preview(offers[:1],name,operator,edition=edition,pages=pages)
            assert first['saved_count']==1
            rest=save_offers.save_offers_from_preview(offers,name,operator,edition=edition,pages=pages)
            assert rest['saved_count']==len(offers)-1 and rest['duplicate_count']==1
            repeated=save_offers.save_offers_from_preview(offers,catalogue_name('renomme.pdf',path.read_bytes()),
                                                       operator,edition=edition,pages=pages)
            assert repeated['saved_count']==0 and repeated['duplicate_count']==len(offers)
            if edition:
                with pytest.raises(ValueError):
                    save_offers.save_offers_from_preview(offers,name,operator,edition='Edition différente',pages=pages)
            pending=[r for r in repo.read_pending() if r['id_catalogue']==first['catalogue_id']]
            assert len(pending)==len(offers)
            selected=pending[0]
            assert not any(r['id_offre']==selected['id_offre'] for r in db_connection.read_valid_offers())
            repo.review_offer(selected['id_offre'],selected,{k:selected[k] for k in OFFER_FIELDS},
                              validate=True,pages=pages)
            view=_prepare_offers_frame(db_connection.read_valid_offers())
            assert selected['id_offre'] in view.id_offre.tolist()
            assert not view.nom_offre.str.contains('DEMO50').any()
    finally:
        real.rollback();real.close()

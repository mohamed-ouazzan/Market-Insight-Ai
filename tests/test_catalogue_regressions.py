"""Références lues sur les PDF réels : valeurs de test, jamais données de l'extracteur."""
from pathlib import Path
import copy
import pytest
from extract_pdf import extract_pdf_pages
from extract_offers_ai import extract_offers_with_metadata,validate_offer
from offer_evidence import unpack_proof,validate_proof,evidence_text
from catalogue_identity import identify_catalogue,validate_catalogue_metadata

DATA=Path(__file__).resolve().parents[1]/'Data'


@pytest.fixture(scope='module')
def catalogues():
    paths={'mt':next(DATA.glob('*Avril*pdf')),'orange':DATA/'catalogue_orange.pdf','inwi':DATA/'catalogue_inwi.pdf'}
    return {op:(extract_pdf_pages(path),path) for op,path in paths.items()}


@pytest.fixture(scope='module')
def results(catalogues):
    return {op:extract_offers_with_metadata(pages,use_llm=False) for op,(pages,path) in catalogues.items()}


def test_all_three_catalogues_return_sourced_candidates(catalogues,results):
    assert {op:len(r.offers) for op,r in results.items()}=={'mt':6,'orange':4,'inwi':4}
    for op,result in results.items():
        pages,_=catalogues[op]
        assert result.summary['pages_lues']==len(pages)
        assert result.summary['candidats_detectes']==len(result.offers)
        assert result.rejected==0
        for item in result.offers:
            validate_offer(item,pages)
            proof=unpack_proof(item['extrait_source'])
            assert proof['sources'][0]['bbox']
            assert proof['document_hash']==pages.document_hash


def test_maroc_telecom_columns_and_cross_page_conditions(results):
    offers=results['mt'].offers
    assert [o['debit_mbps'] for o in offers]==[100,200,500,1000,200,1000]
    assert [unpack_proof(o['extrait_source'])['terms']['prix_normal_document'] for o in offers]==[400,500,800,1000,700,1200]
    assert [o['page_source'] for o in offers]==[2,2,2,2,3,3]
    assert all(o['engagement_mois']==12 and o['frais_installation_ttc']==200 for o in offers)
    assert any(r['page']==3 for r in unpack_proof(offers[0]['extrait_source'])['sources'])
    assert 'migration ADSL' in offers[0]['extrait_source']
    assert [o['prix_mensuel_ttc'] for o in offers]==[None,None,None,None,700,1200]
    assert '20H' in offers[-1]['appels_inclus']


def test_orange_promotion_does_not_shift_to_neighbour(results):
    offers=results['orange'].offers
    terms=[unpack_proof(o['extrait_source'])['terms'] for o in offers]
    assert [o['debit_mbps'] for o in offers]==[20,50,100,200]
    assert [t['prix_normal_document'] for t in terms]==[249,349,449,649]
    assert [t['prix_promotionnel_document'] for t in terms]==[None,249,349,449]
    assert [t['duree_promotion_mois'] for t in terms]==[None,3,3,3]
    assert all(o['prix_mensuel_ttc'] is None for o in offers)  # Aucun TTC indiqué sur cette grille.
    assert [o['frais_installation_ttc'] for o in offers]==[None,0,0,0]
    assert all(o['appels_inclus'] is None for o in offers)  # Services en image, pas d'invention.
    assert all(o['page_source']==28 for o in offers)


def test_inwi_boost_is_not_permanent_speed(results):
    offers=results['inwi'].offers
    terms=[unpack_proof(o['extrait_source'])['terms'] for o in offers]
    assert [o['debit_mbps'] for o in offers]==[20,20,20,200]
    assert [t['debit_temporaire_mbps'] for t in terms]==[50,100,200,None]
    assert [t['duree_debit_temporaire_mois'] for t in terms]==[3,3,3,None]
    assert [t['prix_normal_document'] for t in terms]==[249,349,449,649]
    assert all(o['prix_mensuel_ttc'] is None for o in offers)
    assert all(o['frais_installation_ttc']==0 for o in offers)
    assert '8 jours' in evidence_text(offers[0]['extrait_source'])
    assert 'Canada' in evidence_text(offers[0]['extrait_source'])
    assert any('5 offres' in message for d in results['inwi'].diagnostics for message in d['attention'])


def test_foreign_column_amount_is_rejected(catalogues,results):
    item=results['mt'].offers[4]
    with pytest.raises(ValueError):
        validate_offer({**item,'prix_mensuel_ttc':1200},catalogues['mt'][0])
    with pytest.raises(ValueError):
        validate_offer({**item,'debit_mbps':1000},catalogues['mt'][0])


def test_modified_quote_or_document_is_rejected(catalogues,results):
    import json
    item=results['orange'].offers[0]
    proof=copy.deepcopy(unpack_proof(item['extrait_source']))
    proof['sources'][0]['quote']+=' invention'
    with pytest.raises(ValueError):
        validate_offer({**item,'extrait_source':json.dumps(proof)},catalogues['orange'][0])
    with pytest.raises(ValueError):
        validate_offer(item,catalogues['inwi'][0])


def test_temporary_speed_cannot_replace_permanent_speed(catalogues,results):
    item=results['inwi'].offers[0]
    with pytest.raises(ValueError):
        validate_offer({**item,'debit_mbps':50},catalogues['inwi'][0])


def test_adsl_and_fibre_tables_on_same_page_are_separated(tmp_path):
    import pymupdf
    path=tmp_path/'mixed.pdf'
    with pymupdf.open() as document:
        page=document.new_page(width=600,height=800)
        for title,y,speeds in [('Offres ADSL',40,[20,50]),('Offres Fibre Optique',220,[100,200])]:
            page.insert_text((20,y-10),title,fontsize=14)
            page.draw_rect(pymupdf.Rect(20,y,580,y+100))
            page.draw_line((300,y),(300,y+100))
            page.draw_line((20,y+35),(580,y+35))
            page.draw_line((20,y+65),(580,y+65))
            for x,speed,price in zip([30,310],speeds,[400,500]):
                page.insert_text((x,y+23),f'{price} DH TTC /mois')
                page.insert_text((x,y+55),f'{speed} Mb/s')
                page.insert_text((x,y+85),'Appels fixes inclus')
        document.save(path)
    result=extract_offers_with_metadata(extract_pdf_pages(path),use_llm=False)
    assert [o['debit_mbps'] for o in result.offers]==[100,200]
    assert [o['prix_mensuel_ttc'] for o in result.offers]==[400,500]


def test_operator_and_edition_are_checked(catalogues):
    assert identify_catalogue(catalogues['orange'][0])['operator']=='Orange'
    with pytest.raises(ValueError):
        validate_catalogue_metadata('inwi',None,None,catalogues['orange'][0])
    with pytest.raises(ValueError):
        validate_catalogue_metadata('Orange','Juin 2026',None,catalogues['orange'][0])

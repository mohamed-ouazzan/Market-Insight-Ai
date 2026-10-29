"""Audit reproductible des trois PDF locaux. Aucun enregistrement SQL, aucune API par défaut."""
import argparse
from dataclasses import asdict
import json
from pathlib import Path
import re
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from extract_pdf import extract_pdf_pages
from extract_offers_ai import extract_offers_with_metadata
from offer_evidence import unpack_proof


def legacy_count(pages):
    # Critère observé avant correction : exactement un débit explicite et un prix TTC/mois par page.
    total=0
    for text in pages.values():
        if not re.search(r'\bfibre\b',text,re.I):continue
        speeds=re.findall(r'(\d+)\s*(Mbps|Mb\s*/\s*s|Gbps|Gb\s*/\s*s)\b',text,re.I)
        prices=re.findall(r'(\d+(?:[.,]\d{1,2})?)\s*(?:DH|MAD)\s*TTC\s*(?:/\s*mois|par\s+mois)',text,re.I)
        total+=int(len(speeds)==1 and len(prices)==1)
    return total


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--llm',action='store_true',help='Autoriser les appels au fournisseur configuré')
    args=parser.parse_args()
    documents=[]
    for path in sorted((ROOT/'Data').glob('*.pdf')):
        pages=extract_pdf_pages(path)
        result=extract_offers_with_metadata(pages,use_llm=args.llm)
        documents.append(dict(file=path.name,sha256=pages.document_hash,legacy_accepted=legacy_count(pages),**asdict(result),summary=result.summary))
    output=ROOT/'examples';output.mkdir(exist_ok=True)
    (output/'extraction_catalogues.json').write_text(json.dumps(documents,ensure_ascii=False,indent=2),encoding='utf-8')
    lines=['# Audit des catalogues locaux','',
        'Audit reproductible : `python scripts/audit_catalogues.py`. Lecture seule ; aucune écriture SQL. Sans appel API sauf option `--llm`.',
        '', '## Résultats', '', '| Document | Pages | Avant | Propositions sourcées | Pages des offres |', '| --- | ---: | ---: | ---: | --- |']
    for doc in documents:
        source_pages=sorted(set(o['page_source'] for o in doc['offers']))
        lines.append(f"| {doc['file']} | {doc['summary']['pages_lues']} | {doc['legacy_accepted']} | {len(doc['offers'])} | {', '.join(map(str,source_pages))} |")
    lines += ['', '## Causes observées avant correction', '',
        '- Maroc Telecom : grille de quatre colonnes et grille TV de deux colonnes ; prix sans `/mois` dans la première grille, conditions sur la page suivante contenant une migration ADSL.',
        '- Orange : unité « Méga » non reconnue, quatre cartes avec promotions et prix normal dans une même ligne, absence de TTC dans la grille ; services en partie dans des images.',
        '- inwi : quatre colonnes, plusieurs débits par forfait à cause du débit temporaire ; absence de TTC dans les montants. Le texte annonce cinq offres alors que quatre colonnes sont visibles.',
        '- L’ancien repli demandait un seul débit et un seul prix TTC/mois par page. Le résultat vide ne révélait ni l’absence de clé LLM ni ces incompatibilités.',
        '', '## Contrôle des chiffres extraits', '',
        '| Document | Offre descriptive | Page | Débit permanent | Tarif normal indiqué (DH) | Promo (DH) | Durée promo | Prix mensuel TTC certain |',
        '| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |']
    for doc in documents:
        for offer in doc['offers']:
            terms=unpack_proof(offer['extrait_source'])['terms']
            values=[doc['file'],offer['nom_offre'],offer['page_source'],offer['debit_mbps'],terms['prix_normal_document'],
                    terms['prix_promotionnel_document'],terms['duree_promotion_mois'],offer['prix_mensuel_ttc']]
            lines.append('| '+' | '.join('null' if v is None else str(v) for v in values)+' |')
    lines += ['', '## Vérification et limites', '',
        '- Pages originales rendues et inspectées : Maroc Telecom 2–3, Orange 28, inwi 49. Les valeurs de référence vivent dans les tests, pas dans le moteur.',
        '- Chaque proposition contient une preuve JSON dans le champ source existant : empreinte PDF, page, rectangle, citation native, conditions communes et informations tarifaires. Le contrôle recalcule les citations depuis le PDF.',
        '- Le numéro de page est attribué par le programme. Les modifications sont revalidées avant écriture et avant publication.',
        '- Orange : tarifs normaux 249/349/449/649 DH ; promotions 249/349/449 DH pendant trois mois sur les forfaits 50/100/200 Mbps. Le TTC n’est pas explicité ; ce champ reste null. Les appels en image restent à vérifier visuellement.',
        '- inwi : les trois premiers forfaits ont un débit permanent de 20 Mbps, temporairement 50/100/200 Mbps pendant trois mois. Le quatrième conserve 200 Mbps. Les montants ne portent pas la mention TTC.',
        '- Maroc Telecom : quatre montants TTC en page 2 sans périodicité explicite dans la grille : prix mensuel laissé null. Les deux prix TV mensuels sont explicites. La portée des conditions générales page 3 est signalée pour relecture.',
        '- Aucun OCR ni modèle visuel n’est activé. Les pages image et les services non lisibles sont signalés. La lecture géométrique reste un mode de secours à vérifier humainement.',
        '- Le LLM local n’avait pas de clé configurée au moment du diagnostic. Les états techniques, réponse vide valide et preuves invalides sont couverts par simulation. Une réponse vide valide n’utilise jamais le secours.',
        '- Les 50 offres DEMO50 restent en SQL et sont exclues de la base réelle de comparaison, des compteurs réels et des rapports.',
        '- Les métadonnées existantes et les éditions sont conservées. Un PDF renommé est reconnu par empreinte ; des offres distinctes peuvent être ajoutées au même catalogue.',
        '', 'Le JSON compagnon conserve les diagnostics de chaque page et l’intégralité des citations. Aucun secret de configuration n’y figure.']
    (output/'audit_extraction.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    for doc in documents:
        print(doc['file'],doc['summary'])


if __name__=='__main__':main()

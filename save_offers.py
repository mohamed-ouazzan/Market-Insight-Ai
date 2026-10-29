"""Ajout incrémental et idempotent des offres, sans évolution de schéma."""
from contextlib import closing
import hashlib
import re
from pathlib import Path
from db_connection import get_connection
from extract_offers_ai import validate_offer, OFFER_FIELDS, extract_offers_from_pages
from extract_pdf import extract_pdf_pages
from catalogue_storage import catalogue_name, store_pdf, local_pdf
from catalogue_identity import validate_catalogue_metadata, edition_key
from offer_evidence import unpack_proof, normalized


def ensure_operator(cursor,operator_name):
    cursor.execute('SELECT id_operateur FROM dbo.Operateurs WHERE nom = ?',(operator_name,))
    row=cursor.fetchone()
    if row is None:raise ValueError('Choisissez un opérateur enregistré.')
    return int(row[0])


def offer_identity(offer):
    proof=unpack_proof(offer.get('extrait_source'))
    if proof:
        ref=proof['sources'][0]
        if ref.get('bbox'):
            return ('zone',ref['page'],tuple(round(v,1) for v in ref['bbox']))
    return ('offre',normalized(offer.get('nom_offre') or '').casefold(),offer.get('page_source'),
            normalized(offer.get('extrait_source') or ''))


def _same_document(row,file_name,digest):
    if row['nom_fichier']==file_name:return True
    match=re.search(r'__([a-f0-9]{64})\.pdf$',row['nom_fichier'])
    if digest and match:return match[1]==digest
    if digest:
        path=local_pdf(row['nom_fichier'])
        return bool(path and hashlib.sha256(path.read_bytes()).hexdigest()==digest)
    return False


def save_offers_from_preview(offers,file_name,operator_name,segment='B2C',edition=None,url_source=None,*,pages=None):
    if pages is None:raise ValueError('Le texte source est requis pour enregistrer les offres.')
    validate_catalogue_metadata(operator_name,edition,url_source,pages)
    data=[validate_offer(offer,pages) for offer in offers]
    if not data:raise ValueError('Aucune offre à enregistrer.')
    if len(file_name)>255 or (edition and len(edition)>50) or (url_source and len(url_source)>1000):
        raise ValueError('Nom, édition ou URL trop long pour la base.')
    if segment!='B2C':raise ValueError('Le périmètre est limité au B2C.')
    match=re.search(r'__([a-f0-9]{64})\.pdf$',file_name)
    digest=match[1] if match else getattr(pages,'document_hash',None)
    if digest and getattr(pages,'document_hash',digest)!=digest:
        raise ValueError('L’empreinte du fichier ne correspond pas aux pages source.')
    with closing(get_connection()) as conn:
        try:
            with closing(conn.cursor()) as cursor:
                operator_id=ensure_operator(cursor,operator_name)
                # Verrou de plage pendant la recherche par contenu, y compris les catalogues historiques locaux.
                cursor.execute('''SELECT id_catalogue,id_operateur,nom_fichier,edition,url_source
                    FROM dbo.Catalogues WITH (UPDLOCK,HOLDLOCK)''')
                columns=[c[0] for c in cursor.description]
                rows=[dict(zip(columns,row)) for row in cursor.fetchall()]
                found=[r for r in rows if _same_document(r,file_name,digest)]
                if len(found)>1:
                    raise ValueError('Plusieurs catalogues représentent déjà ce PDF. Rapprochement manuel nécessaire, aucune fusion automatique.')
                if found:
                    old=found[0]
                    if old['id_operateur']!=operator_id:raise ValueError('Ce PDF est déjà rattaché à un autre opérateur.')
                    if old['edition'] and edition and edition_key(old['edition'])!=edition_key(edition):
                        raise ValueError('Édition différente pour le même PDF. Corrigez les métadonnées avant de réimporter.')
                    if old['url_source'] and url_source and old['url_source'].rstrip('/')!=url_source.rstrip('/'):
                        raise ValueError('Source différente pour le même PDF. Vérifiez la source du catalogue enregistré.')
                    catalogue_id=old['id_catalogue']
                    if (not old['edition'] and edition) or (not old['url_source'] and url_source):
                        cursor.execute('''UPDATE dbo.Catalogues SET edition=COALESCE(edition,?),url_source=COALESCE(url_source,?)
                            WHERE id_catalogue=?''',(edition,url_source,catalogue_id))
                else:
                    cursor.execute('''INSERT INTO dbo.Catalogues (id_operateur,nom_fichier,edition,segment,url_source)
                        OUTPUT INSERTED.id_catalogue VALUES (?,?,?,?,?)''',(operator_id,file_name,edition,segment,url_source))
                    catalogue_id=int(cursor.fetchone()[0])
                cursor.execute('''SELECT nom_offre,technologie,debit_mbps,prix_mensuel_ttc,engagement_mois,
                    frais_installation_ttc,appels_inclus,conditions_offre,page_source,extrait_source
                    FROM dbo.Offres WITH (UPDLOCK,HOLDLOCK) WHERE id_catalogue=?''',(catalogue_id,))
                existing=[dict(zip(OFFER_FIELDS,row)) for row in cursor.fetchall()]
                seen={offer_identity(row) for row in existing}
                count,duplicates=0,0
                for offer in data:
                    identity=offer_identity(offer)
                    if identity in seen:
                        duplicates+=1;continue
                    seen.add(identity)
                    cursor.execute('''INSERT INTO dbo.Offres (id_catalogue,nom_offre,technologie,debit_mbps,
                        prix_mensuel_ttc,engagement_mois,frais_installation_ttc,appels_inclus,
                        conditions_offre,page_source,extrait_source,est_validee) VALUES (?,?,?,?,?,?,?,?,?,?,?,0)''',
                        (catalogue_id,)+tuple(offer[k] for k in OFFER_FIELDS))
                    count+=1
            conn.commit()
            return dict(saved_count=count,duplicate_count=duplicates,already_exists=count==0,
                        catalogue=file_name,catalogue_id=catalogue_id,offers=data)
        except Exception:
            conn.rollback();raise


def save_offers_for_catalogue(pdf_path,operator_name,segment='B2C',edition=None,url_source=None):
    content=Path(pdf_path).read_bytes()
    pages=extract_pdf_pages(pdf_path)
    offers=extract_offers_from_pages(pages,operator_name)
    store_pdf(content)
    return save_offers_from_preview(offers,catalogue_name(Path(pdf_path).name,content),operator_name,
                                   segment,edition,url_source,pages=pages)

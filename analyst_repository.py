"""Accès SQL de l'espace analyste ; aucune modification du schéma."""
from contextlib import closing

from db_connection import get_connection
from extract_offers_ai import validate_offer
from provenance import is_synthetic, separate_records


def _read(query, params=()):
    with closing(get_connection()) as conn, closing(conn.cursor()) as cursor:
        cursor.execute(query, params)
        columns = [item[0] for item in cursor.description]
        return [dict(zip(columns, row)) for row in cursor.fetchall()]


def read_counts():
    catalogues = read_catalogues()
    real,demo = separate_records(catalogues)
    # Les marqueurs au niveau offre sont aussi contrôlés : un nom d'opérateur réel ne prouve pas la provenance.
    rows = _read('''SELECT nom_offre,conditions_offre,extrait_source,est_validee,c.nom_fichier,c.edition
        FROM dbo.Offres o JOIN dbo.Catalogues c ON c.id_catalogue=o.id_catalogue''')
    real_offers,demo_offers=separate_records(rows)
    return dict(catalogues=len(real),validees=sum(bool(o['est_validee']) for o in real_offers),
                en_attente=sum(not o['est_validee'] for o in real_offers),
                demonstrations=len(demo_offers),catalogues_demo=len(demo))


def read_operators():
    return _read('SELECT id_operateur, nom FROM dbo.Operateurs ORDER BY nom')


def read_catalogues():
    return _read('''SELECT c.id_catalogue, op.nom AS operateur, c.nom_fichier,
        c.edition, c.url_source, COUNT(o.id_offre) AS offres,
        SUM(CASE WHEN o.est_validee = 1 THEN 1 ELSE 0 END) AS validees,
        SUM(CASE WHEN o.est_validee = 0 THEN 1 ELSE 0 END) AS en_attente
        FROM dbo.Catalogues c JOIN dbo.Operateurs op ON op.id_operateur = c.id_operateur
        LEFT JOIN dbo.Offres o ON o.id_catalogue = c.id_catalogue
        GROUP BY c.id_catalogue, op.nom, c.nom_fichier, c.edition, c.url_source
        ORDER BY c.id_catalogue DESC''')


def read_pending():
    return _read('''SELECT o.id_offre, o.id_catalogue, op.nom AS operateur,
        c.nom_fichier, c.edition, c.url_source, o.nom_offre, o.technologie,
        o.debit_mbps, o.prix_mensuel_ttc, o.engagement_mois,
        o.frais_installation_ttc, o.appels_inclus, o.conditions_offre,
        o.page_source, o.extrait_source
        FROM dbo.Offres o JOIN dbo.Catalogues c ON c.id_catalogue = o.id_catalogue
        JOIN dbo.Operateurs op ON op.id_operateur = c.id_operateur
        WHERE o.est_validee = 0 ORDER BY o.id_offre''')


def review_offer(offer_id, original, edited=None, *, validate=False, reject=False, pages=None):
    """Verrouille et vérifie la version pour éviter d'écraser une autre correction."""
    if validate and reject:
        raise ValueError('Choisissez une seule action.')
    if validate and is_synthetic(original):
        raise ValueError('Une donnée de démonstration ne peut pas être publiée dans l’étude réelle.')
    if validate and pages is None:
        raise ValueError('Le PDF source est nécessaire pour vérifier les preuves avant publication.')
    from extract_offers_ai import OFFER_FIELDS
    data = validate_offer(edited, pages) if not reject else None
    with closing(get_connection()) as conn:
        try:
            with closing(conn.cursor()) as cursor:
                cursor.execute('''SELECT nom_offre, technologie, debit_mbps, prix_mensuel_ttc,
                    engagement_mois, frais_installation_ttc, appels_inclus, conditions_offre,
                    page_source, extrait_source FROM dbo.Offres WITH (UPDLOCK, HOLDLOCK)
                    WHERE id_offre = ? AND est_validee = 0''', (offer_id,))
                row = cursor.fetchone()
                if row is None or any(str(a) != str(original.get(k)) for k, a in zip(OFFER_FIELDS, row)):
                    raise ValueError('Cette offre a changé. Actualisez la liste avant de recommencer.')
                if reject:
                    # Le schéma ne possède aucun statut de rejet : suppression uniquement en attente.
                    cursor.execute('DELETE FROM dbo.Offres WHERE id_offre = ? AND est_validee = 0', (offer_id,))
                else:
                    cursor.execute('''UPDATE dbo.Offres SET nom_offre=?, technologie=?, debit_mbps=?,
                        prix_mensuel_ttc=?, engagement_mois=?, frais_installation_ttc=?, appels_inclus=?,
                        conditions_offre=?, page_source=?, extrait_source=?, est_validee=?
                        WHERE id_offre=? AND est_validee=0''',
                        tuple(data[k] for k in OFFER_FIELDS) + (int(validate), offer_id))
            conn.commit()
        except Exception:
            conn.rollback()
            raise

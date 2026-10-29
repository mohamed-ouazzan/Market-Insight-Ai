import os
from contextlib import closing
from pathlib import Path
import mssql_python
from dotenv import load_dotenv

load_dotenv(Path(__file__).with_name('.env'), encoding='utf-8-sig')


def _value(value):
    return '{' + value.replace('}', '}}') + '}'


def get_connection():
    server = _value(os.getenv('DB_SERVER', 'localhost'))
    database = _value(os.getenv('DB_DATABASE', 'MarketInsight'))
    return mssql_python.connect(
        f'SERVER={server};DATABASE={database};Trusted_Connection=yes;'
        'Encrypt=yes;TrustServerCertificate=yes;',
        timeout=10,
    )


def read_valid_offers(limit: int | None = None):
    if limit is not None and (type(limit) is not int or limit <= 0):
        raise ValueError('La limite doit être un entier strictement positif.')
    query = '''SELECT id_offre, operateur, nom_offre, segment, technologie,
        debit_mbps, prix_mensuel_ttc, engagement_mois, frais_installation_ttc,
        appels_inclus, conditions_offre, nom_fichier, edition, url_source,
        page_source, extrait_source
        FROM dbo.v_OffresValidees ORDER BY id_offre'''
    with closing(get_connection()) as conn:
        with closing(conn.cursor()) as cursor:
            if limit is None:
                cursor.execute(query)
            else:
                cursor.execute(query + ' OFFSET 0 ROWS FETCH NEXT ? ROWS ONLY', (limit,))
            columns = [column[0] for column in cursor.description]
            return [dict(zip(columns, row)) for row in cursor.fetchall()]

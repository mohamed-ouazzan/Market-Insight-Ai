"""Séparation explicite des données de démonstration et des catalogues réels."""
import re
from typing import Final
from offer_evidence import folded

# Contrat commun aux tableaux, calculs, filtres et libellés de l'étude.
# ORIGIN est une colonne dérivée du DataFrame, jamais un champ ajouté à SQL Server.
ORIGIN: Final[str] = 'origine_donnees'
REAL: Final[str] = 'Catalogue réel'
SIMULATED: Final[str] = 'Simulation — tarifs fictifs'

DEMO_MARKERS = re.compile(r'\bdemo\w*\b|\bficti\w*\b|\bsimule\w*\b|\bsyntheti\w*\b',re.I)


def is_synthetic(row):
    return any(DEMO_MARKERS.search(folded(row.get(k) or '')) for k in
               ('nom_fichier','edition','nom_offre','extrait_source','conditions_offre'))


def origin_label(row):
    """Étiquette canonique de la provenance, indépendante du nom de l'opérateur."""
    return SIMULATED if is_synthetic(row) else REAL


def separate_records(rows):
    real,demo=[],[]
    for row in rows:
        (demo if is_synthetic(row) else real).append(row)
    return real,demo

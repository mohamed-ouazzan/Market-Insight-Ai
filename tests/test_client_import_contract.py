"""Vérifie le contrat d'import de la page, sans exécuter une page hors Streamlit."""
import ast
import importlib
from pathlib import Path

import analyse_offers
from provenance import ORIGIN, REAL, SIMULATED, origin_label

ROOT = Path(__file__).resolve().parents[1]


def test_all_local_client_imports_exist_in_expected_modules():
    tree = ast.parse((ROOT / 'pages/1_Espace_Client.py').read_text(encoding='utf-8-sig'))
    checked = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module in {
            'db_connection', 'analyse_offers', 'generate_report', 'ui_common', 'provenance'
        }:
            module = importlib.import_module(node.module)
            assert Path(module.__file__).resolve().parent == ROOT
            for alias in node.names:
                assert hasattr(module, alias.name), f'{node.module}.{alias.name} manque'
                checked.add((node.module, alias.name))
    assert ('provenance', 'ORIGIN') in checked
    assert ('analyse_offers', 'analyse_dataframe') in checked


def test_provenance_constants_and_dataframe_use_the_same_contract(offer):
    demo = {**offer, 'operateur': 'Orange', 'nom_offre': 'DEMO50 Orange'}
    frame = analyse_offers._prepare_offers_frame([offer, demo], dataset='all')
    assert frame[ORIGIN].tolist() == [REAL, SIMULATED]
    assert origin_label(offer) == REAL and origin_label(demo) == SIMULATED
    assert analyse_offers.ORIGIN == ORIGIN
    assert analyse_offers.REAL == REAL and analyse_offers.SIMULATED == SIMULATED
    assert analyse_offers.LABELS[ORIGIN] == 'Origine des données'
    assert analyse_offers._prepare_offers_frame([offer, demo]).operateur.tolist() == ['Maroc Telecom']
    assert analyse_offers._prepare_offers_frame([offer, demo], dataset='simulated').operateur.tolist() == ['Orange']

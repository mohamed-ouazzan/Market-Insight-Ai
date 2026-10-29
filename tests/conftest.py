import sys
from pathlib import Path
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


@pytest.fixture
def offer():
    return dict(id_offre=1, operateur='Maroc Telecom', nom_offre='Fibre 200',
                segment='B2C', technologie='Fibre', debit_mbps=200, prix_mensuel_ttc=700,
                engagement_mois=12, frais_installation_ttc=200, appels_inclus='Fixes inclus',
                conditions_offre='Routeur distinct : 200 DH.', nom_fichier='test.pdf', edition='2025',
                url_source=None, page_source=1,
                extrait_source='Fibre 200 Mbps : 700 DH TTC /mois\nEngagement : 12 mois.\nFrais d’installation : 200 DH TTC.')

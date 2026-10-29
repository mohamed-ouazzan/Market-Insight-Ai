"""Preuves relisibles et vérifiables, stockées dans le champ source existant."""
import json
import re
import unicodedata
from extract_pdf import region_text

FORMAT = 'market-insight-proof-v1'
SPEED = re.compile(r'(\d+(?:[.,]\d+)?)\s*(Gb\s*/\s*s|Gbps|Mb\s*/\s*s|Mbps|M[ée]ga)\b', re.I)
AMOUNT = re.compile(r'(\d+(?:[.,]\d{1,2})?)\s*(?:DH|MAD)\b', re.I)


def normalized(text):
    return ' '.join(str(text).split())


def folded(text):
    return ''.join(c for c in unicodedata.normalize('NFKD', normalized(text).casefold()) if not unicodedata.combining(c))


def speeds(text):
    return [float(m[1].replace(',', '.')) * (1000 if m[2].lower().startswith('g') else 1) for m in SPEED.finditer(text)]


def unpack_proof(value):
    if not isinstance(value, str) or not value.lstrip().startswith('{'):
        return None
    try:
        data = json.loads(value)
    except ValueError:
        return None
    return data if isinstance(data, dict) and data.get('format') == FORMAT else None


def source(pages, page, bbox=None, role='offre'):
    return dict(page=page, bbox=bbox, role=role, quote=region_text(pages, page, bbox))


def pack_proof(sources, terms=None, warnings=None, document_hash=None):
    return json.dumps(dict(format=FORMAT, sources=sources, terms=terms or {}, warnings=warnings or [],
                           document_hash=document_hash), ensure_ascii=False)


def evidence_text(value):
    proof = unpack_proof(value)
    return '\n'.join(s['quote'] for s in proof['sources']) if proof else (value or '')


def validate_proof(data, pages=None):
    proof = unpack_proof(data['extrait_source'])
    if proof:
        sources = proof.get('sources')
        if not isinstance(sources, list) or not sources or sources[0].get('page') != data['page_source']:
            raise ValueError('La page principale de la preuve ne correspond pas à l’offre.')
        if pages is not None:
            digest = getattr(pages, 'document_hash', None)
            if digest and proof.get('document_hash') and digest != proof['document_hash']:
                raise ValueError('Cette preuve appartient à un autre PDF.')
        for ref in sources:
            if not isinstance(ref, dict) or not isinstance(ref.get('page'), int) or not ref.get('quote', '').strip():
                raise ValueError('Référence de preuve invalide.')
            if pages is not None:
                original = region_text(pages, ref['page'], ref.get('bbox'))
                if normalized(ref['quote']) != normalized(original):
                    raise ValueError(f"Preuve altérée ou introuvable, page {ref['page']}.")
    elif pages is not None:
        original = pages.get(data['page_source'])
        quote = normalized(data['extrait_source'] or '')
        if original is None or not quote or quote not in normalized(original):
            raise ValueError('La preuve ne figure pas sur la page indiquée.')
    text = evidence_text(data['extrait_source'])
    folded_text = folded(text)
    # Un chiffre situé n’importe où dans le document ne suffit pas : la preuve est limitée à la colonne et ses conditions.
    if data['debit_mbps'] is not None and data['debit_mbps'] not in speeds(text):
        raise ValueError('Le débit n’est pas justifié dans la preuve de cette offre.')
    if proof and proof.get('terms',{}).get('debit_temporaire_mbps') is not None:
        if data['debit_mbps'] != proof['terms'].get('debit_permanent_mbps'):
            raise ValueError('Le débit permanent ne doit pas être remplacé par le débit temporaire.')
    if data['prix_mensuel_ttc'] is not None:
        primary = proof['sources'][0]['quote'] if proof else text
        amounts = [float(m[1].replace(',', '.')) for m in AMOUNT.finditer(primary)]
        if data['prix_mensuel_ttc'] not in amounts or 'ttc' not in folded(primary):
            raise ValueError('Prix TTC non justifié : gardez null si la fiscalité est inconnue.')
        if proof:
            if proof.get('terms',{}).get('periodicite')!='mensuelle':
                raise ValueError('Périodicité mensuelle non justifiée dans la grille : gardez ce prix vide.')
            expected = proof.get('terms', {}).get('prix_normal_document')
            if expected is not None and data['prix_mensuel_ttc'] != expected:
                raise ValueError('Le prix mensuel de comparaison doit être le prix normal, hors promotion.')
    if data['engagement_mois'] is not None:
        values = re.findall(r'engagement\D{0,20}(\d+)\s*mois', folded_text)
        if str(data['engagement_mois']) not in values:
            raise ValueError('Engagement non justifié dans la preuve.')
    if data['frais_installation_ttc'] is not None:
        chunks = re.findall(r'(?:installation|mise en service)[^.\n]{0,90}', folded_text)
        valid = []
        for chunk in chunks:
            if re.search(r'gratuit|offert', chunk):
                valid.append(0)
            for m in AMOUNT.finditer(chunk):
                value = float(m[1].replace(',', '.'))
                if value == 0 or 'ttc' in chunk:
                    valid.append(value)
        if data['frais_installation_ttc'] not in valid:
            raise ValueError('Frais d’installation TTC non justifiés ; ne pas utiliser le prix du routeur.')
    return proof

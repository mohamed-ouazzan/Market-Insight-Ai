"""PDF locaux adressés par SHA-256, sans clé API ni contenu dans les logs."""
import hashlib
import re
from pathlib import Path

from extract_pdf import extract_pdf_pages

ROOT = Path(__file__).parent / 'Data' / 'imports'


def fingerprint(content):
    return hashlib.sha256(content).hexdigest()


def catalogue_name(original, content):
    stem = Path(original.replace('\\', '/')).stem
    stem = re.sub(r'[^\w .-]', '_', stem)[:160]
    return f'{stem}__{fingerprint(content)}.pdf'


def store_pdf(content):
    ROOT.mkdir(parents=True, exist_ok=True)
    target = ROOT / f'{fingerprint(content)}.pdf'
    if not target.exists():
        target.write_bytes(content)
    return target


def local_pdf(name):
    match = re.search(r'__([a-f0-9]{64})\.pdf$', name)
    if match:
        path = ROOT / f'{match[1]}.pdf'
        return path if path.is_file() else None
    # Catalogues historiques : recherche par nom exact, jamais par chemin fourni.
    if not name or Path(name).name != name or '/' in name or '\\' in name:
        return None
    candidate = Path(__file__).parent / 'Data' / name
    return candidate if candidate.is_file() else None


def source_pages(name):
    path = local_pdf(name)
    return extract_pdf_pages(path) if path else None

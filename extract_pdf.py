"""Lecture native du PDF : mots, lignes, tableaux et coordonnées conservés."""
from pathlib import Path
import hashlib
import pymupdf


class SourcePages(dict):
    def __init__(self, *args, layout=None, document_hash=None, path=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.layout = layout or {}
        self.document_hash = document_hash
        self.path = str(path) if path else None


def region_text(pages, number, bbox=None):
    if bbox is None:
        return pages.get(number, '')
    info = getattr(pages, 'layout', {}).get(number)
    if info is None:
        raise ValueError('Coordonnées absentes : rechargez le PDF pour vérifier cette preuve.')
    x0, y0, x1, y1 = bbox
    if not (0 <= x0 < x1 <= info['width'] + 1 and 0 <= y0 < y1 <= info['height'] + 1):
        raise ValueError('Zone source hors de la page.')
    words = [w for w in info['words'] if x0 <= (w[0]+w[2])/2 <= x1 and y0 <= (w[1]+w[3])/2 <= y1]
    lines, last = [], None
    for word in words:
        key = tuple(word[5:7])
        if key != last:
            lines.append([])
            last = key
        lines[-1].append(word[4])
    return '\n'.join(' '.join(line) for line in lines)


def extract_pdf_pages(pdf_path):
    path = Path(pdf_path)
    pages = SourcePages(document_hash=hashlib.sha256(path.read_bytes()).hexdigest(), path=path)
    with pymupdf.open(path) as doc:
        if doc.needs_pass:
            raise ValueError('PDF protégé par mot de passe.')
        for index, page in enumerate(doc):
            number = index + 1
            pages[number] = page.get_text('text').strip()
            lines = []
            for block in page.get_text('dict')['blocks']:
                if block['type'] != 0:
                    continue
                for line in block['lines']:
                    lines.append(dict(text=''.join(s['text'] for s in line['spans']), bbox=list(line['bbox']),
                                      font_size=max(s['size'] for s in line['spans'])))
            tables, table_error = [], None
            if 'fibre' in pages[number].casefold():
                try:
                    for table in page.find_tables().tables:
                        tables.append(dict(bbox=list(table.bbox), rows=[r.cells for r in table.rows]))
                except Exception:
                    table_error = 'Détection des tableaux impossible ; blocs natifs conservés.'
            pages.layout[number] = dict(width=page.rect.width, height=page.rect.height,
                words=page.get_text('words'), lines=lines, tables=tables, table_error=table_error,
                images=len(page.get_images()), needs_ocr=len(pages[number].strip()) < 60 and bool(page.get_images()))
    return pages


def render_source_page(path, number, bbox=None):
    with pymupdf.open(path) as doc:
        page = doc[number-1]
        return page.get_pixmap(matrix=pymupdf.Matrix(1.5, 1.5), clip=pymupdf.Rect(bbox) if bbox else None).tobytes('png')

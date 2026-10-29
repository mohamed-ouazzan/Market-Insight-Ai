"""Vérification des métadonnées documentaires, sans modifier le schéma SQL."""
import re
from urllib.parse import urlparse
from offer_evidence import folded

MONTHS='janvier|fevrier|mars|avril|mai|juin|juillet|aout|septembre|octobre|novembre|decembre'


def edition_key(value):
    text=folded(value or '')
    match=re.search(r'('+MONTHS+r')\s+(20\d{2})',text)
    return (match[1],match[2]) if match else text


def identify_catalogue(pages):
    text=folded(' '.join(pages.values()))
    counts={op:len(re.findall(pattern,text)) for op,pattern in
            [('Maroc Telecom',r'\bmaroc telecom\b'),('Orange',r'\borange\b'),('inwi',r'\binwi\b')]}
    ranked=sorted(counts,key=counts.get,reverse=True)
    operator=ranked[0] if counts[ranked[0]]>=3 and counts[ranked[0]]>2*counts[ranked[1]] else None
    relevant=' '.join(t for t in pages.values() if 'fibre' in folded(t))
    editions=list(dict.fromkeys(re.findall('(?:'+MONTHS+r')\s+20\d{2}',folded(relevant))))
    if not editions:
        editions=list(dict.fromkeys(re.findall('(?:'+MONTHS+r')\s+20\d{2}',folded(' '.join(list(pages.values())[:2])))))
    return dict(operator=operator,editions=editions)


def validate_catalogue_metadata(operator,edition,url,pages):
    identity=identify_catalogue(pages)
    if identity['operator'] and identity['operator']!=operator:
        raise ValueError(f"Le document identifie {identity['operator']}, pas {operator}.")
    if edition and len(identity['editions'])==1 and edition_key(edition)!=edition_key(identity['editions'][0]):
        raise ValueError('L’édition saisie diffère de celle du document. Vérifiez le PDF.')
    if url:
        parsed=urlparse(url)
        if parsed.scheme not in {'http','https'} or not parsed.hostname or parsed.username or parsed.password:
            raise ValueError('Source : URL http(s) valide, sans identifiants, attendue.')
        domains={'Maroc Telecom':('iam.ma','maroctelecom.ma'),'Orange':('orange.ma',),'inwi':('inwi.ma',)}
        for owner,suffixes in domains.items():
            if owner!=operator and any(parsed.hostname==d or parsed.hostname.endswith('.'+d) for d in suffixes):
                raise ValueError('L’URL appartient à un autre opérateur. Vérifiez la source.')
    return identity

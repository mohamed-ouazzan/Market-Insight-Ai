"""Adaptations de structure (tableaux à cellules et cartes), sans offres codées en dur."""
from statistics import median
import re
from extract_pdf import region_text
from offer_evidence import AMOUNT, SPEED, folded, normalized, speeds, source, pack_proof


def _is_price(text):
    return bool(re.fullmatch(r'\s*\d+(?:[.,]\d{1,2})?\s*(?:DH|MAD)(?:\s*TTC)?(?:\s*/\s*mois)?\s*', text, re.I))


def _fibre_context(pages,number,bbox):
    if 'fibre' in folded(region_text(pages,number,bbox)):
        return True
    lines=getattr(pages,'layout',{}).get(number,{}).get('lines',[])
    headings=[]
    for line in lines:
        value=re.sub(r'^\d+[.)]?\s*','',folded(line['text']))
        if line['bbox'][1]<bbox[1] and re.search(r'^(?:la\s+)?(?:fibre|adsl|4g)|(?:offres?|gamme|forfait).{0,50}(?:fibre|adsl|4g)',value):
            headings.append((line['bbox'][1],value))
    return bool(headings and 'fibre' in max(headings)[1])


def detect_zones(pages, number):
    info = getattr(pages, 'layout', {}).get(number)
    if not info:
        return []
    text = pages[number]
    if 'fibre' not in folded(text):
        return []
    zones = []
    for table in info['tables']:
        if not _fibre_context(pages,number,table['bbox']):
            continue
        for row in table['rows']:
            prices = [(cell, region_text(pages, number, cell)) for cell in row if cell]
            prices = [(cell, value) for cell, value in prices if _is_price(normalized(value))]
            if len(prices) < 2:
                continue
            for cell, price in prices:
                bbox = [cell[0], table['bbox'][1], cell[2], table['bbox'][3]]
                crop = region_text(pages, number, bbox)
                if not SPEED.search(crop):
                    continue
                shared = []
                services = []
                for cells in table['rows']:
                    for common in cells:
                        if common and common[2]-common[0] > 1.5 * (cell[2]-cell[0]):
                            ref = source(pages, number, common, 'condition commune')
                            if ref['quote'] and ref not in shared:
                                shared.append(ref)
                        elif common and abs(common[0]-cell[0]) < 2 and abs(common[2]-cell[2]) < 2:
                            value = region_text(pages,number,common)
                            if re.search(r'appels|\d+\s*h\b|premium.*tv',value,re.I):
                                services.append(value)
                zones.append(dict(bbox=bbox, text=crop, price_text=price, shared=shared, layout='tableau',
                                  services=services,monthly='mensualite' in folded(text) or bool(re.search(r'/\s*mois|par\s+mois',price,re.I))))
            if zones:
                return zones
    # Cartes ou tableau sans bordures : groupe de lignes tarifaires alignées.
    anchors = [line for line in info['lines'] if re.search(r'\d+\s*DH\s*(?:TTC\s*)?/\s*mois', line['text'], re.I)]
    groups = []
    for anchor in sorted(anchors, key=lambda a:a['bbox'][1]):
        if groups and abs(anchor['bbox'][1] - groups[-1][0]['bbox'][1]) < 25:
            groups[-1].append(anchor)
        else:
            groups.append([anchor])
    groups = [g for g in groups if len(g) >= 2 and
              max(a['bbox'][0] for a in g)-min(a['bbox'][0] for a in g) > .2*info['width']]
    if not groups:
        return []
    group = sorted(max(groups, key=len), key=lambda a:a['bbox'][0])
    cards = bool(re.search(r'M[ée]ga', text, re.I))
    if cards:
        starts = [a['bbox'][0] for a in group]
        gap = median(b-a for a,b in zip(starts, starts[1:]))
        bounds = [max(0, x-.06*gap) for x in starts] + [info['width']]
        header_lines = [l for l in info['lines'] if SPEED.search(l['text']) and l['bbox'][1] < min(a['bbox'][1] for a in group)]
        top = max(0, min(l['bbox'][1] for l in header_lines)-5) if header_lines else 0
        bottom = max(l['bbox'][3] for l in info['lines'] if any(k in folded(l['text']) for k in ['installation', 'engagement', 'routeur', 'telephone fixe']))+5
    else:
        centers = [(a['bbox'][0]+a['bbox'][2])/2 for a in group]
        bounds = [0] + [(a+b)/2 for a,b in zip(centers,centers[1:])] + [info['width']]
        top = max(0, min(a['bbox'][1] for a in group)-5)
        # Les paragraphes pleine largeur qui suivent le tableau ne deviennent pas des services propres à une colonne.
        wide = [l['bbox'][1] for l in info['lines'] if l['bbox'][2]-l['bbox'][0] > .65*info['width'] and l['bbox'][1] > top+80]
        bottom = min(wide)-2 if wide else min(info['height'], top+220)
    for index, anchor in enumerate(group):
        bbox = [bounds[index],top,bounds[index+1],bottom]
        crop = region_text(pages,number,bbox)
        if SPEED.search(crop) and _fibre_context(pages,number,bbox):
            zones.append(dict(bbox=bbox,text=crop,price_text=anchor['text'],shared=[],layout='cartes' if cards else 'colonnes',monthly=True))
    return zones


def common_sources(pages, number):
    refs = []
    for n in [number, number+1]:
        info = getattr(pages, 'layout', {}).get(n)
        if not info:
            continue
        if n != number and 'fibre' not in folded(pages[n]):
            continue
        headings = [l for l in info['lines'] if 'conditions generales' in folded(l['text'])]
        if headings:
            box = [0,max(0,min(l['bbox'][1] for l in headings)-2),info['width'],info['height']]
            refs.append(source(pages,n,box,'conditions générales ; portée à vérifier' if n!=number else 'conditions générales'))
        elif n == number:
            if info['tables']:
                bottom=max(t['bbox'][3] for t in info['tables'])
                next_headings=[l['bbox'][1] for l in info['lines'] if l['bbox'][1]>bottom and
                               re.search(r'^\s*\d+[.]\s*offre',folded(l['text']))]
                limit=min(next_headings) if next_headings else .9*info['height']
                after=[l for l in info['lines'] if bottom<l['bbox'][1]<limit]
                if after:
                    refs.append(source(pages,n,[0,bottom+1,info['width'],min(limit,max(l['bbox'][3] for l in after)+1)],
                                       'conditions et renvois sous le tableau'))
            else:
                for line in info['lines']:
                    if re.search(r'engagement\D{0,20}\d+\s*mois',folded(line['text'])):
                        if not re.search(r'M[ée]ga',pages[n],re.I):
                            refs.append(source(pages,n,line['bbox'],'engagement commun'))
    return refs


def _price_terms(price_text):
    text = normalized(price_text)
    amounts = [float(m[1].replace(',','.')) for m in AMOUNT.finditer(text)]
    promo = re.search(r'[x×]\s*(\d+)\s*mois\s*puis',text,re.I)
    if promo and len(amounts)==2:
        return dict(prix_normal_document=amounts[1], prix_promotionnel_document=amounts[0], duree_promotion_mois=int(promo[1]))
    return dict(prix_normal_document=amounts[0] if len(amounts)==1 else None,
                prix_promotionnel_document=None,duree_promotion_mois=None)


def candidate_from_zone(pages, number, zone):
    quote = zone['text']
    refs = [source(pages,number,zone['bbox'])] + zone['shared'] + common_sources(pages,number)
    all_text = '\n'.join(ref['quote'] for ref in refs)
    notes = []
    values = list(dict.fromkeys(speeds(quote)))
    temporary = re.search(r'(\d+)\s*Mbps\s*pendant\s*(\d+)\s*mois\s*puis\s*(\d+)\s*Mbps',normalized(quote),re.I)
    if temporary:
        speed, boost, boost_duration = int(temporary[3]), int(temporary[1]), int(temporary[2])
    else:
        speed = int(values[0]) if len(values)==1 else None
        boost = boost_duration = None
        if speed is None:
            notes.append('Plusieurs débits dans la colonne : débit permanent à préciser.')
    terms = _price_terms(zone['price_text'])
    terms.update(debit_temporaire_mbps=boost,duree_debit_temporaire_mois=boost_duration,
                 debit_permanent_mbps=speed,
                 taxe='TTC' if 'ttc' in folded(zone['price_text']) else 'non précisée',
                 periodicite='mensuelle' if zone['monthly'] else 'non précisée')
    price = terms['prix_normal_document'] if terms['taxe']=='TTC' and zone['monthly'] else None
    if terms['taxe']!='TTC':
        notes.append('Fiscalité non précisée : montant document conservé, prix TTC laissé vide.')
    if not zone['monthly']:
        notes.append('Périodicité non précisée dans la grille : prix mensuel laissé vide.')
    common = folded(all_text)
    duration = re.findall(r'engagement\D{0,20}(\d+)\s*mois',common)
    duration = int(duration[0]) if len(set(duration))==1 else None
    installation = None
    installation_document = None
    install = re.search(r'(?:installation|mise en service)\s*[:]?\s*(gratuit\w*|offert\w*|\d+(?:[.,]\d+)?\s*DH(?:\s*TTC)?)',common,re.I)
    if install:
        if re.search(r'gratuit|offert',install[1]):
            installation=installation_document=0
        else:
            amount = AMOUNT.search(install[1]); amount=float(amount[1].replace(',','.')) if amount else None
            installation_document=amount
            installation=amount if 'ttc' in install[1] or amount==0 else None
    terms['frais_installation_document']=installation_document
    if any(ref['page']!=number for ref in refs):
        notes.append('Conditions sur la page suivante : confirmer leur portée pour cette offre.')
    if zone['layout']=='cartes' and getattr(pages,'layout',{}).get(number,{}).get('images'):
        notes.append('Services en partie en image : relire visuellement les appels et options TV ; aucun service illisible inventé.')
    services = list(zone.get('services', []))
    lines = quote.splitlines()
    if '+' in lines and zone['layout']!='cartes':
        services = ['\n'.join(l for l in lines[lines.index('+')+1:] if l.strip()!='+')]
    # Lignes communes fusionnées du tableau, comme les appels fixes illimités.
    services += [r['quote'] for r in zone['shared'] if 'appels' in folded(r['quote'])]
    services_text='\n'.join(dict.fromkeys(services)) or None
    if services_text and len(services_text)>500:
        services_text=None;notes.append('Services trop longs : compléter manuellement à partir des preuves.')
    equipment = [l for l in all_text.splitlines() if re.search(r'routeur|equipement|mise a disposition|telephone fixe',folded(l))]
    terms['equipement_document'] = equipment
    name = f'Fibre {speed} Mbps' if speed else 'Fibre — débit à vérifier'
    if boost:
        name += f' ({boost} Mbps pendant {boost_duration} mois)'
    if 'premium mt tv' in folded(quote):
        name += ' + Premium MT TV'
    descriptions = []
    for k,label in [('prix_normal_document','Prix normal document (DH)'),('prix_promotionnel_document','Prix promotionnel document (DH)'),
                    ('duree_promotion_mois','Durée promotion (mois)'),('debit_temporaire_mbps','Débit temporaire (Mbps)'),
                    ('duree_debit_temporaire_mois','Durée débit temporaire (mois)')]:
        if terms[k] is not None:descriptions.append(f'{label} : {terms[k]:g}.')
    descriptions += [f"Fiscalité : {terms['taxe']}. Périodicité : {terms['periodicite']}."]
    if installation_document is not None:
        descriptions.append(f'Installation document : {installation_document:g} DH ; TTC confirmé : {"oui" if installation is not None else "non précisé"}.')
    # Le texte original de toutes les conditions reste conservé intégralement dans la preuve multi-page.
    descriptions += ['Équipement : ' + normalized(' ; '.join(equipment))] if equipment else []
    descriptions += [f'Conditions complémentaires : page(s) {", ".join(str(n) for n in sorted(set(r["page"] for r in refs[1:])))}. Voir les preuves originales.'] if len(refs)>1 else []
    descriptions += notes
    conditions=' '.join(descriptions)
    if len(conditions)>2000:
        conditions=' '.join(descriptions[:6]) + ' Conditions et équipement détaillés dans les preuves originales.'
    offer=dict(nom_offre=name,technologie='Fibre',debit_mbps=speed,prix_mensuel_ttc=price,
        engagement_mois=duration,frais_installation_ttc=installation,appels_inclus=services_text,
        conditions_offre=conditions,page_source=number,
        extrait_source=pack_proof(refs,terms,notes,getattr(pages,'document_hash',None)))
    return offer

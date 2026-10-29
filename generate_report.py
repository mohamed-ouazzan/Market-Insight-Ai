"""Rapports descriptifs, sans génération IA ni conclusion concurrentielle implicite."""
import html
import pandas as pd
from provenance import is_synthetic
from offer_evidence import evidence_text
from analyse_offers import business_table

LIMITS = ('Seules les offres Fibre B2C validées et les filtres affichés sont inclus. '
          'Les éditions peuvent différer ; les tarifs ne constituent pas une observation simultanée du marché actuel. '
          'Les données manquantes ne valent pas zéro. TV non structurée : aucun filtre TV fiable. '
          'Les promotions, le prix après promotion et les frais routeur doivent être lus dans les conditions. '
          'Médiane calculée par offre au même débit exact, uniquement avec plusieurs opérateurs. '
          'Le rang porte sur le meilleur prix de chaque opérateur à ce débit ; il ne mesure pas la qualité du service.')


def cell(value):
    if value is None or (not isinstance(value, str) and pd.isna(value)):
        return 'Non précisé'
    return str(value)


def markdown_table(frame):
    def safe(v):
        return html.escape(cell(v)).replace('|', '&#124;').replace('\n', '<br>')
    rows = ['| ' + ' | '.join(map(safe, frame.columns)) + ' |',
            '| ' + ' | '.join(['---'] * len(frame.columns)) + ' |']
    rows += ['| ' + ' | '.join(map(safe, row)) + ' |' for row in frame.itertuples(index=False, name=None)]
    return '\n'.join(rows)


def build_report(df, client_operator, *, dataset='real'):
    if dataset not in {'real', 'simulated'}:
        raise ValueError('Les rapports réels et simulés doivent être exportés séparément.')
    simulated = [is_synthetic(row) for row in df.to_dict('records')]
    if dataset == 'real' and any(simulated):
        raise ValueError('Les données de démonstration sont exclues des rapports réels.')
    if dataset == 'simulated' and not all(simulated):
        raise ValueError('Un rapport simulé ne peut pas inclure des données réelles.')
    report_title = 'Market Insight AI' if dataset == 'real' else 'Market Insight AI — DÉMONSTRATION — TARIFS FICTIFS'
    limits = LIMITS if dataset == 'real' else ('Données simulées pour tester le logiciel. Aucun tarif officiel, aucune conclusion sur le marché réel. ' + LIMITS)
    table = business_table(df)
    sources = df[['operateur', 'nom_fichier', 'edition', 'page_source', 'url_source']].rename(columns={
        'operateur': 'Opérateur', 'nom_fichier': 'Catalogue', 'edition': 'Édition', 'page_source': 'Page', 'url_source': 'Source'})
    notice = ('Une seule offre validée est disponible. Ajoutez et validez des offres concurrentes pour réaliser une comparaison.'
              if len(df) == 1 else 'Rapport descriptif du périmètre sélectionné ; aucun avis généré par IA.')
    scope = f'{len(df)} offre(s), {df.operateur.nunique()} opérateur(s). Opérateur client : {client_operator}.'
    detailed = df[['nom_offre', 'frais_installation_ttc', 'appels_inclus', 'conditions_offre', 'extrait_source']].rename(
        columns={'nom_offre': 'Offre', 'frais_installation_ttc': 'Installation TTC (DH)', 'appels_inclus': 'Appels inclus',
                 'conditions_offre': 'Conditions', 'extrait_source': 'Preuve originale'})
    detailed['Preuve originale'] = detailed['Preuve originale'].map(evidence_text)
    indicators = df[['operateur', 'nom_offre', 'prix_par_100_mbps', 'prix_median_market',
                     'ecart_a_median_market', 'rang_operateur']].rename(columns={
        'operateur': 'Opérateur', 'nom_offre': 'Offre', 'prix_par_100_mbps': 'DH / 100 Mbps',
        'prix_median_market': 'Médiane même débit (DH)', 'ecart_a_median_market': 'Écart médiane (DH)',
        'rang_operateur': 'Rang du meilleur prix opérateur'})
    if not df.ecart_a_median_market.notna().any():
        indicators = indicators.iloc[:, :3]
    objective = ('Tester les tableaux et calculs sur des offres fictives ; aucune offre officielle présentée.'
                 if dataset == 'simulated' else 'Décrire et comparer les offres Fibre B2C documentées et vérifiées.')
    blocks = [('Objectif', objective),
              ('Périmètre', scope), ('Constat', notice)]
    md = '# ' + report_title + '\n\n' + '\n\n'.join(f'## {heading}\n\n{html.escape(text)}' for heading, text in blocks)
    for title, frame in [('Offres', table), ('Indicateurs Python', indicators), ('Services et conditions', detailed), ('Sources', sources)]:
        md += f'\n\n## {title}\n\n' + markdown_table(frame)
    md += '\n\n## Limites\n\n' + limits
    body = '<h1>' + html.escape(report_title) + '</h1>' + ''.join(f'<h2>{heading}</h2><p>{html.escape(text)}</p>' for heading, text in blocks)
    for title, frame in [('Offres', table), ('Indicateurs Python', indicators), ('Services et conditions', detailed), ('Sources', sources)]:
        body += f'<h2>{title}</h2>' + frame.astype(object).fillna('Non précisé').to_html(index=False, escape=True)
    body += '<h2>Limites</h2><p>' + html.escape(limits) + '</p>'
    document = '<!doctype html><html lang="fr"><meta charset="utf-8"><title>Market Insight AI</title><style>body{font:15px system-ui;color:#172B4D;background:#F5F7FB;margin:40px}table{border-collapse:collapse;background:white;width:100%;font-size:13px}td,th{padding:10px;border:1px solid #DFE5ED;text-align:left;overflow-wrap:anywhere}h1{color:#087F8C}h2{font-size:20px}</style><body>' + body + '</body></html>'
    return md, document

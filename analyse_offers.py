"""Indicateurs calculés exclusivement en Python, sur le périmètre affiché."""
import pandas as pd
import plotly.express as px
from db_connection import read_valid_offers
from provenance import is_synthetic, origin_label, ORIGIN, REAL, SIMULATED
from offer_evidence import unpack_proof

BASE_COLUMNS = ['id_offre', 'operateur', 'nom_offre', 'segment', 'technologie', 'debit_mbps',
                'prix_mensuel_ttc', 'engagement_mois', 'frais_installation_ttc', 'appels_inclus',
                'conditions_offre', 'nom_fichier', 'edition', 'url_source', 'page_source', 'extrait_source']
NUMERIC = ['debit_mbps', 'prix_mensuel_ttc', 'engagement_mois', 'frais_installation_ttc']
LABELS = {'operateur': 'Opérateur', 'nom_offre': 'Offre', 'debit_mbps': 'Débit (Mbps)',
          'prix_mensuel_ttc': 'Prix mensuel TTC', 'engagement_mois': 'Engagement',
          'appels_inclus': 'Services inclus', 'frais_installation_ttc': 'Installation TTC',
          'conditions_offre': 'Conditions', 'prix_par_100_mbps': 'DH / 100 Mbps',
          'prix_median_market': 'Médiane du palier (DH)', 'ecart_a_median_market': 'Écart médiane (DH)',
          'rang_operateur': 'Rang du meilleur prix opérateur'}
# Les constantes importées restent réexportées pour les appelants existants.
LABELS[ORIGIN] = 'Origine des données'


def _prepare_offers_frame(raw_rows, *, dataset='real'):
    if dataset not in {'real', 'simulated', 'all'}:
        raise ValueError('Périmètre de données inconnu.')
    rows = [r for r in raw_rows if dataset == 'all' or is_synthetic(r) == (dataset == 'simulated')]
    df = pd.DataFrame(rows, columns=BASE_COLUMNS)
    df[ORIGIN] = [origin_label(r) for r in rows]
    for col in NUMERIC:
        df[col] = pd.to_numeric(df[col], errors='coerce')
    df = df[(df.segment.fillna('').str.strip().str.upper() == 'B2C') &
            (df.technologie.fillna('').str.strip().str.casefold() == 'fibre')].copy()
    df['edition_affichee'] = df['edition'].fillna('Édition non précisée')
    return df


def analyse_dataframe(df):
    df = df.copy()
    df['prix_par_100_mbps'] = (df.prix_mensuel_ttc * 100 / df.debit_mbps.where(df.debit_mbps > 0)).round(2)
    df['debit_tier'] = df.debit_mbps
    for col in ['prix_median_market', 'ecart_a_median_market', 'rang_operateur']:
        df[col] = float('nan')
    usable = df[(df.debit_mbps > 0) & df.prix_mensuel_ttc.notna()]
    # Les simulations peuvent être affichées avec les données réelles, jamais agrégées avec elles.
    grouping = [ORIGIN, 'debit_mbps'] if ORIGIN in usable.columns else ['debit_mbps']
    for _, group in usable.groupby(grouping):
        if group.operateur.nunique() < 2:
            continue
        median = group.prix_mensuel_ttc.median()
        ranks = group.groupby('operateur').prix_mensuel_ttc.min().rank(method='dense')
        df.loc[group.index, 'prix_median_market'] = median
        df.loc[group.index, 'ecart_a_median_market'] = (group.prix_mensuel_ttc - median).round(2)
        df.loc[group.index, 'rang_operateur'] = group.operateur.map(ranks)
    return df


def get_market_dataframe(operator_name=None, fibre_only=None):
    if fibre_only is not None:
        raise ValueError('Le statut TV ne peut pas être déduit du nom des offres.')
    df = analyse_dataframe(_prepare_offers_frame(read_valid_offers()))
    return df if operator_name is None else df[df.operateur == operator_name]


def compute_missed_tiers(operator_name, fibre_only=None, *, frame=None):
    if fibre_only is not None:
        raise ValueError('Statut TV non structuré dans le schéma actuel.')
    df = _prepare_offers_frame(read_valid_offers()) if frame is None else frame
    tiers = set(df.loc[df.debit_mbps > 0, 'debit_mbps'].dropna())
    owned = set(df.loc[df.operateur == operator_name, 'debit_mbps'].dropna())
    return sorted(tiers - owned)


def business_table(df):
    cols = ['operateur', 'nom_offre', 'debit_mbps', 'prix_mensuel_ttc', 'engagement_mois', 'appels_inclus']
    out = df[cols].copy()
    if ORIGIN in df.columns:
        out.insert(0, 'Origine des données', df[ORIGIN])
    out['Tarif document (DH)'] = df.extrait_source.map(lambda value:
        unpack_proof(value).get('terms', {}).get('prix_normal_document') if unpack_proof(value) else None)
    out['engagement_mois'] = out.engagement_mois.map(lambda v: 'Non précisé' if pd.isna(v) else f'{v:g} mois')
    out['appels_inclus'] = out.appels_inclus.fillna('Non précisés — consulter les conditions')
    return out.rename(columns=LABELS)


def _style(fig):
    fig.update_layout(paper_bgcolor='white', plot_bgcolor='white', font_color='#172B4D',
                      margin=dict(l=12, r=12, t=48, b=12), legend_title_text='Opérateur')
    return fig


def _comparable_rows(df, required):
    known = df.dropna(subset=required).copy()
    if ORIGIN in known.columns:
        counts = known.groupby(ORIGIN).operateur.transform('nunique')
        known = known[counts >= 2]
    elif known.operateur.nunique() < 2:
        return known.iloc[0:0]
    return known


def _chart_options(df, title):
    if ORIGIN not in df.columns:
        return dict(title=title)
    options = dict(title=title)
    if (df[ORIGIN] == SIMULATED).any():
        options['title'] += ' — simulations : aucun tarif officiel'
    if df[ORIGIN].nunique() > 1:
        options['facet_col'] = ORIGIN
    return options


def create_price_chart(df):
    known = _comparable_rows(df, ['prix_mensuel_ttc'])
    if known.empty:
        return None
    return _style(px.bar(known, x='nom_offre', y='prix_mensuel_ttc', color='operateur',
                         barmode='group', labels=LABELS, **_chart_options(known, 'Prix des offres du périmètre')))


def create_speed_chart(df):
    known = _comparable_rows(df, ['debit_mbps', 'prix_mensuel_ttc'])
    if known.empty:
        return None
    return _style(px.scatter(known, x='debit_mbps', y='prix_mensuel_ttc', color='operateur',
                             hover_name='nom_offre', labels=LABELS, **_chart_options(known, 'Débit et prix mensuel')))


def create_gap_chart(df):
    known = _comparable_rows(df, ['ecart_a_median_market'])
    if known.empty:
        return None
    return _style(px.bar(known, x='nom_offre', y='ecart_a_median_market', color='operateur',
                         labels=LABELS, **_chart_options(known, 'Écart à la médiane du même débit')))

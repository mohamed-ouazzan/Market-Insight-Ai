import streamlit as st
import hashlib
from db_connection import read_valid_offers
from analyse_offers import (_prepare_offers_frame, analyse_dataframe, business_table, LABELS,
                            compute_missed_tiers, create_price_chart, create_speed_chart, create_gap_chart)
from generate_report import build_report, LIMITS
from ui_common import panel, money, source_details
from provenance import ORIGIN, REAL, SIMULATED

st.title('Étude comparative')
st.write('Offres Fibre B2C validées · données documentaires et simulations identifiées')
st.button('Actualiser les offres', help='Relit les offres validées dans la base, sans cache SQL.')
try:
    raw = read_valid_offers()
except Exception:
    st.error('Connexion à la base indisponible. L’étude ne peut pas être chargée.')
    st.stop()
datasets = {'Toutes les offres validées': 'all', 'Catalogues réels uniquement': 'real',
            'Offres de test simulées uniquement': 'simulated'}
dataset_label = st.selectbox('Données à afficher', list(datasets), key='study_dataset_v2')
base = _prepare_offers_frame(raw, dataset=datasets[dataset_label])
st.caption('Données chargées · seules les offres validées sont incluses.')
if base.empty:
    st.info('Aucune offre Fibre B2C validée disponible dans ce périmètre. Changez le jeu de données ou vérifiez les offres dans l’Espace Analyste.')
    st.stop()
if (base[ORIGIN] == SIMULATED).any():
    st.warning('Ce périmètre contient des offres de test simulées. Elles ne sont pas des tarifs officiels. '
               'Les calculs, graphiques et rapports restent séparés des données réelles.')

# Clés propres au jeu de données et à la version lue : aucune ancienne sélection restrictive ne masque un nouvel opérateur SQL.
signature = hashlib.sha256(base[['id_offre', 'operateur', 'edition_affichee', 'debit_mbps', ORIGIN]]
                           .to_json().encode()).hexdigest()[:12]
namespace = datasets[dataset_label] + '_' + signature

with panel('filters'):
    st.subheader('Périmètre de l’étude')
    a, b, c = st.columns(3)
    available_operators = sorted(base.operateur.dropna().unique())
    chosen = a.multiselect('Opérateurs comparés', available_operators, default=available_operators,
                           key=f'operators_{namespace}')
    editions = b.multiselect('Éditions des catalogues', sorted(base.edition_affichee.unique()), default=sorted(base.edition_affichee.unique()),
                             key=f'editions_{namespace}')
    speeds = sorted(base.debit_mbps.dropna().unique().tolist())
    selected_speeds = c.multiselect('Débits (Mbps)', speeds, default=speeds, key=f'speeds_{namespace}')
    include_unknown = st.checkbox('Inclure les offres dont le débit est inconnu', value=True, key=f'unknown_{namespace}')
    client = st.selectbox('Votre opérateur', available_operators, key=f'client_{namespace}')
    st.caption('Le statut TV n’est pas structuré dans les catalogues enregistrés. Consultez les conditions de chaque offre.')
mask_speed = base.debit_mbps.isin(selected_speeds) | (base.debit_mbps.isna() & include_unknown)
frame = base[base.operateur.isin(chosen) & base.edition_affichee.isin(editions) & mask_speed]
if frame.empty:
    st.info('Aucune offre ne correspond à ces filtres. Élargissez le périmètre de l’étude.')
    st.stop()
frame = analyse_dataframe(frame)
if len(frame) == 1:
    st.info('Une seule offre validée est disponible. Ajoutez et validez des offres concurrentes pour réaliser une comparaison.')
elif frame.operateur.nunique() < 2:
    st.info('Un seul opérateur est représenté dans ce périmètre. Une comparaison concurrentielle demande des offres d’autres opérateurs.')
if frame.edition_affichee.nunique() > 1:
    st.warning('Les éditions des catalogues diffèrent. Les prix ne sont pas nécessairement contemporains.')
st.caption('Éditions du périmètre : ' + ' · '.join(frame.edition_affichee.unique()))

has_simulations = (frame[ORIGIN] == SIMULATED).any()
metric_labels = ['Offres affichées', 'Opérateurs représentés', 'Offres documentaires', 'Offres simulées'] if has_simulations else [
    'Offres affichées', 'Opérateurs représentés', 'Prix médian du périmètre', 'Débits renseignés']
metric_values = [len(frame), frame.operateur.nunique(), int((frame[ORIGIN] == REAL).sum()), int((frame[ORIGIN] == SIMULATED).sum())] if has_simulations else [
    len(frame), frame.operateur.nunique(), money(frame.prix_mensuel_ttc.median()), f'{frame.debit_mbps.notna().sum()} / {len(frame)}']
for i, (col, label, value) in enumerate(zip(st.columns(4), metric_labels, metric_values)):
    with col, panel(f'metric_{i}'):
        st.metric(label, value)
st.caption('Aucune médiane ni aucun rang ne mélange données réelles et simulations. Les calculs simulés servent uniquement à tester l’application.')

with panel('table'):
    st.subheader('Offres du périmètre')
    st.dataframe(business_table(frame), hide_index=True, width='stretch', column_config={
        'Prix mensuel TTC': st.column_config.NumberColumn(format='%.2f DH'),
        'Débit (Mbps)': st.column_config.NumberColumn(format='%d'),
    })
    st.markdown('**Indicateurs par offre**')
    cols = [ORIGIN, 'operateur', 'nom_offre', 'prix_par_100_mbps']
    if frame.ecart_a_median_market.notna().any():
        cols += ['prix_median_market', 'ecart_a_median_market', 'rang_operateur']
    st.dataframe(frame[cols].rename(columns=LABELS), hide_index=True, width='stretch')
    st.caption('Le tarif document n’est pas assimilé à un prix TTC lorsque la fiscalité ou la périodicité manque. Palier = débit permanent exact. Médiane et rang exigent plusieurs opérateurs à prix TTC connu au même débit.')
    for origin, origin_frame in frame.groupby(ORIGIN):
        if origin_frame.operateur.nunique() >= 2:
            missing = compute_missed_tiers(client, frame=origin_frame)
            st.write(f'{origin} · paliers sans offre de {client} : ' + (', '.join(f'{v:g} Mbps' for v in missing) if missing else 'aucun dans ce périmètre.'))

if len(frame) > 1 and frame.operateur.nunique() >= 2:
    charts = [chart for chart in (create_price_chart(frame), create_speed_chart(frame), create_gap_chart(frame)) if chart is not None]
    if charts:
        st.subheader('Lecture visuelle')
        for i, chart in enumerate(charts):
            with panel(f'chart_{i}'):
                st.plotly_chart(chart, width='stretch')
    else:
        st.info('Les prix TTC connus ne couvrent pas plusieurs opérateurs. Aucun graphique concurrentiel n’est produit ; consultez les tarifs documentaires et les informations à vérifier.')

st.subheader('Sources et détails')
offers = frame.to_dict('records')
choice = st.selectbox('Consulter une offre', list(range(len(offers))),
                      format_func=lambda i: f"{offers[i][ORIGIN]} · {offers[i]['operateur']} · {offers[i]['nom_offre']}")
offer = offers[choice]
with panel('source'):
    source_details(offer, key=f"client_{offer['id_offre']}")
    st.markdown('**Services et conditions**')
    st.write(offer.get('appels_inclus') or 'Services non précisés.')
    st.write(offer.get('conditions_offre') or 'Conditions non précisées.')
    st.write('Frais d’installation TTC : ' + money(offer.get('frais_installation_ttc')))
    with st.expander('Détails techniques de l’offre'):
        st.json({k: offer.get(k) for k in ('id_offre', 'segment', 'technologie', 'page_source')})

st.subheader('Rapport de l’étude')
st.caption('Rapport descriptif du périmètre affiché, calculé en Python. Aucune synthèse IA n’est générée ici.')
for origin, report_frame in frame.groupby(ORIGIN):
    simulated = origin == SIMULATED
    report_dataset = 'simulated' if simulated else 'real'
    md, document = build_report(report_frame, client, dataset=report_dataset)
    label = 'Simulation — tarifs fictifs' if simulated else 'Catalogues réels'
    with st.expander(f'Aperçu du rapport · {label}'):
        st.markdown(md)
    a, b = st.columns(2)
    suffix = 'simulation' if simulated else 'reel'
    a.download_button(f'Markdown · {label}', md, file_name=f'market-insight-{suffix}.md', mime='text/markdown', key=f'md_{suffix}')
    b.download_button(f'HTML · {label}', document, file_name=f'market-insight-{suffix}.html', mime='text/html', key=f'html_{suffix}')
with st.expander('Méthode et limites'):
    st.write(LIMITS)

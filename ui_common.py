"""Présentation commune, preuves et brouillons persistants."""
import pandas as pd
import re
import streamlit as st
from catalogue_storage import local_pdf
from extract_offers_ai import OFFER_FIELDS
from offer_evidence import unpack_proof
from extract_pdf import render_source_page
from provenance import is_synthetic


def panel(key):
    return st.container(border=True, key=f'panel_{key}')


def money(value):
    return 'Non précisé' if pd.isna(value) else f'{value:,.2f} DH'.replace(',', ' ')


def safe_url(url):
    return isinstance(url, str) and url.lower().startswith(('https://', 'http://'))


def source_details(offer, pages=None, key='source'):
    display_name = re.sub(r'__[a-f0-9]{64}(?=\.pdf$)', '', offer.get('nom_fichier', 'Catalogue importé'))
    st.caption(f"{offer.get('operateur', '')} · {display_name} · "
               f"{offer.get('edition') or 'Édition non précisée'} · Page {offer.get('page_source') or 'non précisée'}")
    if is_synthetic(offer):
        st.warning('Donnée simulée pour tester l’application. Le nom de l’opérateur ne représente pas un tarif officiel.')
        st.text(offer.get('extrait_source') or 'Exemple de test sans preuve documentaire officielle.')
        return
    if safe_url(offer.get('url_source')):
        st.link_button('Ouvrir la source', offer['url_source'])
    proof = unpack_proof(offer.get('extrait_source'))
    st.markdown('**Preuves du document**')
    if proof:
        terms = proof.get('terms', {})
        if terms:
            st.caption(f"Tarif normal document : {terms.get('prix_normal_document') if terms.get('prix_normal_document') is not None else 'inconnu'} DH · Fiscalité : {terms.get('taxe', 'inconnue')}")
            if terms.get('prix_promotionnel_document') is not None:
                st.write(f"Promotion : {terms['prix_promotionnel_document']:g} DH pendant {terms['duree_promotion_mois']} mois, puis {terms['prix_normal_document']:g} DH.")
            if terms.get('debit_temporaire_mbps') is not None:
                st.write(f"Débit temporaire : {terms['debit_temporaire_mbps']} Mbps pendant {terms['duree_debit_temporaire_mois']} mois ; débit permanent : {offer.get('debit_mbps')} Mbps.")
            if terms.get('frais_installation_document') is not None:
                st.caption(f"Installation indiquée dans le document : {terms['frais_installation_document']:g} DH. Les frais d’équipement restent distincts dans les conditions et preuves.")
        for warning in proof.get('warnings', []):
            st.caption('À vérifier : ' + warning)
        for index, ref in enumerate(proof['sources']):
            with st.expander(f"Page {ref['page']} · {ref.get('role', 'source')}", expanded=index==0):
                st.text(ref['quote'])
    else:
        st.text(offer.get('extrait_source') or 'Aucun extrait renseigné.')
    if pages is not None:
        with st.expander('Texte complet de la page'):
            st.text(pages.get(offer.get('page_source'), 'Page introuvable.'))
    path = local_pdf(offer.get('nom_fichier', ''))
    if path:
        with st.expander('Voir la page originale'):
            refs = proof['sources'] if proof else [dict(page=offer.get('page_source') or 1, bbox=None)]
            for ref in refs:
                try:
                    st.image(render_source_page(path, ref['page'], ref.get('bbox')), width='stretch',
                             caption=f"Page {ref['page']} — zone source" if ref.get('bbox') else f"Page {ref['page']}")
                except (ValueError,IndexError,RuntimeError):
                    st.caption('Aperçu indisponible ; téléchargez le document original.')
        st.download_button('Télécharger le PDF source', path.read_bytes(), file_name=path.name,
                           mime='application/pdf', key=f'pdf_{key}')


def records(frame):
    return [{k: (None if pd.isna(v) else v) for k, v in row.items()}
            for row in frame.to_dict(orient='records')]


def persistent_editor(state_key, *, height='auto', num_rows='fixed'):
    """Sauvegarde les données métier hors des clés de widgets supprimées à la navigation."""
    widget = f'editor_{state_key}'
    base = f'base_{state_key}'
    if widget not in st.session_state:
        st.session_state[base] = st.session_state[state_key].copy(deep=True)
    edited = st.data_editor(st.session_state[base], key=widget, hide_index=True,
                            num_rows=num_rows, width='stretch', height=height,
                            column_config={
                                'nom_offre': st.column_config.TextColumn('Offre'),
                                'technologie': st.column_config.TextColumn('Technologie'),
                                'debit_mbps': st.column_config.NumberColumn('Débit (Mbps)', min_value=1, step=1),
                                'prix_mensuel_ttc': st.column_config.NumberColumn('Prix mensuel TTC (DH)', min_value=0, step=0.01),
                                'engagement_mois': st.column_config.NumberColumn('Engagement (mois)', min_value=0, step=1),
                                'frais_installation_ttc': st.column_config.NumberColumn('Installation TTC (DH)', min_value=0, step=0.01),
                                'appels_inclus': st.column_config.TextColumn('Services / appels inclus'),
                                'conditions_offre': st.column_config.TextColumn('Conditions et promotions'),
                                'page_source': st.column_config.NumberColumn('Page source', min_value=1, step=1),
                                'extrait_source': None,
                            })
    st.session_state[state_key] = edited.copy(deep=True)
    return edited


def offer_frame(items):
    frame = pd.DataFrame(items, columns=OFFER_FIELDS)
    for col in ('prix_mensuel_ttc', 'frais_installation_ttc'):
        frame[col] = pd.to_numeric(frame[col], errors='coerce').astype(float)
    for col in ('debit_mbps', 'engagement_mois', 'page_source'):
        frame[col] = pd.array(frame[col], dtype='Int64')
    for col in ('nom_offre', 'technologie', 'appels_inclus', 'conditions_offre', 'extrait_source'):
        frame[col] = frame[col].astype('string')
    return frame

import streamlit as st
from analyst_repository import read_counts

st.title('Market Insight AI')
st.write('Comparez les offres Fibre des opérateurs marocains à partir de catalogues vérifiés.')
a,b=st.columns(2)
if a.button('Importer un catalogue',type='primary',width='stretch'):
    st.switch_page('pages/2_Espace_Analyste.py')
if b.button('Consulter l’étude',width='stretch'):
    st.switch_page('pages/1_Espace_Client.py')
st.divider()
try:
    counts=read_counts()
except Exception:
    st.error('Connexion à la base indisponible. Les compteurs ne peuvent pas être chargés.')
else:
    a,b,c=st.columns(3)
    a.metric('Catalogues réels',counts['catalogues'])
    b.metric('Offres réelles validées',counts['validees'])
    c.metric('Offres réelles à vérifier',counts['en_attente'])
    if counts.get('demonstrations'):
        st.caption(f"{counts['demonstrations']} offres de test disponibles dans l’étude, clairement signalées comme simulations et séparées des calculs réels.")
    if not counts['catalogues']:
        st.info('Aucun catalogue réel enregistré. Commencez par importer un PDF.')
st.caption('Importer le PDF → Extraire les propositions → Vérifier les preuves → Comparer les offres validées.')

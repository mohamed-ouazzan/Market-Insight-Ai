import streamlit as st

st.set_page_config(page_title='Market Insight AI', page_icon=':material/insights:', layout='wide')
st.html('''<style>
[class*="st-key-panel_"] { background: #fff; }
[data-testid="stSidebar"] h3 {font-size: 1.05rem; margin-bottom: 0;}
[data-testid="stSidebar"] { min-width: 245px; max-width: 280px; }
</style>''')
with st.sidebar:
    st.subheader('Market Insight AI')
    st.caption('Veille Fibre · Maroc')
page = st.navigation([
    st.Page('pages/0_Accueil.py', title='Accueil', icon=':material/home:', default=True),
    st.Page('pages/1_Espace_Client.py', title='Étude comparative', icon=':material/insights:', url_path='etude'),
    st.Page('pages/2_Espace_Analyste.py', title='Espace Analyste', icon=':material/fact_check:', url_path='analyste'),
])
with st.sidebar:
    st.divider()
    st.caption('Des catalogues aux décisions.\n\nÉtude fondée sur des offres vérifiées.')
page.run()

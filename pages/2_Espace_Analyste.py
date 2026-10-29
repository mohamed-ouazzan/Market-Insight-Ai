import hashlib
import json
from pathlib import Path
import streamlit as st
import pandas as pd
from analyst_repository import read_operators,read_pending,read_catalogues,review_offer
from db_connection import read_valid_offers
from extract_pdf import extract_pdf_pages
from extract_offers_ai import extract_offers_with_metadata,validate_offer,OFFER_FIELDS
from llm_client import llm_configuration
from save_offers import save_offers_from_preview
from catalogue_storage import store_pdf,catalogue_name,source_pages,local_pdf
from catalogue_identity import validate_catalogue_metadata,identify_catalogue
from provenance import separate_records,is_synthetic
from offer_evidence import unpack_proof
from ui_common import source_details,persistent_editor,offer_frame,records,safe_url

st.title('Espace Analyste')
st.caption('Importer, corriger et vérifier les offres avant leur publication.')
if 'analyst_notice' in st.session_state:
    st.success(st.session_state.pop('analyst_notice'))
try:
    operators=read_operators();all_pending=read_pending();catalogues=read_catalogues()
    pending,demo_pending=separate_records(all_pending)
except Exception:
    st.error('Connexion à la base indisponible. Les brouillons restent disponibles pendant cette session.')
    operators,pending,catalogues,demo_pending=[],None,None,[]

import_tab,review_tab,history_tab=st.tabs(['Import et aperçu','Validation','Historique des catalogues'])
with import_tab:
    with st.form('import_form'):
        uploaded=st.file_uploader('Catalogue PDF',type=['pdf'])
        local_files=sorted(Path('Data').glob('*.pdf'))
        local_choice=st.selectbox('Ou utiliser un PDF déjà présent sur cet ordinateur',['Aucun']+[p.name for p in local_files])
        a,b=st.columns(2)
        operator=a.selectbox('Opérateur du catalogue',[r['nom'] for r in operators])
        edition=b.text_input('Édition',max_chars=50,placeholder='Date de l’édition, si connue')
        url=st.text_input('Source (URL facultative)',max_chars=1000,placeholder='https://…')
        extract=st.form_submit_button('Extraire les offres',type='primary',disabled=not operators)
    if extract:
        if uploaded is None and local_choice=='Aucun':
            st.warning('Sélectionnez un catalogue PDF.')
        else:
            try:
                original=uploaded.name if uploaded is not None else local_choice
                content=uploaded.getvalue() if uploaded is not None else next(p for p in local_files if p.name==local_choice).read_bytes()
                path=store_pdf(content)
                with st.spinner('Lecture des pages et des colonnes du catalogue…'):
                    pages=extract_pdf_pages(path)
                identity=validate_catalogue_metadata(operator,edition or None,url or None,pages)
                chosen_edition=edition or (identity['editions'][0] if len(identity['editions'])==1 else None)
                with st.spinner('Extraction des propositions et contrôle des preuves…'):
                    result=extract_offers_with_metadata(pages,operator)
                st.session_state['import_draft']=dict(pages=pages,operator=operator,edition=chosen_edition,url=url or None,
                    name=catalogue_name(original,content),original=original,mode=result.mode,rejected=result.rejected,
                    diagnostics=result.diagnostics,summary=result.summary,configuration=result.configuration,identity=identity)
                st.session_state['import_revision']=st.session_state.get('import_revision',0)+1
                key=f"preview_{st.session_state['import_revision']}"
                st.session_state[key]=offer_frame(result.offers)
            except ValueError as exc:
                st.error(str(exc))
            except Exception:
                st.error('Lecture du PDF impossible. Vérifiez le fichier et sa protection. Le brouillon précédent est conservé.')
    if 'import_draft' in st.session_state:
        draft=st.session_state['import_draft']
        st.subheader('Aperçu et correction')
        st.caption(f"{draft['original']} · {draft['operator']} · {draft['edition'] or 'Édition non précisée'}")
        st.info('Mode d’extraction : '+draft['mode'])
        summary=draft.get('summary',{})
        if summary:
            a,b,c=st.columns(3)
            a.metric('Pages lues',summary['pages_lues']);b.metric('Candidats détectés',summary['candidats_detectes']);c.metric('Offres acceptées',summary['offres_acceptees'])
        with st.expander('Diagnostics d’extraction'):
            st.json(draft.get('configuration',{}))
            diag=draft.get('diagnostics',[])
            if diag:
                visible=[]
                for d in diag:
                    visible.append({'Page':d['page'],'Texte (caractères)':d['caracteres'],'Fibre mentionnée':d['pertinente'],
                        'Structure':d['structure'],'Candidats':d['candidats'],'Acceptées':d['acceptees'],'LLM':d['llm'],
                        'Mode':d['mode'],'Motifs de rejet':' ; '.join(d['rejets']),'À vérifier':' ; '.join(d['attention'])})
                st.dataframe(pd.DataFrame(visible),hide_index=True,width='stretch')
                st.download_button('Télécharger le diagnostic JSON',json.dumps(dict(summary=summary,pages=diag),ensure_ascii=False,indent=2),
                                   file_name='diagnostic-extraction.json',mime='application/json')
        key=f"preview_{st.session_state['import_revision']}"
        edited=persistent_editor(key,num_rows='dynamic')
        items=records(edited)
        st.caption('Prix TTC inconnu ≠ zéro. Le tarif document, la promotion et les preuves sont visibles en sélectionnant une offre.')
        if items:
            i=st.selectbox('Consulter les preuves et conditions',list(range(len(items))),format_func=lambda i:f"{i+1} · {items[i].get('nom_offre') or 'Offre sans nom'}")
            source_details({**items[i],'nom_fichier':draft['name'],'operateur':draft['operator'],'edition':draft['edition'],'url_source':draft['url']},draft['pages'],key='preview')
        else:
            st.warning('Aucune proposition acceptée. Consultez les diagnostics : la cause est indiquée par page.')
            number=st.selectbox('Consulter une page du document',list(draft['pages']))
            st.text(draft['pages'][number] or 'Page sans texte : OCR ou analyse visuelle nécessaire.')
        with st.expander('Saisir une offre manquante'):
            with st.form('manual_offer'):
                name=st.text_input('Nom descriptif de l’offre')
                a,b=st.columns(2)
                speed=a.number_input('Débit permanent (Mbps)',min_value=1,value=None,step=1)
                price=b.number_input('Prix normal mensuel TTC justifié (DH)',min_value=0.0,value=None,step=0.01)
                page=st.selectbox('Page de la preuve',list(draft['pages']))
                quote=st.text_area('Extrait original exact à copier depuis cette page')
                add=st.form_submit_button('Ajouter au brouillon')
            if add:
                data={k:None for k in OFFER_FIELDS}
                data.update(nom_offre=name,technologie='Fibre',debit_mbps=speed,prix_mensuel_ttc=price,page_source=page,extrait_source=quote)
                try:
                    data=validate_offer(data,draft['pages'])
                except ValueError as exc:
                    st.error(str(exc))
                else:
                    st.session_state['import_revision']+=1
                    st.session_state[f"preview_{st.session_state['import_revision']}"]=offer_frame(items+[data])
                    st.rerun()
        checked=st.checkbox('J’ai vérifié l’opérateur, l’édition et la source de ce document.',key=f'metadata_{key}')
        if st.button('Enregistrer les offres à vérifier',type='primary',disabled=not items or not checked):
            try:
                result=save_offers_from_preview(items,draft['name'],draft['operator'],edition=draft['edition'],url_source=draft['url'],pages=draft['pages'])
            except ValueError as exc:
                st.error(str(exc))
            except Exception:
                st.error('Enregistrement impossible. Vérifiez la connexion à la base ; le brouillon est conservé.')
            else:
                st.session_state['analyst_notice']=f"{result['saved_count']} nouvelle(s) offre(s) en attente ; {result.get('duplicate_count',0)} doublon(s) ignoré(s)."
                st.rerun()

with review_tab:
    if pending is None:
        st.warning('Offres en attente indisponibles.')
    elif not pending:
        st.info('Aucune offre en attente de vérification.')
    else:
        st.caption(f'{len(pending)} offre(s) réelle(s) en attente de vérification')
        selected_id=st.selectbox('Offre à vérifier',[r['id_offre'] for r in pending],
            format_func=lambda id_:next(f"{r['operateur']} · {r['nom_offre']} · page {r['page_source']}" for r in pending if r['id_offre']==id_))
        original=next(r for r in pending if r['id_offre']==selected_id)
        revision=st.session_state.get(f'review_revision_{selected_id}',0)
        key=f'review_{selected_id}_{revision}'
        if key not in st.session_state:
            st.session_state[key]=offer_frame([{k:original[k] for k in OFFER_FIELDS}])
            st.session_state[f'snapshot_{key}']=original.copy()
        try:pages=source_pages(original['nom_fichier'])
        except Exception:pages=None
        changed=records(persistent_editor(key))[0]
        source_details({**original,**changed},pages,key=f'review_{selected_id}')
        if pages is None:
            st.warning('PDF local absent. La publication est bloquée tant que la preuve ne peut pas être vérifiée. Vos corrections peuvent être enregistrées.')
        signature=hashlib.sha256(json.dumps(changed,sort_keys=True,default=str).encode()).hexdigest()[:12]
        confirmed=st.checkbox('J’ai vérifié les chiffres, les conditions et les preuves dans le catalogue original.',key=f'confirm_{key}_{signature}')
        a,b=st.columns(2)
        validate=a.button('Valider et publier dans l’étude',type='primary',disabled=not confirmed or pages is None)
        save=b.button('Enregistrer les corrections')
        with st.expander('Rejeter cette offre'):
            st.caption('Cette action supprime l’offre non validée. Le rejet n’est pas archivé.')
            reject_confirmed=st.checkbox('Confirmer la suppression de cette offre non validée',key=f'reject_{selected_id}')
            reject=st.button('Rejeter l’offre',disabled=not reject_confirmed)
        if validate or save or reject:
            try:
                review_offer(selected_id,st.session_state[f'snapshot_{key}'],changed,validate=validate,reject=reject,pages=pages)
            except ValueError as exc:st.error(str(exc))
            except Exception:st.error('Action non enregistrée. Le brouillon est conservé ; vérifiez la connexion.')
            else:
                st.session_state.pop(key,None)
                st.session_state[f'review_revision_{selected_id}']=revision+1
                st.session_state['analyst_notice']='Offre validée et publiée.' if validate else 'Offre rejetée.' if reject else 'Corrections enregistrées.'
                st.rerun()
    if demo_pending:
        with st.expander(f'Démonstration — {len(demo_pending)} offre(s) séparée(s)'):
            st.caption('Conservées en base, exclues de la validation destinée à l’étude réelle.')
            st.dataframe(pd.DataFrame(demo_pending)[['operateur','nom_offre','edition']],hide_index=True,width='stretch')

with history_tab:
    if catalogues is None:st.warning('Historique indisponible.')
    elif not catalogues:st.info('Aucun catalogue enregistré.')
    else:
        for cat in catalogues:
            demo=is_synthetic(cat)
            status='Démonstration — exclu de l’étude' if demo else 'À vérifier' if cat['en_attente'] else 'Offres validées' if cat['validees'] else 'Aucune offre enregistrée'
            with st.expander(f"{cat['operateur']} · {cat['edition'] or 'Édition non précisée'} · {status}"):
                st.text(cat['nom_fichier'])
                st.write(f"{cat['offres']} offre(s) · {cat['validees']} validée(s) · {cat['en_attente']} à vérifier")
                if safe_url(cat['url_source']):st.link_button('Ouvrir la source',cat['url_source'])
                path=local_pdf(cat['nom_fichier'])
                if path:
                    st.download_button('Télécharger le PDF',path.read_bytes(),file_name=path.name,mime='application/pdf',key=f"catalogue_{cat['id_catalogue']}")
                elif not demo:st.caption('PDF absent localement. Utilisez la source ou votre document original.')
with st.expander('Diagnostic technique'):
    st.json(llm_configuration())
    st.caption('LLM non configuré ou indisponible : règles sur les colonnes PDF. Pas d’OCR ni de modèle visuel activé ; les services en image doivent être relus.')
    if st.button('Vérifier la connexion'):
        try:read_valid_offers(limit=1)
        except Exception:st.error('Connexion à la base indisponible ou lecture impossible.')
        else:st.success('Connexion disponible. Lecture des offres validées fonctionnelle.')

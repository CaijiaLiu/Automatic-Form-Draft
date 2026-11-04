"""One local flow: recognize synthetic records and prefill official form."""
from __future__ import annotations
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import tempfile
import time
import streamlit as st
from src.autofill import assemble_autofill
from src.layout_tables import extract_with_layout
from src.semantic import local_status,missing_categories
from src.review_jobs import ReviewJobs
from src.official_form import TEXT_FIELDS,CHECKBOX_FIELDS,BUTTON_CHOICES,export_official_draft,export_evidence_report,SOURCE_URL

ROOT=Path(__file__).parent
st.set_page_config(page_title='ITP automatic form draft',layout='wide')
st.title('ITP Drug Access — Automatic Form Draft')
st.warning('Synthetic or public sample records only. Drafts require review and are not for clinical use or submission.')
st.caption('Upload records for one patient → Extract text and tables locally → Prefill HLTH 5328 → Review, edit and export.')
parser_revision=hashlib.sha256(b''.join((ROOT/'src'/name).read_bytes() for name in
    ['extractor.py','demographics.py','prescriber.py','document_text.py','fast_fields.py','semantic.py','models.py','layout_tables.py','official_form.py','autofill.py','clinical_draft.py','review_jobs.py'])).hexdigest()

@st.cache_data(ttl=300,show_spinner='Reading documents and tables locally…')
def read_source(filename: str,content: bytes,revision: str):
    with tempfile.TemporaryDirectory() as tmp:
        path=Path(tmp)/Path(filename).name
        path.write_bytes(content)
        return extract_with_layout(path,allow_ocr=False)

@st.cache_data(ttl=5,show_spinner=False)
def ai_status():return local_status()

@st.cache_resource
def build_review_jobs(revision):
    # A Streamlit rerun can retain an older imported module as well as a cached
    # resource. Pass the revision explicitly and recover the old module once.
    import importlib
    module=importlib.import_module('src.review_jobs')
    if not hasattr(module.ReviewJobs,'start_clinical'):
        module=importlib.reload(module)
    return module.ReviewJobs()

def review_jobs():return build_review_jobs(parser_revision)

@st.fragment(run_every='1s')
def review_progress(job_key):
    job=review_jobs().get(job_key)
    if job and job['future'].done():st.rerun(scope='app')
    if job:st.info(job['message']+' You can continue editing and exporting the draft below.')

def mark_edited(key,field):
    touched=set(st.session_state.get(key+'_edited',[]));touched.add(field)
    st.session_state[key+'_edited']=list(touched)

def render_clinical_panel(result,key,case_key,sources,rows):
    from src.clinical_draft import VERSION
    if result.identity_conflict:return
    st.subheader('AI-assisted Section 3 · Clinical Supporting Details')
    st.caption('Generate an editable English draft from source excerpts: diagnosis, prior treatment and response. Local AI selects original wording; it does not recommend treatment. Scanned pages are deferred.')
    state='clinical_'+case_key
    pending=st.session_state.get(state+'_pending')
    if pending:
        job=review_jobs().get(pending)
        if job and job['future'].done():
            try:
                draft=job['future'].result()
                st.session_state[state+'_result']=draft
                field_key=f'{key}_Supporting Details'
                current=st.session_state.get(field_key,result.values.get('Supporting Details',''))
                unchanged=current==st.session_state.get(state+'_snapshot',current)
                untouched='Supporting Details' not in st.session_state.get(key+'_edited',[])
                if draft.text and unchanged and untouched:
                    st.session_state[field_key]=draft.text
                    st.session_state[state+'_applied']=draft
                elif draft.text:
                    st.session_state[state+'_preserved']=True
            except Exception as exc:st.error('Section 3 review failed: '+type(exc).__name__)
            st.session_state.pop(state+'_pending',None);pending=None
    status=ai_status()
    if not status.get('ready'):st.info(status['detail'])
    if st.button('Generate & auto-fill Section 3 with local AI',disabled=not status.get('ready') or bool(pending),key=state+'_generate'):
        job_key=hashlib.sha256((case_key+parser_revision+VERSION+status['model']).encode()).hexdigest()
        try:
            review_jobs().start_clinical(job_key,sources,rows,status['model'])
            st.session_state[state+'_snapshot']=st.session_state.get(f'{key}_Supporting Details',result.values.get('Supporting Details',''))
            st.session_state[state+'_pending']=job_key;pending=job_key
            st.session_state.pop(state+'_preserved',None)
        except RuntimeError as exc:st.info(str(exc))
    if pending:review_progress(pending)
    draft=st.session_state.get(state+'_result')
    if draft:
        if st.session_state.get(state+'_preserved'):
            st.info('Your Section 3 edits were preserved. Review the suggestion below before replacing your text.')
        if draft.text:
            st.caption(f"Local AI draft ready · {draft.usage.get('wall_seconds','—')} seconds. Review the source links below and edit Supporting Details in the form.")
            with st.expander('Review AI draft and original evidence',expanded=bool(st.session_state.get(state+'_preserved'))):
                st.text(draft.text)
                for item in draft.items:
                    st.markdown('**'+item['category'].replace('_',' ').title()+'** · '+item['filename']+' · '+item['location'])
                    st.text(item['text'])
                for note in draft.notes:st.caption(note)
            if st.button('Replace Supporting Details with this AI draft',key=state+'_apply'):
                st.session_state[f'{key}_Supporting Details']=draft.text
                st.session_state[state+'_applied']=draft
                st.session_state.pop(state+'_preserved',None)
        else:
            st.warning('No AI draft was applied. The existing form is unchanged.')
            for note in draft.notes:st.caption(note)
    applied=st.session_state.get(state+'_applied')
    if applied:
        result.facts.extend(applied.facts)
        st.caption('Section 3 AI source excerpts are included in the separate Internal Evidence Report. Selected passages may be incomplete or misclassified; clinical review is required.')

def render_form(result,key):
    st.subheader('Automatically Prefilled · BC HLTH 5328')
    st.markdown(f'[Official blank form]({SOURCE_URL}) · Original fillable PDF · Draft for review')
    if result.identity_conflict:
        st.error('Different patient names or birth dates were detected. A combined application is blocked. Use records for one patient; original pages remain available for inspection.')
        return
    if not result.facts:
        st.info('No supported fields were found. Inspect the original records; unsupported information will not be added to an application.')
    proposals=result.values
    copied=[field for field,value in proposals.items() if value and
        (field=='Supporting Details' or result.reviews.get(field,{}).get('evidence'))]
    missing=[TEXT_FIELDS[field] for field,value in proposals.items() if not st.session_state.get(f'{key}_{field}',value) and field not in {'Medication Requested','Dose and Regimen'}]
    st.success(f'Source information has automatically filled {len(copied)} form fields. Edits below update the PDF draft on the right.')
    if missing:st.caption('Requires Review — missing or conflicting source information: '+', '.join(missing))
    st.caption('Medication requested and dose/regimen are clinician-entry fields. Source mentions are available for review, but are never automatically applied. The application date defaults to today in Vancouver when not documented.')
    editor,preview=st.columns([1,1])
    edited={}
    with editor:
        for field,label in TEXT_FIELDS.items():
            widget_key=f'{key}_{field}'
            if widget_key not in st.session_state:
                st.session_state[widget_key]=proposals[field]
            elif not st.session_state[widget_key] and field not in st.session_state.get(key+'_edited',[]):
                st.session_state[widget_key]=proposals[field]
            if field in {'Supporting Details','Presciber Name and Mailing Address'}:
                edited[field]=st.text_area(label,height=220 if field=='Supporting Details' else 105,
                    key=widget_key,on_change=mark_edited,args=(key,field))
            else:
                edited[field]=st.text_input(label,
                    placeholder='Clinician entry required' if field in {'Medication Requested','Dose and Regimen'} else 'Requires Review — no reliable source information found',
                    key=widget_key,on_change=mark_edited,args=(key,field))
            review=result.reviews.get(field,{})
            if review.get('evidence'):st.caption('Prefill evidence: '+', '.join(review['evidence'])+' · See Field Sources & Review')
        choices={
            'Request':st.selectbox('New request or renewal',BUTTON_CHOICES['Request'],
                format_func=lambda x:x.lstrip('/'),key=f'{key}_request'),
            'Certification Number':st.selectbox('Prescriber licence type',BUTTON_CHOICES['Certification Number'],
                format_func=lambda x:x.lstrip('/'),key=f'{key}_licence'),
        }
        checks={field:st.checkbox(label,key=f'{key}_{field}') for field,label in CHECKBOX_FIELDS.items()}
        reviewed=st.checkbox('I reviewed the synthetic source records (demo only; not a signature or consent)',key=f'{key}_review')
    with preview:
        st.subheader('Separate PDF Exports')
        evidence=export_evidence_report(edited,result.facts,choices=choices,checks=checks,reviewed=reviewed)
        pdf=None
        try:
            pdf=export_official_draft(edited,result.facts,choices=choices,checks=checks,reviewed=reviewed)
        except ValueError as exc:
            st.error(str(exc))
        if pdf:
            st.download_button('Download Application Draft Only',pdf,
                'hlth_5328_application_draft.pdf','application/pdf',key=f'{key}_download')
        st.download_button('Download Internal Evidence Report',evidence,
            'internal_evidence_review.pdf','application/pdf',key=f'{key}_evidence_download')
        st.caption('For internal checking: full edited text, source references and review notes. Exported separately from the application.')
        options=['Application Draft','Internal Evidence Report'] if pdf else ['Internal Evidence Report']
        selected=st.radio('PDF preview',options,horizontal=True,key=f'{key}_export_preview')
        shown=pdf if selected=='Application Draft' else evidence
        import pymupdf
        with pymupdf.open(stream=shown,filetype='pdf') as doc:
            number=st.selectbox('Preview page',list(range(1,len(doc)+1)),key=f'{key}_preview_{selected}')
            st.image(doc[number-1].get_pixmap(matrix=pymupdf.Matrix(1.5,1.5)).tobytes('png'),
                caption='Preview of the selected export. The application remains an editable PDF.',width='stretch')
        st.caption('All extracted values require review. The application contains no internal evidence pages. Signature, consent and PharmaCare-only areas remain blank.')

def render_sources(result,documents):
    st.subheader('Original PDFs & Linked Table Rows')
    if not documents:
        st.info('No PDFs are included. Text, CSV and Word evidence is available under Field Sources & Review.')
        return
    filename=st.selectbox('Inspect original source',list(documents))
    import pymupdf
    with pymupdf.open(stream=documents[filename],filetype='pdf') as doc:
        number=st.selectbox('Source page',list(range(1,len(doc)+1)))
        page=doc[number-1]
        rows=[r for r in result.rows if r.filename==filename and r.page==number]
        original,extracted=st.columns([1,1])
        with original:
            st.image(page.get_pixmap(matrix=pymupdf.Matrix(1.4,1.4)).tobytes('png'),
                caption=f'Unchanged original: {filename}, page {number}',width='stretch')
        with extracted:
            if rows:
                if any(r.kind=='unmapped_table' for r in rows):
                    st.warning('Table boundaries and cells were recovered, but clinical meanings, date roles and field mappings are not yet resolved. These cells do not automatically populate the application.')
                st.dataframe([{'kind':r.kind,'table':r.table,'row':r.row,**r.cells,'event_date':r.event_date,
                    'date_role':r.date_kind,'subject_context':r.subject_context,'method':r.method}
                    for r in rows],hide_index=True,width='stretch')
                index=st.selectbox('Inspect a linked original row',list(range(len(rows))),
                    format_func=lambda i:f'Table {rows[i].table}, row {rows[i].row}: '+next(iter(rows[i].cells.values())))
                row=rows[index]
                st.image(page.get_pixmap(matrix=pymupdf.Matrix(2,2),
                    clip=pymupdf.Rect(row.bbox)+(-2,-2,2,2)).tobytes('png'),width='stretch',caption='Original image of the selected row')
                st.caption(row.review_reason+' '+row.date_kind+': '+row.date_evidence)
                st.json({'page':row.page,'table':row.table,'row':row.row,'bbox':row.bbox,'cells':row.cells})
            else:
                st.info('No supported table header was recognized on this page. Successful extraction is not assumed.')
    st.download_button('Download Table Rows & Coordinates (JSON)',json.dumps([asdict(r) for r in result.rows],indent=2),
        'layout_rows.json','application/json')

def render_evidence(result):
    st.subheader('Field Proposals, Missing Information & Conflicts')
    if result.identity_conflict:
        st.warning('Patient identity conflict: combined field proposals were not generated.')
    else:
        st.dataframe([{'field':TEXT_FIELDS[field],'proposed_value':review['value'],
            'source_evidence':', '.join(review['evidence']),'status':review['status']}
            for field,review in result.reviews.items()],hide_index=True,width='stretch')
    st.subheader('Complete Source Evidence')
    st.dataframe([{'evidence_id':f'E{i}',**asdict(f)} for i,f in enumerate(result.facts,1)],
        hide_index=True,width='stretch')
    for warning in result.warnings:st.info(warning)
    st.download_button('Download Evidence (JSON)',json.dumps([asdict(f) for f in result.facts],indent=2),
        'evidence_timeline.json','application/json')

uploads=st.file_uploader('Upload chart history, CBC reports, medication charts and application details for one fictional patient',
    type=['pdf','docx','csv','txt','png','jpg','jpeg'],accept_multiple_files=True)
use_sample=st.checkbox('Load a demo sample',disabled=bool(uploads))
sources=[]
if use_sample and not uploads:
    layout_dir=ROOT/'sample_data'/'public_layouts'
    catalog=json.loads((layout_dir/'catalog.json').read_text())
    identity_samples={
        'Mock identity / CBC PDF':ROOT/'outputs/mock_identity_test/UPLOAD_mock_patient_CBC.pdf',
        'Mock identity / CBC scan':ROOT/'outputs/mock_identity_test/UPLOAD_mock_patient_CBC_scan.png',
        'Mock identity / prescriber on separate pages':ROOT/'outputs/prescriber_recognition_demo/split_prescriber.pdf',
        'Mock identity / separate-page scan':ROOT/'outputs/prescriber_recognition_demo/split_prescriber_scan.pdf',
    }
    identity_samples={label:path for label,path in identity_samples.items() if path.exists()}
    options=list(identity_samples)+['Layout / '+item['file'] for item in catalog]+['Earlier local synthetic ITP demo']
    challenge_dir=ROOT/'outputs/realistic_emr_challenge/records'
    challenge_label='Challenge / mixed EMR packet (7 files)'
    if challenge_dir.exists():options.append(challenge_label)
    new_challenge_dir=ROOT/'outputs/new_emr_sample_02/records'
    new_challenge_label='Challenge / new patient (6 files)'
    if new_challenge_dir.exists():options.append(new_challenge_label)
    simple_dir=ROOT/'outputs/new_emr_sample_04_simple_section1/UPLOAD_ONLY'
    simple_label='Demo / simple Section 1 + clinical packet (6 files)'
    if simple_dir.exists():options.insert(0,simple_label)
    public_dir=ROOT/'sample_data'/'public_external'/'pdfs'
    options += [p.name for p in sorted(public_dir.glob('*.pdf'))]
    selected=st.selectbox('Demo source',options)
    if selected in {challenge_label,new_challenge_label,simple_label}:
        directory={challenge_label:challenge_dir,new_challenge_label:new_challenge_dir,simple_label:simple_dir}[selected]
        sources=[(path.name,path.read_bytes()) for path in sorted(directory.iterdir())
                 if path.suffix.lower() in {'.pdf','.csv'}]
        st.caption('Synthetic development challenge with multiple layouts and clinician roles. Fast prefill handles supported fields; unrecognized details and clinical interpretation still require review.')
    elif selected in identity_samples:
        path=identity_samples[selected]
        sources=[(path.name,path.read_bytes())]
        st.caption('Fictional identity and prescriber details. Recognized values remain reviewable; scan-derived text may contain OCR errors.')
    elif selected=='Earlier local synthetic ITP demo':
        sources=[(name,(ROOT/'sample_data'/name).read_bytes()) for name in ['mock_itp_record.txt','mock_patient_context.txt']]
    elif selected.startswith('Layout / '):
        filename=selected.removeprefix('Layout / ')
        item=next(item for item in catalog if item['file']==filename)
        st.markdown(f"[{item['publisher']} original sample]({item['url']})")
        st.caption(item['status']+' '+item['layout'])
        sources=[(filename,(layout_dir/filename).read_bytes())]
    else:
        sources=[(selected,(public_dir/selected).read_bytes())]
        st.caption('Third-party public synthetic PDF. Different samples concern different patients. Foreign identifiers are not converted to BC PHNs or licence numbers.')
elif uploads:
    seen=set()
    for upload in uploads:
        if upload.name in {'\u4f7f\u7528\u8bf4\u660e.txt','START_HERE.txt'}:
            st.info(f'Skipped instruction file: {upload.name}')
            continue
        if upload.name in seen:
            st.error('Duplicate filenames detected. Rename the files to keep their source evidence distinct.')
            st.stop()
        seen.add(upload.name)
        sources.append((upload.name,upload.getvalue()))

if sources:
    fast_started=time.perf_counter()
    facts=[];warnings=[];rows=[]
    for filename,content in sources:
        extracted,notes,linked=read_source(filename,content,parser_revision)
        facts.extend(extracted);warnings.extend(notes);rows.extend(linked)
    result=assemble_autofill(facts,warnings,rows)
    st.caption(f'Fast text/table extraction: {time.perf_counter()-fast_started:.2f}s. Scan OCR and model inference are not part of this pass.')
    case_key=hashlib.sha256(b''.join(name.encode()+content for name,content in sources)).hexdigest()
    key=case_key[:16]
    accepted_key='accepted_ai_'+case_key
    accepted=st.session_state.get(accepted_key,[])
    if accepted:result=assemble_autofill(facts+accepted,warnings,rows)
    targets=missing_categories(result)
    from src.official_form import DEMOGRAPHIC_MAPPING
    reverse={category:field for field,category in DEMOGRAPHIC_MAPPING.items()}
    reverse.update({'prescriber_name':'Presciber Name and Mailing Address','prescriber_address':'Presciber Name and Mailing Address'})
    edited_fields=set(st.session_state.get(key+'_edited',[]))
    targets=[category for category in targets if reverse[category] not in edited_fields]
    st.caption('Fast prefill is ready. Scans are deferred; no AI is needed for fields already found.')
    has_scans=any('deferred' in warning for warning in warnings)
    if (targets or has_scans) and not result.identity_conflict:
        with st.expander('Optional scans and missing-field review',expanded=False):
            status=ai_status() if targets else {'ready':False,'detail':'No missing identity/clinician fields need AI. Scans can be read separately.'}
            st.caption(status['detail'])
            labels={'patient_family_name':'Patient family name','patient_given_name':'Patient given names',
                'patient_dob':'Birth date','patient_phn':'PHN','prescriber_name':'Applicant clinician',
                'prescriber_address':'Clinician mailing address','prescriber_licence':'College licence',
                'prescriber_phone':'Office telephone','prescriber_fax':'Office fax'}
            selected=st.multiselect('Only check these missing fields',targets,default=targets[:3],
                format_func=lambda c:labels[c],key='targets_'+case_key)
            pending_key='pending_'+case_key
            complete_key='complete_'+case_key
            pending=st.session_state.get(pending_key)
            if pending:
                job=review_jobs().get(pending)
                if job and job['future'].done():
                    try:st.session_state[complete_key]=job['future'].result()
                    except Exception as exc:st.error('Local review failed: '+type(exc).__name__)
                    del st.session_state[pending_key];pending=None
            if st.button('Check selected missing fields in background',disabled=not status.get('ready') or not selected or bool(pending)):
                job_key=hashlib.sha256((case_key+parser_revision+status['model']+repr(selected)).encode()).hexdigest()
                try:
                    review_jobs().start(job_key,sources,rows,status['model'],selected)
                    st.session_state.pop(complete_key,None)
                    st.session_state[pending_key]=job_key
                    pending=job_key
                except RuntimeError as exc:st.info(str(exc))
            if has_scans and st.button('Read deferred scans in background — no AI',disabled=bool(pending)):
                job_key=case_key+'_ocr_'+parser_revision
                try:
                    review_jobs().start(job_key,sources,rows,'ocr-only',[])
                    st.session_state.pop(complete_key,None)
                    st.session_state[pending_key]=job_key;pending=job_key
                except RuntimeError as exc:st.info(str(exc))
            if pending:review_progress(pending)
            semantic=st.session_state.get(complete_key)
            if semantic:
                if not semantic.facts:st.info('No supported suggestions were found. Continue with manual entry or inspect the original files.')
                if semantic.raw.get('mode')=='ocr-only':
                    st.caption('Scan candidates are ready for review. They have not been applied to the form.')
                    if st.button('Add scanned-source candidates to review evidence'):
                        seen={(f.category,f.value,f.date,f.filename,f.location) for f in facts+accepted}
                        extra=[f for f in semantic.facts if (f.category,f.value,f.date,f.filename,f.location) not in seen]
                        st.session_state[accepted_key]=accepted+extra
                        result=assemble_autofill(facts+accepted+extra,warnings+semantic.warnings,rows)
                proposed=assemble_autofill(facts+accepted+semantic.facts,warnings+semantic.warnings,rows)
                st.caption('Review suggestions before applying. Existing entries are never overwritten.')
                chosen=[]
                for field,review in proposed.reviews.items():
                    if field in {'Medication Requested','Dose and Regimen','Date of Application'}:continue
                    value=review['value']
                    current=st.session_state.get(f'{key}_{field}',result.values.get(field,''))
                    if value and value!=current:
                        st.text(TEXT_FIELDS[field]+': '+value)
                        from src.official_form import DEMOGRAPHIC_MAPPING
                        categories={'prescriber_name','prescriber_address'} if field=='Presciber Name and Mailing Address' else {DEMOGRAPHIC_MAPPING[field]}
                        with st.expander('Source evidence for '+TEXT_FIELDS[field]):
                            for fact in semantic.facts:
                                if fact.category in categories:
                                    st.text(fact.filename+' | '+fact.location)
                                    st.text(fact.evidence)
                        if current:st.caption('An existing entry is present; edit it manually if you want to change it.')
                        elif st.checkbox('Use this suggestion',value=field not in st.session_state.get(key+'_edited',[]),key='apply_'+case_key+'_'+field):
                            chosen.append(field)
                if st.button('Apply selected suggestions to empty fields',disabled=not chosen):
                    from src.official_form import DEMOGRAPHIC_MAPPING
                    categories=set()
                    for field in chosen:
                        if not st.session_state.get(f'{key}_{field}'):
                            st.session_state[f'{key}_{field}']=proposed.values[field]
                            if field=='Presciber Name and Mailing Address':categories.update(['prescriber_name','prescriber_address'])
                            else:categories.add(DEMOGRAPHIC_MAPPING[field])
                    added=[f for f in semantic.facts if f.category in categories]
                    st.session_state[accepted_key]=accepted+added
                    result=assemble_autofill(facts+accepted+added,warnings+semantic.warnings,rows)
                for warning in semantic.warnings:st.caption(warning)
    elif not result.identity_conflict:
        st.success('No AI calls are needed for the current identity/clinician entries. Review the draft and enter the requested treatment manually.')
    render_clinical_panel(result,key,case_key,sources,rows)
    facts=result.facts
    documents={name:content for name,content in sources if Path(name).suffix.lower()=='.pdf'}
    st.caption(f'Processed {len(sources)} files · {len(rows)} table row candidates · {len(facts)} evidence items.')
    form_tab,source_tab,evidence_tab=st.tabs(['Auto-filled Application','Original Files & Tables','Field Sources & Review'])
    with form_tab:render_form(result,key)
    with source_tab:render_sources(result,documents)
    with evidence_tab:render_evidence(result)
else:
    st.info('Upload records to see the automatically prefilled official form, or load a public CBC or medication chart sample.')

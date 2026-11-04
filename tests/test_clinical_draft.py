import json,threading,time
from io import BytesIO
from pathlib import Path
import pytest
from pypdf import PdfReader
from src.clinical_draft import validate_selection,generate_clinical_draft,ClinicalDraft
from src.official_form import propose_fields,export_official_draft


def units():
    return [dict(id='C1',filename='letter.pdf',location='page 2',text='Immune thrombocytopenia is the working diagnosis.'),
            dict(id='C2',filename='mar.pdf',location='page 1',text='The repeat infusion was cancelled and was not administered.')]


def test_selected_claims_are_copied_from_sources_not_model_prose():
    raw={'selections':[{'id':'C1','category':'diagnosis','text':'The patient qualifies for funding.'},
                        {'id':'C2','category':'treatment'}, {'id':'MISSING','category':'response'}]}
    d=validate_selection(raw,units())
    assert 'qualifies' not in d.text
    assert 'cancelled and was not administered' not in d.text
    assert 'cancelled and was not administered' in d.facts[1].evidence
    assert len(d.facts)==2 and all(f.value==f.evidence for f in d.facts)
    assert any('rejected' in n for n in d.notes)


def test_long_excerpt_remains_in_evidence_without_silent_shortening():
    u=[{**units()[0],'text':'Immune thrombocytopenia is the diagnosis. '+('word '*600)+'.'}]
    d=validate_selection({'selections':[{'id':'C1','category':'diagnosis'}]},u)
    assert d.text=='' and d.facts[0].evidence==u[0]['text']
    assert any('does not fit' in n for n in d.notes)


def test_section3_draft_exports_without_filling_request_fields():
    d=validate_selection({'selections':[{'id':'C1','category':'diagnosis'},{'id':'C2','category':'treatment'}]},units())
    v=propose_fields(d.facts);v['Supporting Details']=d.text
    f=PdfReader(BytesIO(export_official_draft(v,d.facts))).get_fields()
    assert f['Supporting Details']['/V']==d.text
    assert not f['Medication Requested'].get('/V') and not f['Dose and Regimen'].get('/V')


def test_empty_input_does_not_call_model(monkeypatch):
    import src.clinical_draft as c
    monkeypatch.setattr(c,'_request',lambda *a,**k:pytest.fail('No model call expected'))
    assert not generate_clinical_draft([],[],'test').text


def test_truncated_or_failed_ai_leaves_no_draft(tmp_path,monkeypatch):
    import src.clinical_draft as c
    source=tmp_path/'note.txt';source.write_text('ITP diagnosis and prior treatment.')
    def request(route,*a,**kw):
        if route=='/tokenize':return {'tokens':[1]}
        if route=='/slots':return [{'n_ctx':8192}]
        return {'choices':[{'finish_reason':'length','message':{'content':'{}'}}]}
    monkeypatch.setattr(c,'_request',request)
    d=generate_clinical_draft([source],[],'test')
    assert not d.text and any('failed' in n for n in d.notes)


def test_clinical_and_identity_reviews_share_single_worker(monkeypatch):
    from src.review_jobs import ReviewJobs
    gate=threading.Event()
    monkeypatch.setattr(ReviewJobs,'_run_clinical',lambda *a: (gate.wait(3),ClinicalDraft(text='test'))[1])
    jobs=ReviewJobs()
    try:
        job=jobs.start_clinical('clinical',[],[],'test')
        assert not job['future'].done()
        with pytest.raises(RuntimeError,match='already running'):jobs.start('identity',[],[],'test',['patient_dob'])
        gate.set();assert job['future'].result(2).text=='test'
    finally:gate.set();jobs.pool.shutdown(wait=True)


def test_ui_autofills_section3_and_preserves_later_edits(monkeypatch):
    import src.semantic as semantic
    from src.review_jobs import ReviewJobs
    from streamlit.testing.v1 import AppTest
    monkeypatch.setattr(semantic,'local_status',lambda:{'ready':True,'model':'ui-simulated','detail':'Simulated local AI for UI test'})
    draft=validate_selection({'selections':[{'id':'C1','category':'diagnosis'},{'id':'C2','category':'treatment'}]},units(),'ui-simulated')
    monkeypatch.setattr(ReviewJobs,'_run_clinical',lambda *args:draft)
    at=AppTest.from_file(Path('app.py').resolve(),default_timeout=20).run()
    next(x for x in at.checkbox if x.label=='Load a demo sample').check().run()
    next(x for x in at.selectbox if x.label=='Demo source').select('Earlier local synthetic ITP demo').run()
    next(x for x in at.button if x.label=='Generate & auto-fill Section 3 with local AI').click().run()
    time.sleep(.1);at.run()
    assert not at.exception
    field=next(x for x in at.text_area if x.label.startswith('Supporting details'))
    assert field.value==draft.text
    field.set_value('My manually edited clinical summary.').run()
    next(x for x in at.button if x.label=='Generate & auto-fill Section 3 with local AI').click().run()
    time.sleep(.1);at.run()
    assert next(x for x in at.text_area if x.label.startswith('Supporting details')).value=='My manually edited clinical summary.'
    assert not at.exception


def test_live_model_selection_shape_and_routed_citations(monkeypatch):
    import src.clinical_draft as c
    monkeypatch.setattr(c,'clinical_excerpts',lambda *a:(units(),[]))
    monkeypatch.setattr(c,'routed_context',lambda *a:[{'id':1,'text':units()[0]['text']}])
    def request(route,payload=None,**kw):
        if route=='/tokenize':return {'tokens':[1]}
        if route=='/slots':return [{'n_ctx':8192}]
        return {'choices':[{'finish_reason':'stop','message':{'content':json.dumps({'p':[1,2,0,0,0]})}}]}
    monkeypatch.setattr(c,'_request',request)
    d=c.generate_clinical_draft([],[],'test')
    assert units()[0]['text'] in d.text
    assert units()[1]['text'] not in d.text
    assert any('rejected' in n for n in d.notes)


def test_ai_cannot_turn_no_response_into_a_contraindication():
    u=[{**units()[0],'text':'These changes have not established a durable response.'}]
    d=validate_selection({'selections':[{'id':'C1','category':'contraindication'}]},u)
    assert not d.text and d.items[0]['category']=='uncertainty'
    assert any('withheld' in n for n in d.notes)


def test_ui_recovers_pre_section3_module_after_hot_update(monkeypatch):
    import src.review_jobs as jobs_module
    import src.clinical_draft as clinical
    import src.semantic as semantic
    import streamlit as st
    from streamlit.testing.v1 import AppTest
    class LegacyReviewJobs:
        pass  # Reproduces the old module/class retained by a running server.
    st.cache_resource.clear();st.cache_data.clear()
    monkeypatch.setattr(jobs_module,'ReviewJobs',LegacyReviewJobs)
    monkeypatch.setattr(semantic,'local_status',lambda:{'ready':True,'model':'hot-update-test','detail':'Simulated backend'})
    draft=validate_selection({'selections':[{'id':'C1','category':'diagnosis'}]},units(),'hot-update-test')
    monkeypatch.setattr(clinical,'generate_clinical_draft',lambda *a,**k:draft)
    at=AppTest.from_file(Path('app.py').resolve(),default_timeout=20).run()
    next(x for x in at.checkbox if x.label=='Load a demo sample').check().run()
    next(x for x in at.selectbox if x.label=='Demo source').select('Earlier local synthetic ITP demo').run()
    next(x for x in at.button if x.label=='Generate & auto-fill Section 3 with local AI').click().run()
    time.sleep(.1);at.run()
    assert not at.exception
    assert next(x for x in at.text_area if x.label.startswith('Supporting details')).value==draft.text

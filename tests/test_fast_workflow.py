from pathlib import Path
from io import BytesIO
import json,threading,time
import pytest
from pypdf import PdfReader
from src.models import Fact
from src.autofill import autofill_documents
from src.official_form import propose_fields,export_official_draft,field_reviews
from src.semantic import recognize,missing_categories,SemanticResult

def test_request_mentions_never_autofill_but_clinician_can_enter_them():
    facts=[Fact('requested_drug','Source option','Requires Review','note.txt','line 1','Source option'),
           Fact('requested_regimen','Source regimen','Requires Review','note.txt','line 2','Source regimen')]
    values=propose_fields(facts)
    assert values['Medication Requested']==values['Dose and Regimen']==''
    assert field_reviews(facts)['Medication Requested']['evidence']
    values.update({'Medication Requested':'Clinician confirmed option','Dose and Regimen':'Clinician confirmed regimen'})
    pdf=PdfReader(BytesIO(export_official_draft(values,facts)))
    assert pdf.get_fields()['Medication Requested']['/V']=='Clinician confirmed option'

def test_fast_packet_has_all_identity_fields_without_ocr_or_ai(monkeypatch):
    import src.document_text as text
    import src.semantic as semantic
    def forbidden(*a,**k):raise AssertionError('Fast prefill must not call OCR or the model')
    monkeypatch.setattr(text,'image_text',forbidden);monkeypatch.setattr(semantic,'_request',forbidden)
    monkeypatch.setattr(semantic,'local_status',forbidden)
    root=Path('outputs/new_emr_sample_02/records')
    if not root.exists():pytest.skip('Development fixture not present')
    r=autofill_documents(sorted(root.iterdir()),fast=True,semantic=True)
    assert not r.identity_conflict and not missing_categories(r)
    assert r.values['Patient Given Name']=='Maya Elise'
    assert r.values['Patient Family Name']=='LAURENT-DUBOIS'
    assert r.values['PHN']=='MOCK-PHN-0097'
    assert r.values['Presciber Name and Mailing Address']=='Owen Mercer\n300 Fictional Boulevard, Kelowna BC V0V 0V0'
    assert r.values['Medication Requested']==r.values['Dose and Regimen']==''
    assert any('deferred' in w for w in r.warnings)
    assert 'to it to report' not in r.values['Supporting Details']

def test_no_missing_fields_or_manual_request_targets_never_read_model_input(monkeypatch):
    import src.semantic as semantic
    def forbidden(*a,**k):raise AssertionError('No work should be performed')
    monkeypatch.setattr(semantic,'source_units',forbidden)
    assert not recognize([],[],'test',targets=[]).facts
    assert not recognize([],[],'test',targets=['requested_drug','requested_regimen']).facts

def test_only_selected_missing_category_is_queried(tmp_path,monkeypatch):
    import src.semantic as semantic
    p=tmp_path/'patient.txt';p.write_text('PHN: MOCK-PHN-0789')
    calls=[]
    def request(route,payload=None,**kw):
        if route=='/tokenize':return {'tokens':[1,2]}
        if route=='/slots':return [{'n_ctx':8192}]
        calls.append(payload)
        return {'choices':[{'finish_reason':'stop','message':{'content':json.dumps({'value':'MOCK-PHN-0789','status':'supported','sources':['S1']})}}]}
    monkeypatch.setattr(semantic,'_request',request)
    r=recognize([p],[],'test',targets=['patient_phn'])
    assert len(calls)==1 and len(r.facts)==1
    assert r.facts[0].category=='patient_phn'
    assert 'PHN' in calls[0]['messages'][-1]['content']

def test_background_job_returns_immediately_and_prevents_queued_batches(monkeypatch):
    import src.semantic as semantic
    from src.review_jobs import ReviewJobs
    gate=threading.Event();started=threading.Event()
    def fake(*a,**kw):
        started.set();gate.wait(2)
        return SemanticResult(raw={'facts':[]},model='simulated')
    monkeypatch.setattr(semantic,'recognize',fake)
    jobs=ReviewJobs()
    try:
        t=time.monotonic();job=jobs.start('one',[('source.txt',b'Patient: Example')],[],'test',['patient_phn'])
        assert time.monotonic()-t<1
        assert started.wait(1) and not job['future'].done()
        assert jobs.start('one',[],[],'test',['patient_phn']) is job
        with pytest.raises(RuntimeError,match='already running'):jobs.start('two',[],[],'test',['patient_phn'])
        gate.set();assert job['future'].result(timeout=2).model=='simulated'
    finally:gate.set();jobs.pool.shutdown(wait=True)

def test_registration_column_order_and_middle_name_are_not_fixed():
    from src.fast_fields import table_identity_facts
    from src.layout_tables import LayoutRow
    def row(n,values):return LayoutRow('unmapped_table','table.pdf',1,1,n,
        {str(i):v for i,v in enumerate(values)},[10,10,300,100],' | '.join(values),'geometry',
        'Requires Review','unknown','unknown','unknown','Requires Review')
    rows=[row(1,['Other given','DOB','Surname','First']),row(2,['Louise','1988/03/14','Morgan','Avery'])]
    v=propose_fields(table_identity_facts(rows))
    assert v['Patient Given Name']=='Avery Louise' and v['Patient Family Name']=='Morgan'
    assert v['Date of Birth']=='1988/03/14'

def test_unqualified_staff_name_grid_is_not_patient_registration():
    from src.fast_fields import table_identity_facts
    from src.layout_tables import LayoutRow
    def row(n,a,b):return LayoutRow('unmapped_table','staff.pdf',1,1,n,{'a':a,'b':b},[],a+' '+b,'geometry','','','','','')
    assert not table_identity_facts([row(1,'Family','First'),row(2,'Rowan','Alex')])

def test_application_intent_does_not_resolve_two_signatures_or_a_patient_quote():
    from src.prescriber import prescriber_facts
    text='I will submit the Special Authority application.\nTaylor Finch, MD\nRiley Stone, MD'
    assert not any(f.category=='prescriber_name' for f in prescriber_facts([('page 1',text)],'letter.pdf'))
    text='Patient said: I will submit the Special Authority application.\nTaylor Finch, MD'
    assert not any(f.category=='prescriber_name' for f in prescriber_facts([('page 1',text)],'letter.pdf'))

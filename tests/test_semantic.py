import pytest
from src.semantic import validate_response,local_endpoint,source_units

def item(category,value,quote,**kw):
    return {'category':category,'value':value,'date':'Requires Review','status':'documented',
            'explanation':'Source context association.', 'citations':[{'source':'S1','quote':quote}],**kw}

def test_external_origins_and_embedded_urls_are_rejected():
    for value in ['https://example.com','http://example.com','http://127.0.0.1@evil.test','http://localhost/proxy','http://localhost?url=evil.test']:
        with pytest.raises(ValueError):local_endpoint(value)
    assert local_endpoint('http://127.0.0.1:8081')=='http://127.0.0.1:8081'

def test_nonexistent_quotes_and_invented_values_are_rejected():
    units=[{'id':'S1','filename':'letter.pdf','location':'page 2','text':'Priya Chen, MD. Office 250-555-0134.'}]
    r=validate_response({'facts':[item('prescriber_name','Alex Smith','Alex Smith, MD'),
                                 item('prescriber_phone','250-555-0199','Office 250-555-0134')],'issues':[]},units)
    assert r.facts==[] and len(r.warnings)==2

def test_cross_document_citations_remain_attached():
    units=[{'id':'S1','filename':'letter.pdf','location':'page 2','text':'Priya Chen, MD. I will be the physician applying.'},
           {'id':'S2','filename':'directory.pdf','location':'page 1','text':'Office: 250 Demonstration Avenue'}]
    value=item('prescriber_address','250 Demonstration Avenue','Priya Chen, MD. I will be the physician applying.')
    value['citations'].append({'source':'S2','quote':'Office: 250 Demonstration Avenue'})
    r=validate_response({'facts':[value],'issues':[]},units)
    assert r.facts[0].value=='250 Demonstration Avenue'
    assert 'letter.pdf' in r.facts[0].location and 'directory.pdf' in r.facts[0].location
    assert 'not verified' in r.facts[0].review_reason

def test_discussion_cancelled_historical_and_uncertain_do_not_populate_form():
    from src.official_form import propose_fields
    text='Rituximab 375 mg/m2 was cancelled. Eltrombopag discussed, not selected. Old office 12 Sample Road. Priya Chen, MD.'
    units=[{'id':'S1','filename':'chart.pdf','location':'page 1','text':text}]
    items=[item('medication','Rituximab',text,status='cancelled'),
           item('requested_drug','Eltrombopag',text),
           item('prescriber_address','12 Sample Road',text,status='historical'),
           item('prescriber_name','Priya Chen',text,status='uncertain')]
    r=validate_response({'facts':items,'issues':[]},units)
    assert {f.category for f in r.facts}=={'cancelled_order','clinical_discussion','historical_contact'}
    v=propose_fields(r.facts)
    assert not v['Medication Requested'] and not v['Presciber Name and Mailing Address']

def test_invented_date_is_not_attached_to_real_result():
    units=[{'id':'S1','filename':'cbc.pdf','location':'page 1','text':'Platelet count 18; report date unknown.'}]
    r=validate_response({'facts':[item('platelet_count','18','Platelet count 18; report date unknown.',date='2026/01/01')],'issues':[]},units)
    assert r.facts[0].date=='Requires Review'

def test_source_builder_reads_only_supplied_files_not_answer_key(tmp_path):
    path=tmp_path/'record.txt';path.write_text('This is the uploaded source.')
    (tmp_path/'ANSWER_KEY.json').write_text('SECRET ANSWER NEVER SENT')
    assert source_units([path],[])[0]['text']=='This is the uploaded source.'

def test_application_context_retrieves_roles_without_extracting_field_values():
    from src.semantic import application_context
    text='Unrelated opening\nMore irrelevant text\nOffice correspondence\n250 Sample Street\nAdditional context\nUnrelated tail\nExtra unrelated tail'
    units=[{'id':'S7','filename':'letter.pdf','location':'page 2','text':text}]
    selected=application_context(units)
    assert selected[0]['id']=='S7'
    assert '250 Sample Street' in selected[0]['text']
    assert 'Extra unrelated tail' not in selected[0]['text']
    assert selected[0]['filename']=='letter.pdf'

def test_numeric_name_and_computed_dose_are_not_accepted():
    units=[{'id':'S1','filename':'chart.pdf','location':'page 1','text':'Chart 42. Weight 70 kg. IVIG 70 g administered.'}]
    r=validate_response({'facts':[item('patient_family_name','42','Chart 42.'),
                                 item('dose','1 g/kg','Weight 70 kg. IVIG 70 g administered.')],'issues':[]},units)
    assert r.facts==[]

def test_transport_failure_applies_no_model_candidates(tmp_path,monkeypatch):
    import src.semantic as module
    path=tmp_path/'chart.txt';path.write_text('Patient: Avery Morgan')
    def fail(route,payload=None,**kwargs):
        if route=='/tokenize':return {'tokens':[1,2,3]}
        if route=='/slots':return [{'n_ctx':8192}]
        raise ConnectionError('local service unavailable')
    monkeypatch.setattr(module,'_request',fail)
    r=module.recognize([path],[],'local-test')
    assert not r.facts and not r.raw
    assert 'ConnectionError' in r.warnings[0]

def test_source_id_mode_copies_original_evidence_and_rejects_unknown_ids():
    text='Office address:\n250 Sample Street\nVictoria BC V0V 0V0'
    units=[{'id':'S1','filename':'letter.pdf','location':'page 1','text':text}]
    raw={'facts':[{'category':'prescriber_address','value':'250 Sample Street',
                   'status':'documented','citations':['S1']}],'issues':[]}
    r=validate_response(raw,units,reference_only=True)
    assert r.facts[0].evidence==text
    assert r.raw==raw  # raw model output retained, never overwritten with invented quotes
    raw['facts'][0]['citations']=['S404']
    assert not validate_response(raw,units,reference_only=True).facts

def test_identifier_before_dob_does_not_consume_the_birth_date():
    from src.semantic import _date_supported
    text='Chart DEMO-4721\nDOB 1978-11-23\nPrinted 2026-05-20'
    assert _date_supported('1978/11/23',text)
    assert not _date_supported('2026/11/23',text)

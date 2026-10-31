from pathlib import Path
import pytest
from src.layout_tables import extract_layout_rows,extract_with_layout,layout_facts

DATA=Path('sample_data/public_layouts')

@pytest.mark.parametrize('filename,page,result,unit,reference,date',[
    ('testing_cbc.pdf',1,'180','K/mcL','150-450','02/10/14'),
    ('labcorp_cbc_bundle.pdf',1,'6 Critical','x10E3/uL','150-450','10/22/2024'),
    ('labcorp_cbc_bundle.pdf',3,'308','x10E3/uL','150-450','09/15/2026'),
    ('labcorp_cbc_bundle.pdf',5,'250','x10E3/uL','150-450','09/15/2026'),
])
def test_public_cbc_preserves_result_unit_reference_and_collection_date(filename,page,result,unit,reference,date):
    if not (DATA/filename).exists():pytest.skip('Download public layout fixtures first')
    rows,warnings=extract_layout_rows(DATA/filename)
    assert not warnings
    row=next(r for r in rows if r.page==page and r.cells.get('test','').lower().startswith('platelet'))
    assert (row.cells.get('normal') or row.cells.get('current_result_and_flag'))==result
    assert row.cells['units']==unit
    assert row.cells['reference']==reference
    assert row.event_date==date
    assert row.date_kind=='collection date'
    assert row.bbox[2]>row.bbox[0]

def test_public_medication_chart_preserves_day_and_prn_cells():
    rows,_=extract_layout_rows(DATA/'medication_chart.pdf')
    assert len(rows)==7
    expected={'Aspirin':('100mg PO','mane'),'Clopidogrel':('75mg PO','mane'),
              'Apixaban':('5mg PO','BD'),'Bisoprolol':('5mg PO','mane'),
              'Furosemide':('40mg PO','mane'),'Paracetamol':('1g PO','QID PRN'),
              'Ondansetron':('4mg IV','8-hourly PRN')}
    for row in rows:
        assert (row.cells['dose_route'],row.cells['frequency'])==expected[row.cells['medication']]
    aspirin=next(r for r in rows if r.cells['medication']=='Aspirin')
    assert aspirin.cells['sun']=='AT' and aspirin.cells['mon']==''
    ondansetron=next(r for r in rows if r.cells['medication']=='Ondansetron')
    assert ondansetron.cells['doses_given']=='0'
    assert ondansetron.cells['indication']=='for nausea'
    assert 'not individual administration' in ondansetron.date_kind

def test_public_discharge_table_keeps_full_notes():
    rows,_=extract_layout_rows(DATA/'patient_discharge_history.pdf')
    assert len(rows)==5
    row=next(r for r in rows if r.cells['medication']=='Amoxicillin')
    assert row.cells['dose_route']=='1g PO TDS'
    assert row.cells['notes']=='NEW - 4 days remaining to complete 7-day course'
    assert row.event_date=='10/02/2025'
    assert row.date_kind=='discharge date (not medication start date)'

def test_layout_platelet_result_replaces_flattened_footnote_candidate():
    facts,_,rows=extract_with_layout(DATA/'labcorp_cbc_bundle.pdf')
    values=[f.value for f in facts if f.category=='platelet_count']
    assert values==['6 x10E3/uL','308 x10E3/uL','250 x10E3/uL']
    assert all('bbox' in f.location for f in facts if f.category=='platelet_count')

def test_raster_quest_report_does_not_use_reference_limit_as_result():
    import shutil
    if not shutil.which('tesseract'):pytest.skip('Tesseract not installed')
    rows,_=extract_layout_rows(DATA/'quest_cbc.pdf')
    row=next(r for r in rows if r.cells.get('test','').upper()=='PLATELET COUNT')
    assert row.cells['normal']=='215'
    assert row.cells['reference']=='140-400 Thousand/uL'
    assert row.event_date=='Requires Review'
    assert 'OCR' in row.method
    fact=layout_facts([row])[0]
    assert fact.value=='215 Thousand/uL'
    assert 'reference column' in fact.review_reason

from src.prescriber import prescriber_facts
from src.official_form import propose_fields,field_reviews

FIELD='Presciber Name and Mailing Address'

def test_letterhead_and_signature_on_different_pages_keep_both_sources():
    pages=[('page 1','North Demo Hematology Clinic\n250 Example Avenue\nVictoria BC V0V 0V0\nPatient address: 9 Patient Road'),
           ('page 2','Prescribing physician:\nDr. Taylor Finch, MD\nCPSBC licence: DEMO456')]
    facts=prescriber_facts(pages,'split.pdf')
    assert propose_fields(facts)[FIELD]=='Dr. Taylor Finch\n250 Example Avenue, Victoria BC V0V 0V0'
    addr=next(f for f in facts if f.category=='prescriber_address')
    assert 'page 1' in addr.location and 'page 2' in addr.location
    assert '250 Example Avenue' in addr.evidence and 'Dr. Taylor Finch' in addr.evidence

def test_multiline_explicit_address_does_not_absorb_patient_or_contacts():
    pages=[('page 1','Prescriber: Dr. Riley Stone\nPrescriber mailing address:\n120 Sample Road\nVancouver BC V0V 0V0\nPrescriber phone: 604-555-0123\nPatient address: 80 Other Road')]
    facts=prescriber_facts(pages,'chart.pdf')
    assert propose_fields(facts)[FIELD]=='Dr. Riley Stone\n120 Sample Road, Vancouver BC V0V 0V0'
    assert propose_fields(facts)['Phone Number']=='604-555-0123'

def test_competing_clinician_blocks_prevent_unproven_letterhead_link():
    facts=prescriber_facts([('page 1','Clinic address: 100 Demo Street\nVancouver BC V0V 0V0\nReferring physician: Dr. Alex Rowan\nPrescriber: Dr. Riley Stone\nPatient address: 80 Other Road')],'chart.pdf')
    assert propose_fields(facts)[FIELD]=='Dr. Riley Stone'
    assert not any(f.category=='prescriber_address' for f in facts)

def test_conflicting_clinic_addresses_are_not_selected():
    facts=prescriber_facts([('page 1','Clinic address: 100 Demo Street\nClinic address: 200 Sample Avenue'),
                           ('page 2','Prescriber: Dr. Riley Stone')],'chart.pdf')
    assert propose_fields(facts)[FIELD]==''
    assert 'conflicting' in field_reviews(facts)[FIELD]['status']

def test_author_or_ordering_doctor_is_not_implicitly_prescribing():
    facts=prescriber_facts([('page 1','Demo Clinic\n100 Sample Street\nOrdering physician: Dr. Riley Stone\nAUTHOR\nDr. Alex Rowan')],'chart.pdf')
    assert propose_fields(facts)[FIELD]==''

def test_header_cannot_be_mistaken_for_licence_or_address():
    facts=prescriber_facts([('page 1','Prescriber address:\nCPSBC licence:\nPrescriber phone: 604-555-0123')],'chart.pdf')
    assert not any(f.category in {'prescriber_address','prescriber_licence','prescriber_name'} for f in facts)

def test_patient_phone_is_not_added_after_prescriber_block():
    facts=prescriber_facts([('page 1','Prescriber: Dr. Riley Stone\nPatient: Avery Morgan\nTelephone: 604-555-0188')],'chart.pdf')
    assert not any(f.category=='prescriber_phone' for f in facts)
    facts=prescriber_facts([('page 1','Prescriber: Dr. Riley Stone\nPatient phone: 604-555-0188')],'chart.pdf')
    assert not any(f.category=='prescriber_phone' for f in facts)

def test_visual_row_reconstruction_is_independent_of_pdf_content_order():
    from src.document_text import visual_rows
    # Values were stored column-first, labels second; rows are recovered by y.
    words=[(220,100,310,110,'Dr. Taylor Finch'),(220,130,400,140,'250 Example Avenue'),
           (30,100,100,110,'Prescriber:'),(30,130,120,140,'Prescriber address:')]
    text=visual_rows(words)
    facts=prescriber_facts([('page 1',text)],'table.pdf')
    assert propose_fields(facts)[FIELD]=='Dr. Taylor Finch\n250 Example Avenue'

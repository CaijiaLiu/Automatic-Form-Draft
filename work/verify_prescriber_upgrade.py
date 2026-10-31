from pathlib import Path
from io import BytesIO
import json
from dataclasses import asdict
from reportlab.pdfgen import canvas
import pymupdf
from src.autofill import autofill_documents
from src.official_form import export_official_draft

out=Path('outputs/prescriber_recognition_demo');out.mkdir(parents=True,exist_ok=True)
work=Path('work/prescriber_recognition_demo');work.mkdir(parents=True,exist_ok=True)
c=canvas.Canvas(str(out/'split_prescriber.pdf'),pagesize=(612,792))
def heading(page):
 c.setFont('Helvetica-Bold',11);c.setFillColorRGB(.6,0,0)
 c.drawString(40,758,'SYNTHETIC DEMO - FICTIONAL PATIENT AND CLINIC')
 c.setFillColorRGB(0,0,0);c.setFont('Helvetica',9)
 c.drawString(40,35,f'Mock chart for document recognition testing only | page {page} of 2')
def line(y,text,bold=False):
 c.setFont('Helvetica-Bold' if bold else 'Helvetica',12)
 c.drawString(40,y,text)
heading(1)
for y,t in [(710,'North Demo Hematology Clinic'),(687,'250 Example Avenue'),
            (664,'Victoria BC V0V 0V0'),(631,'Clinic phone: 250-555-0111'),
            (608,'Clinic fax: 250-555-0112'),(540,'PATIENT DETAILS'),
            (513,'Patient Name: Avery Morgan'),(489,'DOB: 1984/02/17'),
            (465,'PHN: MOCK-PHN-0001'),(441,'MRN: DEMO-ITP-001'),
            (395,'Patient address: 90 Fictional Road'),(371,'Patient telephone: 250-555-0199'),
            (310,'TEST SCENARIO'),(283,'The prescribing physician appears on page 2.'),
            (258,'The clinic mailing address is in the letterhead above.'),
            (233,'Patient contact details must not be used as prescriber contacts.')]:line(y,t)
c.showPage();heading(2)
for y,t in [(705,'APPLICATION SUPPORT - DEMOGRAPHICS ONLY'),(666,'Patient Name: Avery Morgan'),
            (642,'DOB: 1984/02/17'),(600,'Application date: 2026/10/30'),
            (530,'No medication request or ITP treatment details are supplied.'),
            (400,'Prescribing physician:'),(373,'Dr. Taylor Finch, MD'),
            (345,'CPSBC licence: DEMO456'),(280,'No signature or consent is provided in this mock record.')]:line(y,t)
c.save()
doc=pymupdf.open(out/'split_prescriber.pdf');scan=pymupdf.open()
for i,page in enumerate(doc):
 pix=page.get_pixmap(matrix=pymupdf.Matrix(3,3),alpha=False)
 scan.new_page(width=612,height=792).insert_image(pymupdf.Rect(0,0,612,792),stream=pix.tobytes('png'))
 page.get_pixmap(matrix=pymupdf.Matrix(1.15,1.15)).save(work/f'page_{i+1}.png')
scan.save(out/'split_prescriber_scan.pdf')

expected={
 'Patient Family Name':'Morgan','Patient Given Name':'Avery','Date of Birth':'1984/02/17',
 'PHN':'MOCK-PHN-0001','Presciber Name and Mailing Address':
 'Dr. Taylor Finch\n250 Example Avenue, Victoria BC V0V 0V0',
 'CPSBC or CRNBC Number':'DEMO456','Phone Number':'250-555-0111',
 'Fax Number':'250-555-0112','Date of Application':'2026/10/30',
 'Medication Requested':'','Dose and Regimen':''}
old=Path('outputs/mock_identity_test')
original_expected=json.loads((old/'EXPECTED_FIELDS.json').read_text())
results=[]
for path,key in [(old/'UPLOAD_mock_patient_CBC.pdf',original_expected),
                 (old/'UPLOAD_mock_patient_CBC_scan.png',original_expected),
                 (out/'split_prescriber.pdf',expected),(out/'split_prescriber_scan.pdf',expected)]:
 r=autofill_documents([path])
 checks={k:{'expected':v,'observed':r.values.get(k,''),'match':r.values.get(k,'')==v} for k,v in key.items()}
 results.append({'file':path.name,'identity_conflict':r.identity_conflict,'checks':checks,
                 'warnings':r.warnings,'prescriber_evidence':[asdict(f) for f in r.facts if f.category.startswith('prescriber_')]})
 print(path.name,sum(c['match'] for c in checks.values()),'/',len(checks),flush=True)
 for k,v in checks.items():
  if not v['match']:print(k,v,flush=True)
 if path.name=='split_prescriber_scan.pdf':
  (out/'autofilled_5328_from_scan.pdf').write_bytes(export_official_draft(r.values,r.facts))
  rd=pymupdf.open(out/'autofilled_5328_from_scan.pdf')
  rd[0].get_pixmap(matrix=pymupdf.Matrix(1.2,1.2)).save(work/'form_preview.png')
(out/'verification.json').write_text(json.dumps(results,indent=2))
(out/'EXPECTED_FIELDS.json').write_text(json.dumps(expected,indent=2))
assert all(c['match'] for r in results for c in r['checks'].values())
assert all(not r['identity_conflict'] for r in results)
print('All four controlled examples matched all 9 nonempty form values; 2 missing request fields stayed blank.')

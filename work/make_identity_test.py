from pathlib import Path
import json
from io import BytesIO
import pymupdf
from reportlab.pdfgen import canvas
from reportlab.lib import colors
from reportlab.lib.utils import ImageReader
from src.official_form import export_official_draft
from src.autofill import autofill_documents

OUT=Path('outputs/mock_identity_test'); OUT.mkdir(parents=True,exist_ok=True)
WORK=Path('work/mock_identity_test'); WORK.mkdir(parents=True,exist_ok=True)
expected={
 'Patient Family Name':'Morgan',
 'Patient Given Name':'Avery',
 'Date of Birth':'1984/02/17',
 'PHN':'MOCK-PHN-0001',
 'Presciber Name and Mailing Address':'Dr. Jamie Bennett\n100 Example Street, Vancouver BC V0V 0V0',
 'CPSBC or CRNBC Number':'DEMO123',
 'Phone Number':'604-555-0106',
 'Fax Number':'604-555-0107',
 'Date of Application':'2026/10/30',
 'Medication Requested':'',
 'Dose and Regimen':'',
}
(OUT/'EXPECTED_FIELDS.json').write_text(json.dumps(expected,indent=2))
source=pymupdf.open('outputs/canadian_public_samples/bc_powerchart_fundamentals.pdf')
pix=source[40].get_pixmap(matrix=pymupdf.Matrix(5,5),clip=pymupdf.Rect(90,75.8488,594,204.0489))
crop=WORK/'cbc_original_table.png';pix.save(crop)

path=OUT/'UPLOAD_mock_patient_CBC.pdf'
c=canvas.Canvas(str(path),pagesize=(612,792))
c.setTitle('Mock patient identity test - Canadian EMR training layout')
c.setFillColor(colors.HexColor('#173650'));c.rect(30,722,552,40,fill=1,stroke=0)
c.setFillColor(colors.white);c.setFont('Helvetica-Bold',15)
c.drawString(42,740,'DEMO CLINIC | PATIENT CHART EXTRACT')
c.setFillColor(colors.darkred);c.setFont('Helvetica-Bold',10)
c.drawString(30,704,'SYNTHETIC IDENTITY - MOCK RECORD - NOT FOR CLINICAL USE')

def section(title,y):
 c.setFillColor(colors.HexColor('#e7edf3'));c.rect(30,y-7,552,24,fill=1,stroke=0)
 c.setFillColor(colors.HexColor('#173650'));c.setFont('Helvetica-Bold',11);c.drawString(40,y,title)

def row(label,value,y):
 c.setStrokeColor(colors.HexColor('#c5cdd5'));c.rect(30,y-7,552,27,stroke=1,fill=0)
 c.line(204,y-7,204,y+20)
 c.setFillColor(colors.black);c.setFont('Helvetica',10);c.drawString(40,y+3,label+':')
 c.setFont('Helvetica-Bold',10);c.drawString(214,y+3,value)

section('PATIENT DEMOGRAPHICS',674)
for i,(lab,val) in enumerate([
 ('Patient Name','Avery Morgan'),('DOB','1984/02/17'),
 ('PHN','MOCK-PHN-0001'),('MRN','DEMO-ITP-001'),('Sex','Female')]):
 row(lab,val,643-i*27)

section('PRESCRIBER DETAILS',493)
for i,(lab,val) in enumerate([
 ('Prescriber','Dr. Jamie Bennett'),
 ('Prescriber address','100 Example Street, Vancouver BC V0V 0V0'),
 ('CPSBC licence','DEMO123'),('Prescriber phone','604-555-0106'),
 ('Prescriber fax','604-555-0107'),('Application date','2026/10/30')]):
 row(lab,val,462-i*27)

section('CBC RESULTS | ORIGINAL CANADIAN TRAINING TABLE',285)
c.drawImage(ImageReader(str(crop)),30,118,width=552,height=140.41)
c.setFont('Helvetica',8);c.setFillColor(colors.HexColor('#444444'))
for i,t in enumerate([
 'Source: BC CST Cerner PowerChart Fundamentals, original PDF page 41.',
 'Training table layout and values are unchanged. The mock identity panel above was added locally.',
 'This is an identity-extraction fixture, not an actual EMR export or a coherent clinical ITP case.',
 'All identity/contact values above are fictional. PHN and licence are deliberate demo identifiers.',
 'No requested drug, regimen, diagnosis, signature or consent is supplied by this record.'
]):c.drawString(30,94-i*11,t)
c.save()

# Independent answer key: manually specified values, never derived from extraction.
reference={**expected,'Supporting Details':'Synthetic identity extraction test only. CBC training table is a separate published layout example. No ITP diagnosis, requested drug or regimen is documented. Requires Review.'}
(OUT/'REFERENCE_ONLY_official_5328.pdf').write_bytes(export_official_draft(reference,[],reviewed=False))

doc=pymupdf.open(path)
doc[0].get_pixmap(matrix=pymupdf.Matrix(3,3)).save(OUT/'UPLOAD_mock_patient_CBC_scan.png')
doc[0].get_pixmap(matrix=pymupdf.Matrix(1.25,1.25)).save(WORK/'source_preview.png')
ref=pymupdf.open(OUT/'REFERENCE_ONLY_official_5328.pdf')
ref[0].get_pixmap(matrix=pymupdf.Matrix(1.3,1.3)).save(WORK/'official_preview.png')

results=[]
for filename in ['UPLOAD_mock_patient_CBC.pdf','UPLOAD_mock_patient_CBC_scan.png']:
 result=autofill_documents([OUT/filename])
 checks={k:{'expected':v,'observed':result.values.get(k,''),'match':result.values.get(k,'')==v} for k,v in expected.items()}
 results.append({'file':filename,'identity_conflict':result.identity_conflict,'checks':checks,'warnings':result.warnings})
 print(filename, sum(x['match'] for x in checks.values()),'/',len(checks),flush=True)
 for k,v in checks.items():
  if not v['match']:print(k,v,flush=True)
(OUT/'OBSERVED_EXTRACTION.json').write_text(json.dumps(results,indent=2))

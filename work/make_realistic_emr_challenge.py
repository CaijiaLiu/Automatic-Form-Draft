"""Generate a fixed-answer, multi-layout synthetic chart; never tune the extractor."""
from pathlib import Path
from hashlib import sha256
from xml.sax.saxutils import escape
import csv,json
from reportlab.platypus import SimpleDocTemplate,Paragraph,Spacer,Table,TableStyle,PageBreak
from reportlab.lib.styles import getSampleStyleSheet,ParagraphStyle
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter,landscape
import pymupdf

ROOT=Path('outputs/realistic_emr_challenge'); REC=ROOT/'records';REV=ROOT/'review'
WORK=Path('work/realistic_emr_challenge')
for d in [REC,REV,WORK]:d.mkdir(parents=True,exist_ok=True)

# Written before document creation/extraction. This is the independent answer key.
KEY={
 'scope':'Controlled synthetic development challenge, not independent validation or clinical guidance.',
 'form_fields':{
  'Patient Family Name':'Park','Patient Given Name':'Evelyn Mei','Date of Birth':'1978/11/23',
  'PHN':'MOCK-PHN-0042','Presciber Name and Mailing Address':
  'Dr. Priya Chen\n250 Demonstration Avenue, Victoria BC V0V 0V0',
  'CPSBC or CRNBC Number':'DEMO042','Phone Number':'250-555-0134','Fax Number':'250-555-0135',
  'Medication Requested':'','Dose and Regimen':''},
 'application_date':'Not documented. An editable draft-creation date is allowed, not a historical encounter date.',
 'identity':{'MRN':'DEMO-4721','patient_address':'88 Fictional Road, Nanaimo BC V0V 0V0'},
 'platelet_events':[
  {'collected':'2026-01-08','specimen':'D26-0108','final_value':14,'unit':'10^9/L','source':'02, page 1 / PLT row'},
  {'collected':'2026-01-15','specimen':'D26-0115','final_value':78,'unit':'10^9/L','source':'02, page 1 / PLT row'},
  {'collected':'2026-02-12','specimen':'D26-0212','final_value':17,'unit':'10^9/L','source':'02, page 1 / PLT row'},
  {'collected':'2026-02-19','specimen':'D26-0219','final_value':103,'unit':'10^9/L','source':'02, page 1 / PLT row'},
  {'collected':'2026-03-05','specimen':'D26-0305','final_value':21,'unit':'10^9/L','source':'02, page 1 / PLT row'},
  {'collected':'2026-05-14','specimen':'D26-0514','final_value':18,'unit':'10^9/L','superseded_value':22,
   'source':'02 preliminary column, superseded by 06 amended final report and 07 CSV'}],
 'clinical_events':[
  {'event':'ITP assessment','value':'Immune thrombocytopenia is the working diagnosis; secondary causes still under review.', 'source':'04, page 1 / assessment prose'},
  {'event':'Prednisone exposure','value':'60 mg PO daily started 2026-01-09; then 40 mg PO daily from 2026-01-19 and 20 mg PO daily from 2026-01-26. Exact discontinuation date unknown.', 'source':'03, page 1 / medication reconciliation'},
  {'event':'IVIG course','value':'70 g IV on each of 2026-02-13 and 2026-02-14; both administrations recorded complete, one two-day course.', 'source':'03 / administration table'},
  {'event':'Response','value':'Platelet rise then fall during steroid taper; temporary post-IVIG rise. No durable response established.', 'source':'04, page 1 / longitudinal prose'},
  {'event':'Drug request','value':'No agent or regimen selected. Eltrombopag and romiplostim are discussion options only.', 'source':'04, page 2 / plan'}],
 'must_not_infer':[
  'Rituximab was proposed, cancelled, and not administered; never list it as a completed prior therapy.',
  'Report/print/fax/expiry dates are not collection or administration dates.',
  'CBC reference-range limits, lab footnote 01, and previous-result cells are not current platelet results.',
  'The final 18 replaces preliminary 22 for the same specimen; do not treat them as two independent encounters.',
  'A clotted/cancelled specimen has no numeric result; it is not a platelet count of zero.',
  'Dr. Noah Reed is the referral recipient; Dr. Alex Wong is the discharge author; neither is the applicant.',
  'The legacy order lists an old clinic address/fax. Use the current address/contact linked to the 2026-05-20 letter, or flag unresolved association.',
  'Do not copy patient address/phone into prescriber fields.',
  'A patient-reported stop interval does not establish an exact medication stop date.',
  'No prescriber signature, consent or payer eligibility is established.'],
 'layout_provenance':[
  'Newly authored mock documents, not copied hospital exports and not official forms.',
  'Cumulative results/MAR layout conventions informed by public BC CST Cerner training PDFs.',
  'Problem/history/medication-summary sections informed by public Healthquest Alberta summary example.',
  'No real patient, clinician, clinic or valid provincial identifier is intended.']}
keybytes=json.dumps(KEY,indent=2).encode();(REV/'ANSWER_KEY.json').write_bytes(keybytes)
(REV/'ANSWER_KEY.sha256').write_text(sha256(keybytes).hexdigest()+'  ANSWER_KEY.json\n')

S=getSampleStyleSheet()
S.add(ParagraphStyle(name='SmallCell',fontName='Helvetica',fontSize=8,leading=10))
S.add(ParagraphStyle(name='BodyCompact',fontName='Helvetica',fontSize=10,leading=14,spaceAfter=9))
S.add(ParagraphStyle(name='Tiny',fontName='Helvetica',fontSize=7,leading=9))
BLUE=colors.HexColor('#203f59');GREY=colors.HexColor('#e9eef2')

def p(text,style='BodyCompact'):
 return Paragraph(escape(str(text)).replace('\n','<br/>'),S[style])

def table(rows,widths,header=True,font=8):
 data=[[p(c,'SmallCell') for c in row] for row in rows]
 t=Table(data,colWidths=widths,repeatRows=1 if header else 0,hAlign='LEFT')
 commands=[('GRID',(0,0),(-1,-1),.35,colors.HexColor('#a3adb5')),
           ('VALIGN',(0,0),(-1,-1),'TOP'),('LEFTPADDING',(0,0),(-1,-1),6),
           ('TOPPADDING',(0,0),(-1,-1),6),('BOTTOMPADDING',(0,0),(-1,-1),6)]
 if header:commands += [('BACKGROUND',(0,0),(-1,0),GREY)]
 t.setStyle(TableStyle(commands));return t

def footer(c,d):
 w,h=d.pagesize;c.saveState();c.setFillColor(colors.darkred);c.setFont('Helvetica-Bold',8)
 c.drawString(32,h-22,'SYNTHETIC MOCK - SOFTWARE TESTING ONLY - NOT FOR CLINICAL USE')
 c.setFillColor(colors.grey);c.setFont('Helvetica',7)
 c.drawString(32,19,f'DEMO-4721 | Fictional Canadian-style record | {d.page}')
 c.restoreState()

def save(name,story,size=letter,folder=REC):
 doc=SimpleDocTemplate(str(folder/name),pagesize=size,leftMargin=32,rightMargin=32,
                      topMargin=42,bottomMargin=34,title='Synthetic EMR challenge: '+name)
 doc.build(story,onFirstPage=footer,onLaterPages=footer)

def h(title):return [p(title,'Title'),Spacer(1,8)]

# 01: two-column demographic/provider snapshot, with wrapped cells and multiple clinicians.
save('01_chart_snapshot.pdf',h('Chart snapshot / longitudinal problem list')+[
 p('Ridge Demonstration Health Network  |  Community hematology  |  Snapshot printed 21 May 2026','Tiny'),
 table([['Demographics / registration','Care team / administrative routing'],
 ['Legal surname\nPARK\nGiven name(s)\nEvelyn Mei\nBirth date 23 Nov 1978\nChart DEMO-4721\nPersonal Health Number MOCK-PHN-0042',
  'Responsible consultant\nPriya Chen, MD FRCPC\nCommunity referral\nNoah Reed, MD\nRecent discharge author\nAlex Wong, MD'],
 ['Residential / correspondence\n88 Fictional Road\nNanaimo BC V0V 0V0\nMobile 250-555-0198',
  'Office directory\nRidge Demonstration Hematology\n250 Demonstration Avenue\nVictoria BC V0V 0V0\n250-555-0134 / fax 250-555-0135']],[274,274]),Spacer(1,14),
 table([['Active problem','First recorded','Status / context'],
 ['Thrombocytopenia, immune mechanism under assessment','08 Jan 2026','Hematology follow-up; consultant correspondence filed separately.'],
 ['Insomnia during corticosteroid exposure','22 Jan 2026','Patient reported. Attribution and severity not established.']],[200,100,248]),Spacer(1,14),
 p('Alerts and reconciliation','Heading2'),
 p('Allergy reconciliation not completed at this visit. Pharmacy reconciliation last completed 19 February. Historical orders remain visible in the longitudinal list.')])

# 02: horizontal date columns; preliminary result; units and reference limits distinct.
dates=['08-Jan','15-Jan','12-Feb','19-Feb','05-Mar','14-May*']
rows=[['Analyte / unit','Reference']+dates,
 ['WBC (10^9/L)','4.0-11.0','6.2','11.4 H','8.3','6.8','6.1','6.0'],
 ['RBC (10^12/L)','3.8-5.2','4.22','4.18','4.25','4.19','4.21','4.20'],
 ['Hgb (g/L)','120-160','126','125','127','126','125','128'],
 ['Hct (L/L)','0.36-0.46','0.38','0.37','0.38','0.38','0.37','0.39'],
 ['MCV (fL)','80-100','90','89','90','91','88','93'],
 ['PLT (10^9/L)','150-400','14 L','78 L','17 L','103 L','21 L','22 L*'],
 ['Neutrophils (10^9/L)','2.0-7.5','3.7','9.0 H','5.8','4.2','3.8','3.5'],
 ['Lab annotation','--','01','01','01','01','01','PRELIM']]
save('02_cumulative_CBC.pdf',h('Laboratory cumulative results')+[
 table([['Patient / specimen context','Report parameters'],
 ['Park, Evelyn Mei | DEMO-4721\nDOB 1978-11-23 | PHN MOCK-PHN-0042',
  'Facility: DEMONSTRATION LAB ONLY\nPrinted 2026-05-20 16:40 | all columns are 2026 collection dates']],[364,364]),Spacer(1,14),
 table(rows,[170,90]+[78]*6),Spacer(1,12),
 p('* 14-May column was preliminary at the time this cumulative view was captured. The amended final result is transmitted separately. Laboratory suffix 01 identifies the reporting bench; it is not a result.'),
 table([['Collection date','Specimen accession','Status'],
 ['2026-01-08 / 2026-01-15','D26-0108 / D26-0115','Final'],
 ['2026-02-12 / 2026-02-19','D26-0212 / D26-0219','Final'],
 ['2026-03-05 / 2026-05-14','D26-0305 / D26-0514','Final / preliminary'],
 ['2026-05-13','D26-0513','Cancelled - specimen clotted; no PLT reported']],[180,220,328])],landscape(letter))

# 03: reconciliation, actual administrations, and cancelled proposal in separate tables.
save('03_medication_reconciliation_MAR.pdf',h('Medication reconciliation + administration extract')+[
 p('DEMO-4721 | Evelyn Mei Park | birth 23 Nov 1978 | reconciliation completed 19-Feb-2026'),
 table([['Medication / formulation','Directions / route','Effective interval','Reconciliation state'],
 ['Prednisone 20 mg tablets','60 mg PO each morning','09-Jan to 18-Jan-2026','Prior regimen; not the current home dose'],
 ['Prednisone 20 mg tablets','40 mg PO each morning','19-Jan to 25-Jan-2026','Taper step completed'],
 ['Prednisone 5 mg tablets','20 mg PO each morning','From 26-Jan-2026','Not taking at later review; exact final dose date not verified'],
 ['Cholecalciferol','1,000 units PO daily','Historical home list','Not an ITP-directed treatment']],[185,150,160,233]),Spacer(1,15),
 p('Infusion administration history','Heading2'),
 table([['Product / ordered amount','13-Feb 2026','14-Feb 2026','Documentation'],
 ['Immune globulin, IV\n70 g per administration','09:15 started\n14:05 COMPLETE','09:05 started\n13:50 COMPLETE','Weight 70 kg on order. Course 1, day 1 / day 2. Infusion nursing documentation complete.'],
 ['Rituximab proposal\n375 mg/m2','--','--','Order CANCELLED before release. NOT GIVEN. No administration recorded.']],[220,130,130,248]),Spacer(1,12),
 p('IVIG product lot DEMO-IG-26; expiry 2027-04-30. Pre-infusion observations reviewed. No infusion reaction documented in this extract. Reconciliation source: community pharmacy and patient interview.')],landscape(letter))

# 04: prose reasoning, role resolution from signature, historic-address distractor.
save('04_hematology_followup_letter.pdf',h('Ridge Demonstration Hematology')+[
 p('250 Demonstration Avenue, Victoria BC V0V 0V0\nOffice 250-555-0134  |  Facsimile 250-555-0135'),
 p('20 May 2026\nPrivate correspondence - synthetic training record'),
 table([['To','Re'],['Dr. Noah Reed\nCommunity primary care','Evelyn Mei Park\nDEMO-4721 / born 23 November 1978']],[230,318]),Spacer(1,13),
 p('Thank you for asking me to reassess Ms Park. Immune thrombocytopenia remains the working diagnosis; the review for secondary causes is ongoing. The referral initially used “rule out marrow disorder”, which is not a confirmed second diagnosis.'),
 p('On the initial count of fourteen she was started on oral corticosteroid treatment. The count rose to seventy-eight the following week, then fell to seventeen while the dose was being reduced. She describes substantial sleep disturbance, but a causal adverse-event grade has not been assigned. Her tablet strengths and taper directions are set out in the separate reconciliation sheet.'),
 p('Following the two-day immunoglobulin course, the next count was 103 and the subsequent count was 21. The benefit was short-lived. She recalls stopping the steroid near the end of February or the beginning of March; I cannot supply an exact stop date.'),
 p('The May cumulative view still shows 22. The laboratory has since amended that same specimen to 18; these are not separate visits. No numerical result is available for the clotted specimen on the preceding day.'),
 PageBreak(),p('Follow-up letter / continued','Heading1'),
 p('Evelyn Mei Park | DEMO-4721 | 20 May 2026','Tiny'),Spacer(1,12),
 p('We discussed eltrombopag and romiplostim as possible next options. Neither has been selected or prescribed. Rituximab appears in a cancelled proposal in the infusion module, not in her completed treatment history. A treatment decision is deferred pending review with the patient.'),
 p('I will be the physician applying for Special Authority once the next agent and regimen have been agreed with the patient. Please route the draft for my review at the practice address on the first page of this letter. The old Cedar Demonstration Road address remains on a legacy order and is no longer our mailing address.'),
 Spacer(1,25),p('Priya Chen, MD FRCPC\nHematology\nCPSBC registration: DEMO042'),
 p('Copy: Dr. Noah Reed. This unsigned mock letter does not provide patient consent or an authenticated clinician signature.','Tiny')])

# 05: different author/recipient, inpatient discharge format and stale data.
save('05_discharge_and_legacy_order.pdf',h('Discharge communication / legacy attachment')+[
 table([['Routing','Encounter'],
 ['FROM Alex Wong, MD (discharge author)\nTO Dr. Noah Reed (community follow-up)',
  'Evelyn Mei Park / DEMO-4721\nAdmitted 13-Feb-2026; discharged 15-Feb-2026\nDOB 1978/11/23']],[274,274]),Spacer(1,13),
 p('Brief course','Heading2'),
 p('Observed during the two scheduled immunoglobulin administrations. Infusions were completed according to the attached MAR. CBC follow-up arranged through community hematology. No operative intervention is documented in this mock admission.'),
 table([['Discharge list item','Instruction','Comment'],
 ['Prednisone','Continue taper from existing specialist plan','Taper schedule per community hematology; stop date not confirmed.'],
 ['Cholecalciferol','Continue home directions','Not the drug under consideration for access.']],[140,200,208]),Spacer(1,18),
 p('Legacy order header / archived 09-Jan-2026','Heading2'),
 table([['Ordering physician','Historic office details'],
 ['Priya Chen, MD\nCollege reference DEMO042','12 Cedar Demonstration Road\nVictoria BC V0V 0V0\nFax 250-555-0109\nARCHIVED CONTACT - NOT CURRENT']],[220,328]),Spacer(1,10),
 p('Archived order attached for continuity. Current practice correspondence is filed in the later specialist letter.')])

# 06: standalone amended laboratory report, rasterized to force OCR.
save('amended_native.pdf',h('DEMONSTRATION LAB / amended final report')+[
 table([['Patient','Specimen'],['PARK, Evelyn Mei\nDEMO-4721 | DOB 23 Nov 1978\nPHN MOCK-PHN-0042',
 'Accession D26-0514\nCollected 14-May-2026 08:20\nAmended 15-May-2026 11:05']],[274,274]),Spacer(1,18),
 table([['Investigation','Final value','Flag','Units','Reference interval'],
 ['Platelet count','18','LOW','10^9/L','150-400'],['Previous preliminary value','22','SUPERSEDED','10^9/L','Not an additional specimen']],[155,75,90,70,158]),Spacer(1,14),
 p('AMENDMENT: the platelet result of 22 released as preliminary for accession D26-0514 is withdrawn and replaced by 18. The amendment followed repeat assessment of the original specimen. Ordering service notified; amended report replaces the preliminary release.'),
 p('Sent by demonstration fax gateway 16-May-2026 09:42. Ordering service: Community Hematology. Report identifier D26-0514-A1. No medicine or dose is requested on this laboratory document.')],folder=WORK)
native=pymupdf.open(WORK/'amended_native.pdf'); scanned=pymupdf.open()
for page in native:
 pix=page.get_pixmap(matrix=pymupdf.Matrix(2,2),colorspace=pymupdf.csGRAY,alpha=False)
 scanned.new_page(width=612,height=792).insert_image(pymupdf.Rect(0,0,612,792),stream=pix.tobytes('png'))
scanned.save(REC/'06_amended_result_scan.pdf')

with (REC/'07_lab_history_export.csv').open('w',newline='') as f:
 writer=csv.writer(f);writer.writerow(['chart_id','specimen_accession','collection_timestamp','reported_timestamp','test_code','result','unit','result_status','replaces_result'])
 for date,spec,val in [('2026-01-08','D26-0108',14),('2026-01-15','D26-0115',78),('2026-02-12','D26-0212',17),('2026-02-19','D26-0219',103),('2026-03-05','D26-0305',21)]:
  writer.writerow(['DEMO-4721',spec,date+'T08:20',date+'T11:10','PLT',val,'10^9/L','FINAL',''])
 writer.writerow(['DEMO-4721','D26-0513','2026-05-13T08:10','2026-05-13T09:30','PLT','','10^9/L','CANCELLED_CLOTTED',''])
 writer.writerow(['DEMO-4721','D26-0514','2026-05-14T08:20','2026-05-14T10:30','PLT',22,'10^9/L','PRELIMINARY',''])
 writer.writerow(['DEMO-4721','D26-0514','2026-05-14T08:20','2026-05-15T11:05','PLT',18,'10^9/L','AMENDED_FINAL',22])

manifest=[]
for path in sorted(REC.iterdir()):
 entry={'file':path.name,'sha256':sha256(path.read_bytes()).hexdigest()}
 if path.suffix=='.pdf':
  doc=pymupdf.open(path);entry['pages']=len(doc)
  for i,page in enumerate(doc):page.get_pixmap(matrix=pymupdf.Matrix(1.2,1.2)).save(WORK/(path.stem+f'_{i+1}.png'))
 manifest.append(entry)
(REV/'SOURCE_MANIFEST.json').write_text(json.dumps(manifest,indent=2))
assert sha256((REV/'ANSWER_KEY.json').read_bytes()).hexdigest()==sha256(keybytes).hexdigest()
print('Created 6 PDFs (7 pages), one CSV; answer key frozen before document creation.')

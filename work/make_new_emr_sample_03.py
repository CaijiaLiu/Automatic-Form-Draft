"""Fresh synthetic holdout fixture. Does not import or run the application parser."""
from pathlib import Path
from hashlib import sha256
from xml.sax.saxutils import escape
import json,csv
from reportlab.platypus import SimpleDocTemplate,Paragraph,Spacer,Table,TableStyle,PageBreak
from reportlab.lib.styles import getSampleStyleSheet,ParagraphStyle
from reportlab.lib.pagesizes import letter,landscape
from reportlab.lib import colors
import pymupdf
from PIL import Image,ImageDraw

ROOT=Path('outputs/new_emr_sample_03');REC=ROOT/'records';REV=ROOT/'review';WORK=Path('work/new_emr_sample_03')
for folder in (REC,REV,WORK):folder.mkdir(parents=True,exist_ok=True)
KEY={'patient':{'family':'Bennett','given':'Daniel Aaron','dob':'1983/04/18','PHN':'MOCK-PHN-0136','MRN':'DEMO-6248'},
 'form_fields':{'Patient Family Name':'Bennett','Patient Given Name':'Daniel Aaron',
 'Date of Birth':'1983/04/18','PHN':'MOCK-PHN-0136',
 'Presciber Name and Mailing Address':'Dr. Sophia Grant\n420 Sample Avenue, Victoria BC V0V 0V0',
 'CPSBC or CRNBC Number':'DEMO136','Phone Number':'250-555-0162','Fax Number':'250-555-0163',
 'Medication Requested':'eltrombopag','Dose and Regimen':'25 mg orally once daily'},
 'application_date':'Not explicitly documented. Draft creation date is allowed; 27 October is a letter/encounter date.',
 'clinical_events':[
 {'date':'2026-08-04','event':'PLT','value':11,'unit':'10^9/L','specimen':'H26-804'},
 {'date':'2026-08-05 through 2026-08-08','event':'Dexamethasone','value':'40 mg PO daily; four administrations documented'},
 {'date':'2026-08-12','event':'PLT','value':64,'unit':'10^9/L','specimen':'H26-812'},
 {'date':'2026-09-02','event':'PLT','value':15,'unit':'10^9/L','specimen':'H26-902'},
 {'date':'2026-09-03 and 2026-09-04','event':'IVIG','value':'60 g IV each day; both complete, one two-day course'},
 {'date':'2026-09-08','event':'PLT','value':91,'unit':'10^9/L','specimen':'H26-908'},
 {'date':'2026-10-20','event':'PLT','value':13,'unit':'10^9/L','specimen':'H26-1020','status':'EDTA specimen with clumping; source says count unreliable'},
 {'date':'2026-10-21','event':'PLT','value':21,'unit':'10^9/L','specimen':'C26-1021','status':'New sodium citrate specimen; final lab-reported value. Not an amendment of H26-1020.'}],
 'interpretation':{'diagnosis':'ITP remains the treating hematologist\'s working diagnosis; secondary-cause work-up not declared complete.',
 'response':'Transient rises followed by recurrent thrombocytopenia; no durable response established.',
 'requested_not_administered':'Eltrombopag is selected for this request but has not been started.',
 'discussed_not_used':'Rituximab and mycophenolate discussed as alternatives only.'},
 'source_map':{'patient identity':'01 p1 table; 04 p1; 05 p1',
 'applicant role':'04 p2 first-person application plan and clinician sign-off',
 'current address':'04 p1 letterhead; supersedes archived address on 01',
 'licence_phone_fax':'04 p2 footer',
 'requested_drug_regimen':'04 p2 narrative plan, not a labelled application-field list',
 'platelets':'02 p1 and 05 p1; 06 CSV',
 'actual administrations':'03 p1'},
 'do_not_infer':['Do not substitute family physician Ethan Wells or acute-care author Amelia Ross for Sophia Grant.',
 'Do not use residential address/phone, emergency contact, or archived Nanaimo office contact as applicant contact.',
 'H26-1020 and C26-1021 are distinct specimens/dates, not preliminary/final releases of one sample.',
 'Do not calculate a citrate correction or replace the reported 21 with a derived number.',
 'Tablet strength is 4 mg; total dexamethasone dose is 40 mg. Do not use the tablet strength as daily dose.',
 'Selected access request is not evidence that the patient received or responded to eltrombopag.',
 'Rituximab/mycophenolate discussion is not prior administration.',
 'No real clinical advice, consent, signature, eligibility or submission is established.']}
raw=json.dumps(KEY,indent=2).encode();(REV/'ANSWER_KEY.json').write_bytes(raw)
(REV/'ANSWER_KEY.sha256').write_text(sha256(raw).hexdigest()+'  ANSWER_KEY.json\n')

S=getSampleStyleSheet();S.add(ParagraphStyle(name='CellSmall',fontSize=8.5,leading=11))
S.add(ParagraphStyle(name='Text',fontSize=10.5,leading=14,spaceAfter=10))
S.add(ParagraphStyle(name='Foot',fontSize=8,leading=10,spaceAfter=6))
def p(t,style='Text'):return Paragraph(escape(str(t)).replace('\n','<br/>'),S[style])
def table(data,widths,header=True):
 t=Table([[p(c,'CellSmall') for c in row] for row in data],colWidths=widths,repeatRows=1 if header else 0,hAlign='LEFT')
 st=[('GRID',(0,0),(-1,-1),.4,colors.HexColor('#9caab1')),('VALIGN',(0,0),(-1,-1),'TOP'),
     ('TOPPADDING',(0,0),(-1,-1),7),('BOTTOMPADDING',(0,0),(-1,-1),7),('LEFTPADDING',(0,0),(-1,-1),6)]
 if header:st.append(('BACKGROUND',(0,0),(-1,0),colors.HexColor('#e6eeee')))
 t.setStyle(TableStyle(st));return t
def footer(c,d):
 c.saveState();w,h=d.pagesize;c.setFont('Helvetica-Bold',8);c.setFillColor(colors.darkred)
 c.drawString(32,h-22,'FICTIONAL RECORD - SYNTHETIC SOFTWARE TEST - NOT FOR CLINICAL USE')
 c.setFont('Helvetica',8);c.setFillColor(colors.grey);c.drawString(32,19,f'DEMO-6248 | mock record | page {d.page}');c.restoreState()
def save(name,story,size=letter,folder=REC):
 SimpleDocTemplate(str(folder/name),pagesize=size,leftMargin=32,rightMargin=32,topMargin=44,bottomMargin=35,title='Synthetic test record / '+name).build(story,onFirstPage=footer,onLaterPages=footer)
def heading(t):return [p(t,'Title'),Spacer(1,8)]

save('01_registration_and_routing.pdf',heading('Registration / referral routing')+[
 p('Harbour Demonstration Network | outpatient chart opened 04 August 2026','Foot'),
 table([['FAMILY','FIRST','OTHER GIVEN','BIRTH DATE','CHART'],
 ['BENNETT','Daniel','Aaron','18 Apr 1983','DEMO-6248']],[145,85,85,105,128]),Spacer(1,12),
 table([['Provincial identifier','Patient correspondence'],
 ['MOCK-PHN-0136\nFictional test identifier','72 Demo Crescent\nCourtenay BC V0V 0V0\nMobile: 250-555-0193']],[240,308]),Spacer(1,15),
 table([['Care team / routing role','Contact record'],
 ['Family physician: Ethan Wells, MD','Community follow-up; results copied to primary care.'],
 ['Hematology consultant: Sophia Grant, MD','Practice contact to be confirmed against latest specialist correspondence.'],
 ['Next of kin: Alex Bennett','Emergency contact only; 250-555-0194']],[255,293]),Spacer(1,16),
 p('Archived practice directory entry - January 2025','Heading2'),
 p('Sophia Grant, MD | 18 Old Example Road, Nanaimo BC V0V 0V0\nTel 250-555-0128 / Fax 250-555-0129\nThis entry is inactive following the practice relocation.','Foot')])

save('02_lab_longitudinal_view.pdf',heading('Hematology / serial result ledger')+[
 p('BENNETT, Daniel Aaron | birth 18-Apr-1983 | chart DEMO-6248\nView printed 24-Oct-2026; result dates below are specimen collection dates.','Foot'),
 table([['Collected / accession','WBC\n10^9/L','Hb\ng/L','PLT\n10^9/L','Flag / specimen comment'],
 ['04-Aug-2026\nH26-804','5.8','124','11','L / EDTA / final'],
 ['12-Aug-2026\nH26-812','9.2','126','64','L / EDTA / final'],
 ['02-Sep-2026\nH26-902','6.4','125','15','L / EDTA / final'],
 ['08-Sep-2026\nH26-908','6.0','124','91','L / EDTA / final'],
 ['20-Oct-2026\nH26-1020','5.7','126','13','L / EDTA; platelet clumps noted. Count unreliable; new specimen requested.']],[165,65,65,65,188]),Spacer(1,15),
 table([['Reference intervals','Analytical note'],['WBC 4.0-11.0\nHb 120-160\nPLT 150-400','L denotes below laboratory interval. H26-1020 retained in the historical ledger. A citrate specimen was collected on the following day; see separate report C26-1021.']],[200,348]),
 Spacer(1,12),p('Ordering service: outpatient hematology. No active major bleeding was recorded in the laboratory requisition comments.','Foot')])

save('03_pharmacy_and_infusion_record.pdf',heading('Pharmacy review / administration history')+[
 p('Daniel Aaron Bennett | DEMO-6248 | reconciliation entered 22-Oct-2026','Foot'),
 table([['Product / strength','Quantity per dose','Schedule / route','Dates','Source / state'],
 ['Dexamethasone 4 mg tablets','10 tablets = 40 mg','Once daily, PO','05-Aug to 08-Aug-2026','Four-day course completed; administration recorded on each date.'],
 ['Immune globulin, IV solution','60 g','IV infusion','03-Sep and 04-Sep-2026','Both infusions COMPLETE. One planned two-day course.'],
 ['Cholecalciferol 1,000 unit capsules','1 capsule','Once daily, PO','Home list','Patient reports taking; unrelated to the access request.'],
 ['Rituximab / mycophenolate','--','--','Consultation discussion','No released order; no dispensing or administration documented.']],[165,110,120,145,188]),Spacer(1,18),
 p('Infusion nursing extract','Heading2'),
 table([['Date','Start','End','Status','Product lot / expiry'],
 ['03-Sep-2026','09:10','13:45','Complete','DEMO-IG-97 / 31-Dec-2027'],
 ['04-Sep-2026','09:00','13:35','Complete','DEMO-IG-97 / 31-Dec-2027']],[140,100,100,130,258]),Spacer(1,10),
 p('Weight recorded on the original infusion order: 60 kg. No new dose calculation is documented. Eltrombopag has not been dispensed at the time of this pharmacy review.','Foot')],landscape(letter))

save('04_specialist_letter.pdf',heading('Northshore Demonstration Hematology')+[
 p('420 Sample Avenue\nVictoria BC V0V 0V0'),
 p('27 October 2026\nDr. Ethan Wells\nCommunity primary care'),
 p('Regarding Daniel Aaron Bennett\nBorn 18 April 1983; hospital reference DEMO-6248','Heading2'),
 p('Thank you for the update. I reviewed Mr Bennett after recurrent thrombocytopenia. Immune thrombocytopenia remains my working diagnosis; the secondary-cause assessment is still being completed.'),
 p('There was an initial increase from 11 to 64 after the four-day dexamethasone course. The count subsequently fell to 15. He described insomnia during that course, although the record does not establish a formal adverse-event grade.'),
 p('Following the September immunoglobulin course, the count rose to 91, then declined again. Both infusion days are documented on the separate administration extract. These changes have not established a durable response.'),
 p('The EDTA count of 13 on 20 October was accompanied by platelet clumping. The laboratory requested another specimen and reported 21 on the citrate sample collected on 21 October. Those are different collections, rather than two releases of one accession.'),
 PageBreak(),p('Continuation / treatment discussion','Heading1'),
 p('Daniel Aaron Bennett | DEMO-6248 | 27 October 2026','Foot'),
 p('We reviewed rituximab and mycophenolate as alternatives, neither of which has been used in this record. Following discussion, we have agreed to request coverage for eltrombopag. My intended starting regimen for this application is 25 mg orally once daily. He has not started the medicine and there is no response to it to report.'),
 p('I will submit the Special Authority application and review the completed draft. Please return correspondence to my Victoria practice at the address on the first page. The inactive Nanaimo directory entry should not be used for this application.'),
 Spacer(1,15),p('Sophia Grant, MD FRCPC\nConsultant hematologist'),Spacer(1,20),
 table([['Professional registration','Current practice contact'],['CPSBC DEMO136','Office 250-555-0162\nFacsimile 250-555-0163']],[240,308]),Spacer(1,10),
 p('Unsigned synthetic correspondence. No actual consent, authenticated signature or payer determination is provided. The regimen is invented test content and is not a treatment recommendation.','Foot')])

save('fax_original.pdf',heading('Acute-care fax / laboratory enclosure')+[
 table([['TO','FROM'],['Dr. Sophia Grant, hematology','Amelia Ross, MD\nAcute-care author']],[274,274]),Spacer(1,12),
 p('Transmitted 22-Oct-2026 10:42 | enclosure follows outpatient repeat collection','Foot'),
 table([['Patient','Specimen / timing'],['Daniel Aaron Bennett\nDOB 1983/04/18\nDEMO-6248\nMOCK-PHN-0136','C26-1021\nSodium citrate\nCollected 21-Oct-2026 08:05\nReleased 21-Oct-2026 11:20']],[274,274]),Spacer(1,15),
 table([['Measurement','Reported result','Units','Interval','State'],['Platelet count','21','10^9/L','150-400','Final / low']],[150,110,90,100,98]),Spacer(1,14),
 p('Repeat specimen obtained following clumping in EDTA accession H26-1020. The value above is the laboratory-reported citrate specimen result. No revision to the earlier accession is issued with this enclosure.'),
 p('Acute-care communication author: Amelia Ross, MD. Ongoing outpatient treatment and coverage planning remain with hematology.','Foot')],folder=WORK)
source=pymupdf.open(WORK/'fax_original.pdf');scan=pymupdf.open()
for pg in source:
 pix=pg.get_pixmap(matrix=pymupdf.Matrix(2,2),colorspace=pymupdf.csGRAY,alpha=False)
 scan.new_page(width=612,height=792).insert_image(pymupdf.Rect(0,0,612,792),stream=pix.tobytes('png'))
scan.save(REC/'05_repeat_specimen_fax_scan.pdf')
with (REC/'06_lab_extract.csv').open('w',newline='') as f:
 w=csv.writer(f);w.writerow(['hospital_ref','accession','sample_type','drawn_at','PLT_value','unit','status','lab_comment'])
 for date,acc,value in [('2026-08-04','H26-804',11),('2026-08-12','H26-812',64),('2026-09-02','H26-902',15),('2026-09-08','H26-908',91)]:
  w.writerow(['DEMO-6248',acc,'EDTA',date+'T08:15',value,'10^9/L','FINAL',''])
 w.writerow(['DEMO-6248','H26-1020','EDTA','2026-10-20T08:10',13,'10^9/L','FINAL_WITH_COMMENT','Platelet clumps; count unreliable; repeat requested'])
 w.writerow(['DEMO-6248','C26-1021','SODIUM_CITRATE','2026-10-21T08:05',21,'10^9/L','FINAL','New specimen; laboratory-reported result'])

manifest=[];thumbs=[]
for file in sorted(REC.iterdir()):
 entry={'file':file.name,'sha256':sha256(file.read_bytes()).hexdigest()}
 if file.suffix=='.pdf':
  d=pymupdf.open(file);entry['pages']=len(d)
  for i,pg in enumerate(d):
   pix=pg.get_pixmap(matrix=pymupdf.Matrix(1.2,1.2));dest=WORK/(file.stem+f'_{i+1}.png');pix.save(dest)
   im=Image.open(dest).convert('RGB');im.thumbnail((320,414));card=Image.new('RGB',(340,442),'#eeeeee');card.paste(im,((340-im.width)//2,5));ImageDraw.Draw(card).text((8,424),file.stem+f' p{i+1}',fill='black');thumbs.append(card)
 manifest.append(entry)
(REV/'MANIFEST.json').write_text(json.dumps(manifest,indent=2))
sheet=Image.new('RGB',(1020,442*((len(thumbs)+2)//3)),'white')
for i,im in enumerate(thumbs):sheet.paste(im,((i%3)*340,(i//3)*442))
sheet.save(WORK/'contact_sheet.png')
assert (REV/'ANSWER_KEY.json').read_bytes()==raw
assert len(list(REC.iterdir()))==6
print('Fresh packet created: five PDFs / six PDF pages, plus one CSV. Parser and model were not run.')

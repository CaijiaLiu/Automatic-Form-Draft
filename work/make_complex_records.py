"""Harder synthetic fixtures; no real records, clinical advice, or external calls."""
from pathlib import Path
import csv
import json
import textwrap
import zipfile
from xml.sax.saxutils import escape
from docx import Document
from docx.shared import Inches, Pt, RGBColor
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak
from reportlab.lib.styles import getSampleStyleSheet
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'outputs' / 'complex_itp_records'
OUT.mkdir(parents=True, exist_ok=True)
NOTICE = 'SYNTHETIC MOCK RECORD - SOFTWARE TESTING ONLY'
IDENTITY = 'Patient: Jordan Sample | Synthetic ID: SYN-ITP-002 | Age: 47'

PAGES = [
('Initial hematology consultation', [
    'Document created 2026-01-09. Encounter date 2026-01-08.',
    'Presentation: easy bruising and intermittent gum bleeding. No active major bleeding recorded. This note describes an invented scenario.',
    '2026-01-08 Diagnosis: Immune thrombocytopenia (ITP)',
    'The referral had queried secondary thrombocytopenia; that wording is a historical differential, not a second confirmed diagnosis.',
    '2026-01-08 Platelet count: 16 x 10^9/L',
    'Historical outside count was 29 K/uL on 2025-12-30; the outside report is absent from this packet.',
    'Weight in this fictional record: 68 kg. No dose calculation is requested.',
    '2026-01-09 Medication: Prednisone',
    '2026-01-09 Dose: 60 mg orally once daily',
    'The current medicine list also includes vitamin D. Rituximab was discussed but never administered. No prior splenectomy documented.',
    'The plan was documented as a future follow up, not a completed treatment event.',
]),
('Treatment course and interval review', [
    'Document created 2026-03-10. Summarizes several earlier encounters.',
    '2026-01-16 Platelet count: 83 x 10^9/L',
    '2026-01-16 Treatment response: platelet rise after prednisone; durability not yet known',
    'Dose changes recorded in narrative: prednisolone 40 mg/day from 2026-01-23, then 20 mg/day from 2026-02-06. The switch in drug spelling is unresolved; do not assume an equivalence or a prescribing change.',
    '2026-02-13 Platelet count: 19 x 10^9/L',
    '2026-02-13 Treatment response: loss of response during the recorded steroid taper',
    '2026-02-14 Medication: IVIG',
    '2026-02-14 Dose: 1 g/kg daily for 2 days',
    'Administration record confirms doses on 2026-02-14 and 2026-02-15. This is one course, not two separate therapies.',
    '2026-02-20 Platelet count: 108 x 10^9/L',
    '2026-02-20 Treatment response: temporary platelet rise after IVIG',
    '2026-03-06 Platelet count: 22 x 10^9/L',
    'Patient reported insomnia while taking prednisone. The record does not assign an adverse-event grade or establish causality.',
    'Steroid stop date is not stated in this note. Do not infer it from the end of the taper schedule.',
]),
('Later review and unsigned application discussion', [
    'Document created 2026-06-20. Encounter date 2026-06-18.',
    '2026-04-03 Platelet count: 17 x 10^9/L',
    'A second IVIG course is mentioned as having occurred in early April. Exact administration dates and dose are absent; this cannot be treated as a fully documented course.',
    '2026-04-10 Platelet count: 64 x 10^9/L',
    '2026-05-15 Platelet count: 26 x 10^9/L',
    '2026-06-18 Platelet count: 20 x 10^9/L',
    'The May value above was copied from a preliminary result. The corrected laboratory export in this packet reports a different value for the same specimen.',
    '2026-06-18 Treatment response: sustained benefit is not documented after the previous short-lived rises',
    'Eltrombopag and romiplostim were discussed as possible access requests. Neither has been selected, prescribed, dispensed, or administered in this scenario.',
    'Requested agent, requested dose, prescriber identifier, patient consent and clinician signature are missing.',
    'No real payer criteria were checked. This is an unsigned fictional discussion, not an eligibility decision.',
    'One telephone note uses 03/04/2026 without a date-format convention. Its event date requires manual review.',
])]

styles = getSampleStyleSheet()
styles['BodyText'].fontSize = 10.5
styles['BodyText'].leading = 15
styles['Title'].fontSize = 19
styles['Title'].leading = 23
story = []
for index, (title, paragraphs) in enumerate(PAGES):
    if index:
        story.append(PageBreak())
    story.extend([Paragraph(title, styles['Title']), Paragraph(NOTICE, styles['BodyText']),
                  Paragraph(IDENTITY, styles['BodyText']), Spacer(1, 16)])
    for paragraph in paragraphs:
        story.extend([Paragraph(escape(paragraph), styles['BodyText']), Spacer(1, 9)])
def footer(canvas, doc):
    canvas.setFont('Helvetica', 8)
    canvas.drawString(50, 28, f'SYN-ITP-002 | Synthetic teaching packet | Page {doc.page}')
SimpleDocTemplate(str(OUT / '01_longitudinal_chart.pdf'), rightMargin=50, leftMargin=50,
                  topMargin=42, bottomMargin=45).build(story, onFirstPage=footer, onLaterPages=footer)

doc = Document()
sec = doc.sections[0]
sec.page_width, sec.page_height = Inches(8.5), Inches(11)
sec.top_margin = sec.bottom_margin = Inches(0.65)
sec.left_margin = sec.right_margin = Inches(0.75)
for style_name in ['Normal', 'Title', 'Heading 1', 'Heading 2']:
    doc.styles[style_name].font.name = 'Arial'
    doc.styles[style_name].font.color.rgb = RGBColor(0, 0, 0)
doc.styles['Normal'].font.size = Pt(11)
doc.styles['Normal'].paragraph_format.space_after = Pt(9)
for element in list(doc.styles.element.iter()):
    if element.tag.endswith('}pBdr'):
        element.getparent().remove(element)
doc.add_paragraph('Medication reconciliation and telephone notes', 'Title')
for line in [NOTICE, IDENTITY, 'Reconciliation date: 2026-06-18',
    '2026-06-18 Medication: Prednisone - patient reports no longer taking it',
    'Stop date: patient recalls late February or early March. No exact date verified.',
    'A copied medication list still says prednisone 20 mg daily. This conflicts with the patient report and must not be accepted as the current dose.',
    '2026-02-14 Medication: IVIG - historical completed course only',
    '2026-02-14 Dose: 1 g/kg daily for 2 days',
    'Do not count the repeated IVIG history here as an additional course.',
    'Rituximab: discussed, not given. Eltrombopag: not started. Romiplostim: not started.',
    'Adverse symptoms: insomnia and mood change reported during steroid use; onset date not captured.',
    'No known drug allergies reported in this note; this statement is not a medication order.']:
    doc.add_paragraph(line)
doc.add_page_break()
doc.add_paragraph('Telephone encounter and copied laboratory value', 'Title')
for line in [NOTICE, IDENTITY,
    'Note date: 03/04/2026. Locale/date convention is unspecified.',
    'The caller says the count was nineteen yesterday. There is no attached report or unambiguous collection date.',
    '2026-05-15 Platelet count: 26 K/uL',
    'Copied from preliminary specimen LAB-0515-A. See the corrected result in the CSV before using this count.',
    '2026-06-18 Platelet count: 20 x 10^9/L',
    'A test-only transcription uses the token PLT 2O x 10^9/L, with letter O rather than digit zero. The scan should not be silently treated as a verified numeric result.',
    'No clinician signature or verified prescriber number is present. Requested medicine remains undecided.']:
    doc.add_paragraph(line)
doc.core_properties.author = 'Synthetic Demo Generator'
doc.save(OUT / '02_reconciliation_and_calls.docx')

results = [
('2026-01-08','16','x 10^9/L','LAB-0108-A','final',''),
('2026-01-16','83','K/uL','LAB-0116-A','final',''),
('2026-01-16','83','x 10^9/L','LAB-0116-A','duplicate export','same specimen as preceding row'),
('2026-02-13','19','x 10^9/L','LAB-0213-A','final',''),
('2026-02-20','108','K/uL','LAB-0220-A','final',''),
('2026-03-06','22','x 10^9/L','LAB-0306-A','final',''),
('2026-03-20','18000','/uL','LAB-0320-A','final','unit conversion needed'),
('2026-04-03','17','x 10^9/L','LAB-0403-A','final',''),
('2026-04-10','64','x 10^9/L','LAB-0410-A','final',''),
('2026-04-24','','x 10^9/L','LAB-0424-A','cancelled','sample clotted; no numeric result'),
('2026-05-15','26','K/uL','LAB-0515-A','preliminary','superseded by corrected row'),
('2026-05-15','16','K/uL','LAB-0515-A','corrected','replaces preliminary 26'),
('2026-06-04','<10','x 10^9/L','LAB-0604-A','final','bound only; not an exact count'),
('2026-06-18','20','x 10^9/L','LAB-0618-A','final',''),
]
with (OUT / '03_laboratory_raw.csv').open('w', newline='') as f:
    w = csv.writer(f)
    w.writerow(['synthetic_patient_id','collected_date','analyte','value','unit','specimen_id','status','comment'])
    for date, val, unit, specimen, status, comment in results:
        w.writerow(['SYN-ITP-002',date,'PLT',val,unit,specimen,status,comment])
with (OUT / '04_laboratory_labeled.csv').open('w', newline='') as f:
    w = csv.writer(f)
    w.writerow(['synthetic_patient_id','date','finding','specimen_id','status'])
    for date, val, unit, specimen, status, comment in results:
        w.writerow(['SYN-ITP-002',date,f'Platelet count: {val} {unit}' if val else 'No result - sample clotted',specimen,status])

scan = Image.new('RGB', (1700,2200), '#f7f5ef')
draw = ImageDraw.Draw(scan)
font = ImageFont.truetype('/System/Library/Fonts/Supplemental/Arial.ttf', 32)
scan_text = [NOTICE,'Jordan Sample | SYN-ITP-002','Scanned telephone memo','Filed: 2026-06-19; event date uncertain',
    'Copied result: PLT 2O x 10^9/L','The character after 2 is the letter O.',
    'Patient said "off steroids since early March".',
    'Date of final dose not independently confirmed.',
    'No requested access medicine selected.',
    'This scan is a generated test image, not a real chart.']
for i, line in enumerate(scan_text):
    draw.text((90,160+i*135),line,font=font,fill='#222222')
scan.save(OUT / '05_scan_with_ambiguous_value.png')

(OUT / '06_undated_addendum.txt').write_text(NOTICE+'\n'+IDENTITY+'''\nUndated addendum
Medication: IVIG - history only, not an active prescription
Dose: not documented for the second course
Response: a temporary increase was reported; duration unknown
No splenectomy. Rituximab not administered.
No requested agent selected; no application signed.
The statements above have no event date. Requires Review.
''')
(OUT / '07_patient_and_prescriber_narrative.txt').write_text(
    (ROOT/'sample_data'/'mock_patient_context.txt').read_text())

checks = [
dict(id='C01',issue='document date versus event date',source='01_longitudinal_chart.pdf page 1',expected='diagnosis dated 2026-01-08, not creation date 2026-01-09'),
dict(id='C02',issue='historical differential and negation',source='01_longitudinal_chart.pdf page 1',expected='do not confirm the referral differential; do not count rituximab or splenectomy as received'),
dict(id='C03',issue='taper and spelling change',source='01_longitudinal_chart.pdf page 2',expected='retain dated taper events and unresolved prednisone/prednisolone wording; do not silently equate names'),
dict(id='C04',issue='duplicate course',source='01_longitudinal_chart.pdf page 2 and 02_reconciliation_and_calls.docx page 1',expected='two administrations belong to one February IVIG course; repeated history is not another course'),
dict(id='C05',issue='incomplete second course',source='01_longitudinal_chart.pdf page 3 and 06_undated_addendum.txt',expected='second course reported early April; exact dates and dose Requires Review'),
dict(id='C06',issue='current medication conflict',source='02_reconciliation_and_calls.docx page 1',expected='copied active list and patient-reported discontinuation conflict; current status and exact stop date Requires Review'),
dict(id='C07',issue='corrected count',source='03_laboratory_raw.csv rows 12 and 13 plus PDF page 3',expected='LAB-0515-A corrected 16 supersedes preliminary 26; retain both evidence records and flag discrepancy with copied notes'),
dict(id='C08',issue='unit normalization',source='03_laboratory_raw.csv row 8',expected='18000 /uL equals 18 x 10^9/L; preserve original value and unit'),
dict(id='C09',issue='duplicate specimen',source='03_laboratory_raw.csv rows 3 and 4',expected='same LAB-0116-A specimen; one test, two representations'),
dict(id='C10',issue='inequality and missing result',source='03_laboratory_raw.csv rows 11 and 14',expected='cancelled sample has no result; <10 is an upper bound, not exact 10 or zero'),
dict(id='C11',issue='date ambiguity',source='02_reconciliation_and_calls.docx page 2',expected='03/04/2026 and yesterday require date convention and event context; do not choose silently'),
dict(id='C12',issue='OCR ambiguity',source='05_scan_with_ambiguous_value.png',expected='PLT 2O contains letter O; preserve evidence, do not invent verified numeric result'),
dict(id='C13',issue='missing fields',source='01_longitudinal_chart.pdf page 3',expected='requested agent, requested dose, prescriber identifier, consent and signature Requires Review'),
dict(id='C14',issue='undated evidence',source='06_undated_addendum.txt',expected='facts remain undated; do not borrow an unrelated document date'),
]
(OUT / 'EXPECTED_REVIEW_CASES.json').write_text(json.dumps(checks,indent=2))
(OUT / '使用说明.txt').write_text('''复杂合成 ITP 测试包 v2

同一名虚构患者 SYN-ITP-002，记录跨度为 2025 年 12 月至 2026 年 6 月。
所有内容均由程序编写，药物及剂量仅为软件测试情节，不构成治疗建议。

01：三页纵向病历，含初诊、历史检查、减量、治疗反应和后续申请讨论。
02：两页 Word，含药物核对、停药状态冲突、电话记录和歧义日期。
03：原始结构 CSV，14 行检验数据，使用 PLT/value/unit 分列。
04：与 03 完全相同的数据，转换为第一版提取器认识的标签句式。
05：扫描图片，含字母 O 与数字 0 的歧义。
06：无日期补充记录，含缺失剂量和否定治疗史。
07：同一名虚构患者的身份及处方者叙述，补充 DOB、mock PHN、执照及联系方式。

推荐顺序：
1. 取消网页上的内置简单病例勾选，以免混入旧患者数据。
2. 先上传 01、02、04、06、07，观察提取及原文证据和身份资料预填。
3. 单独用 03 替换 04，比较原始 CSV 和标签 CSV 的识别差异。
4. 再加入 05 检查 OCR 是否可用；没有 OCR 时应出现提示。
不要同时用 03 和 04 计算检查次数，它们是同一批数据的不同表示。
不要上传此说明或 EXPECTED_REVIEW_CASES.json，以免将答案混入输入。

预期结果：EXPECTED_REVIEW_CASES.json 列出 14 个人工核对点，属于测试答案，
不是当前提取器已经实现的功能。行号以 CSV 表头为第 1 行。

已知当前 MVP 限制：
不支持可靠的否定识别、单位统一、药物别名、日期上下文、重复合并、
更正结果优先级或自动冲突审查；可能误把“not administered”等当治疗史。
CSV 原始分列格式可能完全漏提取；标签版本也不保证数值解释正确。
Word/PDF 的换行可能拆开原文证据；扫描文本识别可能失败。
因此，这套数据是用来暴露不足，而不是证明复杂病例已能自动正确处理。
''',encoding='utf-8')

with zipfile.ZipFile(ROOT/'outputs'/'complex_itp_records.zip','w',zipfile.ZIP_DEFLATED) as z:
    for path in sorted(OUT.iterdir()):
        z.write(path, 'complex_itp_records/'+path.name)
print('Created complex packet:', OUT)

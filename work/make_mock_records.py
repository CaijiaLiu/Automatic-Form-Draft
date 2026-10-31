"""Reproducible fictional records for upload testing; no real patient data."""
from pathlib import Path
import csv
import zipfile
from docx import Document
from docx.shared import Inches, Pt, RGBColor
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'outputs' / 'mock_itp_records'
OUT.mkdir(parents=True, exist_ok=True)
ID = 'Patient ID: SYN-ITP-001 | Name: Alex Example | Age: 42'
NOTICE = 'SYNTHETIC MOCK RECORD - SOFTWARE TESTING ONLY'

consult = [
    'Record date: 2026-01-12', ID, NOTICE,
    '2026-01-12 Diagnosis: Immune thrombocytopenia (ITP)',
    '2026-01-12 Platelet count: 18 x 10^9/L',
    '2026-01-12 Presentation: bruising and scattered petechiae.',
    '2026-01-13 Medication: Prednisone',
    '2026-01-13 Dose: 1 mg/kg daily',
    '2026-01-20 Platelet count: 76 x 10^9/L',
    '2026-01-20 Treatment response: initial platelet rise',
    'Fictional scenario values only; no treatment recommendation.',
]
pdf = canvas.Canvas(str(OUT / '01_initial_consult.pdf'), pagesize=letter)
pdf.setTitle('Synthetic ITP initial consultation')
pdf.setFont('Helvetica-Bold', 18)
pdf.drawString(54, 736, 'Synthetic ITP initial consultation')
for i, line in enumerate(consult):
    pdf.setFont('Helvetica', 10)
    pdf.drawString(54, 700 - i * 29, line)
pdf.setFont('Helvetica', 9)
pdf.drawString(54, 42, 'Demo clinic - fictional organization | Page 1 of 1')
pdf.save()

followup = [
    NOTICE, ID, 'Record date: 2026-02-11',
    '2026-02-10 Diagnosis: Immune thrombocytopenia (ITP)',
    '2026-02-10 Platelet count: 24 x 10^9/L',
    '2026-02-10 Treatment response: transient rise then relapse after prednisone',
    '2026-02-11 Medication: IVIG',
    '2026-02-11 Dose: 1 g/kg daily for 2 days',
    '2026-02-18 Platelet count: 92 x 10^9/L',
    '2026-02-18 Treatment response: temporary platelet rise after IVIG',
    'Requested access drug and clinical rationale are deliberately omitted.',
]
doc = Document()
section = doc.sections[0]
section.page_width, section.page_height = Inches(8.5), Inches(11)
section.top_margin = section.bottom_margin = Inches(0.75)
normal = doc.styles['Normal']
normal.font.name, normal.font.size = 'Arial', Pt(11)
normal.paragraph_format.space_after = Pt(12)
doc.styles['Title'].font.color.rgb = RGBColor(0, 0, 0)
for element in list(doc.styles.element.iter()):
    if element.tag.endswith('}pBdr'):
        element.getparent().remove(element)
doc.add_paragraph('Synthetic ITP follow up', 'Title')
for line in followup:
    doc.add_paragraph(line)
doc.core_properties.author = 'Synthetic Demo Generator'
doc.save(OUT / '02_follow_up.docx')

with (OUT / '03_platelet_results.csv').open('w', newline='') as f:
    writer = csv.writer(f)
    writer.writerow(['synthetic_patient_id', 'date', 'finding', 'record_type'])
    for date, count in [('2026-01-12', 18), ('2026-01-20', 76), ('2026-02-10', 24), ('2026-02-18', 92), ('2026-03-03', 21)]:
        writer.writerow(['SYN-ITP-001', date, f'Platelet count: {count} x 10^9/L', 'SYNTHETIC MOCK'])

image = Image.new('RGB', (1700, 2200), '#faf9f6')
draw = ImageDraw.Draw(image)
font_path = '/System/Library/Fonts/Supplemental/Arial.ttf'
font = ImageFont.truetype(font_path, 31)
heading = ImageFont.truetype(font_path, 48)
draw.text((100, 110), 'Synthetic scanned follow up note', fill='black', font=heading)
scan_lines = [NOTICE, 'Patient ID: SYN-ITP-001', 'Name: Alex Example', 'Record date: 2026-03-03',
    '2026-03-03 Diagnosis: ITP', '2026-03-03 Platelet count: 21 x 10^9/L',
    '2026-03-03 Treatment response: inadequate sustained response',
    'after previous prednisone and IVIG courses.',
    'No requested drug recorded. Requires clinician review.',
    'This is a digitally generated scan simulation.',
    'It contains no real patient information.']
for i, line in enumerate(scan_lines):
    draw.text((100, 250 + i * 100), line, fill='#242424', font=font)
image.save(OUT / '04_scanned_follow_up.png')

(OUT / '05_optional_conflicting_note.txt').write_text(
    NOTICE + '\n' + ID + '\n'
    '2026-02-10 Platelet count: 42 x 10^9/L\n'
    'Intentional conflict: the CSV and Word follow up report 24 for this date.\n'
    'Expected human action: compare both source documents; do not choose silently.\n'
)
(OUT / 'START_HERE.txt').write_text('''合成 ITP 上传测试包\n\n所有文件均由程序制作，属于同一名虚构患者 SYN-ITP-001。\n病历中的剂量和检查数值仅是软件测试数据，不构成医疗建议。\n\n基础测试：在网页上传 01 PDF、02 DOCX 和 03 CSV。\n预期：诊断、两种既往药物、剂量、反应和多次血小板结果均有证据来源。\n请求药物和临床理由未提供，应保持 Requires Review。\n\n扫描测试：单独增加 04 PNG；当前环境若没有 Tesseract/pytesseract，\n网页会提示 OCR 不可用，扫描中的信息不会被提取。\n\n冲突测试：最后加入 05 TXT。它故意将 2026-02-10 的血小板结果\n写为 42，与 DOCX/CSV 的 24 不一致。当前 MVP 会保留两个来源，\n但尚不能自动标记所有冲突；请人工查看证据，不要当作已解决。\n\nCSV 含有标签化 finding 列，特意适配第一版规则提取器。\n这不代表任意医院原始 CSV 或任意措辞都能被识别。\n上传前先解压 ZIP；上传文件时不要选择此说明文件。\n''', encoding='utf-8')
with zipfile.ZipFile(ROOT / 'outputs' / 'mock_itp_records.zip', 'w', zipfile.ZIP_DEFLATED) as z:
    for path in sorted(OUT.iterdir()):
        z.write(path, 'mock_itp_records/' + path.name)
print(OUT)

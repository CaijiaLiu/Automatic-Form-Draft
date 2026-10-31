"""Local prefill of the user-selected BC HLTH 5328 PDF; draft exports only."""
from __future__ import annotations

from io import BytesIO
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
from xml.sax.saxutils import escape

from pypdf import PdfReader, PdfWriter
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.pdfgen import canvas
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer

from .models import Fact

TEMPLATE = Path(__file__).resolve().parents[1] / 'assets' / 'bc_5328_original.pdf'
SOURCE_URL = 'https://www2.gov.bc.ca/assets/gov/health/forms/5328fil.pdf'
# Keys are the exact AcroForm names, including the original spelling of Presciber.
TEXT_FIELDS = {
    'Patient Family Name': 'Patient family name',
    'Patient Given Name': 'Patient given name(s)',
    'Date of Birth': 'Date of birth (YYYY/MM/DD)',
    'PHN': 'PHN',
    'Presciber Name and Mailing Address': 'Prescriber name and mailing address',
    'CPSBC or CRNBC Number': 'Prescriber licence number',
    'Phone Number': 'Prescriber phone',
    'Fax Number': 'Prescriber fax',
    'Date of Application': 'Application date (YYYY/MM/DD)',
    'Medication Requested': 'Medication requested',
    'Dose and Regimen': 'Requested dose and regimen',
    'Supporting Details': 'Supporting details (candidate text; verify against evidence)',
}
BUTTON_CHOICES = {
    'Request': ['Requires Review', '/New', '/Renewal'],
    'Certification Number': ['Requires Review', '/CPSBC', '/CRNBC'],
}
CHECKBOX_FIELDS = {
    'Diagnosis Requiring Use': 'Diagnosis requiring use',
    'Previously Tried Therapies': 'Previously tried therapies and response',
    'Patient Specific Contraindications': 'Patient-specific contraindications to alternatives',
}

DEMOGRAPHIC_MAPPING = {
    'Patient Family Name': 'patient_family_name',
    'Patient Given Name': 'patient_given_name',
    'Date of Birth': 'patient_dob',
    'PHN': 'patient_phn',
    'CPSBC or CRNBC Number': 'prescriber_licence',
    'Phone Number': 'prescriber_phone',
    'Fax Number': 'prescriber_fax',
    'Date of Application': 'application_date',
    'Medication Requested': 'requested_drug',
    'Dose and Regimen': 'requested_regimen',
}

def field_reviews(facts: list[Fact]) -> dict[str, dict]:
    """Explain each proposal, including absence, conflicting values and origins."""
    reviews = {}
    identities = {f.value.casefold() for f in facts if f.category=='patient_full_name'}
    for field, category in DEMOGRAPHIC_MAPPING.items():
        candidates = [(i,f) for i,f in enumerate(facts,1) if f.category==category]
        unique = {f.value.casefold():f.value for _,f in candidates}
        reason = []
        value = ''
        if category.startswith('patient_') and len(identities)>1:
            reason.append('Requires Review: multiple patient names detected; identity fields not combined.')
        elif len(unique)>1:
            reason.append('Requires Review: conflicting source values; left blank.')
        elif len(unique)==1:
            if any('ambiguous numeric date' in f.review_reason or 'invalid or unsupported date' in f.review_reason for _,f in candidates):
                reason.append('Requires Review: source date cannot be resolved safely; left blank.')
            else:
                value = next(iter(unique.values()))
                reason.append('Requires Review: source-backed candidate; verify before use.')
        elif field=='Date of Application':
            value = datetime.now(ZoneInfo('America/Vancouver')).strftime('%Y/%m/%d')
            reason.append('Draft creation date generated from today in America/Vancouver; editable; not a date inferred from medical notes.')
        else:
            reason.append('Requires Review: source information missing.')
        reason.extend(sorted({f.review_reason for _,f in candidates if f.review_reason}))
        if category in {'requested_drug','requested_regimen'}:
            value=''
            reason.insert(0,'Clinician entry required. Source mentions are retained for review only; never automatically applied as a treatment request.')
        reviews[field]={'value':value,'status':' '.join(reason), 'evidence':[f'E{i}' for i,_ in candidates]}
    components = {}
    for category in ('prescriber_name','prescriber_address'):
        matches = [(i,f) for i,f in enumerate(facts,1) if f.category==category]
        components[category]=matches
    conflicts = any(len({f.value.casefold() for _,f in v})>1 for v in components.values())
    address = '\n'.join(next(iter({f.value for _,f in v}), '') for v in components.values()).strip()
    reviews['Presciber Name and Mailing Address']={
        'value':'' if conflicts else address,
        'status':'Requires Review: conflicting prescriber name/address; left blank.' if conflicts else
            ('Requires Review: source-backed prescribing role; verify mailing address.' if address else 'Requires Review: source information missing.'),
        'evidence':[f'E{i}' for v in components.values() for i,_ in v],
    }
    if address and not conflicts:
        for category,label in [('prescriber_name','prescriber name'),('prescriber_address','mailing address')]:
            if not components[category]:
                reviews['Presciber Name and Mailing Address']['status']+=f' Requires Review: {label} missing; partial proposal only.'
        reasons=sorted({f.review_reason for matches in components.values() for _,f in matches if f.review_reason})
        reviews['Presciber Name and Mailing Address']['status']+=' '+' '.join(reasons)
    return reviews

def propose_fields(facts: list[Fact]) -> dict[str, str]:
    """Populate source-backed candidates; never convert foreign identifiers."""
    values = {field: '' for field in TEXT_FIELDS}
    for field, review in field_reviews(facts).items():
        values[field] = review['value']
    labels = {'diagnosis': 'Diagnosis', 'medication': 'Therapy mentioned', 'dose': 'Dose mentioned',
              'platelet_count': 'Platelets', 'response': 'Response'}
    lines = ['Requires Review - candidate extraction; verify every statement.']
    for category, label in labels.items():
        selected = [(i, f) for i, f in enumerate(facts, 1) if f.category == category]
        if not selected:
            continue
        lines.append(label + ': ' + '; '.join(f'{f.value} ({f.date})' for i, f in selected))
    lines.append('Requires Review: verify request medicine/dose and all candidate fields against source records.')
    values['Supporting Details'] = '\n'.join(lines)
    return values

def _field_preview(text: str) -> str:
    """Wrap the application summary without silently cutting off clinical text."""
    lines: list[str] = []
    for paragraph in text.replace('\r', '').split('\n'):
        current = ''
        for word in paragraph.split():
            if stringWidth((current + ' ' + word).strip(), 'Helvetica', 9) > 540:
                if current:
                    lines.append(current)
                current = word
                while stringWidth(current, 'Helvetica', 9) > 540:
                    n = len(current)
                    while stringWidth(current[:n], 'Helvetica', 9) > 540:
                        n -= 1
                    lines.append(current[:n])
                    current = current[n:]
            else:
                current = (current + ' ' + word).strip()
        lines.append(current)
    if len(lines) > 7:
        raise ValueError('Supporting details exceed the form space. Shorten the application summary; the separate evidence report retains the full text.')
    return '\n'.join(lines)

def _stamp_page() -> PdfReader:
    out = BytesIO()
    c = canvas.Canvas(out, pagesize=letter)
    c.setFillColor(colors.darkred)
    c.setFont('Helvetica-Bold', 9)
    c.drawCentredString(306, 779, 'SYNTHETIC DEMO - DRAFT ONLY - NOT FOR SUBMISSION')
    c.save()
    out.seek(0)
    return PdfReader(out)

def export_evidence_report(values: dict[str, str], facts: list[Fact], *, reviewed: bool = False,
              choices: dict[str, str] | None = None, checks: dict[str, bool] | None = None) -> bytes:
    """Standalone internal review record; never automatically attached to the form."""
    choices, checks = choices or {}, checks or {}
    out = BytesIO()
    styles = getSampleStyleSheet()
    styles['BodyText'].fontSize = 9.5
    styles['BodyText'].leading = 12
    styles['Heading3'].fontSize = 10.5
    styles['Heading3'].spaceBefore = 7
    styles['Heading3'].spaceAfter = 4
    story = [Paragraph('Internal Evidence &amp; Review Report', styles['Title']),
             Paragraph('SYNTHETIC DEMO - INTERNAL REVIEW ONLY. Separate from the HLTH 5328 application draft; not automatically included in an application export. Prescriber signature and consent are not supplied by this tool.', styles['BodyText']), Spacer(1, 10)]
    status = 'User marked candidate content reviewed (demo only).' if reviewed else 'Requires Review - user has not marked candidate content reviewed.'
    story += [Paragraph(status, styles['BodyText']), Spacer(1, 10)]
    for field, label in TEXT_FIELDS.items():
        val = values.get(field, '').strip() or 'Requires Review - missing'
        story += [Paragraph(escape(label), styles['Heading3']),
                  Paragraph(escape(val).replace('\n', '<br/>'), styles['BodyText'])]
        review = field_reviews(facts).get(field)
        if review:
            story.append(Paragraph(escape(review['status']+' Sources: '+(', '.join(review['evidence']) or 'no source evidence')), styles['BodyText']))
            if values.get(field,'').strip()!=review.get('value','').strip():
                story.append(Paragraph(escape('Edited value differs from the extracted proposal; confirm independently. Original proposal: '+(review.get('value') or '(missing)')),styles['BodyText']))
    story += [Paragraph('Selections', styles['Heading2'])]
    for field in BUTTON_CHOICES:
        story.append(Paragraph(escape(field + ': ' + choices.get(field, 'Requires Review')), styles['BodyText']))
    for field in CHECKBOX_FIELDS:
        story.append(Paragraph(escape(field + ': ' + ('selected by user' if checks.get(field) else 'not selected; not an assertion of absence')), styles['BodyText']))
    story += [Paragraph('Source evidence', styles['Heading2']),
              Paragraph('Rules can misread negation, dose, date, units, current status and conflicting results. Each E reference below is an extracted candidate, not a verified clinical finding. Separate dose statements are not automatically linked to a medicine.', styles['BodyText'])]
    for i, f in enumerate(facts, 1):
        story += [Paragraph(escape(f'E{i} | {f.category} | {f.date}'), styles['Heading3']),
                  Paragraph(escape(f'{f.filename} | {f.location}'), styles['BodyText']),
                  Paragraph(escape(f.evidence), styles['BodyText'])]
        if f.review_reason:
            story.append(Paragraph(escape(f.review_reason), styles['BodyText']))
    doc = SimpleDocTemplate(out, pagesize=letter, title='Internal evidence and review - synthetic demo',
                            leftMargin=45, rightMargin=45, topMargin=45, bottomMargin=45)
    doc.build(story)
    return out.getvalue()

def export_official_draft(values: dict[str, str], facts: list[Fact], *,
                          choices: dict[str, str] | None = None,
                          checks: dict[str, bool] | None = None,
                          reviewed: bool = False) -> bytes:
    choices, checks = choices or {}, checks or {}
    if any(len(values.get(f, '')) > 110 for f in TEXT_FIELDS
           if f not in {'Supporting Details', 'Presciber Name and Mailing Address'}):
        raise ValueError('A short form field exceeds 110 characters. Shorten it before export.')
    if len(values.get('Presciber Name and Mailing Address', '')) > 300:
        raise ValueError('Prescriber name/address exceeds 300 characters. Shorten it before export.')
    writer = PdfWriter()
    writer.clone_document_from_reader(PdfReader(TEMPLATE))
    expected = set(TEXT_FIELDS) | set(BUTTON_CHOICES) | set(CHECKBOX_FIELDS)
    if not expected.issubset(writer.get_fields() or {}):
        raise ValueError('Official template fields changed; mapping requires review.')
    fill = {field: values.get(field, '').strip() for field in TEXT_FIELDS}
    fill['Supporting Details'] = _field_preview(fill['Supporting Details'])
    for field, options in BUTTON_CHOICES.items():
        value = choices.get(field, 'Requires Review')
        if value not in options:
            raise ValueError(f'Unsupported selection for {field}')
        if value != 'Requires Review':
            fill[field] = value
    for field in CHECKBOX_FIELDS:
        fill[field] = '/Yes' if checks.get(field, False) else '/Off'
    # Reject overflowing short fields instead of hiding data in a scrollable box.
    for annotation in writer.pages[0].get('/Annots', []):
        widget = annotation.get_object()
        field = widget.get('/T')
        if field in TEXT_FIELDS and field not in {'Supporting Details', 'Presciber Name and Mailing Address'}:
            value = fill[field]
            width = float(widget['/Rect'][2]) - float(widget['/Rect'][0]) - 6
            if '\n' in value or stringWidth(value, 'Helvetica', 9) > width:
                raise ValueError(f'{TEXT_FIELDS[field]} is too long for its PDF box. Shorten it before export.')
    # Tuple API sets a fixed readable font instead of automatic tiny text.
    encoded = {field: (value, '/Helv', 9) if field in TEXT_FIELDS else value
               for field, value in fill.items()}
    writer.update_page_form_field_values(writer.pages[0], encoded, auto_regenerate=False)
    writer.pages[0].merge_page(_stamp_page().pages[0])
    writer.add_metadata({'/Title': 'SYNTHETIC DEMO - HLTH 5328 draft - not for submission',
                         '/Subject': 'Local candidate prefill; signature and consent not provided'})
    out = BytesIO()
    writer.write(out)
    result = out.getvalue()
    # Validate canonical field values as well as visible widget appearance streams.
    saved = PdfReader(BytesIO(result))
    fields = saved.get_fields() or {}
    for field, value in fill.items():
        if str(fields[field].get('/V', '')) != value:
            raise ValueError(f'PDF field did not save correctly: {field}')
    for annotation in saved.pages[0].get('/Annots', []):
        widget = annotation.get_object()
        name = widget.get('/T')
        if name in TEXT_FIELDS:
            if str(widget.get('/V', '')) != fill[name] or not widget.get('/AP', {}).get('/N'):
                raise ValueError(f'PDF widget value/appearance mismatch: {name}')
    return result

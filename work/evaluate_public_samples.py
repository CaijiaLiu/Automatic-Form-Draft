"""Independent PDF input, publisher-supplied labels; never read labels in app."""
from collections import defaultdict
from dataclasses import asdict
from datetime import datetime
import hashlib
import json
from pathlib import Path
import sys
import zipfile

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from src.extractor import extract_files
from src.official_form import propose_fields

DATA=ROOT/'sample_data'/'public_external'
OUT=ROOT/'outputs'/'public_document_evaluation'
OUT.mkdir(parents=True,exist_ok=True)
manifest=json.loads((DATA/'provenance.json').read_text())
truth={row['pdf_filename']:row for row in map(json.loads,(DATA/'ground_truth.jsonl').read_text().splitlines())}
baseline=json.loads((ROOT/'work'/'public_baseline.json').read_text())
code_hash=hashlib.sha256(b''.join((ROOT/p).read_bytes() for p in ['src/demographics.py','src/extractor.py','src/official_form.py'])).hexdigest()
normalize=lambda text:' '.join(text.split()).casefold()
records=[]
seen_hash=set()
for item in manifest['files']:
    if not item['path'].endswith('.pdf') or item['sha256'] in seen_hash:
        continue
    seen_hash.add(item['sha256'])
    name=Path(item['path']).name
    label=next(row for row in truth.values() if row['pdf_filename']==name or row.get('scanned_pdf_filename')==name)
    facts,warnings=extract_files([DATA/item['path']])
    values=propose_fields(facts)
    expected={
        'Patient Given Name':' '.join(label['patient_name'].split()[:-1]),
        'Patient Family Name':label['patient_name'].split()[-1],
        'Date of Birth':datetime.strptime(label['patient_dob'],'%d/%m/%Y').strftime('%Y/%m/%d'),
    }
    # Name components are evaluated under an explicit final-token surname
    # convention, not asserted as culturally general name parsing.
    tests=[]
    for field,target in expected.items():
        predicted=values[field]
        tests.append({'field':field,'expected':target,'predicted':predicted,
            'result':'correct' if normalize(predicted)==normalize(target) else ('missing' if not predicted else 'incorrect'),
            'baseline_result':'missing'})
    records.append({'file':item['path'],'split':item['split'],
        'variant':'scan/OCR' if item['path'].startswith('pdfs_scanned/') else 'native PDF',
        'sha256':item['sha256'],'tests':tests,'baseline_fact_count':len(baseline[item['path']]['facts']),
        'candidate_count':len(facts),'warnings':warnings,
        'foreign_identifier_checks':{'BC_PHN_left_blank':not values['PHN'],
                                     'BC_licence_left_blank':not values['CPSBC or CRNBC Number']},
        'evidence':[asdict(f) for f in facts if f.category.startswith(('patient_','prescriber_'))]})
summary=defaultdict(lambda:{'correct':0,'missing':0,'incorrect':0,'total':0})
for record in records:
    bucket=record['split']+' / '+record['variant']
    for test in record['tests']:
        summary[bucket][test['result']]+=1
        summary[bucket]['total']+=1
report={'dataset':manifest['source'],'revision':manifest['revision'],'extractor_sha256':code_hash,
        'method':'Fixed 3-development/3-reserved document IDs; publisher labels. Initial frozen audit is preserved separately. A header-boundary rule was hardened after that audit, so this current snapshot is a regression evaluation, not an untouched hold-out claim. No model training; no labels loaded by extractor.',
        'scored_fields':list(expected),'summary':dict(summary),'records':records,
        'limits':['Small convenience sample from one third-party synthetic generator.',
            'Demographic scores do not measure ITP clinical extraction, negation, treatment response or BC eligibility.',
            'Same native/scan document is not an independent patient; identical paired PDFs were deduplicated by SHA256.',
            'Name splitting assumes last token surname; all extracted candidates remain reviewable.',
            'Author, overseas provider ID and encounter date are not automatically prescriber, BC licence or application date.',
            'OCR results may vary with Tesseract version.']}
(OUT/'results.json').write_text(json.dumps(report,indent=2))
lines=['# Public synthetic PDF evaluation','',
    'Source: '+manifest['source'],'Publisher: Jack Webb / Root Cause Analytics. Licence: CC-BY-NC 4.0 (non-commercial evaluation).',
    'Pinned source revision: `'+manifest['revision']+'`. Original PDFs are unchanged. No real patient records are used.','',
    'Initially, 3 documents were used for development and 3 different documents were reserved for validation. True scan variants were additionally evaluated; byte-identical duplicates were excluded.',
    'The initial frozen results are preserved in evaluation_initial.md/results_initial.json. That audit found an OCR column header misread as a surname. A general header-boundary guard was added afterward; the table below is therefore a regression snapshot, not a new untouched hold-out test.',
    'Each PDF is processed independently. Publisher labels are used by this evaluation script only, not by the app.',
    'Only given name, family name and birth date are scored. Given/family labels are derived from the publisher full name using an explicit final-token surname convention.','',
    '| Group | Correct | Missing | Incorrect | Total |','|---|---:|---:|---:|---:|']
for group,count in summary.items():
    lines.append(f"| {group} | {count['correct']} | {count['missing']} | {count['incorrect']} | {count['total']} |")
lines += ['','The previous extractor had no identity-field implementation: baseline 0 correctly prefilled identity fields in this sample. This is a narrow baseline comparison, not general clinical accuracy.','',
    '## Failures and limits','']
for record in records:
    for test in record['tests']:
        if test['result']!='correct':
            lines.append(f"- {record['file']}: {test['field']} {test['result']}; expected `{test['expected']}`, predicted `{test['predicted']}`.")
lines += ['- '+s for s in report['limits']]
lines += ['','## How to try the documents','',
    'Unzip the public test pack and upload ONE original PDF at a time, or select an individual public demo in the local app. The records concern different fictional patients and are not ITP cases.',
    'Never upload results.json or the source ground-truth labels as a clinical input.',
    'BC PHN/licence fields should remain blank for these Australian samples. Their Medicare/provider numbers are not valid substitutes.',
    'Application date defaults to the local draft creation date and has no source-document provenance.',
    'To reproduce: `.venv/bin/python work/evaluate_public_samples.py`. Download/provenance script: `work/fetch_public_samples.py`.']
(OUT/'evaluation.md').write_text('\n'.join(lines))

with zipfile.ZipFile(ROOT/'outputs'/'public_synthetic_test_pack.zip','w',zipfile.ZIP_DEFLATED) as z:
    for item in manifest['files']:
        if item['path'].endswith('.pdf'):
            z.write(DATA/item['path'],item['path'])
    z.write(DATA/'README.md','SOURCE_DATASET_CARD.md')
    z.write(DATA/'provenance.json','PROVENANCE.json')
    z.write(OUT/'evaluation.md','READ_BEFORE_TESTING.md')
    if (OUT/'evaluation_initial.md').exists():
        z.write(OUT/'evaluation_initial.md','INITIAL_FROZEN_EVALUATION.md')
print(json.dumps(dict(summary),indent=2))
print('Detailed report:',OUT/'evaluation.md')

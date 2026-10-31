"""Revalidate recorded real inference and verify presentation without another model call."""
from pathlib import Path
from dataclasses import asdict
from io import BytesIO
import hashlib,json,re
import pymupdf
from pypdf import PdfReader
from streamlit.testing.v1 import AppTest
from src.semantic import source_units,validate_response
from src.autofill import autofill_documents,assemble_autofill
from src.official_form import export_official_draft

ROOT=Path.cwd();OUT=ROOT/'outputs/semantic_integration_demo'
report=json.loads((OUT/'verification.json').read_text())
paths=sorted((ROOT/'outputs/realistic_emr_challenge/records').iterdir())
base=autofill_documents(paths)
units=source_units(paths,base.rows)
sem=validate_response(report['raw_response'],units,report['model'],reference_only=True)
sem.usage=report['usage']
result=assemble_autofill(base.facts+sem.facts,base.warnings+sem.warnings,base.rows)
expected=json.loads((ROOT/'outputs/realistic_emr_challenge/review/ANSWER_KEY.json').read_text())['form_fields']
def comparable(field,value):
    if not value:return ''
    if field=='Presciber Name and Mailing Address':
        first,*rest=value.splitlines()
        first=re.sub(r'^Dr\.?\s+','',first,flags=re.I)
        first=re.sub(r',?\s+(?:MD|FRCPC)(?:\s+(?:MD|FRCPC))*$','',first,flags=re.I)
        value=' '.join([first]+rest)
    return re.sub(r'[^a-z0-9]','',value.casefold())
checks={k:{'expected':v,'before':base.values.get(k,''),'after':result.values.get(k,''),
           'before_exact':base.values.get(k,'')==v,'after_exact':result.values.get(k,'')==v,
           'before_format_normalized':comparable(k,base.values.get(k,''))==comparable(k,v),
           'after_format_normalized':comparable(k,result.values.get(k,''))==comparable(k,v)}
        for k,v in expected.items()}
assert not result.identity_conflict
pdf=export_official_draft(result.values,result.facts)
(OUT/'actual_local_ai_5328_draft.pdf').write_bytes(pdf)
reader=PdfReader(BytesIO(pdf));fields=reader.get_fields()
for k in expected:assert str(fields[k].get('/V',''))==result.values.get(k,'')
for a in reader.pages[0]['/Annots']:
    widget=a.get_object();name=widget.get('/T')
    if name in expected:
        assert str(widget.get('/V',''))==result.values.get(name,'')
        assert widget.get('/AP',{}).get('/N')
doc=pymupdf.open(stream=pdf,filetype='pdf')
for i,page in enumerate(doc):
    if i<2:page.get_pixmap(matrix=pymupdf.Matrix(1.2,1.2)).save(ROOT/f'work/semantic/draft_preview_{i+1}.png')

# Display replay uses the actual recorded model result, not a hand-authored answer.
at=AppTest.from_file(str(ROOT/'app.py'),default_timeout=60).run()
at.checkbox[0].check().run();at.selectbox[0].select('Challenge / mixed EMR packet (7 files)').run()
revision=hashlib.sha256(b''.join((ROOT/'src'/name).read_bytes() for name in
    ['extractor.py','demographics.py','prescriber.py','document_text.py','semantic.py','models.py','layout_tables.py','official_form.py','autofill.py'])).hexdigest()
batch=hashlib.sha256(b''.join(p.name.encode()+p.read_bytes() for p in paths)+revision.encode()+report['model'].encode()).hexdigest()
at.session_state['semantic_'+batch]=sem
at.run();assert not at.exception,at.exception
assert next(x for x in at.text_area if x.label=='Prescriber name and mailing address').value==result.values['Presciber Name and Mailing Address']
report.update({'form_checks':checks,'candidate_facts':[asdict(f) for f in sem.facts],
               'warnings':sem.warnings,'revalidation_note':'Recorded real inference was revalidated after fixing overlapping date-token matching; final UI was replayed from that recorded result. No additional model call or answer-key substitution.',
               'source_hashes':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}})
(OUT/'verification.json').write_text(json.dumps(report,indent=2))
(OUT/'model_provenance.json').write_bytes((ROOT/'work/models/active_model.json').read_bytes())
nonempty=[v for v in checks.values() if v['expected']]
print('Final exact:',sum(x['after_exact'] for x in nonempty),'/',len(nonempty))
print('Final format-normalized:',sum(x['after_format_normalized'] for x in nonempty),'/',len(nonempty))
print('Model candidates:',len(sem.facts),'warnings:',sem.warnings)
print('Final UI replay and interactive PDF values/appearances verified.')

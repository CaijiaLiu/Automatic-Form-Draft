"""Exercise the actual local-model button and preserve observed results."""
from pathlib import Path
from dataclasses import asdict
from io import BytesIO
import json,time,re
from src.semantic import local_status
import src.semantic as semantic_module
from src.autofill import autofill_documents,assemble_autofill
from src.official_form import export_official_draft
from streamlit.testing.v1 import AppTest
import pymupdf
from pypdf import PdfReader

OUT=Path('outputs/semantic_integration_demo');OUT.mkdir(parents=True,exist_ok=True)
original_request=semantic_module._request
def recorded_request(path,*args,**kwargs):
    response=original_request(path,*args,**kwargs)
    if path=='/v1/chat/completions':
        Path('work/semantic/actual_http_response.json').write_text(json.dumps(response,indent=2))
    return response
semantic_module._request=recorded_request
for _ in range(30):
    status=local_status()
    if status.get('ready'):break
    time.sleep(1)
assert status.get('ready'),status
print('Local model ready:',status['model'],flush=True)
at=AppTest.from_file(str(Path('app.py').resolve()),default_timeout=900).run()
at.checkbox[0].check().run()
at.selectbox[0].select('Challenge / mixed EMR packet (7 files)').run()
assert not at.exception,at.exception
button=next(b for b in at.button if b.label=='Read all files with local AI')
start=time.monotonic();print('Starting real model inference through the UI.',flush=True)
button.click().run(timeout=900)
elapsed=time.monotonic()-start
assert not at.exception,at.exception
states=at.session_state._state.filtered_state
sem=next((v for k,v in states.items() if k.startswith('semantic_')),None)
assert sem is not None,'No local model result was stored. '+str([x.value for x in at.error])
assert sem.raw and sem.facts,'No source-grounded model candidates were accepted.'
paths=sorted(Path('outputs/realistic_emr_challenge/records').iterdir())
base=autofill_documents(paths)
result=assemble_autofill(base.facts+sem.facts,base.warnings+sem.warnings,base.rows)
expected=json.loads(Path('outputs/realistic_emr_challenge/review/ANSWER_KEY.json').read_text())['form_fields']
checks={k:{'expected':v,'before':base.values.get(k,''),'after':result.values.get(k,''),
           'before_exact':base.values.get(k,'')==v,'after_exact':result.values.get(k,'')==v}
        for k,v in expected.items()}
report={'model':sem.model,'elapsed_seconds':round(elapsed,2),'usage':sem.usage,
        'method':'Actual local model invoked through Streamlit button; independent pre-existing answer key used only AFTER inference.',
        'identity_conflict':result.identity_conflict,'form_checks':checks,
        'candidate_facts':[asdict(f) for f in sem.facts],'warnings':sem.warnings,'raw_response':sem.raw,
        'scope':'Development fixture, not an independent accuracy estimate. Quoted values are checked, clinical interpretation is not verified.'}
(OUT/'verification.json').write_text(json.dumps(report,indent=2))
print('Model candidates',len(sem.facts),'seconds',round(elapsed,1),'warnings',sem.warnings,flush=True)
print('Field checks',checks,flush=True)
assert not result.identity_conflict,'Identity conflict blocks draft export.'
pdf=export_official_draft(result.values,result.facts)
(OUT/'actual_local_ai_5328_draft.pdf').write_bytes(pdf)
saved=PdfReader(BytesIO(pdf)).get_fields()
for k in expected:assert str(saved[k].get('/V',''))==result.values.get(k,'')
doc=pymupdf.open(stream=pdf,filetype='pdf')
for i,page in enumerate(doc):
    if i<2:page.get_pixmap(matrix=pymupdf.Matrix(1.2,1.2)).save(f'work/semantic/draft_preview_{i+1}.png')
field=next(x for x in at.text_area if x.label=='Prescriber name and mailing address')
assert field.value==result.values['Presciber Name and Mailing Address']
print('Actual model result reached the UI and exported PDF; persisted fields verified.',flush=True)

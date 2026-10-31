"""Record an unchanged-parser baseline against the separately frozen answer key."""
from pathlib import Path
from dataclasses import asdict
from hashlib import sha256
import json
from src.autofill import autofill_documents

ROOT=Path('outputs/realistic_emr_challenge'); REV=ROOT/'review'
keybytes=(REV/'ANSWER_KEY.json').read_bytes()
digest=(REV/'ANSWER_KEY.sha256').read_text().split()[0]
assert sha256(keybytes).hexdigest()==digest
key=json.loads(keybytes)
paths=sorted((ROOT/'records').glob('*'))
results=[]
for path in paths:
 result=autofill_documents([path])
 results.append({'file':path.name,'identity_conflict':result.identity_conflict,'values':result.values,
                 'warnings':result.warnings,'facts':[asdict(f) for f in result.facts],
                 'rows':[asdict(r) for r in result.rows]})
 print(path.name,len(result.facts),'facts',len(result.rows),'rows',flush=True)
combined=autofill_documents(paths)
checks={name:{'expected':expected,'observed':combined.values.get(name,''),
              'exact_match':combined.values.get(name,'')==expected}
        for name,expected in key['form_fields'].items()}
observed={'answer_key_sha256':digest,'method':'Unchanged current local parser; fixture challenge, not blind accuracy estimate.',
          'identity_conflict':combined.identity_conflict,'detected_patient_names':sorted({f.value for f in combined.facts if f.category=='patient_full_name'}),
          'form_checks':checks,'clinical_review':'No automated clinical correctness score. Inspect facts/rows against event-level answer key, including dates, status and specimen correction. A keyword/value occurrence alone is not success.',
          'files':results,'combined_facts':[asdict(f) for f in combined.facts],
          'combined_warnings':combined.warnings}
(REV/'OBSERVED_BASELINE.json').write_text(json.dumps(observed,indent=2))
filled=[(k,c) for k,c in checks.items() if c['expected']]
lines=['# Observed baseline on the harder EMR packet','',
       f'Answer key SHA-256: `{digest}`','',
       f'Identity merge blocked: {combined.identity_conflict}.',
       f'Exact matches among nonempty expected form fields: {sum(c["exact_match"] for _,c in filled)} / {len(filled)}.',
       'This is a deliberately difficult development fixture, not an independent model benchmark. Empty requested-drug/regimen fields are reported separately and do not inflate the nonempty-field result.','',
       '| Form field | Expected | Observed | Match |','| --- | --- | --- | --- |']
for name,c in checks.items():
 expected=c['expected'].replace('\n',' / ') or '(blank / Requires Review)'
 actual=c['observed'].replace('\n',' / ') or '(blank)'
 lines.append(f'| {name} | {expected} | {actual} | {c["exact_match"]} |')
lines+=['','## Document processing','', '| File | Candidate facts | Recognized table rows |','| --- | ---: | ---: |']
for r in results:lines.append(f'| {r["file"]} | {len(r["facts"])} | {len(r["rows"])} |')
lines+=['','## What still needs human assessment','',
 '- Correctly linking each CBC result to the collection date and specimen; no credit for finding a number alone.',
 '- Replacing preliminary 22 with amended final 18 for D26-0514; no false extra visit.',
 '- Combining the two actual IVIG administrations into one course, excluding the cancelled rituximab proposal.',
 '- Separating tablet strength from prescribed daily dose; retaining uncertain prednisone stop date.',
 '- Inferring the applicant from the signed-off clinician context and first-person plan, while excluding the referral recipient and discharge author.',
 '- Associating the latest clinic contact with the applicant across files, without using the old office or patient contact.',
 '- The current rules do not implement general semantic event resolution or robust cross-document role association. Missing rows or a plausible-looking paragraph do not demonstrate successful recognition.','',
 'Full evidence, warning messages and unedited candidates are in OBSERVED_BASELINE.json. Application extraction code was not changed for this packet.']
(REV/'BASELINE_RESULTS.md').write_text('\n'.join(lines))
assert sha256((REV/'ANSWER_KEY.json').read_bytes()).hexdigest()==digest
print('Nonempty form fields:',sum(c['exact_match'] for _,c in filled),'/',len(filled),flush=True)
print('Identity conflict:',combined.identity_conflict,flush=True)

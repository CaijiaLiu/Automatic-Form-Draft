# AI-Assisted ITP Drug Access Application Tool — local MVP

This is a **synthetic-data-only demonstration**, not a clinical device, medical advice, a real application form, or a submission integration. Record processing stays local. Optional AI uses a loopback-only model service; setup downloads public reference files/model weights separately. No hosted AI service receives records.

## Fresh clone setup

Use Python 3.11 or newer. The repository includes code and authored synthetic EMR packets.
The setup unpacks the authored sample archive without changing source file bytes.
Third-party PDFs and the official blank form are downloaded separately from their
publishers, with SHA-256 verification; a changed upstream file is rejected.

```bash
git clone https://github.com/CaijiaLiu/Automatic-Form-Draft.git
cd Automatic-Form-Draft
python3 scripts/fetch_reference_files.py
```

This setup step accesses public document URLs only; it does not upload any records.
See `THIRD_PARTY_NOTICES.md`. After setup, the local app works without external AI.
The default **Demo / simple Section 1 + clinical packet (6 files)** uses Clara Morales
(first name Clara, last name Morales). Its upload files are in
`outputs/new_emr_sample_04_simple_section1/UPLOAD_ONLY`. The separate
`sample_data/clara_morales_upload_only.zip` contains those six files only.

Four additional fictional patients with different treatment histories and platelet
trajectories are under `outputs/ITP_Sample_Library` after setup. Upload one patient
folder at a time. Internal review/answer folders remain local and are excluded
from the published sample archive. `sample_data/itp_sample_library_upload_only.zip` contains the four upload
folders without answers. All new fixtures have simple first/last-name fields and
labelled prescriber contact panels. Identity/contact prefill was checked; these
authored fixtures are not independent clinical accuracy benchmarks.

The older `outputs/new_emr_sample_03/records` packet is also retained;
review answers remain local and are excluded from this repository archive. Sample 03 shares the clinical
course/layout with sample 02 and is not an independent clinical validation case.
Model weights, caches, generated exports and historical audit screenshots are
excluded. Some historical artifact paths below refer to local development outputs
and are not shipped; included generation/evaluation scripts remain under `work/`.

## Run

In Terminal, open this project folder and run either of these options.

**Simplest (macOS):**

```bash
zsh run_demo.sh
```

**Manual:**

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m streamlit run app.py --server.headless=true --server.address=127.0.0.1 --server.port=8503 --browser.gatherUsageStats=false
```

Streamlit will print a local address such as `http://127.0.0.1:8503`; open that address in your browser. Keep that Terminal window running while using the demo. If `python3` is not found, install a current Python 3 release first.

Upload `sample_data/mock_itp_record.txt` first. You can also upload multiple PDF, DOCX, CSV, TXT, PNG, or JPG mock files for the same fictional patient. Files are processed only in the local app process.

## Background startup (this Mac)

After first-time dependency/reference setup, run:

```bash
.venv/bin/python scripts/start_background_demo.py
```

This starts the web app detached from Terminal at `http://127.0.0.1:8503` and,
when local model weights are already installed, starts the optional local model.
Logs and process IDs are under `work/runtime/`. Closing Terminal does not stop
these detached services. A computer restart does stop them; this is not a login
service or a public hosting setup. Optional model startup requires llama.cpp.

## What it does

1. Extracts diagnosis, named medication/treatment, dose, date, platelet count, and response with transparent regular-expression rules.
2. Displays a structured evidence timeline. Every fact records filename, page/paragraph/row/line location, and the source text.
3. Builds an **example only** editable access-application draft. Missing or unsafe-to-infer values are marked `Requires Review`.
4. Exports an explicitly watermarked/labelled PDF draft.

## OCR

Image OCR is best-effort. Install the system Tesseract executable plus `pytesseract` if desired; otherwise image uploads visibly report that no OCR is available. OCR is intentionally not used to make clinical conclusions.

## Official BC HLTH 5328 draft

The default application tab now prefills the user-selected official blank PDF
from https://www2.gov.bc.ca/assets/gov/health/forms/5328fil.pdf (printed revision
2019/09/30). The original stays unchanged in `assets/`.

Upload synthetic records or load the sample, then open **BC HLTH 5328 draft**.
Diagnosis, therapies mentioned, doses, platelet results and responses are proposed
in Supporting Details with E-number references. Review and edit this text. The
rule extractor does not reliably interpret negation, medication status, date
context, units or conflicts, and separate dose facts are not automatically linked
to a specific medicine. No drug is selected or recommended by the tool.

Patient names, DOB, explicitly labelled BC PHN/licence and prescriber contacts
now prefill when supported by source evidence. Name splitting is a reviewable
last-token-surname heuristic. Conflicting values and ambiguous dates remain
blank. Medicare and overseas provider IDs are not mapped to BC identifiers.
Only an explicit prescribing role can populate prescriber identity; a ward author
or referral recipient is not assumed to be the prescriber. Missing fields are
listed as Requires Review in the separate internal evidence report; source evidence is shown per field.
Application date uses an explicit source application date when available;
otherwise it defaults to draft creation date in America/Vancouver, clearly
labelled as generated and editable. Requested agent/regimen remains manual.
Request type, licence type and indication checkboxes require explicit selection.
The review checkbox is only a demo review marker, not signature or consent.

Download the application draft and internal evidence report separately. The draft
retains the actual fillable fields and official layout, with synthetic-draft markings.
The evidence report preserves source filename/location and original evidence. Signature,
consent and PharmaCare-only areas are not completed. The original example
template exporter remains in the source package. The UI now presents one official
form workflow with source/evidence tabs rather than separate example-form flows.

This is a template-prefill demo, not verification of the latest payer criteria,
eligibility, or the appropriate form for a particular medicine. No submission is
performed.

## Independent public synthetic document evaluation

The app includes unchanged external PDFs from Jack Webb / Root Cause Analytics:
https://huggingface.co/datasets/RootCauseAnalytics/synthetic-australian-medical-documents-sample
Their dataset card states that all entities are synthetic. Licence: CC-BY-NC 4.0
for non-commercial evaluation; do not reuse this test dataset commercially without
appropriate rights. The data is Australian and is not an ITP eligibility dataset.

Pinned source revision and per-file SHA256 hashes are in
`sample_data/public_external/provenance.json`. App extraction never reads the
publisher ground-truth labels. Test PDFs are selected individually under Demo
source; do not combine different fictional patients. Native and scan versions
are alternate versions of the same records, not extra independent patients.

Reproduce the audit with `.venv/bin/python work/evaluate_public_samples.py`.
`outputs/public_document_evaluation/evaluation.md` reports correct, missing and
incorrect name/DOB fields, limitations and individual errors. The initial frozen
audit is preserved in `evaluation_initial.md`: it exposed OCR header leakage
into a surname. A general boundary guard was added afterward, so the current
report is a regression evaluation, not an untouched hold-out claim. The scores
are not measurements of general clinical or ITP extraction accuracy.

The built-in ITP demo additionally loads `mock_patient_context.txt`, a clearly
fictional narrative containing demo identity/prescriber details. These local
fixtures are kept separate from the external evaluation.

## Document parsing updates

- Metadata can span line breaks; patient name and DOB also accept a narrow set
  of prose patterns. Exact source spans are retained.
- DOCX paragraphs and table rows are read in document order.
- PDF pages without readable text are rendered locally and passed to Tesseract.
  Install the Tesseract system executable for OCR; Python dependencies are in
  requirements.txt. OCR candidates remain reviewable and may be wrong or missing.
- Selected narrative treatment/platelet patterns are supported; this is still
  rule-based extraction, not arbitrary prose understanding. Event dates are no
  longer borrowed automatically from the first date elsewhere on a page.
- Multiple recognized patient identities block combined application output.
  This is not a complete patient-identity verification system.

## Original public CBC and patient-chart layouts

The default loaded sample is now an unchanged public CBC PDF, rather than a
locally authored text fixture. `sample_data/public_layouts/catalog.json` records
the public source URLs and sample/fictional status for five original documents:

- Testing.com CBC teaching example with separate normal/abnormal result columns.
- Labcorp's official test 005009 six-page sample report bundle, with current and
  previous result columns and three separate example patients.
- Quest's watermarked sample CBC hosted by Ulta Lab Tests, an image-only PDF.
- Root Cause Analytics' public synthetic medication chart with daily signature
  columns and a separate PRN table (CC-BY-NC 4.0).
- The same publisher's two-page synthetic discharge history, including an
  admission panel, narrative course and discharge medication/dose/notes table.

In **Demo source**, select an entry beginning with **Layout /**. Original pages
are rendered unchanged alongside coordinate-based table candidates. Select a row
to inspect its source crop, page, table/row number and bounding box. The row JSON
retains empty columns, date roles, raw source cells and OCR/review labels.

CBC table candidates preserve current values separately from reference intervals
and historical columns. An explicitly recognized platelet row takes precedence
over flattened text (e.g. a superscript lab footnote `01` is not a count).
Medication candidates keep dose, frequency, notes and signature-day cells linked
to the same row. Signature initials are not interpreted as administrations; a
discharge date is not a medication start date. The entire chart narrative is not
claimed to be understood. Multi-patient sample bundles can be inspected but are
blocked from combined application generation.

These files are development/regression cases, not untouched validation samples.
Only the explicitly tested row/column associations are asserted; candidate row
counts are not accuracy scores. Header/coordinate rules do not guarantee arbitrary
merged cells, unknown formats, handwriting or multi-page table continuation.

Tests: `.venv/bin/python -m pytest -q tests/test_layout_tables.py`.
Source hashes, row evidence and Chinese review notes:
`.venv/bin/python work/evaluate_layouts.py`.
Public originals and provenance are packaged in
`outputs/public_cbc_chart_layout_samples.zip` for local review. Preserve publisher
notices and the non-commercial limitation of the CC-BY-NC sample materials.

## Unified upload to automatic form workflow

Upload multiple source files for one fictional patient. The first tab,
**Auto-filled Application**, immediately shows source-backed prefilled fields and a live
preview of the actual exported HLTH 5328 PDF. No copying from the extraction table
is needed. Edits update the PDF on the normal Streamlit input commit/rerun.
The preview column provides two independent exports: **Download Application Draft
Only** (the original, editable one-page HLTH 5328 draft) and **Download Internal
Evidence Report** (edited values, extracted proposals, source evidence and review
notes). A preview selector switches between them. The internal report is never
automatically appended to the application.

Application summaries contain no generated internal E-number references. If
supporting details exceed the form's visible space, the app asks the clinician to
shorten the summary instead of silently truncating it or referring to an attached
internal appendix. The evidence report remains downloadable with the full text,
even when the application cannot yet be exported. Both exports reflect the current
edits and selections; the report marks edits that differ from extracted proposals.
This split does not determine which clinical attachments a real payer requires.

The other tabs are **Original Files & Tables** (original pages and linked rows) and
**Field Sources & Review** (per-field proposals, missing/conflicting values, all evidence).
Recognition and prefill use one pipeline in `src/autofill.py`. Explicitly different
names or DOBs block combined proposals and PDF export; source inspection remains
available. This is still not complete patient-identity verification.

Requested medicine and regimen are clinician-entry fields and never automatically
prefill, even if a source mentions a selected request. Source mentions remain in
the evidence for review. Clinicians can enter their confirmed choices in the web
form and export them. Signatures/consent are not automated.

The default public CBC now demonstrates comma-format identity extraction
(`Doe, John Q.`) plus the linked platelet row reaching the real official PDF
fields. The single-source original sample is not combined with another sample's
patient. To generate its demonstrator export: `.venv/bin/python
work/make_unified_cbc_demo.py`.

## Tests

### Local semantic recognition (optional LLM)

The default workflow is fast native-text/table prefill, with no model call and no
scan OCR. Registration-cell labels and conservative explicit application-intent /
single-clinician sign-off associations add source-linked candidates. Unknown or
ambiguous layouts still need review; this is not general document understanding.

Under **Optional scans and missing-field review**, choose only unresolved identity
or clinician fields and click **Check selected missing fields in background**.
The default selection is at most three fields. The draft remains editable and
exportable during review. Completed suggestions show their source evidence and
require an explicit **Apply selected suggestions to empty fields** action.
Existing entries and manually cleared fields are not silently overwritten.
Model suggestions never populate medicine or dose/regimen fields.

**Read deferred scans in background — no AI** runs local OCR/rules separately.
The user can add its candidates to the review evidence; the clinical summary is
not silently rewritten. Scanned results are deferred, not assumed absent.

The optional AI pass retrieves relevant verbatim passages and
table cells across the selected files, then sends this bounded context to a local
llama.cpp server at `http://127.0.0.1:8081`, requests schema-constrained candidate
facts, resolves cited source IDs to the original text, checks extractive values, and combines accepted
candidates with the rule pipeline before proposing the form. The API route rejects
external origins, bypasses proxy environment variables and refuses redirects.
No hosted AI provider, API key or automatic cloud fallback is configured.

For the small local model, only selected missing application questions are asked one field at a time
over a shared cross-document context. The server reuses the common prompt prefix.
This controls output duplication; it does not require source documents to use
one-field-per-line labels. Printed source values can be marked supported without
being clinically verified; ambiguous associations are withheld. Model-generated
placeholders such as the string "null" are treated as missing, not field values.
The default pass does not infer an application date from a dated clinical letter.

The model phase has a 90-second batch budget; OCR and source preparation are
separate and may take longer. Reaching the budget leaves unresolved fields for
manual entry, not guesses. Only one background job runs at a time on this local
machine, preventing a queue of competing model jobs. Completed results are cached
for the same input/model/selection/version. Case content hashes isolate jobs and
stable form keys preserve edits when a job finishes. Model failure does not
prevent using the fast draft. This improves waiting time without claiming a small
CPU model itself has become faster or more accurate.

Development timings for the two authored mock packets are in
`outputs/fast_workflow_review/performance.json`. They measure the native fast path,
exclude deferred OCR/clinical interpretation, and are not production SLAs or blind
accuracy results. The packets have now been used for parser development.

The default model is Qwen3-1.7B, locally converted from the publisher's pinned
Q8_0 weights to Q4_K_M for this 8 GB M1 machine. The smaller model and requantization
can reduce accuracy. This is a feasibility demo, not a claim that this model is
adequate for clinical document interpretation. Larger models can replace it on
appropriate hardware, but require re-evaluation. CPU inference can take several
minutes. Cached results are reused when the same files/model/parser are unchanged.

Setup (llama.cpp, including `llama-server` and `llama-quantize`, must be installed):

```bash
.venv/bin/python setup_local_ai.py
./run_local_ai.sh
# In another terminal:
./run_demo.sh
```

The setup downloads only public model weights (~1.83 GB), checks the publisher's
SHA-256, and prepares the compact local weight file. It never reads record files.
Source revision: `Qwen/Qwen3-1.7B-GGUF@90862c4b9d2787eaed51d12237eafdfe7c5f6077`.
The source and local quantized file hashes are recorded in
`work/models/active_model.json`. Model weights and scratch model logs are ignored
by Git. Do not publish the scratch directory as a patient-data store.

In the app, select/upload the same patient's records and click the local-AI
button. The model receives only those files, never review answer keys. Native
table content is supplied once with its cell boundaries, not duplicated in
flattened page text. Context limits are checked; records/output are not silently
truncated. The model result is cached in memory (not persisted to disk by the UI).
Original source text, file/page references and review notes accompany candidates.
The application pass returns compact values/status/source IDs; software copies
evidence directly rather than asking the model to reproduce long quotes. This
reduces token generation and model-authored citation errors. IDs still do not prove
the clinician-role or column association is correct.
Discussion/cancelled/superseded facts do not become treatment requests or completed
therapies; uncertain identity/contact associations are withheld from the form.
Missing values remain missing. Model failures keep the rule-only result with an
explicit message. An existing patient-identity conflict blocks model-assisted merging.

Quote/value validation proves source presence, not correct medical interpretation,
correct column association, complete recall or correct clinician role. All proposed
values require manual verification. A model output and its own explanation are
not independent corroboration. The model has no tools, EMR access or submission
capability. Real patient processing remains out of scope.

Programmatic fast path: `autofill_documents(paths, fast=True)`. With
`semantic=True`, only unresolved identity/clinician categories are queried; when
none remain the model is not contacted. Defaults without `fast=True` retain full
local OCR for regression checks. `work/run_semantic_demo.py` and the recorded
semantic integration outputs document the earlier blocking UI experiment; their
old button sequence is historical, not the current fast-first workflow.

### Structure recovery is separate from clinical interpretation

Unknown native PDF tables now fall back to geometric table detection, without
requiring a known clinical header. Unknown CSV schemas retain their columns,
quoted values, empty cells and source row numbers. These rows have kind
`unmapped_table`, preserve source coordinates where available, and are displayed
with an explicit warning. They never become clinical facts or form values until
a supported mapping exists. Screenshot/image-only tables still need a layout/OCR
engine; geometric PDF table detection does not solve them.

The mixed-EMR packet's frozen original baseline remains in
`outputs/realistic_emr_challenge/review/OBSERVED_BASELINE.json`.
`AFTER_STRUCTURE_ONLY.json` records the structural recovery improvement separately;
it must not be presented as improved clinical accuracy. No training or learning
occurs when sample files are uploaded. More realistic mocks improve test coverage;
they affect recognition only through subsequent validated parser/model changes.
Evaluate new template families and patients separately from development examples.

### Prescriber recognition across pages

The local reader now reconstructs native PDF and OCR words in visual row order.
This reduces label/value separation in two-column forms. Explicit prescribing
roles, multiline Canadian mailing addresses, and role-associated contacts are
resolved across all pages of each file. A clinic letterhead address can be proposed
for a single explicit prescriber on another page when there is no competing
ordering/referring/consulting role. Conflicting addresses remain blank. Patient
addresses, patient contacts, document authors, and ordering/referring doctors are
not automatically used as the applicant. Raw source lines and page references
remain attached, including any OCR postal-code letter/digit normalization.

This is an improved local extraction pipeline, not an LLM or general document
understanding model. It cannot establish a doctor's practice affiliation or infer
which physician is applying when roles are ambiguous. Cross-page association is
within a file; an unlabelled clinic on an unrelated uploaded file is not linked.
Mixed native-text/image pages can still omit text inside screenshots. Handwriting,
complex interleaved columns, low-resolution scans and unusual labels remain limitations.

Use **Load a demo sample → Mock identity / prescriber on separate pages**
(or **separate-page scan**) to test the document-wide association. The original
mock CBC PDF/scan are also selectable. The selector includes both public and
locally generated synthetic samples. Parser changes invalidate the cached results
and form editor keys automatically.

```bash
pytest -q
```

## Limitations and safety boundaries

- Rules are brittle: wording, tables, dose units, dates, and negation are not fully understood.
- PDF extraction and OCR can fail or misread scans; OCR-derived candidates are explicitly marked for review.
- It flags some conflicting identity fields but does not fully resolve patient identity, deduplicate facts, detect all clinical conflicts, recommend a medicine, calculate eligibility, authenticate users, encrypt data, audit access, or validate a clinician's judgment.
- `Requires Review` is not a safety guarantee. Clinical personnel must verify every extracted fact and author all clinical rationale.
- Do not upload real patient information. No EMR/FHIR, PharmaCare, or production deployment is included.

## Section 3 local AI draft (demo update)

The application now provides **Generate & auto-fill Section 3 with local AI**.
Start the optional local model using `zsh run_local_ai.sh`; default text/table
prefill still works when the model is unavailable. A focused native-text retrieval
step chooses a small, explicitly limited subset of relevant clinical excerpts.
The local model selects excerpt IDs for diagnosis, actual prior treatment,
response, explicitly documented contraindications and review issues. Software
copies the original wording into an editable Supporting Details draft, rather than
accepting new model-written clinical claims. This is extractive organization, not
clinical reasoning or a verified medical summary. Scan-only pages remain deferred.

Generation runs in the same single background worker as identity/OCR review.
Untouched Supporting Details autofills when a result completes; manual edits are
preserved and replacement requires a separate button. Existing patient and
prescriber fields are not modified. Request medicine and regimen remain manual.
Source filename, page/block/table position and original excerpts are shown beside
the suggestion and included in the separate Internal Evidence Report when applied.

Only whole excerpts that fit the official form are inserted. Omitted excerpts
remain visible with a warning and in the report; no clinical sentence is silently
shortened. Uncertainty excerpts stay in the review panel rather than becoming an
asserted application statement. The model can still choose or classify the wrong
passage, omit important facts or miss a conflict; source presence is not proof of
clinical correctness. A missing contraindication selection does not mean none
exist. Every draft needs human review. The inference request has a 150-second
limit; native-source preparation is separate. CPU speed varies significantly.

Tests include invalid-citation rejection, preserving negation and cancelled-order
wording, PDF export, single-worker behavior and simulated UI edit preservation.
A simulated UI test is not evidence of local-model clinical accuracy.


## Latest verification

The current update passed 68 automated tests, including recovery from an older
imported background-worker module after a Streamlit code update. Real local AI
completion on the development sample and its exported PDF field text were checked.
The successful CPU run took 137.52 seconds; earlier attempts timed out. This is
feasibility evidence, not a speed target or a clinical accuracy result.

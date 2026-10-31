# Third-party documents and model weights

Third-party PDFs are not redistributed in this repository. Run
`python3 scripts/fetch_reference_files.py` to obtain the public references locally.
The manifest pins the locally evaluated file hashes. Public availability does not
transfer ownership or grant permission for commercial reuse.

- BC Ministry of Health: official blank HLTH 5328 form, printed revision 2019/09/30.
  https://www2.gov.bc.ca/assets/gov/health/forms/5328fil.pdf
  Used only as a synthetic draft demonstration target, not a submission service.
- Testing.com, Labcorp, and Quest Diagnostics / Ulta Lab Tests: public sample CBC
  reports. Publisher URLs and descriptions: `sample_data/public_layouts/catalog.json`.
  No blanket redistribution or commercial licence is asserted.
- Jack Webb / Root Cause Analytics: synthetic Australian medical documents,
  CC BY-NC 4.0. Non-commercial evaluation only. Source, revision and hashes are in
  `sample_data/public_external/provenance.json`; the publisher dataset card is
  preserved in that directory's README. Licence:
  https://creativecommons.org/licenses/by-nc/4.0/
- Optional Qwen3-1.7B weights are not included. The separate setup script downloads
  the pinned publisher release and requantizes it locally. Consult the publisher's
  model licence and model card before reuse.

The authored records in `outputs/*/records` are fictional development fixtures,
not real charts or independent validation data. Uploading examples does not train
the model. No general licence over third-party materials is granted by this repo.

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.extractor import extract_files
from src.official_form import propose_fields, export_official_draft

facts, _ = extract_files([ROOT / 'sample_data' / name for name in ['mock_itp_record.txt','mock_patient_context.txt']])
values = propose_fields(facts)
# Source-backed synthetic identifiers and prescriber contacts are populated;
# requested medicine/regimen and signature remain unspecified.
out = ROOT / 'outputs' / 'synthetic_bc_5328_draft.pdf'
out.write_bytes(export_official_draft(values, facts))
print(out)

from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from src.autofill import autofill_documents
from src.official_form import export_official_draft

result=autofill_documents([ROOT/'sample_data'/'public_layouts'/'testing_cbc.pdf'])
assert not result.identity_conflict
path=ROOT/'outputs'/'unified_cbc_autofilled_draft.pdf'
path.write_bytes(export_official_draft(result.values,result.facts))
print(path)

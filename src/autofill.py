"""One pipeline: source documents -> linked facts -> proposed form values."""
from dataclasses import dataclass
from pathlib import Path

from .models import Fact
from .layout_tables import LayoutRow,extract_with_layout
from .official_form import propose_fields,field_reviews

@dataclass
class AutofillResult:
    facts: list[Fact]
    warnings: list[str]
    rows: list[LayoutRow]
    values: dict[str,str]
    reviews: dict
    identity_conflict: bool

def assemble_autofill(facts: list[Fact], warnings: list[str], rows: list[LayoutRow]) -> AutofillResult:
    names={f.value.casefold() for f in facts if f.category=='patient_full_name'}
    births={f.value.casefold() for f in facts if f.category=='patient_dob'}
    conflict=len(names)>1 or len(births)>1
    # Do not even propose a combined application if explicit identities disagree.
    return AutofillResult(facts,warnings,rows,{} if conflict else propose_fields(facts),
        {} if conflict else field_reviews(facts),conflict)

def autofill_documents(paths: list[Path], *, semantic: bool = False, fast: bool = False) -> AutofillResult:
    facts=[];warnings=[];rows=[]
    for path in paths:
        extracted,notes,linked_rows=extract_with_layout(path,allow_ocr=not fast)
        facts.extend(extracted);warnings.extend(notes);rows.extend(linked_rows)
    base=assemble_autofill(facts,warnings,rows)
    if semantic and not base.identity_conflict:
        from .semantic import local_status,recognize,missing_categories
        targets=missing_categories(base)
        if not targets:return base
        status=local_status()
        if status.get('ready'):
            candidates=recognize(paths,rows,status['model'],targets=targets)
            return assemble_autofill(facts+candidates.facts,warnings+candidates.warnings,rows)
        base.warnings.append(status['detail'])
    return base

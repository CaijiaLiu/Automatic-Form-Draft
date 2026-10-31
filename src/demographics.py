"""Conservative document-wide demographic candidates with exact source spans.

Labels may be separated from values by line breaks. Narrative patterns are
independent of the local mock fixture. Name splitting remains a reviewable
heuristic; foreign identifiers are never converted to BC identifiers.
"""
from __future__ import annotations

import re
from datetime import datetime

from .models import Fact

DATE_TOKEN = r'(?:\d{4}[-/]\d{2}[-/]\d{2}|\d{1,2}[/-]\d{1,2}[/-]\d{4}|\d{1,2}\s+[A-Za-z]+\s+\d{4}|[A-Za-z]+\s+\d{1,2},?\s+\d{4})'
NAME = r"[A-Z][A-Za-z'’.-]*(?:[ \t]+[A-Z][A-Za-z'’.-]*){1,4}"

def normalise_date(value: str, text: str = '') -> tuple[str, str]:
    value = value.strip()
    for fmt in ('%Y-%m-%d', '%Y/%m/%d', '%d %B %Y', '%d %b %Y', '%B %d, %Y', '%B %d %Y'):
        try:
            return datetime.strptime(value, fmt).strftime('%Y/%m/%d'), ''
        except ValueError:
            pass
    match = re.fullmatch(r'(\d{1,2})[/-](\d{1,2})[/-](\d{4})', value)
    if match:
        a, b, y = map(int, match.groups())
        if a==b:
            d,m,reason=a,b,''
        elif a > 12 or re.search(r'\b(?:NSW|Australia|Australian|date format\s*:?\s*DD/MM/YYYY)\b', text, re.I):
            d, m = a, b
            reason = 'Requires Review: interpreted D/M/Y using document locale.' if a <= 12 else ''
        elif b > 12:
            m, d, reason = a, b, ''
        else:
            return '', 'Requires Review: ambiguous numeric date; date order unknown.'
        try:
            return datetime(y, m, d).strftime('%Y/%m/%d'), reason
        except ValueError:
            pass
    return '', 'Requires Review: invalid or unsupported date.'

def demographic_facts(text: str, filename: str, location: str, *, document_context: str = '', include_prescriber: bool = True) -> list[Fact]:
    results: list[Fact] = []
    context = document_context or text

    def add(category, value, match, reason=''):
        first = text.count('\n', 0, match.start()) + 1
        last = text.count('\n', 0, match.end()) + 1
        evidence = text[match.start():match.end()].strip()
        fact = Fact(category, value.strip(), 'Requires Review', filename,
                    f'{location}, lines {first}-{last}', evidence, reason)
        if not any(f.category == category and f.value == fact.value and f.evidence == evidence for f in results):
            results.append(fact)

    # Explicit family/given labels can be present in forms and prose alike.
    for category, label in [('patient_family_name', r'(?:patient\s+)?(?:family name|surname|last name)'),
                            ('patient_given_name', r'(?:patient\s+)?(?:given names?|first names?)')]:
        for m in re.finditer(r'(?im)\b' + label + r'\s*[:=]\s*([^\n|;]+)', text):
            add(category, m.group(1).strip(), m)

    for m in re.finditer(r"(?m)\b(?:Patient Name|Name)\s*:\s*([A-Z][A-Za-z'’.-]+),\s*([A-Z][A-Za-z'’.-]*(?:[ \t]+[A-Z][A-Za-z'’.-]*){0,3})",text):
        family,given=m.group(1),m.group(2)
        given=re.split(r'\s+(?:Age|Sex|DOB|MRN)\b',given)[0]
        add('patient_full_name',given+' '+family,m)
        add('patient_family_name',family,m)
        add('patient_given_name',given,m)

    name_patterns = [
        r'(?im)^\s*(?:Patient\s+Name|Patient|Name)\s*:?\s*\n\s*(' + NAME + r')',
        r'(?m)\b(?:Patient\s+[Nn]ame|Patient|Name)\s*[:=]\s*(?:\|\s*)?(' + NAME + r')',
        r'(?m)^\s*RE:\s*\n?\s*(' + NAME + r')',
        r'\b(' + NAME + r')\s*\(\s*(?:born|DOB|date of birth)\b',
    ]
    for expression in name_patterns:
        for m in re.finditer(expression, text):
            name = re.sub(r'\s+', ' ', m.group(1)).strip()
            # OCR may concatenate adjacent column headers into a name. Retain
            # the original evidence but never treat these labels as a surname.
            name = re.split(r'\s+(?:MRN|DOB|PHN|Sex|Address|Phone|Medicare)\b',name)[0].strip()
            # A caption/header is not a patient name.
            if any(x in name.lower() for x in ['date of', 'medical record', 'synthetic training']):
                continue
            add('patient_full_name', name, m)
            parts = name.split()
            if len(parts) >= 2:
                reason = 'Requires Review: name split assumes final word is family name; verify name order.'
                add('patient_family_name', parts[-1], m, reason)
                add('patient_given_name', ' '.join(parts[:-1]), m, reason)

    for m in re.finditer(r'(?i)\b(?:date of birth|birthdate|DOB|born)\s*[:=]?\s*(?:\|\s*)?(' + DATE_TOKEN + r')', text):
        value, reason = normalise_date(m.group(1), context)
        add('patient_dob', value or m.group(1), m, reason)

    rules = {
        'patient_phn': r'(?i)\b(?:BC\s+)?(?:PHN|Personal Health Number)\s*[:=#]?\s*((?:MOCK[- ]PHN[- ]\d+)|(?:\d[\d -]{7,15}\d))',

    }
    for category, expression in rules.items():
        for m in re.finditer(expression, text):
            value = m.group(1).strip().rstrip('.,')
            if category in {'prescriber_phone','prescriber_fax'}:
                value = value.rstrip(' .-')
            add(category, value, m)

    if include_prescriber:
        from .prescriber import prescriber_facts
        results.extend(prescriber_facts([(location,text)],filename))

    for m in re.finditer(r'(?i)\bapplication date\s*(?:is|:|=)?\s*(' + DATE_TOKEN + r')', text):
        value, reason = normalise_date(m.group(1), context)
        add('application_date', value or m.group(1), m, reason)

    # Only an explicitly documented access request is eligible for these fields;
    # a current/historical medication row is not automatically a request.
    for category,label in [('requested_drug',r'(?:medication requested|requested (?:drug|medication))'),
                            ('requested_regimen',r'(?:dose and regimen|requested (?:dose and regimen|regimen|dose))')]:
        for m in re.finditer(r'(?im)^[ \t]*'+label+r'[ \t]*[:=][ \t]*(?:\|[ \t]*)?([^\n;|]+)',text):
            value=m.group(1).strip().rstrip('.')
            if value and not re.match(r'(?i)^(?:requires review|not (?:selected|documented|confirmed)|unknown|pending|none|undecided|n/a)\b',value):
                add(category,value,m,'Requires Review: explicit request in source; not inferred from medication history.')

    # Preserve documentary authorship independently; it is not a prescribing role.
    for m in re.finditer(r'(?im)^\s*(?:AUTHOR|CONSULTANT)\s*:?\s*\n?\s*(Dr\.?\s+'+NAME+r')', text):
        add('document_author', m.group(1).split(',')[0], m)
    return results

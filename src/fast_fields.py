"""High-precision registration-table labels; no model, fixture values or coordinates."""
import re
from .models import Fact
from .demographics import normalise_date

def label(s):return re.sub(r'[^a-z]','',s.casefold())
LABELS={'patient_family_name':{'family','familyname','legalsurname','surname','lastname','patientfamilyname','patientsurname','patientlastname'},
        'patient_given_name':{'first','firstname','givennames','givenname','firstnames','patientgivenname','patientgivennames','patientfirstname'},
        'middle':{'othergiven','othergivennames','middlename','middlenames'},
        'patient_dob':{'birthdate','dateofbirth','dob'},
        'patient_phn':{'phn','personalhealthnumber','bcphn','provincialidentifier'}}

def table_identity_facts(rows):
    out=[];groups={}
    for row in rows:
        if row.kind=='unmapped_table':groups.setdefault((row.filename,row.page,row.table),[]).append(row)
    def emit(category,value,row,evidence):
        if category=='patient_dob':
            value,reason=normalise_date(value)
            if not value:return
        elif category=='patient_phn':
            value=value.splitlines()[0].strip()
            if not re.fullmatch(r'MOCK-PHN-\d+|\d{10}',value):return
        elif not re.fullmatch(r"[A-Za-z'’.-]+(?:\s+[A-Za-z'’.-]+)*",value):return
        out.append(Fact(category,value,'Requires Review',row.filename,
            f'page {row.page}, table {row.table}, row {row.row}, bbox {row.bbox}',evidence,
            'Requires Review: explicit registration label and aligned cell; verify original table.'))
    for group in groups.values():
        if len(group)>1:
            headers=list(group[0].cells.values());values=list(group[1].cells.values());found={}
            for i,h in enumerate(headers):
                for category,aliases in LABELS.items():
                    if label(h) in aliases and i<len(values):found[category]=values[i].strip()
            # Require identity-specific headings, not an arbitrary staff directory.
            patient_context=any(label(h).startswith('patient') for h in headers) or 'patient_dob' in found or 'patient_phn' in found
            if 'patient_family_name' in found and 'patient_given_name' in found and patient_context:
                if found.get('middle'):found['patient_given_name']+=' '+found.pop('middle')
                for category,value in found.items():emit(category,value,group[1],group[0].evidence+'\n'+group[1].evidence)
            elif 'patient_phn' in found:
                header=next((h for h in headers if label(h) in LABELS['patient_phn']),'')
                if label(header)!='provincialidentifier' or found['patient_phn'].startswith('MOCK-PHN-'):
                    emit('patient_phn',found['patient_phn'],group[1],group[0].evidence+'\n'+group[1].evidence)
        for row in group:
            for cell in row.cells.values():
                lines=cell.splitlines()
                if not any(re.search(r'(?i)patient|demograph|registration',h) for h in group[0].cells.values()) and not any(label(x).startswith('patient') for x in lines):continue
                for i,line in enumerate(lines[:-1]):
                    for category,aliases in LABELS.items():
                        if category!='middle' and label(line) in aliases:
                            emit(category,lines[i+1].strip(),row,cell)
    return out

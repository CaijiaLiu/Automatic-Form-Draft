"""Header/word-coordinate table candidates, retaining column and row evidence.

No fixed page coordinates or sample values are used. Limited to recognizable
CBC and medication headers. Unrecognized tables are not silently flattened into
verified rows. These samples are development/regression cases, not a benchmark
claim for arbitrary EHR exports.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re

from .models import Fact

@dataclass
class LayoutRow:
    kind: str
    filename: str
    page: int
    table: int
    row: int
    cells: dict[str, str]
    bbox: list[float]
    evidence: str
    method: str
    event_date: str
    date_kind: str
    date_evidence: str
    subject_context: str
    review_reason: str

def _lines(words):
    result=[]
    for word in sorted(words,key=lambda w:(w[1],w[0])):
        # Use baseline bands, not PDF extraction order (often column-major).
        group=next((line for line in reversed(result[-4:]) if abs(line[0][1]-word[1])<=2.5),None)
        if group is None:
            result.append([word])
        else:
            group.append(word)
    return [sorted(line,key=lambda w:w[0]) for line in result]

def _text(words):
    return ' '.join(w[4] for w in words)

def _header(line):
    tokens=[w[4].lower().strip(':') for w in line]
    joined=' '.join(tokens)
    first=next((w for w in line if w[4].lower() in {'test','drug','medication'}),None)
    if first is None:
        # Quest uses "Test Name" as two separate words in the scan.
        return None
    if 'reference' in tokens and ('units' in tokens or 'range' in tokens or 'interval' in tokens):
        kind='cbc'
        starts={'test':first[0]}
        i=0
        while i<len(line):
            word=line[i]; token=word[4].lower().strip(':')
            if token=='normal':starts['normal']=word[0]
            elif token=='abnormal':starts['abnormal']=word[0]
            elif token=='current':starts['current_result_and_flag']=word[0]
            elif token=='previous':starts['previous_result_and_date']=word[0]
            elif token=='flag' and 'current_result_and_flag' not in starts:starts['flag']=word[0]
            elif token=='units':starts['units']=word[0]
            elif token=='reference':starts['reference']=word[0]
            elif token=='in' and i+1<len(line) and line[i+1][4].lower()=='range':starts['normal']=word[0]
            elif token=='out' and i+2<len(line) and line[i+2][4].lower()=='range':starts['abnormal']=word[0]
            elif token=='result' and not any(k in starts for k in ['normal','current_result_and_flag','previous_result_and_date']):starts['result']=word[0]
            elif token=='lab':starts['lab']=word[0]
            i+=1
        if not any(k in starts for k in ['normal','current_result_and_flag','result']):return None
    elif any(token.startswith('dose') for token in tokens) and ('drug' in tokens or 'medication' in tokens):
        kind='medication'
        starts={'medication':first[0]}
        for word in line:
            token=word[4].lower().strip(':')
            if token=='dose':starts['dose_route']=word[0]
            elif token in {'freq','frequency'}:
                if 'route' in tokens and 'notes' in tokens:
                    continue
                starts['frequency']=word[0]
            elif token=='notes':starts['notes']=word[0]
            elif token=='indication':starts['indication']=word[0]
            elif token=='doses':starts['doses_given']=word[0]
            elif token in {'sun','mon','tue','wed','thu','fri','sat'}:starts[token]=word[0]
    else:
        return None
    # Native PDF text may use a centered header; a small tolerance accommodates
    # centered values. Preserve empty cells; never shift later values left.
    ordered=sorted(starts.items(),key=lambda x:x[1])
    left=max(0,first[0]-12)
    right=max(w[2] for w in line if w[0]>=first[0]) + 12
    # A teaching PDF may have a separate prose column on the right. Once the
    # expected last header ends, exclude that unrelated panel.
    last_key,last_x=ordered[-1]
    if last_key in {'reference','lab'}:
        tail=[w for w in line if w[0]>=last_x and w[4].lower().strip(':') in {'reference','range','interval','lab'}]
        if tail:right=max(w[2] for w in tail)+12
    return kind,ordered,left,right

def _context(lines,kind):
    text='\n'.join(_text(line) for line in lines)
    # Explicit date roles only. Report/print dates are not collection dates.
    if kind=='cbc':
        match=re.search(r'(?i)(?:Date Collected|Collection Date(?:/Time)?)\s*:\s*(\d{1,4}[/-]\d{1,2}[/-]\d{2,4})',text)
        date_kind='collection date'
    else:
        match=re.search(r'(?i)Chart Period\s*:\s*([^\n]+)',text)
        date_kind='chart period (not individual administration dates)'
        if not match:
            match=re.search(r'(?i)Date Discharged\s*:\s*(\d{1,2}[/-]\d{1,2}[/-]\d{4})',text)
            date_kind='discharge date (not medication start date)'
    date=match.group(1).strip() if match else 'Requires Review'
    date_evidence=match.group() if match else 'No explicit event date found; report/print date not substituted.'
    specimen=re.search(r'(?i)(?:Specimen ID|SPEC\s*#)\s*:\s*([^\s]+)',text)
    dob=re.search(r'(?i)DOB:\s*(\d[\d/-]+)',text)
    patient=re.search(r'(?i)Patient Name:\s*([^\n]+)',text)
    subject=' | '.join(x for x in [specimen.group() if specimen else '',dob.group() if dob else '',patient.group() if patient else ''] if x)
    return date,date_kind,date_evidence,subject or 'Requires Review - patient not resolved from page header'

def _page_words(page):
    words=page.get_text('words')
    if len(words)>5:
        return [tuple(w[:5]) for w in words],'native PDF word coordinates'
    import pymupdf
    import pytesseract
    from PIL import Image
    scale=3
    pix=page.get_pixmap(matrix=pymupdf.Matrix(scale,scale),alpha=False)
    data=pytesseract.image_to_data(Image.frombytes('RGB',(pix.width,pix.height),pix.samples),
        output_type=pytesseract.Output.DICT,config='--psm 6',timeout=40)
    words=[]
    for i,text in enumerate(data['text']):
        if text.strip() and float(data['conf'][i])>=15:
            x,y,w,h=[data[key][i]/scale for key in ['left','top','width','height']]
            words.append((x,y,x+w,y+h,text.strip()))
    return words,'OCR word coordinates - verify against scan'

def _raw_csv_rows(path):
    """Keep a structured table even when its schema is unknown to clinical rules."""
    import csv
    with path.open(newline='',encoding='utf-8-sig') as source:
        records=list(csv.reader(source))
    if len(records)<2:return []
    width=max(map(len,records))
    headers=[(records[0][i] if i<len(records[0]) else '') or f'column_{i+1}' for i in range(width)]
    keys=[f'{i+1}: {h}' for i,h in enumerate(headers)]
    result=[]
    for number,record in enumerate(records[1:],2):
        cells={key:record[i] if i<len(record) else '' for i,key in enumerate(keys)}
        result.append(LayoutRow('unmapped_table',path.name,1,1,number,cells,[],
            ' | '.join(k+': '+v for k,v in cells.items()),'CSV column structure',
            'Requires Review','unmapped source schema','Date roles have not been interpreted.',
            'Requires Review - identity not resolved from table',
            'Requires Review: source columns recovered; no clinical event/status mapping applied.'))
    return result


def _geometry_rows(page,path,pageno):
    """Detect table boundaries independently of clinical header vocabulary.

    Raw cells are deliberately excluded from layout_facts: locating a table does
    not establish what a result, date, clinician or cancelled order means.
    """
    rows=[]
    for tableno,table in enumerate(page.find_tables().tables,1):
        matrix=table.extract()
        for rowno,record in enumerate(matrix,1):
            cells={f'column_{i+1}':value or '' for i,value in enumerate(record)}
            bbox=list(table.rows[rowno-1].bbox)
            rows.append(LayoutRow('unmapped_table',path.name,pageno,tableno,rowno,cells,bbox,
                ' | '.join(k+': '+v for k,v in cells.items()),'PDF table geometry (headers not interpreted)',
                'Requires Review','unmapped table','Column/date roles have not been interpreted.',
                'Requires Review - identity not resolved from table',
                'Requires Review: row/column boundaries recovered without keyword matching; includes original header rows. No clinical mapping applied.'))
    return rows


def extract_layout_rows(path: Path, *, allow_ocr=True) -> tuple[list[LayoutRow],list[str]]:
    if path.suffix.lower()=='.csv':
        try:return _raw_csv_rows(path),[]
        except Exception as exc:return [],[f'{path.name}: CSV structure could not be read ({type(exc).__name__}).']
    if path.suffix.lower()!='.pdf':return [],[]
    import pymupdf
    rows=[]; warnings=[]
    try:
        with pymupdf.open(path) as doc:
            for pageno,page in enumerate(doc,1):
                first_row=len(rows)
                if not allow_ocr and len(page.get_text('words'))<=5:continue
                try:
                    words,method=_page_words(page)
                except Exception as exc:
                    warnings.append(f'{path.name} page {pageno}: layout OCR failed ({type(exc).__name__}); Requires Review.')
                    continue
                lines=_lines(words)
                headers=[(i,_header(line)) for i,line in enumerate(lines)]
                headers=[(i,h) for i,h in headers if h]
                for tableno,(start,header) in enumerate(headers,1):
                    kind,anchors,left,right=header
                    if kind=='medication':
                        right=page.rect.width-5  # notes may extend beyond the short header label
                    end=next((i for i,_ in headers if i>start),len(lines))
                    date,date_kind,date_evidence,subject=_context(lines,kind)
                    count=0
                    for line in lines[start+1:end]:
                        cropped=[w for w in line if w[0]>=left and w[0]<right]
                        if not cropped:continue
                        text=_text(cropped)
                        if re.match(r'(?i)^(?:Flag Key|Comment:|\*\* END|Previous Result$|PRESCRIBER$|REGULAR MEDICATIONS$|PRN MEDICATIONS$|Date Created)',text):break
                        cells={name:[] for name,_ in anchors}
                        for word in cropped:
                            key=anchors[0][0]
                            for name,x in anchors[1:]:
                                if word[0]>=x-12:key=name
                            cells[key].append(word[4])
                        cells={k:' '.join(v).strip() for k,v in cells.items()}
                        if kind=='cbc':
                            result_fields=[cells.get(k,'') for k in ['normal','abnormal','current_result_and_flag','result']]
                            if not cells.get('test') or not any(re.match(r'^[<>]?\s*\d',v) for v in result_fields):continue
                        else:
                            if not cells.get('medication') or not re.match(r'^\d',cells.get('dose_route','')):continue
                        count+=1
                        bbox=[min(w[0] for w in cropped),min(w[1] for w in cropped),max(w[2] for w in cropped),max(w[3] for w in cropped)]
                        evidence=' | '.join(k+': '+v for k,v in cells.items())
                        reason='Requires Review: header/coordinate candidate; inspect original row. Blank cells retained.'
                        if kind=='medication':reason+=' Day initials are transcribed, not interpreted as confirmed administrations.'
                        rows.append(LayoutRow(kind,path.name,pageno,tableno,count,cells,[round(x,2) for x in bbox],evidence,method,
                            date,date_kind,date_evidence,subject,reason))
                if len(rows)==first_row:
                    try:rows.extend(_geometry_rows(page,path,pageno))
                    except Exception as exc:
                        warnings.append(f'{path.name} page {pageno}: generic table detection unavailable ({type(exc).__name__}).')
    except Exception as exc:
        warnings.append(f'{path.name}: layout inspection failed ({type(exc).__name__}); Requires Review.')
    return rows,warnings

def layout_facts(rows: list[LayoutRow]) -> list[Fact]:
    facts=[]
    for row in rows:
        if row.kind=='medication':
            value=' | '.join(k+': '+v for k,v in row.cells.items() if v)
            facts.append(Fact('medication',value,row.event_date,row.filename,
                f'page {row.page}, table {row.table}, row {row.row}, bbox {row.bbox}',
                row.evidence+' | '+row.date_evidence,row.review_reason+' '+row.date_kind))
            continue
        if row.kind!='cbc':continue
        test=re.sub(r'\s+\d{2}$','',row.cells.get('test','')).strip()
        if not re.fullmatch(r'(?:platelet(?:s| count)?|PLT)',test,re.I):continue
        candidates=[(k,row.cells.get(k,'')) for k in ['normal','abnormal','current_result_and_flag','result'] if row.cells.get(k)]
        if len(candidates)!=1:continue
        match=re.match(r'^([<>]?\s*\d+(?:\.\d+)?)\b',candidates[0][1])
        if not match:continue
        units=row.cells.get('units','')
        reason=row.review_reason
        if not units:
            # Some reports print the measurement unit after the reference range.
            # Preserve that derivation explicitly; do not substitute the range
            # numbers for the patient's numeric result.
            match_unit=re.search(r'\b(?:Thousand/uL|Million/uL|cells/uL|g/dL|fL|pg|K/mcL)\b',row.cells.get('reference',''),re.I)
            if match_unit:
                units=match_unit.group()
                reason+=' Unit candidate transcribed from reference column; verify against source.'
        value=match.group(1)+((' '+units) if units else ' [unit Requires Review]')
        facts.append(Fact('platelet_count',value,row.event_date,row.filename,
            f'page {row.page}, table {row.table}, row {row.row}, bbox {row.bbox}',
            row.evidence+' | '+row.date_evidence,reason))
    return facts

def extract_with_layout(path: Path, *, allow_ocr=True):
    from .extractor import extract_files
    facts,warnings=extract_files([path],allow_ocr=allow_ocr)
    rows,notes=extract_layout_rows(path,allow_ocr=allow_ocr)
    from .fast_fields import table_identity_facts
    facts.extend(table_identity_facts(rows))
    table_facts=layout_facts(rows)
    platelet_pages={int(re.search(r'page (\d+)',f.location).group(1)) for f in table_facts if f.category=='platelet_count'}
    # On a successfully recognized platelet row, prefer the coordinate-linked
    # result to a flattened-text candidate that could read a footnote as a count.
    facts=[f for f in facts if not(f.category=='platelet_count' and
        (m:=re.match(r'page (\d+)\b',f.location)) and int(m.group(1)) in platelet_pages)]
    return facts+table_facts,warnings+notes,rows

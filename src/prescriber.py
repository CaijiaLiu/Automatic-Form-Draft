"""Document-wide prescribing-role and contact association; no external services.

Candidates retain the exact source lines. Clinic letterhead may be linked across
pages only for a single explicit prescriber, with no competing clinical role.
"""
import re
from .models import Fact

ROLE = r'(?:prescribing physician|prescriber(?: name)?|requesting physician|applicant physician|prescribed by|prescription signed by)'
OTHER = re.compile(r'(?i)\b(?:patient(?:\s+(?:name|address|phone|telephone|fax))?|referring (?:physician|provider)|ordering (?:physician|provider)|consultant|recipient|cc)\s*[:=]')
STREET = re.compile(r'(?i)\b(?:P\.?\s*O\.?\s+Box\s+\d+|\d+[A-Za-z]?(?:[- /]+\d+)?\s+[^\n]{0,65}\b(?:Street|St\.?|Road|Rd\.?|Avenue|Ave\.?|Drive|Dr\.?|Lane|Ln\.?|Way|Boulevard|Blvd\.?|Highway|Hwy\.?|Parade|Court|Ct\.?|Crescent|Cres\.?))\b')
POSTAL = re.compile(r'(?i)\b[A-Z]\d[A-Z]\s?\d[A-Z]\d\b')
CONTACT = re.compile(r'(?i)\b(?:phone|telephone|tel|fax|licen[cs]e|CPSBC|CRNBC|DOB|PHN|application date|MRN)\b')
NAME = r"(?:Dr\.?\s+)?[A-Z][A-Za-z'’.-]+(?:[ \t]+[A-Z][A-Za-z'’.-]+){1,4}"


def prescriber_facts(pages, filename):
    # Retain page boundaries for evidence; windows never cross a page by accident.
    lines=[]
    for location,text in pages:
        lines.extend((location,n,s.strip()) for n,s in enumerate(text.splitlines(),1) if s.strip())
    facts=[]

    def add(category,value,indices,reason=''):
        if not value: return
        selected=[lines[i] for i in sorted(set(indices))]
        evidence='\n'.join(s for _,_,s in selected)
        if category=='prescriber_address' and any('OCR' in loc for loc,_,_ in selected):
            # A Canadian postal code alternates letters/digits. Correct only
            # unambiguous OCR confusions within a province-labelled address.
            def postal_fix(m):
                raw=m.group(2).replace(' ','').upper()
                chars=[]
                for j,c in enumerate(raw):
                    chars.append(c.translate(str.maketrans('0158','OISB')) if j%2==0
                                 else c.translate(str.maketrans('OISBZ','01582')))
                code=''.join(chars)
                if not re.fullmatch(r'[ABCEGHJKLMNPRSTVXY]\d[ABCEGHJKLMNPRSTVWXYZ]\d[ABCEGHJKLMNPRSTVWXYZ]\d',code):return m.group()
                return m.group(1)+' '+code[:3]+' '+code[3:]
            normalized=re.sub(r'\b(BC|AB|ON|SK|MB|QC|NS|NB|NL|PE|NT|NU|YT)\s+([A-Z0-9]{3}\s?[A-Z0-9]{3})\b',postal_fix,value,flags=re.I)
            if normalized!=value:
                value=normalized
                reason+=' OCR postal-code letter/digit substitutions applied; check raw evidence.'
        locations='; '.join(dict.fromkeys(f'{loc}, line {n}' for loc,n,_ in selected))
        if not any(f.category==category and f.value.casefold()==value.casefold() and f.evidence==evidence for f in facts):
            facts.append(Fact(category,value,'Requires Review',filename,locations,evidence,reason))

    names=[]
    for i,(loc,n,line) in enumerate(lines):
        m=re.search(r'(?i)\b'+ROLE+r'\s*(?:is\b|[:=])?\s*$',line)
        inline=re.search(r'(?i)\b'+ROLE+r'\s*(?:is\b|[:=])\s*',line)
        if inline:
            rest=line[inline.end():].strip(' |\t'); idx=i
            if not rest and i+1<len(lines) and lines[i+1][0]==loc:
                rest=lines[i+1][2].strip(' |\t');idx=i+1
        elif m and i+1<len(lines) and lines[i+1][0]==loc:
            rest=lines[i+1][2].strip(' |\t'); idx=i+1
        else: continue
        match=re.match(NAME,rest)
        if not match: continue
        name=re.split(r'\s+(?:MD|FRCPC|MBBS|FRACGP|CPSBC|Clinic|Address|Phone|Fax)\b',match.group())[0].strip().rstrip('.,')
        if any(w in name.lower().split() for w in ['address','mailing','phone','fax','licence','details','number','name']): continue
        if len(re.sub(r'^Dr\.?\s+','',name).split())<2:continue
        names.append((name,i,idx))
        add('prescriber_name',name,[i,idx], 'Requires Review: explicit prescribing role; verify identity.')

    if not names:
        intent=[i for i,(_,_,s) in enumerate(lines) if re.search(r'(?i)^\s*I\s+(?:will|shall|am)\b.{0,100}\b(?:submit|apply|applying)\b',s)
                and re.search(r'(?i)special authority|application|coverage',' '.join(x[2] for x in lines[i:i+3]))]
        signatures=[]
        for i,(_,_,s) in enumerate(lines):
            m=re.fullmatch(r'('+NAME+r'),?\s+MD(?:\s+FRCPC)?',s)
            if m:signatures.append((m.group(1),i))
        if intent and len({n.casefold() for n,_ in signatures})==1:
            name,i=signatures[0];names.append((name,i,i))
            add('prescriber_name',name,intent+[i],
                'Requires Review: single clinician sign-off linked to explicit first-person application intent in this document.')
    unique_names={re.sub(r'[^a-z]','',name.lower()) for name,_,_ in names}
    competing=any(re.search(r'(?i)\b(?:referring (?:physician|provider)|ordering (?:physician|provider)|consultant|recipient)\s*[:=]',s) for _,_,s in lines)

    def local_prescriber(i):
        # Generic contact/address labels must remain in the prescribing block.
        candidates=[]
        for name,start,end in names:
            if lines[start][0]!=lines[i][0] or not end<=i<=end+12:continue
            if any(OTHER.search(lines[j][2]) for j in range(end+1,i+1)):continue
            candidates.append(name)
        return len({n.casefold() for n in candidates})==1

    def address_at(i,offset=0):
        text=lines[i][2][offset:].strip(' |\t');indices=[i]
        if not text and i+1<len(lines) and lines[i+1][0]==lines[i][0]:
            i+=1;text=lines[i][2];indices.append(i)
        if not STREET.search(text):return '',[]
        parts=[text.rstrip('.,')]
        for j in range(i+1,min(i+4,len(lines))):
            nxt=lines[j][2]
            if lines[j][0]!=lines[i][0] or CONTACT.search(nxt) or OTHER.search(nxt) or ':' in nxt:break
            if POSTAL.search(nxt) or re.search(r'\b(?:BC|AB|ON|SK|MB|QC|NS|NB|NL|PE|NT|NU|YT)\b',nxt):
                parts.append(nxt.rstrip('.,'));indices.append(j)
                if POSTAL.search(nxt):break
            else:break
        return ', '.join(parts),indices

    for i,(loc,n,line) in enumerate(lines):
        explicit=re.search(r'(?i)\b(?:prescriber|prescribing physician)\s+(?:mailing\s+)?address\s*[:=]\s*',line)
        clinic=re.search(r'(?i)\bclinic\s+(?:mailing\s+)?address\s*[:=]\s*',line)
        generic=re.search(r'(?i)^\s*(?:mailing\s+)?address\s*[:=]\s*',line)
        if explicit:
            value,indices=address_at(i,explicit.end())
            add('prescriber_address',value,indices,'Requires Review: explicit prescriber address; verify mailing destination.')
        elif clinic and len(unique_names)==1 and not competing:
            value,indices=address_at(i,clinic.end())
            anchors=[idx for _,start,end in names for idx in [start,end]]
            add('prescriber_address',value,indices+anchors,
                'Requires Review: clinic address linked across document to the single explicit prescriber; verify association.')
        elif generic and local_prescriber(i):
            value,indices=address_at(i,generic.end())
            add('prescriber_address',value,indices,'Requires Review: mailing address within prescribing block.')
        elif STREET.search(line) and not OTHER.search(line) and ':' not in line and local_prescriber(i):
            value,indices=address_at(i)
            add('prescriber_address',value,indices,'Requires Review: street address within prescribing block.')
        elif STREET.search(line) and not OTHER.search(line) and ':' not in line and len(unique_names)==1 and not competing:
            header=[j for j in range(max(0,i-2),i) if lines[j][0]==loc
                    and re.search(r'(?i)\b(?:clinic|medical centre|medical center|health centre|health center|hematology)\b',lines[j][2])
                    and not OTHER.search(lines[j][2])]
            if header:
                value,indices=address_at(i)
                anchors=[idx for _,start,end in names for idx in [start,end]]
                add('prescriber_address',value,indices+header+anchors,
                    'Requires Review: clinic letterhead linked to the single explicit prescriber across pages; verify practice affiliation.')

        # A uniquely labelled clinic address can be in a different page's letterhead.
        # Unlabelled letterhead streets are intentionally not assigned globally.
        for category,label in [('prescriber_phone',r'(?:phone|telephone|tel|office(?: phone| telephone)?)'),('prescriber_fax',r'(?:fax|facsimile)')]:
            m=re.search(r'(?i)\b(?:(prescriber|prescribing physician|clinic)\s+)?'+label+r'\s*[:=]?\s*',line)
            if not m:continue
            role=(m.group(1) or '').lower()
            if role=='clinic' and (len(unique_names)!=1 or competing):continue
            header_contact=False
            if len(unique_names)==1 and not competing:
                for j in range(max(0,i-3),i):
                    if lines[j][0]!=loc or OTHER.search(lines[j][2]) or not STREET.search(lines[j][2]):continue
                    if any(OTHER.search(lines[k][2]) for k in range(j+1,i+1)):continue
                    if any(f.category=='prescriber_address' and lines[j][2] in f.evidence for f in facts):header_contact=True
            if not role and not local_prescriber(i) and not header_contact:continue
            text=line[m.end():]
            indices=[i]
            if not text and i+1<len(lines) and lines[i+1][0]==loc:
                text=lines[i+1][2];indices.append(i+1)
            phone=re.match(r'\+?\d[\d ().+-]{6,24}|\(\d{3}\)[\d .-]{7,17}',text)
            if phone and 10<=len(re.sub(r'\D','',phone.group()))<=11:
                add(category,phone.group().strip(' .-'),indices,'Requires Review: role-associated contact; verify recipient.')

        m=re.search(r'(?i)\b(?:CPSBC|CRNBC)\s+(?:licen[cs]e|registration|number|no\.?|#)\s*[:=#]\s*',line)
        if not m and len(unique_names)==1:
            m=re.search(r'(?i)\b(?:CPSBC|CRNBC)\s+(?=[A-Z0-9-]*\d)',line)
        if m:
            text=line[m.end():];indices=[i]
            if not text and i+1<len(lines) and lines[i+1][0]==loc:text=lines[i+1][2];indices.append(i+1)
            value=re.match(r'[A-Z0-9-]{3,25}',text,re.I)
            if value and re.search(r'\d',value.group()):add('prescriber_licence',value.group(),indices)
    return facts

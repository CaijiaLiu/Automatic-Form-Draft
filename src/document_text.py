"""Read native/OCR words in visual row order, retaining page/line evidence."""

def visual_rows(words):
    rows=[]
    for x0,y0,x1,y1,text in sorted(words,key=lambda w:(w[1],w[0])):
        row=next((r for r in reversed(rows[-4:]) if abs(r[0][1]-y0)<=3),None)
        if row is None:rows.append([(x0,y0,x1,y1,text)])
        else:row.append((x0,y0,x1,y1,text))
    return '\n'.join(' '.join(w[4] for w in sorted(r,key=lambda w:w[0])) for r in rows)


def image_text(image):
    import pytesseract
    data=pytesseract.image_to_data(image,output_type=pytesseract.Output.DICT,config='--psm 6',timeout=40)
    scale=max(1,image.width/612)
    return visual_rows([(data['left'][i]/scale,data['top'][i]/scale,
                         (data['left'][i]+data['width'][i])/scale,
                         (data['top'][i]+data['height'][i])/scale,text)
                        for i,text in enumerate(data['text']) if text.strip() and float(data['conf'][i])>=15])


def pdf_text(path,allow_ocr=True):
    import pymupdf
    from PIL import Image
    pages=[]
    with pymupdf.open(path) as doc:
        for i,page in enumerate(doc,1):
            words=[tuple(w[:5]) for w in page.get_text('words')]
            if len(words)>5:
                pages.append((f'page {i} (visual rows)',visual_rows(words)))
            else:
                if not allow_ocr:
                    pages.append((f'page {i} OCR deferred',''));continue
                try:
                    pix=page.get_pixmap(matrix=pymupdf.Matrix(3,3),alpha=False)
                    text=image_text(Image.frombytes('RGB',(pix.width,pix.height),pix.samples))
                    pages.append((f'page {i} OCR (visual rows)',text))
                except Exception as exc:
                    pages.append((f'page {i} OCR unavailable ({type(exc).__name__})',''))
    return pages

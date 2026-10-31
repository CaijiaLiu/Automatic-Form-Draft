from pathlib import Path
from src.layout_tables import extract_layout_rows,layout_facts


def test_unknown_csv_schema_preserves_quoted_cells_and_empty_values(tmp_path):
    path=tmp_path/'unknown.csv'
    path.write_text('accession,state,note,value\nA1,CANCELLED,"clotted, no result",\nA2,FINAL,verified,18\n')
    rows,warnings=extract_layout_rows(path)
    assert not warnings
    assert rows[0].cells['3: note']=='clotted, no result'
    assert rows[0].cells['4: value']==''
    assert rows[1].cells['4: value']=='18'
    assert rows[0].row==2
    assert layout_facts(rows)==[]


def test_unknown_table_headers_do_not_prevent_cell_extraction(tmp_path):
    from reportlab.pdfgen import canvas
    path=tmp_path/'unfamiliar.pdf'
    c=canvas.Canvas(str(path),pagesize=(600,800))
    for x in [40,200,360]:c.line(x,600,x,720)
    for y in [600,640,680,720]:c.line(40,y,360,y)
    for x,y,text in [(50,695,'Specimen'),(210,695,'Disposition'),
                     (50,655,'A1'),(210,655,'Cancelled'),(50,615,'A2'),(210,615,'Amended')]:
        c.drawString(x,y,text)
    c.save()
    rows,warnings=extract_layout_rows(path)
    assert not warnings
    assert len(rows)==3
    assert rows[0].cells=={'column_1':'Specimen','column_2':'Disposition'}
    assert rows[2].cells=={'column_1':'A2','column_2':'Amended'}
    assert rows[2].bbox[2]>rows[2].bbox[0]
    assert rows[2].kind=='unmapped_table'
    assert layout_facts(rows)==[]

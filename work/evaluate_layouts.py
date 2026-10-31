"""Package provenance and observed development results of original public PDFs."""
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import sys
import zipfile

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from src.layout_tables import extract_layout_rows,layout_facts
DATA=ROOT/'sample_data'/'public_layouts'
OUT=ROOT/'outputs'/'public_layout_review'
OUT.mkdir(parents=True,exist_ok=True)
catalog=json.loads((DATA/'catalog.json').read_text())
results=[]
for item in catalog:
    path=DATA/item['file']
    rows,warnings=extract_layout_rows(path)
    import pymupdf
    with pymupdf.open(path) as doc:
        item['pages']=len(doc)
    item['sha256']=hashlib.sha256(path.read_bytes()).hexdigest()
    results.append({**item,'row_candidates':len(rows),'warnings':warnings,
        'rows':[asdict(r) for r in rows], 'linked_facts':[asdict(f) for f in layout_facts(rows)]})
(OUT/'sources_and_results.json').write_text(json.dumps(results,indent=2,ensure_ascii=False))
lines=['# 公开原始医疗表格版式检查','',
    '本次使用外部公开 PDF 原件，未改写病例文字，也未重新制作表格。样本分别来自实验室官方示例、CBC 教学示例和第三方公开合成病历。',
    '这是根据这些文件开发、人工核对后的回归测试，不是陌生医院文书的盲测准确率。','',
    '| 原始文件 | 页数 | 候选数据行 | 版式要点 |','|---|---:|---:|---|']
for r in results:
    lines.append(f"| {r['file']} | {r['pages']} | {r['row_candidates']} | {r['layout']} |")
lines += ['','## 已人工核对的关键对应关系','',
    '- Testing CBC：血小板 180，单位 K/mcL，参考范围 150-450；结果来自 Normal 列，而不是参考范围。',
    '- Labcorp 第 1、3、5 页：血小板结果分别是 6、308、250；01 是实验室脚注标号，不是结果。Critical 属于第 1 页的 6。',
    '- Labcorp 的 Previous Result and Date 是独立列；本样本该列为空，必须保持为空。采样日期与打印/报告日期分开保存。',
    '- Quest 图像 PDF：血小板 215，参考范围 140-400 Thousand/uL；没有采样日期，仍为 Requires Review。单位位于参考列，派生为单位候选时明确注明来源。',
    '- Medication chart：7 行药物，每一行保留药名、剂量/途径、频次。星期列的空格不向左填充；AT、RB、DC 保留为原始缩写，不推断其临床含义。PRN 的 0 次给药不是缺失值。',
    '- 出院用药表：5 行。Amoxicillin 对应 1g PO TDS 和完整的剩余疗程备注；出院日期不当作起始用药日期。','',
    '## 使用方法','',
    '在网页勾选加载公开样本，从 Demo source 选择 Layout 开头的项目。左边是原始 PDF 页，右边是按列提取的候选行。选择任意一行，可看到源行截图、页码及坐标。',
    '文件属于不同示例患者，请分别测试。Labcorp 原件本身含三个不同样例，工具允许查看各页表格，但阻止合并生成一名患者的申请。','',
    '## 范围与未解决问题','',
    '- 行数是候选条目数量，不是正确率。只对上述关键行列关系进行了明确断言，不能据此声称所有字段正确。',
    '- 目前使用表头与文字坐标。支持本次所见的 CBC/药物表头，不保证任意合并单元格、跨页延续、手写或自定义缩写。',
    '- 扫描报告需要本地 Tesseract，OCR 仍会漏字、错字，结果须与原页比对。',
    '- Patient history 原页的就诊资料、病程和调查结果保持可见；本次没有实现对整段病史的完整语义理解。',
    '- 原始字段、空单元格和日期角色均保留，缺失不靠历史值或参考区间补齐。',
    '- 没有临床建议、药物选择、真实患者处理或外部 AI 上传。','',
    '## 来源及使用范围','']
for r in results:
    lines += [f"- [{r['publisher']} — {r['title']}]({r['url']})：{r['status']}"]
lines += ['', '公开可下载不等于可任意商业再授权。各原件保留出版方声明；Root Cause Analytics 文件为 CC-BY-NC 4.0，仅用于本地非商业评估。',
          '', '重跑：`.venv/bin/python -m pytest -q tests/test_layout_tables.py`；生成检查报告：`.venv/bin/python work/evaluate_layouts.py`。']
(OUT/'版式检查与测试说明.md').write_text('\n'.join(lines),encoding='utf-8')
with zipfile.ZipFile(ROOT/'outputs'/'public_cbc_chart_layout_samples.zip','w',zipfile.ZIP_DEFLATED) as z:
    for item in catalog:
        z.write(DATA/item['file'],'original_pdfs/'+item['file'])
    z.write(OUT/'sources_and_results.json','SOURCE_PROVENANCE_AND_RESULTS.json')
    z.write(OUT/'版式检查与测试说明.md','先读版式检查说明.md')
print('\n'.join(f"{r['file']}: {r['row_candidates']} row candidates" for r in results))

"""Fetch unchanged public, explicitly synthetic PDFs for local evaluation."""
import hashlib
import json
import urllib.request
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor

ROOT = Path(__file__).resolve().parents[1]
DEST = ROOT / 'sample_data' / 'public_external'
DEST.mkdir(parents=True, exist_ok=True)
REPO = 'RootCauseAnalytics/synthetic-australian-medical-documents-sample'
API = 'https://huggingface.co/api/datasets/' + REPO

def get(url):
    req = urllib.request.Request(url, headers={'User-Agent': 'LocalSyntheticEvaluation/1.0'})
    with urllib.request.urlopen(req, timeout=60) as response:
        return response.read()

revision = '75d0072abf04f324303069bd2f6753c429fd9a52'
tree = json.loads(get(API + '/tree/' + revision + '?recursive=true&limit=1000'))
# Fixed IDs chosen by document types, not extraction success. Do not change after scoring.
splits = {'0001': 'development', '0006': 'development', '0010': 'development',
          '0023': 'held_out', '0033': 'held_out', '0045': 'held_out'}
paths = [item['path'] for item in tree if item['type']=='file' and
         item['path'].startswith(('pdfs/', 'pdfs_scanned/')) and item['path'].split('/')[-1][:4] in splits]
paths += ['README.md','ground_truth.jsonl']

def download(path):
    url = f'https://huggingface.co/datasets/{REPO}/resolve/{revision}/{path}'
    data = get(url)
    local = DEST / path
    local.parent.mkdir(parents=True, exist_ok=True)
    local.write_bytes(data)
    return {'path':path, 'url':url, 'sha256':hashlib.sha256(data).hexdigest(),
            'split':splits.get(path.split('/')[-1][:4], 'reference'), 'bytes':len(data)}

with ThreadPoolExecutor(max_workers=4) as pool:
    files = list(pool.map(download, paths))
manifest = {'source':'https://huggingface.co/datasets/'+REPO, 'revision':revision,
            'author':'Jack Webb / Root Cause Analytics', 'license':'CC-BY-NC-4.0',
            'purpose':'Non-commercial local evaluation only; all entities synthetic per dataset card',
            'downloaded':'2026-10-30', 'files':files}
(DEST/'provenance.json').write_text(json.dumps(manifest, indent=2))
print('Downloaded',len(files),'files at revision',revision)
for item in files:
    print(item['split'],item['path'],item['bytes'])

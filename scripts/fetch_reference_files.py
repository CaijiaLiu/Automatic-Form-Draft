"""Download public reference PDFs locally; never upload source records."""
from pathlib import Path
import hashlib
import json
import urllib.request
import zipfile

ROOT = Path(__file__).resolve().parents[1]

def main():
    with zipfile.ZipFile(ROOT / 'sample_data/synthetic_emr_packets.zip') as bundle:
        for entry in bundle.infolist():
            target = (ROOT / entry.filename).resolve()
            if ROOT not in target.parents:
                raise RuntimeError('Unsafe sample archive path')
            if not target.exists():
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(bundle.read(entry))
    print('Authored synthetic sample packets ready.')
    for item in json.loads(Path(__file__).with_name('reference_files.json').read_text()):
        target = ROOT / item['path']
        if target.exists() and hashlib.sha256(target.read_bytes()).hexdigest() == item['sha256']:
            continue
        request = urllib.request.Request(item['url'], headers={'User-Agent': 'SyntheticDemoReferenceSetup/1.0'})
        with urllib.request.urlopen(request, timeout=90) as response:
            data = response.read()
        if hashlib.sha256(data).hexdigest() != item['sha256']:
            raise RuntimeError(f"Publisher file changed; review before use: {item['path']}")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        print('Downloaded:', item['path'])
    print('Reference files verified. Start the local demo using the README instructions.')

if __name__ == '__main__':
    main()

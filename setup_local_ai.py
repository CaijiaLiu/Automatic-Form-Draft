"""Download a pinned public model; never reads or uploads medical source files."""
from pathlib import Path
import urllib.request,hashlib,subprocess,json,shutil

ROOT=Path(__file__).resolve().parent
MODEL=ROOT/'work/models/Qwen3-1.7B-Q8_0.gguf'
REVISION='90862c4b9d2787eaed51d12237eafdfe7c5f6077'
SHA256='061b54daade076b5d3362dac252678d17da8c68f07560be70818cace6590cb1a'
URL=f'https://huggingface.co/Qwen/Qwen3-1.7B-GGUF/resolve/{REVISION}/{MODEL.name}'

def digest(path):
    h=hashlib.sha256()
    with path.open('rb') as source:
        for chunk in iter(lambda:source.read(8*1024*1024),b''):h.update(chunk)
    return h.hexdigest()

if __name__=='__main__':
    MODEL.parent.mkdir(parents=True,exist_ok=True)
    if MODEL.exists():
        if digest(MODEL)!=SHA256:raise SystemExit('Existing model checksum mismatch; download not overwritten.')
        print('Pinned local model already present; checksum verified.')
    else:
        tmp=MODEL.with_suffix('.gguf.part')
        print('Downloading pinned Qwen3-1.7B Q8_0 weights (1.83 GB). No records are transmitted.')
        with urllib.request.urlopen(URL,timeout=30) as response,tmp.open('wb') as target:
            while chunk:=response.read(8*1024*1024):target.write(chunk)
        if digest(tmp)!=SHA256:raise SystemExit('Download checksum mismatch; partial model was not installed.')
        tmp.rename(MODEL)
        print('Model downloaded and checksum verified.')
    quant=MODEL.parent/'Qwen3-1.7B-local-Q4_K_M.gguf'
    if not quant.exists():
        binary=shutil.which('llama-quantize')
        if not binary:raise SystemExit('Install llama.cpp (including llama-quantize) before preparing the compact model.')
        tmp=quant.with_suffix('.gguf.part')
        print('Preparing a smaller local Q4_K_M model for 8 GB machines. Quantization can reduce accuracy.')
        with (MODEL.parent/'quantization.log').open('w') as log:
            subprocess.run([binary,'--allow-requantize',str(MODEL),str(tmp),'Q4_K_M','4'],stdout=log,stderr=log,check=True)
        tmp.rename(quant)
    manifest={'source_repo':'Qwen/Qwen3-1.7B-GGUF','source_revision':REVISION,
              'source_sha256':SHA256,'local_quantization':'Q8_0 -> Q4_K_M; accuracy may differ from original model',
              'local_file':quant.name,'local_sha256':digest(quant)}
    (MODEL.parent/'active_model.json').write_text(json.dumps(manifest,indent=2))
    print('Compact model prepared. Start ./run_local_ai.sh.')

"""Start local demo services detached from Terminal; never downloads or uploads data."""
from pathlib import Path
import os,subprocess,time,urllib.request
ROOT=Path(__file__).resolve().parents[1]
LOG=ROOT/'work/runtime';LOG.mkdir(parents=True,exist_ok=True)
URL='http://127.0.0.1:8503'
opener=urllib.request.build_opener(urllib.request.ProxyHandler({}))
def health(url):
    try:
        with opener.open(url,timeout=1) as r:return r.status==200
    except Exception:return False

def spawn(args,name):
    with (LOG/(name+'.log')).open('ab') as log:
        process=subprocess.Popen(args,cwd=ROOT,stdin=subprocess.DEVNULL,stdout=log,
            stderr=subprocess.STDOUT,start_new_session=True,close_fds=True,
            env={**os.environ,"PATH":"/opt/homebrew/bin:/usr/local/bin:"+os.environ.get("PATH","/usr/bin:/bin")})
    (LOG/(name+'.pid')).write_text(str(process.pid))
    return process

if not health(URL+'/_stcore/health'):
    app=spawn([str(ROOT/'.venv/bin/python'),'-m','streamlit','run','app.py',
        '--server.headless=true','--server.address=127.0.0.1','--server.port=8503',
        '--browser.gatherUsageStats=false'],'web')
    for _ in range(40):
        if health(URL+'/_stcore/health'):break
        if app.poll() is not None:raise SystemExit('Demo failed to start. See '+str(LOG/'web.log'))
        time.sleep(.3)
    else:raise SystemExit('Demo startup timed out. See '+str(LOG/'web.log'))
# Optional model is already installed on this development computer. No new download.
model=ROOT/'work/models/Qwen3-1.7B-local-Q4_K_M.gguf'
if model.exists() and not health('http://127.0.0.1:8081/health'):
    # llama.cpp can need time to load, so check the port before spawning another process.
    import socket
    try:
        with socket.create_connection(('127.0.0.1',8081),timeout=1):pass
    except OSError:
        spawn(['/bin/zsh',str(ROOT/'run_local_ai.sh')],'model')
print(URL)

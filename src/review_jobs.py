"""Single-worker optional local review; never blocks editing or overwrites fields."""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import tempfile,time,threading

class ReviewJobs:
    def __init__(self):
        self.pool=ThreadPoolExecutor(max_workers=1,thread_name_prefix='itp-local-review')
        self.jobs={};self.lock=threading.Lock()

    def start(self,key,sources,rows,model,targets):
        with self.lock:
            existing=self.jobs.get(key)
            if existing:
                if not existing['future'].done():return existing
                if not existing['future'].exception():
                    cached=existing['future'].result()
                    retryable=not cached.raw or any(any(word in w.lower() for word in ['failed','truncated','budget']) for w in cached.warnings)
                    if not retryable:return existing
            if any(not job['future'].done() for job in self.jobs.values()):
                raise RuntimeError('A local review is already running. Continue editing; another review can start when it finishes.')
            while len(self.jobs)>=8:self.jobs.pop(next(iter(self.jobs)))
            job={'message':'Reading selected source evidence in the background.','started':time.monotonic()}
            job['future']=self.pool.submit(self._run,job,sources,rows,model,tuple(targets))
            self.jobs[key]=job
            return job

    def _run(self,job,sources,rows,model,targets):
        from .semantic import recognize
        def progress(message):
            with self.lock:job['message']=message
        with tempfile.TemporaryDirectory() as tmp:
            paths=[]
            for filename,content in sources:
                path=Path(tmp)/Path(filename).name;path.write_bytes(content);paths.append(path)
            if targets:
                result=recognize(paths,rows,model,targets=targets,progress=progress)
            else:
                from .semantic import SemanticResult
                from .layout_tables import extract_with_layout
                result=SemanticResult(model='Local OCR / rules',raw={'mode':'ocr-only'})
                for path in paths:
                    progress('Reading scans locally; no AI model is used.')
                    facts,notes,_=extract_with_layout(path)
                    result.facts.extend(facts);result.warnings.extend(notes)
        result.usage['wall_seconds']=round(time.monotonic()-job['started'],2)
        return result

    def get(self,key):
        with self.lock:return self.jobs.get(key)

    def start_clinical(self,key,sources,rows,model):
        """Share the single worker with identity/OCR review; never queue models."""
        with self.lock:
            existing=self.jobs.get(key)
            if existing and (not existing['future'].done() or
                (not existing['future'].exception() and existing['future'].result().text)):
                return existing
            if any(not job['future'].done() for job in self.jobs.values()):
                raise RuntimeError('A local review is already running. Try again when it finishes.')
            while len(self.jobs)>=8:self.jobs.pop(next(iter(self.jobs)))
            job={'message':'Preparing Section 3 in the background.','started':time.monotonic()}
            job['future']=self.pool.submit(self._run_clinical,job,sources,rows,model)
            self.jobs[key]=job
            return job

    def _run_clinical(self,job,sources,rows,model):
        from .clinical_draft import generate_clinical_draft
        def progress(message):
            with self.lock:job['message']=message
        with tempfile.TemporaryDirectory() as tmp:
            paths=[]
            for filename,content in sources:
                path=Path(tmp)/Path(filename).name;path.write_bytes(content);paths.append(path)
            return generate_clinical_draft(paths,rows,model,progress=progress)

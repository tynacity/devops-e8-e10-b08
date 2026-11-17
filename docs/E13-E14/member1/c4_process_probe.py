import pathlib,subprocess,json,time,uuid,concurrent.futures
r=pathlib.Path(__file__).resolve().parents[3];w=r/'work/c4-process-proof-03';w.mkdir(exist_ok=False)
marker='e13probe_'+uuid.uuid4().hex
(w/'Dockerfile').write_text('FROM python:3.13-slim@sha256:70729b46c69b4f1e97c4822c1af3df53a1476cf5ddc6c087c0c10bc3a5678c2f\nRUN python3 -c "import time; time.sleep(120)" '+marker+'\n')
probe="import pathlib,json; print(json.dumps([{'pid':p.name,'cmd':(p/'cmdline').read_bytes().decode(errors='replace')} for p in pathlib.Path('/proc').iterdir() if p.name.isdigit() and (p/'cmdline').exists() and b'"+marker+"' in (p/'cmdline').read_bytes().split(bytes([0]))]))"
def scan():
 x=subprocess.run(['docker','run','--rm','--privileged','--pid=host','--user','0','course-e11e12:241880528','python3','-c',probe],capture_output=True,text=True);return {'exit':x.returncode,'stdout':x.stdout,'stderr':x.stderr}
import importlib.util
spec=importlib.util.spec_from_file_location('autobuild',r/'labs/e11e12/vendor/draft/autobuild.py');module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
argv=['docker','build','--no-cache','--progress=plain','-f',str(w/'Dockerfile'),str(w)]
def timed_build():
 try: return {'exit':module.execute(argv,w/'stdout.log',w/'build.log',12)}
 except TimeoutError as e:return {'status':'TIMED_OUT','error':str(e)}
pool=concurrent.futures.ThreadPoolExecutor();future=pool.submit(timed_build)
# observe a real RUN before cancelling, capped at 45 seconds
observations=[]
for i in range(30):
 x=scan();observations.append(x)
 if json.loads(x['stdout'] or '[]'):break
 time.sleep(1)
result=future.result();time.sleep(3)
after=scan();(w/'proof.json').write_text(json.dumps({'marker':marker,'client_result':result,'before':observations,'after':after},indent=2));print(json.dumps(after))

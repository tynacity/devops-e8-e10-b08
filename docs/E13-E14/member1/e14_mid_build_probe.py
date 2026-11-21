import pathlib,subprocess,json,urllib.request,time,concurrent.futures,uuid
r=pathlib.Path(__file__).resolve().parents[3];w=r/'work/e14-mid-build-fault';w.mkdir(exist_ok=False);marker='e14mid_'+uuid.uuid4().hex
candidate=r/'data/e14-mid-candidate.Dockerfile';candidate.write_text((r/'data/e13-upstream-student/H1-jsmn/candidate.member1.Dockerfile').read_text().replace('RUN make app','RUN python3 -c "import time; time.sleep(120)" '+marker+'\nRUN make app'))
payload={'project':'/course/work/e13-H1-jsmn-06/base-project','out':'/course/work/e14-mid-build-fault/build','candidate':'/course/data/e14-mid-candidate.Dockerfile','build_timeout':180,'expected_output':'1','job_id':marker,'trace_id':marker};(w/'request.json').write_text(json.dumps(payload,indent=2))
def call():
 try:
  req=urllib.request.Request('http://127.0.0.1:18083/v1/run',data=json.dumps(payload).encode(),headers={'Content-Type':'application/json'})
  with urllib.request.urlopen(req,timeout=200) as x:return {'http':x.status,'body':x.read().decode()}
 except Exception as e:return {'error':str(e)}
probe="import pathlib,json; print(json.dumps([{'pid':p.name,'cmd':(p/'cmdline').read_bytes().decode(errors='replace')} for p in pathlib.Path('/proc').iterdir() if p.name.isdigit() and (p/'cmdline').exists() and b'"+marker+"' in (p/'cmdline').read_bytes().split(bytes([0]))]))"
def scan():
 x=subprocess.run(['docker','run','--rm','--privileged','--pid=host','--user','0','course-e11e12:241880528','python3','-c',probe],capture_output=True,text=True);return json.loads(x.stdout)
pool=concurrent.futures.ThreadPoolExecutor();f=pool.submit(call);before=[]
for i in range(45):
 before=scan()
 if before:break
 if f.done():break
 time.sleep(1)
assert before, 'Build process not observed; do not claim mid-build fault'
stop=subprocess.run(['docker','stop','--time','2','e14-member1-draft-1'],capture_output=True,text=True);time.sleep(3);after=scan();response=f.result()
subprocess.run(['docker','start','e14-member1-draft-1'],check=True,capture_output=True)
health=[]
for i in range(30):
 try:
  with urllib.request.urlopen('http://127.0.0.1:18083/health',timeout=2) as x:health.append(json.load(x));break
 except Exception:time.sleep(1)
(w/'proof.json').write_text(json.dumps({'marker':marker,'before':before,'after':after,'stop_exit':stop.returncode,'failed_request':response,'recovered_health':health},indent=2));assert not after;print('observed running build, stopped service, no remaining marker process, recovered health')

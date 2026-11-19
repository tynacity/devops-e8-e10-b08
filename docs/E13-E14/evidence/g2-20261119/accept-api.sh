python3 - <<'PY'
from pathlib import Path
import urllib.request,urllib.error,urllib.parse,json,hashlib,subprocess,time,datetime
repo=Path('/root/241880492/e13-g2-member4-20261119/repo')
work=repo/'work/member4-g2';inputs=repo/'data/headerflow'
env=json.loads((work/'environment.json').read_bytes());base_url='http://127.0.0.1:'+str(env['api_port'])
http=work/'http';http.mkdir()
def sha(raw):return hashlib.sha256(raw).hexdigest()
def source_state():
 p=inputs/'project/repo'
 def git(*args):return subprocess.check_output(['git',*args],cwd=p,text=True).strip()
 names=subprocess.check_output(['git','ls-files','-z'],cwd=p).decode().split('\0')
 return {'head':git('rev-parse','HEAD'),'status':git('status','--porcelain'),'files':{n:sha((p/n).read_bytes()) for n in names if n}}
sequence=0
def request(method,path,body=None,label='http'):
 global sequence
 sequence+=1
 raw=None if body is None else json.dumps(body).encode()
 req=urllib.request.Request(base_url+path,data=raw,method=method,headers={'Content-Type':'application/json'})
 try:
  response=urllib.request.urlopen(req,timeout=30)
 except urllib.error.HTTPError as e:response=e
 with response:
  data=response.read();headers=dict(response.headers);status=response.status
 parsed=json.loads(data) if 'application/json' in headers.get('Content-Type','') else None
 (http/f'{sequence:03d}-{label}.json').write_text(json.dumps({'method':method,'path':path,'request':body,'status':status,'headers':headers,'response':parsed,'body_sha256':sha(data),'body_bytes':len(data)},ensure_ascii=False,indent=2)+'\n')
 return status,parsed,data,headers
def wait_job(jid):
 end=time.monotonic()+900
 while time.monotonic()<end:
  status,data,_,_=request('GET','/v1/jobs/'+jid,label='poll')
  assert status==200
  if data['status'] not in ('QUEUED','RUNNING'):return data
  time.sleep(2)
 raise TimeoutError('Job did not terminate within 900 seconds')
def manifest_and_downloads(jid):
 status,result,_,_=request('GET',f'/v1/jobs/{jid}/artifacts',label='artifacts')
 assert status==200
 checks=[]
 for a in result.get('artifacts',[]):
  prefix=f'artifact://{jid}/';assert a['uri'].startswith(prefix)
  name=a['uri'][len(prefix):]
  status,_,raw,headers=request('GET',f'/v1/jobs/{jid}/files/'+urllib.parse.quote(name,safe='/'),label='download')
  assert status==200 and sha(raw)==a['sha256']==headers.get('X-Content-SHA256') and len(raw)==a['bytes'],name
  checks.append({'path':name,'sha256':sha(raw),'bytes':len(raw),'http':status})
 (work/(jid+'-downloads.json')).write_text(json.dumps(checks,indent=2)+'\n')
 return result,checks
name=env['api_name'];container=env['api_id']
before=source_state();(work/'source-before.json').write_text(json.dumps(before,indent=2)+'\n')
report=inputs/'a-report/incremental-check.json';producer=inputs/'a-report/result.json'
original_report=report.read_bytes();original_producer=producer.read_bytes()
assert sha(original_report)=='45a1067267c489716c441b3edadf1be0132ff74378b81902c7c957beadb4e838'
assert sha(original_producer)=='6ccab6bc665dd4838f5dc0d4cb55cf29e371b1b42696b20081eae8ba1eddf029'
tampered=original_report.replace(b'  \"schema_version\"',b'\t \"schema_version\"',1)
assert len(tampered)==len(original_report) and sum(a!=b for a,b in zip(tampered,original_report))==1
assert json.loads(tampered)==json.loads(original_report)
(inputs/'tampered-incremental-check.json').write_bytes(tampered)
(work/'C3-mutation.json').write_text(json.dumps({'bytes':len(tampered),'changed_byte_count':1,'json_semantically_equal':True,'original_sha256':sha(original_report),'mutated_sha256':sha(tampered),'declared_sha256_unchanged':True,'producer_manifest_unchanged':True},indent=2)+'\n')
normal=dict(mode='e13-b',profile='explicit',repo='/course/data/headerflow/project/repo',base='88af5173a249ee4f30f3d7da51b20169db47d234',target='961f40cb8fbb71de304b782ff754522d59d51305',candidate='/course/data/headerflow/candidate.Dockerfile',expected_output='1',build_timeout=600,report='/course/data/headerflow/a-report/incremental-check.json',producer_manifest='/course/data/headerflow/a-report/result.json',report_sha256=sha(original_report))
cases=[];positive=None
try:
 status,health,_,_=request('GET','/health',label='health')
 assert status==200 and health['service_id']==name
 for label,changes,expected in [('C2-wrong-target',{'target':normal['base']},'STALE_REPORT'),('C3-tampered',{'report':'/course/data/headerflow/tampered-incremental-check.json'},'ARTIFACT_HASH_MISMATCH'),('C1-positive-control',{},None)]:
  req=normal|changes;key='member4-g2-20261119-'+label
  status,submitted,_,_=request('POST','/v1/jobs',{'input':req,'idempotency_key':key},label=label+'-submit')
  assert status==202
  jid=submitted['job_id']
  final=wait_job(jid)
  result,downloads=manifest_and_downloads(jid)
  evidence=repo/'work/member4-g2-api'/jid/'evidence'
  if expected:
   assert final['status']==result['status']=='FAILED' and result['error']['code']==expected
   assert result['stages']==[] and not (evidence/'draft-build').exists() and not (evidence/'mdfixer').exists()
  else:
   assert final['status']==result['status']=='SUCCEEDED' and result['original_source_unchanged'] is True
   assert result['source_report']['sha256']==normal['report_sha256']
   assert result['source_report']['job_id']=='job-10302c35430f449993b0caa0d7050bb8'
   assert result['source_report']['trace_id']=='trace-ff64eab93d4b4a35b606cc9009db7340'
   assert jid!=result['source_report']['job_id'] and result['trace_id']!=result['source_report']['trace_id']
   assert (evidence/'mdfixer/consumed-report.json').read_bytes()==original_report
   assert (evidence/'mdfixer/producer-result.json').read_bytes()==original_producer
   recheck=json.loads((evidence/'recheck.json').read_bytes())['data']
   assert recheck['remaining_missing']==0 and any((f['type'],f['target'],f['dependency'])==('REDUNDANT','main.o','unused.h') for f in recheck['findings'])
   runtime=json.loads((evidence/'execution-runtime.json').read_bytes())
   assert len(runtime['operations'])==1 and runtime['operations'][0]['action']=='mdfixer'
   assert result['execution_image_id']==runtime['image_id'] and runtime['image_id'] in runtime['operations'][0]['command']
   assert sha((evidence/'mdfixer/candidate.patch').read_bytes())=='4d9e61596043231b12564b623b74a1b974519202ee491492fccb9c1654b89ee6'
   positive=result
  cases.append({'case':label,'job_id':jid,'trace_id':result['trace_id'],'status':result['status'],'error_code':result.get('error',{}).get('code'),'artifacts_downloaded_and_verified':len(downloads),'draft_started':(evidence/'draft-build').exists()})
  print('Verified '+label,flush=True)
 assert len({c['job_id'] for c in cases})==3 and len({c['trace_id'] for c in cases})==3
 assert len(list((repo/'work/member4-g2-api').glob('job-*/state.json')))==3
 for c in cases:
  status,current,_,_=request('GET','/v1/jobs/'+c['job_id'],label='C7-terminal-state')
  assert status==200 and current['status']==c['status']
 assert before==source_state() and original_report==report.read_bytes() and original_producer==producer.read_bytes()
 (work/'source-after.json').write_text(json.dumps(source_state(),indent=2)+'\n')
 summary={'checked_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'tool_commit':env['source'],'entry':'POST /v1/jobs, mode=e13-b','project':'A-HeaderFlow','cases':cases,'C2_C3':'PASS; rejected before DRAFT and MDFixer','C7_support':'Distinct task directories and identities; failed tasks remain terminal after succeeding subsequent task','jobs_created':3,'A_freeze':'G2-A-20261118-0408405-v1','A_tool_commit_declared':'04084055221c9f59683d648b3766f86ed07bdd73','C3_changed_byte_count':1,'source_unchanged':True,'source_report_unchanged':True,'execution_image_id':positive['execution_image_id'],'environment_image':env['environment_image'],'download_hashes_verified':sum(c['artifacts_downloaded_and_verified'] for c in cases),'scope':'Member4 independent G2 paired-project C1-C3 API verification at fixed ac923c5; not E14 four-role HTTP deployment or A-side sign-off'}
 (work/'api-acceptance.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n')
 print(json.dumps(summary,ensure_ascii=False,indent=2))
finally:
 info=json.loads(subprocess.check_output(['docker','inspect',name]))[0]
 assert info['Id']==container and any(m['Source']==str(repo) and m['Destination']=='/course' for m in info['Mounts'])
 p=subprocess.run(['docker','logs',name],capture_output=True,text=True)
 (work/'api-container.log').write_text(p.stdout+p.stderr)
 p=subprocess.run(['docker','stop','--time','20',name],capture_output=True,text=True,timeout=40)
 (work/'api-stop.log').write_text(p.stdout+p.stderr)
 assert p.returncode==0
 print('Dedicated acceptance API stopped; original services untouched')
PY

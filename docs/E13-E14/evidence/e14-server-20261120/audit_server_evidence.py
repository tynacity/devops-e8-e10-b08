from pathlib import Path
import json, hashlib, re, importlib.util
from urllib.parse import quote,unquote
root=Path(__file__).resolve().parent
j=lambda p:json.loads(p.read_text(encoding='utf-8-sig'))
h=lambda b:hashlib.sha256(b).hexdigest()
source='7b7e67b6c005bdf27ca7645790d75623230c00fe'
rows=[];deployments=[]
for scope,sub,count in [('headerflow','',277),('tinyexpr','',455),('recovery','timeout',50),('recovery','recovery',277)]:
 base=root/'server-runtime'/scope/'run/evidence';p=base/sub;d=p/'downloads'
 state=j(p/'state.json');manifest=j(p/'artifacts.json');request=j(p/'request.json');submitted=j(p/'submitted.json')
 jid=state['job_id'];tid=state['trace_id'];expected='FAILED' if sub=='timeout' else 'SUCCEEDED'
 assert state['status']==manifest['status']==expected
 assert submitted['status']=='QUEUED' and submitted['job_id']==jid
 assert state['request_hash']==submitted['request_hash']==h(json.dumps(request['input'],sort_keys=True).encode())
 assert state['idempotency_key']==submitted['idempotency_key']==request['idempotency_key']
 assert j(d/'request.json')==request['input']
 assert manifest['job_id']==jid and manifest['trace_id']==tid and manifest['original_source_unchanged']
 assert (base/'source-sha.txt').read_text().strip()==source
 assert j(d/'source-before.json')==j(d/'source-after.json')
 before=j(d/'source-before.json');assert before['head']==request['input']['target'] and before['status']==''
 assert manifest['base_commit']==request['input']['base'] and manifest['target_commit']==request['input']['target']
 paths=set(); api=(base/'jobs-api.log').read_text(); getpaths={unquote(x) for x in re.findall(r'"GET ([^ ]+) HTTP/1.1" 200',api)}
 for ref in manifest['artifacts']:
  prefix='artifact://'+jid+'/';assert ref['uri'].startswith(prefix)
  rel=ref['uri'][len(prefix):]; assert '..' not in Path(rel).parts and not Path(rel).is_absolute() and rel not in paths
  paths.add(rel);raw=(d/rel).read_bytes();assert len(raw)==ref['bytes'] and h(raw)==ref['sha256'],rel
  assert '/v1/jobs/'+jid+'/files/'+rel in getpaths,rel
 assert len(paths)==count and paths=={f.relative_to(d).as_posix() for f in d.rglob('*') if f.is_file()}
 events=[json.loads(l) for l in (base/'four-roles.log').read_text().splitlines() if l.startswith('{')]
 events=[e for e in events if e['job_id']==jid];assert events and all(e['trace_id']==tid for e in events)
 row={'case':sub or scope,'job_id':jid,'trace_id':tid,'status':expected,'downloaded_artifacts_verified':count,'download_GET_200_verified':count,'source_unchanged':True,'base':manifest['base_commit'],'target':manifest['target_commit']}
 if sub!='timeout':
  assert [x['name'] for x in manifest['stages']]==['draft','full-check','incremental-check','repair','recheck']
  for ref in manifest['stages']:
   raw=(d/(ref['name']+'.json')).read_bytes();a=ref['artifact'];assert len(raw)==a['bytes'] and h(raw)==a['sha256']
   expected_commit=manifest['base_commit'] if ref['name']=='full-check' else manifest['target_commit']
   stage=json.loads(raw);assert stage['job_id']==jid and stage['trace_id']==tid and stage['commit']==expected_commit and stage['status']=='SUCCEEDED'
  for role in ['draft','buildchecker','echecker','mdfixer']:assert any(e['role']==role and e['status']=='SUCCEEDED' for e in events)
  for name in ['draft','baseline','target','incremental','repair','recheck']:
   q=j(d/(name+'-request.json'));assert q['job_id']==jid and q['trace_id']==tid
  image=manifest['execution_image_id'];runtime=j(d/'execution-runtime.json');assert runtime['image_id']==image and len(runtime['operations'])==6
  assert all(o['image_id']==image and image in o['command'] and o['exit_code']==0 for o in runtime['operations'])
  repair=j(d/'repair-response.json');assert repair['validation']['accepted'] and all(repair['validation']['checks'].values()) and repair['execution_image_id']==image
  assert h((d/'repair-work/component/candidate.patch').read_bytes())==repair['sha256']
  inc=(d/'incremental/incremental-check.json').read_bytes();prod=j(d/'incremental/producer-result.json')
  assert prod['job_id']==jid and prod['trace_id']==tid and prod['stages'][0]['artifact']['sha256']==h(inc) and prod['stages'][0]['artifact']['bytes']==len(inc)
  assert repair['input_report']['sha256']==j(d/'repair-request.json')['report_sha256']==j(d/'repair-work/component-request.json')['report_sha256']==h(inc)
  recheck=j(d/'recheck-response.json');assert recheck['execution_image_id']==image and recheck['result']['build_exit_code']==0
  assert not any(f['type']=='MISSING' for f in recheck['result']['findings'])
  assert runtime['operations'][-1]['project']==repair['repaired_project']
  draft=j(d/'draft-build/result.json');v=draft['verification'];assert draft['status']=='SUCCEEDED' and v['exit_code']==0 and v['output_matches'] and v['actual_output'].strip()==request['input']['expected_output'].strip() and image in v['command']
  assert draft['attempts'][-1]['image_id']==image
  if scope=='tinyexpr':
   assert set(recheck['result']['observed_targets'])=={'example','example.o','tinyexpr.o'}
   assert (base/'detector-sha.txt').read_text().strip()=='8355af8e45623855c3397442598bd07e27f1ec1a' and not (base/'detector-status.txt').read_text().strip()
  row.update(execution_image_id=image,stages_verified=5,runtime_operations_verified=6,missing_after_repair=0,recheck_observed_targets=recheck['result']['observed_targets'],candidate_sha256=draft['candidate_sha256'],output_verified=True)
 else:
  assert state['error']['code']=='TIMEOUT' and request['input']['build_timeout']==0.01 and manifest['stages']==[]
  assert j(p/'state-after-recovery.json')==state
  draft=j(d/'draft-build/result.json');assert draft['status']=='TIMED_OUT' and '0.01s' in draft['error'] and 'verification' not in draft
  assert not (p/'build-tag-1-after-timeout.log').read_text().strip()
  processes=(p/'draft-processes-after-timeout.log').read_text();assert 'service.py' in processes and 'docker build' not in processes and 'buildx' not in processes
  assert any(e['role']=='draft' and e['status']=='FAILED' for e in events)
  row.update(error_code='TIMEOUT',build_timeout_seconds=0.01,scope='Docker build client budget timeout, no verification container started',terminal_state_retained_after_recovery=True)
 rows.append(row)
 if sub!='timeout':
  summary=j(base/'verification.json'); project=summary['compose_project']; down=(base/'compose-down.log').read_text()
  for role in ['draft','buildchecker','echecker','mdfixer']:assert re.search(re.escape(project+'-'+role+'-1')+r'\s+Removed',down)
  assert re.search(re.escape(project+'_default')+r'\s+Removed',down)
  assert (base/'carrier-image.log').read_text().strip()=='sha256:1fa773b9ed7fdf35281eda86ec53ebf61048f271a70a43f9ccfd0e2d7a759829 linux/amd64'
  deployments.append({'case':scope,'compose_project':project,'four_role_and_network_removal_logged':True})
repo=Path('F:/codes/devops_labs/e13-e14-paired-20261118')
spec=importlib.util.spec_from_file_location('scan',repo/'scripts/secret_scan.py');scan=importlib.util.module_from_spec(spec);spec.loader.exec_module(scan)
text_count=0;binary_count=0;hits=[]
for f in (root/'server-runtime').rglob('*'):
 if not f.is_file():continue
 raw=f.read_bytes()
 try: s=raw.decode('utf-8')
 except UnicodeDecodeError:binary_count+=1;continue
 if '\0' in s:binary_count+=1;continue
 text_count+=1;hits+=scan.scan_text(s,str(f.relative_to(root)))
assert not hits,hits
result={'source_sha':source,'result':'PASS','audit_scope':'Member4 offline original evidence verification; live image audit recorded separately; no workload re-execution','total_downloaded_artifacts_verified':sum(r['downloaded_artifacts_verified'] for r in rows),'tasks':rows,'deployments':deployments,'received_scan':{'text_files':text_count,'binary_files_excluded':binary_count,'hits':len(hits)},'limitations':['No saved HTTP response headers; verified download bodies and GET 200 access logs.','Timeout is Docker client build-budget cancellation; no proof of an in-container runtime timeout.','No new same-key replay/conflict evidence; C8 retains previous version scope.','Server source SHA log received; no original server working-tree status log.']}
(root/'server-evidence-audit.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps(result,ensure_ascii=False,indent=2))

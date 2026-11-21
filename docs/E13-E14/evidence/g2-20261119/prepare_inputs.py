from pathlib import Path
import hashlib,json,zipfile,subprocess
root=Path(__file__).resolve().parent
raw=root/'expanded'
sha=lambda b:hashlib.sha256(b).hexdigest()
files=json.loads((raw/'FILES.json').read_bytes())
assert {x['path'] for x in files}=={p.name for p in raw.iterdir() if p.name!='FILES.json'}
for row in files:
 b=(raw/row['path']).read_bytes();assert len(b)==row['bytes'] and sha(b)==row['sha256']
r=json.loads((raw/'incremental-check.json').read_bytes());m=json.loads((raw/'result.json').read_bytes())
base='88af5173a249ee4f30f3d7da51b20169db47d234';target='961f40cb8fbb71de304b782ff754522d59d51305'
assert r['schema_version']==m['schema_version']=='e11e12-1'
assert r['status']==m['status']=='SUCCEEDED'
assert r['kind']=='incremental-check' and r['commit']==r['data']['commit']==m['target_commit']==target
assert m['base_commit']==base and r['data']['schema_version']=='e8e10-1'
assert all(r[k]==m[k] for k in ['job_id','trace_id'])
entry,=[s['artifact'] for s in m['stages'] if s['name']=='incremental-check']
assert entry==dict(uri=f"artifact://{r['job_id']}/incremental-check.json",sha256=sha((raw/'incremental-check.json').read_bytes()),bytes=(raw/'incremental-check.json').stat().st_size)
assert [a for a in m['artifacts'] if a['uri']==entry['uri']]==[entry]
producer='04084055221c9f59683d648b3766f86ed07bdd73'
source_log,=[a for a in m['artifacts'] if a['uri'].endswith('/logs/producer-source.log')]
assert source_log['bytes']==41 and source_log['sha256']==sha((producer+'\n').encode())
assert sha((raw/'candidate.Dockerfile').read_bytes())=='3836baf65c06a241b58505606714f4d443067ae894390471335ff212db1437dd'
old=Path('F:/notes/tmp/e13-paired-20261118/headerflow-verified-inputs.zip')
assert sha(old.read_bytes())=='3792ba278c58068384b4a4ddec0fe901b9c38d52114849558ac57deff741e844'
project=root/'project-check'
with zipfile.ZipFile(old) as z:
 for n in z.namelist():
  if not n.startswith('headerflow/project/repo/') or n.endswith('/'):continue
  p=(project/n.removeprefix('headerflow/project/repo/')).resolve();assert p.is_relative_to(project.resolve())
  p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(z.read(n))
for name in ['heads','tags']:(project/'.git/refs'/name).mkdir(parents=True,exist_ok=True)
def git(*args):return subprocess.check_output(['git',*args],cwd=project)
assert git('rev-parse','HEAD').decode().strip()==target
assert git('status','--porcelain')==b''
subprocess.run(['git','merge-base','--is-ancestor',base,target],cwd=project,check=True)
project_checks=[]
for revision,folder in [(base,'base-project'),(target,'target-project')]:
 entries=[a for a in m['artifacts'] if a['uri'].startswith(f"artifact://{r['job_id']}/{folder}/")]
 assert len(entries)==10
 for a in entries:
  name=a['uri'].split('/'+folder+'/',1)[1];b=git('show',revision+':'+name)
  assert sha(b)==a['sha256'] and len(b)==a['bytes'],name
 project_checks.append({'commit':revision,'producer_source_file_hashes_verified':len(entries)})
out=root/'g2-verified-inputs.zip'
assert not out.exists()
with zipfile.ZipFile(old) as z,zipfile.ZipFile(out,'w',zipfile.ZIP_DEFLATED) as dst:
 for n in z.namelist():
  if n.startswith('headerflow/project/repo/') and not n.endswith('/'):dst.writestr(n,z.read(n))
 dst.write(raw/'candidate.Dockerfile','headerflow/candidate.Dockerfile')
 for n in ['incremental-check.json','result.json']:dst.write(raw/n,'headerflow/a-report/'+n)
summary={'date':'2026-11-19','input_package_sha256':sha((root/'G2-HeaderFlow-input-review.zip').read_bytes()),'files_manifest_verified':len(files),'A_freeze':'G2-A-20261118-0408405-v1','A_tool_commit_declared':producer,'producer_source_log_digest_matches_declared_commit':True,'A_tool_checkout_independently_verified':False,'B_runtime_commit':'ac923c516129d863346710ce029d37b12ea8336c','base':base,'target':target,'source_job_id':r['job_id'],'source_trace_id':r['trace_id'],'report_sha256':entry['sha256'],'producer_manifest_sha256':sha((raw/'result.json').read_bytes()),'candidate_sha256':sha((raw/'candidate.Dockerfile').read_bytes()),'project_snapshots_verified':project_checks,'project_source':'Previously accepted exact Git repository; both G2 snapshots independently matched to producer manifest','derived_inputs_sha256':sha(out.read_bytes()),'full_A_artifact_tree_received':False,'report_references_verified_against_received_bytes':1,'note':'Input review package contains report, producer manifest, candidate and README, not every artifact listed by producer. README is valid UTF-8; original input bytes retained unchanged.'}
(root/'input-acceptance.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps(summary,ensure_ascii=False,indent=2))

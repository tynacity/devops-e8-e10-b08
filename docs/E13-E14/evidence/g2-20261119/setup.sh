set -eu
python3 - <<'PY'
from pathlib import Path,PurePosixPath
import subprocess,hashlib,json,zipfile,socket,urllib.request
root=Path('/root/241880492/e13-g2-member4-20261119');repo=root/'repo'
assert not repo.exists(),'Preserve existing G2 acceptance directory'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
assert sha(root/'incoming/g2-verified-inputs.zip')=='b44b19c18fad88a30b699b7d47ce78afddb7b8d16540dc0c0d844511ed327938'
subprocess.run(['git','clone','--no-hardlinks','--no-checkout','/root/241880492/e13-e14-paired-20261118/repo',str(repo)],check=True)
subprocess.run(['git','checkout','--detach','ac923c516129d863346710ce029d37b12ea8336c'],cwd=repo,check=True)
def git(*args,cwd=repo):return subprocess.check_output(['git',*args],cwd=cwd,text=True).strip()
assert git('rev-parse','HEAD')=='ac923c516129d863346710ce029d37b12ea8336c' and not git('status','--porcelain')
git('config','--local','user.name','241880492')
data=repo/'data';data.mkdir()
with zipfile.ZipFile(root/'incoming/g2-verified-inputs.zip') as z:
 for i in z.infolist():
  p=PurePosixPath(i.filename)
  assert not p.is_absolute() and '..' not in p.parts and ':' not in i.filename
  assert (data/i.filename).resolve().is_relative_to(data.resolve())
  assert (i.external_attr>>16)&0o170000!=0o120000
 z.extractall(data)
project=data/'headerflow/project/repo'
for n in ['heads','tags']:(project/'.git/refs'/n).mkdir(parents=True,exist_ok=True)
assert Path(git('rev-parse','--show-toplevel',cwd=project)).resolve()==project.resolve()
assert git('rev-parse','HEAD',cwd=project)=='961f40cb8fbb71de304b782ff754522d59d51305'
git('merge-base','--is-ancestor','88af5173a249ee4f30f3d7da51b20169db47d234','HEAD',cwd=project)
assert not git('status','--porcelain',cwd=project)
assert sha(data/'headerflow/a-report/incremental-check.json')=='45a1067267c489716c441b3edadf1be0132ff74378b81902c7c957beadb4e838'
assert sha(data/'headerflow/a-report/result.json')=='6ccab6bc665dd4838f5dc0d4cb55cf29e371b1b42696b20081eae8ba1eddf029'
assert sha(data/'headerflow/candidate.Dockerfile')=='3836baf65c06a241b58505606714f4d443067ae894390471335ff212db1437dd'
environment='sha256:1fa773b9ed7fdf35281eda86ec53ebf61048f271a70a43f9ccfd0e2d7a759829'
image=json.loads(subprocess.check_output(['docker','image','inspect','course-e11e12:241880492']))[0]
assert image['Id']==environment and image['Architecture']=='amd64'
work=repo/'work/member4-g2';work.mkdir(parents=True)
health={}
for port in (18546,18547):
 with urllib.request.urlopen(f'http://127.0.0.1:{port}/health',timeout=5) as r:health[str(port)]={'status':r.status,'body':json.load(r)}
(work/'old-services-before.json').write_text(json.dumps(health,indent=2)+'\n')
port=18593;name='e13-member4-g2-20261119'
with socket.socket() as probe:probe.bind(('127.0.0.1',port))
assert subprocess.run(['docker','container','inspect',name],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL).returncode!=0
start=['python3','run_e11e12.py','serve','--port',str(port),'--store-root','work/member4-g2-api','--container-name',name,'--detach']
p=subprocess.run(start,cwd=repo,capture_output=True,text=True,timeout=60)
(work/'api-start.log').write_text(p.stdout+p.stderr)
assert p.returncode==0,'Could not start dedicated API'
info=json.loads(subprocess.check_output(['docker','inspect',name]))[0]
assert info['Image']==environment and any(m['Source']==str(repo) and m['Destination']=='/course' for m in info['Mounts'])
summary={'source':git('rev-parse','HEAD'),'environment_image':environment,'platform':'linux/amd64','api_name':name,'api_id':info['Id'],'api_port':port,'input_archive_sha256':sha(root/'incoming/g2-verified-inputs.zip'),'source_repo':str(project)}
(work/'environment.json').write_text(json.dumps(summary,indent=2)+'\n')
print(json.dumps(summary,indent=2))
PY

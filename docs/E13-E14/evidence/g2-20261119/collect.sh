set -eu
python3 - <<'PY'
from pathlib import Path
import subprocess,json,hashlib,urllib.request,tarfile,datetime,importlib.util
root=Path('/root/241880492/e13-g2-member4-20261119');repo=root/'repo';work=repo/'work/member4-g2'
api=json.loads((work/'api-acceptance.json').read_bytes())
assert api['tool_commit']=='ac923c516129d863346710ce029d37b12ea8336c'
scan_dir=work/'C6';scan_dir.mkdir()
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
spec=importlib.util.spec_from_file_location('scan',repo/'scripts/secret_scan.py')
scan=importlib.util.module_from_spec(spec);spec.loader.exec_module(scan)
images=[]
for label,image_id in [('environment',api['environment_image']),('execution',api['execution_image_id'])]:
 info=json.loads(subprocess.check_output(['docker','image','inspect',image_id]))[0]
 assert info['Id']==image_id and info['Architecture']=='amd64' and info['Os']=='linux'
 item={'scope':label,'image_id':image_id,'platform':'linux/amd64','checks':[]}
 for name,args in [('history',['docker','history','--no-trunc','--format','{{.CreatedBy}}',image_id]),('env',['docker','image','inspect','--format','{{range .Config.Env}}{{println .}}{{end}}',image_id])]:
  raw=subprocess.check_output(args);assert not scan.scan_text(raw.decode('utf-8'),label+'-'+name),'Image scan hit; raw export stopped'
  p=scan_dir/(label+'-'+name+'.log');p.write_bytes(raw)
  item['checks'].append({'scope':name,'file':p.name,'bytes':len(raw),'sha256':sha(p),'hits':0})
 images.append(item)
p=subprocess.run(['python3','labs/e13e14/scan_runtime_logs.py',str(work),str(repo/'work/member4-g2-api')],cwd=repo,capture_output=True,text=True,timeout=120)
(scan_dir/'runtime.log').write_text(p.stdout+p.stderr);assert p.returncode==0,'Runtime scan failed'
health={}
for port in (18546,18547):
 with urllib.request.urlopen(f'http://127.0.0.1:{port}/health',timeout=5) as r:health[str(port)]={'http':r.status,'body':json.load(r)}
(work/'old-services-after.json').write_text(json.dumps(health,indent=2)+'\n')
assert subprocess.run(['docker','inspect','e13-member4-g2-20261119'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL).returncode!=0
summary={'checked_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'tool_commit':api['tool_commit'],'images':images,'runtime_exit':0,'scope':'Current G2 runtime logs and actual image history/config env; source and fake-value regression reused at unchanged fixed source; no layer filesystem scan','old_services_http_200':all(v['http']==200 for v in health.values()),'dedicated_api_stopped':True}
(work/'scan-acceptance.json').write_text(json.dumps(summary,indent=2)+'\n')
manifest=[]
for folder in [work,repo/'work/member4-g2-api']:
 for p in sorted(folder.rglob('*')):
  if p.is_file() and not p.is_symlink():manifest.append({'path':str(p.relative_to(repo/'work')),'bytes':p.stat().st_size,'sha256':sha(p)})
(root/'FILES.json').write_text(json.dumps(manifest,indent=2)+'\n')
archive=root/'member4-g2-ac923c5.tar.gz';assert not archive.exists()
with tarfile.open(archive,'w:gz') as t:
 t.add(work,arcname=work.name)
 t.add(repo/'work/member4-g2-api',arcname='member4-g2-api')
 t.add(root/'FILES.json',arcname='FILES.json')
print(json.dumps({'summary':summary,'archive':str(archive),'sha256':sha(archive),'bytes':archive.stat().st_size,'manifest_files':len(manifest)},indent=2))
PY

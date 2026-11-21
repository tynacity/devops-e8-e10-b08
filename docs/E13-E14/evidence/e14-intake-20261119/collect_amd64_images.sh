set -eu
python3 - <<'PY'
from pathlib import Path
import datetime,hashlib,json,subprocess,tarfile,importlib.util
repo=Path('/root/241880492/e13-e14-paired-20261118/repo')
out=repo.parent/'member4-e14-newdelivery-20261119'
out.mkdir(exist_ok=True)
spec=importlib.util.spec_from_file_location('scan',repo/'scripts/secret_scan.py')
scan=importlib.util.module_from_spec(spec);spec.loader.exec_module(scan)
images=[('reject','sha256:10b2cf326a7720d2c2e849148d919cf89b124f547fe51d20cccf215b1f1d17d5'),('positive','sha256:b41f5a2b56f68334325f23e2777578b9224f8cf92f8ecb2bd4f82c813068ed17')]
summary={'utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'scope':'Docker history commands and configured environment only; no layer filesystem scan','images':[]}
for label,image in images:
 entry={'variant':label,'image_id':image,'checks':[]}
 p=subprocess.run(['docker','image','inspect','--format','{{.Id}} {{.Os}}/{{.Architecture}}',image],capture_output=True,text=True,timeout=30)
 if p.returncode:
  entry['available']=False;summary['images'].append(entry);continue
 assert p.stdout.strip()==image+' linux/amd64'
 entry['available']=True;entry['platform']='linux/amd64'
 for name,args in [('history',['docker','history','--no-trunc','--format','{{.CreatedBy}}',image]),('env',['docker','image','inspect','--format','{{range .Config.Env}}{{println .}}{{end}}',image])]:
  p=subprocess.run(args,capture_output=True,timeout=30)
  assert p.returncode==0
  raw=p.stdout;hits=scan.scan_text(raw.decode('utf-8'),label+'-'+name)
  if hits: raise RuntimeError('Image scan found suspected secret; raw export stopped')
  filename=label+'-'+name+'.log';(out/filename).write_bytes(raw)
  entry['checks'].append({'scope':name,'file':filename,'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest(),'hits':0,'exit_code':0})
 summary['images'].append(entry)
summary['all_available_and_passed']=all(x['available'] and len(x['checks'])==2 for x in summary['images'])
(out/'image-audit.json').write_text(json.dumps(summary,indent=2)+'\n')
archive=out.with_suffix('.tar.gz')
with tarfile.open(archive,'w:gz') as t:
 for p in sorted(out.iterdir()):t.add(p,arcname=p.name)
print(json.dumps({'summary':summary,'archive':str(archive),'sha256':hashlib.sha256(archive.read_bytes()).hexdigest()},indent=2))
PY

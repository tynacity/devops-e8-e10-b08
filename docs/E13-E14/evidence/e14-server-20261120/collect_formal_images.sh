set -eu
python3 - <<'PY'
from pathlib import Path
import datetime,hashlib,json,subprocess,tarfile,importlib.util
repo=Path('/root/241880492/e13-e14-paired-20261118/repo')
out=repo.parent/'member4-e14-formal-audit-20261120'
out.mkdir(exist_ok=True)
spec=importlib.util.spec_from_file_location('scan',repo/'scripts/secret_scan.py')
scan=importlib.util.module_from_spec(spec);spec.loader.exec_module(scan)
images=[('headerflow','sha256:231de698ad24a368a1a6ccdf6ede045f6d0db26fb5fa334b6425cfab28357d2a'),('tinyexpr','sha256:929f86d18a011dff1dc551bcf3d7be9b081e5d060fe032bef7c424c34de4b703'),('recovery','sha256:ac1a02010573cbdd57802e5b9dbc1befe1a8cc5d9aa97ff31761018ae80146f6')]
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
summary['compose_current_checks']=[]
for project in ['b08-e14-241880546-e623b57c40','b08-e14-241880546-5bc5681b71','b08-e14-241880546-828903a7d0']:
 entry={'project':project}
 for kind,args in [('containers',['docker','ps','-aq']),('networks',['docker','network','ls','-q'])]:
  p=subprocess.run(args+['--filter','label=com.docker.compose.project='+project],capture_output=True,text=True,timeout=30)
  assert p.returncode==0
  entry[kind]=p.stdout.splitlines()
 summary['compose_current_checks'].append(entry)
p=subprocess.run(['docker','image','ls','--format','{{.ID}}','e6-draft-replay:def0727e3a5e499a88bc49859040da20-1'],capture_output=True,text=True,timeout=30)
assert p.returncode==0
summary['timeout_tag_current_ids']=p.stdout.splitlines()
(out/'image-audit.json').write_text(json.dumps(summary,indent=2)+'\n')
archive=out.with_suffix('.tar.gz')
with tarfile.open(archive,'w:gz') as t:
 for p in sorted(out.iterdir()):t.add(p,arcname=p.name)
print(json.dumps({'summary':summary,'archive':str(archive),'sha256':hashlib.sha256(archive.read_bytes()).hexdigest()},indent=2))
PY

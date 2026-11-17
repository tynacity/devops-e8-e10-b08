"""Host runner for member 1; stores console and exit code in a fresh work path."""
import argparse, pathlib, subprocess, json
p=argparse.ArgumentParser();p.add_argument('request');p.add_argument('output');a=p.parse_args()
r=pathlib.Path(__file__).resolve().parent;o=r/'work'/a.output
if o.exists():p.error('Output exists; preserve prior evidence')
cmd=['docker','run','--rm','--user','0:0','--cap-add','SYS_PTRACE','-v',str(r)+':/course','-v','/var/run/docker.sock:/var/run/docker.sock','-w','/course','-e','E11_HOST_ROOT='+str(r),'-e','PYTHONPATH=/course/labs/e11e12:/course/labs/e8e10:/course/labs/e11e12/vendor:/app','course-e11e12:241880528','sh','-c',"git config --global --add safe.directory '*' && exec python3 labs/e11e12/pipeline.py --request \"$1\" --out \"$2\"",'member1','/course/'+a.request,'/course/work/'+a.output]
o.parent.mkdir(exist_ok=True)
with o.with_suffix('.console.log').open('w') as f:code=subprocess.call(cmd,stdout=f,stderr=subprocess.STDOUT)
o.with_suffix('.exitcode').write_text(str(code)+'\n');print('exit=',code)
raise SystemExit(code)

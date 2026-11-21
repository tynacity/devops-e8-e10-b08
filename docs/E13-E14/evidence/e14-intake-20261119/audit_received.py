from pathlib import Path
import hashlib, json, subprocess, difflib

ROOT = Path(__file__).resolve().parent
EXP = ROOT / 'expanded'
REPO = Path('F:/codes/devops_labs/e13-e14-paired-20261118')

def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()
def load(path): return json.loads(path.read_bytes())
def check(base, name, digest, size=None):
    p = (base / name).resolve()
    assert p.is_relative_to(base.resolve()) and p.is_file(), name
    assert sha(p) == digest and (size is None or p.stat().st_size == size), name

manifests = []
for sub in ('member1', 'member2'):
    base = EXP / sub
    names = []
    for line in (base/'SHA256SUMS.txt').read_text(encoding='utf-8-sig').splitlines():
        if not line.strip(): continue
        digest, name = line.split(None, 1); name = name.lstrip('* ')
        check(base, name, digest); names.append(name)
    assert len(names) == len(set(names))
    assert set(names) == {p.relative_to(base).as_posix() for p in base.rglob('*') if p.is_file()} - {'SHA256SUMS.txt'}
    manifests.append({'package': sub, 'files_verified': len(names)})
c5 = EXP/'member2-c5'
manifest = load(c5/'SHA256SUMS.json')
for name, row in manifest.items(): check(c5, name, row['sha256'], row['bytes'])
assert set(manifest) == {p.relative_to(c5).as_posix() for p in c5.rglob('*') if p.is_file()} - {'SHA256SUMS.json'}
manifests.append({'package': 'member2-c5', 'files_verified': len(manifest)})

# Previously accepted packages are reused only when their bytes match.
prior = Path('F:/notes/DevOps_E13_E14_新增材料筛选_20261119')
assert sha(EXP/'member2/e14/成员1-E14接线实跑交付-20261119.zip') == sha(ROOT/'incoming/成员1-E14接线实跑交付-20261119.zip')
assert sha(EXP/'member2/source/B08-E14-rehearsal-source.zip') == sha(prior/'incoming/B08-E14-rehearsal-source.zip')
assert sha(EXP/'member2/review/成员1-部署条件补交-20261118.zip') == sha(prior/'incoming/成员1-部署条件补交-20261118.zip')
assert sha(EXP/'member2/review/成员2_E13_C6复核确认_20261119.md') == sha(prior/'incoming/成员2_E13_C6复核确认_20261119.md')
assert sha(EXP/'member2/review/member4-paired-f09349a.tar.gz') == '5c37447af3278d5368d9562f222a129fca263fe608ebf5eb77c1cc842089c3ae'
historical = []
for p in (EXP/'member2/docs/students/241880529/e13-e14/evidence').glob('*.zip'):
    relative = p.relative_to(EXP/'member2').as_posix()
    data = subprocess.check_output(['git', 'show', 'efa63135f51bfed6d7047ae2de916ef80885ac07:'+relative], cwd=REPO)
    assert hashlib.sha256(data).hexdigest() == sha(p)
    historical.append({'path': relative, 'sha256': sha(p), 'matches_accepted_component_commit': True})
identity = load(prior/'expanded/rehearsal/SOURCE_IDENTITY.json')
assert load(EXP/'member1/SOURCE_IDENTITY.json') == identity
tested_identity = load(c5/'source-identity.json')
assert all(tested_identity[k] == v for k, v in identity.items())
hook = tested_identity['test_instrumentation']
base_source = subprocess.check_output(['git','show','fcd36c0:'+hook['path']], cwd=REPO)
assert hashlib.sha256(base_source).hexdigest() == hook['before_sha256']
assert sha(c5/'mdfixer-tested.py') == hook['tested_sha256']
diff = ''.join(difflib.unified_diff(base_source.decode().splitlines(True),(c5/'mdfixer-tested.py').read_text(encoding='utf-8').splitlines(True),fromfile='fcd36c0/mdfixer.py',tofile='test-instrumented/mdfixer.py'))
(ROOT/'test-instrumentation.diff').write_text(diff,encoding='utf-8',newline='\n')

tasks = []
selected = [(EXP/'member1/work'/name, 'arm64') for name in ['headerflow-01','tinyexpr-01','headerflow-restored-01']]
selected += [(c5/'work'/name, 'amd64') for name in ['reject-missing-config','positive-after-rejection']]
for folder, platform in selected:
    r = load(folder/'result.json'); reject = folder.name == 'reject-missing-config'
    assert r['status'] == ('FAILED' if reject else 'SUCCEEDED')
    artifacts = r['artifacts']; stages = r['stages']
    for row in artifacts: check(folder,row['uri'],row['sha256'],row['bytes'])
    for stage in stages:
        row = stage['artifact']; check(folder,row['uri'],row['sha256'])
        obj=load(folder/row['uri'])
        assert obj['job_id']==r['job_id'] and obj['trace_id']==r['trace_id'] and obj['status']=='SUCCEEDED'
    assert [s['name'] for s in stages] == (['draft','full-check','incremental-check'] if reject else ['draft','full-check','incremental-check','repair','recheck'])
    assert load(folder/'source-before.json') == load(folder/'source-after.json') and r['original_source_unchanged']
    runtime = load(folder/'execution-runtime.json'); image = r['execution_image_id']
    assert runtime['image_id'] == image and len(runtime['operations']) == (5 if reject else 6)
    assert all(op['image_id']==image and image in op['command'] and op['exit_code']==0 for op in runtime['operations'])
    component = folder/'repair-work/component'
    assert load(component/'source-before.json') == load(component/'source-after.json')
    assert (folder/'incremental/incremental-check.json').read_bytes() == (component/'consumed-report.json').read_bytes()
    assert (folder/'incremental/producer-result.json').read_bytes() == (component/'producer-result.json').read_bytes()
    request=load(folder/'repair-request.json'); producer=load(component/'producer-result.json')
    report_hash=sha(component/'consumed-report.json')
    assert request['report_sha256']==report_hash and request['execution_image_id']==image
    assert producer['job_id']==r['job_id'] and producer['trace_id']==r['trace_id'] and producer['target_commit']==r['target_commit']
    assert producer['stages'][0]['artifact']['sha256']==report_hash
    v=load(component/'validation/validation.json')
    assert v['accepted'] == (not reject) and v['rollback'] == reject
    response=load(folder/'repair-response.json')
    if reject:
        assert load(component/'target-before.json') == load(component/'target-after.json')
        assert v['checks']['patch_applies'] and v['checks']['build'] and v['checks']['test']
        assert not v['checks']['header_change'] and not v['checks']['no_missing']
        assert response['http']==422 and 'REPAIR_REJECTED' in response['error']
        generated=(component/'generated-candidate.patch').read_bytes()
        assert (component/'candidate.patch').read_bytes() == generated.replace(b'+main.o: main.c unused.h config.h extra.h\n',b'+main.o: main.c unused.h extra.h\n',1)
    else:
        assert all(v['checks'].values())
        assert load(folder/'recheck.json')['data']['remaining_missing']==0
        assert sha(component/'candidate.patch')==response['sha256']
        assert response['input_report']['sha256']==report_hash and response['input_report']['job_id']==r['job_id']
        assert '/repair-work/component/target-project' in runtime['operations'][-1]['project']
    tasks.append({'task':folder.name,'platform':platform,'job_id':r['job_id'],'trace_id':r['trace_id'],'status':r['status'],'image':image,'artifacts_checked':len(artifacts),'stages_checked':len(stages),'operations':len(runtime['operations']),'source_unchanged':True,'accepted':v['accepted'],'rollback':v['rollback'],'report_binding_verified':True})

timeout=EXP/'member1/work/e14-timeout-01'
proof=load(timeout/'process-proof.json')
assert proof['observed_running'] and not proof['after'] and proof['inner_status']=='TIMED_OUT' and proof['outer_status']=='FAILED'
result=load(timeout/'result.json')
assert result['status']=='FAILED' and result['stages']==[]
for row in result['artifacts']: check(timeout,row['uri'],row['sha256'],row['bytes'])
assert 'draft: DRAFT_TIMED_OUT' in proof['outer_error']
cleanup=load(c5/'cleanup-verification.json');assert cleanup['remaining']=={'container':[],'network':[]}
images=[]
for p in (EXP/'member1/work/new-image-scan').glob('*-inspect.json'):
    info=load(p);info=info[0] if isinstance(info,list) else info
    assert info['Os']=='linux' and info['Architecture']=='arm64'
    prefix=info['Id'].split(':')[1][:12];assert p.name==prefix+'-inspect.json'
    images.append({'id':info['Id'],'platform':'linux/arm64','history_sha256':sha(p.with_name(prefix+'-history.txt')),'env_sha256':sha(p.with_name(prefix+'-env.txt'))})
assert len(images)==4 and {i['id'] for i in images} >= {t['image'] for t in tasks if t['platform']=='arm64'}
supplements=['成员2_C6复核确认摘要_20261119.json','成员2_E13_C6复核记录_20261118.md','成员2_新交付核验脚本_20261118.py']
for name in supplements: assert (EXP/'member2/review'/name).is_file()
summary={'date':'2026-11-19','method':'Offline original-evidence verification; no task reruns','manifests':manifests,'historical_packages':historical,'source_identity':identity,'test_instrumentation':hook,'tasks':tasks,'successful_and_rejection_artifacts':sum(t['artifacts_checked'] for t in tasks),'stage_references':sum(t['stages_checked'] for t in tasks),'timeout':{'job_id':result['job_id'],'status':'FAILED','inner_status':'TIMED_OUT','observed_running':True,'after_empty':True,'artifacts_checked':len(result['artifacts'])},'member2_cleanup':cleanup,'ARM64_images':images,'C6_process_attachments_received':supplements,'G2_new_input_received':False,'formal_source_commit_received':False,'outer_jobs_four_service_acceptance':False,'overall_gate':'BLOCKED'}
(ROOT/'acceptance.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
print(json.dumps({k:v for k,v in summary.items() if k in ['manifests','successful_and_rejection_artifacts','stage_references','timeout','C6_process_attachments_received']},ensure_ascii=False,indent=2))

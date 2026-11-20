from pathlib import Path
import hashlib,json,subprocess
root=Path(__file__).resolve().parent
repo=Path('F:/codes/devops_labs/e14-member3-7b7e67b-review-20261120')
common=Path('F:/codes/devops_labs/e13-e14-paired-20261118')
def sha(b):return hashlib.sha256(b).hexdigest()
def git(*args):return subprocess.check_output(['git','-c','core.quotePath=false',*args],cwd=repo)
latest='7b7e67b6c005bdf27ca7645790d75623230c00fe';wiring='9ec1f53429116fc3a1da60f4cac0388fe86023bd';base='4d74450c208ccb956dc31f48e6ac6b794464b520'
assert git('rev-parse','HEAD').decode().strip()==latest
assert git('rev-parse',latest+'^').decode().strip()==wiring
assert git('rev-parse',wiring+'^').decode().strip()==base
assert not git('status','--porcelain')
identity=json.loads((common/'docs/E13-E14/evidence/e14-intake-20261119/acceptance.json').read_bytes())['source_identity']
files=[]
for name,digest in identity['overlay_files'].items():
 before=git('show',wiring+':'+name);after=git('show',latest+':'+name)
 assert sha(before)==digest
 files.append({'path':name,'rehearsal_and_9ec1f53_sha256':digest,'7b7e67b_sha256':sha(after),'unchanged_at_API_commit':before==after})
assert [r['path'] for r in files if not r['unchanged_at_API_commit']]==['labs/e13e14/orchestrate.py']
assert git('diff','--name-only',base,wiring).decode().splitlines()==sorted(identity['overlay_files'])
assert git('diff','--name-only',identity['base_commit'],base,'--','labs','scripts','.github','run_e11e12.py')==b''
assert sha(git('show',latest+':labs/e13e14/mdfixer.py'))=='088393f75734d427c2db701d337ec45699d6dccf2e7d6d092ad37d13ff842443'
api_delta=git('-c','core.quotePath=false','diff','--name-only',wiring,latest).decode().splitlines()
assert set(api_delta)=={'docs/E13-E14/成员3-E14任务API.md','labs/e11e12/server.py','labs/e13e14/jobs_api.py','labs/e13e14/orchestrate.py','labs/e13e14/tests/test_member3_e14_jobs_api.py'}
(root/'api-change.diff').write_bytes(git('diff',wiring,latest,'--','labs/e11e12/server.py','labs/e13e14/orchestrate.py'))
g2=json.loads((root/'incoming/B组一次性回执_双向签收登记副本.json').read_bytes())
own=json.loads((common/'docs/E13-E14/evidence/g2-20261119/api-acceptance.json').read_bytes())
input_info=json.loads((common/'docs/E13-E14/evidence/g2-20261119/input-acceptance.json').read_bytes())
c1=g2['C1_A_consumption']
assert g2['A_freeze_id']==input_info['A_freeze']==own['A_freeze']
assert g2['A_source_commit']==input_info['A_tool_commit_declared']
assert c1['B_source_commit']==own['tool_commit']
assert c1['A_project_target']==input_info['target']
for field in ['source_job_id','source_trace_id']:assert c1[field]==input_info[field]
assert c1['source_report_sha256']==input_info['report_sha256']
assert c1['source_producer_result_sha256']==input_info['producer_manifest_sha256']
assert c1['DRAFT_image_id']==c1['MDFixer_image_id']==own['execution_image_id']
case_names={'C1-positive-control':('C1_A_consumption','B_'),'C2-wrong-target':('C2_old_target',''),'C3-tampered':('C3_same_size_tamper','')}
for case in own['cases']:
 block,prefix=case_names[case['case']];r=g2[block]
 assert r[prefix+'job_id']==case['job_id'] and r[prefix+'trace_id']==case['trace_id']
 if case['error_code']:assert r['actual']==case['error_code']
 else:assert r['status']==case['status'] and r['accepted'] is True
mut=json.loads((common/'docs/E13-E14/evidence/g2-20261119/C3-mutation.json').read_bytes())
assert g2['C3_same_size_tamper']['modified_sha256']==mut['mutated_sha256']
runtime=Path('F:/notes/DevOps_E13_G2输入核对_20261119/runtime/member4-g2-api')/c1['B_job_id']/'evidence'
assert sha((runtime/'mdfixer/candidate.patch').read_bytes())==c1['patch_sha256']
review=(root/'incoming/G2复核回执_给成员4.md').read_text(encoding='utf-8')
for case in own['cases']:
 assert case['job_id'] in review and case['trace_id'] in review
assert own['tool_commit'] in review and sha((common/'docs/E13-E14/evidence/g2-20261119/member4-g2-ac923c5.tar.gz').read_bytes()) in review
signA=g2['G2_HeaderFlow_A_signoff'];signB=g2['TinyExpr_detection_signoff']
assert signA['confirmed_by'] and signA['confirmed_at_Asia_Shanghai'] and signA['C1_C2_C3_verified'] is True
assert signA['freeze_id']==input_info['A_freeze'] and signA['A_report_sha256']==input_info['report_sha256']
assert signB['confirmed_by'] and signB['confirmed_at_Asia_Shanghai'] and signB['accepted'] is True
assert signB['target']==json.loads((common/'docs/E13-E14/input-manifest.json').read_bytes())['B_project']['target']
assert g2['confirmed_by'] is None and g2['B_human_confirmation_scope']=='TinyExpr_detection_signoff only'
h3=next((root/'expanded/成员1-最终环境与H3候选复核-20261119').rglob('SHA256SUMS.txt')).parent
h3_count=0
for line in (h3/'SHA256SUMS.txt').read_text(encoding='utf-8').splitlines():
 digest,name=line.split(None,1);p=h3/name.strip();assert p.resolve().is_relative_to(h3.resolve()) and sha(p.read_bytes())==digest;h3_count+=1
old_h3=json.loads((common/'docs/E13-E14/evidence/member3-20261118/acceptance.json').read_bytes())
accepted=next(r for r in old_h3['H3'] if r['variant']=='tools')
h3_review=json.loads((h3/'H3复核.json').read_bytes())
assert h3_review['candidate_sha256']==accepted['candidate_sha256']==sha((h3/'H3-release-candidate.Dockerfile').read_bytes())
assert h3_review['evidence_archive_sha256']==accepted['archive_sha256'] and h3_review['runtime_image']==accepted['execution_image_id']
original=next(r for r in old_h3['H3'] if r['variant']=='original')
assert sha((h3/'H3-original-candidate.Dockerfile').read_bytes())==original['candidate_sha256']
assert (h3/'H3-release-candidate.Dockerfile').read_bytes()==(h3/'H3-original-candidate.Dockerfile').read_bytes().replace(b'build-essential',b'build-essential strace git')
summary={'date':'2026-11-20','candidate_sha':latest,'wiring_sha':wiring,'parent_registration_sha':base,'bundle_complete_history_verified':True,'six_file_identity':files,'API_commit_changed_files':api_delta,'prior_component_and_workflow_bytes_unchanged_before_wiring':True,'member2_negative_test_hook_absent':True,'candidate_worktree_clean':True,'G2_peer_review':'Received; runtime SHA/job/trace/archive digest matched local original evidence; no rerun','G2_bilateral_receipt':'Received member3 forwarded registration copy; scoped confirmations accepted for current G2','G2_signers':{'A':signA,'B':signB},'G2_top_level_null_confirmation':'Preserved; not a missing current G2 scoped confirmation or approval of final B release','G2_reference_limit':'A original confirmation JSON, TinyExpr original artifact tree and referenced G2 registration audit were not included in this intake; no independent A-side rerun or remote audit claimed','H3_candidate_owner_confirmation':'Accepted against existing original/successful candidates and run archive','H3_manifest_files_verified':h3_count,'environment_proposal':json.loads((h3/'环境范围建议.json').read_bytes()),'E14_server_acceptance':'PENDING_MEMBER3_RUN_AT_7b7e67b','candidate_CI':'PENDING_COLLECTION','production_code_merged_into_common_branch':False,'overall_gate':'BLOCKED'}
(root/'acceptance.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print('Verified bundle lineage, six rehearsal file hashes, API delta, G2 task identities/signoff scope and H3 candidate confirmation.')

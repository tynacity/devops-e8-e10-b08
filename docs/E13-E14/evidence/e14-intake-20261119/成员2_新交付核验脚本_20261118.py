"""Offline receipt verification; does not contact Docker or change shared branches."""
from pathlib import Path
import hashlib
import importlib.util
import io
import json
import subprocess
import sys
import tarfile

import zipfile

REPO = Path(__file__).resolve().parents[1]
INBOX = Path('D:/APP/Wechat/WeChat Files/wxid_r9dn90rvrd9k22/FileStorage/File/2026-11')
OUT = REPO / 'work/member4-review-20261118'
OUT.mkdir(parents=True, exist_ok=True)
COMMIT = 'f09349a1f464ddfd0428a1e824f82867e98d89f8'

def sha(b):
    return hashlib.sha256(b).hexdigest()

def load_module(name, path):
    data = subprocess.check_output(['git', 'show', f'{COMMIT}:{path}'], cwd=REPO)
    dest = OUT / (name + '.py')
    dest.write_bytes(data)
    spec = importlib.util.spec_from_file_location(name, dest)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

runtime = load_module('review_runtime_scanner', 'labs/e13e14/scan_runtime_logs.py')
scanner = load_module('review_secret_scanner', 'scripts/secret_scan.py')
report = {'review_date': '2026-11-18', 'method': 'offline evidence review and local scanner replay; no server rerun', 'tool_commit': COMMIT, 'packages': []}
for name in ['DevOps_E13_E14_成员4门禁与发布准备_20261118.zip', 'DevOps_E13_E14_成员4跨组验收交付_20261118.zip']:
    raw = (INBOX / name).read_bytes()
    with zipfile.ZipFile(io.BytesIO(raw)) as z:
        root = z.namelist()[0].split('/')[0] + '/'
        manifest = json.loads(z.read(root + 'SHA256SUMS.json'))
        for row in manifest:
            data = z.read(root + row['path'])
            assert len(data) == row['bytes'] and sha(data) == row['sha256'], row['path']
        assert set(z.namelist()) == {root + row['path'] for row in manifest} | {root + 'SHA256SUMS.json'}
        report['packages'].append({'name': name, 'sha256': sha(raw), 'verified_files': len(manifest)})
        if '跨组' in name:
            paired = z.read(root + 'member4-paired-f09349a.tar.gz')

assert sha(paired) == '5c37447af3278d5368d9562f222a129fca263fe608ebf5eb77c1cc842089c3ae'
with tarfile.open(fileobj=io.BytesIO(paired), mode='r:gz') as t:
    files = {m.name: t.extractfile(m).read() for m in t.getmembers() if m.isfile()}
c6 = json.loads(files['member4-paired/c6-acceptance.json'])
assert c6['tool_commit'] == COMMIT
prefix = 'member4-paired/C6/'
fake = 'sk-' + 'member4paired0123456789abcdef'
probe = ('api_key = "' + fake + '"\n').encode()
assert sha(probe) == c6['fake_key']['injected_file_sha256']
assert sha(files[prefix + 'probe.log']) == c6['fake_key']['cleaned_file_sha256']
hit = files[prefix + 'fake-hit.log'].decode()
assert 'hits=2 errors=0' in hit and 'FOUND' in hit and fake not in hit
assert 'hits=0 errors=0' in files[prefix + 'fake-clean.log'].decode()
assert files[prefix + 'probe.log'] == b'cleaned isolated test log\n'
probe_path = OUT / 'local-probe.log'
probe_path.write_bytes(probe)
cmd = [sys.executable, '-X', 'utf8', str(OUT / 'review_runtime_scanner.py'), str(probe_path)]
p = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8')
assert p.returncode == 1 and 'hits=2 errors=0' in p.stdout and fake not in p.stdout + p.stderr
(OUT / 'local-fake-hit.log').write_text(p.stdout + p.stderr, encoding='utf-8')
probe_path.write_bytes(b'cleaned isolated test log\n')
p = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8')
assert p.returncode == 0 and 'hits=0 errors=0' in p.stdout
(OUT / 'local-fake-clean.log').write_text(p.stdout + p.stderr, encoding='utf-8')
for image in c6['images']:
    label = image['scope']
    info = json.loads(files[prefix + label + '-inspect.log'])[0]
    assert info['Id'] == image['image_id'] and info['Architecture'] == 'amd64'
    for kind in ['history', 'environment']:
        data = files[prefix + label + '-' + kind + '.log']
        assert sha(data) == image[kind + '_sha256']
        assert not scanner.scan_text(data.decode(), label + '-' + kind)
    assert image['scan_exit_code'] == 0

# Repeat the archived runtime scan in memory, with the original scanner rules.
checked = 0
hits = []
for name, data in files.items():
    if '.git' in name.split('/') or b'\x00' in data[:4096]:
        continue
    checked += 1
    for lineno, line in enumerate(data.decode('utf-8', errors='replace').splitlines(), 1):
        for label, pattern in runtime.PATTERNS:
            for match in pattern.finditer(line):
                value = match.group(match.lastindex or 0)
                if label == 'secret assignment' and (runtime.PLACEHOLDER.search(value) or value.startswith('&') or '(' in value or '[' in value):
                    continue
                hits.append({'path': name, 'line': lineno, 'pattern': label})
assert not hits, hits
report['c6'] = {'conclusion': 'PASS within original scope; final release scan pending', 'fake_replay_hit_exit': 1, 'fake_replay_clean_exit': 0, 'redacted': True, 'images_verified': c6['images'], 'archived_runtime_text_files_reviewed': checked, 'archived_runtime_hits': 0, 'original_runtime_log': files[prefix+'runtime.log'].decode().strip(), 'limitations': ['Original source/history scan reviewed as logged evidence, not re-executed.', 'Docker history/config env only; no exhaustive filesystem layer scan.', 'Does not include H3 new execution images, later service images/logs, or ARM64.']}

with zipfile.ZipFile(INBOX / 'H3_成员3交接_241880546_20261118.zip') as z:
    root = z.namelist()[0].split('/')[0] + '/'
    report['h3'] = []
    for variant in ['original', 'tools']:
        data = z.read(root + variant + '/h3-evidence.tar.gz')
        assert sha(data) == z.read(root + variant + '/h3-evidence.tar.gz.sha256').decode().split()[0]
        with tarfile.open(fileobj=io.BytesIO(data), mode='r:gz') as t:
            h3 = {m.name: t.extractfile(m).read() for m in t.getmembers() if m.isfile()}
        base = 'h3-evidence/'
        manifest = json.loads(h3[base + 'SHA256SUMS.json'])
        for name, row in manifest.items():
            payload = h3[base + name]
            assert len(payload) == row['bytes'] and sha(payload) == row['sha256'], name
        result = json.loads(h3[base + 'run/result.json'])
        references = result['artifacts'] + [s['artifact'] for s in result['stages']]
        for row in references:
            path = row['uri'].split('/', 3)[3]
            payload = h3[base + 'run/' + path]
            assert len(payload) == row['bytes'] and sha(payload) == row['sha256'], path
        before = json.loads(h3[base + 'record/project-before.json'])
        after = json.loads(h3[base + 'record/project-after.json'])
        assert before == after and before['head'] == result['target_commit']
        if variant == 'tools':
            val = json.loads(h3[base + 'run/validation/validation.json'])
            final = json.loads(h3[base + 'run/final-full/findings.json'])
            assert result['status'] == 'SUCCEEDED' and val['accepted'] and all(val['checks'].values())
            assert final['status'] == 'SUCCEEDED' and final['findings'] == []
        else:
            assert result['status'] == 'FAILED' and result['error']['code'] == 'FULL_CHECK_FAILED'
        report['h3'].append({'variant': variant, 'sha256': sha(data), 'files_verified': len(manifest), 'artifact_and_stage_checks': len(references), 'status': result['status'], 'original_source_unchanged': True, 'image_id': result['execution_image_id'], 'job_id': result['job_id']})

target = OUT / 'verification.json'
target.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
print(json.dumps(report, ensure_ascii=False, indent=2))

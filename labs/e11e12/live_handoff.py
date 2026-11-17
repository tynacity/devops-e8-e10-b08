"""B's E13 entry for an independently produced incremental report."""
import hashlib
import json
import math
from pathlib import Path
import re
import subprocess
import uuid

from pipeline import ROOT, Failure, artifact, command, save, snapshot
from tinyexpr_repair import consume


def validate_request(request):
    """Validate input shape and path boundaries before queuing an API job."""
    for key in ('base', 'target', 'report_sha256'):
        value = request.get(key)
        width = 64 if key == 'report_sha256' else 40
        if not isinstance(value, str) or not re.fullmatch('[0-9a-f]{%d}' % width, value):
            raise Failure('INVALID_REQUEST', f'{key} must be a full lowercase hex value')
    profile = request.get('profile', 'explicit')
    if profile not in ('explicit', 'tinyexpr'):
        raise Failure('INVALID_REQUEST', 'Expected profile explicit or tinyexpr')
    if not isinstance(request.get('expected_output'), str):
        raise Failure('INVALID_REQUEST', 'Provide the actual expected program output')
    timeout = request.get('build_timeout', 600)
    if (type(timeout) not in (int, float) or not 0 < timeout <= 3600 or not math.isfinite(timeout)):
        raise Failure('INVALID_REQUEST', 'build_timeout must be a positive number up to 3600 seconds')
    paths = {}
    data = ROOT / 'data'
    for key in ('repo', 'candidate', 'report', 'producer_manifest'):
        value = request.get(key)
        if not isinstance(value, str) or not value:
            raise Failure('INVALID_REQUEST', f'{key} is required')
        path = Path(value).resolve()
        if not path.is_relative_to(data) or path == data:
            raise Failure('INVALID_REQUEST', f'{key} must be below {data}')
        if not (path.is_dir() if key == 'repo' else path.is_file()):
            raise Failure('INVALID_REQUEST', f'{key} is not available')
        paths[key] = path
    return paths


def execute_handoff(request, out, job_id=None):
    """Validate A's original bytes, build B's image, and run MDFixer inside it."""
    out = out.resolve()
    work = ROOT / 'work'
    if out == work or not out.is_relative_to(work):
        raise Failure('INVALID_REQUEST', 'Use a new output directory below work/')
    try:
        out.mkdir(parents=True, exist_ok=False)
    except FileExistsError as exc:
        raise Failure('OUTPUT_EXISTS', 'Use a new output directory') from exc
    job_id = job_id or 'job-' + uuid.uuid4().hex
    trace_id = 'trace-' + uuid.uuid4().hex
    result = dict(schema_version='e11e12-1', mode='e13-b', job_id=job_id, trace_id=trace_id,
                  status='RUNNING', stages=[])
    runtime = None
    save(out / 'request.json', request)

    def stage(name, data, *files):
        path = out / (name + '.json')
        save(path, dict(schema_version='e11e12-1', job_id=job_id, trace_id=trace_id,
                        kind=name, commit=request['target'], status='SUCCEEDED', data=data,
                        artifacts=[artifact(p, out, job_id) for p in files]))
        result['stages'].append(dict(name=name, artifact=artifact(path, out, job_id)))

    try:
        paths = validate_request(request)
        target = request['target']
        result.update(base_commit=request['base'], target_commit=target)
        incoming = out / 'incoming'
        incoming.mkdir()
        report = incoming / 'incremental-check.json'
        manifest = incoming / 'producer-result.json'
        candidate = incoming / 'candidate.Dockerfile'
        for key, path in (('report', report), ('producer_manifest', manifest), ('candidate', candidate)):
            path.write_bytes(paths[key].read_bytes())
        envelope = consume(report, target, manifest, request['report_sha256'])
        producer = json.loads(manifest.read_bytes())
        if producer.get('base_commit') != request['base']:
            raise Failure('STALE_REPORT', 'Producer baseline differs')
        entry, = [s['artifact'] for s in producer['stages'] if s['name'] == 'incremental-check']
        if type(entry.get('bytes')) != int or entry['bytes'] != report.stat().st_size:
            raise Failure('ARTIFACT_HASH_MISMATCH', 'Report size differs from producer manifest')
        source_report = dict(
            job_id=envelope['job_id'], trace_id=envelope['trace_id'], commit=target,
            uri=entry['uri'], sha256=request['report_sha256'],
            producer_manifest_sha256=hashlib.sha256(manifest.read_bytes()).hexdigest())
        result['source_report'] = source_report
        stage('consume-a', source_report, report, manifest)

        profile = request.get('profile', 'explicit')
        build_project = out / 'draft-project'
        snapshot(paths['repo'], target, build_project, out / 'logs',
                 'tinyexpr' if profile == 'tinyexpr' else None)
        from draft.autobuild import auto_build
        draft = auto_build(build_project, candidate, out / 'draft-build', request['expected_output'],
                           timeout=request.get('build_timeout', 600))
        if draft['status'] != 'SUCCEEDED':
            raise Failure('DRAFT_FAILED', draft.get('error') or 'Inspect draft-build logs')
        image = draft['attempts'][-1]['image_id']
        verification = draft['verification']
        if verification['exit_code'] != 0 or not verification['output_matches'] or image not in verification['command']:
            raise Failure('DRAFT_IMAGE_UNVERIFIED', 'DRAFT did not verify the selected image')
        if command(['docker', 'image', 'inspect', '--format', '{{.Id}}', image],
                   ROOT, out / 'logs/draft-image-inspect.log') != image:
            raise Failure('DRAFT_IMAGE_MISMATCH', 'The inspected image differs from DRAFT output')
        stage('draft', draft, out / 'draft-build/result.json', candidate)

        from draft_runtime import DraftRuntime
        runtime = DraftRuntime(ROOT, out, image)
        result['execution_image_id'] = runtime.image_id
        component_request = out / 'mdfixer-request.json'
        save(component_request, dict(profile=profile, repo=runtime.mapped(paths['repo']), target=target,
                                     report=runtime.mapped(report), producer_manifest=runtime.mapped(manifest),
                                     report_sha256=request['report_sha256']))
        repair_dir = out / 'mdfixer'
        repair = runtime.run('mdfixer', paths['repo'], evidence=repair_dir, component_request=component_request)
        result['original_source_unchanged'] = repair.get('original_source_unchanged')
        if repair['status'] != 'SUCCEEDED':
            error = repair['error']
            raise Failure(error['code'], error['message'])
        if repair.get('original_source_unchanged') is not True:
            raise Failure('SOURCE_CHANGED', 'MDFixer could not establish input protection')
        if repair.get('input') != dict(kind='incremental-check', sha256=source_report['sha256'],
                                       commit=target, job_id=source_report['job_id'],
                                       trace_id=source_report['trace_id']):
            raise Failure('ARTIFACT_ID_MISMATCH', 'MDFixer did not return the accepted A report identity')
        if ((repair_dir / 'consumed-report.json').read_bytes() != report.read_bytes()
                or (repair_dir / 'producer-result.json').read_bytes() != manifest.read_bytes()):
            raise Failure('ARTIFACT_HASH_MISMATCH', 'MDFixer consumed different input bytes')
        verdict = repair['validation']
        final = json.loads((repair_dir / 'recheck.json').read_bytes())
        if not verdict['accepted']:
            raise Failure('REPAIR_REJECTED', 'MDFixer did not accept the candidate')
        if final['status'] != 'SUCCEEDED' or any(f['type'] == 'MISSING' for f in final['findings']):
            raise Failure('RECHECK_FAILED', 'Dynamic recheck did not clear missing dependencies')
        stage('repair', dict(source_report=source_report, validation=verdict), repair_dir / 'result.json',
              repair_dir / 'candidate.patch', repair_dir / 'validation/validation.json')
        stage('recheck', dict(findings=final['findings'], remaining_missing=0), repair_dir / 'recheck.json')
        result['status'] = 'SUCCEEDED'
    except subprocess.TimeoutExpired as exc:
        result.update(status='TIMED_OUT', error=dict(code='COMMAND_TIMEOUT', message=str(exc)))
    except (ValueError, OSError, KeyError, TypeError, AttributeError, subprocess.SubprocessError) as exc:
        result.update(status='FAILED', error=dict(code=getattr(exc, 'code', 'EXECUTION_FAILED'), message=str(exc)))
    if runtime:
        save(out / 'execution-runtime.json', dict(image_id=runtime.image_id, operations=runtime.records))
    result['artifacts'] = [artifact(p, out, job_id) for p in sorted(out.rglob('*'))
                           if p.is_file() and '.git' not in p.parts and not p.is_symlink()]
    save(out / 'result.json', result)
    return result

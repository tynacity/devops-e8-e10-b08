"""Run paired-project role work via the DRAFT service's job-bound image."""
import hashlib
import json
import math
import re
import time
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from draft_runtime import DraftRuntime
from pipeline import Failure, TINYEXPR_TARGETS, artifact, command, normalized, save, tinyexpr_detector
from tinyexpr_repair import consume


PROFILES = ('explicit', 'tinyexpr')
STEPS = ('baseline', 'target', 'scan-base', 'scan-target', 'repair', 'recheck')
RUNTIME_TIMEOUT = 930
RUNTIME_URL = 'http://draft:8080/v1/runtime'
IMAGE_PATTERN = r'sha256:[0-9a-f]{64}'


def require(condition, code, message):
    if not condition:
        raise Failure(code, message)


def build_budget(value):
    require(type(value) in (int, float) and math.isfinite(value) and 0 < value <= 3600,
            'INVALID_REQUEST', 'Expected a build timeout above zero and at most 3600 seconds')
    return value


def json_file(path):
    return json.loads(path.read_bytes())


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def report_identity(envelope, data):
    require((envelope['job_id'], envelope['trace_id'], envelope['commit']) ==
            (data['job_id'], data['trace_id'], data['target_commit']),
            'ARTIFACT_ID_MISMATCH', 'Incremental report is not from this task')


class RuntimeSessions:
    def __init__(self, root):
        self.root = root
        self.jobs = {}

    def register(self, data, project, out, drafted):
        job, trace, profile = data['job_id'], data['trace_id'], data['profile']
        require(re.fullmatch(r'job-[0-9a-f]{32}', job) and re.fullmatch(r'trace-[0-9a-f]{32}', trace),
                'INVALID_REQUEST', 'A complete job and trace ID are required')
        require(profile in PROFILES and re.fullmatch(r'[0-9a-f]{40}', data['target_commit']),
                'INVALID_REQUEST', 'Unknown profile or invalid target commit')
        now = time.monotonic()
        self.jobs = {key: item for key, item in self.jobs.items() if now - item['last_used'] < 3600}
        require(job not in self.jobs and len(self.jobs) < 16, 'RUNTIME_BUSY', 'Job is already bound or runtime capacity was reached')
        task = out.parent
        require(out.name == 'draft-build' and project == task / 'target-project' and (task / 'base-project').is_dir(),
                'INVALID_REQUEST', 'Expected isolated base, target and draft folders for this task')
        verification = drafted['verification']
        image = drafted['attempts'][-1]['image_id']
        require(re.fullmatch(IMAGE_PATTERN, image) and verification['exit_code'] == 0 and
                verification['output_matches'] is True and verification['command'][-1] == image,
                'DRAFT_IMAGE_UNVERIFIED', 'DRAFT did not verify the chosen image')
        require(command(['docker', 'image', 'inspect', '--format', '{{.Id}}', image], self.root,
                        out / 'execution-image-inspect.log') == image,
                'DRAFT_IMAGE_MISMATCH', 'Built and inspected image IDs differ')
        detector = tinyexpr_detector(task / 'logs') if profile == 'tinyexpr' else None
        runtime = DraftRuntime(self.root, task, image, detector=detector)
        self.jobs[job] = dict(task=task, runtime=runtime, detector=detector, trace_id=trace, profile=profile,
                              target_commit=data['target_commit'], step=0, last_used=now)
        return image

    def execute(self, data):
        require(set(data) <= {'job_id', 'trace_id', 'profile', 'target_commit', 'slot', 'report_sha256'},
                'INVALID_REQUEST', 'Runtime accepts only job identity and a named slot')
        session = self.jobs.get(data['job_id'])
        require(session is not None and time.monotonic() - session['last_used'] < 3600 and
                all(data.get(key) == session[key] for key in ('trace_id', 'profile', 'target_commit')),
                'RUNTIME_ID_MISMATCH', 'No matching DRAFT job binding')
        slot = data['slot']
        require(slot == STEPS[session['step']], 'RUNTIME_ORDER_MISMATCH', 'Runtime slot is out of order')
        task = session['task']
        runtime = session['runtime']
        source = task / 'target-project'
        component = task / 'repair-work/component'
        runtime.detector = session['detector'] if slot != 'repair' else None
        try:
            if slot == 'baseline':
                result = runtime.run('full', task / 'base-project', evidence=task / 'baseline-full')
            elif slot == 'target':
                result = runtime.run('full', source, evidence=task / 'target-full')
            elif slot == 'scan-base':
                result = runtime.run('scan', task / 'base-project')
            elif slot == 'scan-target':
                result = runtime.run('scan', source, cache=task / 'incremental/baseline-cache.json')
            elif slot == 'repair':
                result = self.repair(runtime, task, source, component, data)
            else:
                result = runtime.run('full', component / 'target-project', evidence=task / 'final-full')
            session['step'] += 1
            session['last_used'] = time.monotonic()
            if slot == 'recheck':
                self.jobs.pop(data['job_id'])
            return {'status': 'SUCCEEDED', 'result': result, 'execution_image_id': runtime.image_id}
        except Exception:
            self.jobs.pop(data['job_id'], None)
            raise
        finally:
            save(task / 'execution-runtime.json', dict(image_id=runtime.image_id, operations=runtime.records))

    @staticmethod
    def repair(runtime, task, source, component, data):
        report = task / 'incremental/incremental-check.json'
        producer = task / 'incremental/producer-result.json'
        request_path = task / 'repair-work/component-request.json'
        expected = data['report_sha256']
        report_identity(consume(report, data['target_commit'], producer, expected), data)
        manifest = json_file(producer)
        binding = manifest['stages'][0]['artifact']
        require(binding['bytes'] == report.stat().st_size and binding['sha256'] == expected,
                'ARTIFACT_HASH_MISMATCH', 'Report byte length or digest does not match producer')
        save(request_path, dict(profile=data['profile'], repo=runtime.mapped(source), target=data['target_commit'],
                                report=runtime.mapped(report), producer_manifest=runtime.mapped(producer), report_sha256=expected))
        result = runtime.run('mdfixer', source, evidence=component, component_request=request_path)
        if result['status'] != 'SUCCEEDED':
            raise Failure(result['error']['code'], result['error']['message'])
        require(result.get('original_source_unchanged') is True and result['validation']['accepted'] is True,
                'REPAIR_REJECTED', 'Repair or source protection did not pass')
        info = result.get('input', {})
        require(info == dict(kind='incremental-check', commit=data['target_commit'], sha256=expected,
                             job_id=data['job_id'], trace_id=data['trace_id']), 'ARTIFACT_ID_MISMATCH', 'Repair input identity differs')
        require((component / 'consumed-report.json').read_bytes() == report.read_bytes() and
                (component / 'producer-result.json').read_bytes() == producer.read_bytes(),
                'ARTIFACT_HASH_MISMATCH', 'Repair saved different input bytes')
        return result


def call_runtime(data, slot, **extra):
    payload = {key: data[key] for key in ('job_id', 'trace_id', 'profile', 'target_commit')}
    request = Request(RUNTIME_URL, data=json.dumps(dict(payload, slot=slot, **extra)).encode(),
                      headers={'Content-Type': 'application/json'})
    try:
        with urlopen(request, timeout=RUNTIME_TIMEOUT) as response:
            result = json.load(response)
    except HTTPError as error:
        detail = json.load(error)
        raise Failure(detail.get('error_code', 'DRAFT_RUNTIME_FAILED'), detail.get('error', 'DRAFT runtime failed')) from error
    require(result['status'] == 'SUCCEEDED' and result['execution_image_id'] == data['execution_image_id'],
            'DRAFT_IMAGE_MISMATCH', 'Downstream stage did not use the bound image')
    return result['result']


def paired_role(role, data, out, project, local, wire):
    profile = data['profile']
    require(profile in PROFILES, 'INVALID_REQUEST', 'Unknown paired profile')
    image = data['execution_image_id']
    task = out.parent
    if role == 'buildchecker':
        folders = {'baseline-full': ('baseline', task / 'base-project'),
                   'target-full': ('target', task / 'target-project'),
                   'final-full': ('recheck', task / 'repair-work/component/target-project')}
        require(out.name in folders and folders[out.name][1] == project, 'INVALID_REQUEST', 'Unexpected BuildChecker stage path')
        result = call_runtime(data, folders[out.name][0])
        require(result['status'] == 'SUCCEEDED', 'FULL_CHECK_FAILED', result.get('error') or 'Full check failed')
        return dict(status='SUCCEEDED', result=result, artifact=wire(out / 'findings.json'), execution_image_id=image)
    require(project == task / 'target-project', 'INVALID_REQUEST', 'Expected current task target snapshot')
    if role == 'echecker':
        require(out.name == 'incremental' and local(data['base']) == task / 'base-project' and
                local(data['baseline_graph']) == task / 'baseline-full/actual-graph.json' and
                local(data['target_findings']) == task / 'target-full/findings.json',
                'INVALID_REQUEST', 'Unexpected EChecker stage path')
        targets = TINYEXPR_TARGETS if profile == 'tinyexpr' else ('main.o', 'helper.o')
        old = call_runtime(data, 'scan-base')
        graph = json_file(task / 'baseline-full/actual-graph.json')
        projected = {target: sorted({edge['dependency'] for edge in graph if edge['target'] == target}) for target in targets}
        require(projected == old['actual'], 'GRAPH_MISMATCH', 'Baseline BuildChecker and EChecker graphs differ')
        old['actual'] = projected
        save(out / 'baseline-cache.json', old)
        current = call_runtime(data, 'scan-target')
        reference = json_file(task / 'target-full/findings.json')
        require(reference['status'] == 'SUCCEEDED' and current['commit'] == data['target_commit'],
                'STALE_REPORT', 'Expected successful target report from this commit')
        if profile == 'tinyexpr':
            require(all(set(observed) == set(targets) for observed in (current['actual'], current['declared'], reference['observed_targets'])),
                    'TARGET_COVERAGE_MISMATCH', 'TinyExpr must cover both objects and the example link')
        match_scope = None if profile == 'tinyexpr' else targets
        require(normalized(current['findings'], match_scope) == normalized(reference['findings'], match_scope),
                'FINDINGS_MISMATCH', 'Incremental and full findings differ')
        job, trace, target = data['job_id'], data['trace_id'], data['target_commit']
        report = out / 'incremental-check.json'
        save(report, dict(schema_version='e11e12-1', kind='incremental-check', status='SUCCEEDED', commit=target,
                          job_id=job, trace_id=trace, data=current))
        producer = out / 'producer-result.json'
        save(producer, dict(schema_version='e11e12-1', status='SUCCEEDED', job_id=job, trace_id=trace, target_commit=target,
                            stages=[dict(name='incremental-check', artifact=artifact(report, out, job))]))
        return dict(status='SUCCEEDED', report=wire(report), producer_manifest=wire(producer), sha256=digest(report),
                    findings=current['findings'], execution_image_id=image)
    if role == 'mdfixer':
        require(out.name == 'repair-work' and local(data['report']) == task / 'incremental/incremental-check.json' and
                local(data['producer_manifest']) == task / 'incremental/producer-result.json',
                'INVALID_REQUEST', 'Unexpected MDFixer stage path')
        result = call_runtime(data, 'repair', report_sha256=data['report_sha256'])
        component = out / 'component'
        candidate = component / 'candidate.patch'
        return dict(status='SUCCEEDED', patch=wire(candidate), sha256=digest(candidate), validation=result['validation'],
                    repaired_project=wire(component / 'target-project'), execution_image_id=image, input_report=result['input'])
    raise Failure('INVALID_REQUEST', 'Unknown paired-project role')

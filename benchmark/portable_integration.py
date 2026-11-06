"""Independent SuiteBridge integration comparison; no product imports.

Each output directory is a new retained attempt. Default scope is all frozen
F01-F28 variants, R0-R5, and two explicit module-selection probes. --cases is
for a clearly labeled diagnostic subset and cannot produce a full gate pass.
"""
import argparse
from collections import Counter
import hashlib
import json
import os
from pathlib import Path
import resource
import shutil
import signal
import subprocess
import sys
import time
import xml.etree.ElementTree as ET

ROOT = Path(__file__).absolute().parent.parent
# Configured explicitly by main(); preserve venv executable symlink paths.
TARGET = None
FRONTEND = None
CORPUS = None
OBSERVER = ROOT / 'benchmark/native_observer.py'
ATOMIC = ROOT / 'benchmark/atomic_observer_wrapper.py'
STRICT = ['--assert=plain', '--capture=no', '-p', 'no:warnings', '-p', 'no:cacheprovider', '--color=no']
EVENT_FIELDS = {'sequence', 'kind', 'id', 'parent_id', 'occurrence', 'exception_type', 'message', 'reason'}
FAILURES = {'failure', 'error', 'subtest_failure', 'subtest_error', 'unexpected_success'}
EVALUATOR_VERSION = 2


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text())


def save(path, value):
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + '\n')


def tree_manifest(root):
    return {p.relative_to(root).as_posix(): sha(p) for p in sorted(root.rglob('*'))
            if p.is_file() and '__pycache__' not in p.parts and p.suffix != '.pyc'}


def normalize(value, roots):
    """Only declared fresh worktree prefixes differ between native observations."""
    if isinstance(value, str):
        for root in sorted({str(p) for p in roots}, key=len, reverse=True):
            value = value.replace(root, '<WORKTREE>')
        return value
    if isinstance(value, list):
        return [normalize(item, roots) for item in value]
    if isinstance(value, dict):
        return {key: normalize(item, roots) for key, item in value.items()}
    return value


def native_events(payload, roots):
    events = payload['events']
    if not isinstance(events, list):
        raise ValueError('Native events must be a list')
    projected = []
    for index, event in enumerate(events):
        if set(event) - EVENT_FIELDS - {'group_id'}:
            raise ValueError('Undeclared native event metadata: ' + repr(set(event) - EVENT_FIELDS))
        if event.get('sequence') != index:
            raise ValueError('Native event sequence is missing, repeated or reordered')
        projected.append({key: value for key, value in event.items() if key != 'group_id'})
    return normalize(projected, roots)


def trace_parts(path, mixed=False, roots=()):
    rows = [] if not path.exists() else [json.loads(line) for line in path.read_text().splitlines()]
    frontend, native = [], []
    for row in rows:
        if mixed and row and row[0] in {'frontend.body', 'frontend.warning_filter'}:
            frontend.append(row)
        else:
            native.append(row)
    return normalize(native, roots), normalize(frontend, roots)


def compare_native(reference, candidate, reference_trace, candidate_trace, roots):
    issues = []
    status = {'completed': 'complete', 'empty_selection': 'complete'}
    if reference['status'] != status.get(candidate['status'], candidate['status']):
        issues.append('Native completion status differs')
    for key in ['discovered', 'selected_inventory', 'tests_run', 'successful', 'executed', 'loader_errors', 'fatal_error']:
        if normalize(reference.get(key), roots) != normalize(candidate.get(key), roots):
            issues.append('Native ' + key + ' differs')
    a, b = native_events(reference, roots), native_events(candidate, roots)
    if a != b:
        first = next((i for i, pair in enumerate(zip(a, b)) if pair[0] != pair[1]), min(len(a), len(b)))
        issues.append(f'Ordered native callback events differ at {first}; lengths {len(a)}/{len(b)}')
    if reference_trace != candidate_trace:
        issues.append('Ordered native fixture/body/cleanup trace differs')
    reference_env = reference.get('target_environment', reference.get('environment', {}))
    candidate_env = candidate.get('target_environment', candidate.get('environment', {}))
    for key in ['executable', 'version', 'sys_path', 'dependencies', 'pygments_present']:
        if normalize(reference_env.get(key), roots) != normalize(candidate_env.get(key), roots):
            issues.append('Native target environment ' + key + ' differs')
    for label, payload in [('reference', reference), ('candidate', candidate)]:
        starts = [e for e in payload['events'] if e['kind'] == 'start']
        if len(starts) != payload['tests_run']:
            issues.append(label + ' native start count disagrees with tests_run')
        if [e.get('occurrence') for e in starts] != list(range(1, len(starts) + 1)):
            issues.append(label + ' native occurrence ordinals are not global and sequential')
        env = payload.get('target_environment', payload.get('environment', {}))
        if env.get('executable') != str(TARGET):
            issues.append(label + ' did not use the exact target venv executable path')
        if env.get('pygments_present') is not False:
            issues.append(label + ' target Pygments absence was not established')
    return issues


def parse_junit(path):
    root = ET.parse(path).getroot()
    suites = [root] if root.tag == 'testsuite' else list(root.findall('.//testsuite'))
    if not suites:
        raise ValueError('JUnit contains no testsuite element')
    result = {'testcases': [], 'issues': [], 'counts': {'tests': 0, 'failures': 0, 'errors': 0, 'skipped': 0}}
    for suite in suites:
        cases = list(suite.findall('testcase'))
        actual = {'tests': len(cases), 'failures': sum(c.find('failure') is not None for c in cases),
                  'errors': sum(c.find('error') is not None for c in cases),
                  'skipped': sum(c.find('skipped') is not None for c in cases)}
        for key, value in actual.items():
            result['counts'][key] += value
            if int(suite.get(key, '-1')) != value:
                result['issues'].append('JUnit declared ' + key + ' does not match testcase elements')
        for case in cases:
            result['testcases'].append({'name': case.get('name'), 'classname': case.get('classname'),
                'failure': case.find('failure') is not None, 'error': case.find('error') is not None,
                'skipped': case.find('skipped') is not None,
                'detail': ''.join(case.itertext())})
    return result


def reporting_finding(role, message, issues, observations):
    """Baseline report defects stay visible without requiring the product to copy them."""
    if role == 'atomic':
        observations.append('atomic: ' + message)
    else:
        issues.append(role + ': ' + message)


def group_reporting_issues(public, native, groups, xml):
    issues = []
    plan = {g['group_id']: g for g in public['planned_groups']}
    flattened = []
    for group in public['group_results']:
        identifier = group['group_id']
        data = groups[identifier]
        declared = plan[identifier]
        name = ('native-suite[atomic]' if declared['mode'] == 'atomic'
                else 'native-module[' + declared['module_name'] + ']')
        entries = [entry for entry in xml['testcases'] if entry['name'] == name]
        if len(entries) != 1:
            issues.append('Group ' + identifier + ' has no unique JUnit item')
            continue
        entry = entries[0]
        events = [e for e in data['events'] if e['kind'] not in {'run_start', 'run_stop'}]
        flattened.extend(events)
        if any(e.get('group_id') != identifier for e in events):
            issues.append('Group event metadata assigns events to another group')
        if declared['mode'] == 'module':
            module = declared['module_name']
            for event in events:
                parent = event.get('parent_id') or event.get('id') or ''
                belongs = (parent.startswith(module + '.') or parent.endswith('(' + module + ')')
                           or '(' + module + '.' in parent)
                if not belongs:
                    issues.append('Native event parent does not belong to declared module ' + module)
                    break
        failure_events = [e for e in events if e['kind'] in FAILURES]
        if data['tests_run'] != sum(e['kind'] == 'start' for e in events):
            issues.append('Group native test count differs from its start events')
        if data['status'] == 'completed':
            if data['successful'] != (not failure_events):
                issues.append('Group success flag differs from native outcome events')
            if failure_events:
                if not (entry['failure'] or entry['error']) or entry['skipped']:
                    issues.append('Native failing group is not a failed JUnit item')
                for event in failure_events:
                    if str(event['id']) not in entry['detail']:
                        issues.append('Group JUnit omitted its native failing identity ' + str(event['id']))
                    if event.get('exception_type') and event['exception_type'] not in entry['detail']:
                        issues.append('Group JUnit omitted its native exception type')
            elif not any(e['kind'] == 'success' for e in events):
                if not entry['skipped'] or entry['failure'] or entry['error']:
                    issues.append('No-success native group was represented as a passing or failed normal test')
            elif entry['failure'] or entry['error'] or entry['skipped']:
                issues.append('Successful native group has an inconsistent JUnit outcome')
        elif data['status'] == 'interrupted':
            detail = entry['detail'].lower()
            if not (entry['failure'] or entry['error']) or entry['skipped']:
                issues.append('Interrupted native group lacks a named nonpassing JUnit outcome')
            if 'interrupted' not in detail or 'not a native assertion failure' not in detail:
                issues.append('Interrupted group JUnit does not distinguish interruption from native assertion failure')
        else:
            issues.append('Group reporting is incomplete: ' + str(data['status']))
    expected = [e for e in native['events'] if e['kind'] not in {'run_start', 'run_stop'}]
    if flattened != expected:
        issues.append('Group artifacts do not exactly partition the final native callback sequence')
    actual_names = [entry['name'] for entry in xml['testcases'] if entry['name'] and entry['name'].startswith('native-')]
    expected_names = [('native-suite[atomic]' if plan[g['group_id']]['mode'] == 'atomic'
                       else 'native-module[' + plan[g['group_id']]['module_name'] + ']')
                      for g in public['group_results']]
    if Counter(actual_names) != Counter(expected_names):
        issues.append('JUnit contains missing, extra or duplicated executed native group items')
    return issues


def proc_identity(pid):
    try:
        values = Path(f'/proc/{pid}/stat').read_text().rpartition(') ')[2].split()
        return {'pid': pid, 'parent': int(values[1]), 'group': int(values[2]),
                'start': int(values[19]), 'state': values[0]}
    except (FileNotFoundError, ProcessLookupError, IndexError):
        return None


def observe_descendants(pid, owned):
    identity = proc_identity(pid)
    if identity is None:
        return
    owned.setdefault(pid, identity)
    try:
        children = Path(f'/proc/{pid}/task/{pid}/children').read_text().split()
    except FileNotFoundError:
        return
    for child in children:
        observe_descendants(int(child), owned)


def terminate_owned(owned):
    killed = []
    for pid, expected in reversed(list(owned.items())):
        actual = proc_identity(pid)
        if actual is not None and actual['start'] == expected['start'] and actual['state'] != 'Z':
            try:
                os.kill(pid, signal.SIGKILL)
                killed.append(pid)
            except ProcessLookupError:
                pass
    return killed


def run_process(command, cwd, env, log_path, watchdog=45):
    before = resource.getrusage(resource.RUSAGE_CHILDREN)
    started = time.perf_counter()
    owned = {}
    with log_path.open('xb') as stream:
        process = subprocess.Popen(command, cwd=cwd, env=env, stdout=stream,
                                   stderr=subprocess.STDOUT, start_new_session=True)
        status = 'completed'
        while True:
            observe_descendants(process.pid, owned)
            try:
                code = process.wait(timeout=0.1)
                break
            except subprocess.TimeoutExpired:
                if time.perf_counter() - started >= watchdog:
                    status = 'experimental_watchdog_timeout'
                    terminate_owned(owned)
                    code = process.wait()
                    break
        remaining = terminate_owned(owned)
        if remaining and status == 'completed':
            status = 'remaining_descendants_terminated'
    after = resource.getrusage(resource.RUSAGE_CHILDREN)
    return {'command': command, 'cwd': str(cwd), 'exit_code': code, 'status': status,
            'cpu_seconds': after.ru_utime + after.ru_stime - before.ru_utime - before.ru_stime,
            'wall_seconds': time.perf_counter() - started, 'log_sha256': sha(log_path),
            'owned_process_identities': list(owned.values()), 'terminated_remaining_pids': remaining,
            'watchdog_seconds': watchdog,
            'cpu_accounting': ('Linux waited-process CPU includes descendants waited by frontend; child diagnostic receipts are not added again.'
                               if status == 'completed' else 'Observed waited CPU only; abrupt orphaned descendant cost may be incomplete.')}


def validate_freeze():
    freeze = read(ROOT / 'benchmark/portable-source-freeze.json')
    for path, expected in freeze['files'].items():
        if sha(ROOT / path) != expected:
            raise ValueError('Preimplementation frozen source changed: ' + path)
    expected_corpus = read(ROOT / 'benchmark/corpus-manifest.json')
    if tree_manifest(CORPUS) != expected_corpus:
        raise ValueError('Pinned real corpus differs from retained base manifest')


def cases():
    fixture_manifest = read(ROOT / 'benchmark/frozen-fixtures/manifest.json')
    result = [{'key': p['project_key'], 'kind': 'fixture', 'entry': p, 'module': None}
              for p in fixture_manifest['projects']]
    result += [{'key': p['id'], 'kind': 'real', 'entry': p, 'module': None}
               for p in read(ROOT / 'benchmark/real-corpus-variants.json')['variants']]
    for base, module in [('F28/main', 'test_b'), ('R3', 'test_extensions')]:
        parent = next(p for p in result if p['key'] == base)
        result.append(dict(parent, key=base + '/selected-' + module, module=module))
    return result


def materialize(case, work):
    if case['kind'] == 'fixture':
        source = ROOT / 'benchmark/frozen-fixtures' / case['entry']['project_key']
        shutil.copytree(source, work, ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
        for path, expected in case['entry']['source_sha256'].items():
            if sha(work / path) != expected:
                raise ValueError('Fixture copy hash mismatch')
    else:
        shutil.copytree(CORPUS, work, ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
        for patch in case['entry']['patches']:
            path = work / patch['path']
            if patch['op'] == 'create':
                if path.exists():
                    raise ValueError('New real-case path exists')
                text = patch['after']
            else:
                if sha(path) != patch['base_sha256']:
                    raise ValueError('Real-case base hash mismatch')
                text = path.read_text()
                if text.count(patch['before']) != patch['expected_occurrences']:
                    raise ValueError('Real-case literal occurrence mismatch')
                text = text.replace(patch['before'], patch['after'])
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text)
            if sha(path) != patch['mutated_sha256']:
                raise ValueError('Real-case mutated hash mismatch')


def environment(trace, work):
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE='1', PYTHONHASHSEED='0',
               PYTHONNOUSERSITE='1', NATIVE_FIXTURE_TRACE=str(trace))
    for key in list(env):
        if key.startswith(('PYTEST_', 'INTEGRATION_')) or key in {'PYTHONPATH', 'PYTHONHOME', 'PYGMENTS_VERSION'}:
            env.pop(key)
    return env


def execute(case, role, directory):
    directory.mkdir(parents=True, exist_ok=False)
    work = directory / 'worktree'
    materialize(case, work)
    initial = tree_manifest(work)
    trace = directory / 'trace.jsonl'
    env = environment(trace, work)
    module = case['module']
    mixed = case['entry'].get('id') == 'F27'
    report = directory / ('bridge-report/native.json' if role == 'bridge' else 'native-report/native.json')
    junit = directory / 'pytest.xml'
    if role == 'native':
        command = [str(TARGET), str(OBSERVER), '--root', str(work), '--tests', 'tests', '--output', str(report)]
        if module:
            command += ['--module', module]
    else:
        env['PYTHONPATH'] = str(ROOT)
        env.update(PYTEST_DISABLE_PLUGIN_AUTOLOAD='1', PYTEST_ADDOPTS='', PYTEST_PLUGINS='')
        if role == 'atomic':
            env.update(INTEGRATION_NATIVE_ROOT=str(work), INTEGRATION_NATIVE_OUTPUT=str(report),
                       INTEGRATION_NATIVE_PYTHON=str(TARGET))
            paths = [str(ATOMIC)]
            extra = []
        else:
            paths = ['tests' + (f'::native-module[{module}]' if module else '')]
            extra = ['-p', 'suitebridge', '--native-unittest', 'tests', '--native-root', str(work),
                     '--native-python', str(TARGET), '--native-report', str(report)]
        if mixed:
            paths.append('ordinary_pytest_tests')
        command = [str(FRONTEND), '-m', 'pytest', *paths, '--rootdir', str(work), '-q', '--tb=short',
                   '--junitxml', str(junit), *STRICT, *extra]
    receipt = run_process(command, work, env, directory / 'process.log')
    receipt['environment_overrides'] = {k: env.get(k) for k in ['PYTHONDONTWRITEBYTECODE', 'PYTHONHASHSEED',
        'PYTHONNOUSERSITE', 'PYTEST_DISABLE_PLUGIN_AUTOLOAD', 'PYTEST_ADDOPTS', 'PYTEST_PLUGINS',
        'PYTHONPATH', 'PYTHONHOME', 'PYGMENTS_VERSION', 'NATIVE_FIXTURE_TRACE']}
    receipt['source_unchanged'] = tree_manifest(work) == initial
    receipt['source_manifest_sha256'] = hashlib.sha256(json.dumps(initial, sort_keys=True).encode()).hexdigest()
    save(directory / 'source-manifest.json', initial)
    receipt['artifact_hashes'] = {p.relative_to(directory).as_posix(): sha(p) for p in sorted(directory.rglob('*'))
                                 if p.is_file() and work not in p.parents}
    save(directory / 'receipt.json', receipt)
    return {'role': role, 'directory': directory, 'work': work, 'trace': trace,
            'report_path': report, 'junit_path': junit, 'receipt': receipt, 'mixed': mixed}


def load_native(invocation):
    report = read(invocation['report_path'])
    if invocation['role'] != 'bridge':
        return report, report, [], {}
    issues = []
    relative = report.get('native_artifact')
    if not isinstance(relative, str):
        raise ValueError('Bridge final native artifact is absent')
    part = Path(relative)
    if part.is_absolute() or '..' in part.parts:
        raise ValueError('Bridge artifact escapes output directory')
    path = invocation['report_path'].parent / part
    if sha(path) != report.get('native_artifact_sha256'):
        raise ValueError('Bridge final native artifact hash mismatch')
    native = read(path)
    if native['events'] != report['events']:
        issues.append('Public bridge callbacks differ from final native artifact')
    if report.get('native_successful') != native['successful']:
        issues.append('Public native_successful differs from native artifact')
    if report.get('pytest_exitstatus') != invocation['receipt']['exit_code']:
        issues.append('Public pytest exit status differs from process exit')
    groups = {}
    for group in report.get('group_results', []):
        relative = Path(group['artifact'])
        if relative.is_absolute() or '..' in relative.parts:
            raise ValueError('Group artifact escapes output directory')
        group_path = invocation['report_path'].parent / relative
        if sha(group_path) != group['sha256']:
            issues.append('Group artifact hash mismatch')
        if group['group_id'] in groups:
            issues.append('Duplicate executed group artifact')
        data = read(group_path)
        if data.get('group_id') != group['group_id'] or data.get('status') != group['status']:
            issues.append('Group artifact identity/status differs from public report')
        groups[group['group_id']] = data
    return native, report, issues, groups


def check_invocation(invocation, native, public):
    issues, observations = [], []
    receipt, role = invocation['receipt'], invocation['role']
    if receipt['status'] != 'completed':
        issues.append(role + ': process watchdog/cleanup failure')
    if not receipt['source_unchanged']:
        issues.append(role + ': source tree changed during execution')
    if native['status'] == 'interrupted':
        expected_codes = {130} if role == 'native' else {2}
    elif native['status'] in {'complete', 'completed', 'empty_selection'}:
        expected_codes = {0 if native['successful'] else 1}
        if (role == 'bridge' and native['tests_run'] == 0 and not native['executed']
                and not native.get('loader_errors') and not public.get('selected_groups')):
            expected_codes = {0, 5}
    else:
        issues.append(role + ': unexpected incomplete native status ' + str(native['status']))
        expected_codes = {1, 2, 130}
    if receipt['exit_code'] not in expected_codes:
        issues.append(role + ': CLI exit does not agree with declared native outcome')
    xml = None
    if role != 'native':
        try:
            xml = parse_junit(invocation['junit_path'])
        except (OSError, ValueError, ET.ParseError) as error:
            reporting_finding(role, 'JUnit is unavailable or invalid: ' + repr(error), issues, observations)
        if xml is not None:
            for problem in xml['issues']:
                reporting_finding(role, problem, issues, observations)
        if xml is not None and native['status'] != 'interrupted':
            expected_items = (1 if role == 'atomic' else len(public['selected_groups'])) + (2 if invocation['mixed'] else 0)
            if xml['counts']['tests'] != expected_items:
                reporting_finding(role, 'JUnit item count is not actual pytest group/function count', issues, observations)
            if role == 'bridge':
                planned = {g['group_id']: g for g in public['planned_groups']}
                expected_names = [('native-suite[atomic]' if planned[g]['mode'] == 'atomic'
                                   else 'native-module[' + planned[g]['module_name'] + ']') for g in public['selected_groups']]
                actual_names = [x['name'] for x in xml['testcases'] if x['name'].startswith('native-')]
                if Counter(actual_names) != Counter(expected_names):
                    issues.append('Bridge JUnit names do not match selected module/atomic groups')
        elif xml is not None:
            identified_failures = [entry for entry in xml['testcases'] if entry['name'] and (entry['failure'] or entry['error'])]
            if not identified_failures:
                reporting_finding(role, 'Interrupted invocation has no identified nonpassing pytest item', issues, observations)
        log = (invocation['directory'] / 'process.log').read_text(errors='replace')
        for event in native['events']:
            if event['kind'] in FAILURES:
                if str(event['id']) not in log:
                    reporting_finding(role, 'CLI omitted native failing identity ' + str(event['id']), issues, observations)
                if event.get('exception_type') and event['exception_type'] not in log:
                    reporting_finding(role, 'CLI omitted native exception type ' + event['exception_type'], issues, observations)
    return issues, xml, observations


def assess(case, invocations):
    issues, observations, natives, publics, xmls, group_artifacts = [], [], {}, {}, {}, {}
    roots = [v['work'] for v in invocations.values()]
    traces, frontend_traces = {}, {}
    for role, item in invocations.items():
        native, public, findings, group_artifacts[role] = load_native(item)
        natives[role], publics[role] = native, public
        issues.extend(findings)
        more, xmls[role], reporting = check_invocation(item, native, public)
        issues.extend(more)
        observations.extend(reporting)
        traces[role], frontend_traces[role] = trace_parts(item['trace'], item['mixed'], roots)
    for role in ['atomic', 'bridge']:
        if role in natives:
            issues += [role + ': ' + issue for issue in compare_native(natives['native'], natives[role],
                       traces['native'], traces[role], roots)]
    if invocations['native']['mixed']:
        if frontend_traces['atomic'] != frontend_traces['bridge']:
            issues.append('Mixed frontend pytest trace/warning state differs from atomic subprocess baseline')
        if len(frontend_traces['atomic']) != 2:
            issues.append('Mixed frontend pytest population did not produce exactly two trace entries')
    bridge = publics['bridge']
    if xmls['bridge'] is not None:
        issues.extend(group_reporting_issues(bridge, natives['bridge'], group_artifacts['bridge'], xmls['bridge']))
    if case['module']:
        if len(bridge['selected_groups']) != 1 or not bridge['omitted_groups']:
            issues.append('Explicit module selection did not select one group and expose omissions')
        selected = {g['group_id']: g for g in bridge['planned_groups']}[bridge['selected_groups'][0]]
        if selected['module_name'] != case['module'] or selected['mode'] == 'atomic':
            issues.append('Explicit module selection selected the wrong or an atomic group')
    if case['key'] in {'R3', 'F28/main'}:
        failed_groups = [x['name'] for x in (xmls['bridge'] or {'testcases': []})['testcases'] if x['failure'] or x['error']]
        if len(set(failed_groups)) < 2 or not all(x.startswith('native-module[') for x in failed_groups):
            issues.append('Two native failure areas did not produce distinct module-level JUnit failures')
        atomic_failures = [x for x in (xmls['atomic'] or {'testcases': []})['testcases'] if x['failure'] or x['error']]
        if len(atomic_failures) != 1:
            issues.append('Atomic baseline did not retain its single failing pytest item')
    if case['key'] == 'R0':
        for role, data in natives.items():
            skips = sum(e['kind'] == 'skip' for e in data['events'])
            if data['tests_run'] != 1024 or skips != 5 or not data['successful']:
                issues.append(role + ': pristine real corpus lost the 1024/5-skip passing coverage gate')
    counts = {role: {'native_tests_run': data['tests_run'], 'native_status': data['status'],
                    'native_event_counts': dict(Counter(e['kind'] for e in data['events'])),
                    'junit': xmls[role]['counts'] if xmls[role] else None}
              for role, data in natives.items()}
    return {'issues': issues, 'baseline_reporting_observations': observations, 'counts': counts,
            'bridge_group_modes': dict(Counter(g['mode'] for g in bridge['planned_groups'])),
            'bridge_selected_groups': bridge['selected_groups'], 'bridge_omitted_groups': bridge['omitted_groups']}


def main():
    global TARGET, FRONTEND, CORPUS
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--target-python', type=Path, required=True, help='Target venv executable; no Pygments installed')
    parser.add_argument('--frontend-python', type=Path, required=True, help='Frontend venv executable with pytest')
    parser.add_argument('--corpus', type=Path, required=True, help='Untouched extracted Markdown 3.9 sdist')
    parser.add_argument('--cases', nargs='+', help='Diagnostic subset only; cannot satisfy the full gate')
    parser.add_argument('--preflight', action='store_true', help='Validate frozen inputs and seal sources without running any product')
    args = parser.parse_args()
    TARGET, FRONTEND, CORPUS = (p.absolute() for p in (args.target_python, args.frontend_python, args.corpus))
    for name, executable in [('target', TARGET), ('frontend', FRONTEND)]:
        if not executable.is_file() or not os.access(executable, os.X_OK):
            parser.error(name + ' Python is not an executable file')
        if not (executable.parent.parent / 'pyvenv.cfg').is_file():
            parser.error(name + ' Python must be inside a venv bin directory for bounded environment sealing')
    if not CORPUS.is_dir():
        parser.error('--corpus must be the extracted sdist directory')
    output_root = args.output.absolute().resolve()
    for source_root in [CORPUS, TARGET.parent.parent, FRONTEND.parent.parent, ROOT / 'benchmark/frozen-fixtures']:
        if output_root.is_relative_to(source_root.resolve()):
            parser.error('--output must be outside corpus, interpreter environments and frozen fixtures')
    validate_freeze()
    chosen = cases()
    if args.cases:
        unknown = set(args.cases) - {c['key'] for c in chosen}
        if unknown:
            raise ValueError('Unknown diagnostic case keys: ' + repr(unknown))
        chosen = [c for c in chosen if c['key'] in args.cases]
    output = args.output.absolute()
    output.mkdir(parents=True, exist_ok=False)
    product_sources = [p for p in ROOT.glob('*.py') if p.name.startswith('suitebridge')]
    if not product_sources:
        raise ValueError('Product sources are absent')
    paths = [Path(__file__).absolute(), ATOMIC, OBSERVER, ROOT / 'evidence/public-contract.md',
             ROOT / 'evidence/public-interruption-addendum.md',
             ROOT / 'benchmark/portable-source-freeze.json', ROOT / 'benchmark/corpus-manifest.json',
             ROOT / 'benchmark/frozen-fixtures/manifest.json', ROOT / 'benchmark/real-corpus-variants.json',
             *product_sources]
    seal = {p.relative_to(ROOT).as_posix(): sha(p) for p in paths}
    save(output / 'seal.json', seal)
    for relative, expected in seal.items():
        snapshot = output / 'source-snapshot' / relative
        snapshot.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / relative, snapshot)
        if sha(snapshot) != expected:
            raise ValueError('Source changed while creating immutable attempt snapshot: ' + relative)
    environments = {name: tree_manifest(path.parent.parent) for name, path in [('target', TARGET), ('frontend', FRONTEND)]}
    save(output / 'environment-manifests.json', environments)
    save(output / 'plan.json', {'evaluator_version': EVALUATOR_VERSION,
        'baseline_reporting_interpretation': 'evidence/public-interruption-addendum.md; native parity and required usefulness evidence remain blocking.',
        'case_keys': [c['key'] for c in chosen], 'full_scope': not bool(args.cases),
        'normalization': 'Only declared fresh worktree roots, native status complete/completed/empty_selection mapping, and extra group_id metadata.',
        'frontend_flags': STRICT, 'target': str(TARGET), 'frontend': str(FRONTEND),
        'watchdog': '45-second symmetric experimental hang watchdog, not a user/provider quota.',
        'cpu_accounting': 'Outer Linux waited-child process CPU includes waited descendants; no double addition of atomic target receipt.'})
    if args.preflight:
        print(json.dumps({'preflight': 'pass', 'case_count': len(chosen), 'product_executed': False}))
        return
    records = []
    start_wall = time.perf_counter()
    start_self = resource.getrusage(resource.RUSAGE_SELF)
    try:
        for index, case in enumerate(chosen):
            row = {'case': case['key'], 'module': case['module'], 'roles': {}, 'issues': []}
            roles = ['native', 'atomic', 'bridge'] if case['module'] is None else ['native', 'bridge']
            # Reverse comparator order on alternating cases; no timing threshold is claimed.
            if index % 2:
                roles.reverse()
            invocations = {}
            for role in roles:
                invocation = execute(case, role, output / 'cases' / case['key'] / role)
                invocations[role] = invocation
                row['roles'][role] = invocation['receipt']
            try:
                row.update(assess(case, invocations))
            except Exception as error:
                row['issues'].append('Comparison incomplete: ' + repr(error))
            row['pass'] = not row['issues']
            records.append(row)
            save(output / 'records.json', records)
            print(json.dumps({'case': row['case'], 'pass': row['pass'], 'issues': row['issues']}), flush=True)
        changed = [path for path, expected in seal.items() if sha(ROOT / path) != expected]
        validate_freeze()
        environment_changes = [name for name, path in [('target', TARGET), ('frontend', FRONTEND)]
                               if tree_manifest(path.parent.parent) != environments[name]]
        finish_self = resource.getrusage(resource.RUSAGE_SELF)
        summary = {'complete_scope': not bool(args.cases) and len(records) == 40,
                   'evaluator_version': EVALUATOR_VERSION,
                   'cases_run': len(records), 'case_failures': [r['case'] for r in records if r['issues']],
                   'baseline_reporting_observations': [{'case': r['case'], 'observations': r['baseline_reporting_observations']}
                                                       for r in records if r.get('baseline_reporting_observations')],
                   'changed_sources': changed, 'changed_environments': environment_changes,
                   'process_cpu_seconds': sum(v['cpu_seconds'] for r in records for v in r['roles'].values()),
                   'controller_cpu_seconds': finish_self.ru_utime + finish_self.ru_stime - start_self.ru_utime - start_self.ru_stime,
                   'wall_seconds': time.perf_counter() - start_wall,
                   'no_speed_claim': True, 'transport_scope': 'F29-F34 have an independent owner and are not covered by this summary.'}
        summary['integration_pass'] = summary['complete_scope'] and not summary['case_failures'] and not changed and not environment_changes
        save(output / 'summary.json', summary)
        print(json.dumps(summary, indent=2), flush=True)
    except BaseException as error:
        save(output / 'attempt-error.json', {'error': repr(error), 'cases_completed': len(records),
             'elapsed_wall_seconds': time.perf_counter() - start_wall})
        raise


if __name__ == '__main__':
    main()

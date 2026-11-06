"""Integration checks for the immutable F29-F34 transport fixtures.

Run only after the product owners declare a sealed integrated candidate ready.
Every invocation uses a new evidence directory; failed runs are never overwritten.
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
import os
from pathlib import Path
import resource
import signal
import subprocess
import sys
import time
import xml.etree.ElementTree as ET

import transport_fixtures as fixtures

ROOT = Path(__file__).resolve().parents[1]
FRONTEND = None
TARGET = None
OBSERVER = ROOT / 'benchmark/native_observer.py'
FROZEN_SOURCE = '4fdbd8008d10d0b1aae180d345f8417583cb3ffed3a98f5d8b942bc61bdbbd4c'
FROZEN_MANIFEST = '5741c8f3fc6c581247c9c03baa6b3727fcd908def17807a3a7b35cadacf80008'
STRICT = ['--assert=plain', '--capture=no', '-p', 'no:warnings', '-p', 'no:cacheprovider']
COMPLETE = {'complete', 'completed'}


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, payload):
    Path(path).write_text(json.dumps(payload, sort_keys=True, indent=2) + '\n')


def json_file(path):
    path = Path(path)
    return json.loads(path.read_text()) if path.exists() else None


def json_lines(path):
    path = Path(path)
    return [json.loads(line) for line in path.read_text().splitlines()] if path.exists() else []


def tree_manifest(root):
    root = Path(root)
    result = {}
    for path in sorted(root.rglob('*')):
        if '__pycache__' in path.parts:
            continue
        if path.is_symlink():
            result[str(path.relative_to(root))] = {'symlink': os.readlink(path)}
        elif path.is_file():
            result[str(path.relative_to(root))] = {'sha256': digest(path), 'bytes': path.stat().st_size}
    return result


def identity(pid):
    try:
        fields = Path(f'/proc/{pid}/stat').read_text().rsplit(')', 1)[1].split()
        return {'pid': int(pid), 'state': fields[0], 'parent': int(fields[1]),
                'process_group': int(fields[2]), 'start_time': fields[19]}
    except (FileNotFoundError, ProcessLookupError):
        return None


def same_identity(record):
    current = identity(record['pid'])
    return current if current and current['start_time'] == record['start_time'] else None


def descendants(pid):
    result = []
    try:
        children = Path(f'/proc/{pid}/task/{pid}/children').read_text().split()
    except FileNotFoundError:
        return result
    for child in children:
        record = identity(int(child))
        if record:
            result.append(record)
            result.extend(descendants(record['pid']))
    return result


def live(record):
    current = same_identity(record)
    return bool(current and current['state'] not in {'Z', 'X'})


def emergency_cleanup(records):
    """Terminate only groups whose leader and a current member are owned records."""
    owned = {entry['pid']: entry for entry in records}
    killed = []
    groups = {entry['process_group'] for entry in records if live(entry)}
    for group in groups:
        if group not in owned:
            continue
        anchors = [entry for entry in records if entry['process_group'] == group and live(entry)]
        if not anchors:
            continue
        try:
            os.killpg(group, signal.SIGKILL)
            killed.append(group)
        except ProcessLookupError:
            pass
    return killed


def run_process(command, cwd, environment, folder, cancel_trace=None):
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=False)
    before = resource.getrusage(resource.RUSAGE_CHILDREN)
    controller_before = time.process_time()
    started = time.monotonic()
    seen = {}
    receipt = {'command': [str(value) for value in command], 'cwd': str(cwd),
               'started_utc': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
               'watchdog_seconds': 45, 'cancel_sent': False, 'timed_out': False,
               'forced_cleanup': False}
    readiness = None
    cancel_at = None
    stdout_path, stderr_path = folder / 'stdout.bin', folder / 'stderr.bin'
    with stdout_path.open('wb') as stdout, stderr_path.open('wb') as stderr:
        process = subprocess.Popen(receipt['command'], cwd=cwd, env=environment,
                                   stdout=stdout, stderr=stderr, start_new_session=True)
        own = identity(process.pid)
        if own:
            seen[(own['pid'], own['start_time'])] = own
        receipt['pid'] = process.pid
        while process.poll() is None:
            for record in descendants(process.pid):
                seen[(record['pid'], record['start_time'])] = record
            now = time.monotonic()
            if cancel_trace is not None and cancel_at is None:
                try:
                    entries = json_lines(cancel_trace)
                except (json.JSONDecodeError, OSError):
                    entries = []
                readiness = next((entry for entry in entries if entry.get('event') == 'F32:body:entered'), None)
                if readiness is not None:
                    for name in ['worker', 'descendant']:
                        record = readiness[name]
                        seen[(record['pid'], record['start_time'])] = record
                    os.kill(process.pid, signal.SIGINT)
                    cancel_at = now
                    receipt['cancel_sent'] = True
                    receipt['readiness'] = readiness
                elif now - started >= 30:
                    receipt['readiness_timeout'] = True
                    break
            if cancel_at is not None and now - cancel_at >= 5:
                receipt['cancellation_deadline_exceeded'] = True
                break
            if now - started >= 45:
                receipt['timed_out'] = True
                break
            time.sleep(0.05)
        if process.poll() is None:
            receipt['forced_cleanup'] = True
            receipt['emergency_groups'] = emergency_cleanup(list(seen.values()))
            process.kill()
        receipt['exit_code'] = process.wait()
    if readiness is not None:
        end = cancel_at + 5
        while time.monotonic() < end and (same_identity(readiness['worker']) is not None or live(readiness['descendant'])):
            time.sleep(0.05)
        receipt['worker_reaped_by_frontend'] = same_identity(readiness['worker']) is None
        receipt['descendant_not_live'] = not live(readiness['descendant'])
        receipt['cancellation_cleanup_seconds'] = time.monotonic() - cancel_at
    remaining = [entry for entry in seen.values() if entry['pid'] != receipt['pid'] and live(entry)]
    receipt['live_owned_descendants_before_emergency_cleanup'] = remaining
    if remaining:
        receipt['forced_cleanup'] = True
        receipt['emergency_groups'] = emergency_cleanup(list(seen.values()))
        time.sleep(0.05)
    after = resource.getrusage(resource.RUSAGE_CHILDREN)
    receipt.update(cpu_seconds=after.ru_utime + after.ru_stime - before.ru_utime - before.ru_stime,
                   controller_cpu_seconds=time.process_time() - controller_before,
                   wall_seconds=time.monotonic() - started,
                   observed_owned_processes=list(seen.values()),
                   stdout_sha256=digest(stdout_path), stderr_sha256=digest(stderr_path),
                   stdout_bytes=stdout_path.stat().st_size, stderr_bytes=stderr_path.stat().st_size)
    write(folder / 'receipt.json', receipt)
    return receipt


def base_environment(project, trace, config=None, frontend=False):
    environment = dict(os.environ)
    environment.update(PYTHONDONTWRITEBYTECODE='1', PYTHONHASHSEED='0', PYGMENTS_VERSION='',
                       PYTEST_DISABLE_PLUGIN_AUTOLOAD='1', PYTEST_ADDOPTS='', PYTEST_PLUGINS='',
                       SUITEBRIDGE_FIXTURE_TRACE=str(trace))
    environment.pop('PYTEST_CURRENT_TEST', None)
    environment.pop('PYTHONHOME', None)
    environment['PYTHONPATH'] = os.pathsep.join([str(ROOT), str(project)]) if frontend else str(project)
    if config:
        environment.update(config.get('environment', {}))
    return environment


def materialize(case_id, variant, directory):
    config = fixtures.materialize(case_id, directory, variant)
    project = Path(config['root'])
    write(project.parent / (project.name + '-configuration.json'), config)
    write(project.parent / (project.name + '-source-manifest.json'), tree_manifest(project))
    return config


def sources_unchanged(project):
    project = Path(project)
    before = json_file(project.parent / (project.name + '-source-manifest.json'))
    after = tree_manifest(project)
    write(project.parent / (project.name + '-source-manifest-after.json'), after)
    return before == after


def native_reference(case_id, variant, case_dir):
    config = materialize(case_id, variant, case_dir / 'reference-project')
    project = Path(config['root'])
    trace = case_dir / 'reference-trace.jsonl'
    output = case_dir / 'reference-native.json'
    target = config.get('target_python', str(TARGET))
    command = [target, str(OBSERVER), '--root', str(project), '--output', str(output)]
    receipt = run_process(command, project, base_environment(project, trace, config), case_dir / 'reference-process')
    report = json_file(output)
    events = report['events'] if report else json_lines(output.with_suffix('.events.jsonl'))
    return {'receipt': receipt, 'report': report, 'events': events, 'trace': json_lines(trace),
            'project': str(project), 'stdout': str(case_dir / 'reference-process/stdout.bin'),
            'stderr': str(case_dir / 'reference-process/stderr.bin')}


def pytest_command(config, report, junit):
    project = Path(config['root'])
    target = config.get('target_python', str(TARGET))
    native_root = config.get('native_root', str(project))
    command = [str(FRONTEND), '-m', 'pytest', *STRICT, '-p', 'suitebridge',
               '--native-unittest', 'tests', '--native-python', target,
               '--native-root', native_root, '--native-report', str(report),
               '--native-timeout', '45', 'tests']
    if (project / 'frontend_cases').exists():
        command.append('frontend_cases')
    command.extend(['--junitxml', str(junit)])
    return command


def junit_summary(path):
    if not path.exists():
        return None
    document = ET.parse(path).getroot()
    suites = [document] if document.tag == 'testsuite' else document.findall('testsuite')
    cases = []
    for suite in suites:
        for case in suite.findall('testcase'):
            cases.append({**case.attrib, 'failures': len(case.findall('failure')),
                          'errors': len(case.findall('error')), 'skipped': len(case.findall('skipped'))})
    totals = {name: sum(int(suite.get(name, '0')) for suite in suites)
              for name in ['tests', 'failures', 'errors', 'skipped']}
    actual = {'tests': len(cases), **{name: sum(case[name] for case in cases)
                                    for name in ['failures', 'errors', 'skipped']}}
    return {'declared': totals, 'actual': actual, 'counts_consistent': totals == actual, 'cases': cases}


def bridge_run(case_id, variant, case_dir):
    config = materialize(case_id, variant, case_dir / 'bridge-project')
    project = Path(config['root'])
    trace = case_dir / 'bridge-trace.jsonl'
    output_dir = case_dir / 'bridge-output'
    report_path, junit = output_dir / 'native.json', output_dir / 'pytest.xml'
    command = pytest_command(config, report_path, junit)
    receipt = run_process(command, project, base_environment(project, trace, config, frontend=True),
                          case_dir / 'bridge-process', cancel_trace=trace if case_id == 'F32' else None)
    report = json_file(report_path)
    summary = junit_summary(junit)
    write(case_dir / 'junit-summary.json', summary)
    diagnostics = (case_dir / 'bridge-process/stdout.bin').read_bytes() + (case_dir / 'bridge-process/stderr.bin').read_bytes()
    return {'receipt': receipt, 'report': report, 'trace': json_lines(trace), 'junit': summary,
            'config': config, 'output_dir': str(output_dir), 'diagnostics': diagnostics.decode('utf-8', 'replace')}


def normalized_events(events):
    keys = ['sequence', 'kind', 'id', 'parent_id', 'occurrence', 'exception_type', 'message', 'reason']
    return [{key: event[key] for key in keys if key in event} for event in events]


def event_sequences_valid(events):
    return [event.get('sequence') for event in events] == list(range(len(events)))


def payload_custody(output_dir, stream, payload):
    worker = Path(output_dir) / 'worker'
    paths = sorted(worker.rglob(f'*.{stream}.bin'))
    matches = [{'path': str(path), 'bytes': path.stat().st_size, 'sha256': digest(path),
                'payload_occurrences': path.read_bytes().count(payload)} for path in paths]
    return {'artifacts': matches, 'payload_occurrences': sum(item['payload_occurrences'] for item in matches)}


def acknowledged_artifacts(bridge):
    report = bridge['report'] or {}
    root = Path(bridge['output_dir'])
    references = [('final', report.get('native_artifact'), report.get('native_artifact_sha256'), None)]
    references.extend(('group', item.get('artifact'), item.get('sha256'), item)
                      for item in report.get('group_results', []))
    observations = []
    for kind, relative, expected, metadata in references:
        item = {'kind': kind, 'artifact': relative, 'valid': False}
        if not isinstance(relative, str) or not relative or Path(relative).is_absolute() or '..' in Path(relative).parts:
            observations.append(item)
            continue
        path = root / relative
        parts = [root.joinpath(*Path(relative).parts[:count]) for count in range(1, len(Path(relative).parts) + 1)]
        if any(part.is_symlink() for part in parts) or not path.is_file() or not path.resolve().is_relative_to(root.resolve()):
            observations.append(item)
            continue
        data = json_file(path)
        item['hash_matches'] = digest(path) == expected
        item['identity_matches'] = data.get('schema_version') == 1 and data.get('invocation_id') == report.get('invocation_id')
        if kind == 'final':
            item['content_matches'] = all(data.get(key) == report.get(key) for key in
                                          ['events', 'tests_run', 'counts', 'target_environment', 'selected_groups', 'executed_groups', 'status'])
            item['success_matches'] = data.get('successful') == report.get('native_successful')
        else:
            item['content_matches'] = data.get('group_id') == metadata.get('group_id') and data.get('status') == metadata.get('status')
            public = {event['sequence']: event for event in report.get('events', [])}
            item['events_match'] = all(public.get(event['sequence']) == event for event in data.get('events', []))
            item['count_matches'] = data.get('tests_run') == sum(event.get('kind') == 'start' for event in data.get('events', []))
        item['valid'] = all(value for key, value in item.items() if key.endswith('_matches') or key == 'events_match')
        observations.append(item)
    return {'passed': bool(report.get('group_results')) and all(item['valid'] for item in observations),
            'references': observations}


def completed_success(bridge):
    report = bridge['report'] or {}
    return bridge['receipt']['exit_code'] == 0 and report.get('status') in COMPLETE and report.get('successful') is True


def incomplete_report(bridge):
    report = bridge['report']
    return bool(report is not None and report.get('status') not in COMPLETE and
                report.get('successful') is not True and bridge['receipt']['exit_code'] != 0)


def no_successful_final_artifact(output_dir):
    for path in Path(output_dir).rglob('*.json'):
        if path.name not in {'native.json', 'native-final.json'}:
            continue
        value = json_file(path)
        if isinstance(value, dict) and value.get('status') in COMPLETE and value.get('successful') is True:
            return False
    return True


def protocol_case(variant, case_dir):
    config = materialize('F31', variant, case_dir / 'worker-project')
    project = Path(config['root'])
    artifact_dir = case_dir / 'worker-artifacts'
    artifact_dir.mkdir()
    trace = case_dir / 'worker-trace.jsonl'
    command = [str(TARGET), str(ROOT / 'suitebridge_worker.py'), '--root', str(project),
               '--tests', 'tests', '--output-dir', str(artifact_dir)]
    before = resource.getrusage(resource.RUSAGE_CHILDREN)
    started = time.monotonic()
    receipt = fixtures.run_protocol_fault(command, case_dir / 'protocol-driver', trace, variant,
                                          base_environment(project, trace, config), project)
    after = resource.getrusage(resource.RUSAGE_CHILDREN)
    receipt['cpu_seconds'] = after.ru_utime + after.ru_stime - before.ru_utime - before.ru_stime
    receipt['wall_seconds'] = time.monotonic() - started
    artifact_checks = []
    for response in receipt.get('received', []):
        if 'artifact' not in response:
            continue
        path = artifact_dir / response['artifact']
        safe = path.resolve().is_relative_to(artifact_dir.resolve())
        artifact_checks.append({'artifact': response['artifact'], 'within_output_directory': safe,
                                'sha256_matches': safe and path.is_file() and digest(path) == response.get('sha256')})
    checks = {'frozen_protocol_fault_check': receipt['passed'],
              'fixture_sources_unchanged': sources_unchanged(project),
              'acknowledged_artifacts_valid': all(item['within_output_directory'] and item['sha256_matches'] for item in artifact_checks)}
    write(case_dir / 'protocol-observation.json', {'receipt': receipt, 'artifact_checks': artifact_checks})
    return checks, {'protocol_receipt': 'protocol-observation.json'}


def run_case(case_id, variant, case_dir):
    case_dir.mkdir()
    if case_id == 'F31':
        return protocol_case(variant, case_dir)
    reference = None
    if case_id in {'F29', 'F33'} or (case_id == 'F30' and variant == 'abrupt_exit'):
        reference = native_reference(case_id, variant, case_dir)
    bridge = bridge_run(case_id, variant, case_dir)
    report = bridge['report'] or {}
    events = report.get('events', [])
    checks = {'no_watchdog_or_emergency_cleanup': not bridge['receipt']['timed_out'] and not bridge['receipt']['forced_cleanup'],
              'bridge_fixture_sources_unchanged': sources_unchanged(bridge['config']['root']),
              'native_event_sequence_valid': event_sequences_valid(events),
              'junit_counts_consistent_if_written': bridge['junit'] is None or bridge['junit']['counts_consistent']}
    if reference:
        checks['reference_fixture_sources_unchanged'] = sources_unchanged(reference['project'])
    detail = {'bridge_exit_code': bridge['receipt']['exit_code'], 'bridge_status': report.get('status'),
              'bridge_trace': bridge['trace']}
    if case_id in {'F29', 'F33'}:
        custody = acknowledged_artifacts(bridge)
        checks['acknowledged_artifacts_valid'] = custody['passed']
        detail['artifact_custody'] = custody
    if case_id == 'F29':
        expected_trace = ['F29:body:start', 'F29:body:end']
        stdout = payload_custody(bridge['output_dir'], 'stdout', fixtures.F29_STDOUT)
        stderr = payload_custody(bridge['output_dir'], 'stderr', fixtures.F29_STDERR)
        detail.update(stdout_custody=stdout, stderr_custody=stderr)
        checks.update(native_reference_passed=reference['receipt']['exit_code'] == 0,
                      bridge_completed_successfully=completed_success(bridge),
                      reference_trace_exact=[event['event'] for event in reference['trace']] == expected_trace,
                      bridge_trace_exact=[event['event'] for event in bridge['trace']] == expected_trace,
                      reference_stdout_exact=Path(reference['stdout']).read_bytes().count(fixtures.F29_STDOUT) == 1,
                      reference_stderr_exact=Path(reference['stderr']).read_bytes().count(fixtures.F29_STDERR) == 1,
                      bridge_stdout_exact=stdout['payload_occurrences'] == 1,
                      bridge_stderr_exact=stderr['payload_occurrences'] == 1,
                      native_events_exact=normalized_events(reference['events']) == normalized_events(events),
                      one_native_occurrence=report.get('tests_run') == 1,
                      one_pytest_group=bridge['junit'] is not None and bridge['junit']['actual']['tests'] == 1)
    elif case_id == 'F30':
        checks.update(incomplete_native_artifact=incomplete_report(bridge),
                      no_successful_final_artifact=no_successful_final_artifact(bridge['output_dir']))
        if variant == 'abrupt_exit':
            expected = ['F30:body:entered']
            checks.update(native_exit_23=reference['receipt']['exit_code'] == 23,
                          reference_trace_exact=[event['event'] for event in reference['trace']] == expected,
                          bridge_trace_exact=[event['event'] for event in bridge['trace']] == expected,
                          acknowledged_events_exact=normalized_events(reference['events']) == normalized_events(events),
                          no_completed_group=not report.get('executed_groups'),
                          remaining_group_visible=any(group.get('module_name') == 'test_zz_remaining' and
                                                      group.get('group_id') in report.get('uncompleted_selected_groups', [])
                                                      for group in report.get('planned_groups', [])))
        else:
            checks.update(no_native_events=events == [], no_native_bodies=bridge['trace'] == [],
                          partial_frame_diagnostic=any(word in bridge['diagnostics'].lower() for word in ['frame', 'eof', 'closed']))
    elif case_id == 'F32':
        checks.update(cancel_sent_after_readiness=bridge['receipt']['cancel_sent'],
                      worker_reaped_by_frontend=bridge['receipt'].get('worker_reaped_by_frontend', False),
                      descendant_not_live=bridge['receipt'].get('descendant_not_live', False),
                      incomplete_native_artifact=incomplete_report(bridge),
                      no_successful_final_artifact=no_successful_final_artifact(bridge['output_dir']),
                      one_native_start_prefix=sum(event.get('kind') == 'start' for event in events) == 1,
                      no_invented_native_outcomes=not any(event.get('kind') in
                          {'stop', 'success', 'failure', 'error', 'skip', 'expected_failure', 'unexpected_success'} for event in events),
                      no_completed_group=not report.get('executed_groups'),
                      one_entered_body=[event['event'] for event in bridge['trace']] == ['F32:body:entered'])
        if bridge['junit']:
            checks['interrupted_group_not_reported_as_pass'] = all(
                case['failures'] or case['errors'] or case['skipped'] for case in bridge['junit']['cases'])
    elif case_id == 'F33':
        expected = Counter(['F33:native:verified', 'F33:frontend:verified'])
        environment = report.get('target_environment', {})
        checks.update(native_reference_passed=reference['receipt']['exit_code'] == 0,
                      bridge_completed_successfully=completed_success(bridge),
                      native_events_exact=normalized_events(reference['events']) == normalized_events(events),
                      both_populations_once=Counter(item['event'] for item in bridge['trace']) == expected,
                      reference_one_native=Counter(item['event'] for item in reference['trace']) == Counter(['F33:native:verified']),
                      two_pytest_items=bridge['junit'] is not None and bridge['junit']['actual']['tests'] == 2,
                      one_native_occurrence=report.get('tests_run') == 1,
                      no_pygments_in_target=environment.get('pygments_present') is False,
                      executable_path_exact=environment.get('executable') == bridge['config']['target_python'])
    else:
        invalid_path = bridge['config'].get('native_root', bridge['config'].get('target_python'))
        checks.update(nonzero_configuration_status=bridge['receipt']['exit_code'] != 0,
                      no_native_body=bridge['trace'] == [], no_native_events=events == [],
                      concrete_invalid_path_diagnostic=str(invalid_path) in bridge['diagnostics'],
                      no_successful_final_artifact=no_successful_final_artifact(bridge['output_dir']))
    write(case_dir / 'bridge-observation.json', {key: value for key, value in bridge.items() if key != 'diagnostics'})
    if reference:
        write(case_dir / 'reference-observation.json', reference)
    return checks, detail


def main():
    global FRONTEND, TARGET
    parser = argparse.ArgumentParser()
    parser.add_argument('--target-python', required=True)
    parser.add_argument('--frontend-python', required=True)
    parser.add_argument('--output', required=True, help='New output directory; must not already exist.')
    parser.add_argument('--case', action='append', help='Explicit targeted rerun only; default is every frozen variant.')
    args = parser.parse_args()
    if sys.platform != 'linux' or sys.version_info[:2] != (3, 14):
        parser.error('These frozen transport checks require Linux and Python 3.14.')
    FRONTEND = Path(args.frontend_python).absolute()
    TARGET = Path(args.target_python).absolute()
    for name, executable in [('frontend', FRONTEND), ('target', TARGET)]:
        cfg = executable.parent.parent / 'pyvenv.cfg'
        if executable.parent.name != 'bin' or not executable.is_file() or not cfg.is_file():
            parser.error(name + ' must name an existing venv bin/python with pyvenv.cfg')
        values = dict(line.split(' = ', 1) for line in cfg.read_text().splitlines() if ' = ' in line)
        if not values.get('version', '').startswith('3.14.'):
            parser.error(name + ' venv must use Python 3.14')
    if TARGET.is_symlink():
        parser.error('The frozen target baseline requires a venv created with --copies; the second F33 variant creates its own symlink alias.')
    fixtures.configure(TARGET, FRONTEND)
    manifest_path = ROOT / 'benchmark/transport-fixtures-manifest.json'
    if digest(manifest_path) != FROZEN_MANIFEST:
        raise RuntimeError('Frozen transport manifest changed')
    frozen = json_file(manifest_path)
    actual = fixtures.manifest()
    if actual['cases'] != frozen['cases'] or actual['wire'] != frozen['wire']:
        raise RuntimeError('Frozen literal fixture sources or expected behavior changed')
    product_files = [ROOT / name for name in ['suitebridge.py', 'suitebridge_worker.py', 'suitebridge_protocol.py']]
    pins = {path.name: digest(path) for path in product_files}
    all_cases = [(case_id, variant) for case_id, case in fixtures.CASES.items() for variant in case['variants']]
    requested = set(args.case or [])
    if requested - {case_id + '/' + variant for case_id, variant in all_cases}:
        raise ValueError('Unknown frozen case selector')
    cases = [(case_id, variant) for case_id, variant in all_cases if not requested or case_id + '/' + variant in requested]
    output = Path(args.output).absolute()
    output.mkdir(parents=True, exist_ok=False)
    candidate = output / 'candidate-sources'
    candidate.mkdir()
    for path in product_files + [Path(__file__)]:
        (candidate / path.name).write_bytes(path.read_bytes())
    environments = {name: tree_manifest(path) for name, path in
                    [('frontend', FRONTEND.parent.parent), ('target', TARGET.parent.parent)]}
    write(output / 'environment-manifests-before.json', environments)
    batch_before = resource.getrusage(resource.RUSAGE_CHILDREN)
    batch_cpu = time.process_time()
    batch_started = time.monotonic()
    write(output / 'input-pins.json', {'product': pins, 'transport_source': digest(ROOT / 'benchmark/transport_fixtures.py'),
                                      'original_frozen_fixture_source': FROZEN_SOURCE,
                                      'transport_manifest': FROZEN_MANIFEST, 'harness': digest(__file__),
                                      'native_observer': digest(OBSERVER),
                                      'contract': digest(ROOT / 'evidence/public-contract.md'),
                                      'frontend_python': str(FRONTEND), 'target_python': str(TARGET),
                                      'frontend_python_sha256': digest(FRONTEND), 'target_python_sha256': digest(TARGET),
                                      'requested_cases': cases, 'selection_kind': 'targeted_recheck' if requested else 'all_frozen_variants'})
    records = []
    for case_id, variant in cases:
        if any(digest(path) != pins[path.name] for path in product_files):
            write(output / 'stopped.json', {'reason': 'Product changed during the batch', 'completed': records})
            raise RuntimeError('Product source changed during the batch; retained results, no automatic retry')
        directory = output / (case_id + '-' + variant)
        try:
            checks, detail = run_case(case_id, variant, directory)
            record = {'case': case_id, 'variant': variant, 'checks': checks,
                      'passed': all(checks.values()), 'detail': detail}
        except Exception as error:
            record = {'case': case_id, 'variant': variant, 'passed': False,
                      'harness_error': type(error).__name__ + ': ' + str(error)}
        write(output / (case_id + '-' + variant + '-result.json'), record)
        records.append(record)
        write(output / 'summary.json', {'results': records, 'all_requested_cases_completed': len(records) == len(cases),
                                       'source_and_environment_checks_pending': True, 'passed': False,
                                       'provisional_case_checks_passed': all(row['passed'] for row in records)})
        print(json.dumps({'case': case_id, 'variant': variant, 'passed': record['passed'],
                          'failed_checks': [name for name, passed in record.get('checks', {}).items() if not passed],
                          'harness_error': record.get('harness_error')}), flush=True)
    unchanged = all(digest(path) == pins[path.name] for path in product_files)
    environments_after = {name: tree_manifest(path) for name, path in
                          [('frontend', FRONTEND.parent.parent), ('target', TARGET.parent.parent)]}
    write(output / 'environment-manifests-after.json', environments_after)
    environment_unchanged = environments == environments_after
    write(output / 'source-stability.json', {'unchanged_after_batch': unchanged,
                                             'existing_environments_unchanged': environment_unchanged})
    batch_after = resource.getrusage(resource.RUSAGE_CHILDREN)
    write(output / 'costs.json', {'wall_seconds': time.monotonic() - batch_started,
                                'controller_cpu_seconds': time.process_time() - batch_cpu,
                                'waited_descendant_cpu_seconds': batch_after.ru_utime + batch_after.ru_stime -
                                batch_before.ru_utime - batch_before.ru_stime,
                                'note': 'Waited-child CPU includes native workers reaped by pytest; orphan descendants may not be included.'})
    passed = unchanged and environment_unchanged and all(record['passed'] for record in records)
    write(output / 'summary.json', {'results': records, 'all_requested_cases_completed': len(records) == len(cases),
                                   'all_frozen_variants_requested': len(cases) == len(all_cases),
                                   'product_sources_unchanged': unchanged,
                                   'existing_environments_unchanged': environment_unchanged, 'passed': passed})
    return 0 if passed else 1


if __name__ == '__main__':
    raise SystemExit(main())

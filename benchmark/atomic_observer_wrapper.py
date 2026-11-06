"""One pytest item delegates the complete native suite to the independent oracle.

This is the coarse baseline. It contains no product imports or grouping logic.
"""
import hashlib
import json
import os
from pathlib import Path
import resource
import subprocess
import time

import pytest


def test_atomic_native_suite(request):
    root = Path(os.environ['INTEGRATION_NATIVE_ROOT']).absolute()
    output = Path(os.environ['INTEGRATION_NATIVE_OUTPUT']).absolute()
    target = os.environ['INTEGRATION_NATIVE_PYTHON']
    observer = Path(__file__).with_name('native_observer.py')
    output.parent.mkdir(parents=True, exist_ok=True)
    if output.exists():
        raise FileExistsError('Refusing to overwrite native baseline artifact')
    env = dict(os.environ)
    for key in list(env):
        if key.startswith(('PYTEST_', 'INTEGRATION_')) or key in {'PYTHONPATH', 'PYTHONHOME', 'PYGMENTS_VERSION'}:
            env.pop(key)
    command = [target, str(observer), '--root', str(root), '--tests', 'tests', '--output', str(output)]
    before = resource.getrusage(resource.RUSAGE_CHILDREN)
    start = time.perf_counter()
    stdout_path = output.parent / 'target.stdout'
    stderr_path = output.parent / 'target.stderr'
    with stdout_path.open('xb') as stdout, stderr_path.open('xb') as stderr:
        child = subprocess.Popen(command, cwd=root, env=env, stdout=stdout, stderr=stderr)
        try:
            code = child.wait()
        except BaseException:
            child.kill()
            child.wait()
            raise
    after = resource.getrusage(resource.RUSAGE_CHILDREN)
    receipt = {'command': command, 'exit_code': code,
               'wall_seconds': time.perf_counter() - start,
               'cpu_seconds': after.ru_utime + after.ru_stime - before.ru_utime - before.ru_stime,
               'cpu_accounting': 'Diagnostic child cost only; included in outer Linux waited-child CPU total.'}
    (output.parent / 'target-receipt.json').write_text(json.dumps(receipt, indent=2) + '\n')
    if not output.is_file():
        pytest.fail('Native observer did not produce its required artifact', pytrace=False)
    payload = json.loads(output.read_text())
    request.node.user_properties.extend([
        ('native_report', str(output)),
        ('native_report_sha256', hashlib.sha256(output.read_bytes()).hexdigest()),
        ('native_tests_started', payload['tests_run']),
    ])
    if payload['status'] == 'interrupted':
        raise KeyboardInterrupt('Native observer interrupted; retained artifact: ' + str(output))
    if payload['status'] != 'complete' or code not in (0, 1):
        pytest.fail('Native observer incomplete: ' + str(payload.get('fatal_error', payload['status'])), pytrace=False)
    expected = 0 if payload['successful'] else 1
    if code != expected:
        pytest.fail('Native observer exit disagrees with its artifact', pytrace=False)
    failures = [e for e in payload['events'] if e['kind'] in
                {'failure', 'error', 'subtest_failure', 'subtest_error', 'unexpected_success'}]
    if failures or not payload['successful']:
        details = '\n'.join(f"{e['id']}: {e.get('exception_type', e['kind'])}: {e.get('message', '')}"
                            for e in failures)
        pytest.fail('Native suite failed:\n' + details + '\nNative report: ' + str(output), pytrace=False)
    if not any(e['kind'] == 'success' for e in payload['events']):
        pytest.skip('Native suite has no successful native tests; inspect native report for skips/expected failures/empty inventory')

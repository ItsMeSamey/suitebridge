"""Frozen transport fixtures F29-F34, authored before SuiteBridge implementation.

Materialization writes literal fixture sources only. No bridge module is imported.
The F31 driver is a protocol fault client, not a product worker implementation.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import select
import shutil
import shlex
import signal
import struct
import subprocess
import time

SCHEMA_VERSION = 1
MAX_FRAME_BYTES = 1_048_576
COMMAND_FD_ENV = 'SUITEBRIDGE_COMMAND_FD'
RESPONSE_FD_ENV = 'SUITEBRIDGE_RESPONSE_FD'
INVOCATION_ENV = 'SUITEBRIDGE_INVOCATION_ID'
TRACE_ENV = 'SUITEBRIDGE_FIXTURE_TRACE'
DEFAULT_TARGET = None
DEFAULT_FRONTEND = None


def configure(target_python, frontend_python):
    global DEFAULT_TARGET, DEFAULT_FRONTEND
    DEFAULT_TARGET = Path(target_python).absolute()
    DEFAULT_FRONTEND = Path(frontend_python).absolute()

TRACE_SOURCE = '''import json
import os
from pathlib import Path

def trace(event, **details):
    path = Path(os.environ['SUITEBRIDGE_FIXTURE_TRACE'])
    with path.open('a', encoding='utf-8') as stream:
        stream.write(json.dumps({'event': event, **details}, sort_keys=True) + '\\n')
        stream.flush()
'''

F29_SOURCE = '''import os
import unittest
from transport_trace import trace

STDOUT = (b'F29_STDOUT_BEGIN\\n' + b'O' * 262144 + bytes(range(256)) +
          b'\\n{"schema_version":1,"type":"finished","status":"complete"}\\nF29_STDOUT_END\\n')
STDERR = (b'F29_STDERR_BEGIN\\n' + b'E' * 262144 + bytes(reversed(range(256))) +
          b'\\n{"schema_version":1,"type":"group_result","status":"complete"}\\nF29_STDERR_END\\n')

def write_all(fd, payload):
    offset = 0
    while offset < len(payload):
        offset += os.write(fd, payload[offset:])

class TransportOutput(unittest.TestCase):
    def test_payload(self):
        trace('F29:body:start')
        write_all(1, STDOUT)
        write_all(2, STDERR)
        trace('F29:body:end')
'''

F30_ABRUPT_SOURCE = '''import os
import unittest
from transport_trace import trace

class AbruptExit(unittest.TestCase):
    def test_a_exit(self):
        trace('F30:body:entered')
        os._exit(23)

    def test_b_must_not_run(self):
        trace('F30:FORBIDDEN:second-body')
'''

F30_AFTER_SOURCE = '''import unittest
from transport_trace import trace

class RemainingGroup(unittest.TestCase):
    def test_must_not_run(self):
        trace('F30:FORBIDDEN:remaining-group')
'''

PARTIAL_WORKER_SOURCE = '''#!/usr/bin/python
import os
import struct

fd = int(os.environ['SUITEBRIDGE_RESPONSE_FD'])
os.write(fd, struct.pack('>I', 64) + b'{"schema_version":')
os.close(fd)
os._exit(24)
'''

F31_A_SOURCE = '''import unittest
from transport_trace import trace

class FirstGroup(unittest.TestCase):
    def test_body(self):
        trace('F31:a:body')
'''

F31_B_SOURCE = '''import unittest
from transport_trace import trace

class SecondGroup(unittest.TestCase):
    def test_body(self):
        trace('F31:b:body')
'''

F32_SOURCE = '''import os
from pathlib import Path
import subprocess
import sys
import time
import unittest
from transport_trace import trace

def identity(pid):
    fields = Path('/proc/' + str(pid) + '/stat').read_text().rsplit(')', 1)[1].split()
    return {'pid': pid, 'process_group': os.getpgid(pid), 'start_time': fields[19]}

class CancelEnteredBody(unittest.TestCase):
    def test_wait_for_frontend_cancellation(self):
        child = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(120)'],
                                 stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        trace('F32:body:entered', worker=identity(os.getpid()), descendant=identity(child.pid))
        while True:
            time.sleep(0.1)
'''

F33_NATIVE_SOURCE = '''import importlib.util
import os
from pathlib import Path
import sys
import unittest
from transport_trace import trace

class NativeEnvironment(unittest.TestCase):
    def test_target_environment(self):
        expected_executable = os.environ['SUITEBRIDGE_EXPECTED_TARGET_EXECUTABLE']
        expected_prefix = os.environ['SUITEBRIDGE_EXPECTED_TARGET_PREFIX']
        forbidden_site = os.environ['SUITEBRIDGE_FORBIDDEN_FRONTEND_SITE']
        self.assertEqual(sys.executable, expected_executable)
        self.assertEqual(sys.prefix, expected_prefix)
        self.assertEqual(Path(expected_executable).is_symlink(),
                         os.environ['SUITEBRIDGE_EXPECT_TARGET_SYMLINK'] == '1')
        self.assertIsNone(importlib.util.find_spec('pygments'))
        self.assertIsNone(importlib.util.find_spec('pytest'))
        self.assertNotIn(forbidden_site, sys.path)
        trace('F33:native:verified', executable=sys.executable, prefix=sys.prefix)
'''

F33_FRONTEND_SOURCE = '''import os
import sys
import pygments
from transport_trace import trace

def test_frontend_environment():
    assert pygments.__version__ == '2.21.0'
    assert sys.executable == os.environ['SUITEBRIDGE_EXPECTED_FRONTEND_EXECUTABLE']
    assert sys.prefix == os.environ['SUITEBRIDGE_EXPECTED_FRONTEND_PREFIX']
    trace('F33:frontend:verified', executable=sys.executable, prefix=sys.prefix)
'''

F34_SOURCE = '''import unittest
from transport_trace import trace

class MustNotExecute(unittest.TestCase):
    def test_forbidden(self):
        trace('F34:FORBIDDEN:body')
'''


def ordinary_files(test_files):
    return {'transport_trace.py': TRACE_SOURCE, 'tests/__init__.py': '', **test_files}


F29_STDOUT = (b'F29_STDOUT_BEGIN\n' + b'O' * 262144 + bytes(range(256)) +
              b'\n{"schema_version":1,"type":"finished","status":"complete"}\nF29_STDOUT_END\n')
F29_STDERR = (b'F29_STDERR_BEGIN\n' + b'E' * 262144 + bytes(reversed(range(256))) +
              b'\n{"schema_version":1,"type":"group_result","status":"complete"}\nF29_STDERR_END\n')

CASES = {
    'F29': {
        'variants': {'output_isolation': ordinary_files({'tests/test_output.py': F29_SOURCE})},
        'expected': {
            'mode': 'native_reference_and_bridge',
            'native_ids': ['test_output.TransportOutput.test_payload'],
            'trace': ['F29:body:start', 'F29:body:end'],
            'native_outcome': 'one success, no repeats',
            'protocol': 'Valid independent frames; stdout/stderr content is never parsed as protocol.',
            'raw_payloads': {
                'stdout': {'bytes': len(F29_STDOUT), 'sha256': hashlib.sha256(F29_STDOUT).hexdigest(), 'occurrences': 1},
                'stderr': {'bytes': len(F29_STDERR), 'sha256': hashlib.sha256(F29_STDERR).hexdigest(), 'occurrences': 1}},
            'output_check': 'Retained raw files must contain the exact contiguous payload once; do not UTF-8 decode before comparison.',
            'watchdog_seconds': 45}},
    'F30': {
        'variants': {
            'abrupt_exit': ordinary_files({'tests/test_abrupt.py': F30_ABRUPT_SOURCE,
                                           'tests/test_zz_remaining.py': F30_AFTER_SOURCE}),
            'partial_frame_eof': {'partial_worker.py': PARTIAL_WORKER_SOURCE}},
        'expected': {
            'abrupt_exit': {'mode': 'controlled_native_exit_and_bridge', 'target_exit': 23,
                            'trace': ['F30:body:entered'], 'session_exit': 'nonzero',
                            'status': 'incomplete', 'retries': 0,
                            'custody': 'Retain acknowledged prefix; active group incomplete, remaining group unexecuted; no invented failure callback or passing group.'},
            'partial_frame_eof': {'mode': 'fake_target_executable', 'worker_exit': 24,
                                  'wire_hex': (struct.pack('>I', 64) + b'{"schema_version":').hex(),
                                  'session_exit': 'nonzero', 'status': 'incomplete', 'retries': 0,
                                  'acknowledged_plan': False, 'native_bodies': 0,
                                  'custody': 'Explicit partial frame/EOF diagnostic and no successful final artifact.'}}},
    'F31': {
        'variants': {variant: ordinary_files({'tests/test_a_group.py': F31_A_SOURCE,
                                             'tests/test_b_group.py': F31_B_SOURCE})
                     for variant in ['duplicate_sequence', 'unknown_group', 'out_of_order_group', 'oversized_frame']},
        'expected': {
            'mode': 'protocol_client_against_real_worker',
            'plan_modules': ['test_a_group', 'test_b_group'],
            'error_type': 'error', 'error_code': 'invalid_request', 'worker_exit': 'nonzero',
            'worker_must_be_reaped': True, 'retries': 0,
            'duplicate_sequence_trace': ['F31:a:body'],
            'other_variant_trace': [],
            'oversized_frame_hex': struct.pack('>I', MAX_FRAME_BYTES + 1).hex(),
            'watchdog_seconds': 45,
            'faults': {
                'duplicate_sequence': 'After plan/select and first valid run, resend the identical sequence=1 run command for the first group.',
                'unknown_group': 'After selection, send sequence=1 run for __suitebridge_unknown_group__.',
                'out_of_order_group': 'Select both groups in native order, then request the second group first with sequence=1.',
                'oversized_frame': 'After selection, send only a length header declaring MAX_FRAME_BYTES+1; no body follows.'}}},
    'F32': {
        'variants': {'cancel_owned_worker': ordinary_files({'tests/test_cancel.py': F32_SOURCE})},
        'expected': {
            'mode': 'controlled_frontend_cancellation_only',
            'readiness_event': 'F32:body:entered',
            'cancellation': 'Send one SIGINT to the frontend PID after the readiness event; do not initially signal the worker or its descendant.',
            'readiness_deadline_seconds': 30, 'cleanup_deadline_seconds': 5,
            'session_exit': 'nonzero', 'status': 'interrupted or incomplete',
            'live_processes_after_cleanup': 0,
            'ownership': 'Match PID plus /proc start_time from readiness before assessing or emergency-cleaning the worker/descendant; never act on a reused PID.',
            'worker_requirement': 'Frontend reaps its worker; worker is absent, descendant absent or dead zombie; no matching live process remains.',
            'artifact': 'Valid interrupted/incomplete native artifact or explicit report-generation error, never a successful final artifact.',
            'emergency_cleanup': 'Harness may kill only identity-verified owned groups after the deadline; needing this cleanup is a failed fixture, not a pass.',
            'retries': 0}},
    'F33': {
        'variants': {variant: {**ordinary_files({'tests/test_environment.py': F33_NATIVE_SOURCE}),
                               'frontend_cases/test_frontend_environment.py': F33_FRONTEND_SOURCE}
                     for variant in ['mixed_existing_venv', 'mixed_symlinked_venv']},
        'expected': {
            'mode': 'mixed_frontend_and_native_invocation',
            'native_ids': ['test_environment.NativeEnvironment.test_target_environment'],
            'frontend_ids': ['frontend_cases/test_frontend_environment.py::test_frontend_environment'],
            'trace_event_multiset': ['F33:native:verified', 'F33:frontend:verified'],
            'native_environment': 'Existing no-Pygments target venv, requested symlinked bin/python path retained exactly; sys.prefix is that target venv.',
            'frontend_environment': 'Existing pytest venv with Pygments 2.21.0; frontend execution path/prefix remain separate.',
            'required_environment': ['SUITEBRIDGE_EXPECTED_TARGET_EXECUTABLE', 'SUITEBRIDGE_EXPECTED_TARGET_PREFIX',
                                     'SUITEBRIDGE_FORBIDDEN_FRONTEND_SITE', 'SUITEBRIDGE_EXPECTED_FRONTEND_EXECUTABLE',
                                     'SUITEBRIDGE_EXPECTED_FRONTEND_PREFIX', 'SUITEBRIDGE_EXPECT_TARGET_SYMLINK'],
            'path_policy': 'Use absolute lexical venv/bin/python paths for execution. The existing target is a copied regular executable; the second variant uses the approved fixture-owned target_alias facade.',
            'alias_actions': ['Create target_alias/bin and target_alias/lib/python3.14.',
                              'Symlink target_alias/bin/python to the existing target executable without changing that executable.',
                              'Copy the existing target pyvenv.cfg unchanged.',
                              'Symlink target_alias/lib/python3.14/site-packages to existing target site-packages.'],
            'result': 'Both populations pass exactly once, or report a real environment mismatch; no environment substitution.'}},
    'F34': {
        'variants': {
            'nonexistent_target': ordinary_files({'tests/test_forbidden.py': F34_SOURCE}),
            'invalid_native_root': {**ordinary_files({'tests/test_forbidden.py': F34_SOURCE}),
                                    'invalid_native_root': 'This is a regular file, not a native project directory.\n'}},
        'expected': {
            'nonexistent_target': {'target_path': '<fixture-root>/does-not-exist/bin/python',
                                   'precondition': 'Path must not exist; native project root is otherwise valid.'},
            'invalid_native_root': {'native_root': '<fixture-root>/invalid_native_root',
                                    'precondition': 'Native root is the supplied regular file; target interpreter is valid.'},
            'mode': 'configuration_error', 'session_exit': 'nonzero explicit usage/collection/infrastructure error',
            'trace': [], 'native_bodies': 0, 'worker_substitution': False, 'retries': 0,
            'artifact': 'An explicit configuration diagnostic and no successful native artifact; missing output is not a pass.'}}
}


def manifest():
    cases = {}
    for case_id, case in CASES.items():
        cases[case_id] = {'expected': case['expected'], 'variants': {}}
        for variant, files in case['variants'].items():
            cases[case_id]['variants'][variant] = {
                'files': {name: {'bytes': len(content.encode('utf-8')),
                                  'sha256': hashlib.sha256(content.encode('utf-8')).hexdigest()}
                          for name, content in files.items()}}
    return {'schema_version': 1, 'scope': 'Frozen fixture sources and expected behavior, not product implementation or observed results.',
            'wire': {'frame_header': '4-byte unsigned big-endian body byte length',
                     'body': 'UTF-8 JSON object', 'max_frame_bytes': MAX_FRAME_BYTES,
                     'required_fields': ['schema_version', 'type', 'sequence', 'invocation_id', 'group_id'],
                     'sequence': 'Each direction starts at 0 and increases by exactly one.',
                     'nongroup_group_id': None,
                     'environment': [COMMAND_FD_ENV, RESPONSE_FD_ENV, INVOCATION_ENV],
                     'message_types': ['plan', 'select', 'selected', 'run', 'group_result', 'finish', 'finished', 'error']},
            'environment_fixture_sources': environment_fixture_sources(), 'cases': cases}


def environment_fixture_sources():
    """Pin read-only sources for the separately approved F33 venv facade."""
    prefix = DEFAULT_TARGET.parent.parent
    site = prefix / 'lib/python3.14/site-packages'
    package_files = {str(path.relative_to(site)): hashlib.sha256(path.read_bytes()).hexdigest()
                     for path in sorted(site.rglob('*'))
                     if path.is_file() and '__pycache__' not in path.parts}
    return {'target_python_lexical': str(DEFAULT_TARGET),
            'target_python_resolved_for_provenance_only': str(DEFAULT_TARGET.resolve()),
            'target_python_sha256': hashlib.sha256(DEFAULT_TARGET.read_bytes()).hexdigest(),
            'pyvenv_cfg_source': str(prefix / 'pyvenv.cfg'),
            'pyvenv_cfg_sha256': hashlib.sha256((prefix / 'pyvenv.cfg').read_bytes()).hexdigest(),
            'site_packages_symlink_target': str(site),
            'site_package_files': package_files,
            'frontend_python_lexical': str(DEFAULT_FRONTEND)}


def materialize(case_id, destination, variant=None):
    """Write one frozen project/shim into a new directory; never execute it."""
    case = CASES[case_id]
    if variant is None:
        if len(case['variants']) != 1:
            raise ValueError('Choose one explicit frozen variant')
        variant = next(iter(case['variants']))
    files = case['variants'][variant]
    destination = Path(destination).absolute()
    destination.mkdir(parents=True, exist_ok=False)
    for name, content in files.items():
        output = destination / name
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(content, encoding='utf-8')
        if name == 'partial_worker.py':
            output.chmod(0o755)
    configuration = {'case_id': case_id, 'variant': variant, 'root': str(destination),
                     'trace_environment': TRACE_ENV, 'expected': case['expected']}
    if case_id == 'F33':
        target = DEFAULT_TARGET
        actions = []
        if variant == 'mixed_symlinked_venv':
            alias = destination / 'target_alias'
            (alias / 'bin').mkdir(parents=True)
            (alias / 'lib/python3.14').mkdir(parents=True)
            target = alias / 'bin/python'
            target.symlink_to(DEFAULT_TARGET)
            shutil.copyfile(DEFAULT_TARGET.parent.parent / 'pyvenv.cfg', alias / 'pyvenv.cfg')
            (alias / 'lib/python3.14/site-packages').symlink_to(
                DEFAULT_TARGET.parent.parent / 'lib/python3.14/site-packages', target_is_directory=True)
            actions = [{'action': 'symlink', 'path': str(target), 'target': str(DEFAULT_TARGET)},
                       {'action': 'copy', 'path': str(alias / 'pyvenv.cfg'),
                        'source': str(DEFAULT_TARGET.parent.parent / 'pyvenv.cfg')},
                       {'action': 'symlink', 'path': str(alias / 'lib/python3.14/site-packages'),
                        'target': str(DEFAULT_TARGET.parent.parent / 'lib/python3.14/site-packages')}]
        configuration.update(target_python=str(target), alias_creation_actions=actions,
                             environment={
            'SUITEBRIDGE_EXPECTED_TARGET_EXECUTABLE': str(target),
            'SUITEBRIDGE_EXPECTED_TARGET_PREFIX': str(target.parent.parent),
            'SUITEBRIDGE_EXPECT_TARGET_SYMLINK': '1' if variant == 'mixed_symlinked_venv' else '0',
            'SUITEBRIDGE_FORBIDDEN_FRONTEND_SITE': str(DEFAULT_FRONTEND.parent.parent / 'lib/python3.14/site-packages'),
            'SUITEBRIDGE_EXPECTED_FRONTEND_EXECUTABLE': str(DEFAULT_FRONTEND),
            'SUITEBRIDGE_EXPECTED_FRONTEND_PREFIX': str(DEFAULT_FRONTEND.parent.parent)})
    elif case_id == 'F30' and variant == 'partial_frame_eof':
        # Keep the frozen shim bytes intact, including its historical shebang.
        # The supplied frontend Python executes it through this POSIX launcher.
        launcher = destination / 'partial_worker_launcher'
        launcher.write_text('#!/bin/sh\nexec ' + shlex.quote(str(DEFAULT_FRONTEND)) + ' ' +
                            shlex.quote(str(destination / 'partial_worker.py')) + ' \"$@\"\n')
        launcher.chmod(0o755)
        configuration['target_python'] = str(launcher)
    elif case_id == 'F34':
        if variant == 'nonexistent_target':
            configuration['target_python'] = str(destination / 'does-not-exist/bin/python')
        else:
            configuration['native_root'] = str(destination / 'invalid_native_root')
    return configuration


def run_protocol_fault(command, output_directory, trace_path, variant, environment, working_directory):
    """Send a frozen F31 command fault to a real worker; retain every observation.

    The caller supplies the real worker command and its ordinary project/artifact
    configuration. This client supplies only the agreed dedicated FD transport.
    It never imports, patches, restarts or retries product code.
    """
    if variant not in CASES['F31']['variants']:
        raise ValueError('Unknown frozen F31 variant')
    output_directory = Path(output_directory)
    output_directory.mkdir(parents=True, exist_ok=False)
    trace_path = Path(trace_path)
    if trace_path.exists():
        raise ValueError('Trace must be a new file')
    command_read, command_write = os.pipe()
    response_read, response_write = os.pipe()
    invocation = 'fixture-F31-' + variant
    child_env = dict(environment)
    child_env.update({COMMAND_FD_ENV: str(command_read), RESPONSE_FD_ENV: str(response_write),
                      INVOCATION_ENV: invocation, TRACE_ENV: str(trace_path)})
    receipt = {'case_id': 'F31', 'variant': variant, 'command': list(command), 'cwd': str(working_directory),
               'invocation_id': invocation, 'sent': [], 'received': [], 'forced_cleanup': False}
    deadline = time.monotonic() + 45

    def exact(count):
        value = b''
        while len(value) < count:
            remaining = deadline - time.monotonic()
            if remaining <= 0 or not select.select([response_read], [], [], remaining)[0]:
                raise TimeoutError('F31 experimental hang watchdog')
            part = os.read(response_read, count - len(value))
            if not part:
                raise EOFError('Worker response EOF before complete frame')
            value += part
        return value

    def receive():
        length = struct.unpack('>I', exact(4))[0]
        if length > MAX_FRAME_BYTES:
            raise ValueError('Worker response exceeded frozen maximum frame size')
        payload = json.loads(exact(length).decode('utf-8'))
        if not isinstance(payload, dict):
            raise ValueError('Worker response was not an object')
        receipt['received'].append(payload)
        expected_sequence = len(receipt['received']) - 1
        for key, expected in [('schema_version', 1), ('sequence', expected_sequence), ('invocation_id', invocation)]:
            if payload.get(key) != expected:
                raise ValueError('Worker response envelope mismatch: ' + key)
        if 'group_id' not in payload:
            raise ValueError('Worker response missing group_id')
        return payload

    def send(message_type, sequence, group_id=None, **fields):
        payload = {'schema_version': 1, 'type': message_type, 'sequence': sequence,
                   'invocation_id': invocation, 'group_id': group_id, **fields}
        encoded = json.dumps(payload, separators=(',', ':')).encode('utf-8')
        frame = struct.pack('>I', len(encoded)) + encoded
        offset = 0
        while offset < len(frame):
            offset += os.write(command_write, frame[offset:])
        receipt['sent'].append(payload)

    process = None
    try:
        with (output_directory / 'worker.stdout').open('wb') as stdout, (output_directory / 'worker.stderr').open('wb') as stderr:
            process = subprocess.Popen(list(command), cwd=working_directory, env=child_env, stdout=stdout, stderr=stderr,
                                       pass_fds=(command_read, response_write), start_new_session=True)
            os.close(command_read)
            command_read = None
            os.close(response_write)
            response_write = None
            plan = receive()
            if plan.get('type') != 'plan':
                raise ValueError('Expected initial worker plan')
            groups = plan.get('groups', [])
            if [group.get('module_name') for group in groups] != ['test_a_group', 'test_b_group']:
                raise ValueError('F31 fixture must produce the two frozen ordinary modules in native order')
            group_ids = [group['group_id'] for group in groups]
            if len(set(group_ids)) != 2:
                raise ValueError('F31 plan group identities are not distinct')
            send('select', 0, selected_groups=group_ids)
            selected = receive()
            if selected.get('type') != 'selected' or selected.get('selected_groups') != group_ids:
                raise ValueError('Worker did not acknowledge the fixed selection')
            if variant == 'duplicate_sequence':
                send('run', 1, group_ids[0])
                result = receive()
                if result.get('type') != 'group_result' or result.get('group_id') != group_ids[0]:
                    raise ValueError('Expected first group result before duplicate request')
                send('run', 1, group_ids[0])
            elif variant == 'unknown_group':
                send('run', 1, '__suitebridge_unknown_group__')
            elif variant == 'out_of_order_group':
                send('run', 1, group_ids[1])
            else:
                raw = struct.pack('>I', MAX_FRAME_BYTES + 1)
                os.write(command_write, raw)
                receipt['sent'].append({'raw_frame_hex': raw.hex()})
            response = receive()
            receipt['error_response_valid'] = response.get('type') == 'error' and response.get('code') == 'invalid_request'
            os.close(command_write)
            command_write = None
            receipt['worker_exit_code'] = process.wait(timeout=max(0.001, deadline - time.monotonic()))
    except Exception as error:
        receipt['driver_error'] = type(error).__name__ + ': ' + str(error)
    finally:
        if process is not None and process.poll() is None:
            receipt['forced_cleanup'] = True
            os.killpg(process.pid, signal.SIGKILL)
            receipt['worker_exit_code'] = process.wait()
        for fd in [command_read, command_write, response_read, response_write]:
            if fd is not None:
                os.close(fd)
    try:
        records = [json.loads(line) for line in trace_path.read_text().splitlines()] if trace_path.exists() else []
    except Exception as error:
        records = []
        receipt['driver_error'] = 'Trace read failed: ' + type(error).__name__ + ': ' + str(error)
    receipt['trace'] = records
    expected_trace = ['F31:a:body'] if variant == 'duplicate_sequence' else []
    receipt['passed'] = (receipt.get('error_response_valid', False) and
                         receipt.get('worker_exit_code') not in (None, 0) and
                         not receipt['forced_cleanup'] and 'driver_error' not in receipt and
                         [entry.get('event') for entry in records] == expected_trace)
    (output_directory / 'fault-receipt.json').write_text(json.dumps(receipt, indent=2) + '\n')
    return receipt

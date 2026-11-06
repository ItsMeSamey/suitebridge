"""Bounded native unittest module integration for pytest.

Native cases execute in the requested interpreter. Pytest items represent whole
native module groups, never individual native tests.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import select
import signal
import struct
import subprocess
import tempfile
import time
import uuid

import pytest


MAX_FRAME_BYTES = 1024 * 1024
SCHEMA_VERSION = 1
STATE = pytest.StashKey()
FAILURE_KINDS = {'failure', 'error', 'unexpected_success', 'subtest_failure', 'subtest_error'}
EVENT_KINDS = FAILURE_KINDS | {'run_start', 'run_stop', 'start', 'stop', 'success',
                              'skip', 'expected_failure', 'subtest_success'}


class BridgeError(Exception):
    """Actionable native worker or transport failure."""


class NativeGroupFailure(Exception):
    """Native failures belonging to one reported pytest group."""


class NativeGroupInterrupted(Exception):
    """An incomplete pytest group, without an inferred native failure."""


def atomic_json(path, value):
    with tempfile.NamedTemporaryFile('w', encoding='utf-8', dir=path.parent,
                                     prefix='.suitebridge-', delete=False) as stream:
        temporary = Path(stream.name)
        json.dump(value, stream, indent=2, sort_keys=True)
        stream.write('\n')
    try:
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def lexical_absolute(value):
    # Resolving an executable symlink can change Python's venv identity.
    return Path(os.path.abspath(os.path.expanduser(value)))


def event_failure_details(events):
    lines = []
    for event in events:
        if event.get('kind') in FAILURE_KINDS:
            label = event.get('exception_type') or event['kind']
            message = event.get('message', '')
            lines.append(f"{event.get('id', '<unknown native identity>')}: {label}" +
                         (f"\n  {message}" if message else ''))
    return '\n'.join(lines)


class Controller:
    def __init__(self, config, root, native_root, target, output, timeout):
        self.config = config
        self.root = root
        self.native_root = native_root
        self.target = target
        self.output = output
        self.output_dir = output.parent
        self.worker_dir = self.output_dir / 'worker'
        self.worker_dir.mkdir()
        self.timeout = timeout
        self.invocation_id = uuid.uuid4().hex
        self.process = None
        self.command_fd = None
        self.response_fd = None
        self.send_sequence = 0
        self.receive_sequence = 0
        self.plan = None
        self.groups = []
        self.selected = []
        self.executed = []
        self.items = []
        self.selected_sent = False
        self.finished = False
        self.failed = False
        self.interrupted = False
        self.native_collected = False
        self.native_selectors = None
        self.collect_only = bool(config.option.collectonly)
        self.report = {
            'schema_version': SCHEMA_VERSION, 'invocation_id': self.invocation_id,
            'status': 'starting', 'successful': False, 'native_successful': False,
            'target_python_requested': str(target), 'native_root': str(native_root),
            'worker_artifact_root': 'worker', 'planned_groups': [], 'selected_groups': [],
            'executed_groups': [], 'omitted_groups': [], 'group_results': [],
            'events': [], 'tests_run': 0, 'pytest_group_nodes': [],
            'notice': 'Pytest items are native module groups. Omitted groups are not validated.',
        }
        self.persist()

    def persist(self):
        try:
            atomic_json(self.output, self.report)
        except Exception as error:
            raise BridgeError(f'Cannot write native report {self.output}: {error}') from error

    def _deadline(self):
        return None if self.timeout is None else time.monotonic() + self.timeout

    def _ready(self, fd, writing, deadline):
        remaining = None if deadline is None else deadline - time.monotonic()
        if remaining is not None and remaining <= 0:
            raise BridgeError(f'Native worker exceeded the requested {self.timeout:g}-second communication watchdog')
        readable, writable, _ = select.select([] if writing else [fd], [fd] if writing else [], [], remaining)
        if not (writable if writing else readable):
            raise BridgeError(f'Native worker exceeded the requested {self.timeout:g}-second communication watchdog')

    def _read_exact(self, count, deadline):
        parts = []
        remaining = count
        while remaining:
            self._ready(self.response_fd, False, deadline)
            chunk = os.read(self.response_fd, min(remaining, 65536))
            if not chunk:
                code = self.process.poll() if self.process else None
                raise BridgeError(f'Native worker closed its protocol stream during a frame (exit {code})')
            parts.append(chunk)
            remaining -= len(chunk)
        return b''.join(parts)

    def _receive(self, expected_type):
        deadline = self._deadline()
        header = self._read_exact(4, deadline)
        length, = struct.unpack('!I', header)
        if length == 0 or length > MAX_FRAME_BYTES:
            raise BridgeError(f'Invalid native protocol frame length: {length}')
        try:
            message = json.loads(self._read_exact(length, deadline).decode('utf-8'))
        except (ValueError, UnicodeError) as error:
            raise BridgeError('Native worker returned malformed UTF-8 JSON') from error
        if not isinstance(message, dict):
            raise BridgeError('Native worker returned a non-object protocol message')
        required = {'schema_version', 'type', 'sequence', 'invocation_id', 'group_id'}
        if not required.issubset(message):
            raise BridgeError('Native worker protocol message is missing required envelope fields')
        if (type(message['schema_version']) is not int or message['schema_version'] != SCHEMA_VERSION or
                message['invocation_id'] != self.invocation_id or
                type(message['sequence']) is not int or
                message['sequence'] != self.receive_sequence):
            raise BridgeError('Native worker protocol identity, schema or sequence mismatch')
        self.receive_sequence += 1
        if message['type'] == 'error':
            details = message.get('error')
            if isinstance(details, dict):
                details = str(details.get('exception_type', 'worker error')) + ': ' + str(details.get('message', ''))
            else:
                details = message.get('message', message.get('code'))
            raise BridgeError('Native worker rejected a request: ' + str(details))
        if message['type'] != expected_type:
            raise BridgeError(f'Expected native protocol {expected_type}, received {message["type"]!r}')
        return message

    def _send(self, kind, group_id=None, **fields):
        message = {'schema_version': SCHEMA_VERSION, 'type': kind,
                   'sequence': self.send_sequence, 'invocation_id': self.invocation_id,
                   'group_id': group_id, **fields}
        payload = json.dumps(message, separators=(',', ':')).encode('utf-8')
        if len(payload) > MAX_FRAME_BYTES:
            raise BridgeError('Native request exceeds the protocol frame bound')
        raw = struct.pack('!I', len(payload)) + payload
        deadline = self._deadline()
        offset = 0
        while offset < len(raw):
            self._ready(self.command_fd, True, deadline)
            try:
                count = os.write(self.command_fd, raw[offset:offset + 4096])
            except OSError as error:
                raise BridgeError(f'Cannot send request to native worker: {error}') from error
            if count <= 0:
                raise BridgeError('Native worker command stream closed')
            offset += count
        self.send_sequence += 1

    def start(self):
        if self.process is not None:
            return
        command_read, command_write = os.pipe()
        response_read, response_write = os.pipe()
        environment = dict(os.environ)
        for name in list(environment):
            if name in {'PYTHONPATH', 'PYTHONHOME'} or name.startswith('PYTEST_'):
                environment.pop(name)
        environment.update(PYTHONDONTWRITEBYTECODE='1', PYTHONNOUSERSITE='1',
                           SUITEBRIDGE_COMMAND_FD=str(command_read),
                           SUITEBRIDGE_RESPONSE_FD=str(response_write),
                           SUITEBRIDGE_INVOCATION_ID=self.invocation_id)
        command = [str(self.target), str(Path(__file__).with_name('suitebridge_worker.py').absolute()),
                   '--root', str(self.root), '--tests', self.native_root.relative_to(self.root).as_posix(),
                   '--output-dir', str(self.worker_dir)]
        self.report['worker_command'] = command
        try:
            with (self.worker_dir / 'worker.stdout.bin').open('xb') as stdout, \
                    (self.worker_dir / 'worker.stderr.bin').open('xb') as stderr:
                self.process = subprocess.Popen(command, cwd=self.root, env=environment,
                    stdin=subprocess.DEVNULL, stdout=stdout, stderr=stderr,
                    pass_fds=(command_read, response_write), start_new_session=True)
        except Exception as error:
            for descriptor in (command_read, command_write, response_read, response_write):
                os.close(descriptor)
            raise BridgeError(f'Cannot start target Python {self.target}: {error}. '
                              'Set --native-python to the interpreter that runs your unittest suite.') from error
        os.close(command_read)
        os.close(response_write)
        self.command_fd, self.response_fd = command_write, response_read
        self.report.update(worker_pid=self.process.pid, worker_process_group=self.process.pid)
        self.persist()
        plan = self._receive('plan')
        if plan['group_id'] is not None or not isinstance(plan.get('groups'), list):
            raise BridgeError('Native worker returned an invalid group plan')
        groups = plan['groups']
        identifiers = []
        for group in groups:
            if not isinstance(group, dict) or not isinstance(group.get('group_id'), str):
                raise BridgeError('Native plan contains an invalid group')
            if group.get('mode') not in {'module', 'atomic'}:
                raise BridgeError('Native plan contains an unsupported group mode')
            if group['mode'] == 'module' and not isinstance(group.get('module_name'), str):
                raise BridgeError('Native module group has no module name')
            identifiers.append(group['group_id'])
        if len(identifiers) != len(set(identifiers)):
            raise BridgeError('Native worker returned duplicate group identities')
        self.plan, self.groups = plan, groups
        environment = plan.get('target_environment', plan.get('environment'))
        if not isinstance(environment, dict) or environment.get('executable') != str(self.target):
            raise BridgeError('Native worker did not report the exact requested target interpreter path')
        self.report.update(status='collected', planned_groups=groups,
                           target_environment=environment,
                           discovery_errors=plan.get('loader_errors', []),
                           loader_errors=plan.get('loader_errors', []),
                           discovered=plan.get('discovered'),
                           event_artifact=plan.get('event_artifact', 'native-events.jsonl'))
        self.persist()

    def choose(self, items):
        native = [item for item in items if isinstance(item, NativeGroupItem) and item.controller is self]
        ids = [item.group['group_id'] for item in native]
        planned = [group['group_id'] for group in self.groups]
        if len(ids) != len(set(ids)) or ids != [identifier for identifier in planned if identifier in ids]:
            raise BridgeError('Native groups were duplicated or reordered; native discovery order is required')
        self.items = native
        self.report['pytest_group_nodes'] = [{'group_id': item.group['group_id'], 'nodeid': item.nodeid}
                                              for item in native]
        self.selected = [] if self.collect_only else ids
        self.report.update(selected_groups=list(self.selected),
                           omitted_groups=[identifier for identifier in planned if identifier not in self.selected],
                           status='collected_only' if self.collect_only else 'selected')
        self._send('select', selected_groups=self.selected, collect_only=self.collect_only)
        acknowledgement = self._receive('selected')
        if acknowledgement['group_id'] is not None:
            raise BridgeError('Native selection acknowledgement has an unexpected group identity')
        acknowledged = acknowledgement.get('selected_groups')
        if acknowledged != self.selected:
            raise BridgeError('Native selection acknowledgement changed the selected group list')
        self.selected_sent = True
        self.persist()

    def _artifact(self, message):
        relative = message.get('artifact')
        expected = message.get('sha256')
        if not isinstance(relative, str) or not isinstance(expected, str):
            raise BridgeError('Native response is missing its result artifact and hash')
        path_part = Path(relative)
        if path_part.is_absolute() or '..' in path_part.parts or not path_part.parts:
            raise BridgeError('Native response artifact path escapes the invocation directory')
        path = self.worker_dir / path_part
        current = self.worker_dir
        for part in path_part.parts:
            current = current / part
            if current.is_symlink():
                raise BridgeError('Native response artifact must not use symbolic links')
        if not path.is_file() or not path.resolve().is_relative_to(self.worker_dir.resolve()):
            raise BridgeError('Native response artifact is missing or outside its invocation directory')
        raw = path.read_bytes()
        if hashlib.sha256(raw).hexdigest() != expected:
            raise BridgeError('Native response artifact hash mismatch')
        try:
            data = json.loads(raw)
        except (ValueError, UnicodeError) as error:
            raise BridgeError('Native response artifact is not valid JSON') from error
        if (not isinstance(data, dict) or type(data.get('schema_version')) is not int or
                data.get('schema_version') != SCHEMA_VERSION or
                data.get('invocation_id') != self.invocation_id):
            raise BridgeError('Native result artifact has an invalid schema or invocation identity')
        return data, str(Path('worker') / path_part)

    def _validate_events(self, data, cumulative=False):
        events = data.get('events')
        tests_run = data.get('tests_run')
        if (not isinstance(events, list) or type(tests_run) is not int or tests_run < 0 or
                any(not isinstance(event, dict) for event in events)):
            raise BridgeError('Native artifact has an invalid event or test-count inventory')
        previous = None
        for event in events:
            sequence = event.get('sequence')
            occurrence = event.get('occurrence')
            if (type(sequence) is not int or sequence < 0 or event.get('kind') not in EVENT_KINDS or
                    ('id' not in event) or ('parent_id' not in event) or
                    (event['id'] is not None and not isinstance(event['id'], str)) or
                    (event['parent_id'] is not None and not isinstance(event['parent_id'], str)) or
                    (occurrence is not None and (type(occurrence) is not int or occurrence < 1))):
                raise BridgeError('Native artifact contains a malformed event')
            if previous is not None and sequence != previous + 1:
                raise BridgeError('Native artifact event sequence is not consecutive')
            previous = sequence
        if cumulative and events and events[0]['sequence'] != 0:
            raise BridgeError('Cumulative native event inventory does not start at zero')
        if sum(event['kind'] == 'start' for event in events) != tests_run:
            raise BridgeError('Native event inventory disagrees with its test count')
        return events

    def run_group(self, group):
        identifier = group['group_id']
        if self.failed or self.finished or not self.selected_sent:
            raise BridgeError('Native worker is unavailable; no group was retried')
        if len(self.executed) >= len(self.selected) or self.selected[len(self.executed)] != identifier:
            raise BridgeError('Native group execution no longer matches the selected native order')
        self._send('run', group_id=identifier)
        response = self._receive('group_result')
        if response['group_id'] != identifier:
            raise BridgeError('Native worker returned a different group than requested')
        data, path = self._artifact(response)
        if data.get('group_id') != identifier or data.get('status') != response.get('status'):
            raise BridgeError('Native group result identity or status disagrees with its response')
        if type(data.get('successful')) is not bool or data['successful'] != response.get('successful'):
            raise BridgeError('Native group success status disagrees with its response')
        self._validate_events(data)
        self.report['group_results'].append({'group_id': identifier, 'artifact': path,
                                            'sha256': response['sha256'], 'status': data.get('status')})
        if data.get('status') == 'completed':
            self.executed.append(identifier)
            self.report['executed_groups'] = list(self.executed)
        self.report['status'] = 'running'
        self.persist()
        return data

    def _prefix(self):
        relative = self.report.get('event_artifact', 'native-events.jsonl')
        if not isinstance(relative, str) or Path(relative).is_absolute() or '..' in Path(relative).parts:
            return
        path = self.worker_dir / relative
        current = self.worker_dir
        for part in Path(relative).parts:
            current = current / part
            if current.is_symlink():
                self.report['event_prefix_error'] = 'Event prefix path contains a symbolic link'
                return
        if not path.is_file() or not path.resolve().is_relative_to(self.worker_dir.resolve()):
            return
        events = []
        try:
            with path.open(encoding='utf-8') as stream:
                for line in stream:
                    try:
                        event = json.loads(line)
                    except ValueError:
                        self.report['event_prefix_truncated'] = True
                        break
                    if not isinstance(event, dict):
                        self.report['event_prefix_truncated'] = True
                        break
                    events.append(event)
        except (OSError, UnicodeError) as error:
            self.report['event_prefix_error'] = str(error)
        self.report['events'] = events
        self.report['tests_run'] = sum(event.get('kind') == 'start' for event in events)
        self.report['event_custody'] = 'flushed worker prefix; completion is not implied'

    def abort(self, reason, interrupted=False):
        self.failed = True
        self.interrupted = self.interrupted or interrupted
        self.report.update(status='interrupted' if self.interrupted else 'incomplete',
                           successful=False, native_successful=False, infrastructure_error=str(reason))
        self.terminate()
        self._prefix()
        self.report['uncompleted_selected_groups'] = [group for group in self.selected if group not in self.executed]
        self.persist()

    def terminate(self):
        if self.process is not None:
            if self.process.poll() is None:
                try:
                    os.killpg(self.process.pid, signal.SIGTERM)
                except ProcessLookupError:
                    pass
                try:
                    self.process.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    try:
                        os.killpg(self.process.pid, signal.SIGKILL)
                    except ProcessLookupError:
                        pass
                    self.process.wait()
            else:
                self.process.wait()
            # A worker may exit while one of its owned descendants remains.
            try:
                os.killpg(self.process.pid, 0)
            except ProcessLookupError:
                pass
            else:
                try:
                    os.killpg(self.process.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                self.report['remaining_worker_descendants_terminated'] = True
            self.report['worker_exit_code'] = self.process.returncode
            self.report['worker_reaped'] = True
        for name in ('command_fd', 'response_fd'):
            descriptor = getattr(self, name)
            if descriptor is not None:
                try:
                    os.close(descriptor)
                except OSError:
                    pass
                setattr(self, name, None)

    def finish(self):
        if self.finished or self.failed:
            return
        if self.process is None:
            self.report.update(status='not_collected', successful=False)
            self.persist()
            self.finished = True
            return
        if not self.selected_sent:
            self.choose([])
        self._send('finish')
        response = self._receive('finished')
        if response['group_id'] is not None:
            raise BridgeError('Native completion response has an unexpected group identity')
        data, artifact = self._artifact(response)
        if data.get('status') != response.get('status'):
            raise BridgeError('Native completion artifact status disagrees with its response')
        if type(data.get('successful')) is not bool or data['successful'] != response.get('successful'):
            raise BridgeError('Native completion success status disagrees with its response')
        self._validate_events(data, cumulative=True)
        kinds = [event['kind'] for event in data['events']]
        if data.get('status') == 'collected_only':
            if kinds or data['tests_run'] != 0:
                raise BridgeError('Collection-only native completion executed native events')
        elif data.get('status') in {'completed', 'empty_selection'}:
            if (not kinds or kinds[0] != 'run_start' or kinds[-1] != 'run_stop' or
                    kinds.count('run_start') != 1 or kinds.count('run_stop') != 1):
                raise BridgeError('Native completion did not preserve one logical run lifecycle')
        if data.get('selected_groups') != self.selected or data.get('executed_groups') != self.executed:
            raise BridgeError('Native completion changed the selected or acknowledged executed groups')
        if data.get('planned_groups') != self.groups:
            raise BridgeError('Native completion changed its discovery plan')
        loader_errors = data.get('loader_errors')
        if not isinstance(loader_errors, list) or any(not isinstance(value, str) for value in loader_errors):
            raise BridgeError('Native completion has an invalid discovery error inventory')
        if data.get('status') == 'completed' and self.executed != self.selected:
            raise BridgeError('Native completion omitted a selected group')
        if data.get('status') == 'completed' and data['successful'] != (
                not any(event['kind'] in FAILURE_KINDS for event in data['events'])):
            raise BridgeError('Native completion success flag disagrees with its failure events')
        self.report.update(native_artifact=artifact, native_artifact_sha256=response['sha256'],
                           native_status=data.get('status'), events=data.get('events', []),
                           tests_run=data.get('tests_run', 0), counts=data.get('counts', {}),
                           target_environment=data.get('target_environment', self.report.get('target_environment', {})),
                           discovered=data.get('discovered'), selected_inventory=data.get('selected_inventory'),
                           loader_errors=loader_errors, discovery_errors=loader_errors,
                           native_successful=bool(data.get('successful')), status=data.get('status'),
                           executed_groups=list(self.executed),
                           uncompleted_selected_groups=[g for g in self.selected if g not in self.executed])
        if data.get('status') not in {'completed', 'empty_selection', 'collected_only'}:
            self.interrupted = data.get('status') == 'interrupted' or self.interrupted
            self.failed = True
            self.report['successful'] = False
        if self.interrupted:
            self.report['status'] = 'interrupted'
        self.finished = True
        try:
            self.process.wait(timeout=self.timeout)
        except subprocess.TimeoutExpired as error:
            raise BridgeError('Native worker did not exit within the requested watchdog after completion') from error
        code = self.process.returncode
        expected = ({0 if data['successful'] else 1} if data.get('status') == 'completed'
                    else {0} if data.get('status') in {'empty_selection', 'collected_only'}
                    else {130} if data.get('status') == 'interrupted' else {2})
        if code not in expected:
            raise BridgeError(f'Native worker exited unexpectedly after completion: {code}')
        self.terminate()
        self.persist()


class NativeDirectory(pytest.Directory):
    def collect(self):
        controller = self.config.stash[STATE]
        if controller.native_collected:
            raise self.CollectError('The configured native directory was collected twice; duplicate native execution is refused')
        controller.native_collected = True
        try:
            controller.start()
        except KeyboardInterrupt:
            controller.abort('Interrupted during native discovery', interrupted=True)
            raise
        except Exception as error:
            controller.abort(error)
            raise self.CollectError(str(error)) from error
        for index, group in enumerate(controller.groups):
            name = ('native-suite[atomic]' if group['mode'] == 'atomic'
                    else f"native-module[{group['module_name']}]")
            yield NativeGroupItem.from_parent(self, name=name, controller=controller,
                                             group=group, native_index=index)


class NativeGroupItem(pytest.Item):
    def __init__(self, *, controller, group, native_index, **kwargs):
        super().__init__(**kwargs)
        self.controller = controller
        self.group = group
        self.native_index = native_index

    def runtest(self):
        controller = self.controller
        try:
            data = controller.run_group(self.group)
            if data.get('status') == 'interrupted':
                controller.interrupted = True
                controller.finish()
                raise KeyboardInterrupt('Native suite interrupted; retained native report: ' + str(controller.output))
            if data.get('status') != 'completed':
                raise BridgeError('Native group did not complete; see ' + str(controller.output))
            events = data.get('events')
            if not isinstance(events, list):
                raise BridgeError('Native group artifact has no event inventory')
            failures = event_failure_details(events)
            if failures or not data.get('successful'):
                raise NativeGroupFailure('Native module group failed:\n' +
                    (failures or 'The native result reported failure without a complete success outcome.') +
                    '\nNative event report: ' + str(controller.output))
            success_count = sum(event.get('kind') == 'success' for event in events)
            skips = sum(event.get('kind') == 'skip' for event in events)
            expected_failures = sum(event.get('kind') == 'expected_failure' for event in events)
            if success_count == 0:
                pytest.skip(f'Native group has no successful native tests: {skips} skip entries, '
                            f'{expected_failures} expected failures, {data.get("tests_run", 0)} tests started')
        except NativeGroupFailure:
            raise
        except KeyboardInterrupt:
            if not controller.finished:
                controller.abort('Frontend interrupted while native work was active', interrupted=True)
            message = ('INTERRUPTED: native module group did not complete. '
                       'This reports interruption, not a native assertion failure.\n'
                       'Retained native event report: ' + str(controller.output))
            # Complete pytest's call/teardown reporting before its loop stops.
            # Direct KeyboardInterrupt leaves JUnit's setup entry unfinished.
            self.session.shouldstop = message
            raise NativeGroupInterrupted(message) from None
        except pytest.skip.Exception:
            raise
        except Exception as error:
            controller.abort(error)
            raise BridgeError(str(error)) from error

    def repr_failure(self, excinfo, style=None):
        if isinstance(excinfo.value, (NativeGroupFailure, NativeGroupInterrupted, BridgeError)):
            return str(excinfo.value)
        return super().repr_failure(excinfo, style=style)

    def reportinfo(self):
        return self.path, 0, 'native module group: ' + (self.group.get('module_name') or 'atomic suite')


def pytest_addoption(parser):
    group = parser.getgroup('suitebridge', 'Native unittest module groups in a separate interpreter')
    group.addoption('--native-unittest', metavar='PATH', help='One native discovery directory relative to --native-root')
    group.addoption('--native-root', metavar='PATH', help='Native project root (default: invocation directory)')
    group.addoption('--native-python', metavar='PATH', help='Exact absolute target venv interpreter path')
    group.addoption('--native-report', metavar='PATH', help='Native JSON report inside a new, nonexistent invocation directory')
    group.addoption('--native-timeout', metavar='SECONDS', type=float,
                    help='Optional communication hang watchdog per request; unset means no watchdog')


def pytest_configure(config):
    discovery = config.getoption('native_unittest')
    if discovery is None:
        return
    output = None
    created = False
    try:
        for option in ('native_python', 'native_report'):
            if not config.getoption(option):
                raise BridgeError('--native-unittest requires --' + option.replace('_', '-'))
        output = lexical_absolute(config.getoption('native_report'))
        output.parent.mkdir(parents=True, exist_ok=False)
        created = True
        if output.name == 'worker':
            raise BridgeError('--native-report filename must not be the reserved worker directory name')
        root = lexical_absolute(config.getoption('native_root') or str(config.invocation_params.dir)).resolve()
        if not root.is_dir():
            raise BridgeError(f'Native project root is not a directory: {root}')
        relative = Path(discovery)
        if relative.is_absolute() or '..' in relative.parts:
            raise BridgeError('--native-unittest must be a project-relative discovery directory')
        native_root = (root / relative).resolve()
        if not native_root.is_dir() or not native_root.is_relative_to(root):
            raise BridgeError(f'Native discovery root is not a directory inside {root}: {native_root}')
        if output.parent.resolve().is_relative_to(root):
            raise BridgeError('--native-report invocation directory must be outside the native project')
        target_value = config.getoption('native_python')
        if not Path(os.path.expanduser(target_value)).is_absolute():
            raise BridgeError('--native-python must name an absolute interpreter path')
        target = lexical_absolute(target_value)
        if not target.is_file() or not os.access(target, os.X_OK):
            raise BridgeError(f'Target Python is missing or not executable: {target}. '
                              'Use the absolute interpreter path that runs your unittest suite.')
        timeout = config.getoption('native_timeout')
        if timeout is not None and timeout <= 0:
            raise BridgeError('--native-timeout must be positive when supplied')
        if os.environ.get('PYTEST_DISABLE_PLUGIN_AUTOLOAD') != '1':
            raise BridgeError('SuiteBridge requires PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 for its supported serial frontend')
        if os.environ.get('PYTEST_ADDOPTS') or os.environ.get('PYTEST_PLUGINS'):
            raise BridgeError('Clear PYTEST_ADDOPTS and PYTEST_PLUGINS for the supported frontend configuration')
        if config.getoption('assertmode') != 'plain' or config.getoption('capture') != 'no':
            raise BridgeError('SuiteBridge requires --assert=plain --capture=no')
        if config.pluginmanager.hasplugin('warnings') or config.pluginmanager.hasplugin('cacheprovider'):
            raise BridgeError('SuiteBridge requires -p no:warnings -p no:cacheprovider')
        if config.pluginmanager.hasplugin('xdist') or config.pluginmanager.hasplugin('testmon'):
            raise BridgeError('SuiteBridge does not support xdist or testmon integration')
        requested_selectors = []
        rewritten_arguments = []
        full_native_argument = False
        for argument in config.args:
            argument_parts = str(argument).split('::')
            path_part = argument_parts[0]
            path = lexical_absolute(str(Path(config.invocation_params.dir) / path_part)).resolve()
            if path != native_root and path.is_relative_to(native_root):
                raise BridgeError('Select a native module group through the discovery directory, not a native file: '
                                  f'{native_root}::native-module[module_name]')
            if path == native_root and len(argument_parts) > 1:
                selector = argument_parts[1]
                if (len(argument_parts) != 2 or not (
                        (selector.startswith('native-module[') and selector.endswith(']')) or
                        selector == 'native-suite[atomic]')):
                    raise BridgeError('Native selection supports whole group node IDs only; '
                                      'individual native tests are not pytest items')
                requested_selectors.append(selector)
                # Pytest rejects directory::parts before consulting directory collectors.
                # Resolve only our native group syntax through the group filter below.
                rewritten_arguments.append(path_part)
            else:
                rewritten_arguments.append(str(argument))
                if len(argument_parts) == 1 and path.is_dir() and native_root.is_relative_to(path):
                    full_native_argument = True
        config.args[:] = rewritten_arguments
        controller = Controller(config, root, native_root, target, output, timeout)
        if requested_selectors and not full_native_argument:
            controller.native_selectors = set(requested_selectors)
            controller.report['requested_group_selectors'] = sorted(controller.native_selectors)
            controller.persist()
        config.stash[STATE] = controller
    except Exception as error:
        if created and output is not None:
            try:
                atomic_json(output, {'schema_version': SCHEMA_VERSION, 'status': 'preflight_error',
                                     'successful': False, 'error': str(error), 'tests_run': 0,
                                     'note': 'No native test body was started.'})
            except Exception:
                pass
        raise pytest.UsageError(str(error)) from error


@pytest.hookimpl(tryfirst=True)
def pytest_collect_directory(path, parent):
    controller = parent.config.stash.get(STATE, None)
    if controller is not None and path.resolve() == controller.native_root:
        return NativeDirectory.from_parent(parent, path=path)
    return None


@pytest.hookimpl(trylast=True)
def pytest_collection_modifyitems(session, config, items):
    controller = config.stash.get(STATE, None)
    if controller is None or controller.native_selectors is None or controller.failed:
        return
    available = {('native-suite[atomic]' if group['mode'] == 'atomic'
                  else f"native-module[{group['module_name']}]") for group in controller.groups}
    unknown = controller.native_selectors - available
    if unknown:
        message = 'Unknown native module group selector: ' + ', '.join(sorted(unknown))
        controller.abort(message)
        raise pytest.UsageError(message)
    removed = [item for item in items if isinstance(item, NativeGroupItem) and
               item.controller is controller and item.name not in controller.native_selectors]
    if removed:
        items[:] = [item for item in items if item not in removed]
        config.hook.pytest_deselected(items=removed)


@pytest.hookimpl(trylast=True)
def pytest_collection_finish(session):
    controller = session.config.stash.get(STATE, None)
    if controller is None or controller.failed:
        return
    try:
        if not controller.native_collected:
            raise BridgeError('The configured native discovery directory was not collected; '
                              f'include {controller.native_root} in the pytest paths')
        controller.choose(session.items)
    except KeyboardInterrupt:
        controller.abort('Interrupted during native selection', interrupted=True)
        raise
    except Exception as error:
        controller.abort(error)
        raise pytest.UsageError(str(error)) from error


@pytest.hookimpl(tryfirst=True)
def pytest_sessionfinish(session, exitstatus):
    controller = session.config.stash.get(STATE, None)
    if controller is None:
        return
    try:
        controller.finish()
    except KeyboardInterrupt:
        controller.abort('Interrupted during native completion', interrupted=True)
        session.exitstatus = pytest.ExitCode.INTERRUPTED
    except Exception as error:
        controller.abort(error)
        if int(session.exitstatus) == 0:
            session.exitstatus = pytest.ExitCode.TESTS_FAILED
    if controller.interrupted:
        session.exitstatus = pytest.ExitCode.INTERRUPTED
    elif controller.failed and int(session.exitstatus) == 0:
        session.exitstatus = pytest.ExitCode.TESTS_FAILED
    if (controller.report.get('status') == 'completed' and
            not controller.report.get('native_successful') and int(session.exitstatus) == 0):
        session.exitstatus = pytest.ExitCode.TESTS_FAILED
    controller.report['pytest_exitstatus'] = int(session.exitstatus)
    controller.report['successful'] = bool(controller.report.get('native_successful') and
                                            int(session.exitstatus) == 0 and
                                            controller.report.get('status') == 'completed')
    try:
        controller.persist()
    except BridgeError as error:
        reporter = session.config.pluginmanager.getplugin('terminalreporter')
        if reporter:
            reporter.write_line(str(error), red=True)
        if int(session.exitstatus) == 0:
            session.exitstatus = pytest.ExitCode.TESTS_FAILED


def pytest_unconfigure(config):
    controller = config.stash.get(STATE, None)
    if controller is not None:
        controller.terminate()


def pytest_terminal_summary(terminalreporter, exitstatus, config):
    controller = config.stash.get(STATE, None)
    if controller is None:
        return
    terminalreporter.write_sep('-', 'SuiteBridge native result (pytest items are module groups)')
    terminalreporter.write_line(f"Native status: {controller.report.get('status')}; "
        f"native tests started: {controller.report.get('tests_run', 0)}; "
        f"groups executed: {len(controller.executed)}/{len(controller.selected)}")
    terminalreporter.write_line(f"Omitted native groups: {len(controller.report.get('omitted_groups', []))} (not validated)")
    if controller.report.get('infrastructure_error'):
        terminalreporter.write_line('Native infrastructure error: ' + controller.report['infrastructure_error'])
    terminalreporter.write_line('Exact native results: ' + str(controller.output))

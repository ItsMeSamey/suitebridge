#!/usr/bin/env python3
"""Persistent stdlib-only native unittest worker for SuiteBridge."""
from __future__ import annotations

import argparse
from collections import Counter
from contextlib import contextmanager
import hashlib
import importlib.metadata
import importlib.util
import inspect
import json
import os
from pathlib import Path
import sys
import tempfile
import traceback
import unittest

from suitebridge_protocol import ProtocolError, SCHEMA_VERSION, read_frame, write_frame

ORDINARY_SUITE_METHODS = {name: inspect.getattr_static(unittest.TestSuite, name)
                          for name in ('run', '__call__', '__iter__')}
ORDINARY_CASE_METHODS = {name: inspect.getattr_static(unittest.TestCase, name)
                         for name in ('run', '__call__')}


def has_ordinary_dispatch(instance, methods):
    # Static lookup includes instance attributes without invoking custom descriptors.
    if inspect.getattr_static(type(instance), '__getattribute__') is not object.__getattribute__:
        return False
    return all(inspect.getattr_static(instance, name) is method
               for name, method in methods.items())


class InvalidRequest(ProtocolError):
    pass


def exception_details(error):
    return {'exception_type': type(error).__module__ + '.' + type(error).__qualname__,
            'message': str(error)}


def hash_file(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def artifact(directory, name, value):
    path = directory / name
    with path.open('x', encoding='utf-8') as stream:
        json.dump(value, stream, ensure_ascii=True, indent=2, sort_keys=True)
        stream.write('\n')
        stream.flush()
    return {'artifact': name, 'sha256': hash_file(path)}


@contextmanager
def output_files(directory, stem):
    paths = [directory / (stem + suffix) for suffix in ('.stdout.bin', '.stderr.bin')]
    for stream in (sys.stdout, sys.stderr):
        stream.flush()
    saved = [os.dup(1), os.dup(2)]
    files = []
    try:
        files = [path.open('xb', buffering=0) for path in paths]
        for descriptor, stream in zip((1, 2), files):
            os.dup2(stream.fileno(), descriptor)
        yield {'stdout': paths[0].name, 'stderr': paths[1].name}
    finally:
        for stream in (sys.stdout, sys.stderr):
            try:
                stream.flush()
            except (OSError, ValueError):
                pass
        for descriptor, original in zip((1, 2), saved):
            os.dup2(original, descriptor)
            os.close(original)
        for stream in files:
            stream.close()


class Channel:
    def __init__(self):
        self.command_fd = int(os.environ['SUITEBRIDGE_COMMAND_FD'])
        self.response_fd = int(os.environ['SUITEBRIDGE_RESPONSE_FD'])
        self.invocation = os.environ['SUITEBRIDGE_INVOCATION_ID']
        if not self.invocation or self.command_fd < 3 or self.response_fd < 3:
            raise ValueError('invalid inherited protocol configuration')
        if self.command_fd == self.response_fd:
            raise ValueError('command and response descriptors must be distinct')
        self.incoming = 0
        self.outgoing = 0

    def send(self, kind, group=None, **payload):
        message = dict(payload, schema_version=SCHEMA_VERSION, type=kind,
                       sequence=self.outgoing, invocation_id=self.invocation,
                       group_id=group)
        write_frame(self.response_fd, message)
        self.outgoing += 1

    def receive(self):
        message = read_frame(self.command_fd)
        if type(message.get('schema_version')) is not int or message['schema_version'] != SCHEMA_VERSION:
            raise InvalidRequest('unsupported schema_version')
        if message.get('invocation_id') != self.invocation:
            raise InvalidRequest('invocation_id mismatch')
        if type(message.get('sequence')) is not int or message['sequence'] != self.incoming:
            raise InvalidRequest('sequence is duplicate or out of order')
        if not isinstance(message.get('type'), str) or 'group_id' not in message:
            raise InvalidRequest('missing message type or group_id')
        if message['group_id'] is not None and not isinstance(message['group_id'], str):
            raise InvalidRequest('group_id must be a string or null')
        self.incoming += 1
        return message


def inspect_tree(suite):
    """Inspect only ordinary concrete containers; never enter custom iterators."""
    leaves = []
    custom_case = False

    def visit(node):
        nonlocal custom_case
        if type(node) is not unittest.TestSuite:
            return 'custom_or_lazy_suite'
        if not has_ordinary_dispatch(node, ORDINARY_SUITE_METHODS):
            return 'configured_suite_dispatch'
        if type(node._tests) is not list:
            return 'custom_or_lazy_suite'
        for child in node._tests:
            if isinstance(child, unittest.BaseTestSuite):
                reason = visit(child)
                if reason:
                    return reason
            elif isinstance(child, unittest.TestCase):
                if not has_ordinary_dispatch(child, ORDINARY_CASE_METHODS):
                    custom_case = True
                leaves.append(child)
            else:
                return 'opaque_suite_member'
        return None

    reason = visit(suite)
    return (None, reason) if reason else (leaves, 'custom_test_run_or_call' if custom_case else None)


def copy_group(suite, module):
    clone = unittest.TestSuite()
    clone.__dict__.update(suite.__dict__)
    children = []
    for child in suite._tests:
        if type(child) is unittest.TestSuite:
            subtree = copy_group(child, module)
            if subtree._tests:
                children.append(subtree)
        elif type(child).__module__ == module:
            children.append(child)
    clone._tests = children
    return clone


def plan_suite(suite):
    cases, reason = inspect_tree(suite)
    if cases is not None:
        segments = []
        for case in cases:
            module = type(case).__module__
            if not segments or segments[-1] != module:
                segments.append(module)
        if len(set(segments)) != len(segments):
            reason = 'noncontiguous_modules'
    if reason:
        discovered = [case.id() for case in cases] if cases is not None else None
        occurrences = ([{'id': native_id, 'ordinal': index + 1}
                        for index, native_id in enumerate(discovered)]
                       if discovered is not None else None)
        return ([{'group_id': 'atomic', 'module_name': None,
                  'test_count': len(discovered) if discovered is not None else None,
                  'test_occurrences': occurrences, 'mode': 'atomic', 'fallback_reason': reason}],
                {'atomic': suite}, discovered, reason)
    groups, executables, discovered = [], {}, []
    ordinal = 0
    for index, module in enumerate(segments):
        identity = f'g{index:04d}'
        occurrences = []
        for case in cases:
            if type(case).__module__ == module:
                ordinal += 1
                native_id = case.id()
                discovered.append(native_id)
                occurrences.append({'id': native_id, 'ordinal': ordinal})
        groups.append({'group_id': identity, 'module_name': module,
                       'test_count': len(occurrences), 'test_occurrences': occurrences,
                       'mode': 'module'})
        executables[identity] = copy_group(suite, module)
    return groups, executables, discovered, None


class NativeResult(unittest.TextTestResult):
    """Observe standard callbacks without changing their native classification."""
    def __init__(self, *args, event_stream, **kwargs):
        super().__init__(*args, **kwargs)
        self.event_stream = event_stream
        self.records = []
        self.active_group = None
        self.parent = None
        self.ordinal = None
        self.next_ordinal = 1

    def record(self, kind, *, case=None, parent=None, error=None, reason=None):
        native_id = case.id() if case is not None else None
        entry = {'sequence': len(self.records), 'kind': kind, 'id': native_id,
                 'parent_id': native_id if parent is None else parent,
                 'occurrence': self.ordinal, 'group_id': self.active_group}
        if error is not None:
            entry['exception_type'] = error[0].__module__ + '.' + error[0].__qualname__
            entry['message'] = str(error[1])
        if reason is not None:
            entry['reason'] = reason
        self.records.append(entry)
        self.event_stream.write(json.dumps(entry, ensure_ascii=True, sort_keys=True) + '\n')
        self.event_stream.flush()

    def startTestRun(self):
        self.record('run_start')
        super().startTestRun()

    def stopTestRun(self):
        self.active_group = None
        self.record('run_stop')
        super().stopTestRun()

    def startTest(self, test):
        self.ordinal = self.next_ordinal
        self.next_ordinal += 1
        self.parent = test.id()
        self.record('start', case=test)
        super().startTest(test)

    def stopTest(self, test):
        self.record('stop', case=test)
        super().stopTest(test)
        self.parent = None
        self.ordinal = None

    def addSuccess(self, test):
        self.record('success', case=test)
        super().addSuccess(test)

    def addFailure(self, test, err):
        self.record('failure', case=test, error=err)
        super().addFailure(test, err)

    def addError(self, test, err):
        self.record('error', case=test, error=err)
        super().addError(test, err)

    def addSkip(self, test, reason):
        self.record('skip', case=test, parent=self.parent or test.id(), reason=reason)
        super().addSkip(test, reason)

    def addExpectedFailure(self, test, err):
        self.record('expected_failure', case=test, error=err)
        super().addExpectedFailure(test, err)

    def addUnexpectedSuccess(self, test):
        self.record('unexpected_success', case=test)
        super().addUnexpectedSuccess(test)

    def addSubTest(self, test, subtest, err):
        if err is None:
            outcome = 'subtest_success'
        elif issubclass(err[0], test.failureException):
            outcome = 'subtest_failure'
        else:
            outcome = 'subtest_error'
        self.record(outcome, case=subtest, parent=test.id(), error=err)
        super().addSubTest(test, subtest, err)


def outcome_counts(events):
    kinds = Counter(event['kind'] for event in events)
    return {'tests_started': kinds['start'], 'tests_stopped': kinds['stop'],
            'successes': kinds['success'], 'skipped_entries': kinds['skip'],
            'expected_failures': kinds['expected_failure'],
            'unexpected_successes': kinds['unexpected_success'],
            'assertion_failures': kinds['failure'] + kinds['subtest_failure'],
            'errors': kinds['error'] + kinds['subtest_error'],
            'subtest_events': sum(kinds[name] for name in ('subtest_success', 'subtest_failure', 'subtest_error'))}


def events_successful(events):
    return not any(event['kind'] in {'failure', 'error', 'unexpected_success',
                                    'subtest_failure', 'subtest_error'} for event in events)


class Invocation:
    def __init__(self, args, channel):
        self.args = args
        self.channel = channel
        self.groups = []
        self.executables = {}
        self.selected = []
        self.executed = []
        self.attempted = []
        self.incomplete = []
        self.group_results = []
        self.result = None
        self.environment = {}
        self.discovered = None
        self.loader_errors = []
        self.inventory_note = None
        self.collect_only = False
        self.interrupted = None
        self.finished_request = False
        self.native_artifact_written = False

    def report(self, status, error=None):
        events = self.result.records if self.result is not None else []
        selected_inventory = None
        if self.discovered is not None:
            selected_inventory = [occurrence['id'] for group in self.groups
                                  if group['group_id'] in self.selected
                                  for occurrence in group['test_occurrences']]
        value = {'schema_version': 1, 'invocation_id': self.channel.invocation,
                 'status': status, 'discovery_status': 'errors' if self.loader_errors else 'complete',
                 'target_environment': self.environment, 'discovered': self.discovered,
                 'selected_inventory': selected_inventory, 'inventory_note': self.inventory_note,
                 'planned_groups': self.groups, 'selected_groups': self.selected,
                 'executed_groups': self.executed, 'group_results': self.group_results,
                 'attempted_groups': self.attempted, 'incomplete_groups': self.incomplete,
                 'unexecuted_groups': [g['group_id'] for g in self.groups if g['group_id'] not in self.attempted],
                 'events': events, 'loader_errors': self.loader_errors,
                 'tests_run': self.result.testsRun if self.result is not None else 0,
                 'executed': [event['id'] for event in events if event['kind'] == 'start'],
                 'counts': outcome_counts(events), 'event_artifact': 'native-events.jsonl',
                 'successful': status in {'completed', 'empty_selection'} and events_successful(events),
                 'output_files': {'stdout': 'session.stdout.bin', 'stderr': 'session.stderr.bin'}}
        if error is not None:
            value['fatal_error'] = exception_details(error)
        return value

    def final_artifact(self, status, error=None):
        value = self.report(status, error)
        reference = artifact(self.args.output_dir, 'native-final.json', value)
        self.native_artifact_written = True
        return value, reference

    def selection(self):
        message = self.channel.receive()
        if message['type'] != 'select' or message['group_id'] is not None:
            raise InvalidRequest('expected one nongroup select request')
        selected = message.get('selected_groups')
        ordered = [group['group_id'] for group in self.groups]
        if (not isinstance(selected, list) or any(not isinstance(item, str) for item in selected)
                or len(selected) != len(set(selected))
                or any(item not in ordered for item in selected)
                or selected != [item for item in ordered if item in selected]):
            raise InvalidRequest('selected_groups must be a unique native-order subset')
        collect_only = message.get('collect_only', False)
        if type(collect_only) is not bool or (collect_only and selected):
            raise InvalidRequest('collect_only requires an empty selected_groups list')
        self.selected = selected
        self.collect_only = collect_only
        self.channel.send('selected', selected_groups=selected, collect_only=collect_only)

    def validate_finish(self, message):
        if message['type'] != 'finish' or message['group_id'] is not None:
            raise InvalidRequest('expected nongroup finish request')
        self.finished_request = True

    def execute_group(self, group_id, result):
        start = len(result.records)
        before_tests = result.testsRun
        result.active_group = group_id
        status = 'completed'
        error = None
        self.attempted.append(group_id)
        with output_files(self.args.output_dir, 'group-' + group_id) as outputs:
            try:
                self.executables[group_id](result)
            except BaseException as caught:
                status = 'interrupted' if isinstance(caught, KeyboardInterrupt) else 'incomplete'
                error = caught
                self.interrupted = caught
                traceback.print_exc()
            finally:
                # Each ordinary group has already completed its native final teardown.
                # Clear only boundary bookkeeping; cumulative public result state remains.
                if status == 'completed':
                    result._previousTestClass = None
                    result._moduleSetUpFailed = False
                    result._testRunEntered = False
        events = result.records[start:]
        value = {'schema_version': 1, 'invocation_id': self.channel.invocation,
                 'group_id': group_id, 'status': status,
                 'successful': status == 'completed' and events_successful(events),
                 'tests_run': result.testsRun - before_tests, 'events': events,
                 'counts': outcome_counts(events), 'output_files': outputs}
        if error is not None:
            value['fatal_error'] = exception_details(error)
        reference = artifact(self.args.output_dir, 'group-' + group_id + '.json', value)
        if status == 'completed':
            self.executed.append(group_id)
        else:
            self.incomplete.append(group_id)
        self.group_results.append(dict(group_id=group_id, status=status,
                                       successful=value['successful'], **reference))
        result.active_group = None
        self.channel.send('group_result', group=group_id, status=status,
                          successful=value['successful'], tests_run=value['tests_run'],
                          counts=value['counts'], **reference)

    def dispatch(self, result):
        for expected in self.selected:
            message = self.channel.receive()
            if message['type'] != 'run' or message['group_id'] != expected:
                raise InvalidRequest('expected the next selected group exactly once: ' + expected)
            self.execute_group(expected, result)
            if self.interrupted is not None:
                self.validate_finish(self.channel.receive())
                return
        self.validate_finish(self.channel.receive())

    def execute(self):
        self.selection()
        if self.collect_only:
            self.validate_finish(self.channel.receive())
            return 'collected_only'
        with (self.args.output_dir / 'native-events.jsonl').open('a', encoding='utf-8') as events:
            def make_result(*args, **kwargs):
                self.result = NativeResult(*args, event_stream=events, **kwargs)
                return self.result

            # TextTestRunner owns the one warnings context and logical run lifecycle.
            class DispatchSuite:
                def __call__(nested_self, result):
                    self.dispatch(result)
                    return result

            unittest.TextTestRunner(stream=sys.stderr, verbosity=0,
                                    resultclass=make_result).run(DispatchSuite())
        if self.interrupted is not None:
            return 'interrupted' if isinstance(self.interrupted, KeyboardInterrupt) else 'incomplete'
        return 'empty_selection' if self.groups and not self.selected else 'completed'


def arguments():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--tests', required=True)
    parser.add_argument('--pattern', default='test*.py')
    parser.add_argument('--output-dir', type=Path, required=True)
    args = parser.parse_args()
    args.root = args.root.resolve()
    args.output_dir = args.output_dir.resolve()
    if not args.root.is_dir():
        raise ValueError('native root must be an existing directory')
    if Path(args.tests).is_absolute() or '..' in Path(args.tests).parts:
        raise ValueError('native discovery path must be relative and contained in the root')
    discovery = (args.root / args.tests).resolve()
    if not discovery.is_relative_to(args.root) or not discovery.is_dir():
        raise ValueError('native discovery root must be an existing contained directory')
    if not args.output_dir.is_dir():
        raise ValueError('frontend must create a fresh invocation output directory')
    if args.output_dir.is_relative_to(args.root):
        raise ValueError('invocation output directory must be outside the native project')
    return args


def target_paths(root):
    helper = Path(__file__).resolve().parent
    frontend_paths = {Path(value or os.getcwd()).resolve()
                      for value in os.environ.get('PYTHONPATH', '').split(os.pathsep) if value}
    for name in tuple(os.environ):
        if name in {'PYTHONPATH', 'PYTHONHOME'} or name.startswith('PYTEST_'):
            os.environ.pop(name, None)
    sys.path[:] = [path for path in sys.path
                   if Path(path or os.getcwd()).resolve() not in frontend_paths | {helper}]
    os.chdir(root)
    sys.path.insert(0, str(root))


def main():
    channel = None
    invocation = None
    try:
        channel = Channel()
        args = arguments()
        # Reserve worker artifacts once; pre-existing artifacts are never reused.
        with (args.output_dir / '.suitebridge-worker').open('x', encoding='utf-8') as marker:
            marker.write(channel.invocation + '\n')
        for name in ('native-final.json', 'native-events.jsonl'):
            if (args.output_dir / name).exists():
                raise ValueError('refusing pre-existing worker artifact: ' + name)
        (args.output_dir / 'native-events.jsonl').touch(exist_ok=False)
        target_paths(args.root)
        sys.dont_write_bytecode = True
        invocation = Invocation(args, channel)
        with tempfile.TemporaryDirectory(prefix='suitebridge-pycache-') as bytecode_cache:
            sys.pycache_prefix = bytecode_cache
            with output_files(args.output_dir, 'session'):
                invocation.environment = {
                    'executable': sys.executable, 'prefix': sys.prefix, 'base_prefix': sys.base_prefix,
                    'version': sys.version, 'sys_path': list(sys.path),
                    'pygments_present': importlib.util.find_spec('pygments') is not None,
                    'dependencies': sorted((distribution.metadata.get('Name', ''), distribution.version)
                                           for distribution in importlib.metadata.distributions())}
                with output_files(args.output_dir, 'discovery'):
                    loader = unittest.TestLoader()
                    suite = loader.discover(args.tests, pattern=args.pattern)
                invocation.loader_errors = list(loader.errors)
                invocation.environment['sys_path'] = list(sys.path)
                invocation.groups, invocation.executables, invocation.discovered, invocation.inventory_note = plan_suite(suite)
                channel.send('plan', groups=invocation.groups,
                             target_environment=invocation.environment,
                             loader_errors=invocation.loader_errors,
                             discovery_status='errors' if loader.errors else 'complete',
                             discovered=invocation.discovered,
                             inventory_note=invocation.inventory_note,
                             event_artifact='native-events.jsonl')
                status = invocation.execute()
                report, reference = invocation.final_artifact(status, invocation.interrupted)
                channel.send('finished', status=status, successful=report['successful'], **reference)
                if status == 'collected_only':
                    return 0
                if invocation.interrupted is not None:
                    return 130 if isinstance(invocation.interrupted, KeyboardInterrupt) else 2
                return 0 if report['successful'] else 1
    except BaseException as error:
        reference = {}
        status = 'interrupted' if isinstance(error, KeyboardInterrupt) else 'incomplete'
        if invocation is not None and not invocation.native_artifact_written:
            try:
                _, reference = invocation.final_artifact(status, error)
            except BaseException as artifact_error:
                print('SuiteBridge could not write final artifact: ' + str(artifact_error), file=sys.stderr)
        if channel is not None:
            try:
                channel.send('error', code='invalid_request' if isinstance(error, ProtocolError) else 'worker_error',
                             status=status, error=exception_details(error), **reference)
            except (OSError, ProtocolError):
                pass
        traceback.print_exc(file=sys.stderr)
        return 130 if isinstance(error, KeyboardInterrupt) else 2


if __name__ == '__main__':
    raise SystemExit(main())

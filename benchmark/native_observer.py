"""Independent observer for native unittest behavior; not imported by the product."""
from __future__ import annotations

import argparse
import importlib.metadata
import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile
import traceback
import unittest


def inventory(suite):
    if type(suite) is not unittest.TestSuite:
        return None
    found = []
    for item in suite._tests:
        if isinstance(item, unittest.TestSuite):
            nested = inventory(item)
            if nested is None:
                return None
            found.extend(nested)
        else:
            found.append(item.id())
    return found


class Observer(unittest.TextTestResult):
    def __init__(self, *args, event_file=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.events = []
        self.current_id = None
        self.current_occurrence = None
        self.occurrences = 0
        self.event_file = event_file

    def event(self, kind, test=None, parent=None, err=None, reason=None):
        identity = test.id() if test is not None else None
        item = {'sequence': len(self.events), 'kind': kind, 'id': identity,
                'parent_id': parent if parent is not None else identity,
                'occurrence': self.current_occurrence}
        if err is not None:
            item['exception_type'] = err[0].__module__ + '.' + err[0].__qualname__
            item['message'] = str(err[1])
        if reason is not None:
            item['reason'] = reason
        self.events.append(item)
        if self.event_file:
            self.event_file.write(json.dumps(item, sort_keys=True) + '\n')
            self.event_file.flush()

    def startTestRun(self):
        self.event('run_start')
        super().startTestRun()

    def stopTestRun(self):
        self.event('run_stop')
        super().stopTestRun()

    def startTest(self, test):
        self.occurrences += 1
        self.current_occurrence = self.occurrences
        self.current_id = test.id()
        self.event('start', test)
        super().startTest(test)

    def stopTest(self, test):
        self.event('stop', test)
        super().stopTest(test)
        self.current_id = None
        self.current_occurrence = None

    def addSuccess(self, test):
        self.event('success', test)
        super().addSuccess(test)

    def addFailure(self, test, err):
        self.event('failure', test, err=err)
        super().addFailure(test, err)

    def addError(self, test, err):
        self.event('error', test, err=err)
        super().addError(test, err)

    def addSkip(self, test, reason):
        self.event('skip', test, parent=self.current_id or test.id(), reason=reason)
        super().addSkip(test, reason)

    def addExpectedFailure(self, test, err):
        self.event('expected_failure', test, err=err)
        super().addExpectedFailure(test, err)

    def addUnexpectedSuccess(self, test):
        self.event('unexpected_success', test)
        super().addUnexpectedSuccess(test)

    def addSubTest(self, test, subtest, err):
        kind = ('subtest_success' if err is None else
                'subtest_failure' if issubclass(err[0], test.failureException) else 'subtest_error')
        self.event(kind, subtest, parent=test.id(), err=err)
        super().addSubTest(test, subtest, err)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--tests', default='tests')
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--pattern', default='test*.py')
    parser.add_argument('--module', action='append', help='Explicit native module subset for selection oracle')
    args = parser.parse_args()
    root, output = args.root.resolve(), args.output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    if output.exists():
        raise FileExistsError('Refusing to overwrite observer output')
    os.chdir(root)
    observer_directory = Path(__file__).resolve().parent
    sys.path[:] = [entry for entry in sys.path
                   if Path(entry or os.getcwd()).resolve() != observer_directory]
    sys.path.insert(0, str(root))
    empty_cache = tempfile.TemporaryDirectory(prefix='suitebridge-oracle-pycache-')
    sys.pycache_prefix = empty_cache.name
    sys.dont_write_bytecode = True
    report = {'schema_version': 1, 'status': 'starting', 'discovered': None,
              'events': [], 'loader_errors': [], 'tests_run': 0, 'successful': False,
              'target_environment': {'executable': sys.executable, 'version': sys.version,
                  'sys_path': list(sys.path),
                  'pygments_present': importlib.util.find_spec('pygments') is not None,
                  'dependencies': sorted((d.metadata.get('Name', ''), d.version)
                                         for d in importlib.metadata.distributions())}}
    result = None
    exit_code = 2
    event_path = output.with_suffix('.events.jsonl')
    with event_path.open('x') as event_file:
        try:
            loader = unittest.TestLoader()
            suite = loader.discover(args.tests, pattern=args.pattern)
            report['loader_errors'] = loader.errors
            report['discovered'] = inventory(suite)
            report['target_environment']['sys_path'] = list(sys.path)
            if report['discovered'] is None:
                report['inventory_note'] = 'Custom suite inventory is not traversed before execution.'
            if args.module:
                def subset(node):
                    if type(node) is not unittest.TestSuite:
                        raise ValueError('Module subset is unsupported for a custom suite')
                    children = []
                    for child in node._tests:
                        if isinstance(child, unittest.TestSuite):
                            selected = subset(child)
                            if selected.countTestCases():
                                children.append(selected)
                        elif child.__class__.__module__ in args.module:
                            children.append(child)
                    return unittest.TestSuite(children)
                suite = subset(suite)
            report['selected_inventory'] = inventory(suite)
            def make_result(*values, **options):
                nonlocal result
                result = Observer(*values, event_file=event_file, **options)
                return result
            runner = unittest.TextTestRunner(verbosity=0, resultclass=make_result)
            runner.run(suite)
            report['status'] = 'complete'
            report['successful'] = result.wasSuccessful()
            exit_code = 0 if result.wasSuccessful() else 1
        except BaseException as error:
            report['status'] = 'interrupted' if isinstance(error, KeyboardInterrupt) else 'aborted'
            report['fatal_error'] = {'exception_type': type(error).__module__ + '.' + type(error).__qualname__,
                                     'message': str(error)}
            traceback.print_exc()
            exit_code = 130 if isinstance(error, KeyboardInterrupt) else 2
        finally:
            if result is not None:
                report['events'] = result.events
                report['tests_run'] = result.testsRun
                report['executed'] = [event['id'] for event in result.events if event['kind'] == 'start']
            else:
                report['executed'] = []
            output.write_text(json.dumps(report, indent=2, sort_keys=True) + '\n')
    return exit_code


if __name__ == '__main__':
    raise SystemExit(main())

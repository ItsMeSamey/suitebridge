"""Harness-only regression checks; these never import or execute SuiteBridge."""
import copy
import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('integration_harness', Path(__file__).resolve().parents[1] / 'portable_integration.py')
harness = importlib.util.module_from_spec(spec)
spec.loader.exec_module(harness)


def payload():
    events = [
        {'sequence': 0, 'kind': 'run_start', 'id': None, 'parent_id': None, 'occurrence': None},
        {'sequence': 1, 'kind': 'start', 'id': 'm.C.test', 'parent_id': 'm.C.test', 'occurrence': 1},
        {'sequence': 2, 'kind': 'success', 'id': 'm.C.test', 'parent_id': 'm.C.test', 'occurrence': 1},
        {'sequence': 3, 'kind': 'stop', 'id': 'm.C.test', 'parent_id': 'm.C.test', 'occurrence': 1},
        {'sequence': 4, 'kind': 'run_stop', 'id': None, 'parent_id': None, 'occurrence': None},
    ]
    return {'status': 'complete', 'discovered': ['m.C.test'], 'selected_inventory': ['m.C.test'],
            'executed': ['m.C.test'], 'tests_run': 1, 'successful': True, 'loader_errors': [],
            'events': events, 'target_environment': {'executable': str(harness.TARGET),
            'pygments_present': False, 'sys_path': ['/tmp/native/tree'], 'dependencies': [], 'version': 'fixture'}}


class HarnessTests(unittest.TestCase):
    def group_example(self):
        events = []
        groups = {}
        xml = {'testcases': []}
        plan = []
        results = []
        for index, module in enumerate(['a', 'b']):
            identity = module + '.C.test'
            identifier = 'g' + str(index)
            one = []
            for kind in ['start', 'failure' if index == 0 else 'success', 'stop']:
                event = {'sequence': len(events) + len(one), 'kind': kind, 'id': identity,
                         'parent_id': identity, 'occurrence': index + 1, 'group_id': identifier}
                if kind == 'failure':
                    event.update(exception_type='builtins.AssertionError', message='fixture failure')
                one.append(event)
            events.extend(one)
            groups[identifier] = {'events': one, 'tests_run': 1, 'status': 'completed', 'successful': index != 0}
            plan.append({'group_id': identifier, 'module_name': module, 'mode': 'module'})
            results.append({'group_id': identifier})
            xml['testcases'].append({'name': 'native-module[' + module + ']', 'failure': index == 0,
                                    'error': False, 'skipped': False,
                                    'detail': identity + ': builtins.AssertionError: fixture failure' if index == 0 else ''})
        return {'planned_groups': plan, 'group_results': results}, {'events': events}, groups, xml

    def test_reporting_role_rule_is_general_and_candidate_stays_blocking(self):
        issues, observations = [], []
        harness.reporting_finding('atomic', 'arbitrary XML defect', issues, observations)
        harness.reporting_finding('bridge', 'arbitrary XML defect', issues, observations)
        self.assertEqual(issues, ['bridge: arbitrary XML defect'])
        self.assertEqual(observations, ['atomic: arbitrary XML defect'])

    def test_exact_group_event_to_junit_attribution_accepts_consistent_reports(self):
        self.assertEqual(harness.group_reporting_issues(*self.group_example()), [])

    def test_swapped_group_outcomes_fail_even_when_aggregate_xml_counts_match(self):
        public, native, groups, xml = self.group_example()
        xml['testcases'][0]['failure'] = False
        xml['testcases'][1]['failure'] = True
        self.assertTrue(harness.group_reporting_issues(public, native, groups, xml))

    def test_group_artifacts_cannot_drop_an_event(self):
        public, native, groups, xml = self.group_example()
        groups['g1']['events'] = groups['g1']['events'][:-1]
        self.assertIn('Group artifacts do not exactly partition the final native callback sequence',
                      harness.group_reporting_issues(public, native, groups, xml))

    def test_native_event_cannot_be_attributed_to_an_unrelated_module(self):
        public, native, groups, xml = self.group_example()
        public['planned_groups'][0]['module_name'] = 'unrelated'
        xml['testcases'][0]['name'] = 'native-module[unrelated]'
        self.assertTrue(any('does not belong' in issue for issue in
                            harness.group_reporting_issues(public, native, groups, xml)))

    def test_interruption_requires_an_explicit_named_nonpassing_group(self):
        public, native, groups, xml = self.group_example()
        groups['g0']['status'] = 'interrupted'
        xml['testcases'][0]['detail'] = 'INTERRUPTED; not a native assertion failure'
        self.assertEqual(harness.group_reporting_issues(public, native, groups, xml), [])
        xml['testcases'][0]['detail'] = 'failed'
        self.assertTrue(harness.group_reporting_issues(public, native, groups, xml))

    def test_target_environment_removes_frontend_transient_variables(self):
        with patch.dict('os.environ', {'PYTEST_CURRENT_TEST': 'frontend-test',
                                      'INTEGRATION_NATIVE_ROOT': '/frontend/root',
                                      'PYTHONPATH': '/frontend/site-packages'}):
            env = harness.environment(Path('/retained/trace.jsonl'), Path('/target/project'))
        self.assertFalse(any(key.startswith(('PYTEST_', 'INTEGRATION_')) for key in env))
        self.assertNotIn('PYTHONPATH', env)
        self.assertEqual(env['NATIVE_FIXTURE_TRACE'], '/retained/trace.jsonl')

    def test_only_declared_metadata_and_complete_status_are_normalized(self):
        reference = payload()
        candidate = copy.deepcopy(reference)
        candidate['status'] = 'completed'
        candidate['target_environment']['sys_path'] = ['/tmp/bridge/tree']
        for event in candidate['events']:
            event['group_id'] = 'module:m'
        self.assertEqual(harness.compare_native(reference, candidate, [['body']], [['body']],
                                               ['/tmp/native/tree', '/tmp/bridge/tree']), [])

    def test_lost_callback_fails_even_with_matching_test_count(self):
        reference = payload()
        candidate = copy.deepcopy(reference)
        candidate['events'][2]['kind'] = 'skip'
        candidate['events'][2]['reason'] = 'unexpected skip'
        self.assertTrue(harness.compare_native(reference, candidate, [], [], []))

    def test_reordered_or_duplicate_event_sequence_is_rejected(self):
        candidate = payload()
        candidate['events'][3]['sequence'] = 2
        with self.assertRaisesRegex(ValueError, 'sequence'):
            harness.native_events(candidate, [])

    def test_fixture_order_is_part_of_the_gate(self):
        reference = payload()
        self.assertIn('Ordered native fixture/body/cleanup trace differs',
                      harness.compare_native(reference, copy.deepcopy(reference),
                                             [['setup'], ['body']], [['body'], ['setup']], []))

    def test_exception_message_is_not_normalized_away(self):
        reference = payload()
        reference['events'][2].update(kind='error', exception_type='builtins.ValueError', message='actual failure')
        reference['successful'] = False
        candidate = copy.deepcopy(reference)
        candidate['events'][2]['message'] = 'different failure'
        self.assertTrue(harness.compare_native(reference, candidate, [], [], []))

    def test_frontend_path_leak_is_detected(self):
        reference = payload()
        candidate = copy.deepcopy(reference)
        candidate['target_environment']['sys_path'].append('/frontend/site-packages')
        self.assertIn('Native target environment sys_path differs',
                      harness.compare_native(reference, candidate, [], [], []))

    def test_non_target_interpreter_is_rejected_even_if_both_reports_claim_it(self):
        reference = payload()
        reference['target_environment']['executable'] = '/usr/bin/python'
        issues = harness.compare_native(reference, copy.deepcopy(reference), [], [], [])
        self.assertTrue(any('exact target venv' in issue for issue in issues))

    def test_mixed_trace_separation_has_a_narrow_allowlist(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'trace.jsonl'
            path.write_text('["frontend.body"]\n["frontend.warning_filter", []]\n["frontend.lookalike"]\n["body"]\n')
            native, frontend = harness.trace_parts(path, mixed=True)
            self.assertEqual(frontend, [['frontend.body'], ['frontend.warning_filter', []]])
            self.assertEqual(native, [['frontend.lookalike'], ['body']])

    def test_junit_counts_are_checked_against_real_elements(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'pytest.xml'
            path.write_text('<testsuites><testsuite tests="9" failures="0" errors="0" skipped="0"><testcase name="native-module[m]"><failure>bad</failure></testcase></testsuite></testsuites>')
            parsed = harness.parse_junit(path)
            self.assertEqual(parsed['counts']['tests'], 1)
            self.assertEqual(parsed['counts']['failures'], 1)
            self.assertEqual(len(parsed['issues']), 2)

    def test_empty_junit_has_zero_items(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'pytest.xml'
            path.write_text('<testsuite tests="0" failures="0" errors="0" skipped="0"/>')
            parsed = harness.parse_junit(path)
            self.assertEqual(parsed['testcases'], [])
            self.assertEqual(parsed['issues'], [])

    def test_frozen_scope_has_all_variants_and_both_selection_probes(self):
        cases = harness.cases()
        self.assertEqual(len(cases), 40)
        self.assertEqual(sum(c['module'] is not None for c in cases), 2)
        self.assertIn('R3/selected-test_extensions', {c['key'] for c in cases})
        self.assertEqual(sum(c['kind'] == 'real' and c['module'] is None for c in cases), 6)


if __name__ == '__main__':
    unittest.main()

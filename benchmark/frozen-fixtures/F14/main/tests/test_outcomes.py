import unittest
from fixture_support import record


class Outcomes(unittest.TestCase):
    def test_pass(self): record("pass.body")
    @unittest.skip("decorated skip")
    def test_skip(self): record("skip.body.unexpected")
    @unittest.expectedFailure
    def test_expected_failure(self):
        record("expected_failure.body")
        self.fail("expected failure")
    @unittest.expectedFailure
    def test_unexpected_success(self): record("unexpected_success.body")

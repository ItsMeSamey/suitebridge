import unittest
from fixture_support import record


class Case(unittest.TestCase):
    def setUp(self):
        record("test.setup")
        self.addCleanup(record, "test.cleanup", "first")
        self.addCleanup(record, "test.cleanup", "second")
        raise RuntimeError("test setup failed")
    def tearDown(self): record("test.teardown.unexpected")
    def test_one(self): record("body.unexpected")

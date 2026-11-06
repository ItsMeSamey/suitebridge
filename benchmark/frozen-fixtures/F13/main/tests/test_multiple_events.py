import unittest
from fixture_support import record


def failing_cleanup():
    record("cleanup", "failing")
    raise RuntimeError("cleanup failed")

class Case(unittest.TestCase):
    def setUp(self):
        record("setup")
        self.addCleanup(record, "cleanup", "last")
        self.addCleanup(failing_cleanup)
    def test_one(self):
        record("body")
        self.fail("body failed")
    def tearDown(self):
        record("teardown")
        raise RuntimeError("teardown failed")

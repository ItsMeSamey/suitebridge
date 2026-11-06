import unittest
from fixture_support import record


class Case(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        record("class.setup")
        cls.addClassCleanup(record, "class.cleanup", "first")
        cls.addClassCleanup(record, "class.cleanup", "second")
        raise unittest.SkipTest("class setup skipped")
    @classmethod
    def tearDownClass(cls): record("class.teardown.unexpected")
    def test_one(self): record("body.unexpected", "one")
    def test_two(self): record("body.unexpected", "two")

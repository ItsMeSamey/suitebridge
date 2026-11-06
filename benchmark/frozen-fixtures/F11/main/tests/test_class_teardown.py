import unittest
from fixture_support import record


class Case(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        record("class.setup")
        cls.addClassCleanup(record, "class.cleanup", "first")
        cls.addClassCleanup(record, "class.cleanup", "second")
    @classmethod
    def tearDownClass(cls):
        record("class.teardown")
        raise RuntimeError("class teardown failed")
    def test_one(self): record("body")

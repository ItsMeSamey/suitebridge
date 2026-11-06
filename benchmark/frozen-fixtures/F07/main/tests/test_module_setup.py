import unittest
from fixture_support import record


def setUpModule():
    record("module.setup")
    unittest.addModuleCleanup(record, "module.cleanup", "first")
    unittest.addModuleCleanup(record, "module.cleanup", "second")
    raise unittest.SkipTest("module setup skipped")

def tearDownModule(): record("module.teardown.unexpected")

class Case(unittest.TestCase):
    def test_one(self): record("body.unexpected", "one")
    def test_two(self): record("body.unexpected", "two")

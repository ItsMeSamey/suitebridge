import unittest
from fixture_support import record


def setUpModule():
    record("module.setup")
    unittest.addModuleCleanup(record, "module.cleanup", "first")
    unittest.addModuleCleanup(record, "module.cleanup", "second")

def tearDownModule():
    record("module.teardown")
    raise RuntimeError("module teardown failed")

class Case(unittest.TestCase):
    def test_one(self): record("body")

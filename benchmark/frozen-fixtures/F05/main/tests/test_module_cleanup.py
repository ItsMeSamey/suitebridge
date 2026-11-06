import unittest
from fixture_support import record


def setUpModule():
    record("module.setup")
    unittest.addModuleCleanup(record, "module.cleanup", "first")
    unittest.addModuleCleanup(record, "module.cleanup", "second")

def tearDownModule():
    record("module.teardown")

class One(unittest.TestCase):
    def test_one(self): record("one.body")

class Two(unittest.TestCase):
    def test_two(self): record("two.body")

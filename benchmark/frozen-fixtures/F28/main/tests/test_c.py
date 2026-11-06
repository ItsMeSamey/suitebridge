import unittest
from fixture_support import record


def setUpModule():
    record('pass.c', "module.setup")
    unittest.addModuleCleanup(record, 'pass.c', "module.cleanup")

def tearDownModule():
    record('pass.c', "module.teardown")

class One(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        record('pass.c', cls.__name__, "class.setup")
        cls.addClassCleanup(record, 'pass.c', cls.__name__, "class.cleanup")

    @classmethod
    def tearDownClass(cls):
        record('pass.c', cls.__name__, "class.teardown")

    def setUp(self):
        record('pass.c', self.id(), "test.setup")
        self.addCleanup(record, 'pass.c', self.id(), "test.cleanup")

    def tearDown(self):
        record('pass.c', self.id(), "test.teardown")

    def test_one(self):
        record('pass.c', self.id(), "body")
        self.assertEqual(1, 1)

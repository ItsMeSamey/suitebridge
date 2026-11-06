import unittest
from fixture_support import record


def setUpModule():
    record('healthy', "module.setup")
    unittest.addModuleCleanup(record, 'healthy', "module.cleanup")

def tearDownModule():
    record('healthy', "module.teardown")

class One(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        record('healthy', cls.__name__, "class.setup")
        cls.addClassCleanup(record, 'healthy', cls.__name__, "class.cleanup")

    @classmethod
    def tearDownClass(cls):
        record('healthy', cls.__name__, "class.teardown")

    def setUp(self):
        record('healthy', self.id(), "test.setup")
        self.addCleanup(record, 'healthy', self.id(), "test.cleanup")

    def tearDown(self):
        record('healthy', self.id(), "test.teardown")

    def test_one(self):
        record('healthy', self.id(), "body")
        self.assertEqual(1, 1)

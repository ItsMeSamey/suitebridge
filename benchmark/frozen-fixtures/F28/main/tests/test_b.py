import unittest
from fixture_support import record


def setUpModule():
    record('failure.b', "module.setup")
    unittest.addModuleCleanup(record, 'failure.b', "module.cleanup")

def tearDownModule():
    record('failure.b', "module.teardown")

class One(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        record('failure.b', cls.__name__, "class.setup")
        cls.addClassCleanup(record, 'failure.b', cls.__name__, "class.cleanup")

    @classmethod
    def tearDownClass(cls):
        record('failure.b', cls.__name__, "class.teardown")

    def setUp(self):
        record('failure.b', self.id(), "test.setup")
        self.addCleanup(record, 'failure.b', self.id(), "test.cleanup")

    def tearDown(self):
        record('failure.b', self.id(), "test.teardown")

    def test_one(self):
        record('failure.b', self.id(), "body")
        self.assertEqual(1, 2)

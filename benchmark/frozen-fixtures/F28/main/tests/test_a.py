import unittest
from fixture_support import record


def setUpModule():
    record('failure.a', "module.setup")
    unittest.addModuleCleanup(record, 'failure.a', "module.cleanup")

def tearDownModule():
    record('failure.a', "module.teardown")

class One(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        record('failure.a', cls.__name__, "class.setup")
        cls.addClassCleanup(record, 'failure.a', cls.__name__, "class.cleanup")

    @classmethod
    def tearDownClass(cls):
        record('failure.a', cls.__name__, "class.teardown")

    def setUp(self):
        record('failure.a', self.id(), "test.setup")
        self.addCleanup(record, 'failure.a', self.id(), "test.cleanup")

    def tearDown(self):
        record('failure.a', self.id(), "test.teardown")

    def test_one(self):
        record('failure.a', self.id(), "body")
        self.assertEqual(1, 2)

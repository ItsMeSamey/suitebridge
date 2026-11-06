import unittest
from fixture_support import record


def setUpModule():
    record('discovery', "module.setup")
    unittest.addModuleCleanup(record, 'discovery', "module.cleanup")

def tearDownModule():
    record('discovery', "module.teardown")

class One(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        record('discovery', cls.__name__, "class.setup")
        cls.addClassCleanup(record, 'discovery', cls.__name__, "class.cleanup")

    @classmethod
    def tearDownClass(cls):
        record('discovery', cls.__name__, "class.teardown")

    def setUp(self):
        record('discovery', self.id(), "test.setup")
        self.addCleanup(record, 'discovery', self.id(), "test.cleanup")

    def tearDown(self):
        record('discovery', self.id(), "test.teardown")

    def test_one(self):
        record('discovery', self.id(), "body")
        self.assertEqual(1, 1)

    def test_two(self):
        record('discovery', self.id(), "body")
        self.assertEqual(1, 1)

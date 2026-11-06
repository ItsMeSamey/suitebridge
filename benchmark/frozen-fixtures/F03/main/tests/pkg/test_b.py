import unittest
from fixture_support import record


def setUpModule():
    record('pkg.b', "module.setup")
    unittest.addModuleCleanup(record, 'pkg.b', "module.cleanup")

def tearDownModule():
    record('pkg.b', "module.teardown")

class One(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        record('pkg.b', cls.__name__, "class.setup")
        cls.addClassCleanup(record, 'pkg.b', cls.__name__, "class.cleanup")

    @classmethod
    def tearDownClass(cls):
        record('pkg.b', cls.__name__, "class.teardown")

    def setUp(self):
        record('pkg.b', self.id(), "test.setup")
        self.addCleanup(record, 'pkg.b', self.id(), "test.cleanup")

    def tearDown(self):
        record('pkg.b', self.id(), "test.teardown")

    def test_one(self):
        record('pkg.b', self.id(), "body")
        self.assertEqual(1, 1)

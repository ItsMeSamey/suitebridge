import unittest
from fixture_support import record


def setUpModule():
    record('counter.a', "module.setup")
    unittest.addModuleCleanup(record, 'counter.a', "module.cleanup")

def tearDownModule():
    record('counter.a', "module.teardown")

class One(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        record('counter.a', cls.__name__, "class.setup")
        cls.addClassCleanup(record, 'counter.a', cls.__name__, "class.cleanup")

    @classmethod
    def tearDownClass(cls):
        record('counter.a', cls.__name__, "class.teardown")

    def setUp(self):
        record('counter.a', self.id(), "test.setup")
        self.addCleanup(record, 'counter.a', self.id(), "test.cleanup")

    def tearDown(self):
        record('counter.a', self.id(), "test.teardown")

    def test_one(self):
        record('counter.a', self.id(), "body")
        self.assertEqual(1, 1)

    def run(self, result=None):
        if result is None:
            return super().run(result)
        record("counter.before", self.id(), result.testsRun)
        try:
            return super().run(result)
        finally:
            record("counter.after", self.id(), result.testsRun)

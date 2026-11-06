import unittest
from fixture_support import record


def setUpModule():
    record('class_order', "module.setup")
    unittest.addModuleCleanup(record, 'class_order', "module.cleanup")

def tearDownModule():
    record('class_order', "module.teardown")

class Alpha(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        record('class_order', cls.__name__, "class.setup")
        cls.addClassCleanup(record, 'class_order', cls.__name__, "class.cleanup")

    @classmethod
    def tearDownClass(cls):
        record('class_order', cls.__name__, "class.teardown")

    def setUp(self):
        record('class_order', self.id(), "test.setup")
        self.addCleanup(record, 'class_order', self.id(), "test.cleanup")

    def tearDown(self):
        record('class_order', self.id(), "test.teardown")

    def test_one(self):
        record('class_order', self.id(), "body")
        self.assertEqual(1, 1)

    def test_two(self):
        record('class_order', self.id(), "body")
        self.assertEqual(1, 1)

class Beta(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        record('class_order', cls.__name__, "class.setup")
        cls.addClassCleanup(record, 'class_order', cls.__name__, "class.cleanup")

    @classmethod
    def tearDownClass(cls):
        record('class_order', cls.__name__, "class.teardown")

    def setUp(self):
        record('class_order', self.id(), "test.setup")
        self.addCleanup(record, 'class_order', self.id(), "test.cleanup")

    def tearDown(self):
        record('class_order', self.id(), "test.teardown")

    def test_one(self):
        record('class_order', self.id(), "body")
        self.assertEqual(1, 1)

    def test_two(self):
        record('class_order', self.id(), "body")
        self.assertEqual(1, 1)

def load_tests(loader, standard_tests, pattern):
    return unittest.TestSuite([Alpha("test_one"), Beta("test_one"), Alpha("test_two")])

import warnings
from fixture_support import record

def test_frontend_population():
    record("frontend.body")
    assert 2 + 2 == 4

def test_frontend_warnings_unchanged():
    record("frontend.warning_filter", [
        [action, getattr(message, "pattern", message),
         category.__module__ + "." + category.__qualname__,
         getattr(module, "pattern", module), lineno]
        for action, message, category, module, lineno in warnings.filters
    ])
    assert True

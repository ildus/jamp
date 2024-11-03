import pytest


def pytest_configure(config):
    import sys

    sys._called_from_test = True


def pytest_unconfigure(config):
    import sys

    if hasattr(sys, '_called_from_test'):
        delattr(sys, '_called_from_test')


@pytest.fixture(autouse=True)
def run_around_tests():
    from jamp.jam_builtins import Builtins

    Builtins.clear_output()

    yield

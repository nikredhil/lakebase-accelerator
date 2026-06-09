import pytest


def pytest_addoption(parser):
    parser.addoption("--e2e", action="store_true", help="run end-to-end deploy/destroy tests")


def pytest_collection_modifyitems(config, items):
    if not config.getoption("--e2e"):
        skip_e2e = pytest.mark.skip(reason="need --e2e to run")
        for item in items:
            if "e2e" in item.keywords:
                item.add_marker(skip_e2e)

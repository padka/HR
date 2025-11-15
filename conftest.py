import pytest


def pytest_addoption(parser):
    parser.addoption(
        "--redis-url",
        action="store",
        default="redis://localhost:6379/0",
        help="Redis connection URL for notification integration tests",
    )


@pytest.fixture(scope="session")
def redis_url(pytestconfig):
    return pytestconfig.getoption("--redis-url")

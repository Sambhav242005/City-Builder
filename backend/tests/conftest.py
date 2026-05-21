import pytest

from app.main import service


@pytest.fixture(autouse=True)
def reset_service_state():
    service.reset()
    yield
    service.reset()

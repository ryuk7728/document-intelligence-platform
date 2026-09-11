import pytest

from app.core.config import get_settings
from app.core.database import reset_database_state_for_tests


@pytest.fixture(autouse=True)
def reset_cached_state() -> None:
    get_settings.cache_clear()
    reset_database_state_for_tests()
    yield
    get_settings.cache_clear()
    reset_database_state_for_tests()


"""Test fixtures work correctly."""

import sentry_sdk
from scholarag.app import main  # noqa: F401


def test_sentry_disabled():
    """Test that sentry is disabled."""
    with sentry_sdk.isolation_scope() as scope:
        assert scope.get_client().dsn is None

"""Shared fixtures for API tests."""

import pytest

from sec_semantic_search.api.app import app
from sec_semantic_search.api.rate_limit import RateLimitMiddleware


@pytest.fixture(autouse=True)
def _reset_rate_limiter():
    """Reset the rate limiter before each test to prevent cross-test leaks."""
    middleware = app.middleware_stack
    while middleware is not None:
        if isinstance(middleware, RateLimitMiddleware):
            middleware.reset()
            break
        middleware = getattr(middleware, "app", None)

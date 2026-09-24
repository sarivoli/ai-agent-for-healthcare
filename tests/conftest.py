"""
Pytest configuration and shared fixtures for Healthcare Platform tests.
"""

import pytest
from src.db.mock_healthcare_db import db


@pytest.fixture(autouse=True)
def reset_db_state():
    """Automatically reset mock database before and after each test run."""
    db.reset()
    yield
    db.reset()

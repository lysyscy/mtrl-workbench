"""Shared preview seed seam; each server owns its schema before seeding."""
import pytest


@pytest.fixture(scope='module')
def preview_seed():
    return lambda env: None

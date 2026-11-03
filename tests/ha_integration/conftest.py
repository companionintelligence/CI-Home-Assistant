"""Shared fixtures for the Companion Voice integration tests.

These tests run the integration inside Home Assistant with
pytest-homeassistant-custom-component. Run them from the repository root:
  python3 -m pytest tests/ha_integration
"""
import pytest

pytest_plugins = ["pytest_homeassistant_custom_component"]


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    """Let Home Assistant load custom_components/ from this repository."""
    yield

"""Define fixtures for AirNow tests."""

from typing import Any

from custom_components.heatmiserneo.const import DOMAIN
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from homeassistant.core import HomeAssistant


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    """Automatically enable loading of custom integrations in all tests."""
    return


@pytest.fixture(name="config_entry")
def config_entry_fixture(
    hass: HomeAssistant, config: dict[str, Any], options: dict[str, Any]
) -> MockConfigEntry:
    """Mock a config entry for the integration."""
    entry = MockConfigEntry(domain=DOMAIN, data={"host": "test-hub", "port": 1234})
    entry.add_to_hass(hass)
    return entry

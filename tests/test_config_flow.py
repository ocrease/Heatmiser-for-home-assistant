"""Test the heatmiserneo config flow."""

from custom_components.heatmiserneo.const import DOMAIN
import pytest

from homeassistant.config_entries import SOURCE_USER
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType


@pytest.mark.asyncio
async def test_form(
    hass: HomeAssistant,  # , config: dict[str, Any], options: dict[str, Any]
) -> None:
    """Test that the form is served with no input."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] is FlowResultType.MENU
    assert result["step_id"] == "choose_discovery_method"

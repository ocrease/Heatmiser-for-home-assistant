
# SPDX-License-Identifier: Apache-2.0 OR GPL-2.0-only

"""
homeassistant.components.climate.heatmiserneo
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Heatmiser NeoStat control via Heatmiser Neo-hub
"""

import logging
import asyncio
from datetime import timedelta
import async_timeout
 
from homeassistant.components.climate import ClimateEntity
from homeassistant.components.climate.const import (
    ATTR_TARGET_TEMP_HIGH,
    ATTR_TARGET_TEMP_LOW,
    CURRENT_HVAC_COOL,
    CURRENT_HVAC_HEAT,
    CURRENT_HVAC_IDLE,
    HVAC_MODE_COOL,
    HVAC_MODE_FAN_ONLY,
    HVAC_MODE_HEAT,
    HVAC_MODE_HEAT_COOL,
    HVAC_MODE_OFF,
    SUPPORT_TARGET_TEMPERATURE,
    SUPPORT_TARGET_TEMPERATURE_RANGE,
)
from homeassistant.const import ATTR_TEMPERATURE, TEMP_CELSIUS, TEMP_FAHRENHEIT
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)

from neohubapi.neohub import NeoHub, NeoStat, HCMode
from .const import DOMAIN, HUB

_LOGGER = logging.getLogger(__name__)


SUPPORT_FLAGS = 0

# This should be in the neohubapi.neohub enums code
import enum
class AvailableMode(str, enum.Enum):
    HEAT = "heat"
    COOL = "cool"
    VENT = "vent"
    AUTO = "auto"

hvac_mode_mapping = {
    AvailableMode.AUTO: HVAC_MODE_HEAT_COOL, 
    AvailableMode.COOL: HVAC_MODE_COOL, 
    AvailableMode.VENT: HVAC_MODE_FAN_ONLY, 
    AvailableMode.HEAT: HVAC_MODE_HEAT
}

async def async_setup_entry(hass, entry, async_add_entities):

    hub: NeoHub = hass.data[DOMAIN][HUB]

    async def async_update_data():
        """Fetch data from the Hub all at once and make it available for
           all thermostats.
        """
        _LOGGER.info(f"Executing update_data()")
        
        async with async_timeout.timeout(30):
            _, devices_data = await hub.get_live_data()
            system_data = await hub.get_system()
            #_LOGGER.debug(f"system_data: {system_data}")
            
            stats = {stat.name : stat for stat in devices_data['thermostats']}
            _LOGGER.debug(f"stats: {stats}")
            
            return (stats, system_data)

    coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        # Name of the data. For logging purposes.
        name="neostat",
        update_method=async_update_data,
        # Polling interval. Will only be polled if there are subscribers.
        update_interval=timedelta(seconds=30)
    )

    await coordinator.async_config_entry_first_refresh()

    (thermostats, system_data) = coordinator.data

    temperature_unit = system_data.CORF

    entities = [NeoStatEntity(thermostat, temperature_unit, coordinator) for thermostat in thermostats.values()]
    _LOGGER.info(f"Adding Thermostats: {entities}")
    async_add_entities(entities, True)
    
class NeoStatEntity(CoordinatorEntity, ClimateEntity):
    """ Represents a Heatmiser neoStat thermostat. """
    def __init__(self, neostat: NeoStat, unit_of_measurement, coordinator: DataUpdateCoordinator):
        super().__init__(coordinator)
        _LOGGER.debug(f"Creating {neostat}")
        
        self._neostat = neostat
        self._unit_of_measurement = unit_of_measurement
        self._coordinator = coordinator
        self._hvac_modes = []
        if hasattr(neostat, 'standby'):
            self._hvac_modes.append(HVAC_MODE_OFF)
        for mode in neostat.available_modes:
            self._hvac_modes.append(hvac_mode_mapping[mode])
      
    @property
    def data(self):
        """Helper to get the data for the current thermostat. """
        (devices, _) = self._coordinator.data
        return devices[self.name]
        
    @property
    def supported_features(self):
        """Return the list of supported features."""
        hvac_mode = self.hvac_mode
        if hvac_mode == HVAC_MODE_HEAT:
            return SUPPORT_FLAGS | SUPPORT_TARGET_TEMPERATURE
        elif hvac_mode == HVAC_MODE_COOL:
            return SUPPORT_FLAGS | SUPPORT_TARGET_TEMPERATURE
        elif hvac_mode == HVAC_MODE_OFF:
            return SUPPORT_FLAGS
        elif hvac_mode == HVAC_MODE_HEAT_COOL:
            return SUPPORT_FLAGS | SUPPORT_TARGET_TEMPERATURE_RANGE
        elif hvac_mode == HVAC_MODE_FAN_ONLY:
            return SUPPORT_FLAGS | SUPPORT_TARGET_TEMPERATURE
        else:
            _LOGGER.error(f"Unsupported hvac mode: {hvac_mode}")
            return SUPPORT_FLAGS
            
    @property
    def should_poll(self):
        """ Don't poll - we fetch the data from the hub all at once """
        return False

    @property
    def name(self):
        """ Returns the name. """
        return self._neostat.name

    @property
    def unique_id(self):
        """Return a unique ID."""
        return self._neostat.name

    @property
    def temperature_unit(self):
        """Return the unit of measurement."""
        if self._unit_of_measurement == "C":
            return TEMP_CELSIUS
        if self._unit_of_measurement == "F":
            return TEMP_FAHRENHEIT
        return self._unit_of_measurement
        
    @property
    def current_temperature(self):
        """ Returns the current temperature. """
        return float(self.data.temperature)

    @property
    def target_temperature(self):
        """Return the temperature we try to reach."""
        return float(self.data.target_temperature)

    @property
    def target_temperature_high(self):
        """Return the temperature we try to reach."""
        return float(self.data.cool_temp)

    @property
    def target_temperature_low(self):
        """Return the temperature we try to reach."""
        return float(self.data.target_temperature)

    @property
    def device_state_attributes(self):
        """Return the additional state attributes."""
        attributes = {}
        # Exclude attribute if floor temperature is 127 or higher
        # (V1 of the NeoStat reports 127 when no probe is connected, V2 reports 127.5)
        if float(self.data.current_floor_temperature) < 127: 
            attributes['floor_temperature'] = float(self.data.current_floor_temperature)

        return attributes
    
    @property
    def hvac_action(self):
        """Return current activity ie. currently heating, cooling, idle."""
        if self.data.heat_on:
            return CURRENT_HVAC_HEAT
        elif self.data.cool_on:
            return CURRENT_HVAC_COOL
        else:
            return CURRENT_HVAC_IDLE
            
    @property
    def hvac_mode(self):
        """Return current operation mode ie. heat, cool, off."""
        if self.data.standby or not self.data.hc_mode:
            return HVAC_MODE_OFF
            
        hc_mode = HCMode(self.data.hc_mode)
        if hc_mode == HCMode.AUTO and AvailableMode.AUTO in self.data.available_modes:
            return HVAC_MODE_HEAT_COOL
        elif hc_mode == HCMode.VENT and AvailableMode.VENT in self.data.available_modes:
            return HVAC_MODE_FAN_ONLY
        elif hc_mode == HCMode.COOLING and AvailableMode.COOL in self.data.available_modes:
            return HVAC_MODE_COOL
        else:
            return HVAC_MODE_HEAT
            
    @property
    def hvac_modes(self):
        """Return the list of available operation modes."""
        return self._hvac_modes
    
    @property
    def device_info(self):
        return {
            "identifiers": {("heatmiser neoStat", self._neostat.name)},
            "name": self._neostat.name,
            "manufacturer": "Heatmiser",
            "model": "neoStat",
            "suggested_area": self._neostat.name,
        }

    async def async_set_temperature(self, **kwargs):
        """ Set new target temperature. """
        _LOGGER.info(f"{self.name} : Executing set_temperature() with: {kwargs}")
        _LOGGER.debug(f"self.data: {self.data}")
        
        low_temp = kwargs.get(ATTR_TEMPERATURE) or kwargs.get(ATTR_TARGET_TEMP_LOW)
        high_temp = kwargs.get(ATTR_TARGET_TEMP_HIGH)

        set_target_temperature_task = asyncio.create_task(self._neostat.set_target_temperature(low_temp))
        response = await set_target_temperature_task
        if response:
            _LOGGER.info(f"{self.name} : Called set_target_temperature with: {low_temp} (response: {response})")
        
        set_target_cool_temperature_task = asyncio.create_task(self._neostat.set_cool_temp(high_temp))
        response = await set_target_cool_temperature_task
        if response:
            _LOGGER.info(f"{self.name} : Called set_cool_temp with: {high_temp} (response: {response})")

        # The change of target temperature may trigger a change in the current hvac_action
        # so we schedule a refresh to get new data asap.
        await self._coordinator.async_request_refresh()

    async def async_set_hvac_mode(self, hvac_mode):
        """Set hvac mode."""
        _LOGGER.info(f"{self.name} : Executing set_hvac_mode() with: {hvac_mode}")
        _LOGGER.debug(f"self.data: {self.data}")
        
        hc_mode: HCMode = None
        if hvac_mode == HVAC_MODE_HEAT:
            hc_mode = HCMode.HEATING
        elif hvac_mode == HVAC_MODE_COOL:
            hc_mode = HCMode.COOLING
        elif hvac_mode == HVAC_MODE_HEAT_COOL:
            hc_mode = HCMode.AUTO
        elif hvac_mode == HVAC_MODE_FAN_ONLY:
            hc_mode = HCMode.VENT

        # Optimistically update the mode so that the UI feels snappy.
        # The value will be confirmed next time we get new data.
        self.data.hc_mode = hc_mode
        self.async_schedule_update_ha_state(False)

        if hc_mode:
            set_hc_mode_task = asyncio.create_task(self._neostat.set_hc_mode(hc_mode))
            response = await set_hc_mode_task
            _LOGGER.info(f"{self.name} : Called set_hc_mode() with: {hc_mode} (response: {response})")

        frost: bool = True if hvac_mode == HVAC_MODE_OFF else False
        set_frost_task = asyncio.create_task(self._neostat.set_frost(frost))
        response = await set_frost_task
        _LOGGER.info(f"{self.name} : Called set_frost() with: {frost} (response: {response})")
        

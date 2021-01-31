from homeassistant.components.binary_sensor import BinarySensorEntity

from .const import DOMAIN

from homeassistant.components.lock import LockEntity, SUPPORT_OPEN
from homeassistant.helpers import entity_platform, service
import voluptuous as vol
import homeassistant.helpers.config_validation as cv

from aionuki import NukiLock, NukiOpener
from .const import DOMAIN, SERVICE_LOCK_N_GO, ATTR_CODE

from homeassistant.helpers.config_validation import (  # https://github.com/home-assistant/core/blob/dev/homeassistant/components/lock/__init__.py
    make_entity_service_schema,
)

import logging

_LOGGER = logging.getLogger(__name__)


class NukiDoorSensorPlatform(BinarySensorEntity):
    # Should Home Assistant check with the entity for an updated state. If set to False, entity will need to notify Home Assistant of new updates by calling one of the schedule update methods.
    should_poll = False

    # Type of binary sensor.
    device_class = "door"  # On means open, Off means closed.

    def __init__(self, config, obj):
        self._config = config
        self.lockObj = obj
        super().__init__()

    # Generic Properties
    @property
    def available(self):
        """ Indicate if Home Assistant is able to read the state and control the underlying device. """
        return True and self.enabled

    @property
    def device_state_attributes(self):
        """ Extra information to store in the state machine. It needs to be information that further explains the state, it should not be static information like firmware version. """
        return {}

    @property
    def unique_id(self):
        """ A unique identifier for this entity. Needs to be unique within a platform (ie light.hue). Should not be configurable by the user or be changeable. Learn more. """
        return str(self.lockObj.nuki_id) + "_doorsensor"

    @property
    def name(self):
        """ Name of the entity. """
        return "Door Sensor"

    # Binary sensor properties
    @property
    def is_on(self):
        """ If the binary sensor is currently on or off.. """
        return self.lockObj.is_open

    @property
    def device_info(self):
        """Device info for the ups."""
        if not self.unique_id:
            return None
        device_info = {
            "identifiers": {(DOMAIN, self.lockObj.nuki_id)},
            "name": self.name,
            "via_device": self.lockObj.nuki_id,
        }
        return device_info

    # Type of binary sensor.
    device_class = "door"  # On means open, Off means closed.
    # "battery" # On means low, Off means normal.


# Setup
async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the Hue lights from a config entry."""

    platform = hass.data[DOMAIN][config_entry.entry_id]

    deviceList = []
    for lock in platform.devices:
        print("device", lock)
        device = NukiDoorSensorPlatform(config_entry.data, lock)
        platform.registerUpdateCallback(device.async_schedule_update_ha_state)

        deviceList.append(device)

    async_add_entities(deviceList, True)
    print("Started door sensor platform.")

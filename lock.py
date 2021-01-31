from homeassistant.components.lock import LockEntity, SUPPORT_OPEN
from homeassistant.helpers import entity_platform, service
import voluptuous as vol
import homeassistant.helpers.config_validation as cv

from aionuki import NukiLock, NukiOpener
from .const import DOMAIN, SERVICE_LOCK_N_GO, ATTR_CODE

from homeassistant.helpers.config_validation import (  # https://github.com/home-assistant/core/blob/dev/homeassistant/components/lock/__init__.py
    make_entity_service_schema,
)

"""
TODO: read and base on this
https://github.com/home-assistant/core/blob/2fb3be50ab0b806cfc099bc3671ad6c8ee4195e4/homeassistant/components/august/lock.py

"""

# Rename to lockentity
class NukiLockPlatform(LockEntity):
    # Should Home Assistant check with the entity for an updated state. If set to False, entity will need to notify Home Assistant of new updates by calling one of the schedule update methods.
    should_poll = False

    lockObj = None

    def __init__(self, coordinator, config, obj):
        # super().__init__(coordinator)
        self._config = config

        self.coordinator = coordinator
        self.lockObj = obj

    # Generic Properties
    @property
    def device_class(self):
        """ Indicate if Home Assistant is able to read the state and control the underlying device. """
        if isinstance(self.lock, NukiLock):
            return "door"
        elif isinstance(self.lock, NukiOpener):
            return "opener"
        else:
            return None

    @property
    def icon(self):
        """ Indicate if Home Assistant is able to read the state and control the underlying device. """
        return "mdi:doorbell" if (self.device_class == "opener") else None

    @property
    def available(self):
        """ Indicate if Home Assistant is able to read the state and control the underlying device. """
        return True and self.enabled

    # https://developers.home-assistant.io/docs/device_registry_index
    @property
    def device_info(self):
        """Device info."""
        return {
            "identifiers": {(DOMAIN, self.lockObj.nuki_id)},
            "name": self.name,
            "manufacturer": "Nuki",
            "model": "Nuki Smart Lock",
            "default_name": "Nuki Smart Lock",
            "via_device": self.coordinator.bridgeId,
        }
        # if self._firmware:
        #    device_info["sw_version"] = self._firmware

    '''
    @property
    def state_attributes(self):
        """Return the state attributes."""
        state_attr = {}
        for prop, attr in PROP_TO_ATTR.items():
            value = getattr(self, prop)
            if value is not None:
                state_attr[attr] = value
        return state_attr
    '''

    @property
    def state(self):
        """Return the state."""
        locked = self.is_locked
        if locked is None:
            return None
        return "locked" if locked else "unlocked"

    @property
    def supported_features(self):
        """Flag supported features."""
        """
        Have to cast to int. If not, error:
        File "/workspaces/homeassistant_core/homeassistant/components/lock/device_action.py", line 64, in async_get_actions
            if features & (SUPPORT_OPEN):
        TypeError: unsupported operand type(s) for &: 'method' and 'int'
        """
        return int(SUPPORT_OPEN)

    @property
    def device_state_attributes(self):
        """ Extra information to store in the state machine. It needs to be information that further explains the state, it should not be static information like firmware version. """
        return self.lockObj._json

    @property
    def unique_id(self):
        """ A unique identifier for this entity. Needs to be unique within a platform (ie light.hue). Should not be configurable by the user or be changeable. Learn more. """
        return self.lockObj.nuki_id

    @property
    def name(self):
        """ Name of the entity. """
        return self.lockObj.name

    # Lock properties
    @property
    def is_locked(self):
        """ Indication of whether the lock is currently locked. Used to determine state. """
        return self.lockObj.is_locked

    @property
    def is_open(self):
        """ Indication of whether the lock is currently locked. Used to determine state. """
        return self.lockObj.is_open

    @property
    def is_lockngoinprogress(self):
        """ Indication of whether the lock is currently locked. Used to determine state. """
        return self.lockObj.is_lockngo_in_progress

    @property
    def changed_by(self):
        """ Describes what the last change was triggered by. """
        return "callback"

    @property
    def code_format(self):
        """ Regex for code format or None if no code is required. """
        return "[0-9]+"

    def testCode(self, code=None):
        return code == "hello"

    async def async_unlock(self, *args, code=None):
        """Unlock all or specified locks. A code to unlock the lock with may optionally be specified."""
        print("UnlockArgs:", code, *args)
        if self.testCode(code):
            await self.lockObj.unlock()
        else:
            print("wrong code", code)

    async def async_lock(self, code=None):
        """Lock all or specified locks. A code to lock the lock with may optionally be specified."""
        if self.testCode(code):
            await self.lockObj.lock()
        else:
            print("wrong code", code)

    async def async_open(self, code=None):
        """Open (unlatch) all or specified locks. A code to open the lock with may optionally be specified."""
        if self.testCode(code):
            await self.lockObj.unlatch()
        else:
            print("wrong code", code)

    async def async_lockngo(self, code=None):
        if self.testCode(code):
            await self.lockObj.lock_n_go()  # TODO: support for unlatch=False, block=False):
        else:
            print("wrong code", code)

    # lock n go?
    # Sepparate component for opener: no sense to keep the state of an opener. Maybe just turn on when opening and back off after 1s

    def set_option(self, night_sound=None):
        print("Service,", night_sound)


async def async_setup(hass, config_entry):
    LOCK_SERVICE_SCHEMA = make_entity_service_schema(
        {vol.Optional(ATTR_CODE): cv.string}
    )

    platform = hass.data[DOMAIN][config_entry.entry_id]

    platform.async_register_entity_service(
        SERVICE_LOCK_N_GO, LOCK_SERVICE_SCHEMA, "async_lockngo"
    )
    print("async_setup finished")


# Setup
async def async_setup_entry(hass, config_entry, async_add_devices):
    """Set up the Hue lights from a config entry."""

    platform = hass.data[DOMAIN][config_entry.entry_id]

    deviceList = []
    for lock in platform.devices:
        print("device", lock)
        device = NukiLockPlatform(platform, config_entry.data, lock)
        platform.registerUpdateCallback(device.async_schedule_update_ha_state)

        deviceList.append(device)

    platform = entity_platform.current_platform.get()
    print("entityplatform", platform)

    print("Starting with bridge:", platform)
    async_add_devices(deviceList)

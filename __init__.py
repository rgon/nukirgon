"""The nukirgon integration."""
import asyncio
import async_timeout

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import Entity
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers import device_registry as dr

from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from .const import DOMAIN

from aiohttp.web import HTTPException  # Response
from aionuki import NukiBridge
from aionuki.constants import BRIDGE_TYPE_HW

import logging
_LOGGER = logging.getLogger(__name__)


DEFAULT_NAME = "Nuki Bridge"

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Required("host"): str,
                vol.Required("port"): cv.port,
                vol.Required("token"): str,
                vol.Required("serverHost"): str,
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)

CONFIG_SETTINGS = vol.Schema({vol.Required("serverHost"): str})

CALLBACK_URL_BASE = f"nukicallback"

# TODO List the platforms that you want to support.
# For your initial PR, limit it to 1 platform.
PLATFORMS = ["binary_sensor", "lock"]

"""
The nuki API allows POST to an HTTP calback URL with encoded JSON state data.
It does not provide a way to communicate with other methods nor allows setting a header.
Attempts at registering a header-less HTTP endpoint:
    + message to /api/events/eventName
        Doesn't work without token authentication
        trusted_networks doesn't work with the api (avoids requiring the Bearer token Header). shame!
    + registering a signed_path using the ws API with a large enough timeout
        signed_path not working with POST methods (rendered useless)
    + Registering a custom route for the component on the http server router: server:port/components/COMPONENTDOMAIN
        Requires setting url parameters for bridge ID discrimination
        Nuki bridge trims url parameters off, even if '?' is encoded as '%3F'
    + Registering a custom variable route for the component on the http integration's server.
        Working!
        Not elegant
    + Register webhook with components.webhook, like components.push
        Working!
        Elegant!
        Current approach. Note: there is NO documentation on home-assistant.io to explain how to develop this. TODO: contribute to it!
"""


async def webhook_handler(
    hass, webhook_id, request
):  # Not defined in class so webhooks can be reused: when unloading and reloading components.
    """Handle incoming webhook POST with image files."""
    try:
        with async_timeout.timeout(5):
            data = await request.json()
    except (asyncio.TimeoutError, HTTPException) as error:
        _LOGGER.error("Could not get information from POST <%s>", error)
        return

    queryID = webhook_id.replace(
        CALLBACK_URL_BASE + "_", ""
    )

    if queryID and queryID in hass.data[DOMAIN]:
        platform = hass.data[DOMAIN][queryID]
        try:
            await platform.callback_event_handler(data)
        except: # BridgeUninitializedException
            _LOGGER.error(f"Error handling callback for {queryID}.")
        else:
            _LOGGER.debug(f"Lock exists. {queryID}")
        # return Response(text="ok")
    else:
        _LOGGER.error(f"Webhook handled for unknown Nuki Bridge {queryID}")
    # else:
    # return Response(text="err: unknown id", status=406, reason="Unknown id.")


class NukiCoordinator:  # Handles the connection to a single bridge
    _firmwareVersion = 0
    _wifiVersion = 0
    _is_hardware_bridge = None

    def __init__(self, hass, bridge, serverHostname, _id):
        self.hass = hass
        self.id = _id
        self.serverHostname = serverHostname

        self.nukiBridge = bridge

        self.updateCallbacks = []

        self.devices = []
        _LOGGER.debug("Configuring Nuki Platform {_id}")

    async def registerWebhook(self):
        # nukicallback_c8a3dc372a5a52c5d5144880bc597fce
        _LOGGER.debug(f"Registering webhook {CALLBACK_URL_BASE}_{self.id}")
        try:
            self.hass.components.webhook.async_register(
                DOMAIN,
                self.name,
                CALLBACK_URL_BASE + f"_{self.id}",
                webhook_handler,
            )
        except ValueError:
            _LOGGER.error(f"In {self.name}, webhook {CALLBACK_URL_BASE}_{self.id} already used")

    def registerUpdateCallback(self, callback): # Called by platforms
        self.updateCallbacks.append(callback)

    async def callUpdateCallbacks(self):
        for callback in self.updateCallbacks:
            try:
                callback()
            except: 
                _LOGGER.error("Couldn't call an update notifier callback.")
    
    @property
    def callback_event_url(self):
        ''' URL push state update wehbook url'''
        return f"http://{self.serverHostname}:{self.hass.config.api.port}/api/webhook/{CALLBACK_URL_BASE}_{self.id}"

    async def callback_event_handler(self, event): # Throws error
        ''' Called from the webhook callback handler '''
        _LOGGER.debug(f"Callback from nuki bridge event: {event}")
        await self.nukiBridge.interpret_callback(event)

    # --- Interaction with the lock
    async def clearBridgeCallbacks(self):
        ''' Clear pre-existing callbacks '''
        try:
            await self.nukiBridge.callback_remove_all()
        except:
            _LOGGER.error("Couldn't remove bridge callbacks.")

    async def installBridgeCallback(self):
        ''' Add this callback to the bridge '''
        try:
            await self.nukiBridge.callback_add(self.callback_event_url)
        except:
            _LOGGER.error("Couldn't remove bridge callbacks.")

    async def removeCallback(self):
        ''' Remove this callback from the bridge '''
        try:
            return await self.nukiBridge.callback_remove_by_url(self.callback_event_url)
        except:
            _LOGGER.error("Couldn't remove this callback from the bridge.")

    async def cleanup(self):
        await self.removeCallback()
        await self.nukiBridge.__aexit__(None, None, None)
        _LOGGER.debug("Cleaned up bridge object.")

    async def connect(self):
        await self.nukiBridge.connect()
        bridgeInfo = await self.nukiBridge.info()
        self._firmwareVersion = bridgeInfo.get("firmwareVersion")
        self._wifiVersion = bridgeInfo.get("wifiFirmwareVersion")
        self._is_hardware_bridge = bridgeInfo.get("bridgeType") == BRIDGE_TYPE_HW

        await self.installBridgeCallback()
        await self.getDevices()


    async def getDevices(self):
        self.devices = await self.nukiBridge.getDevices()
        return self.devices

    # async def async_update(self): # This method should fetch the latest state from the device and store it in an instance variable for the properties to return it.

    @property
    def bridgeId(self):
        return self.nukiBridge.bridgeId

    @property
    def name(self):
        return "Nuki Bridge"

    @property
    def model(self):
        return f"Nuki {'Hardware' if self._is_hardware_bridge else 'Software'} Bridge"

    @property
    def swVersion(self):
        return f"firmware {self._firmwareVersion} wifi {self._wifiVersion}"


async def async_setup(hass: HomeAssistant, config: dict):
    """Set up the nukirgon component."""
    _LOGGER.debug("Platform setup.")

    hass.data[DOMAIN] = {}
    return True


async def async_setup_entry(hass, configEntry):
    """Set up nukirgon from a config entry."""

    bridge = NukiBridge(
        configEntry.data.get("hostname"),
        configEntry.data.get("port"),
        token=configEntry.data.get("token"),
    )

    coordinator = NukiCoordinator(
        hass, bridge, configEntry.data.get("serverHostname"), configEntry.entry_id
    )

    await coordinator.registerWebhook() # tries

    hass.data[DOMAIN][configEntry.entry_id] = coordinator

    try:
        await coordinator.connect()
    except Exception as ex:
        _LOGGER.error(f"Unable to connect to bridge: {str(ex)}")
        # Set available false
    else:
        _LOGGER.debug("Set up platform coordinator asynchronously.")
    
    # Use `hass.async_create_task` to avoid a circular dependency between the platform and the component
    async def setup_platforms():
        for platform in PLATFORMS:
            await hass.config_entries.async_forward_entry_setup(configEntry, platform)

    hass.async_create_task(setup_platforms())

    device_registry = await dr.async_get_registry(hass)

    device_registry.async_get_or_create(
        config_entry_id=configEntry.entry_id,
        identifiers={(DOMAIN, coordinator.nukiBridge.bridgeId)},
        manufacturer="Nuki",
        name=coordinator.name,
        model=coordinator.model,
        sw_version=coordinator.swVersion,
    )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Unload a config entry."""
    unload_ok = all(
        await asyncio.gather(
            *[
                hass.config_entries.async_forward_entry_unload(entry, component)
                for component in PLATFORMS
            ]
        )
    )

    if unload_ok:
        try:
            await hass.data[DOMAIN][entry.entry_id].cleanup()
        except:
            _LOGGER.error("Error unloading Nuki Platform.")
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok


# On unload platform:
# callbackPointer = None

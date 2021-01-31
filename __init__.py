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
    )  # queryID = request.match_info["id"]
    print("handling hook", webhook_id, queryID)

    print("request id:", id)
    if queryID and queryID in hass.data[DOMAIN]:
        platform = hass.data[DOMAIN][queryID]
        await platform.callback_event_handler(data)
        print("lock exists", queryID)
        # return Response(text="ok")
    else:
        _LOGGER.error(f"Webhook handled for unknown Nuki Bridge {queryID}")
    # else:
    # return Response(text="err: unknown id", status=406, reason="Unknown id.")


class NukiCoordinator:  # Handles the connection to a single bridge
    _firmwareVersion = 0
    _wifiVersion = 0
    _is_hardware_bridge = None

    def __init__(self, hass, bridge, serverHostname, id):
        self.hass = hass
        self.id = id
        self.remove_event_listener = None

        self.serverHostname = serverHostname

        self.nukiBridge = bridge

        self.updateCallbacks = []

        self.devices = []
        print("Configuring Nuki Platform", id)

    async def registerWebhook(self):
        # nukicallback_c8a3dc372a5a52c5d5144880bc597fce
        print(
            "reginstering webhook",
            CALLBACK_URL_BASE + f"_{self.id}",
        )
        try:
            self.hass.components.webhook.async_register(
                DOMAIN,
                self.name,
                CALLBACK_URL_BASE + f"_{self.id}",
                webhook_handler,
            )
        except ValueError:
            _LOGGER.error(
                "In <%s>, webhook_id <%s> already used", self.name, self.webhook_id
            )

    @property
    def callback_event_url(self):
        """Return url for push state updates (nuki callback sent to the event bus)."""
        # return f"http://{self.serverHostname}:{self.hass.config.api.port}{CALLBACK_URL_BASE}/{self.id}"
        return f"http://{self.serverHostname}:{self.hass.config.api.port}/api/webhook/{CALLBACK_URL_BASE}_{self.id}"

    async def callback_event_handler(self, event):
        _LOGGER.debug("Callback from nuki bridge event: %s", event)
        print(f"Answer is: {event}")
        await self.nukiBridge.interpret_callback(event)

        await self.callUpdateCallbacks()
        print("Finally:", (await self.nukiBridge.locks)[0].state_name)

    def registerUpdateCallback(self, callback):
        self.updateCallbacks.append(callback)

    async def callUpdateCallbacks(self):
        print("calling back")
        for callback in self.updateCallbacks:
            callback()

    # --- Interaction with the lock
    async def clearBridgeCallbacks(self):
        # Clear pre-existing callbacks
        for i in range(0, 3):
            await self.nukiBridge.callback_remove(i)

    async def installBridgeCallback(self):
        await self.nukiBridge.callback_add(self.callback_event_url)

    async def removeCallback(self):
        return await self.nukiBridge.callback_remove_by_url(self.callback_event_url)

    async def cleanup(self):
        await self.removeCallback()
        await self.nukiBridge.__aexit__(None, None, None)
        print("cleaned up")

    async def connect(self):
        await self.nukiBridge.connect()
        bridgeInfo = await self.nukiBridge.info()
        self._firmwareVersion = bridgeInfo.get("firmwareVersion")
        self._wifiVersion = bridgeInfo.get("wifiFirmwareVersion")
        self._is_hardware_bridge = bridgeInfo.get("bridgeType") == BRIDGE_TYPE_HW

    async def getDevices(self):
        # TODO
        print("TODO: unimplemented")
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

    # try to connect to the lock, add the callback etc
    # raise PlatformNotReady if unable to connect during platform setup (

    # Handles expiration of auth credentials. Refresh if possible or print correct error and fail setup. If based on a config entry, should trigger a new config entry flow to re-authorize. (docs)
    # Handles device/service unavailable. Log a warning once when unavailable, log once when reconnected.

    # TODO: move to config flow

    # except Exception as ex:
    # _LOGGER.error("Unable to connect to wirelesstag.net service: %s", str(ex))
    # hass.components.persistent_notification.create(
    #    f"Error: {ex}<br />Please restart hass after fixing this.",
    #    title=NOTIFICATION_TITLE,
    #    notification_id=NOTIFICATION_ID,
    # )
    # return False

    # await platform.removeCallback()

    print("Platform setup")

    hass.data[DOMAIN] = {}
    return True


async def async_setup_entry(hass, configEntry):
    """Set up nukirgon from a config entry."""
    # TODO Store an API object for your platforms to access

    bridge = NukiBridge(
        configEntry.data.get("hostname"),
        configEntry.data.get("port"),
        token=configEntry.data.get("token"),
    )

    coordinator = NukiCoordinator(
        hass, bridge, configEntry.data.get("serverHostname"), configEntry.entry_id
    )
    await coordinator.registerWebhook()

    hass.data[DOMAIN][configEntry.entry_id] = coordinator

    try:
        await coordinator.connect()
    except Exception as ex:
        _LOGGER.error("Unable to connect: %s", str(ex))
    else:
        await coordinator.installBridgeCallback()
        print("Set up asynchronously", await coordinator.nukiBridge.callback_list())

    # TODO: Get devices here
    await coordinator.getDevices()

    # Use `hass.async_create_task` to avoid a circular dependency between the platform and the component
    async def setup_platforms():
        for platform in PLATFORMS:
            print(
                "Platform setup",
                await hass.config_entries.async_forward_entry_setup(
                    configEntry, platform
                ),
            )

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
        await hass.data[DOMAIN][entry.entry_id].cleanup()
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok


# On unload platform:
# callbackPointer = None

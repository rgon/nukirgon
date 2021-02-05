"""Config flow for nukirgon integration."""
import logging
import asyncio

import voluptuous as vol

from homeassistant import config_entries, core, exceptions, util
import homeassistant.helpers.config_validation as cv

from .const import DOMAIN  # pylint:disable=unused-import

from aionuki import NukiBridge
from aionuki.exceptions import InvalidCredentialsException

_LOGGER = logging.getLogger(__name__)

# This data entry flow crap is a mess. I cannot get a hold of it.


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for nukirgon."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_PUSH

    config_host = None
    config_port = None
    config_token = None
    server_host = None

    task_autodiscover = None
    task_interactivetoken = None
    task_testconfig = None
    token_error = False

    thisBridge = None

    async def autodiscover(self):
        try:
            # TODO: testing
            bridges = await NukiBridge.discover()
            self.thisBridge = bridges[0]()

            self.config_host = self.thisBridge.hostname
            self.config_port = self.thisBridge.port
        except:
            return self.async_abort(reason="communtication_error")

    async def getTokenInteractive(self):
        _LOGGER.debug("Authenticating interactively.")
        try:
            self.config_token = await self.thisBridge.auth()
            await self.testConfig()
            _LOGGER.debug("Successfully ested config.")
            # await asyncio.sleep(2)
        except:
            return self.async_abort(
                reason="communtication_error"
            )  # Only comm error, wrong token makes no sense.

    async def testConfig(self):
        try:
            await self.thisBridge.connect(self.config_token)
        except Exception as e:
            if isinstance(e, InvalidCredentialsException):
                self.token_error = True
            else:
                return self.async_abort(reason="communtication_error")
        else:
            self.token_error = False

    async def _async_do_task(self, task):
        await task  # A task that take some time to complete.

        # To avoid a potential deadlock we create a new task that continues the flow.
        self.hass.async_create_task(
            self.hass.config_entries.flow.async_configure(flow_id=self.flow_id)
        )

    async def async_step_user(self, user_input=None):
        """Step 1."""

        if user_input is None:  # first
            return self.async_show_form(
                step_id="user",
                data_schema=vol.Schema(
                    {vol.Optional("autodiscover", default=True): bool}
                ),
            )
        else:
            if user_input["autodiscover"] == True:
                self.task_autodiscover = self.hass.async_create_task(
                    self._async_do_task(self.autodiscover())
                )
                return self.async_show_progress(
                    step_id="read_ip",
                    progress_action="task_autodiscover",
                    # progress_action="autodiscover",
                )
            else:
                return self.async_show_form(
                    step_id="read_ip",
                    data_schema=vol.Schema(
                        {vol.Required("host"): str, vol.Required("port"): cv.port}
                    ),
                    errors={"base": "autodiscover_fail"},
                )

    async def async_step_read_ip(self, user_input=None):
        if user_input is not None:  # First entry
            if user_input["host"] != "" and user_input["port"] != "":
                self.config_host = user_input["host"]
                self.config_port = user_input["port"]

                self.thisBridge = NukiBridge(self.config_host, self.config_port)

                res = await self.async_set_unique_id(self.thisBridge.bridgeId)
                if res != None:
                    return self.async_abort(reason="already_configured")
                else:
                    return self.async_show_form(
                        step_id="token",
                        data_schema=vol.Schema(
                            {
                                vol.Optional("token"): str,
                                vol.Optional("interactiveauth"): bool,
                            }
                        ),
                        description_placeholders={
                            "bridgeInfo": f"{self.config_host}:{self.config_port}"
                        },
                    )
            else:
                return self.async_show_form(
                    step_id="read_ip",
                    data_schema=vol.Schema(
                        {vol.Required("host"): str, vol.Required("port"): cv.port}
                    ),
                    errors={"base": "data_format_error"},
                )
                # error, show this form again
        else:  # On progress done.
            if self.config_host:  # Successful
                res = await self.async_set_unique_id(self.thisBridge.bridgeId)
                if res == None:
                    # show configuration with rest
                    return self.async_show_progress_done(
                        next_step_id="autodiscover_progressdone_mezzanine_ok"
                    )
                else:  # Already configured
                    return self.async_show_progress_done(
                        next_step_id="autodiscover_progressdone_mezzanine_alreadyconfigured"
                    )
            else:  # Fails
                return self.async_show_progress_done(
                    next_step_id="autodiscover_progressdone_mezzanine_err"
                )

    async def async_step_autodiscover_progressdone_mezzanine_ok(self, user_input=None):
        return self.async_show_form(
            step_id="token",
            data_schema=vol.Schema(
                {vol.Optional("token"): str, vol.Required("interactiveauth"): bool}
            ),
            description_placeholders={
                "bridgeInfo": f"{self.config_host}:{self.config_port}"
            },
        )

    async def async_step_autodiscover_progressdone_mezzanine_alreadyconfigured(
        self, user_input=None
    ):
        return self.async_show_form(
            step_id="read_ip",
            data_schema=vol.Schema(
                {vol.Required("host"): str, vol.Required("port"): cv.port}
            ),
            errors={"base": "already_configured_autodiscover"},
        )

    async def async_step_autodiscover_progressdone_mezzanine_err(self, user_input=None):
        return self.async_show_form(
            step_id="read_ip",
            data_schema=vol.Schema(
                {vol.Required("host"): str, vol.Required("port"): cv.port}
            ),
            errors={"base": "autodiscover_fail"},
        )

    async def async_step_token(self, user_input=None):
        if (
            "interactiveauth" in user_input and user_input["interactiveauth"] == True
        ):  # step 2 interactive
            self.task_interactivetoken = self.hass.async_create_task(
                self._async_do_task(self.getTokenInteractive())
            )

            return self.async_show_progress(
                step_id="get_token_interactive",
                # progress_action="getTokenInteractive",
                progress_action="task_interactivetoken",
            )
        else:  # manual: test config
            self.config_token = user_input["token"]

            self.task_testconfig = self.hass.async_create_task(
                self._async_do_task(self.testConfig())
            )

            return self.async_show_progress(
                step_id="get_token_manual",
                progress_action="task_testconfig",
                # progress_action="testConfig",
            )

    async def async_step_get_token_interactive(self, user_input=None):
        if self.config_token:
            # continue, ok
            return self.async_show_progress_done(
                next_step_id="end_progressdone_mezzanine"
            )
        else:
            return self.async_show_progress_done(
                next_step_id="interactiveauth_progressdone_mezzanine_err"
            )

    async def async_step_interactiveauth_progressdone_mezzanine_err(
        self, user_input=None
    ):
        return self.async_show_form(
            step_id="token",
            data_schema=vol.Schema({vol.Required("token"): str}),
            errors={"base": "interactiveauth_fail"},
            description_placeholders={
                "bridgeInfo": f"{self.config_host}:{self.config_port}"
            },
        )

    async def async_step_get_token_manual(self, user_input=None):
        if self.token_error:
            return self.async_show_progress_done(
                next_step_id="manualtoken_progressdone_mezzanine_err"
            )
        else:
            return self.async_show_progress_done(
                next_step_id="end_progressdone_mezzanine"
            )

    async def async_step_manualtoken_progressdone_mezzanine_err(self, user_input=None):
        return self.async_show_form(
            step_id="token",
            data_schema=vol.Schema({vol.Required("token"): str}),
            errors={"base": "token_error"},
            description_placeholders={
                "bridgeInfo": f"{self.config_host}:{self.config_port}"
            },
        )

    async def async_step_end_progressdone_mezzanine(self, user_input=None):
        autoDiscoveredIP = util.get_local_ip()

        return self.async_show_form(
            step_id="pre_end",
            data_schema=vol.Schema(
                {
                    vol.Required("serverhost", default=autoDiscoveredIP): str,
                    vol.Optional("clearcallbacks", default=True): bool,
                }
            ),
        )

    async def async_step_pre_end(self, user_input=None):
        if user_input is not None:
            if user_input["clearcallbacks"]:
                await self.thisBridge.callback_remove_all()
                _LOGGER.debug("Clearing callbacks.")

            self.server_host = user_input["serverhost"]
            # else: raise error

        _LOGGER.info(f"server_hostname {self.server_host}")

        return self.async_create_entry(
            title=self.thisBridge.bridgeId,
            data={
                "hostname": self.config_host,
                "port": self.config_port,
                "server_hostname": self.server_host,
                "token": self.config_token,
            },
        )

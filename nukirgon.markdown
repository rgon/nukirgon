---
title: Nuki
description: Nuki Smart Lock and opener integration, with support for door sensor etc.
ha_category:
  - Lock
ha_release: 0.119.0
ha_iot_class: Local Push
ha_codeowners:
  - "@rgon"
ha_domain: nukirgon
---

The `nukirgon` platform allows you to control [Nuki Smart Locks](https://nuki.io/en/smart-lock/) via a [physical bridge](https://nuki.io/en/bridge/).

To add a Nuki bridge to your installation, you need to enable developer mode on your bridge and define a port and an access token. This can be achieved using the [Android app](https://play.google.com/store/apps/details?id=io.nuki) or [iPhone app](https://apps.apple.com/app/nuki-smart-lock/id1044998081). Go to manage my devices, and select the bridge. Within the bridge configuration turn on the HTTP API and check the details in the screen. Please note that the API token should be 6-20 characters long, even though the app allows you to set a longer one.

Then configure the integration with one of the following methods:

## Configuration

### Using the config flow (recommended):

Add the integration in the Homeassistant `Configuration` -> `Integrations` -> + `Add Integration`. Follow the steps that appear in the screen.

This integration allows a semi-automated setup that requires no manual entry of data. The bridge can be automatically discovered using the `nuki.io` servers or have its IP and port manually entered. The token, as well, can be input manually or interactively: push the bridge's button once when the guide prompts you to and it will retrieve it automatically.

Be sure to input your server's local (LAN) IP address, since this is required for the push functionality to work. We cannot properly auto-discover it if HA is running inside a docker container, sorry for the inconvenience.

### Using the `configuration.yaml` file:

```yaml
# Example configuration.yaml entry
nukirgon:
  host: 192.168.2.2
  port: 8080
  token: fe2345ef
  serverHost: 192.168.10.2
```

{% configuration %}
host:
description: The IP or hostname of the Nuki bridge.
required: true
type: string
port:
description: The port on which the Nuki bridge is listening on.
required: true
type: integer
token:
description: The token that was defined when setting up the bridge.
required: true
type: string
serverHost:
description: The IP or hostname of the HomeAssistant server (as accessible by the bridge's network).
required: true
type: string
{% endconfiguration %}

### Post-configuration checklist:

Make sure your HomeAssistant instance (port 8123) is accessible from the Nuki Bridge's network. Enable LAN access to that port if using a firewall (ufw allow 8123), and allow access to that port from the bridge's network in your router if the it's running on an isolated LAN.

### Notes:

TODO: test cleanup (problem: cannot del_route in aiohttp.router, so dangling pointer to function).

## Services

### Service `lock_n_go`

This will first unlock, wait a few seconds (20 by default) then re-lock. The wait period can be customized through the app.
See the [Nuki Website](https://nuki.io/en/support/smart-lock/sl-features/locking-with-the-smart-lock/) for more details about this feature.

| Service data attribute | Optional | Description                                                      |
| ---------------------- | -------- | ---------------------------------------------------------------- |
| `entity_id`            | yes      | String or list of strings that point at `entity_id`s Nuki Locks. |
| `unlatch`              | yes      | Boolean - Whether to unlatch the door when first opening it.     |

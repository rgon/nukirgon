# async Nuki HomeAssistant Integration
This is Alpha software far from being in an usable state.

### REQUIRES: 
+ [aionuki](https://github.com/rgon/aionuki)
+ Nuki Bridge
+ Nuki lock
+ Home Assistant
+ Server in a network which the bridge can access (firewall allowed from bridge to server)

### SELLING POINTS / WHAT WORKS / WHY I MADE THIS:
+ Local Push
+ Door sensor integration
+ Events (Triggers and actions) are working
+ Completely automatic setup (no need to enter a single digit)
+ Config flow
+ Fully Async (integratior + library + http comms)
+ ~Lock/unlock protected by pin code, limiting which users can access~ (how to use?)
+ Multiple bridge support (for large homes with multiple entrances)

### TODO:
+ Figure out how to pass the code in an automation yaml
+ How to integrate and show service in the device
+ PR for pin input in lock
+ Lock 'n' go entity service: how to integrate without spinning another lock (platform) ?
+ Proper battery sensors etc
+ Connectivity
+ Opener integration
+ Parametrized Opener/Lock creation and platform setup
+ Remove all debug print()s
+ Set password in config flow/configuration.yaml
+ Door state not changing on lock/unlock
+ Notification for the UI when the code is wrong.
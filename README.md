# Felicita Arc Scale Integration for Home Assistant

> [!CAUTION]
> This integration is included with Home Assistant since version 2024.12. Switch to the the built-in integration instead.

[![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=zweckj&repository=felicita&category=integration)

This is a custom component to integrate Felicita Arc scales in Home Assistant.

## Features
- Weight measurement
- Battery level
- Timer control
- Tare function
- Unit toggle
- Precision toggle

## Installation

1. Install via HACS by adding this repository as a custom repository
2. Restart Home Assistant
3. Add the integration via the UI
4. Select your Felicita Arc scale from the discovered devices

## Supported Devices
- Felicita Arc

## Credits
- Based on the original Acaia integration by @zweckj

## Setup
This integration requires a Bluetooth connection from HA to your scale. You can use an ESP Home [Bluetooth Proxy](https://esphome.github.io/bluetooth-proxies/) if you're not close enough.

After you added the integration to your HA, when you turn your scale on, it should be discovered automatically from Home Assistant.

This integration is tested so far with a Lunar (2021). If you have a different scale, please feel free to test and report back. 

For scale versions before 2021, uncheck the `is_new_style_scale` setting during setup.

# Felicita Arc Scale Integration for Home Assistant


This is a custom component to integrate Felicita Arc scales in Home Assistant.

## Features
- Weight measurement
- Battery level
- Timer control
- Tare function
- Unit toggle

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

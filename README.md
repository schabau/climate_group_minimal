# Home Assistant Climate Group Minimal

A lightweight, no-frills helper tool for Climate Groups in Home Assistant. Specifically designed to group multiple radiator thermostats and calculate their average temperature. Nothing more, nothing less.

## Installation

### Option 1: HACS (Custom Repository)
* Open HACS in Home Assistant.
* Click on the 3 dots in the top right corner and select **Custom repositories**.
* Paste the URL of this GitHub Repository. `https://github.com/schabau/climate_group_minimal`
* Select **Integration** as the Category and click **Add**.
* Search for "Climate Group Minimal", click **Download**, and restart Home Assistant.

### Option 2: Manual Installation
* Download the latest release from GitHub.
* Copy the `climate_group_minimal` folder into your `custom_components` directory.
* Restart Home Assistant.

## Configuration

Climate Group Minimal is configured directly via the Home Assistant user interface, just like creating a "Helper". You can create a new helper (group) via the UI under Settings -> Devices & Services -> Helper (tab) and select "Climate Group Minimal".

## Credits

This project is a lightweight derivative based on [Climate Group Helper for Home Assistant](https://github.com/bjrnptrsn/climate_group_helper). Special thanks to the original author for the foundation!
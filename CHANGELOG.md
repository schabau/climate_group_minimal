# Changelog

## 0.2.0 - 11/2026

*   Replaced deprecated attributes for compatibility with future Home Assistant releases (2027.11+).
*   Added Home Assistant Marketplace (2026.11+) installation instructions.

## 0.1.0 - 08/2026

First version of Climate Group Minimal for Home Assistant, forked from Climate Group Helper.

## Features

*   Group Climate Entities: Any number of climate entities can be combined into a group.
*   Synchronized Control: A change in target temperature or heating mode is synchronized with all group members.
*   Average temperature: The average temperature of the individual members of the group is used as the current temperature.
*   Variable averaging: You can choose between mean, median, minimum, or maximum for calculating the target temperature.
*   Temperature rounding: You can choose between the exact temperature, rounded to half a degree (0.5°) or a whole degree (1°).
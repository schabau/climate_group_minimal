"""Group several climate devices into one climate device."""
from __future__ import annotations

import logging
from statistics import mean, median
from typing import Any

from homeassistant.components.climate import (
    ATTR_CURRENT_TEMPERATURE,
    ATTR_HVAC_ACTION,
    ATTR_HVAC_MODE,
    ATTR_HVAC_MODES,
    ATTR_MAX_TEMP,
    ATTR_MIN_TEMP,
    ATTR_TARGET_TEMP_HIGH,
    ATTR_TARGET_TEMP_LOW,
    ATTR_TARGET_TEMP_STEP,
    DEFAULT_MAX_TEMP,
    DEFAULT_MIN_TEMP,
    DOMAIN as CLIMATE_DOMAIN,
    SERVICE_SET_HVAC_MODE,
    SERVICE_SET_TEMPERATURE,
    ClimateEntity,
    ClimateEntityFeature,
    HVACAction,
    HVACMode,
)
from homeassistant.components.group.entity import GroupEntity
from homeassistant.components.group.util import (
    find_state_attributes,
    reduce_attribute,
    states_equal,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_ENTITY_ID,
    ATTR_SUPPORTED_FEATURES,
    ATTR_TEMPERATURE,
    CONF_ENTITIES,
    CONF_NAME,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    ATTR_ASSUMED_STATE,
    ATTR_CURRENT_HVAC_MODES,
    ATTR_GROUP_IN_SYNC,
    ATTR_LAST_ACTIVE_HVAC_MODE,
    ATTR_TARGET_HVAC_MODE,
    CONF_AVERAGE_OPTION,
    CONF_HVAC_MODE_STRATEGY,
    CONF_ROUND_OPTION,
    HVAC_MODE_STRATEGY_AUTO,
    HVAC_MODE_STRATEGY_NORMAL,
    HVAC_MODE_STRATEGY_OFF_PRIORITY,
    AverageOption,
    RoundOption,
)

CALC_TYPES = {
    AverageOption.MIN: min,
    AverageOption.MAX: max,
    AverageOption.MEAN: mean,
    AverageOption.MEDIAN: median,
}

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 0

DEFAULT_SUPPORTED_FEATURES = ClimateEntityFeature.TURN_OFF | ClimateEntityFeature.TURN_ON


def mean_round(value: float | None, round_option: str = RoundOption.NONE) -> float | None:
    """Round the decimal part of a float to a fractional value with a certain precision."""
    if value is None:
        return None

    if round_option == RoundOption.HALF:
        return round(value * 2) / 2
    if round_option == RoundOption.INTEGER:
        return round(value)
    return value


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Initialize Climate Group Minimal config entry."""
    config = {**config_entry.data, **config_entry.options}

    registry = er.async_get(hass)
    entities = er.async_validate_entity_ids(registry, config[CONF_ENTITIES])

    hvac_mode_strategy = config.get(CONF_HVAC_MODE_STRATEGY, HVAC_MODE_STRATEGY_NORMAL)

    async_add_entities(
        [
            ClimateGroup(
                unique_id=config_entry.unique_id,
                name=config.get(CONF_NAME, config_entry.title),
                entity_ids=entities,
                average_option=config.get(CONF_AVERAGE_OPTION, AverageOption.MEAN),
                round_option=config.get(CONF_ROUND_OPTION, RoundOption.NONE),
                hvac_mode_strategy=hvac_mode_strategy,
            )
        ]
    )


class ClimateGroup(GroupEntity, ClimateEntity):
    """Representation of a Climate Group Minimal."""

    def __init__(
        self,
        unique_id: str | None,
        name: str,
        entity_ids: list[str],
        average_option: str,
        round_option: str,
        hvac_mode_strategy: str,
    ) -> None:
        """Initialize a Climate Group Minimal."""
        self._attr_unique_id = unique_id
        self._attr_name = name
        self._entity_ids = entity_ids
        self._average_calc = CALC_TYPES[average_option]
        self._round_option = round_option
        self._hvac_mode_strategy = hvac_mode_strategy

        self._target_hvac_mode = None
        self._last_active_hvac_mode = None

        self._attr_supported_features = DEFAULT_SUPPORTED_FEATURES
        self._attr_temperature_unit = UnitOfTemperature.CELSIUS

        self._attr_available = False
        self._attr_assumed_state = True
        self._attr_extra_state_attributes = {}

        self._attr_current_temperature = None
        self._attr_target_temperature = None
        self._attr_target_temperature_step = None
        self._attr_target_temperature_low = None
        self._attr_target_temperature_high = None
        self._attr_min_temp = None
        self._attr_max_temp = None

        self._attr_hvac_modes = [HVACMode.OFF]
        self._attr_hvac_mode = None
        self._attr_hvac_action = None

    @callback
    def async_update_group_state(self) -> None:
        """Query all members and determine the Climate Group Minimal state."""
        self._attr_extra_state_attributes = {
            CONF_AVERAGE_OPTION: self._average_calc.__name__,
            CONF_ROUND_OPTION: self._round_option,
            CONF_HVAC_MODE_STRATEGY: self._hvac_mode_strategy,
        }

        all_states = [
            state
            for entity_id in self._entity_ids
            if (state := self.hass.states.get(entity_id)) is not None
        ]

        states = [
            state
            for state in all_states
            if state.state not in (STATE_UNAVAILABLE, STATE_UNKNOWN)
        ]

        if states:
            available_hvac_modes = list(find_state_attributes(states, ATTR_HVAC_MODES))
            self._attr_hvac_modes = (
                list(set().union(*available_hvac_modes))
                if available_hvac_modes
                else [HVACMode.OFF]
            )

            current_hvac_modes = sorted([state.state for state in states])
            active_hvac_modes = [mode for mode in current_hvac_modes if mode != HVACMode.OFF]

            most_common_active_hvac_mode = (
                max(active_hvac_modes, key=active_hvac_modes.count)
                if active_hvac_modes
                else None
            )

            strategy = self._hvac_mode_strategy
            if strategy == HVAC_MODE_STRATEGY_AUTO:
                if self._target_hvac_mode in (HVACMode.OFF, None):
                    strategy = HVAC_MODE_STRATEGY_NORMAL
                else:
                    strategy = HVAC_MODE_STRATEGY_OFF_PRIORITY

            if strategy == HVAC_MODE_STRATEGY_NORMAL:
                if (
                    all(mode == HVACMode.OFF for mode in current_hvac_modes)
                    if current_hvac_modes
                    else False
                ):
                    self._attr_hvac_mode = HVACMode.OFF
                else:
                    self._attr_hvac_mode = most_common_active_hvac_mode
            elif strategy == HVAC_MODE_STRATEGY_OFF_PRIORITY:
                if HVACMode.OFF in current_hvac_modes:
                    self._attr_hvac_mode = HVACMode.OFF
                else:
                    self._attr_hvac_mode = most_common_active_hvac_mode

            if (self._attr_hvac_mode != HVACMode.OFF) and (
                self._attr_hvac_mode != self._last_active_hvac_mode
            ):
                self._last_active_hvac_mode = self._attr_hvac_mode

            self._attr_available = True
            self._attr_assumed_state = not states_equal(states)
            self._attr_temperature_unit = self.hass.config.units.temperature_unit

            # Ist-Temperatur = Mittelwert aller Thermostate
            self._attr_current_temperature = reduce_attribute(
                states, ATTR_CURRENT_TEMPERATURE, reduce=lambda *data: mean(data)
            )

            # Soll-Temperatur = Gemittelter Wert nach eingestellter Option
            self._attr_target_temperature = reduce_attribute(
                states, ATTR_TEMPERATURE, reduce=lambda *data: self._average_calc(data)
            )
            if self._attr_target_temperature is not None:
                self._attr_target_temperature = mean_round(
                    self._attr_target_temperature, self._round_option
                )

            self._attr_target_temperature_low = reduce_attribute(
                states, ATTR_TARGET_TEMP_LOW, reduce=lambda *data: self._average_calc(data)
            )
            if self._attr_target_temperature_low is not None:
                self._attr_target_temperature_low = mean_round(
                    self._attr_target_temperature_low, self._round_option
                )

            self._attr_target_temperature_high = reduce_attribute(
                states,
                ATTR_TARGET_TEMP_HIGH,
                reduce=lambda *data: self._average_calc(data),
            )
            if self._attr_target_temperature_high is not None:
                self._attr_target_temperature_high = mean_round(
                    self._attr_target_temperature_high, self._round_option
                )

            self._attr_target_temperature_step = reduce_attribute(
                states, ATTR_TARGET_TEMP_STEP, reduce=max
            )
            self._attr_min_temp = reduce_attribute(
                states, ATTR_MIN_TEMP, reduce=max, default=DEFAULT_MIN_TEMP
            )
            self._attr_max_temp = reduce_attribute(
                states, ATTR_MAX_TEMP, reduce=min, default=DEFAULT_MAX_TEMP
            )

            current_hvac_actions = list(find_state_attributes(states, ATTR_HVAC_ACTION))
            if current_hvac_actions:
                active_hvac_actions = [
                    action for action in current_hvac_actions if action != HVACAction.OFF
                ]
                if active_hvac_actions:
                    self._attr_hvac_action = max(
                        active_hvac_actions, key=active_hvac_actions.count
                    )
                elif all(action == HVACAction.OFF for action in current_hvac_actions):
                    self._attr_hvac_action = HVACAction.OFF
            else:
                self._attr_hvac_action = None

            self._attr_supported_features = DEFAULT_SUPPORTED_FEATURES
            for support in find_state_attributes(states, ATTR_SUPPORTED_FEATURES):
                if self._attr_supported_features == DEFAULT_SUPPORTED_FEATURES:
                    self._attr_supported_features = support
                    continue
                self._attr_supported_features &= support

            # Setzt dauerhaft die Mitglieder-Anzeige für die GUI
            self._attr_extra_state_attributes[ATTR_ENTITY_ID] = self._entity_ids
            self._attr_extra_state_attributes[ATTR_ASSUMED_STATE] = self._attr_assumed_state
            self._attr_extra_state_attributes[ATTR_LAST_ACTIVE_HVAC_MODE] = (
                self._last_active_hvac_mode
            )
            self._attr_extra_state_attributes[ATTR_TARGET_HVAC_MODE] = (
                self._target_hvac_mode
            )
            self._attr_extra_state_attributes[ATTR_CURRENT_HVAC_MODES] = (
                current_hvac_modes
            )
            if self._target_hvac_mode is not None:
                self._attr_extra_state_attributes[ATTR_GROUP_IN_SYNC] = (
                    len(set(current_hvac_modes)) == 1
                    and current_hvac_modes[0] == self._target_hvac_mode
                )
            else:
                self._attr_extra_state_attributes[ATTR_GROUP_IN_SYNC] = False

        else:
            self._attr_hvac_mode = None
            self._attr_available = False

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Forward the set_temperature command to all climate in the Climate Group Minimal."""
        data = {ATTR_ENTITY_ID: self._entity_ids}

        if ATTR_HVAC_MODE in kwargs:
            await self.async_set_hvac_mode(kwargs[ATTR_HVAC_MODE])

        if ATTR_TEMPERATURE in kwargs:
            data[ATTR_TEMPERATURE] = kwargs[ATTR_TEMPERATURE]
        if ATTR_TARGET_TEMP_LOW in kwargs:
            data[ATTR_TARGET_TEMP_LOW] = kwargs[ATTR_TARGET_TEMP_LOW]
        if ATTR_TARGET_TEMP_HIGH in kwargs:
            data[ATTR_TARGET_TEMP_HIGH] = kwargs[ATTR_TARGET_TEMP_HIGH]

        _LOGGER.debug("Setting temperature: %s", data)
        await self.hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_SET_TEMPERATURE,
            data,
            blocking=True,
            context=self._context,
        )

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Forward the set_hvac_mode command to all climate in the Climate Group Minimal."""
        self._target_hvac_mode = hvac_mode
        self.async_defer_or_update_ha_state()

        data = {ATTR_ENTITY_ID: self._entity_ids, ATTR_HVAC_MODE: hvac_mode}
        _LOGGER.debug("Setting HVAC mode: %s", data)
        await self.hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_SET_HVAC_MODE,
            data,
            blocking=True,
            context=self._context,
        )

    async def async_turn_on(self) -> None:
        """Forward the turn_on command to all climate in the Climate Group Minimal."""
        if self._last_active_hvac_mode is not None:
            _LOGGER.debug(
                "Turn on with the last active HVAC mode: %s",
                self._last_active_hvac_mode,
            )
            await self.async_set_hvac_mode(self._last_active_hvac_mode)
        elif self._attr_hvac_modes:
            for mode in self._attr_hvac_modes:
                if mode != HVACMode.OFF:
                    _LOGGER.debug("Turn on with first available HVAC mode: %s", mode)
                    await self.async_set_hvac_mode(mode)
                    break
        else:
            _LOGGER.debug("Can't turn on: No HVAC modes available")

    async def async_turn_off(self) -> None:
        """Forward the turn_off command to all climate in the Climate Group Minimal."""
        if HVACMode.OFF in self._attr_hvac_modes:
            _LOGGER.debug("Turn off with HVAC mode 'off'")
            await self.async_set_hvac_mode(HVACMode.OFF)
        else:
            _LOGGER.debug("Can't turn off: HVAC mode 'off' not available")

    async def async_toggle(self) -> None:
        """Toggle the entity."""
        if self._attr_hvac_mode == HVACMode.OFF:
            await self.async_turn_on()
        else:
            await self.async_turn_off()
"""Home Assistant NEIS School integration."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.event import async_track_time_change

from .api import NeisAPI
from .const import CONF_API_KEY
from .coordinator import NeisSchoolCoordinator

PLATFORMS = ["sensor", "binary_sensor", "calendar"]
type NeisSchoolConfigEntry = ConfigEntry[NeisSchoolCoordinator]


async def async_setup_entry(hass: HomeAssistant, entry: NeisSchoolConfigEntry) -> bool:
    """Set up NEIS School from a config entry."""
    api_key = entry.options.get(CONF_API_KEY)
    api = NeisAPI(async_get_clientsession(hass), str(api_key) if api_key else None)
    coordinator = NeisSchoolCoordinator(hass, entry, api)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator

    @callback
    def _midnight_refresh(_now) -> None:
        hass.async_create_task(coordinator.async_request_refresh())

    entry.async_on_unload(
        async_track_time_change(hass, _midnight_refresh, hour=0, minute=0, second=5)
    )
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: NeisSchoolConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload after options change."""
    await hass.config_entries.async_reload(entry.entry_id)

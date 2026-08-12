"""Home Assistant NEIS School integration."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.event import async_track_time_change

from .api import NeisAPI
from .const import CONF_API_KEY, CONF_SCHOOL_CODE, DOMAIN, REFRESH_TIMES
from .coordinator import NeisSchoolCoordinator

PLATFORMS = [Platform.SENSOR, Platform.BINARY_SENSOR, Platform.CALENDAR]
type NeisSchoolConfigEntry = ConfigEntry[NeisSchoolCoordinator]


async def async_setup_entry(hass: HomeAssistant, entry: NeisSchoolConfigEntry) -> bool:
    """Set up NEIS School from a config entry."""
    api_key = entry.data.get(CONF_API_KEY, entry.options.get(CONF_API_KEY))
    api = NeisAPI(async_get_clientsession(hass), str(api_key) if api_key else None)
    coordinator = NeisSchoolCoordinator(hass, entry, api)
    await coordinator.async_initialize()
    entry.runtime_data = coordinator

    @callback
    def _midnight_refresh(_now) -> None:
        hass.async_create_task(coordinator.async_project_date(_now.date()))

    @callback
    def _scheduled_refresh(_now) -> None:
        hass.async_create_task(coordinator.async_request_refresh())

    entry.async_on_unload(
        async_track_time_change(hass, _midnight_refresh, hour=0, minute=0, second=5)
    )
    for hour, minute in REFRESH_TIMES:
        entry.async_on_unload(
            async_track_time_change(
                hass, _scheduled_refresh, hour=hour, minute=minute, second=0
            )
        )
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: NeisSchoolConfigEntry) -> bool:
    """Unload a config entry."""
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        entry.runtime_data.async_shutdown()
        entry.runtime_data.clear_incomplete_issue()
    return unloaded


async def async_migrate_entry(
    hass: HomeAssistant, entry: NeisSchoolConfigEntry
) -> bool:
    """Migrate beta entries without changing user-facing entity IDs."""
    if entry.version != 1:
        return True

    data = dict(entry.data)
    options = dict(entry.options)
    if CONF_API_KEY in options and CONF_API_KEY not in data:
        data[CONF_API_KEY] = options.pop(CONF_API_KEY)

    old_prefix = f"{data[CONF_SCHOOL_CODE]}_"
    entity_registry = er.async_get(hass)
    for registry_entry in er.async_entries_for_config_entry(
        entity_registry, entry.entry_id
    ):
        if registry_entry.unique_id.startswith(old_prefix):
            suffix = registry_entry.unique_id.removeprefix(old_prefix)
            entity_registry.async_update_entity(
                registry_entry.entity_id,
                new_unique_id=f"{entry.entry_id}_{suffix}",
            )

    device_registry = dr.async_get(hass)
    device = device_registry.async_get_device(
        identifiers={(DOMAIN, str(data[CONF_SCHOOL_CODE]))}
    )
    if device is not None:
        device_registry.async_update_device(
            device.id,
            new_identifiers={(DOMAIN, entry.entry_id)},
        )

    hass.config_entries.async_update_entry(
        entry,
        data=data,
        options=options,
        unique_id=None,
        version=2,
    )
    return True


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload after options change."""
    await hass.config_entries.async_reload(entry.entry_id)

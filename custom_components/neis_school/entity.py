"""Base entity for NEIS School."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    CONF_SCHOOL_HOMEPAGE,
    CONF_SCHOOL_KIND,
    CONF_SCHOOL_NAME,
    DOMAIN,
)
from .coordinator import NeisSchoolCoordinator


class NeisSchoolEntity(CoordinatorEntity[NeisSchoolCoordinator]):
    """Base class for entities associated with one school."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: NeisSchoolCoordinator) -> None:
        """Initialize common entity properties."""
        super().__init__(coordinator)
        entry = coordinator.entry
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.school_code)},
            name=str(entry.data[CONF_SCHOOL_NAME]),
            manufacturer="NEIS",
            model=str(entry.data[CONF_SCHOOL_KIND]),
            configuration_url=entry.data.get(CONF_SCHOOL_HOMEPAGE),
        )

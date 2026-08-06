"""Base entity for NEIS School."""

from __future__ import annotations

import voluptuous as vol
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    CONF_SCHOOL_HOMEPAGE,
    CONF_SCHOOL_KIND,
    DOMAIN,
)
from .coordinator import NeisSchoolCoordinator


def _normalize_configuration_url(value: object) -> str | None:
    """Return a valid device configuration URL for a school homepage."""
    if not value or not (homepage := str(value).strip()):
        return None

    if "://" not in homepage:
        homepage = f"https://{homepage}"

    try:
        return cv.url(homepage)
    except vol.Invalid:
        return None


class NeisSchoolEntity(CoordinatorEntity[NeisSchoolCoordinator]):
    """Base class for entities associated with one school."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: NeisSchoolCoordinator) -> None:
        """Initialize common entity properties."""
        super().__init__(coordinator)
        entry = coordinator.entry
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=entry.title,
            manufacturer="NEIS",
            model=str(entry.data[CONF_SCHOOL_KIND]),
            configuration_url=_normalize_configuration_url(
                entry.data.get(CONF_SCHOOL_HOMEPAGE)
            ),
        )

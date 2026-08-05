"""Tests for beta config-entry registry migration."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.neis_school import async_migrate_entry, async_unload_entry
from custom_components.neis_school.const import (
    CONF_API_KEY,
    CONF_CLASS_NAME,
    CONF_GRADE,
    CONF_SCHOOL_CODE,
    DOMAIN,
)


async def test_version_one_migration_preserves_registries(hass) -> None:
    entry = MockConfigEntry(
        domain=DOMAIN,
        version=1,
        unique_id="7201202",
        data={CONF_SCHOOL_CODE: "7201202"},
        options={
            CONF_API_KEY: "secret-key",
            CONF_GRADE: 6,
            CONF_CLASS_NAME: "2",
        },
    )
    entry.add_to_hass(hass)

    device_registry = dr.async_get(hass)
    old_device = device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, "7201202")},
        name="사용자 지정 기기",
    )
    entity_registry = er.async_get(hass)
    old_entity = entity_registry.async_get_or_create(
        "sensor",
        DOMAIN,
        "7201202_schedule_today",
        config_entry=entry,
        device_id=old_device.id,
        suggested_object_id="custom_schedule",
    )

    assert await async_migrate_entry(hass, entry)

    migrated_entity = entity_registry.async_get(old_entity.entity_id)
    migrated_device = device_registry.async_get(old_device.id)
    assert entry.version == 2
    assert entry.unique_id is None
    assert entry.data[CONF_API_KEY] == "secret-key"
    assert CONF_API_KEY not in entry.options
    assert migrated_entity is not None
    assert migrated_entity.entity_id == old_entity.entity_id
    assert migrated_entity.unique_id == f"{entry.entry_id}_schedule_today"
    assert migrated_device is not None
    assert migrated_device.identifiers == {(DOMAIN, entry.entry_id)}
    assert migrated_device.name == "사용자 지정 기기"


async def test_unload_clears_the_entry_scoped_repair(hass) -> None:
    runtime_data = SimpleNamespace(clear_incomplete_issue=Mock())
    entry = SimpleNamespace(runtime_data=runtime_data)
    with patch.object(
        hass.config_entries,
        "async_unload_platforms",
        AsyncMock(return_value=True),
    ):
        assert await async_unload_entry(hass, entry)

    runtime_data.clear_incomplete_issue.assert_called_once_with()

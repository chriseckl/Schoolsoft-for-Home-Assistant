"""SchoolSoft integration setup."""
from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DOMAIN, PLATFORMS, UPDATE_INTERVAL
from .coordinator import SchoolSoftCoordinator

type SchoolSoftConfigEntry = ConfigEntry[SchoolSoftCoordinator]


async def async_setup_entry(hass: HomeAssistant, entry: SchoolSoftConfigEntry) -> bool:
    """Set up SchoolSoft from a config entry."""
    coordinator = SchoolSoftCoordinator(
        hass,
        async_get_clientsession(hass),
        entry.data,
        UPDATE_INTERVAL,
    )
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: SchoolSoftConfigEntry) -> bool:
    """Unload a SchoolSoft config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

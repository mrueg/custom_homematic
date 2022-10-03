"""Module with hahomematic services."""
from __future__ import annotations

from datetime import datetime
import logging
from typing import Any

from hahomematic.const import (
    ATTR_ADDRESS,
    ATTR_INTERFACE_ID,
    ATTR_NAME,
    ATTR_PARAMETER,
    ATTR_VALUE,
    HmForcedDeviceAvailability,
    HmPlatform,
)
from hahomematic.entity import BaseEntity, GenericEntity
import voluptuous as vol

from homeassistant.const import ATTR_ENTITY_ID, ATTR_MODE, ATTR_TIME
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import device_registry as dr
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.device_registry import DeviceEntry
from homeassistant.helpers.service import (
    async_register_admin_service,
    verify_domain_control,
)

from .const import (
    ATTR_PARAMSET,
    ATTR_PARAMSET_KEY,
    ATTR_RX_MODE,
    ATTR_VALUE_TYPE,
    CONTROL_UNITS,
    DOMAIN,
)
from .control_unit import ControlUnit, HaHubSensor, get_cu_by_interface_id, get_device
from .helpers import HmBaseEntity, get_device_address_at_interface_from_identifiers

_LOGGER = logging.getLogger(__name__)

ATTR_CHANNEL = "channel"
ATTR_DEVICE_ID = "device_id"
DEFAULT_CHANNEL = 1

SERVICE_CLEAR_CACHE = "clear_cache"
SERVICE_DELETE_DEVICE = "delete_device"
SERVICE_FORCE_DEVICE_AVAILABILITY = "force_device_availability"
SERVICE_EXPORT_DEVICE_DEFINITION = "export_device_definition"
SERVICE_PUT_PARAMSET = "put_paramset"
SERVICE_SET_DEVICE_VALUE = "set_device_value"
SERVICE_SET_DEVICE_VALUE_RAW = "set_device_value_raw"
SERVICE_SET_INSTALL_MODE = "set_install_mode"
SERVICE_SET_VARIABLE_VALUE = "set_variable_value"

HMIP_LOCAL_SERVICES = [
    SERVICE_CLEAR_CACHE,
    SERVICE_DELETE_DEVICE,
    SERVICE_FORCE_DEVICE_AVAILABILITY,
    SERVICE_EXPORT_DEVICE_DEFINITION,
    SERVICE_PUT_PARAMSET,
    SERVICE_SET_DEVICE_VALUE,
    SERVICE_SET_DEVICE_VALUE_RAW,
    SERVICE_SET_INSTALL_MODE,
    SERVICE_SET_VARIABLE_VALUE,
]

SCHEMA_SERVICE_CLEAR_CACHE = vol.Schema(
    {
        vol.Required(ATTR_ENTITY_ID): cv.string,
    }
)

SCHEMA_SERVICE_DELETE_DEVICE = vol.Schema(
    {
        vol.Required(ATTR_DEVICE_ID): cv.string,
    }
)

SCHEMA_SERVICE_EXPORT_DEVICE_DEFINITION = vol.Schema(
    {
        vol.Required(ATTR_DEVICE_ID): cv.string,
    }
)

SCHEMA_SERVICE_FORCE_DEVICE_AVAILABILITY = vol.Schema(
    {
        vol.Required(ATTR_DEVICE_ID): cv.string,
    }
)

SCHEMA_SERVICE_SET_VARIABLE_VALUE = vol.Schema(
    {
        vol.Required(ATTR_ENTITY_ID): cv.string,
        vol.Required(ATTR_NAME): cv.string,
        vol.Required(ATTR_VALUE): cv.match_all,
    }
)

SCHEMA_SERVICE_SET_INSTALL_MODE = vol.Schema(
    {
        vol.Required(ATTR_INTERFACE_ID): cv.string,
        vol.Optional(ATTR_TIME, default=60): cv.positive_int,
        vol.Optional(ATTR_MODE, default=1): vol.All(vol.Coerce(int), vol.In([1, 2])),
        vol.Optional(ATTR_ADDRESS): vol.All(cv.string, vol.Upper),
    }
)

SCHEMA_SERVICE_SET_DEVICE_VALUE = vol.Schema(
    {
        vol.Required(ATTR_DEVICE_ID): cv.string,
        vol.Required(ATTR_CHANNEL, default=DEFAULT_CHANNEL): vol.Coerce(int),
        vol.Required(ATTR_PARAMETER): vol.All(cv.string, vol.Upper),
        vol.Required(ATTR_VALUE): cv.match_all,
        vol.Optional(ATTR_VALUE_TYPE): vol.In(
            ["boolean", "dateTime.iso8601", "double", "int", "string"]
        ),
        vol.Optional(ATTR_RX_MODE): vol.All(cv.string, vol.Upper),
    }
)

SCHEMA_SERVICE_SET_DEVICE_VALUE_RAW = vol.Schema(
    {
        vol.Required(ATTR_INTERFACE_ID): cv.string,
        vol.Required(ATTR_ADDRESS): cv.string,
        vol.Required(ATTR_PARAMETER): vol.All(cv.string, vol.Upper),
        vol.Required(ATTR_VALUE): cv.match_all,
        vol.Optional(ATTR_VALUE_TYPE): vol.In(
            ["boolean", "dateTime.iso8601", "double", "int", "string"]
        ),
        vol.Optional(ATTR_RX_MODE): vol.All(cv.string, vol.Upper),
    }
)

SCHEMA_SERVICE_PUT_PARAMSET = vol.Schema(
    {
        vol.Required(ATTR_DEVICE_ID): cv.string,
        vol.Optional(ATTR_CHANNEL): vol.Coerce(int),
        vol.Required(ATTR_PARAMSET_KEY): vol.All(cv.string, vol.Upper),
        vol.Required(ATTR_PARAMSET): dict,
        vol.Optional(ATTR_RX_MODE): vol.All(cv.string, vol.Upper),
    }
)


async def async_setup_services(hass: HomeAssistant) -> None:
    """Create the hahomematic services."""

    @verify_domain_control(hass, DOMAIN)
    async def async_call_hmip_local_service(service: ServiceCall) -> None:
        """Call correct Homematic(IP) Local service."""
        service_name = service.service

        if service_name == SERVICE_CLEAR_CACHE:
            await _async_service_clear_cache(hass=hass, service=service)
        elif service_name == SERVICE_DELETE_DEVICE:
            await _async_service_delete_device(hass=hass, service=service)
        elif service_name == SERVICE_EXPORT_DEVICE_DEFINITION:
            await _async_service_export_device_definition(hass=hass, service=service)
        elif service_name == SERVICE_FORCE_DEVICE_AVAILABILITY:
            await _async_service_force_device_availability(hass=hass, service=service)
        elif service_name == SERVICE_PUT_PARAMSET:
            await _async_service_put_paramset(hass=hass, service=service)
        elif service_name == SERVICE_SET_INSTALL_MODE:
            await _async_service_set_install_mode(hass=hass, service=service)
        elif service_name == SERVICE_SET_DEVICE_VALUE:
            await _async_service_set_device_value(hass=hass, service=service)
        elif service_name == SERVICE_SET_DEVICE_VALUE_RAW:
            await _async_service_set_device_value_raw(hass=hass, service=service)
        elif service_name == SERVICE_SET_VARIABLE_VALUE:
            await _async_service_set_variable_value(hass=hass, service=service)

    async_register_admin_service(
        hass=hass,
        domain=DOMAIN,
        service=SERVICE_CLEAR_CACHE,
        service_func=async_call_hmip_local_service,
        schema=SCHEMA_SERVICE_CLEAR_CACHE,
    )

    async_register_admin_service(
        hass=hass,
        domain=DOMAIN,
        service=SERVICE_DELETE_DEVICE,
        service_func=async_call_hmip_local_service,
        schema=SCHEMA_SERVICE_DELETE_DEVICE,
    )

    async_register_admin_service(
        hass=hass,
        domain=DOMAIN,
        service=SERVICE_EXPORT_DEVICE_DEFINITION,
        service_func=async_call_hmip_local_service,
        schema=SCHEMA_SERVICE_EXPORT_DEVICE_DEFINITION,
    )

    async_register_admin_service(
        hass=hass,
        domain=DOMAIN,
        service=SERVICE_FORCE_DEVICE_AVAILABILITY,
        service_func=async_call_hmip_local_service,
        schema=SCHEMA_SERVICE_FORCE_DEVICE_AVAILABILITY,
    )

    hass.services.async_register(
        domain=DOMAIN,
        service=SERVICE_SET_VARIABLE_VALUE,
        service_func=async_call_hmip_local_service,
        schema=SCHEMA_SERVICE_SET_VARIABLE_VALUE,
    )

    hass.services.async_register(
        domain=DOMAIN,
        service=SERVICE_SET_DEVICE_VALUE,
        service_func=async_call_hmip_local_service,
        schema=SCHEMA_SERVICE_SET_DEVICE_VALUE,
    )

    hass.services.async_register(
        domain=DOMAIN,
        service=SERVICE_SET_DEVICE_VALUE_RAW,
        service_func=async_call_hmip_local_service,
        schema=SCHEMA_SERVICE_SET_DEVICE_VALUE_RAW,
    )

    async_register_admin_service(
        hass=hass,
        domain=DOMAIN,
        service=SERVICE_SET_INSTALL_MODE,
        service_func=async_call_hmip_local_service,
        schema=SCHEMA_SERVICE_SET_INSTALL_MODE,
    )

    hass.services.async_register(
        domain=DOMAIN,
        service=SERVICE_PUT_PARAMSET,
        service_func=async_call_hmip_local_service,
        schema=SCHEMA_SERVICE_PUT_PARAMSET,
    )


async def async_unload_services(hass: HomeAssistant) -> None:
    """Unload Homematic(IP) Local services."""
    if hass.data[DOMAIN][CONTROL_UNITS]:
        return

    for hmip_local_service in HMIP_LOCAL_SERVICES:
        hass.services.async_remove(domain=DOMAIN, service=hmip_local_service)


async def _async_service_delete_device(
    hass: HomeAssistant, service: ServiceCall
) -> None:
    """Service to delete a HomeMatic device from HA."""
    device_id = service.data[ATTR_DEVICE_ID]

    if (address_data := _get_interface_address(hass=hass, device_id=device_id)) is None:
        return None

    interface_id: str = address_data[0]
    device_address: str = address_data[1]

    if interface_id and device_address:
        if control_unit := get_cu_by_interface_id(hass=hass, interface_id=interface_id):
            await control_unit.central.delete_device(
                interface_id=interface_id, device_address=device_address
            )
            _LOGGER.debug(
                "Called delete_device: %s, %s",
                interface_id,
                device_address,
            )


async def _async_service_export_device_definition(
    hass: HomeAssistant, service: ServiceCall
) -> None:
    """Service to call setValue method for HomeMatic devices."""
    device_id = service.data[ATTR_DEVICE_ID]

    if hm_device := get_device(hass=hass, device_id=device_id):
        await hm_device.export_device_definition()

        _LOGGER.debug(
            "Called export_device_definition: %s, %s",
            hm_device.name,
            hm_device.device_address,
        )


async def _async_service_force_device_availability(
    hass: HomeAssistant, service: ServiceCall
) -> None:
    """Service to force device availability on a HomeMatic devices."""
    device_id = service.data[ATTR_DEVICE_ID]

    if hm_device := get_device(hass=hass, device_id=device_id):
        hm_device.set_forced_availability(
            forced_availability=HmForcedDeviceAvailability.FORCE_TRUE
        )

        _LOGGER.debug(
            "Called force_device_availability: %s, %s",
            hm_device.name,
            hm_device.device_address,
        )


async def _async_service_set_variable_value(
    hass: HomeAssistant, service: ServiceCall
) -> None:
    """Service to call setValue method for HomeMatic system variable."""
    entity_id = service.data[ATTR_ENTITY_ID]
    name = service.data[ATTR_NAME]
    value = service.data[ATTR_VALUE]

    if hub_entity := _get_hub_entity_by_id(hass=hass, entity_id=entity_id):
        if ha_hub := hub_entity.control.central.hub:
            await ha_hub.set_system_variable(name=name, value=value)


async def _async_service_set_device_value(
    hass: HomeAssistant, service: ServiceCall
) -> None:
    """Service to call setValue method for HomeMatic devices."""
    device_id = service.data[ATTR_DEVICE_ID]
    channel = service.data[ATTR_CHANNEL]
    parameter = service.data[ATTR_PARAMETER]
    value = service.data[ATTR_VALUE]
    value_type = service.data.get(ATTR_VALUE_TYPE)
    rx_mode = service.data.get(ATTR_RX_MODE)

    if (
        address_data := _get_interface_address(
            hass=hass, device_id=device_id, channel=channel
        )
    ) is None:
        return None

    interface_id: str = address_data[0]
    channel_address: str = address_data[1]

    await _call_set_device_value(
        hass=hass,
        interface_id=interface_id,
        channel_address=channel_address,
        parameter=parameter,
        value=value,
        value_type=value_type,
        rx_mode=rx_mode,
    )


async def _async_service_set_device_value_raw(
    hass: HomeAssistant, service: ServiceCall
) -> None:
    """Service to call setValue method for HomeMatic devices."""
    interface_id = service.data[ATTR_INTERFACE_ID]
    channel_address = service.data[ATTR_ADDRESS]
    parameter = service.data[ATTR_PARAMETER]
    value = service.data[ATTR_VALUE]
    value_type = service.data.get(ATTR_VALUE_TYPE)
    rx_mode = service.data.get(ATTR_RX_MODE)

    await _call_set_device_value(
        hass=hass,
        interface_id=interface_id,
        channel_address=channel_address,
        parameter=parameter,
        value=value,
        value_type=value_type,
        rx_mode=rx_mode,
    )


async def _call_set_device_value(
    hass: HomeAssistant,
    interface_id: str,
    channel_address: str,
    parameter: str,
    value: Any,
    value_type: str | None,
    rx_mode: str | None = None,
) -> None:
    """Call the set_value on the backend."""
    if value_type:
        # Convert value into correct XML-RPC Type.
        # https://docs.python.org/3/library/xmlrpc.client.html#xmlrpc.client.ServerProxy
        if value_type == "int":
            value = int(value)
        elif value_type == "double":
            value = float(value)
        elif value_type == "boolean":
            value = bool(value)
        elif value_type == "dateTime.iso8601":
            value = datetime.strptime(value, "%Y%m%dT%H:%M:%S")
        else:
            # Default is 'string'
            value = str(value)

    _LOGGER.debug(
        "Calling setValue: %s, %s, %s, %s, %s",
        interface_id,
        channel_address,
        parameter,
        value,
        rx_mode,
    )

    if interface_id and channel_address:
        if control_unit := get_cu_by_interface_id(hass=hass, interface_id=interface_id):
            await control_unit.central.set_value(
                interface_id=interface_id,
                channel_address=channel_address,
                parameter=parameter,
                value=value,
                rx_mode=rx_mode,
            )


async def _async_service_set_install_mode(
    hass: HomeAssistant, service: ServiceCall
) -> None:
    """Service to set interface_id into install mode."""
    interface_id = service.data[ATTR_INTERFACE_ID]
    mode: int = service.data.get(ATTR_MODE, 1)
    time: int = service.data.get(ATTR_TIME, 60)
    device_address = service.data.get(ATTR_ADDRESS)

    if control_unit := get_cu_by_interface_id(hass=hass, interface_id=interface_id):
        await control_unit.central.set_install_mode(
            interface_id, t=time, mode=mode, device_address=device_address
        )


async def _async_service_clear_cache(hass: HomeAssistant, service: ServiceCall) -> None:
    """Service to clear the cache."""
    entity_id = service.data[ATTR_ENTITY_ID]

    if hub_entity := _get_hub_entity_by_id(hass=hass, entity_id=entity_id):
        await hub_entity.control.central.clear_all()


async def _async_service_put_paramset(
    hass: HomeAssistant, service: ServiceCall
) -> None:
    """Service to call the putParamset method on a HomeMatic connection."""
    device_id = service.data[ATTR_DEVICE_ID]
    channel = service.data.get(ATTR_CHANNEL)
    paramset_key = service.data[ATTR_PARAMSET_KEY]
    # When passing in the paramset from a YAML file we get an OrderedDict
    # here instead of a dict, so add this explicit cast.
    # The service schema makes sure that this cast works.
    paramset = dict(service.data[ATTR_PARAMSET])
    rx_mode = service.data.get(ATTR_RX_MODE)

    if (
        address_data := _get_interface_address(
            hass=hass, device_id=device_id, channel=channel
        )
    ) is None:
        return None

    interface_id: str = address_data[0]
    address: str = address_data[1]

    _LOGGER.debug(
        "Calling putParamset: %s, %s, %s, %s, %s",
        interface_id,
        address,
        paramset_key,
        paramset,
        rx_mode,
    )

    if interface_id and address:
        if control_unit := get_cu_by_interface_id(hass=hass, interface_id=interface_id):
            await control_unit.central.put_paramset(
                interface_id=interface_id,
                address=address,
                paramset_key=paramset_key,
                value=paramset,
                rx_mode=rx_mode,
            )


def _get_interface_address(
    hass: HomeAssistant, device_id: str, channel: int | None = None
) -> tuple[str, str] | None:
    """Return interface and channel_address with given device_id and channel."""
    device_registry = dr.async_get(hass)
    device_entry: DeviceEntry | None = device_registry.async_get(device_id)
    if not device_entry:
        return None
    if (
        data := get_device_address_at_interface_from_identifiers(
            identifiers=device_entry.identifiers
        )
    ) is None:
        return None

    device_address = data[0]
    interface_id = data[1]

    address = f"{device_address}:{channel}" if channel is not None else device_address
    return interface_id, address


def _get_entity(hass: HomeAssistant, entity_id: str) -> HmBaseEntity | None:
    """Return entity by given entity_id."""
    control_unit: ControlUnit
    for control_unit in hass.data[DOMAIN][CONTROL_UNITS].values():
        if hm_entity := control_unit.async_get_hm_entity(entity_id=entity_id):
            return hm_entity
    return None


def _get_entities_by_platform(
    hass: HomeAssistant, platform: HmPlatform
) -> list[BaseEntity]:
    """Return entities by given platform."""
    control_unit: ControlUnit
    hm_entities: list[BaseEntity] = []
    for control_unit in hass.data[DOMAIN][CONTROL_UNITS].values():
        hm_entities.extend(
            control_unit.async_get_hm_entities_by_platform(platform=platform)
        )
    return hm_entities


def _get_hm_entity(
    hass: HomeAssistant, interface_id: str, channel_address: str, parameter: str
) -> GenericEntity | None:
    """Get homematic entity."""
    if control_unit := get_cu_by_interface_id(hass=hass, interface_id=interface_id):
        return control_unit.central.get_hm_entity(
            channel_address=channel_address, parameter=parameter
        )
    return None


def _get_hub_entity_by_id(hass: HomeAssistant, entity_id: str) -> HaHubSensor | None:
    """Get ControlUnit by device address."""
    if entity_id.startswith("homematicip_local"):
        old_entity_id = entity_id
        entity_id = entity_id.replace("homematicip_local.", "sensor.")
        _LOGGER.warning(
            "Using service call with %s will be removed with HA 11.2022. Use %s instead",
            old_entity_id,
            entity_id,
        )

    for entry_id in hass.data[DOMAIN][CONTROL_UNITS].keys():
        control_unit: ControlUnit = hass.data[DOMAIN][CONTROL_UNITS][entry_id]
        if (
            control_unit
            and control_unit.hub_entity
            and control_unit.hub_entity.entity_id == entity_id
        ):
            return control_unit.hub_entity
    return None

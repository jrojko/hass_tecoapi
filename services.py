"""Services for TecoAPI."""
import logging
import json

import voluptuous as vol

import homeassistant.helpers.config_validation as cv

from .const import (
    DATA_TECOAPI,
    DOMAIN,
    SERVICE_SET_OBJECT,
    SERVICE_GET_OBJECT,
    CONF_OBJECT,
    CONF_VALUE,
)

_LOGGER = logging.getLogger(__name__)

async def async_register_services(hass):
    """Register public services."""

    async def set_parameter(call):
        data = hass.data[DATA_TECOAPI]

        await data.async_put('PutObject', call.data[CONF_OBJECT], call.data[CONF_VALUE])

    async def get_parameter(call):
        data = hass.data[DATA_TECOAPI]
        value = await data.async_get('GetObject', call.data[CONF_OBJECT], False)

        hass.components.persistent_notification.async_create(
            json.dumps(value, indent=1), "Nibe get parameter result"
        )

    SERVICE_SET_OBJECT_SCHEMA = vol.Schema(
        {
            vol.Required(CONF_OBJECT): cv.string,
            vol.Required(CONF_VALUE) : cv.match_all,
        }
    )

    SERVICE_GET_OBJECT_SCHEMA = vol.Schema(
        {vol.Required(CONF_OBJECT): cv.string}
    )

    hass.services.async_register(
        DOMAIN, SERVICE_SET_OBJECT, set_parameter, SERVICE_SET_OBJECT_SCHEMA
    )

    hass.services.async_register(
        DOMAIN, SERVICE_GET_OBJECT, get_parameter, SERVICE_GET_OBJECT_SCHEMA
    )

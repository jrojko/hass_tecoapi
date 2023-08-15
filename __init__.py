"""The TecoAPI component."""

import logging
import json
import asyncio
import aiohttp
import async_timeout
import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant import config_entries
from homeassistant.components import persistent_notification
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.const import (
    CONF_RESOURCE,
    CONF_USERNAME,
    CONF_PASSWORD,
    CONF_SWITCHES,
    CONF_SENSORS,
    CONF_BINARY_SENSORS,
    CONF_HEADERS,
    CONF_TIMEOUT,
    CONF_VERIFY_SSL,
)

from .const import (
    DATA_TECOAPI,
    DOMAIN,
    CONF_GETINFO,
    CONF_GETLIST,
    DEFAULT_TIMEOUT,
    DEFAULT_TIMEOUT_WAIT,
    DEFAULT_VERIFY_SSL,
    TECOAPI_GETINFO,
    TECOAPI_GETLIST,
)

from .switch import SWITCH_SCHEMA
from .sensor import SENSOR_SCHEMA
from .binary_sensor import BINARY_SENSOR_SCHEMA
from .services import async_register_services

TECOAPI_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_RESOURCE): cv.url,
        vol.Required(CONF_USERNAME): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
        vol.Optional(CONF_HEADERS): {cv.string: cv.string},
        vol.Optional(CONF_VERIFY_SSL, default = DEFAULT_VERIFY_SSL): cv.boolean,
        vol.Optional(CONF_TIMEOUT, default = DEFAULT_TIMEOUT): cv.positive_float,
        vol.Optional(CONF_GETINFO, default = False): cv.boolean,
        vol.Optional(CONF_GETLIST, default = False): cv.boolean,
        vol.Optional(CONF_SWITCHES, default = []): vol.All(cv.ensure_list, [vol.Schema(SWITCH_SCHEMA)]),
        vol.Optional(CONF_SENSORS, default = []): vol.All(cv.ensure_list, [vol.Schema(SENSOR_SCHEMA)]),
        vol.Optional(CONF_BINARY_SENSORS, default = []): vol.All(cv.ensure_list, [vol.Schema(BINARY_SENSOR_SCHEMA)]),
    }
)

CONFIG_SCHEMA = vol.Schema({DOMAIN: TECOAPI_SCHEMA}, extra=vol.ALLOW_EXTRA)

FORWARD_PLATFORMS = { 
    "switch": CONF_SWITCHES,
    "sensor": CONF_SENSORS,
    "binary_sensor": CONF_BINARY_SENSORS,
}

_LOGGER = logging.getLogger(__name__)

async def async_setup(hass, config):
    """Configure the Teco TecoAPI component."""

    component_config = config[DOMAIN]

    hass.data[DATA_TECOAPI] = TecoApiData(hass, component_config)

    if component_config.get(CONF_GETINFO):
        hass.helpers.discovery.load_platform("sensor", DOMAIN, TECOAPI_GETINFO, config)

    if component_config.get(CONF_GETLIST):
        hass.helpers.discovery.load_platform("sensor", DOMAIN, TECOAPI_GETLIST, config)

    for platform, pconfig in FORWARD_PLATFORMS.items():
        if pconfig in component_config:
            hass.helpers.discovery.load_platform(platform, DOMAIN, component_config[pconfig], config)

    if config.get(CONF_GETLIST):
        hass.helpers.discovery.load_platform("sensor", DOMAIN, TECOAPI_GETINFO, config)

    await async_register_services(hass)

    return True

class TecoApiData:
    """Holder for TecoApiData data."""

    def __init__(self, hass, config):
        """Init."""
        self.hass = hass
        self.resource = config.get(CONF_RESOURCE)
        if self.resource[-1] != '/':
            self.resource += '/'

        username = config.get(CONF_USERNAME)
        password = config.get(CONF_PASSWORD)
        self.auth = aiohttp.BasicAuth(username, password=password)
#        self.authB = requests.auth.HTTPBasicAuth(username, password)
#        self.authD = requests.auth.HTTPDigestAuth(username, password)

        self.headers = config.get(CONF_HEADERS)
        self.verify_ssl = config.get(CONF_VERIFY_SSL)
        self.timeout = config.get(CONF_TIMEOUT)
        self.parallel_updates_semaphore = asyncio.Semaphore(1)

    async def async_put(self, service, objectid, value):
        """Send a date to the TecoAPI."""
        websession = async_get_clientsession(self.hass, self.verify_ssl)

        resource = self.resource + service

        async with self.parallel_updates_semaphore:
            with async_timeout.timeout(self.timeout):
                if objectid:
                    body = json.dumps({objectid: value})
                else:
                    body = json.dumps(value)

                req = await websession.put(
                    resource,
                    auth = self.auth,
                    headers = self.headers,
                    data = bytes(body, "ascii"),
                )

                if req.status == 204:
                    return True

                _LOGGER.error(
                    _LOGGER.debug("TecoApi PUT %s %s failed. Status: %s", service, body, req.status)
                )

        return False

    async def async_get(self, service, objectid, wait):
        """Get the latest data from TecoAPI."""
        websession = async_get_clientsession(self.hass, self.verify_ssl)

        resource = self.resource + service
        if objectid:
            resource += '?' + objectid

        async with self.parallel_updates_semaphore:
            with async_timeout.timeout(DEFAULT_TIMEOUT_WAIT if wait else self.timeout):
                req = await websession.get(
                    resource,
                    auth = self.auth,
                    headers = self.headers,
                )

                if req.status == 200:
                    text = await req.text()

                    value = json.loads(text)    

                    if objectid:
                        for partid in objectid.split('.'):
                            value = value[partid]

                    return value

            _LOGGER.error(
                _LOGGER.debug("TecoApi GET %s %s failed. Status: %s", service, objectid, req.status)
            )

        return None

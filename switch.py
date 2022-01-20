"""TecoAPI Switch."""
import logging
from datetime import timedelta
import asyncio
import voluptuous as vol
import aiohttp

import homeassistant.helpers.config_validation as cv
from homeassistant.exceptions import PlatformNotReady
from homeassistant.components.switch import (
    PLATFORM_SCHEMA,
    DEVICE_CLASSES_SCHEMA,
    SwitchEntity, DOMAIN as DOMAIN_SWITCH
)
from homeassistant.const import (
    CONF_NAME,
    CONF_DEVICE_CLASS,
)

from .const import (
    DOMAIN,
    DATA_TECOAPI,
    CONF_OBJECT,
    CONF_SUBOBJECTS,
    TECOAPI_GETOBJECT,
)

SWITCH_SCHEMA = {
    vol.Required(CONF_OBJECT): cv.string,
    vol.Optional(CONF_NAME, default=""): cv.string,
    vol.Optional(CONF_DEVICE_CLASS): DEVICE_CLASSES_SCHEMA,
    vol.Optional(CONF_SUBOBJECTS, default=[]): vol.All(cv.ensure_list, [vol.Self]),
}

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(SWITCH_SCHEMA)

PARALLEL_UPDATES = 0
SCAN_INTERVAL = timedelta(seconds=3)

_LOGGER = logging.getLogger(__name__)

async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up the TecoAPI switch."""

    if DATA_TECOAPI not in hass.data:
        raise PlatformNotReady

    data = hass.data[DATA_TECOAPI]

    entities = []

    if discovery_info is None:
        objectid = config.get(CONF_OBJECT)
        await async_setup_switch(hass, data, config, entities, objectid)
    else:
        for child_config in discovery_info:
            objectid = child_config.get(CONF_OBJECT)
            await async_setup_switch(hass, data, child_config, entities, objectid)

    async_add_entities(entities, True)

async def async_setup_switch(hass, data, config, entities, objectid, parent = None):
    """Setup switch helper"""
        # pylint: disable=too-many-arguments

    try:
        if parent is None:
            value = await data.async_get(TECOAPI_GETOBJECT, objectid, True)
        else:
            value = parent.child_values[objectid]

        if type(value) is dict:
            switch = TecoApiSwitch(data, config, objectid, value, parent)
            pos = len(entities)

            switches_config = config.get(CONF_SUBOBJECTS, [])

            for childid in value:
                child_config = next((item for item in switches_config if item.get(CONF_OBJECT) == childid), {})
                await async_setup_switch(hass, data, child_config, entities, childid, switch)

            if parent is None or not switch._children:
                entities.insert(pos, switch)
        elif type(value) is bool:
            entities.append(TecoApiSwitch(data, config, objectid, value, parent))
        else:
            _LOGGER.error("Unable to setup %s", objectid)

    except asyncio.TimeoutError:
        _LOGGER.exception("Timed out %s while setup", objectid)
    except aiohttp.ClientError as err:
        _LOGGER.exception("Error while %s setup: %s", objectid, err)

class TecoApiSwitch(SwitchEntity):
    """TecoAPI Switch Entity."""
    # pylint: disable=too-many-instance-attributes

    def __init__(self, data, config, objectid, value, parent):
        """Init."""
        # pylint: disable=too-many-arguments

        self._name = config.get(CONF_NAME)
        self._device_class = config.get(CONF_DEVICE_CLASS)

        self._data = data
        self._objectid = objectid 
        self._parent = parent

        self._children = []
        if parent: 
            parent._children.append(self)
            self._name = self._name or parent._name + ' ' + objectid
        else:
            self._name = self._name or objectid
            self._value = value #only root items store data

        self.entity_id = self.unique_id

    @property
    def unique_id(self):
        """Return unique identifier."""
        return DOMAIN_SWITCH + "." + DOMAIN + "_" + self.fullobjectid.lower().replace(".", "_")

    @property
    def name(self):
        """Return the name of the switch."""
        return self._name

    @property
    def device_class(self):
        """Return the class of this device, from component DEVICE_CLASSES."""
        return self._device_class

    @property
    def is_on(self):
        """Return if entity is on."""
        if self._children:
            for child in self._children:
                if child.is_on:
                    return True
            return False

        if self._parent:
            return self._parent.child_values[self._objectid]
        return self._value

    async def async_turn_on(self, **kwargs):
        """Turn the device on."""
        if self._children:
            for child in self._children:
                await child.async_turn_on(**kwargs)
        else:
            try:
                if await self._data.async_put('PutObject', self.fullobjectid, True):
                    if self._parent:
                        self._parent.child_values[self._objectid] = True
                    else:
                        self._value = True
            except asyncio.TimeoutError:
                _LOGGER.exception("Timed out while %s switching on", self._objectid)
            except aiohttp.ClientError as err:
                _LOGGER.error("Error while %s switching on %s", self._objectid, err)

    async def async_turn_off(self, **kwargs):
        """Turn the device off."""
        if self._children:
            for child in self._children:
                await child.async_turn_off(**kwargs)
        else:
            try:
                if await self._data.async_put('PutObject', self.fullobjectid, False):
                    if self._parent:
                        self._parent.child_values[self._objectid] = False
                    else:
                        self._value = False
            except asyncio.TimeoutError:
                _LOGGER.exception("Timed out %s while switching off", self._objectid)
            except aiohttp.ClientError as err:
                _LOGGER.error("Error while %s switching off %s", self._objectid, err)

    async def async_update(self):
        """Get the current state, catching errors."""
        if self._parent is None:
            try:
                value = await self._data.async_get(TECOAPI_GETOBJECT, self._objectid, False)
                if value is None:
                    _LOGGER.error("Unable to update %s", self._objectid)
                else:
                    self._value = value

            except asyncio.TimeoutError:
                _LOGGER.warning("Timed out %s while fetching data", self._objectid)
            except aiohttp.ClientError as err:
                _LOGGER.exception("Error while %s fetching data: %s", self._objectid, err)

    ### Heplers ###
    @property
    def child_values(self):
        if self._parent:
            ret = self._parent.child_values[self._objectid]
        else: 
            ret = self._value

        return ret

    @property
    def fullobjectid(self):
        if self._parent:
            return self._parent.fullobjectid + '.' + self._objectid
        return self._objectid


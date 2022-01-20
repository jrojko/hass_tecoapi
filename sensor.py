""""TecoAPI Sensor."""
import logging
from datetime import timedelta
import asyncio
import voluptuous as vol
import aiohttp

from homeassistant.core import split_entity_id
from homeassistant.components.group import (
    ATTR_ADD_ENTITIES,
    ATTR_OBJECT_ID,
    SERVICE_SET,
    DOMAIN as DOMAIN_GROUP
)
import homeassistant.helpers.config_validation as cv
from homeassistant.exceptions import PlatformNotReady
from homeassistant.components.sensor import (
    PLATFORM_SCHEMA,
    DEVICE_CLASSES_SCHEMA,
    DOMAIN as DOMAIN_SENSOR
)
from homeassistant.helpers.entity import Entity
from homeassistant.const import (
    CONF_NAME,
    CONF_DEVICE_CLASS,
    CONF_UNIT_OF_MEASUREMENT,
)

from .const import (
    DOMAIN,
    DATA_TECOAPI,
    CONF_OBJECT,
    CONF_SUBOBJECTS,
    TECOAPI_GETOBJECT,
    TECOAPI_GETINFO,
    TECOAPI_GETLIST,
)

SENSOR_SCHEMA = {
    vol.Required(CONF_OBJECT): cv.string,
    vol.Optional(CONF_NAME, default=""): cv.string,
    vol.Optional(CONF_DEVICE_CLASS): DEVICE_CLASSES_SCHEMA,
    vol.Optional(CONF_UNIT_OF_MEASUREMENT, default=""): cv.string,
    vol.Optional(CONF_SUBOBJECTS, default=[]): vol.All(cv.ensure_list, [vol.Self]), 
}

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(SENSOR_SCHEMA)

PARALLEL_UPDATES = 0
SCAN_INTERVAL = timedelta(seconds=3)

_LOGGER = logging.getLogger(__name__)


async def create_group(hass, name, entities):
    """Create group"""
    group = hass.components.group

    entity = await group.Group.async_create_group(
            hass,
            name,
#            control=False,
            object_id = "{}_{}".format(DOMAIN, "entities"),
        )

    _, group_id = split_entity_id(entity.entity_id)

    ids = []
    for ent in entities:
        if not ent._children:
            ids.append(ent.entity_id)

    hass.async_add_job(
                hass.services.async_call(
                    DOMAIN_GROUP,
                    SERVICE_SET,
                    {ATTR_OBJECT_ID: group_id, ATTR_ADD_ENTITIES: ids},
                )
            )

async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up the TecoAPI sensor."""

    if DATA_TECOAPI not in hass.data:
        raise PlatformNotReady

    data = hass.data[DATA_TECOAPI]

    entities = []

    if discovery_info is None:
        objectid = config.get(CONF_OBJECT)
        await async_setup_sensor(hass, data, config, entities, objectid)
    elif discovery_info == TECOAPI_GETINFO:
        name = "TecoAPI Info"
        xconfig = {CONF_NAME: name}
        await async_setup_sensor(hass, data, xconfig, entities, TECOAPI_GETINFO)
    elif discovery_info == TECOAPI_GETLIST:
        objects = await data.async_get(TECOAPI_GETLIST, None, True)
        for objectid in objects:
            await async_setup_sensor(hass, data, None, entities, objectid)
    else:
        for child_config in discovery_info:
            objectid = child_config.get(CONF_OBJECT)
            await async_setup_sensor(hass, data, child_config, entities, objectid)

    async_add_entities(entities, True)

    for entity in entities:
        if entity._parent is None:
            entities = entity.get_all_sensors()
            if len(entities) > 1:
                await create_group(hass, entity.name, entities)

async def async_setup_sensor(hass, data, config, entities, objectid, parent = None):
    """Set up sensor helper """
    # pylint: disable=too-many-arguments
    try:
        if parent is None:
            if objectid == TECOAPI_GETINFO:
                value = await data.async_get(TECOAPI_GETINFO, None, True)
            else:
                value = await data.async_get(TECOAPI_GETOBJECT, objectid, True)
        else:
            value = parent.child_values[objectid]

        if type(value) is dict:
            sensor = TecoApiSensor(data, config, objectid, value, parent)
            pos = len(entities)

            sensors_config = config.get(CONF_SUBOBJECTS, [])

            for childid in value:
                child_config = next((item for item in sensors_config if item.get(CONF_OBJECT) == childid), {})
                await async_setup_sensor(hass, data, child_config, entities, childid, sensor)

            if parent is None or not sensor._children:
                entities.insert(pos, sensor)
        elif type(value) is not None:
            entities.append(TecoApiSensor(data, config, objectid, value, parent))
        else:
            _LOGGER.error("Unable to setup %s", objectid)

    except asyncio.TimeoutError:
        _LOGGER.exception("Timed out %s while setup", objectid)
    except aiohttp.ClientError as err:
        _LOGGER.exception("Error while %s setup: %s", objectid, err)

class TecoApiSensor(Entity):
    """TecoAPI Sensor Entity."""
    # pylint: disable=too-many-instance-attributes

    def __init__(self, data, config, objectid, value, parent):
        """Init."""
        # pylint: disable=too-many-arguments

        self._name = config.get(CONF_NAME)
        self._device_class = config.get(CONF_DEVICE_CLASS)
        self._unit_of_measurement = config.get(CONF_UNIT_OF_MEASUREMENT)

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
        return DOMAIN_SENSOR + "." + DOMAIN + "_" + self.fullobjectid.lower().replace(".", "_")

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def device_class(self):
        """Return the class of this device, from component DEVICE_CLASSES."""
        return self._device_class

    @property
    def state(self):
        """Return the state of the sensor."""
        if self._children:
            return None 

        if self._parent:
            return self._parent.child_values[self._objectid]
        else:
            return self._value

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement."""
        return self._unit_of_measurement

    async def async_update(self):
        """Get the current state, catching errors."""
        if self._parent is None:
            try:
                if self._objectid == TECOAPI_GETINFO:
                    value = await self._data.async_get(TECOAPI_GETINFO, None, False)
                else:
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
        else:
            return self._objectid

    def get_all_sensors(self, sensors = None):
        if sensors is None:
            sensors = []

        if len(self._children) > 0:
            for child in self._children:
                child.get_all_sensors(sensors)
        else:
            sensors.append(self)

        return sensors

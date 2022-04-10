"""Support for Microsoft face recognition."""
from __future__ import annotations

import asyncio
import io
import logging

from azure.cognitiveservices.vision.face import FaceClient
from azure.cognitiveservices.vision.face.models import (
    APIErrorException,
    Person,
    PersonGroup,
)
from msrest.authentication import CognitiveServicesCredentials
import voluptuous as vol

from homeassistant.components import camera
from homeassistant.const import ATTR_NAME, CONF_API_KEY, CONF_TIMEOUT
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.typing import ConfigType
from homeassistant.util import slugify

_LOGGER = logging.getLogger(__name__)

ATTR_CAMERA_ENTITY = "camera_entity"
ATTR_GROUP = "group"
ATTR_PERSON = "person"
ATTR_RECOGNITION_MODEL = "recognition_model"
ATTR_DETECTION_MODEL = "detection_model"

# CONF_AZURE_DETECTION_MODEL = "azure_detection_model"
# CONF_AZURE_RECOGNITION_MODEL = "azure_recognition_model"
CONF_AZURE_REGION = "azure_region"
DEFAULT_AZURE_DETECTION_MODEL = "detection_01"
DEFAULT_AZURE_RECOGNITION_MODEL = "recognition_01"
SUPPORTED_DETECTION_MODEL = ["detection_01", "detection_02", "detection_03"]
SUPPORTED_RECOGNITION_MODELS = [
    "recognition_01",
    "recognition_02",
    "recognition_03",
    "recognition_04",
]

DATA_MICROSOFT_FACE = "microsoft_face"
DEFAULT_TIMEOUT = 10
DOMAIN = "microsoft_face"

FACE_API_URL = "api.cognitive.microsoft.com/face/v1.0/{0}"

SERVICE_CREATE_GROUP = "create_group"
SERVICE_CREATE_PERSON = "create_person"
SERVICE_DELETE_GROUP = "delete_group"
SERVICE_DELETE_PERSON = "delete_person"
SERVICE_FACE_PERSON = "face_person"
SERVICE_TRAIN_GROUP = "train_group"

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Required(CONF_API_KEY): cv.string,
                vol.Optional(CONF_AZURE_REGION, default="westus"): cv.string,
                # vol.Optional(
                #    CONF_AZURE_DETECTION_MODEL, default=DEFAULT_AZURE_DETECTION_MODEL
                # ): cv.string,
                # vol.Optional(
                #    CONF_AZURE_RECOGNITION_MODEL,
                #    default=DEFAULT_AZURE_RECOGNITION_MODEL,
                # ): cv.string,
                vol.Optional(CONF_TIMEOUT, default=DEFAULT_TIMEOUT): cv.positive_int,
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)

SCHEMA_GROUP_SERVICE = vol.Schema(
    {
        vol.Required(ATTR_NAME): cv.string,
        vol.Optional(ATTR_RECOGNITION_MODEL): cv.string,
    }
)

SCHEMA_PERSON_SERVICE = SCHEMA_GROUP_SERVICE.extend(
    {vol.Required(ATTR_GROUP): cv.slugify}
)

SCHEMA_FACE_SERVICE = vol.Schema(
    {
        vol.Required(ATTR_PERSON): cv.string,
        vol.Required(ATTR_GROUP): cv.slugify,
        vol.Required(ATTR_CAMERA_ENTITY): cv.entity_id,
        vol.Optional(ATTR_DETECTION_MODEL): cv.string,
    }
)

SCHEMA_TRAIN_SERVICE = vol.Schema({vol.Required(ATTR_GROUP): cv.slugify})


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up Microsoft Face."""
    entities: dict[str, MicrosoftFaceGroupEntity] = {}
    face = MicrosoftFace(
        hass,
        config[DOMAIN].get(CONF_AZURE_REGION),
        config[DOMAIN].get(CONF_API_KEY),
        config[DOMAIN].get(CONF_TIMEOUT),
        entities,
    )

    try:
        # read exists group/person from cloud and create entities
        await face.update_store()
    except HomeAssistantError as err:
        _LOGGER.error("Can't load data from face api: %s", err)
        return False

    hass.data[DATA_MICROSOFT_FACE] = face

    async def async_create_group(service: ServiceCall) -> None:
        """Create a new person group."""
        name = service.data[ATTR_NAME]
        g_id = slugify(name)
        if ATTR_RECOGNITION_MODEL not in service.data:
            recognition_model = DEFAULT_AZURE_RECOGNITION_MODEL
        else:
            recognition_model = service.data[ATTR_RECOGNITION_MODEL]

        try:
            await hass.async_add_executor_job(
                face.face_client.person_group.create,
                g_id,
                name,
                None,
                recognition_model,
            )

            face.store[g_id] = {}

            entities[g_id] = MicrosoftFaceGroupEntity(
                hass, face, g_id, name, recognition_model
            )
            entities[g_id].async_write_ha_state()
        except APIErrorException as err:
            _LOGGER.error("Can't create group '%s' with error: %s", g_id, err)
        # except HomeAssistantError as err:
        #    _LOGGER.error("Can't create group '%s' with error: %s", g_id, err)

    hass.services.async_register(
        DOMAIN, SERVICE_CREATE_GROUP, async_create_group, schema=SCHEMA_GROUP_SERVICE
    )

    async def async_delete_group(service: ServiceCall) -> None:
        """Delete a person group."""
        g_id = slugify(service.data[ATTR_NAME])

        try:
            await hass.async_add_executor_job(
                face.face_client.person_group.delete, g_id
            )

            face.store.pop(g_id)

            entity = entities.pop(g_id)
            hass.states.async_remove(entity.entity_id, service.context)
        except APIErrorException as err:
            _LOGGER.error("Can't delete group '%s' with error: %s", g_id, err)
        # except HomeAssistantError as err:
        #    _LOGGER.error("Can't delete group '%s' with error: %s", g_id, err)

    hass.services.async_register(
        DOMAIN, SERVICE_DELETE_GROUP, async_delete_group, schema=SCHEMA_GROUP_SERVICE
    )

    async def async_train_group(service: ServiceCall) -> None:
        """Train a person group."""
        g_id = service.data[ATTR_GROUP]

        try:
            await hass.async_add_executor_job(face.face_client.person_group.train, g_id)
        except APIErrorException as err:
            _LOGGER.error("Can't train group '%s' with error: %s", g_id, err)
        # except HomeAssistantError as err:
        #    _LOGGER.error("Can't train group '%s' with error: %s", g_id, err)

    hass.services.async_register(
        DOMAIN, SERVICE_TRAIN_GROUP, async_train_group, schema=SCHEMA_TRAIN_SERVICE
    )

    async def async_create_person(service: ServiceCall) -> None:
        """Create a person in a group."""
        name = service.data[ATTR_NAME]
        g_id = service.data[ATTR_GROUP]

        try:
            person: Person = await hass.async_add_executor_job(
                face.face_client.person_group_person.create, g_id, name
            )

            face.store[g_id][name] = person.person_id
            entities[g_id].async_write_ha_state()
        except APIErrorException as err:
            _LOGGER.error("Can't create person '%s' with error: %s", name, err)
        # except HomeAssistantError as err:
        #    _LOGGER.error("Can't create person '%s' with error: %s", name, err)

    hass.services.async_register(
        DOMAIN, SERVICE_CREATE_PERSON, async_create_person, schema=SCHEMA_PERSON_SERVICE
    )

    async def async_delete_person(service: ServiceCall) -> None:
        """Delete a person in a group."""
        name = service.data[ATTR_NAME]
        g_id = service.data[ATTR_GROUP]
        p_id = face.store[g_id].get(name)

        try:
            await hass.async_add_executor_job(
                face.face_client.person_group_person.delete, g_id, p_id
            )

            face.store[g_id].pop(name)
            entities[g_id].async_write_ha_state()
        except APIErrorException as err:
            _LOGGER.error("Can't delete person '%s' with error: %s", p_id, err)
        # except HomeAssistantError as err:
        #    _LOGGER.error("Can't delete person '%s' with error: %s", p_id, err)

    hass.services.async_register(
        DOMAIN, SERVICE_DELETE_PERSON, async_delete_person, schema=SCHEMA_PERSON_SERVICE
    )

    async def async_face_person(service: ServiceCall) -> None:
        """Add a new face picture to a person."""
        g_id = service.data[ATTR_GROUP]
        p_id = face.store[g_id].get(service.data[ATTR_PERSON])

        if ATTR_DETECTION_MODEL not in service.data:
            detection_model = DEFAULT_AZURE_DETECTION_MODEL
        else:
            detection_model = service.data[ATTR_DETECTION_MODEL]

        camera_entity = service.data[ATTR_CAMERA_ENTITY]

        try:
            image = await camera.async_get_image(hass, camera_entity)

            await hass.async_add_executor_job(
                face.face_client.person_group_person.add_face_from_stream,
                g_id,
                p_id,
                io.BytesIO(bytearray(image.content)),
                None,
                None,
                detection_model,
            )
        except APIErrorException as err:
            _LOGGER.error(
                "Can't add an image of a person '%s' with error: %s", p_id, err
            )
        # except HomeAssistantError as err:
        #    _LOGGER.error(
        #        "Can't add an image of a person '%s' with error: %s", p_id, err
        #    )

    hass.services.async_register(
        DOMAIN, SERVICE_FACE_PERSON, async_face_person, schema=SCHEMA_FACE_SERVICE
    )

    return True


class MicrosoftFaceGroupEntity(Entity):
    """Person-Group state/data Entity."""

    def __init__(
        self, hass, api, g_id, name, recognition_model=DEFAULT_AZURE_RECOGNITION_MODEL
    ):
        """Initialize person/group entity."""
        self.hass = hass
        self._api = api
        self._id = g_id
        self._name = name
        self._recognition_model = recognition_model

    @property
    def name(self):
        """Return the name of the entity."""
        return self._name

    @property
    def entity_id(self):
        """Return entity id."""
        return f"{DOMAIN}.{self._id}"

    @property
    def state(self):
        """Return the state of the entity."""
        return len(self._api.store[self._id])

    @property
    def should_poll(self):
        """Return True if entity has to be polled for state."""
        return False

    @property
    def state_attributes(self):
        """Return device specific state attributes."""
        return {ATTR_RECOGNITION_MODEL: self._recognition_model}

    @property
    def extra_state_attributes(self):
        """Return device specific state attributes."""
        attr = {}
        for name, p_id in self._api.store[self._id].items():
            attr[name] = p_id

        return attr


class MicrosoftFace:
    """Microsoft Face api for Home Assistant."""

    def __init__(
        self,
        hass,
        server_loc,
        # detection_model,
        # recognition_model,
        api_key,
        timeout,
        entities,
    ):
        """Initialize Microsoft Face api."""
        self.hass = hass
        self.websession = async_get_clientsession(hass)
        self.timeout = timeout
        self._api_key = api_key
        self._server_url = f"https://{server_loc}.{FACE_API_URL}"
        # self._detection_model = detection_model
        # self._recognition_model = recognition_model
        self._store = {}
        self._entities = entities
        self._azure_endpoint = f"https://{server_loc}.api.cognitive.microsoft.com"
        self.face_client = FaceClient(
            self._azure_endpoint, CognitiveServicesCredentials(self._api_key)
        )

    # @property
    # def detection_model(self):
    #    """Return Azure detectionModel."""
    #    return self._detection_model

    # @property
    # def recognition_model(self):
    #    """Return Azure recognitionModel."""
    #    return self._recognition_model

    @property
    def store(self):
        """Store group/person data and IDs."""
        return self._store

    async def update_store(self):
        """Load all group/person data into local store."""
        groups: PersonGroup = await self.hass.async_add_executor_job(
            self.face_client.person_group.list, None, None, True
        )

        tasks = []
        group: PersonGroup
        for group in groups:
            self._store[group.person_group_id] = {}
            self._entities[group.person_group_id] = MicrosoftFaceGroupEntity(
                self.hass,
                self,
                group.person_group_id,
                group.name,
                group.recognition_model,
            )

            persons: Person = await self.hass.async_add_executor_job(
                self.face_client.person_group_person.list, group.person_group_id
            )

            person: Person
            for person in persons:
                self._store[group.person_group_id][person.name] = person.person_id

            tasks.append(
                asyncio.create_task(
                    self._entities[group.person_group_id].async_update_ha_state()
                )
            )

        if tasks:
            await asyncio.wait(tasks)

"""Component that will help set the Microsoft face for verify processing."""
from __future__ import annotations

import io
import logging

from azure.cognitiveservices.vision.face.models import APIErrorException
import voluptuous as vol

from homeassistant.components.image_processing import (
    ATTR_CONFIDENCE,
    CONF_CONFIDENCE,
    PLATFORM_SCHEMA,
    ImageProcessingFaceEntity,
)
from homeassistant.components.microsoft_face import (
    ATTR_RECOGNITION_MODEL,
    DATA_MICROSOFT_FACE,
    DEFAULT_AZURE_DETECTION_MODEL,
    DEFAULT_AZURE_RECOGNITION_MODEL,
    SUPPORTED_DETECTION_MODEL,
    MicrosoftFace,
    MicrosoftFaceGroupEntity,
)
from homeassistant.const import ATTR_NAME, CONF_ENTITY_ID, CONF_NAME, CONF_SOURCE
from homeassistant.core import HomeAssistant, split_entity_id
from homeassistant.exceptions import HomeAssistantError
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

_LOGGER = logging.getLogger(__name__)

CONF_GROUP = "group"
CONF_DETECTION_MODEL = "detection_model"


def validate_detection_model(detection_model):
    """Validate face detection_model."""
    if detection_model not in SUPPORTED_DETECTION_MODEL:
        raise vol.Invalid(f"Invalid attribute {detection_model}")
    return detection_model


PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_GROUP): cv.slugify,
        vol.Optional(
            CONF_DETECTION_MODEL, default=DEFAULT_AZURE_DETECTION_MODEL
        ): vol.All(cv.string, validate_detection_model),
    }
)


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the Microsoft Face identify platform."""
    api = hass.data[DATA_MICROSOFT_FACE]
    face_group = config[CONF_GROUP]
    confidence = config[CONF_CONFIDENCE]
    detection_model = config[CONF_DETECTION_MODEL]

    entities = []
    for camera in config[CONF_SOURCE]:
        entities.append(
            MicrosoftFaceIdentifyEntity(
                camera[CONF_ENTITY_ID],
                api,
                face_group,
                confidence,
                detection_model,
                camera.get(CONF_NAME),
            )
        )

    async_add_entities(entities)


class MicrosoftFaceIdentifyEntity(ImageProcessingFaceEntity):
    """Representation of the Microsoft Face API entity for identify."""

    def __init__(
        self, camera_entity, api, face_group, confidence, detection_model, name=None
    ):
        """Initialize the Microsoft Face API."""
        super().__init__()

        self._api: MicrosoftFace = api
        self._camera = camera_entity
        self._confidence = confidence
        self._face_group = face_group
        self._detection_model = detection_model
        self._recognition_model = DEFAULT_AZURE_RECOGNITION_MODEL

        if name:
            self._name = name
        else:
            self._name = f"MicrosoftFace {split_entity_id(camera_entity)[1]}"

        # read state_attributes 'recognition_model' from entity
        for item in self._api._entities.items():
            group: MicrosoftFaceGroupEntity = item[1]
            if group._id == self._face_group:
                if ATTR_RECOGNITION_MODEL in group.state_attributes:
                    self._recognition_model = group.state_attributes[
                        ATTR_RECOGNITION_MODEL
                    ]
                break

    @property
    def confidence(self):
        """Return minimum confidence for send events."""
        return self._confidence

    @property
    def camera_entity(self):
        """Return camera entity id from process pictures."""
        return self._camera

    @property
    def name(self):
        """Return the name of the entity."""
        return self._name

    async def async_process_image(self, image):
        """Process image.

        This method is a coroutine.
        """
        detect = []
        try:
            # face_data = await self._api.call_api(
            #     "post",
            #     "detect",
            #     image,
            #     binary=True,
            #     params={
            #         "detectionModel": self._api.detection_model,
            #         "recognitionModel": self._api.recognition_model,
            #     },
            # )
            detected_face = await self.hass.async_add_executor_job(
                self._api.face_client.face.detect_with_stream,
                io.BytesIO(bytearray(image)),
                True,
                False,
                None,
                self._recognition_model,
                True,
                self._detection_model,
            )

            # if face_data:
            #     face_ids = [data["faceId"] for data in face_data]
            #     detect = await self._api.call_api(
            #         "post",
            #         "identify",
            #         {"faceIds": face_ids, "personGroupId": self._face_group},
            #     )
            if detected_face:
                face_ids = []
                for data in detected_face:
                    face_ids.append(data.face_id)
                # face_ids = [data["faceId"] for data in detected_face]
                detect = await self.hass.async_add_executor_job(
                    self._api.face_client.face.identify, face_ids, self._face_group
                )
        except APIErrorException as err:
            _LOGGER.error("Can't process image on Microsoft face: %s", err)
            return
        except HomeAssistantError as err:
            _LOGGER.error("Can't process image on Microsoft face: %s", err)
            return

        # Parse data
        known_faces = []
        total = 0
        for face in detect:
            total += 1
            if not face.candidates:
                continue

            data = face.candidates[0]
            name = ""
            for s_name, s_id in self._api.store[self._face_group].items():
                if data.person_id == s_id:
                    name = s_name
                    break

            known_faces.append(
                {ATTR_NAME: name, ATTR_CONFIDENCE: data.confidence * 100}
            )

        self.async_process_faces(known_faces, total)

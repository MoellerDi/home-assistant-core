"""Component that will help set the Microsoft face detect processing."""
from __future__ import annotations

import io
import logging

from azure.cognitiveservices.vision.face import FaceClient
from azure.cognitiveservices.vision.face.models import (
    APIErrorException,
    DetectedFace,
    DetectionModel,
    FaceAttributes,
)
import voluptuous as vol

from homeassistant.components.camera import Camera
from homeassistant.components.image_processing import (
    ATTR_AGE,
    ATTR_GENDER,
    ATTR_GLASSES,
    PLATFORM_SCHEMA,
    ImageProcessingFaceEntity,
)
from homeassistant.components.microsoft_face import (
    DATA_MICROSOFT_FACE,
    DEFAULT_AZURE_DETECTION_MODEL,
    SUPPORTED_DETECTION_MODEL,
)
from homeassistant.const import CONF_ENTITY_ID, CONF_NAME, CONF_SOURCE
from homeassistant.core import HomeAssistant, split_entity_id
from homeassistant.exceptions import HomeAssistantError
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

_LOGGER = logging.getLogger(__name__)

ATTR_ACCESSORIES = "accessories"
ATTR_BLUR = "blur"
ATTR_EMOTION = "emotion"
ATTR_EXPOSURE = "exposure"
ATTR_FACIAL_HAIR = "facialHair"
ATTR_HAIR = "hair"
ATTR_HEADPOSE = "headPose"
ATTR_MAKEUP = "makeup"
ATTR_MASK = "mask"
ATTR_NOISE = "noise"
ATTR_OCCLUSION = "occlusion"
ATTR_QUALITY_FOR_RECOGNITION = "qualityForRecognition"
ATTR_SMILE = "smile"

SUPPORTED_ATTRIBUTES = [
    ATTR_ACCESSORIES,
    ATTR_AGE,
    ATTR_BLUR,
    ATTR_EMOTION,
    ATTR_EXPOSURE,
    ATTR_FACIAL_HAIR,
    ATTR_GENDER,
    ATTR_GLASSES,
    ATTR_HAIR,
    ATTR_HEADPOSE,
    ATTR_MAKEUP,
    ATTR_MASK,
    ATTR_NOISE,
    ATTR_OCCLUSION,
    ATTR_QUALITY_FOR_RECOGNITION,
    ATTR_SMILE,
]

CONF_ATTRIBUTES = "attributes"
CONF_DETECTION_MODEL = "detection_model"
DEFAULT_ATTRIBUTES = [ATTR_AGE, ATTR_GENDER]


def validate_attributes(list_attributes):
    """Validate face attributes."""
    for attr in list_attributes:
        if attr not in SUPPORTED_ATTRIBUTES:
            raise vol.Invalid(f"Invalid attribute {attr}")
    return list_attributes


def validate_detection_model(detection_model):
    """Validate face detection_model."""
    if detection_model not in SUPPORTED_DETECTION_MODEL:
        raise vol.Invalid(f"Invalid attribute {detection_model}")
    return detection_model


PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Optional(CONF_ATTRIBUTES, default=DEFAULT_ATTRIBUTES): vol.All(
            cv.ensure_list, validate_attributes
        ),
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
    """Set up the Microsoft Face detection platform."""
    api = hass.data[DATA_MICROSOFT_FACE]
    attributes = config[CONF_ATTRIBUTES]
    detection_model = config[CONF_DETECTION_MODEL]

    entities = []
    for camera in config[CONF_SOURCE]:
        entities.append(
            MicrosoftFaceDetectEntity(
                camera[CONF_ENTITY_ID],
                api,
                attributes,
                detection_model,
                camera.get(CONF_NAME),
            )
        )

    async_add_entities(entities)


class MicrosoftFaceDetectEntity(ImageProcessingFaceEntity):
    """Microsoft Face API entity for identify."""

    def __init__(self, camera_entity, api, attributes, detection_model, name=None):
        """Initialize Microsoft Face."""
        super().__init__()

        self._face_client: FaceClient = api.face_client
        self._camera: Camera = camera_entity
        self._attributes: FaceAttributes = attributes
        self._detection_model: DetectionModel = detection_model

        if name:
            self._name = name
        else:
            self._name = f"MicrosoftFace {split_entity_id(camera_entity)[1]}"

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
        try:
            detected_faces: DetectedFace = await self.hass.async_add_executor_job(
                self._face_client.face.detect_with_stream,
                io.BytesIO(bytearray(image)),
                True,
                False,
                self._attributes,
                None,
                True,
                self._detection_model,
            )
        except APIErrorException as err:
            _LOGGER.error("Can't process image on microsoft face: %s", err)
            return
        except HomeAssistantError as err:
            _LOGGER.error("Can't process image on microsoft face: %s", err)
            return

        faces = []
        face: DetectedFace
        for face in detected_faces:
            face_attr = {}
            for attr in self._attributes:
                if attr in face.face_attributes.as_dict():
                    face_attr[attr] = face.face_attributes.as_dict()[attr]

            if face_attr:
                faces.append(face_attr)

        self.async_process_faces(faces, len(detected_faces))

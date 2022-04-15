"""The tests for the microsoft face platform."""
from unittest.mock import MagicMock, Mock, patch

from azure.cognitiveservices.vision.face import FaceClient
from azure.cognitiveservices.vision.face.models import Person, PersonGroup
from msrest.authentication import CognitiveServicesCredentials

from homeassistant.components import camera, microsoft_face as mf
from homeassistant.components.microsoft_face import (
    ATTR_CAMERA_ENTITY,
    ATTR_GROUP,
    ATTR_PERSON,
    CONF_AZURE_REGION,
    DOMAIN,
    SERVICE_CREATE_GROUP,
    SERVICE_CREATE_PERSON,
    SERVICE_DELETE_GROUP,
    SERVICE_DELETE_PERSON,
    SERVICE_FACE_PERSON,
    SERVICE_TRAIN_GROUP,
)
from homeassistant.const import ATTR_NAME, CONF_API_KEY, CONF_TIMEOUT
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry

# def create_group(hass, name):
#     """Create a new person group.

#     This is a legacy helper method. Do not use it for new tests.
#     """
#     data = {ATTR_NAME: name}
#     hass.async_create_task(hass.services.async_call(DOMAIN, SERVICE_CREATE_GROUP, data))


# def delete_group(hass, name):
#     """Delete a person group.

#     This is a legacy helper method. Do not use it for new tests.
#     """
#     data = {ATTR_NAME: name}
#     hass.async_create_task(hass.services.async_call(DOMAIN, SERVICE_DELETE_GROUP, data))


# def train_group(hass, group):
#     """Train a person group.

#     This is a legacy helper method. Do not use it for new tests.
#     """
#     data = {ATTR_GROUP: group}
#     hass.async_create_task(hass.services.async_call(DOMAIN, SERVICE_TRAIN_GROUP, data))


# def create_person(hass, group, name):
#     """Create a person in a group.

#     This is a legacy helper method. Do not use it for new tests.
#     """
#     data = {ATTR_GROUP: group, ATTR_NAME: name}
#     hass.async_create_task(
#         hass.services.async_call(DOMAIN, SERVICE_CREATE_PERSON, data)
#     )


# def delete_person(hass, group, name):
#     """Delete a person in a group.

#     This is a legacy helper method. Do not use it for new tests.
#     """
#     data = {ATTR_GROUP: group, ATTR_NAME: name}
#     hass.async_create_task(
#         hass.services.async_call(DOMAIN, SERVICE_DELETE_PERSON, data)
#     )


# def face_person(hass, group, person, camera_entity):
#     """Add a new face picture to a person.

#     This is a legacy helper method. Do not use it for new tests.
#     """
#     data = {ATTR_GROUP: group, ATTR_PERSON: person, ATTR_CAMERA_ENTITY: camera_entity}
#     hass.async_create_task(hass.services.async_call(DOMAIN, SERVICE_FACE_PERSON, data))


CONFIG = {
    mf.DOMAIN: {
        "api_key": "12345678abcdef",
        CONF_AZURE_REGION: "westus",
        CONF_TIMEOUT: 22,
    }
}
ENDPOINT_URL = f"https://westus.{mf.FACE_API_URL}"


# @pytest.fixture
# def mock_update():
#     """Mock update store."""
#     with patch(
#         "homeassistant.components.microsoft_face.MicrosoftFace.update_store",
#         return_value=None,
#     ) as mock_update_store:
#         yield mock_update_store


# async def test_setup_component(hass, mock_update):
#     """Set up component."""
#     with assert_setup_component(3, mf.DOMAIN):
#         assert await async_setup_component(hass, mf.DOMAIN, CONFIG)


# async def test_setup_component_wrong_api_key(hass, mock_update):
#     """Set up component without api key."""
#     with assert_setup_component(0, mf.DOMAIN):
#         await async_setup_component(hass, mf.DOMAIN, {mf.DOMAIN: {}})


async def test_setup_component(hass: HomeAssistant) -> None:
    """Test initialization of the integration with some default data."""
    face_client_mock = await init_integration(hass, CONFIG)

    face_client_mock.person_group.list.assert_called_once()
    face_client_mock.person_group_person.list.assert_called_once()

    entity_group1 = hass.states.get("microsoft_face.test_group1")
    assert entity_group1 is not None
    assert "person1" in entity_group1.attributes


async def test_setup_component_test_service(hass: HomeAssistant) -> None:
    """Set up component."""
    await init_integration(hass, CONFIG)

    assert hass.services.has_service(mf.DOMAIN, "create_group")
    assert hass.services.has_service(mf.DOMAIN, "delete_group")
    assert hass.services.has_service(mf.DOMAIN, "train_group")
    assert hass.services.has_service(mf.DOMAIN, "create_person")
    assert hass.services.has_service(mf.DOMAIN, "delete_person")
    assert hass.services.has_service(mf.DOMAIN, "face_person")


async def test_service_create_group(hass: HomeAssistant) -> None:
    """Set up component, test delete a person group service."""
    face_client_mock = await init_integration(hass, CONFIG)

    group_name = "test_group2"

    entity_group = hass.states.get(f"microsoft_face.{group_name}")
    assert entity_group is None

    data = {ATTR_NAME: group_name}
    hass.async_create_task(hass.services.async_call(DOMAIN, SERVICE_CREATE_GROUP, data))
    await hass.async_block_till_done()

    face_client_mock.person_group.create.assert_called_once()
    entity_group = hass.states.get(f"microsoft_face.{group_name}")
    assert entity_group is not None


async def test_service_delete_group(hass: HomeAssistant) -> None:
    """Set up component, test delete a person group service."""
    face_client_mock = await init_integration(hass, CONFIG)

    group_name = "test_group1"

    entity_group = hass.states.get(f"microsoft_face.{group_name}")
    assert entity_group is not None

    data = {ATTR_NAME: group_name}
    hass.async_create_task(hass.services.async_call(DOMAIN, SERVICE_DELETE_GROUP, data))
    await hass.async_block_till_done()

    face_client_mock.person_group.delete.assert_called_once()
    entity_group = hass.states.get(f"microsoft_face.{group_name}")
    assert entity_group is None


async def test_service_train_group(hass: HomeAssistant) -> None:
    """Set up component, test train group service."""
    face_client_mock = await init_integration(hass, CONFIG)

    group = "test_group1"
    data = {ATTR_GROUP: group}
    hass.async_create_task(hass.services.async_call(DOMAIN, SERVICE_TRAIN_GROUP, data))
    await hass.async_block_till_done()

    face_client_mock.person_group.train.assert_called_once()


async def test_service_delete_person(hass: HomeAssistant) -> None:
    """Set up component, test delete person service."""
    face_client_mock = await init_integration(hass, CONFIG)

    group = "test_group1"
    person = "person1"

    entity_group1 = hass.states.get(f"microsoft_face.{group}")
    assert entity_group1 is not None
    assert person in entity_group1.attributes

    data = {ATTR_GROUP: group, ATTR_NAME: person}
    hass.async_create_task(
        hass.services.async_call(DOMAIN, SERVICE_DELETE_PERSON, data)
    )
    await hass.async_block_till_done()

    face_client_mock.person_group_person.delete.assert_called_once()
    entity_group1 = hass.states.get(f"microsoft_face.{group}")
    assert entity_group1 is not None
    assert person not in entity_group1.attributes


async def test_service_create_person(hass: HomeAssistant) -> None:
    """Set up component, test create person service."""
    face_client_mock = await init_integration(hass, CONFIG)

    group = "test_group1"
    person = "person1"

    data = {ATTR_GROUP: group, ATTR_NAME: person}
    hass.async_create_task(
        hass.services.async_call(DOMAIN, SERVICE_CREATE_PERSON, data)
    )
    await hass.async_block_till_done()

    face_client_mock.person_group_person.create.assert_called_once()
    entity_group1 = hass.states.get(f"microsoft_face.{group}")
    assert entity_group1 is not None
    assert person in entity_group1.attributes


async def test_service_face_person(hass: HomeAssistant) -> None:
    """Set up component, test add a new face picture to a person service."""
    CONFIG["camera"] = {"platform": "demo"}

    patch(
        "homeassistant.components.camera.async_get_image",
        return_value=camera.Image("image/jpeg", b"Test"),
    )

    face_client_mock = await init_integration(hass, CONFIG)

    group = "test_group1"
    person = "person1"
    camera_entity = "camera.demo_camera"
    data = {ATTR_GROUP: group, ATTR_PERSON: person, ATTR_CAMERA_ENTITY: camera_entity}

    hass.async_create_task(hass.services.async_call(DOMAIN, SERVICE_FACE_PERSON, data))
    await hass.async_block_till_done()

    face_client_mock.person_group_person.add_face_from_stream.assert_called_once()


# async def test_setup_component_test_entities(
#     hass: HomeAssistant, aioclient_mock, mock_update
# ):
#     """Set up component."""

#     aioclient_mock.get(
#         ENDPOINT_URL.format("persongroups"),
#         text=load_fixture("microsoft_face_persongroups.json"),
#     )
#     aioclient_mock.get(
#         ENDPOINT_URL.format("persongroups/test_group1/persons"),
#         text=load_fixture("microsoft_face_persons.json"),
#     )
#     aioclient_mock.get(
#         ENDPOINT_URL.format("persongroups/test_group2/persons"),
#         text=load_fixture("microsoft_face_persons.json"),
#     )

#     with assert_setup_component(3, mf.DOMAIN):
#         await async_setup_component(hass, mf.DOMAIN, CONFIG)

#     assert len(aioclient_mock.mock_calls) == 3

#     entity_group1 = hass.states.get("microsoft_face.test_group1")
#     entity_group2 = hass.states.get("microsoft_face.test_group2")

#     assert entity_group1 is not None
#     assert entity_group2 is not None

#     assert entity_group1.attributes["Ryan"] == "25985303-c537-4467-b41d-bdb45cd95ca1"
#     assert entity_group1.attributes["David"] == "2ae4935b-9659-44c3-977f-61fac20d0538"

#     assert entity_group2.attributes["Ryan"] == "25985303-c537-4467-b41d-bdb45cd95ca1"
#     assert entity_group2.attributes["David"] == "2ae4935b-9659-44c3-977f-61fac20d0538"


# async def test_service_groups(hass, mock_update, aioclient_mock):
#     """Set up component, test groups services."""
#     aioclient_mock.put(
#         ENDPOINT_URL.format("persongroups/service_group"),
#         status=200,
#         text="{}",
#     )
#     aioclient_mock.delete(
#         ENDPOINT_URL.format("persongroups/service_group"),
#         status=200,
#         text="{}",
#     )

#     with assert_setup_component(3, mf.DOMAIN):
#         await async_setup_component(hass, mf.DOMAIN, CONFIG)

#     create_group(hass, "Service Group")
#     await hass.async_block_till_done()

#     entity = hass.states.get("microsoft_face.service_group")
#     assert entity is not None
#     assert len(aioclient_mock.mock_calls) == 1

#     delete_group(hass, "Service Group")
#     await hass.async_block_till_done()

#     entity = hass.states.get("microsoft_face.service_group")
#     assert entity is None
#     assert len(aioclient_mock.mock_calls) == 2


# async def test_service_person(hass, aioclient_mock):
#     """Set up component, test person services."""
#     aioclient_mock.get(
#         ENDPOINT_URL.format("persongroups"),
#         text=load_fixture("microsoft_face_persongroups.json"),
#     )
#     aioclient_mock.get(
#         ENDPOINT_URL.format("persongroups/test_group1/persons"),
#         text=load_fixture("microsoft_face_persons.json"),
#     )
#     aioclient_mock.get(
#         ENDPOINT_URL.format("persongroups/test_group2/persons"),
#         text=load_fixture("microsoft_face_persons.json"),
#     )

#     with assert_setup_component(3, mf.DOMAIN):
#         await async_setup_component(hass, mf.DOMAIN, CONFIG)

#     assert len(aioclient_mock.mock_calls) == 3

#     aioclient_mock.post(
#         ENDPOINT_URL.format("persongroups/test_group1/persons"),
#         text=load_fixture("microsoft_face_create_person.json"),
#     )
#     aioclient_mock.delete(
#         ENDPOINT_URL.format(
#             "persongroups/test_group1/persons/25985303-c537-4467-b41d-bdb45cd95ca1"
#         ),
#         status=200,
#         text="{}",
#     )

#     create_person(hass, "test group1", "Hans")
#     await hass.async_block_till_done()

#     entity_group1 = hass.states.get("microsoft_face.test_group1")

#     assert len(aioclient_mock.mock_calls) == 4
#     assert entity_group1 is not None
#     assert entity_group1.attributes["Hans"] == "25985303-c537-4467-b41d-bdb45cd95ca1"

#     delete_person(hass, "test group1", "Hans")
#     await hass.async_block_till_done()

#     entity_group1 = hass.states.get("microsoft_face.test_group1")

#     assert len(aioclient_mock.mock_calls) == 5
#     assert entity_group1 is not None
#     assert "Hans" not in entity_group1.attributes


# async def test_service_train(hass, mock_update, aioclient_mock):
#     """Set up component, test train groups services."""
#     with assert_setup_component(3, mf.DOMAIN):
#         await async_setup_component(hass, mf.DOMAIN, CONFIG)

#     aioclient_mock.post(
#         ENDPOINT_URL.format("persongroups/service_group/train"),
#         status=200,
#         text="{}",
#     )

#     train_group(hass, "Service Group")
#     await hass.async_block_till_done()

#     assert len(aioclient_mock.mock_calls) == 1


# async def test_service_face(hass, aioclient_mock):
#     """Set up component, test person face services."""
#     aioclient_mock.get(
#         ENDPOINT_URL.format("persongroups"),
#         text=load_fixture("microsoft_face_persongroups.json"),
#     )
#     aioclient_mock.get(
#         ENDPOINT_URL.format("persongroups/test_group1/persons"),
#         text=load_fixture("microsoft_face_persons.json"),
#     )
#     aioclient_mock.get(
#         ENDPOINT_URL.format("persongroups/test_group2/persons"),
#         text=load_fixture("microsoft_face_persons.json"),
#     )

#     CONFIG["camera"] = {"platform": "demo"}
#     with assert_setup_component(3, mf.DOMAIN):
#         await async_setup_component(hass, mf.DOMAIN, CONFIG)

#     assert len(aioclient_mock.mock_calls) == 3

#     aioclient_mock.post(
#         ENDPOINT_URL.format(
#             "persongroups/test_group2/persons/"
#             "2ae4935b-9659-44c3-977f-61fac20d0538/persistedFaces"
#         ),
#         status=200,
#         text="{}",
#     )

#     with patch(
#         "homeassistant.components.camera.async_get_image",
#         return_value=camera.Image("image/jpeg", b"Test"),
#     ):
#         face_person(hass, "test_group2", "David", "camera.demo_camera")
#         await hass.async_block_till_done()

#     assert len(aioclient_mock.mock_calls) == 4
#     assert aioclient_mock.mock_calls[3][2] == b"Test"


# async def test_service_status_400(hass, mock_update, aioclient_mock):
#     """Set up component, test groups services with error."""
#     aioclient_mock.put(
#         ENDPOINT_URL.format("persongroups/service_group"),
#         status=400,
#         text="{'error': {'message': 'Error'}}",
#     )

#     with assert_setup_component(3, mf.DOMAIN):
#         await async_setup_component(hass, mf.DOMAIN, CONFIG)

#     create_group(hass, "Service Group")
#     await hass.async_block_till_done()

#     entity = hass.states.get("microsoft_face.service_group")
#     assert entity is None
#     assert len(aioclient_mock.mock_calls) == 1


# async def test_service_status_timeout(hass, mock_update, aioclient_mock):
#     """Set up component, test groups services with timeout."""
#     aioclient_mock.put(
#         ENDPOINT_URL.format("persongroups/service_group"),
#         status=400,
#         exc=asyncio.TimeoutError(),
#     )

#     with assert_setup_component(3, mf.DOMAIN):
#         await async_setup_component(hass, mf.DOMAIN, CONFIG)

#     create_group(hass, "Service Group")
#     await hass.async_block_till_done()

#     entity = hass.states.get("microsoft_face.service_group")
#     assert entity is None
#     assert len(aioclient_mock.mock_calls) == 1


async def init_integration(hass: HomeAssistant, config) -> MockConfigEntry:
    """Set up the Mazda Connected Services integration in Home Assistant."""
    config_entry = MockConfigEntry(domain=DOMAIN, data=config)
    config_entry.add_to_hass(hass)

    face_client_mock = MagicMock(
        FaceClient(
            "https://westus.api.cognitive.microsoft.com",
            CognitiveServicesCredentials(config[DOMAIN].get(CONF_API_KEY)),
        )
    )

    face_client_mock.person_group.list = Mock(
        return_value=[
            PersonGroup(
                name="test_group1",
                person_group_id="test_group1",
                recognition_model="recognition_01",
            )
        ]
    )
    face_client_mock.person_group_person.list = Mock(
        return_value=[
            Person(
                name="person1",
                person_id="person1",
            )
        ]
    )

    with patch(
        "homeassistant.components.microsoft_face.FaceClient",
        return_value=face_client_mock,
    ):
        assert await async_setup_component(hass, mf.DOMAIN, CONFIG)
    await hass.async_block_till_done()

    return face_client_mock

import uuid
from typing import Any, Mapping, Sequence

import pytest
from fastapi.testclient import TestClient

from examples.siren import Person
from fastapi_hypermodel import get_siren_action, get_siren_link, SirenActionType


@pytest.fixture()
def people_uri() -> str:
    return "/people"


@pytest.fixture()
def find_uri_template(siren_client: TestClient, people_uri: str) -> SirenActionType:
    reponse = siren_client.get(people_uri).json()
    find_uri = get_siren_action(reponse, "find")
    assert find_uri
    return find_uri


@pytest.fixture()
def update_uri_template(siren_client: TestClient, people_uri: str) -> SirenActionType:
    reponse = siren_client.get(people_uri).json()
    update_uri = get_siren_action(reponse, "update")
    assert update_uri
    return update_uri

@pytest.fixture()
def person_response(
    siren_client: TestClient,
    find_uri_template: SirenActionType,
    person: Person
) -> Mapping[str, Any]:
    find_uri = person.parse_uri(find_uri_template.href)

    assert find_uri_template.method

    return siren_client.request(find_uri_template.method, find_uri).json()


def test_people_content_type(siren_client: TestClient, people_uri: str) -> None:
    response = siren_client.get(people_uri)
    content_type = response.headers.get("content-type")
    assert content_type == "application/siren+json"


def test_get_people(siren_client: TestClient, people_uri: str) -> None:
    response = siren_client.get(people_uri).json()

    people = response.get("entities", [])
    assert len(people) == 2
    assert all(person.get("rel") == "people" for person in people)

    self_uri = get_siren_link(response, "self")
    assert self_uri
    assert self_uri.href == people_uri

    find_uri = get_siren_action(response, "find")
    assert find_uri
    assert find_uri.templated
    assert people_uri in find_uri.href


def test_get_person(
    person_response: Mapping[str, Any],
    person: Person,
    people_uri: str,
) -> None:
    person_self_link = get_siren_link(person_response, "self")
    
    assert person_self_link

    assert people_uri in person_self_link.href

    assert person.properties

    person_id = person.properties.get("id_", "")
    assert person_id in person_self_link.href
    assert person_response.get("properties", {}).get("id_") == person_id

    entities = person_response.get("entities")
    assert entities
    assert len(entities) == 2


def test_update_person_from_uri_template(
    siren_client: TestClient,
    person_response: Mapping[str, Any],
    update_uri_template: SirenActionType,
    person: Person,
) -> None:
    new_data = {"name": f"updated_{uuid.uuid4().hex}"}

    update_uri = person.parse_uri(update_uri_template.href)

    assert update_uri_template.method
    response = siren_client.request(update_uri_template.method, update_uri, json=new_data).json()

    assert response.get("properties").get("name") == new_data.get("name")
    assert response.get("properties").get("name") != person_response.get("name")

    person_response_uri = get_siren_link(person_response, "self")
    after_uri = get_siren_link(response, "self")
    
    assert person_response_uri
    assert after_uri
    assert person_response_uri.href == after_uri.href


def test_update_person_from_update_uri(
    siren_client: TestClient, person_response: Mapping[str, Any]
) -> None:
    new_data = {"name": f"updated_{uuid.uuid4().hex}"}

    update_action = get_siren_action(person_response, "update")
    assert update_action
    assert update_action.method
    response = siren_client.request(update_action.method, update_action.href, json=new_data).json()

    assert response.get("properties").get("name") == new_data.get("name")
    assert response.get("properties").get("name") != person_response.get("name")

    person_response_uri = get_siren_link(person_response, "self")
    after_uri = get_siren_link(response, "self")

    assert person_response_uri
    assert after_uri
    assert person_response_uri.href == after_uri.href


def test_get_person_items(
    siren_client: TestClient, person_response: Mapping[str, Any]
) -> None:
    person_items: Sequence[Mapping[str, str]] = person_response.get("entities", [])

    assert person_items
    assert isinstance(person_items, list)
    assert all(item.get("rel") == "items" for item in person_items)

    first_item, *_ = person_items
    first_item_uri = get_siren_link(first_item, "self")
    assert first_item_uri
    first_item_response = siren_client.get(first_item_uri.href).json()
    first_item_response.update({"rel": "items"})

    assert first_item == first_item_response


@pytest.fixture()
def existing_item() -> Any:
    return {"id_": "item04"}


@pytest.fixture()
def non_existing_item() -> Any:
    return {"id_": "item05"}


def test_add_item_to_unlocked_person(
    siren_client: TestClient,
    find_uri_template: SirenActionType,
    unlocked_person: Person,
    existing_item: Any,
) -> None:
    find_uri = unlocked_person.parse_uri(find_uri_template.href)

    assert find_uri_template.method
    before = siren_client.request(find_uri_template.method, find_uri).json()

    before_items = before.get("entities", {})
    add_item_action = get_siren_action(before, "add_item")

    assert add_item_action
    assert add_item_action.method
    assert add_item_action.fields

    for required_field in add_item_action.fields:
        assert existing_item.get(required_field.name)

    after = siren_client.request(
        add_item_action.method, add_item_action.href, json=existing_item
    ).json()
    after_items = after.get("entities", {})
    assert after_items

    lenght_before = len(before_items)
    lenght_after = len(after_items)
    assert lenght_before + 1 == lenght_after

    assert after_items[-1].get("properties").get("id_") == existing_item.get("id_")


def test_add_item_to_unlocked_person_nonexisting_item(
    siren_client: TestClient,
    find_uri_template: SirenActionType,
    unlocked_person: Person,
    non_existing_item: Any,
) -> None:
    find_uri = unlocked_person.parse_uri(find_uri_template.href)

    assert find_uri_template.method

    before = siren_client.request(find_uri_template.method, find_uri).json()

    add_item_action = get_siren_action(before, "add_item")

    assert add_item_action
    assert add_item_action.method

    response = siren_client.request(
        add_item_action.method, add_item_action.href, json=non_existing_item
    )

    assert response.status_code == 404
    assert response.json() == {"detail": "No item found with id item05"}


def test_add_item_to_locked_person(
    siren_client: TestClient,
    find_uri_template: SirenActionType,
    locked_person: Person,
) -> None:
    find_uri = locked_person.parse_uri(find_uri_template.href)

    assert find_uri_template.method

    before = siren_client.request(find_uri_template.method, find_uri).json()

    add_item_action = get_siren_link(before, "add_item")

    assert not add_item_action

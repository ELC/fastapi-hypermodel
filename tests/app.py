from typing import List, Optional, ClassVar

from fastapi import FastAPI
from pydantic import ConfigDict, Field
from pydantic.main import BaseModel

from fastapi_hypermodel import HyperModel, LinkSet, UrlFor
from fastapi_hypermodel.hypermodel import HALFor


class ItemSummary(HyperModel):
    name: str
    id: str

    href: UrlFor = UrlFor("read_item", {"item_id": "<id>"})


class ItemDetail(ItemSummary):
    description: Optional[str] = None
    price: float


class ItemUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    price: Optional[float] = None


class ItemCreate(ItemUpdate):
    id: str


class Person(HyperModel):
    model_config = ConfigDict(str_max_length=10)

    name: str
    id: str
    is_locked: bool
    items: List[ItemSummary]

    href: UrlFor = UrlFor("read_person", {"person_id": "<id>"})
    links: LinkSet = LinkSet(
        {
            "self": UrlFor("read_person", {"person_id": "<id>"}),
            "items": UrlFor("read_person_items", {"person_id": "<id>"}),
            "addItem": UrlFor(
                "put_person_items",
                {"person_id": "<id>"},
                condition=lambda values: not values["is_locked"],
            ),
        }
    )

    hal_href: HALFor = HALFor("read_person", {"person_id": "<id>"})
    hal_links: LinkSet = Field(
        default=LinkSet(
            {
                "self": HALFor("read_person", {"person_id": "<id>"}),
                "items": HALFor("read_person_items", {"person_id": "<id>"}),
                "addItem": HALFor(
                    "put_person_items",
                    {"person_id": "<id>"},
                    description="Add an item to this person and the items list",
                    condition=lambda values: not values["is_locked"],
                ),
            }
        ),
        alias="_links",
    )


items = {
    "item01": {"id": "item01", "name": "Foo", "price": 50.2},
    "item02": {
        "id": "item02",
        "name": "Bar",
        "description": "The Bar fighters",
        "price": 62,
    },
    "item03": {
        "id": "item03",
        "name": "Baz",
        "description": "There goes my baz",
        "price": 50.2,
    },
}

people = {
    "person01": {
        "id": "person01",
        "name": "Alice",
        "is_locked": False,
        "items": [items["item01"], items["item02"]],
    },
    "person02": {
        "id": "person02",
        "name": "Bob",
        "is_locked": True,
        "items": [items["item03"]],
    },
}


test_app = FastAPI()
HyperModel.init_app(test_app)


@test_app.get(
    "/items",
    response_model=List[ItemSummary],
)
def read_items():
    return list(items.values())


@test_app.get("/items/{item_id}", response_model=ItemDetail)
def read_item(item_id: str):
    return items[item_id]


@test_app.put("/items/{item_id}", response_model=ItemDetail)
def update_item(item_id: str, item: ItemUpdate):
    items[item_id].update(item.model_dump(exclude_none=True))
    return items[item_id]


@test_app.get(
    "/people",
    response_model=List[Person],
)
def read_people():
    return list(people.values())


@test_app.get("/people/{person_id}", response_model=Person)
def read_person(person_id: str):
    return people[person_id]


@test_app.get("/people/{person_id}/items", response_model=List[ItemDetail])
def read_person_items(person_id: str):
    return people[person_id]["items"]


@test_app.put("/people/{person_id}/items", response_model=List[ItemDetail])
def put_person_items(person_id: str, item: ItemCreate):
    items[item.id] = item.model_dump()
    people[person_id]["items"].append(item.model_dump())  # type: ignore
    return people[person_id]["items"]

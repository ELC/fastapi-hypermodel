from __future__ import annotations

from itertools import starmap
from typing import (
    Any,
    Callable,
    Dict,
    List,
    Mapping,
    Sequence,
    Type,
    TypeVar,
    Union,
    cast,
)

import jsonschema
from fastapi.routing import APIRoute
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    PrivateAttr,
    field_validator,
    model_serializer,
    model_validator,
)
from pydantic.fields import FieldInfo
from starlette.applications import Starlette
from starlette.responses import JSONResponse
from starlette.routing import Route
from typing_extensions import Self

from fastapi_hypermodel.hypermodel import AbstractHyperField, HasName, HyperModel
from fastapi_hypermodel.url_type import UrlType
from fastapi_hypermodel.utils import (
    get_route_from_app,
    resolve_param_values,
)

from .siren_schema import schema


class SirenBase(BaseModel):
    class_: Union[Sequence[str], None] = Field(default=None, alias="class")
    title: Union[str, None] = Field(default=None)

    @model_serializer
    def serialize(self: Self) -> Mapping[str, Any]:
        return {self.model_fields[k].alias or k: v for k, v in self if v}


class SirenLinkType(SirenBase):
    rel: Sequence[str] = Field(default_factory=list)
    href: UrlType = Field(default=UrlType())
    type_: Union[str, None] = Field(default=None, alias="type")

    @field_validator("rel", "href")
    @classmethod
    def mandatory(cls: Type[Self], value: Union[str, None]) -> str:
        if not value:
            error_message = "Field rel and href are mandatory"
            raise ValueError(error_message)
        return value


class SirenLinkFor(SirenLinkType, AbstractHyperField[SirenLinkType]):
    # pylint: disable=too-many-instance-attributes
    _endpoint: str = PrivateAttr()
    _param_values: Mapping[str, str] = PrivateAttr()
    _templated: bool = PrivateAttr()
    _condition: Union[Callable[[Mapping[str, Any]], bool], None] = PrivateAttr()

    # For details on the folllowing fields, check https://datatracker.ietf.org/doc/html/draft-kelly-json-hal
    _title: Union[str, None] = PrivateAttr()
    _type: Union[str, None] = PrivateAttr()
    _rel: Sequence[str] = PrivateAttr()
    _class: Union[Sequence[str], None] = PrivateAttr()

    def __init__(
        self: Self,
        endpoint: Union[HasName, str],
        param_values: Union[Mapping[str, str], None] = None,
        templated: bool = False,
        condition: Union[Callable[[Mapping[str, Any]], bool], None] = None,
        title: Union[str, None] = None,
        type_: Union[str, None] = None,
        rel: Union[Sequence[str], None] = None,
        class_: Union[Sequence[str], None] = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self._endpoint = (
            endpoint.__name__ if isinstance(endpoint, HasName) else endpoint
        )
        self._param_values = param_values or {}
        self._templated = templated
        self._condition = condition
        self._title = title
        self._type = type_
        self._rel = rel or []
        self._class = class_

    def _get_uri_path(
        self: Self, app: Starlette, values: Mapping[str, Any], route: Union[Route, str]
    ) -> UrlType:
        if self._templated and isinstance(route, Route):
            return UrlType(route.path)

        params = resolve_param_values(self._param_values, values)
        return UrlType(app.url_path_for(self._endpoint, **params))

    def __call__(
        self: Self, app: Union[Starlette, None], values: Mapping[str, Any]
    ) -> Union[SirenLinkType, None]:
        if app is None:
            return None

        if self._condition and not self._condition(values):
            return None

        route = get_route_from_app(app, self._endpoint)

        properties = values.get("properties", values)
        uri_path = self._get_uri_path(app, properties, route)

        # Using model_validate to avoid conflicts with keyword class
        return SirenLinkType.model_validate({
            "href": uri_path,
            "rel": self._rel,
            "title": self._title,
            "type": self._type,
            "class": self._class,
        })


class SirenFieldType(SirenBase):
    name: str
    type_: Union[str, None] = Field(default=None, alias="type")
    value: Union[Any, None] = None

    @classmethod
    def from_field_info(cls: Type[Self], name: str, field_info: FieldInfo) -> Self:
        return cls.model_validate({
            "name": name,
            "type": cls.parse_type(field_info.annotation),
            "value": field_info.default,
        })

    @staticmethod
    def parse_type(python_type: Union[Type[Any], None]) -> str:
        type_repr = repr(python_type)

        text_types = ("str",)
        if any(text_type in type_repr for text_type in text_types):
            return "text"

        number_types = ("float", "int")
        if any(number_type in type_repr for number_type in number_types):
            return "number"

        return "text"


class SirenActionType(SirenBase):
    name: str = Field(default="")
    method: str = Field(default="GET")
    href: UrlType = Field(default=UrlType())
    type_: Union[str, None] = Field(default=None, alias="type")
    fields: Union[Sequence[SirenFieldType], None] = Field(default=None)
    templated: bool = Field(default=False)

    @field_validator("name", "href")
    @classmethod
    def mandatory(cls: Type[Self], value: Union[str, None]) -> str:
        if not value:
            error_message = f"Field name and href are mandatory, {value}"
            raise ValueError(error_message)
        return value


class SirenActionFor(SirenActionType, AbstractHyperField[SirenActionType]):  # pylint: disable=too-many-instance-attributes
    _endpoint: str = PrivateAttr()
    _param_values: Mapping[str, str] = PrivateAttr()
    _templated: bool = PrivateAttr()
    _condition: Union[Callable[[Mapping[str, Any]], bool], None] = PrivateAttr()
    _populate_fields: bool = PrivateAttr()

    # For details on the folllowing fields, check https://github.com/kevinswiber/siren
    _class: Union[Sequence[str], None] = PrivateAttr()
    _title: Union[str, None] = PrivateAttr()
    _name: Union[str, None] = PrivateAttr()
    _method: Union[str, None] = PrivateAttr()
    _type: Union[str, None] = PrivateAttr()
    _fields: Union[Sequence[SirenFieldType], None] = PrivateAttr()

    def __init__(
        self: Self,
        endpoint: Union[HasName, str],
        param_values: Union[Mapping[str, str], None] = None,
        templated: bool = False,
        condition: Union[Callable[[Mapping[str, Any]], bool], None] = None,
        populate_fields: bool = True,
        title: Union[str, None] = None,
        type_: Union[str, None] = None,
        class_: Union[Sequence[str], None] = None,
        fields: Union[Sequence[SirenFieldType], None] = None,
        method: Union[str, None] = None,
        name: Union[str, None] = "",
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self._endpoint = (
            endpoint.__name__ if isinstance(endpoint, HasName) else endpoint
        )
        self._param_values = param_values or {}
        self._templated = templated
        self._condition = condition
        self._populate_fields = populate_fields
        self._title = title
        self._type = type_
        self._fields = fields or []
        self._method = method
        self._name = name
        self._class = class_

    def _get_uri_path(
        self: Self, app: Starlette, values: Mapping[str, Any], route: Union[Route, str]
    ) -> UrlType:
        if self._templated and isinstance(route, Route):
            return UrlType(route.path)

        params = resolve_param_values(self._param_values, values)
        return UrlType(app.url_path_for(self._endpoint, **params))

    def _prepopulate_fields(
        self: Self, fields: Sequence[SirenFieldType], values: Mapping[str, Any]
    ) -> List[SirenFieldType]:
        if not self._populate_fields:
            return list(fields)

        for field in fields:
            value = values.get(field.name) or field.value
            field.value = str(value)
        return list(fields)

    def _compute_fields(
        self: Self, route: Route, values: Mapping[str, Any]
    ) -> List[SirenFieldType]:
        if not isinstance(route, APIRoute):  # pragma: no cover
            route.body_field = ""  # type: ignore
            route = cast(APIRoute, route)

        body_field = route.body_field
        if not body_field:
            return []

        annotation: Any = body_field.field_info.annotation or {}
        model_fields: Any = annotation.model_fields if annotation else {}
        model_fields = cast(Dict[str, FieldInfo], model_fields)

        fields = list(starmap(SirenFieldType.from_field_info, model_fields.items()))
        return self._prepopulate_fields(fields, values)

    def __call__(
        self: Self, app: Union[Starlette, None], values: Mapping[str, Any]
    ) -> Union[SirenActionType, None]:
        if app is None:
            return None

        if self._condition and not self._condition(values):
            return None

        route = get_route_from_app(app, self._endpoint)

        if not self._method:
            self._method = next(iter(route.methods or {}), None)

        uri_path = self._get_uri_path(app, values, route)

        if not self._fields:
            self._fields = self._compute_fields(route, values)

        if not self._type and self._fields:
            self._type = "application/x-www-form-urlencoded"

        # Using model_validate to avoid conflicts with class and type
        return SirenActionType.model_validate({
            "href": uri_path,
            "name": self._name,
            "fields": self._fields,
            "method": self._method,
            "title": self._title,
            "type": self._type,
            "class": self._class,
            "templated": self._templated,
        })


class SirenEntityType(SirenBase):
    properties: Union[Mapping[str, Any], None] = None
    entities: Union[Sequence[Union[SirenEmbeddedType, SirenLinkType]], None] = None
    links: Union[Sequence[SirenLinkType], None] = None
    actions: Union[Sequence[SirenActionType], None] = None


class SirenEmbeddedType(SirenEntityType):
    rel: Sequence[str] = Field()


T = TypeVar("T", bound=Callable[..., Any])

SIREN_RESERVED_FIELDS = {
    "properties",
    "entities",
    "links",
    "actions",
}


class SirenHyperModel(HyperModel):
    properties: Dict[str, Any] = Field(default_factory=dict)
    entities: Sequence[Union[SirenEmbeddedType, SirenLinkType]] = Field(
        default_factory=list
    )
    links: Sequence[SirenLinkFor] = Field(default_factory=list)
    actions: Sequence[SirenActionFor] = Field(default_factory=list)

    # This config is needed to use the Self in Embedded
    model_config = ConfigDict(arbitrary_types_allowed=True)

    @model_validator(mode="after")
    def add_hypermodels_to_entities(self: Self) -> Self:
        entities: List[Union[SirenEmbeddedType, SirenLinkType]] = []
        for name, field in self:
            alias = self.model_fields[name].alias or name

            if alias in SIREN_RESERVED_FIELDS:
                continue

            value: Sequence[Union[Any, Self]] = (
                field if isinstance(field, Sequence) else [field]
            )

            if not all(
                isinstance(element, (SirenHyperModel, SirenLinkType))
                for element in value
            ):
                continue

            for field_ in value:
                if isinstance(field_, SirenLinkType):
                    entities.append(field_)
                    continue

                child = self.as_embedded(field_, alias)
                entities.append(child)

            delattr(self, name)

        self.entities = entities

        return self

    @model_validator(mode="after")
    def add_properties(self: Self) -> Self:
        properties = {}
        for name, field in self:
            alias = self.model_fields[name].alias or name

            if alias in SIREN_RESERVED_FIELDS:
                continue

            value: Sequence[Any] = field if isinstance(field, Sequence) else [field]

            omit_types: Any = (
                AbstractHyperField,
                SirenLinkFor,
                SirenLinkType,
                SirenActionFor,
                SirenActionType,
                SirenHyperModel,
            )
            if any(isinstance(value_, omit_types) for value_ in value):
                continue

            properties[alias] = value if isinstance(field, Sequence) else field

            delattr(self, name)

        if not self.properties:
            self.properties = {}

        self.properties.update(properties)

        return self

    @model_validator(mode="after")
    def add_links(self: Self) -> Self:
        links_key = "links"
        validated_links: List[SirenLinkFor] = []
        for name, value in self:
            alias = self.model_fields[name].alias or name

            if alias != links_key or not value:
                continue

            links = cast(Sequence[SirenLinkFor], value)
            properties = self.properties or {}
            validated_links = self._validate_factory(links, properties)
            self.links = validated_links

        self.validate_has_self_link(validated_links)

        return self

    @staticmethod
    def validate_has_self_link(links: Sequence[SirenLinkFor]) -> None:
        if not links:
            return

        if any(link.rel == ["self"] for link in links):
            return

        error_message = "If links are present, a link with rel self must be present"
        raise ValueError(error_message)

    @model_validator(mode="after")
    def add_actions(self: Self) -> Self:
        actions_key = "actions"
        for name, value in self:
            alias = self.model_fields[name].alias or name

            if alias != actions_key or not value:
                continue

            properties = self.properties or {}
            actions = cast(Sequence[SirenActionFor], value)
            self.actions = self._validate_factory(actions, properties)

        return self

    def _validate_factory(
        self: Self, elements: Sequence[T], properties: Mapping[str, str]
    ) -> List[T]:
        validated_elements: List[T] = []
        for element_factory in elements:
            element = element_factory(self._app, properties)
            if not element:
                continue
            validated_elements.append(element)
        return validated_elements

    @model_validator(mode="after")
    def no_action_outside_of_actions(self: Self) -> Self:
        for _, field in self:
            if not isinstance(field, (SirenActionFor, SirenActionType)):
                continue

            error_message = "All actions must be inside the actions property"
            raise ValueError(error_message)

        return self

    @model_serializer
    def serialize(self: Self) -> Mapping[str, Any]:
        return {self.model_fields[k].alias or k: v for k, v in self if v}

    @staticmethod
    def as_embedded(field: SirenHyperModel, rel: str) -> SirenEmbeddedType:
        return SirenEmbeddedType(rel=[rel], **field.model_dump())

    def parse_uri(self: Self, uri_template: str) -> str:
        return self._parse_uri(self.properties, uri_template)


class SirenResponse(JSONResponse):
    media_type = "application/siren+json"

    @staticmethod
    def _validate(content: Any) -> None:
        jsonschema.validate(instance=content, schema=schema)

    def render(self: Self, content: Any) -> bytes:
        self._validate(content)
        return super().render(content)


def get_siren_link(response: Any, link_name: str) -> Union[SirenLinkType, None]:
    links = response.get("links", [])
    link = next((link for link in links if link_name in link.get("rel")), None)
    return SirenLinkType.model_validate(link) if link else None


def get_siren_action(response: Any, action_name: str) -> Union[SirenActionType, None]:
    actions = response.get("actions", [])
    action = next(
        (action for action in actions if action_name in action.get("name")), None
    )
    return SirenActionType.model_validate(action) if action else None

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class MapInput(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True, allow_inf_nan=False)


class BuildingInput(MapInput):
    name: str = Field(min_length=1, max_length=255)
    branch_id: int | None = None
    address: str | None = Field(default=None, max_length=500)


class FloorInput(MapInput):
    name: str = Field(min_length=1, max_length=255)
    width: float = Field(default=40, ge=2, le=500)
    height: float = Field(default=25, ge=2, le=500)


class PlanShape(MapInput):
    id: str = Field(min_length=1, max_length=80, pattern=r"^[a-zA-Z0-9_-]+$")
    kind: Literal["room", "wall", "door", "text", "desk"]
    x: float = Field(ge=0, le=500)
    y: float = Field(ge=0, le=500)
    width: float | None = Field(default=None, ge=0.5, le=500)
    height: float | None = Field(default=None, ge=0.5, le=500)
    x2: float | None = Field(default=None, ge=0, le=500)
    y2: float | None = Field(default=None, ge=0, le=500)
    label: str = Field(default="", max_length=200)
    color: str = Field(default="#e6f4ff", pattern=r"^#[0-9a-fA-F]{6}$")
    number: str = Field(default="", max_length=50)
    department_id: int | None = Field(default=None, gt=0)
    notes: str = Field(default="", max_length=2000)
    locked: bool = False
    group_id: str | None = Field(default=None, max_length=80, pattern=r"^[a-zA-Z0-9_-]+$")

    @model_validator(mode="after")
    def geometry(self):
        if self.kind in {"room", "desk"} and (self.width is None or self.height is None):
            raise ValueError("Укажите ширину и длину комнаты")
        if self.kind in {"wall", "door"}:
            if self.x2 is None or self.y2 is None or (self.x == self.x2 and self.y == self.y2):
                raise ValueError("Укажите две разные точки стены или двери")
        if self.kind == "text" and not self.label:
            raise ValueError("Введите текст подписи")
        return self


class MarkerInput(MapInput):
    entity_type: Literal["workplace", "device", "warehouse_item"]
    entity_id: int = Field(gt=0)
    x: float = Field(ge=0, le=500)
    y: float = Field(ge=0, le=500)
    rotation: float = Field(default=0, ge=0, lt=360)
    room_id: str | None = Field(default=None, max_length=80, pattern=r"^[a-zA-Z0-9_-]+$")
    locked: bool = False
    group_id: str | None = Field(default=None, max_length=80, pattern=r"^[a-zA-Z0-9_-]+$")
    from_floor_id: int | None = Field(default=None, gt=0)
    from_revision: int | None = Field(default=None, ge=1)


class FloorSave(FloorInput):
    revision: int = Field(ge=1)
    background_opacity: float = Field(default=0.4, ge=0, le=1)
    remove_background: bool = False
    background_revision: int | None = Field(default=None, ge=1)
    version_label: str | None = Field(default=None, max_length=200)
    shapes: list[PlanShape] = Field(default_factory=list, max_length=2000)
    markers: list[MarkerInput] = Field(default_factory=list, max_length=1000)

    @model_validator(mode="after")
    def bounds_and_duplicates(self):
        if len({shape.id for shape in self.shapes}) != len(self.shapes):
            raise ValueError("У элементов плана должны быть разные идентификаторы")
        if len({(marker.entity_type, marker.entity_id) for marker in self.markers}) != len(self.markers):
            raise ValueError("Один объект нельзя разместить на плане дважды")
        rooms = {shape.id: shape for shape in self.shapes if shape.kind == 'room'}
        numbers = [room.number.casefold() for room in rooms.values() if room.number]
        if len(numbers) != len(set(numbers)):
            raise ValueError("Номера кабинетов на этаже должны быть уникальными")
        for marker in self.markers:
            if marker.room_id and marker.room_id not in rooms:
                raise ValueError("Кабинет отметки отсутствует на плане")
            room = rooms.get(marker.room_id)
            if room and not (room.x <= marker.x <= room.x + room.width and room.y <= marker.y <= room.y + room.height):
                raise ValueError("Отметка должна находиться внутри выбранного кабинета")
        for shape in self.shapes:
            right = shape.x + shape.width if shape.kind in {"room", "desk"} else shape.x
            bottom = shape.y + shape.height if shape.kind in {"room", "desk"} else shape.y
            if (max(right, shape.x2 or 0) > self.width or max(bottom, shape.y2 or 0) > self.height):
                raise ValueError("Элемент выходит за границы плана")
        if any(marker.x > self.width or marker.y > self.height for marker in self.markers):
            raise ValueError("Отметка выходит за границы плана")
        return self

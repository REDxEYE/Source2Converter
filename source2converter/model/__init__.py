from dataclasses import dataclass, field
from typing import Optional

import numpy as np

from SourceIO.library.utils import Buffer
from source2converter.model.skeleton import Skeleton, Attachment


@dataclass
class ShapeKey:
    name: str
    indices: np.ndarray = field(repr=False)
    delta_attributes: dict[str, np.ndarray] = field(repr=False)
    stereo: bool = False


@dataclass
class Mesh:
    name: str
    strips: list[tuple[int, np.ndarray]] = field(repr=False)
    vertex_attributes: dict[str, np.ndarray] = field(repr=False)
    shape_keys: list[ShapeKey]


@dataclass
class Lod:
    switch_point: float
    mesh: Mesh
    # meshes: list[Mesh]


class SubModel:
    pass


class NullSubModel(SubModel):
    pass


@dataclass
class LoddedSubModel(SubModel):
    name: str
    lods: list[Lod]


@dataclass
class BodyGroup:
    name: str
    sub_models: list[SubModel]


@dataclass
class Material:
    name: str
    full_path: str
    buffer: Buffer


@dataclass
class Model:
    name: str
    skeleton: Optional[Skeleton] = None
    attachments: list[Attachment] = field(default_factory=list)
    bodygroups: list[BodyGroup] = field(default_factory=list)
    materials: list[Material] = field(default_factory=list)
    has_shape_keys: bool = False

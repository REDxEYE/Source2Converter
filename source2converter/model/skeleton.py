from dataclasses import dataclass, field
from typing import Optional

import numpy as np

from SourceIO.library.shared.types import Vector3, Vector4


@dataclass
class Bone:
    name: str
    parent_name: Optional[str]
    translation: Vector3
    rotation: Vector4


class AttachmentParentType:
    NONE = 0
    SINGLE_BONE = 1
    MULTI_BONE = 2


@dataclass
class Attachment:
    name: str
    parent_type: AttachmentParentType
    parent_name: str
    translation: Vector3
    rotation: Vector4


@dataclass
class Skeleton:
    bones: list[Bone] = field(default_factory=list)

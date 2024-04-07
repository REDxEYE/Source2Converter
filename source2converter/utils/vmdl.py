import dataclasses
from dataclasses import dataclass, field
from typing import Any, TypeVar

from SourceIO.library.utils.s2_keyvalues import KeyValues


@dataclass
class Node(dict[str, Any]):
    _class: str = field(init=False, default="")

    def dump(self):
        data = dataclasses.asdict(self)
        data["_class"] = self.__class__.__name__
        return data


T = TypeVar("T", bound=Node)


@dataclass
class ListNode(Node[T]):
    children: list[T] = field(default_factory=list, init=False)

    def append(self, child: T):
        self.children.append(child)
        return self

    def dump(self):
        data = dataclasses.asdict(self)
        data["children"] = [child.dump() for child in self.children]
        data["_class"] = self.__class__.__name__
        return data


@dataclass
class RootNode(ListNode[T]):
    model_archetype: str = ""
    primary_associated_entity: str = ""
    anim_graph_name: str = ""


@dataclass
class LODGroup(Node):
    switch_threshold: float = 0
    meshes: list[str] = field(default_factory=list)


@dataclass
class LODGroupList(ListNode[LODGroup]):
    pass


@dataclass
class RenderMeshFile(Node):
    name: str
    filename: str
    import_scale: float = 1.0


@dataclass
class RenderMeshList(ListNode[RenderMeshFile]):
    pass


@dataclass
class AnimationList(ListNode):
    pass


@dataclass
class BodyGroupChoice(Node):
    meshes: list[str]


@dataclass
class BodyGroup(ListNode[BodyGroupChoice]):
    name: str
    hidden_in_tools: bool = False


@dataclass
class BodyGroupList(ListNode[BodyGroup]):
    pass


@dataclass
class JiggleBoneList(ListNode):
    pass


@dataclass
class MaterialGroupList(ListNode):
    pass


@dataclass
class MorphControlList(ListNode):
    pass


@dataclass
class MorphRuleList(ListNode):
    pass


@dataclass
class BoneMarkupList(Node):
    bone_cull_type: str = "None"


@dataclass
class EmptyAnim(Node):
    activity_name: str = ""
    activity_weight: int = 1
    anim_markup_ordered: bool = False
    delta: bool = False
    disable_compression: bool = False
    fade_in_time: float = 0.2
    fade_out_time: float = 0.2
    frame_count: int = 1
    frame_rate: int = 30
    hidden: bool = False
    looping: bool = False
    name: str = "ref"
    weight_list_name: str = ""
    worldSpace: bool = False


@dataclass
class MaterialGroup(Node):
    name: str
    remaps: list[dict] = False

    def add_remap(self, from_: str, to: str):
        self.remaps.append({"from": from_, "to": to})
        return self


@dataclass
class Attachment(Node):
    name: str
    parent_bone: str
    relative_origin: tuple[float, float, float]
    relative_angles: tuple[float, float, float]
    weight: float = 1.0
    ignore_rotation: bool = False


class AttachmentList(ListNode[Attachment]):
    pass


# @dataclass
# class JiggleBone(Node):
#     name: str
#     hidden_in_tools: bool = False


class Vmdl:
    def __init__(self):
        self._root_node = RootNode()

    def append(self, child: T) -> T:
        self._root_node.append(child)
        return child

    def write(self):
        return KeyValues.dump_str('KV3',
                                  ('text', 'e21c7f3c-8a33-41c5-9977-a76d3a32aa0d'),
                                  ('modeldoc28', 'fb63b6ca-f435-4aa0-a2c7-c66ddc651dca'),
                                  {"rootNode": self._root_node.dump()}
                                  )

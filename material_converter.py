import sys
from pathlib import Path
from typing import Tuple, TypeVar, Type

from SourceIO.source1.vmt.valve_material import VMT
from shader_converters.eyerefract import EyeRefract
from shader_converters.lightmappedgeneric import LightmappedGeneric
from shader_converters.shader_base import ShaderBase
from shader_converters.unlitgeneric import UnlitGeneric
from shader_converters.vertexlitgeneric import VertexLitGeneric
from utils import normalize_path

MaterialName = TypeVar('MaterialName', str, str)
CdPath = TypeVar('CdPath', str, str)
MaterialPath = TypeVar('MaterialPath', str, str)
Material = Tuple[MaterialName, CdPath, MaterialPath]

s1_to_s2_shader = {
    "worldvertextransition": LightmappedGeneric,
    "lightmappedgeneric": LightmappedGeneric,
    "vertexlitgeneric": VertexLitGeneric,
    "unlitgeneric": UnlitGeneric,
    "eyes": EyeRefract,
    "eyerefract": EyeRefract,
}


def convert_material(material: Material, target_addon: Path, sbox_mode=False):
    vmt = VMT(material[2])
    vmt.parse()
    shader_converter: Type[ShaderBase] = s1_to_s2_shader.get(vmt.shader, None)
    if shader_converter is None:
        sys.stderr.write(f'Unsupported shader: "{vmt.shader}"\n')
        return False, vmt.shader

    mat_path = normalize_path(Path(material[1]) / material[0]).resolve()
    mat_name = mat_path.stem
    mat_path = mat_path.parent
    converter = shader_converter(mat_name, mat_path, vmt, target_addon, sbox_mode)
    try:
        converter.convert()
    except Exception as ex:
        print(f'Failed to convert {material[2]}')
    converter.write_vmat()
    return True, vmt.shader

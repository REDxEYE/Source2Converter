import os
import shlex
from pathlib import Path
from typing import Tuple, TypeVar

from SourceIO.source_shared.content_manager import ContentManager
from SourceIO.utilities.keyvalues import KVParser
from utils import normalize_path, sanitize_name
from PIL import Image, ImageOps
from SourceIO.source1.vtf.VTFWrapper import VTFLib

MaterialName = TypeVar('MaterialName', str, str)
CdPath = TypeVar('CdPath', str, str)
MaterialPath = TypeVar('MaterialPath', str, str)
Material = Tuple[MaterialName, CdPath, MaterialPath]

vtf_lib = VTFLib.VTFLib()


def stupid_valve_fix(line):
    return line.strip('[]')


def remap_value(value, _from, _to):
    value = min(value, _from[1])
    value = value / (_from[1] - _from[0])
    return (1 - value) * (_to[1] - _to[0])


s1_to_s2_shader = {
    "vertexlitgeneric": "vr_complex",
    "unlitgeneric": "vr_complex",
}


def load_vtf(path):
    content_manager = ContentManager()
    print(f"Loading texture {path}")
    texture_path = content_manager.find_texture(path)
    if texture_path and vtf_lib.image_load_from_buffer(texture_path.read()):
        texture = Image.frombytes("RGBA", (vtf_lib.width(), vtf_lib.height()), vtf_lib.get_rgba8888().contents)
        return texture
    else:
        print(f"Texture {path} not found!")
    return None


def write_settings(filename, props):
    with open(filename, 'w') as settings:
        settings.write('"settings"\n{\n')
        for _key, _value in props.items():
            settings.write(f'\t"{_key}"\t{_value}\n')
        settings.write('}\n')


def fix_vector(str_vector: str, div_value=1):
    str_vector = str_vector.strip('"\'[]{} \t')
    values = [float(v) / div_value for v in str_vector.split(' ')]
    if len(values) < 3:
        values.extend([0.0] * max(3 - len(values), 0))
    return '"[{} {} {}]"'.format(*values)


def convert_material(material: Material, target_addon: Path):
    content_manager = ContentManager()
    maps = {}
    relative_to_path = target_addon
    mat_name, mat_path, s1_material = material
    mat_name = sanitize_name(mat_name)
    parser = KVParser('vmt', s1_material.read().decode())
    s1_shader, s1_material_props = parser.parse()
    if s1_shader not in s1_to_s2_shader:
        print(f"Skipping {mat_name}, unsupported \"{s1_shader}\" shader")
        return None, None

    for prop_name, prop_value in s1_material_props.items():
        if "$basetexture" == prop_name:
            maps["color"] = load_vtf(prop_value)
        if "$bumpmap" == prop_name:
            maps["normal"] = load_vtf(prop_value)
        if "$detail" == prop_name:
            maps['detail'] = load_vtf(prop_value)
        if "$selfillummask" == prop_name:
            maps['illum'] = load_vtf(prop_value)
        if "$phongexponenttexture" in prop_name:
            maps['exp'] = load_vtf(prop_value)
        if "$envmapmask" == prop_name and '$envmap' == s1_material_props:
            maps['envmap'] = load_vtf(prop_value)
        if "$ambientoccltexture" == prop_name or "$ambientocclusiontexture" == prop_name:
            maps['ao'] = load_vtf(prop_value)

    s2_material_props = {}
    if s1_shader == 'unlitgeneric':
        s2_material_props['F_UNLIT'] = 1
    target_material_path = target_addon / 'materials' / normalize_path(str(mat_path).strip("/\\"))
    # noinspection PyTypeChecker
    os.makedirs(target_material_path, exist_ok=True)

    if maps.get('color'):
        texture = maps['color'].convert('RGB')
        texture_path = target_material_path / f'{mat_name}_color.tga'
        texture.convert("RGB").save(texture_path)
        write_settings(target_material_path / f'{mat_name}_color.txt', {'nolod': 1})
        s2_material_props['TextureColor'] = texture_path.relative_to(relative_to_path)

    if maps.get('normal'):
        texture = maps['normal'].convert('RGB')
        texture = Image.merge("RGB", [texture.getchannel("R"),
                                      ImageOps.invert(texture.getchannel("G")),
                                      texture.getchannel("B")])
        texture_path = target_material_path / f'{mat_name}_normal.tga'
        texture.convert("RGB").save(texture_path)
        write_settings(target_material_path / f'{mat_name}_normal.txt', {'nolod': 1})
        s2_material_props['TextureNormal'] = texture_path.relative_to(relative_to_path)

    s2_material_props['F_MORPH_SUPPORTED'] = 1
    s2_material_props['F_SPECULAR'] = 1

    for prop_name, prop_value in s1_material_props.items():
        if prop_name == '$basemapalphaphongmask':
            if maps.get('color', None):
                texture = maps['color'].getchannel("A")
                texture = ImageOps.invert(texture)
                texture_path = target_material_path / f'{mat_name}_rough.tga'
                write_settings(target_material_path / f'{mat_name}_rough.txt', {'nolod': 1})
                texture.save(texture_path)
                s2_material_props['TextureRoughness'] = texture_path.relative_to(relative_to_path)

        elif prop_name == '$normalmapalphaphongmask':
            if maps.get('normal', None):
                texture = maps['normal'].getchannel("A")
                texture = ImageOps.invert(texture)
                texture_path = target_material_path / f'{mat_name}_rough.tga'
                write_settings(target_material_path / f'{mat_name}_rough.txt', {'nolod': 1})
                texture.save(texture_path)
                s2_material_props['TextureRoughness'] = texture_path.relative_to(relative_to_path)

        elif prop_name == '$ambientoccltexture' or prop_name == '$ambientocclusiontexture':
            if maps.get('ao', None):
                texture = maps['ao']
                texture_path = target_material_path / f'{mat_name}_ao.tga'
                texture.convert("L").save(texture_path)
                write_settings(target_material_path / f'{mat_name}_ao.txt', {'nolod': 1})
                s2_material_props['TextureAmbientOcclusion'] = texture_path.relative_to(relative_to_path)

        elif prop_name == '$normalmapalphaenvmapmask':
            if maps.get('normal', None):
                texture = maps['normal'].getchannel("A")
                texture = ImageOps.invert(texture)
                texture_path = target_material_path / f'{mat_name}_rough.tga'
                write_settings(target_material_path / f'{mat_name}_rough.txt', {'nolod': 1})
                texture.save(texture_path)
                s2_material_props['TextureRoughness'] = texture_path.relative_to(relative_to_path)

        elif prop_name == '$basealphaenvmapmask':
            if maps.get('color', None):
                texture = maps['color'].getchannel("A")
                texture = ImageOps.invert(texture)
                texture_path = target_material_path / f'{mat_name}_rough.tga'
                write_settings(target_material_path / f'{mat_name}_rough.txt', {'nolod': 1})
                texture.save(texture_path)
                s2_material_props['TextureRoughness'] = texture_path.relative_to(relative_to_path)

        elif prop_name == '$envmap' or prop_name == '$envmapmask':
            if maps.get('envmap', None):
                texture = maps['envmap'].convert("RGB")
                texture_path = target_material_path / f'{mat_name}_ao.tga'
                write_settings(target_material_path / f'{mat_name}_ao.txt', {'nolod': 1})
                texture.save(texture_path)
                s2_material_props['TextureAmbientOcclusion'] = texture_path.relative_to(relative_to_path)
                s2_material_props['g_flAmbientOcclusionDirectSpecular'] = 0.0

        if prop_name == '$phong':
            if maps.get('exp', None):
                texture = maps['exp'].getchannel("R").convert("L")
                # texture = ImageOps.invert(texture)
                texture_path = target_material_path / f'{mat_name}_ao.tga'
                texture.convert("L").save(texture_path)
                if "$phongboost" in s1_material_props:
                    write_settings(target_material_path / f'{mat_name}_ao.txt',
                                   {"brightness": s1_material_props["$phongboost"], "nolod": 1}
                                   )
                s2_material_props['TextureAmbientOcclusion'] = texture_path.relative_to(relative_to_path)
                s2_material_props['g_flAmbientOcclusionDirectSpecular'] = 1.0
                if '$phongalbedotint' in s1_material_props and int(s1_material_props['$phongalbedotint']) == 1:
                    texture = maps['exp'].getchannel("G").convert("L")
                    texture_path = target_material_path / f'{mat_name}_metallic.tga'
                    write_settings(target_material_path / f'{mat_name}_metallic.txt', {'nolod': 1})
                    texture.convert("L").save(texture_path)
                    s2_material_props['F_METALNESS_TEXTURE'] = 1
                    s2_material_props['TextureMetalness'] = texture_path.relative_to(relative_to_path)

            elif '$phongexponent' in s1_material_props and 'TextureRoughness' not in s2_material_props:
                spec_value = (min(float(s1_material_props["$phongexponent"]), 255) / 255)
                if '$phongboost' in s1_material_props:
                    boost = (1 - min(float(s1_material_props['$phongboost']) / 255, 1.0)) ** 2
                else:
                    boost = 1
                final_spec = (-10642.28 + (254.2042 - -10642.28) / (
                        1 + (float(spec_value) / 2402433000000) ** 0.1705696)) / 255
                final_spec = final_spec * boost * 0.85
                s2_material_props['TextureRoughness'] = f'"[{final_spec} {final_spec} {final_spec} 0.000]"'
            else:
                final_spec = 60 / 255.0
                s2_material_props['TextureRoughness'] = f'"[{final_spec} {final_spec} {final_spec} 0.000]"'

        if prop_name == '$selfillum':
            s2_material_props['F_SELF_ILLUM'] = 1
            if maps.get('illum', None):
                texture = maps['illum'].convert("L")
                texture_path = target_material_path / f'{mat_name}_selfillum.tga'
                write_settings(target_material_path / f'{mat_name}_selfillum.txt', {'nolod': 1})
                texture.save(texture_path)
                s2_material_props['TextureSelfIllumMask'] = texture_path.relative_to(relative_to_path)
            if '$selfillumtint' in s1_material_props:
                s2_material_props['g_vSelfIllumTint'] = fix_vector(s1_material_props['$selfillumtint'])
            if '$selfillummaskscale' in s1_material_props:
                s2_material_props['g_vSelfIllumTint'] = s1_material_props['$selfillummaskscale']

        if prop_name == "$translucent" or prop_name == "$alphatest":
            if maps.get('color'):
                if "$translucent" in s1_material_props:
                    s2_material_props['F_TRANSLUCENT'] = 1
                elif "$alphatest" in s1_material_props:
                    s2_material_props['F_ALPHA_TEST'] = 1
                if "$additive" in s1_material_props:
                    s2_material_props['F_ADDITIVE_BLEND'] = 1

                texture = maps['color'].getchannel("A")
                texture_path = target_material_path / f'{mat_name}_trans.tga'
                write_settings(target_material_path / f'{mat_name}_trans.txt', {'nolod': 1})
                texture.save(texture_path)
                s2_material_props['TextureTranslucency'] = texture_path.relative_to(relative_to_path)

        if prop_name == "$color":
            if "{" in prop_value:
                s2_material_props['g_vColorTint'] = fix_vector(prop_value, 255)
            elif "[" in prop_value:
                s2_material_props['g_vColorTint'] = fix_vector(prop_value)

        if prop_name == "$color2":
            if "$blendtintbybasealpha" in s2_material_props and maps.get('color', None):
                texture = maps['color'].getchannel("A").convert("L")
                texture_path = target_material_path / f'{mat_name}_colormask.tga'
                write_settings(target_material_path / f'{mat_name}_colormask.txt', {'nolod': 1})
                texture.save(texture_path)
                s2_material_props['TextureTintMask'] = texture_path.relative_to(relative_to_path)
                s2_material_props['F_TINT_MASK'] = 1
            if "{" in prop_value:
                s2_material_props['g_vColorTint'] = fix_vector(prop_value, 255)
            elif "[" in prop_value:
                s2_material_props['g_vColorTint'] = fix_vector(prop_value)

        if prop_name == "$detail":
            if maps.get('detail', None):
                texture_path = target_material_path / f'{Path(prop_value).stem}.tga'
                if not texture_path.exists():
                    texture = maps['detail']
                    texture.save(texture_path)
                    write_settings(target_material_path / f'{Path(prop_value).stem}.txt', {'nolod': 1})
                s2_material_props['TextureDetail'] = texture_path.relative_to(relative_to_path)

                if '$detailblendmode' in s1_material_props:
                    s2_material_props['F_DETAIL_TEXTURE'] = 2
                else:
                    s2_material_props['F_DETAIL_TEXTURE'] = 1

                if '$detailscale' in s1_material_props:
                    s2_material_props['g_vDetailTexCoordScale'] = '"[{0} {0}]"'.format(
                        s1_material_props['$detailscale'])
                if '$detailblendfactor' in s1_material_props:
                    s2_material_props['g_flDetailBlendFactor'] = s1_material_props['$detailblendfactor']
    return s1_to_s2_shader[s1_shader], s2_material_props

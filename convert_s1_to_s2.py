import os
import shlex
import sys
from ctypes import windll
from pathlib import Path

import numpy as np

k32 = windll.LoadLibrary('kernel32.dll')
setConsoleModeProc = k32.SetConsoleMode
setConsoleModeProc(k32.GetStdHandle(-11), 0x0001 | 0x0002 | 0x0004)

os.environ['NO_BPY'] = '1'

from PIL import Image, ImageOps

from SourceIO.source1.new_mdl.mdl import Mdl
from SourceIO.source1.new_vvd.vvd import Vvd
from SourceIO.source1.new_vtx.vtx import Vtx
from SourceIO.source1.vtf.VTFWrapper import VTFLib
from SourceIO.source1.vtf.VTFWrapper.VTFLibEnums import ImageFlag

from SourceIO.source2.utils.kv3_generator import KV3mdl
from SourceIO.source1.source1_to_dmx import decompile

vtf_lib = VTFLib.VTFLib()

from SourceIO.utilities.valve_utils import encode_quotes
from SourceIO.utilities import valve_utils

s2fm_addon_folder = Path(input("Source2 addon folder:").replace('"',
                                                                '') or r"F:\SteamLibrary\steamapps\common\Half-Life Alyx\content\hlvr_addons\s2fm")

s1_model = Path(input("Source1 model:").replace('"','') or r"H:\SteamLibrary\SteamApps\common\SourceFilmmaker\game\Furry\models\Norpo\demo_thug.mdl")

s1_mdl = Mdl(s1_model)
s1_mdl.read()


def decompile_s1_model(mdl: Mdl, mdl_path: Path, output, gameinfo):
    vvd_path = mdl_path.with_suffix(".vvd")
    vtx_path = mdl_path.with_suffix(".dx90.vtx")
    vvd = Vvd(vvd_path)
    vtx = Vtx(vtx_path)
    vvd.read()
    vtx.read()
    return decompile(mdl, vvd, vtx, output, gameinfo)

def remove_ext(path):
    path = Path(path)
    return str(path.with_suffix(""))

def normalize_path(path):
    return Path(str(path).lower())

s1_materials = []
s1_textures = []
refl_range = 0.5

# handle S1 materials
model_name = s1_model.stem
mod_path = valve_utils.get_mod_path(s1_model)
rel_model_path = normalize_path(s1_model.relative_to(mod_path))
gi_path = mod_path / 'gameinfo.txt'
if not gi_path.exists():
    raise FileNotFoundError("Failed to find gameinfo file")
else:
    print('\033[94mFound \033[95mgameinfo.txt\033[94m file\033[0m'.format(s1_model))
gi = valve_utils.GameInfoFile(gi_path)

#remove DMX material prefix
for material in s1_mdl.materials:
    for mat_path in s1_mdl.materials_paths:
        if str(Path(mat_path)) in str(Path(material.name)):
            material.name = str(Path(material.name).relative_to(Path(mat_path)))

for material in s1_mdl.materials:
    for mat_path in s1_mdl.materials_paths:
        if str(Path(mat_path)) in str(Path(material.name)):
            print("DMX materials")
        mat = gi.find_material(Path(mat_path) / material.name, True)
        if mat:
            s1_materials.append((material.name, mat_path, mat))
            break

os.makedirs(s2fm_addon_folder / rel_model_path.with_suffix(''), exist_ok=True)

if 1:
    mesh_files = decompile_s1_model(s1_mdl, s1_model, s2fm_addon_folder / rel_model_path.with_suffix(''), gi)

    s2_vmodel = normalize_path(s2fm_addon_folder / rel_model_path.with_suffix("") / Path(model_name).with_suffix('.vmdl'))
    os.makedirs(s2_vmodel.parent, exist_ok=True)
    vmdl = KV3mdl()
    for mesh_name, mesh_path in mesh_files.items():
        vmdl.add_render_mesh(remove_ext(mesh_name), str(mesh_path.relative_to(s2fm_addon_folder)))

    for s1_bodygroup in s1_mdl.body_parts:
        bodygroup = vmdl.add_bodygroup(s1_bodygroup.name)
        for mesh in s1_bodygroup.models:
            if len(mesh.meshes) == 0:
                continue
            vmdl.add_bodygroup_choice(bodygroup, remove_ext(mesh.name))

    with s2_vmodel.open('w') as f:
        f.write(vmdl.dump())

s1_to_s2_shader = {
    "vertexlitgeneric": "vr_complex",
    "unlitgeneric": "vr_complex",
}


def normalized_parse_line(line):
    """
    Line parser that extracts key value pairs from a line and returns a list of the tokens with escaped quotes.
    """
    # Fix any trailing slashes that are escaping quotes
    if line.endswith('\\"'):
        line = line.rsplit('\\"', 1)
        line = '\\\\"'.join(line)
    elif line.endswith("\\'"):
        line = line.rsplit("\\'", 1)
        line = "\\\\'".join(line)

    lex = shlex.shlex(line, posix=True)
    lex.escapedquotes = '\"\''
    lex.whitespace = ' \n\t='
    lex.wordchars += '|.:/\\+*%$'  # Do not split on these chars
    # Escape all quotes in result
    tokens = [encode_quotes(token) for token in lex]
    tokens[0] = tokens[0].lower()
    if len(tokens) == 1:
        # Key with no value gets empty string as value
        tokens.append('')
    elif len(tokens) > 2:
        # Multiple value tokens, invalid
        raise TypeError
    vals = tokens[1].split(" ")
    if vals and len(vals) > 1:
        a = [val.isnumeric() for val in vals]
        if all(a):
            tokens[1] = list(map(int, vals))
    return tokens


if 1:  # convert S1 mat to S2 material

    def load_vtf(path):
        texture_path = gi.find_texture(path)
        if texture_path and vtf_lib.image_load(texture_path):
            texture = Image.frombytes("RGBA", (vtf_lib.width(), vtf_lib.height()),
                                      vtf_lib.get_rgba8888().contents)
            return texture
        return None


    def vector_type(str_vector):
        if str_vector[0] == "{" and str_vector[-1] == "}":
            return int
        elif str_vector[0] == "[" and str_vector[-1] == "]":
            return float
        return None


    def convert_vector(str_vector, multiplier):
        vector_t = vector_type(str_vector)
        str_vector = str_vector.strip("{}[]")
        vector_value = map(vector_t, str_vector.split(" "))
        return [int(v * multiplier) for v in vector_value]


    base_map: Image.Image = None
    bump_map: Image.Image = None
    phong_map: Image.Image = None
    phong_exp_map: Image.Image = None

    env_map: Image.Image = None
    illum_map: Image.Image = None
    ao_map: Image.Image = None
    detail_map: Image.Image = None


    def write_vmat(mat_name, mat_props, mat_path):
        mat_name = mat_name.replace(' ', '_').lower()
        mat_path = mat_path.lower()
        os.makedirs(s2fm_addon_folder / 'materials' / mat_path, exist_ok=True)
        material_file = (s2fm_addon_folder / 'materials' / mat_path / mat_name).with_suffix('.vmat')
        relative_material_file = (Path('materials') / mat_path / mat_name).with_suffix("")
        print(f"Converting {mat_name}")
        print(f"Saving to {material_file}\n\n")

        def write_settings(filepath, props):
            with open(filepath, 'w') as settings:
                settings.write('"settings"\n{\n')
                for key, value in props.items():
                    settings.write(f'\t"{key}"\t{value}\n')
                settings.write(' }\n')

        with material_file.open('w') as vmat_file:
            vmat_file.write('// Converted with SourceIO Source1 converter\n\n')
            vmat_file.write('Layer0\n{\n\tshader "' + s2_shader + '.vfx"\n\n')
            vmat_file.write("F_MORPH_SUPPORTED 1\n")
            if base_map is not None:
                base_map.convert("RGB").save(str(material_file.with_suffix("")) + '_color.tga')
                write_settings(str(material_file.with_suffix("")) + "_color.txt", {"nolod": 1})
                vmat_file.write('\tTextureColor "' + str(relative_material_file) + '_color.tga' + '"\n')

            if bump_map is not None:
                final_bump = Image.merge("RGB", [bump_map.getchannel("R"),
                                                 ImageOps.invert(bump_map.getchannel("G")),
                                                 bump_map.getchannel("B")])
                write_settings(str(material_file.with_suffix("")) + "_normal.txt", {"nolod": 1})
                final_bump.save(str(material_file.with_suffix("")) + '_normal.tga')
                vmat_file.write('\tTextureNormal "' + str(relative_material_file) + '_normal.tga' + '"\n')

            if "$basemapalphaphongmask" in mat_props:
                phong_map = bump_map.getchannel("A")
                phong_map.convert("L").save(str(material_file.with_suffix("")) + '_ao.tga')
                if "$phongboost" in mat_props:
                    ao_settings_file_name = str(material_file.with_suffix("")) + "_ao.txt"
                    write_settings(ao_settings_file_name, {"brightness": mat_props["$phongboost"], "nolod": 1})
                vmat_file.write(f'\tg_vReflectanceRange "[0.000 {refl_range}]"\n')
                vmat_file.write('\tTextureAmbientOcclusion "' + str(relative_material_file) + '_ao.tga' + '"\n')
                vmat_file.write('\tg_flAmbientOcclusionDirectSpecular "1.000"\n')

            if "$normalmapalphaenvmapmask" in mat_props:
                env_map = bump_map.getchannel("A")
                env_map.convert("L").save(str(material_file.with_suffix("")) + '_ao.tga')
                write_settings(str(material_file.with_suffix("")) + "_ao.txt", {"nolod": 1})
                vmat_file.write('\tTextureAmbientOcclusion "' + str(relative_material_file) + '_ao.tga' + '"\n')
                vmat_file.write('\tg_flAmbientOcclusionDirectSpecular "0.000"\n')

            if "$phong" in mat_props:
                vmat_file.write('\tF_SPECULAR 1\n')
                if phong_exp_map is not None:
                    phong_exp_map_flip = phong_exp_map.convert('RGB')
                    phong_exp_map_flip = ImageOps.invert(phong_exp_map_flip)
                    phong_exp_map_flip.save(str(material_file.with_suffix("")) + '_rough.tga')
                    write_settings(str(material_file.with_suffix("")) + "_rough.txt", {"nolod": 1})

                    vmat_file.write('\tTextureRoughness "' + str(relative_material_file) + '_rough.tga' + '"\n')
                elif "$phongexponent" in mat_props:
                    spec_value = mat_props["$phongexponent"]
                    final_spec = (-10642.28 + (254.2042 - -10642.28) / (
                            1 + (float(spec_value) / 2402433000000) ** 0.1705696)) / 255
                    vmat_file.write('\tTextureRoughness "[{0} {0} {0} 0.000]"\n'.format(final_spec))
                else:
                    final_spec = 60
                    vmat_file.write('\tTextureRoughness "[{0} {0} {0} 0.000]"\n'.format(final_spec))

            if "$translucent" in mat_props or "$alphatest" in mat_props:
                if "$translucent" in mat_props:
                    vmat_file.write('\tF_TRANSLUCENT 1\n')
                elif "$alphatest" in mat_props:
                    vmat_file.write('\tF_ALPHA_TEST 1\n')
                if "$additive" in mat_props:
                    vmat_file.write('\tF_ADDITIVE_BLEND 1\n')
                base_map.getchannel("A").convert('L').save(str(material_file.with_suffix("")) + '_trans.tga')
                vmat_file.write('\tTextureTranslucency "' + str(relative_material_file) + '_trans.tga' + '"\n')

            if "$color" in mat_props:
                color_vector_type = vector_type(mat_props["$color"])
                if color_vector_type is int:
                    vmat_file.write('\tg_vColorTint {} {} {}\n'.format(*convert_vector(mat_props["$color"], 255)))
                elif color_vector_type is float:
                    vmat_file.write('\tg_vColorTint {} {} {}\n'.format(*convert_vector(mat_props["$color"], 1)))
            elif "$color2" in mat_props:
                color_vector_type = vector_type(mat_props["$color"])
                if "$blendtintbybasealpha" in mat_props:
                    mask_map_convert = base_map.getchannel('A').convert("L")
                    mask_map_convert.save(str(relative_material_file) + '_colormask.tga')
                    vmat_file.write(
                        '\tF_TINT_MASK 1\n\tTextureTintMask "{}_colormask.tga"\n'.format(str(relative_material_file)))
                if color_vector_type is int:
                    vmat_file.write('\tg_vColorTint {} {} {}\n'.format(*convert_vector(mat_props["$color2"], 255)))
                elif color_vector_type is float:
                    vmat_file.write('\tg_vColorTint {} {} {}\n'.format(*convert_vector(mat_props["$color2"], 1)))

            if "$selfillum" in mat_props:
                raise NotImplementedError(
                    "open an issue on github and attach model with material that you tried to convert")
                # vmat_file.write('\tF_SELF_ILLUM 1\n')
                # vmat_file.write('\tTextureSelfIllumMask "' + str(relative_material_file) + '_selfillum.tga' + '"\n')
                # if "$selfillumtint" in mat_props:
                #     print(mat_props["$selfillumtint"])
                #     vmat_file.write('\tg_vSelfIllumTint ' + fixVector(mat_props["$selfillumtint"]) + '\n')
                # if "$selfillummaskscale" in mat_props:
                #     vmat_file.write('\tg_flSelfIllumScale "' + mat_props['$selfillummaskscale'] + '"\n')

            # if "$detail" in mat_props:
            #     # Detail textures are unique since they're almost always shared with other materials,
            #     # So in this case we just copy it once and then continue to process like normal
            #     tgaPath = modPath + "materials\\" + parseVMTPath(mat_props["$detail"]) + ".tga"
            #     if not os.path.exists(addFolderExtension(tgaPath)):
            #         try:
            #             copyfile(tgaPath, addFolderExtension(tgaPath))
            #             print("+ " + addFolderExtension(tgaPath) + " copied to target directory!")
            #         except:
            #             print("- ERROR: $detail file " + parseVMTPath(mat_props["$detail"]) + " in TGA does not exist. Skipping!")
            #
            #     vmat_file.write('\tTextureDetail "' + 'materials/' + parseVMTPath(mat_props["$detail"]) + '.tga"\n')
            #     if "$detailblendmode" in mat_props:
            #         vmat_file.write('\tF_DETAIL_TEXTURE 2\n')  # Overlay
            #     else:
            #         vmat_file.write('\tF_DETAIL_TEXTURE 1\n')  # Mod2X
            #     if "$detailscale" in mat_props:
            #         vmat_file.write('\tg_vDetailTexCoordScale "[' + mat_props["$detailscale"] + ' ' + mat_props["$detailscale"] + ']"\n')
            #     if "$detailblendfactor" in mat_props:
            #         vmat_file.write('\tg_flDetailBlendFactor "' + mat_props["$detailblendfactor"] + '"\n')

            vmat_file.write('}\n')


    for mat_name, mat_path, s1_material in s1_materials:
        print(f"Parsing {mat_name} material")
        kv = valve_utils.KeyValueFile(s1_material, line_parser=normalized_parse_line)
        s1_shader = kv[0].key
        if s1_shader not in s1_to_s2_shader:
            print(f"Skipping {mat_name}, unsupported \"{s1_shader}\" shader")
            continue
        s2_shader = s1_to_s2_shader[s1_shader]

        # base_map: Image.Image = 1
        # bump_map: Image.Image = 1
        # phong_map: Image.Image = 1
        # phong_exp_map: Image.Image = 1
        #
        # env_map: Image.Image = 1
        # illum_map: Image.Image = 1
        # ao_map: Image.Image = 1
        # detail_map: Image.Image = 1

        # collect all textures
        for key, value in kv.as_dict[s1_shader].items():
            # print(key, value)
            if "$basetexture" in key.lower():
                base_map = load_vtf(value) or base_map
            if "$bumpmap" in key.lower():
                bump_map = load_vtf(value) or bump_map
            if "$selfillummask" in key.lower():
                illum_map = load_vtf(value) or illum_map
            if "$phongexponenttexture" in key.lower():
                phong_exp_map = load_vtf(value) or phong_exp_map
        write_vmat(mat_name, kv.as_dict[s1_shader], mat_path)

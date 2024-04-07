from pathlib import Path

import numpy as np
from PIL import ImageChops, Image, ImageOps

from SourceIO.library.shared.content_providers.content_manager import ContentManager
from SourceIO.library.source1.vmt import VMT
from SourceIO.library.utils import Buffer
from source2converter.materials.material_converter_tags import register_material_converter, SourceType, GameType
from source2converter.materials.source1.common import load_texture, write_texture, write_vector, ensure_length

def phong_to_pbr_roughness(phongexponent, phongboost, max_observed_phongexponent=256):
    # Normalize phongexponent to a 0-1 range, assuming max_observed_phongexponent as a reference maximum
    normalized_exponent = np.clip(phongexponent / max_observed_phongexponent, 0, 1)

    # Convert normalized exponent to a preliminary roughness value
    # Assuming an inverse relationship; high exponent means low roughness
    preliminary_roughness = 1 - normalized_exponent

    # Adjust roughness based on phongboost, this adjustment is heuristic and may need tuning
    # Assuming phongboost scales between 0 and 10 as a common range; adjust if your range differs
    boost_adjustment = np.log1p(phongboost) / np.log1p(50)  # Logarithmic adjustment for smoother scaling

    # Final roughness combines preliminary roughness with an adjustment based on phongboost
    # The direction and magnitude of this adjustment can be tweaked as necessary
    final_roughness = np.clip(preliminary_roughness + (boost_adjustment * 0.1) - 0.05, 0, 1)

    return final_roughness

@register_material_converter(SourceType.Source1Source, GameType.CS2, "vertexlitgeneric", True)
def convert_vertex_lit_generic_flexed(material_path: Path, buffer: Buffer, content_manager: ContentManager,
                                      enable_flexes: bool = True):
    material = VMT(buffer, material_path.as_posix())
    texture_output_path = material_path.parent

    textures = {}
    if material.get('proxies', None):
        proxies = material.get('proxies')
        for proxy_name, proxy_data in proxies.items():
            if proxy_name == 'selectfirstifnonzero':
                result_var = proxy_data.get('resultvar')
                src1_var = proxy_data.get('srcvar1')
                src2_var = proxy_data.get('srcvar2')
                src1_value, src1_type = material.get_vector(src1_var, [0])
                if not all(src1_value):
                    material.data[result_var] = material.get(src2_var)
                else:
                    material.data[result_var] = material.get(src1_var)

    base_texture_param = material.get_string('$basetexture', None)
    if base_texture_param is not None:
        base_texture = textures['color_map'] = load_texture(base_texture_param, content_manager)

        if material.get_int('$basemapalphaphongmask', 0):
            textures['phong_map'] = base_texture.getchannel('A')
        if (material.get_int('$basemapalphaenvmapmask', 0) or
                material.get_int('$basealphaenvmapmask', 0)):
            textures['env_map'] = base_texture.getchannel('A')
        if (material.get_int('$selfillum', 0) and
                material.get_string('$selfillummask', None) is None):
            textures['illum_mask'] = base_texture.getchannel('A')
        if (material.get_int('$translucent', 0) or
                material.get_int('$alphatest', 0)):
            textures['alpha'] = base_texture.getchannel('A')
        if material.get_int('$blendtintbybasealpha', 0):
            textures['color_mask'] = base_texture.getchannel('A')

    normal_texture_param = material.get_string('$bumpmap', None)
    if normal_texture_param is None:
        normal_texture_param = material.get_string('$normalmap', None)
    if normal_texture_param is not None:
        normal_texture = textures['normal_map'] = load_texture(normal_texture_param, content_manager)
        if material.get_int('$normalmapalphaenvmapmask', 0):
            textures['env_map'] = normal_texture.getchannel('A')

    env_mask_texture_param = material.get_string('$envmapmask', None)
    if material.get_string("$envmap", None) is not None and env_mask_texture_param is not None:
        textures['env_map'] = load_texture(env_mask_texture_param, content_manager)

    phong_exp_texture_param = material.get_string('$phongexponenttexture', None)
    if phong_exp_texture_param is not None:
        textures['phong_exp_map'] = load_texture(phong_exp_texture_param, content_manager)

    selfillum_mask_texture_param = material.get_string('$selfillummask', None)
    if selfillum_mask_texture_param is not None and material.get_int('$selfillum', 0):
        textures['illum_mask'] = load_texture(selfillum_mask_texture_param, content_manager)

    ao_texture_param = material.get_string('$ambientoccltexture', None)
    if ao_texture_param is None:
        ao_texture_param = material.get_string('$ambientocclusiontexture', None)
    if ao_texture_param is not None:
        textures['ao_map'] = load_texture(ao_texture_param, content_manager)
    # TODO: basemapluminancephongmask
    params = {}
    exported_textures = []
    if enable_flexes:
        params["F_MORPH_SUPPORTED"] = 1
        params["shader"] = "csgo_character.vfx"
    else:
        params["shader"] = "csgo_complex.vfx"

    if 'color_map' in textures:
        params['TextureColor'] = write_texture(exported_textures, textures['color_map'].convert("RGB"),
                                               material_path.stem + '_color', texture_output_path)

    if 'normal_map' in textures and not material.get_int('$ssbump', 0):
        tmp = textures['normal_map'].convert("RGB")
        r, g, b = tmp.split()
        g = ImageChops.invert(g)
        tmp = Image.merge('RGB', (r, g, b))
        params['TextureNormal'] = write_texture(exported_textures, tmp, material_path.stem + '_normal',
                                                texture_output_path)

    if 'phong_map' in textures:
        props = {}
        if material.get_int('$phongboost', 0):
            props['brightness'] = material.get_float('$phongboost')
        params['TextureAmbientOcclusion'] = write_texture(exported_textures, textures['phong_map'],
                                                          material_path.stem + '_ao',
                                                          texture_output_path, **props)
        params['g_vReflectanceRange'] = [0.0, 0.5]
    elif 'env_map' in textures:
        params['TextureAmbientOcclusion'] = write_texture(exported_textures, textures['env_map'],
                                                          material_path.stem + '_ao',
                                                          texture_output_path)
        params['g_flAmbientOcclusionDirectSpecular'] = 0.0
    elif 'ao_map' in textures:
        params['TextureAmbientOcclusion'] = write_texture(exported_textures, textures['ao_map'],
                                                          material_path.stem + '_ao',
                                                          texture_output_path)
        params['g_flAmbientOcclusionDirectSpecular'] = 0.0

    if material.get_int('$phong', 0):
        params['F_SPECULAR'] = 1
        exponent = material.get_int('$phongexponent', 0)
        boost = material.get_int('$phongboost', 1)
        if 'phong_exp_map' in textures:
            phong_exp_map_flip = ImageOps.invert(textures['phong_exp_map'].getchannel("R"))
            params['TextureRoughness'] = write_texture(exported_textures, phong_exp_map_flip,
                                                       material_path.stem + '_rough',
                                                       texture_output_path)
        elif exponent:
            spec_value = exponent
            spec_final = (-10642.28 + (254.2042 - -10642.28) / (1 + (spec_value / 2402433e6) ** 0.1705696)) / 255
            spec_final = spec_final * 255/boost
            spec_final = min(255, max(0, spec_final*1.5))
            params['TextureRoughness'] = write_vector([spec_final, spec_final, spec_final, 0.0])
        else:
            params['TextureRoughness'] = write_vector([60.0, 60.0, 60.0, 0.0])

    if material.get_int('$selfillum', 0) and 'illum_mask' in textures:
        params['F_SELF_ILLUM'] = 1
        params['TextureSelfIllumMask'] = write_texture(exported_textures, textures['illum_mask'],
                                                       material_path.stem + 'illum_mask',
                                                       texture_output_path)
        if material.get_vector('$selfillumtint', [0, 0, 0])[1] is not None:
            value, vtype = material.get_vector('$selfillumtint')
            if vtype is int:
                value = [v / 255 for v in value]
            params['g_vSelfIllumTint'] = write_vector(ensure_length(value, 3, 1.0))
        if material.get_int('$selfillummaskscale', 0):
            params['g_flSelfIllumScale'] = material.get_int('$selfillummaskscale')

    if material.get_int('$translucent', 0) and material.get_int('$alphatest', 0):
        if material.get_int('$translucent', 0):
            params['F_TRANSLUCENT'] = 1
        elif material.get_int('$alphatest', 0):
            params['F_ALPHA_TEST'] = 1
        if material.get_int('$additive', 0):
            params['F_ADDITIVE_BLEND'] = 1
        params['TextureTranslucency'] = write_texture(exported_textures, textures['alpha'],
                                                      material_path.stem + 'trans',
                                                      texture_output_path)

    if material.get_vector('$color', None)[1] is not None:
        value, vtype = material.get_vector('$color')
        if vtype is int:
            value = [v / 255 for v in value]
        params['g_vColorTint'] = write_vector(ensure_length(value, 3, 1.0))
    elif material.get_vector('$color2', None)[1] is not None:
        if material.get_int('$blendtintbybasealpha', 0):
            params['F_TINT_MASK'] = 1
            params['TextureTintMask'] = write_texture(exported_textures, textures['color_mask'],
                                                      material_path.stem + 'colormask',
                                                      texture_output_path)
        value, vtype = material.get_vector('$color2')
        if vtype is int:
            value = [v / 255 for v in value]
        params['g_vColorTint'] = write_vector(ensure_length(value, 3, 1.0))

    if material.get_string('$detail', None) is not None and False:
        params['TextureDetail'] = 'NOT IMPLEMENTED'
        params['F_DETAIL_TEXTURE'] = 2 if material.get_int('$detailblendmode', 0) else 1
        if material.get_int('$detailscale', 0):
            value = material.get_int('$detailscale', 0)
            params['g_vDetailTexCoordScale'] = f'[{value} {value}]'
        if material.get_int('$detailblendfactor', 0):
            value = material.get_int('$detailblendfactor', 0)
            params['g_flDetailBlendFactor'] = value

    print("Unused params:")
    for k, v in material.get_unvisited_params().items():
        print(f"{k} = {v}")

    return params, exported_textures


@register_material_converter(SourceType.Source1Source, GameType.CS2, "vertexlitgeneric", False)
def convert_vertex_lit_generic(material_path: Path, buffer: Buffer, content_manager: ContentManager):
    return convert_vertex_lit_generic_flexed(material_path, buffer, content_manager, False)

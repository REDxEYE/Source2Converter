from PIL import ImageOps

from .shader_base import ShaderBase


class VertexLitGeneric(ShaderBase):

    def convert(self):
        material = self._material
        vmat_params = self._vmat_params

        if material.get_subblock('proxies', None):
            proxies = material.get_subblock('proxies')
            for proxy_name, proxy_data in proxies.items():
                if proxy_name == 'selectfirstifnonzero':
                    result_var = proxy_data.get('resultvar')
                    src1_var = proxy_data.get('srcvar1')
                    src2_var = proxy_data.get('srcvar2')
                    src1_value, src1_type = material.get_vector(src1_var, [0])
                    if not all(src1_value):
                        material.get_raw_data()[result_var] = material.get_param(src2_var)
                    else:
                        material.get_raw_data()[result_var] = material.get_param(src1_var)

        base_texture_param = material.get_string('$basetexture', None)
        if base_texture_param is not None:
            base_texture = self._textures['color_map'] = self.load_texture(base_texture_param)

            if material.get_int('$basemapalphaphongmask', 0):
                self._textures['phong_map'] = base_texture.getchannel('A')
            if material.get_int('$basemapalphaenvmapmask', 0):
                self._textures['env_map'] = base_texture.getchannel('A')
            if material.get_int('$selfillum', 0) and \
                    material.get_string('$selfillummask', None) is None:
                self._textures['illum_mask'] = base_texture.getchannel('A')
            if material.get_int('$translucent', 0) or material.get_int('$alphatest', 0):
                self._textures['alpha'] = base_texture.getchannel('A')
            if material.get_int('$basealphaenvmapmask', 0):
                self._textures['env_map'] = base_texture.getchannel('A')
            if material.get_int('$blendtintbybasealpha', 0):
                self._textures['color_mask'] = base_texture.getchannel('A')

        normal_texture_param = material.get_string('$bumpmap', None)
        if normal_texture_param is None:
            normal_texture_param = material.get_string('$normalmap', None)
        if normal_texture_param is not None:
            normal_texture = self._textures['normal_map'] = self.load_texture(normal_texture_param)
            if material.get_int('$basemapalphaphongmask', 0):
                self._textures['phong_map'] = normal_texture.getchannel('A')
            if material.get_int('$normalmapalphaenvmapmask', 0):
                self._textures['env_map'] = normal_texture.getchannel('A')

        env_mask_texture_param = material.get_string('$envmapmask', None)
        if material.get_string("$envmap", None) is not None and env_mask_texture_param is not None:
            self._textures['env_map'] = self.load_texture(env_mask_texture_param)

        phong_exp_texture_param = material.get_string('$phongexponenttexture', None)
        if phong_exp_texture_param is not None:
            self._textures['phong_exp_map'] = self.load_texture(phong_exp_texture_param)

        selfillum_mask_texture_param = material.get_string('$selfillummask', None)
        if selfillum_mask_texture_param is not None and material.get_int('$selfillum', 0):
            self._textures['illum_mask'] = self.load_texture(selfillum_mask_texture_param)

        ao_texture_param = material.get_string('$ambientoccltexture', None)
        if ao_texture_param is None:
            ao_texture_param = material.get_string('$ambientocclusiontexture', None)
        if ao_texture_param is not None:
            self._textures['ao_map'] = self.load_texture(ao_texture_param)

        if 'color_map' in self._textures:
            vmat_params['TextureColor'] = self.write_texture(self._textures['color_map'].convert("RGB"), 'color')
        if 'normal_map' in self._textures and not material.get_int('$ssbump', 0):
            vmat_params['TextureNormal'] = self.write_texture(self._textures['normal_map'].convert("RGB"), 'normal',
                                                              {"legacy_source1_inverted_normal": 1})
        if 'phong_map' in self._textures:
            props = {}
            if material.get_int('$phongboost', 0):
                props['brightness'] = material.get_float('$phongboost')
            vmat_params['TextureAmbientOcclusion'] = self.write_texture(self._textures['phong_map'], 'ao', props)
            vmat_params['g_vReflectanceRange'] = [0.000, 0.5]
        elif 'env_map' in self._textures:
            vmat_params['TextureAmbientOcclusion'] = self.write_texture(self._textures['env_map'], 'ao')
            vmat_params['g_flAmbientOcclusionDirectSpecular'] = 0.000
        elif 'ao_map' in self._textures:
            vmat_params['TextureAmbientOcclusion'] = self.write_texture(self._textures['ao_map'], 'ao')
            vmat_params['g_flAmbientOcclusionDirectSpecular'] = 0.0

        if material.get_int('$phong', 0):
            vmat_params['F_SPECULAR'] = 1
            if 'phong_exp_map' in self._textures:
                phong_exp_map_flip = self._textures['phong_exp_map'].convert('RGB')
                phong_exp_map_flip = ImageOps.invert(phong_exp_map_flip)
                vmat_params['TextureRoughness'] = self.write_texture(phong_exp_map_flip, 'rough')
            elif material.get_int('$phongexponent', 0):
                spec_value = material.get_int('$phongexponent', 0)
                spec_final = (-10642.28 + (254.2042 - -10642.28) / (1 + (spec_value / 2402433e6) ** 0.1705696)) / 255
                spec_final *= 1.5
                vmat_params['TextureRoughness'] = self._write_vector([spec_final, spec_final, spec_final, 0.0])
            else:
                vmat_params['TextureRoughness'] = self._write_vector([60.0, 60.0, 60.0, 0.0])

        if material.get_int('$selfillum', 0) and 'illum_mask' in self._textures:
            vmat_params['F_SELF_ILLUM'] = 1
            vmat_params['TextureSelfIllumMask'] = self.write_texture(self._textures['illum_mask'])
            if material.get_vector('$selfillumtint', [0, 0, 0])[1] is not None:
                value, vtype = material.get_vector('$selfillumtint')
                if vtype is int:
                    value = [v / 255 for v in value]
                vmat_params['g_vSelfIllumTint'] = self._write_vector(self.ensure_length(value, 3, 0.0))
            if material.get_int('$selfillummaskscale', 0):
                vmat_params['g_flSelfIllumScale'] = material.get_int('$selfillummaskscale')

        if material.get_int('$translucent', 0) and material.get_int('$alphatest', 0):
            if material.get_int('$translucent', 0):
                vmat_params['F_TRANSLUCENT'] = 1
            elif material.get_int('$alphatest', 0):
                vmat_params['F_ALPHA_TEST'] = 1
            if material.get_int('$additive', 0):
                vmat_params['F_ADDITIVE_BLEND'] = 1
            vmat_params['TextureTranslucency'] = self.write_texture(self._textures['alpha'], 'trans')

        if material.get_vector('$color', None)[1] is not None:
            value, vtype = material.get_vector('$color')
            if vtype is int:
                value = [v / 255 for v in value]
            vmat_params['g_vColorTint'] = self._write_vector(self.ensure_length(value, 3, 0.0))
        elif material.get_vector('$color2', None)[1] is not None:
            if material.get_int('$blendtintbybasealpha', 0):
                vmat_params['F_TINT_MASK'] = 1
                vmat_params['TextureTintMask'] = self.write_texture(self._textures['color_mask'], 'colormask')
            value, vtype = material.get_vector('$color2')
            if vtype is int:
                value = [v / 255 for v in value]
            vmat_params['g_vColorTint'] = self._write_vector(self.ensure_length(value, 3, 0.0))

        if material.get_string('$detail', None) is not None and False:
            vmat_params['TextureDetail'] = 'NOT IMPLEMENTED'
            vmat_params['F_DETAIL_TEXTURE'] = 2 if material.get_int('$detailblendmode', 0) else 1
            if material.get_int('$detailscale', 0):
                value = material.get_int('$detailscale', 0)
                vmat_params['g_vDetailTexCoordScale'] = f'[{value} {value}]'
            if material.get_int('$detailblendfactor', 0):
                value = material.get_int('$detailblendfactor', 0)
                vmat_params['g_flDetailBlendFactor'] = value

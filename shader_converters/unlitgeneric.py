from PIL import ImageOps

from .shader_base import ShaderBase


class UnlitGeneric(ShaderBase):
    def convert(self):
        material = self._material
        vmat_params = self._vmat_params

        base_texture_param = material.get_string('$basetexture', None)
        if base_texture_param is not None:
            base_texture = self._textures['color_map'] = self.load_texture(base_texture_param)
            if material.get_int('$translucent', 0) or material.get_int('$alphatest', 0):
                self._textures['alpha'] = base_texture.getchannel('A')

        vmat_params['F_SELF_ILLUM'] = 1
        if 'color_map' in self._textures:
            vmat_params['TextureColor'] = self.write_texture(self._textures['color_map'].convert("RGB"), 'color')

        if material.get_int('$color', 0):
            vtype, value = material.get_vector('$color')
            if vtype is int:
                value = [v / 255 for v in value]
            vmat_params['g_vColorTint'] = self._write_vector(self.ensure_length(value, 3, 0.0))
        elif material.get_int('$color2', 0):
            if material.get_int('$blendtintbybasealpha', 0):
                vmat_params['F_TINT_MASK'] = 1
                vmat_params['TextureTintMask'] = self.write_texture(self._textures['mask'], 'colormask')
            vtype, value = material.get_vector('$color2')
            if vtype is int:
                value = [v / 255 for v in value]
            vmat_params['g_vColorTint'] = self._write_vector(self.ensure_length(value, 3, 0.0))
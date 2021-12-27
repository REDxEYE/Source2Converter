from PIL import ImageOps

from .shader_base import ShaderBase


class EyeRefract(ShaderBase):
    def convert(self):
        material = self._vmt
        vmat_params = self._vmat_params

        base_texture_param = material.get_string('$iris', None)
        if base_texture_param is not None:
            basetexture = self._textures['color_map'] = self.load_texture(base_texture_param)
            self._textures['color_map'] = basetexture.convert('RGB')
        vmat_params['TextureColor'] = self.write_texture(self._textures['color_map'].convert("RGB"), 'color')

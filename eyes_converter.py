import numpy as np

from SourceIO.source1.mdl.structs.bone import Bone
from SourceIO.source1.mdl.structs.eyeball import Eyeball
from SourceIO.utilities.datamodel import DataModel, load
from SourceIO.utilities import datamodel
from SourceIO.source1.mdl.mdl_file import Mdl


class EyeConverter:

    def __init__(self):
        pass

    def get_eye_asset(self):
        return load('assets/eye.dmx')

    def process_mdl(self, mdl: Mdl):
        eyeballs = []
        for bodygroup in mdl.body_parts:
            for model in bodygroup.models:
                if model.eyeballs:
                    eyeballs.extend(model.eyeballs)
        for eyeball in eyeballs:
            parent_bone = mdl.bones[eyeball.bone_index]
            eye_asset = self.get_eye_asset()
            eye_asset = self.adjust_uv(eye_asset, eyeball)
            eye_asset = self.adjust_position(eye_asset, eyeball, parent_bone)
            if eyeball.name == "":
                eyeball.name = 'eyeball_' + ('L' if eyeball.org[0] > 0 else 'R')
            eye_asset.write(eyeball.name + '.dmx', 'binary', 9)

    @staticmethod
    def adjust_uv(eye_asset: DataModel, eyeball: Eyeball):
        vertex_data_block = eye_asset.find_elements('bind', elemtype='DmeVertexData')[0]
        uv_data = np.array(vertex_data_block['texcoord$0'])
        non_zero = np.where((uv_data != [0.0, 0.0]).all(axis=1))[0]
        scale = eyeball.iris_scale / 2
        uv_data[non_zero] *= scale
        uv_data[non_zero] += ((scale / 2) * (1 if eyeball.iris_scale > 2 else -1))
        vertex_data_block['texcoord$0'] = datamodel.make_array(uv_data, datamodel.Vector2)
        return eye_asset

    @staticmethod
    def adjust_position(eye_asset: DataModel, eyeball: Eyeball, parent_bone: Bone):
        vertex_data_block = eye_asset.find_elements('bind', elemtype='DmeVertexData')[0]
        vertex_data_data = np.array(vertex_data_block['position$0'])
        scale = eyeball.radius
        vertex_data_data *= scale
        vertex_data_data += np.array(eyeball.org)
        vertex_data_block['position$0'] = datamodel.make_array(vertex_data_data, datamodel.Vector3)
        return eye_asset

from pathlib import Path

import numpy as np
from scipy.spatial.transform import Rotation as R

from SourceIO.source1.dmx.source1_to_dmx import normalize_path
from SourceIO.source1.mdl.structs.bone import Bone
from SourceIO.source1.mdl.structs.eyeball import Eyeball
from SourceIO.source_shared.content_manager import ContentManager
from SourceIO.utilities.datamodel import DataModel, load
from SourceIO.utilities import datamodel
from SourceIO.source1.mdl.mdl_file import Mdl


class EyeConverter:
    def __init__(self):
        pass

    def get_eye_asset(self):
        return load('assets/eye.dmx')

    def process_mdl(self, mdl: Mdl, output_path):
        output_path = Path(output_path)
        eyeballs = []
        dmx_eyebals = []
        for bodygroup in mdl.body_parts:
            for model in bodygroup.models:
                for mesh in model.meshes:
                    if mesh.material_type == 1:
                        model.eyeballs[mesh.material_param].material_id = mesh.material_index
                if model.eyeballs:
                    eyeballs.extend(model.eyeballs)
        for eyeball in eyeballs:
            parent_bone = mdl.bones[eyeball.bone_index]
            if eyeball.name == "":
                eyeball.name = 'eyeball_' + ('L' if eyeball.org[0] > 0 else 'R')
            eye_asset = self.get_eye_asset()
            eye_asset = self.adjust_uv(eye_asset, eyeball)
            eye_asset = self.adjust_position(eye_asset, eyeball, parent_bone)
            eye_asset = self.adjust_bones(eye_asset, eyeball, parent_bone)
            mat = eye_asset.find_elements(elemtype='DmeMaterial')[0]
            faceset = eye_asset.find_elements(elemtype='DmeFaceSet')[0]
            material_path = material_name = mdl.materials[eyeball.material_id].name
            for cd_mat in mdl.materials_paths:
                full_path = ContentManager().find_material(Path(cd_mat) / material_name)
                if full_path is not None:
                    material_path = str(
                        Path('materials') / Path(normalize_path(cd_mat)) / normalize_path(material_name))
                    break

            mat.name = material_name
            mat['mtlName'] = material_path
            faceset.name = mdl.materials[eyeball.material_id].name
            faceset['mtlName'] = material_path

            eyeball_filename = output_path / (eyeball.name + '.dmx')
            dmx_eyebals.append((eyeball.name, eyeball_filename))
            eye_asset.write(eyeball_filename, 'binary', 9)
        return dmx_eyebals

    @staticmethod
    def adjust_uv(eye_asset: DataModel, eyeball: Eyeball):
        vertex_data_block = eye_asset.find_elements('bind', elemtype='DmeVertexData')[0]
        uv_data = np.array(vertex_data_block['texcoord$0'])
        non_zero = np.where((uv_data != [0.0, 1.0]).all(axis=1))[0]
        scale = eyeball.iris_scale / 2
        uv_data[non_zero] *= scale
        uv_data[non_zero] += 0.5
        vertex_data_block['texcoord$0'] = datamodel.make_array(uv_data, datamodel.Vector2)
        return eye_asset

    @staticmethod
    def adjust_position(eye_asset: DataModel, eyeball: Eyeball, parent_bone: Bone):
        vertex_data_block = eye_asset.find_elements('bind', elemtype='DmeVertexData')[0]
        vertex_data_pos = np.array(vertex_data_block['position$0'])
        vertex_data_norm = np.array(vertex_data_block['normal$0'])
        scale = eyeball.radius
        vertex_data_pos *= scale * 0.95
        eye_org = np.array(eyeball.org)
        eye_org[0] *= -1

        up_axis = vector_i_rotate(eyeball.up, parent_bone.pose_to_bone)
        if up_axis[1] > 0.99 or up_axis[1] < 1.01:
            pass

        eyeball_orientation_matrix = rotation_matrix((up_axis * 90))

        vertex_data_pos = np.dot(eyeball_orientation_matrix, vertex_data_pos.T).T
        vertex_data_norm = np.dot(eyeball_orientation_matrix, vertex_data_norm.T).T
        transform = collect_transforms(parent_bone)
        M = np.ones([4, len(vertex_data_pos)], dtype=np.float32)
        M[0:3, :] = vertex_data_pos.T
        vertex_data_pos = transform @ M
        vertex_data_pos = vertex_data_pos[0:3, :].T
        vertex_data_pos = np.subtract(vertex_data_pos, eye_org)

        transform[0][3] = 0
        transform[1][3] = 0
        transform[2][3] = 0
        M = np.ones([4, len(vertex_data_norm)], dtype=np.float32)
        M[0:3, :] = vertex_data_norm.T
        vertex_data_norm = transform @ M
        vertex_data_norm = vertex_data_norm[0:3, :].T
        vertex_data_norm = np.apply_along_axis(normalized,
                                               1,
                                               vertex_data_norm)[:, 0, :]
        vertex_data_block['position$0'] = datamodel.make_array(vertex_data_pos, datamodel.Vector3)
        vertex_data_block['normal$0'] = datamodel.make_array(vertex_data_norm, datamodel.Vector3)
        return eye_asset

    @staticmethod
    def adjust_bones(eye_asset: DataModel, eyeball: Eyeball, parent_bone: Bone):
        head_bone: datamodel.Element = find_element(eye_asset, name='HEAD', elem_type='DmeJoint')
        head_transform: datamodel.Element = head_bone['transform']

        eye_bone: datamodel.Element = find_element(eye_asset, name='EYE', elem_type='DmeJoint')
        eye_transform: datamodel.Element = eye_bone['transform']

        eye_bone.name = eyeball.name
        eye_transform.name = eyeball.name

        head_bone.name = parent_bone.name
        head_transform.name = parent_bone.name

        eye_org = np.array(eyeball.org)
        # eye_org[0] *= -1

        eye_transform['position'] = datamodel.Vector3(eye_org)
        head_transform['position'] = datamodel.Vector3(parent_bone.position)
        head_transform['orientation'] = datamodel.Vector3(parent_bone.rotation)

        head_transform2, eye_transform2 = eye_asset.root['skeleton']['baseStates'][0]['transforms'][:2]

        eye_transform2['position'] = datamodel.Vector3(eye_org)
        eye_transform2.name = eyeball.name
        head_transform2['position'] = datamodel.Vector3(parent_bone.position)
        head_transform2['orientation'] = datamodel.Vector3(parent_bone.rotation)
        head_transform2.name = parent_bone.name

        return eye_asset


def find_element(dm: DataModel, name=None, elem_type=None):
    for elem in dm.elements:
        elem: datamodel.Element
        if name is not None and elem.name != name:
            continue
        if elem_type is not None and elem.type != elem_type:
            continue
        return elem


def rotation_matrix(rotation):
    """
    Return the rotation matrix associated with counterclockwise rotation about
    the given axis by theta radians.
    """
    r: R = R.from_euler('XYZ', rotation, degrees=True)
    return r.as_matrix()


def normalized(a, axis=-1, order=2):
    l2 = np.atleast_1d(np.linalg.norm(a, order, axis))
    l2[l2 == 0] = 1
    return a / np.expand_dims(l2, axis)


def collect_transforms(bone: Bone):
    # bone.rotation - Euler
    # bone.position - Vector3D
    matrix = bone.matrix  # 4x4 Matrix
    if bone.parent_bone_index != -1:
        parent_transform = collect_transforms(bone.parent)
        return np.dot(parent_transform, matrix, )
    else:
        return matrix


def vector_i_rotate(inp, matrix):
    return np.dot(inp, matrix[:3, :3])

from pathlib import Path
from typing import Optional

import numpy as np

from SourceIO.library.models.mdl.structs.header import StudioHDRFlags
from SourceIO.library.models.mdl.v49 import MdlV49
from SourceIO.library.models.mdl.structs import (
    Bone as MdlBone,
    Model as MdlModel,
    Mesh as MdlMesh,
    BodyPart as MdlBodyPart
)
from SourceIO.library.models.vtx import open_vtx
from SourceIO.library.models.vtx.v7.structs import (
    BodyPart as VtxBodyPart,
    Model as VtxModel,
    ModelLod as VtxModelLod,
    Mesh as VtxMesh
)
from SourceIO.library.models.vvd import Vvd
from SourceIO.library.shared.content_providers.content_manager import ContentManager
from SourceIO.library.utils import Buffer
from SourceIO.library.utils.common import get_slice
from SourceIO.library.utils.path_utilities import find_vtx_cm, path_stem, collect_full_material_names
from SourceIO.logger import SourceLogMan
from source2converter.mdl.model_converter_tags import register_model_converter
from source2converter.model import Model, Skeleton, Material, Mesh, Lod, SubModel, BodyGroup, ShapeKey, LoddedSubModel, \
    NullSubModel
from source2converter.model.skeleton import Bone, Attachment, AttachmentParentType
from source2converter.utils.math_utils import decompose_matrix_to_rts, quaternion_to_euler

log_manager = SourceLogMan()
logger = log_manager.get_logger('MDL Converter')


def convert_skeleton(mdl: MdlV49):
    if mdl.header.flags & StudioHDRFlags.STATIC_PROP:
        return None
    mdl_bones: list[MdlBone] = mdl.bones
    skeleton = Skeleton()
    for mdl_bone in mdl_bones:
        parent_id = mdl_bone.parent_bone_id
        parent_name = mdl_bones[parent_id].name if parent_id >= 0 else None
        bone = Bone(mdl_bone.name, parent_name, mdl_bone.position, mdl_bone.quat)
        skeleton.bones.append(bone)
    return skeleton


def update_mesh_for_lod(mesh):
    # Step 1: Identify all used vertices across strips
    all_used_indices = np.unique(np.concatenate([strip[1] for strip in mesh.strips]))

    # Map old indices to new indices
    index_mapping = np.full(np.max(all_used_indices) + 1, -1, dtype=int)
    index_mapping[all_used_indices] = np.arange(all_used_indices.size)

    # Step 2: Remap indices in each strip
    mesh.strips = [(mat_idx, index_mapping[indices]) for mat_idx, indices in mesh.strips]

    # Step 3 & 4: Adjust and Remap Shape Key Indices
    for shape_key in mesh.shape_keys:
        # Determine which indices in the shape key are also in the LOD
        valid_indices_mask = np.isin(shape_key.indices, all_used_indices)
        filtered_indices = shape_key.indices[valid_indices_mask]

        # Remap these indices to the new indices in the LOD mesh
        remapped_indices = index_mapping[filtered_indices]

        # Filter and remap shape key indices
        shape_key.indices = remapped_indices

        # Step 5: Adjust delta_attributes only for valid (remaining) indices
        for attr, deltas in shape_key.delta_attributes.items():
            shape_key.delta_attributes[attr] = deltas[valid_indices_mask]

    # Create new vertex attributes containing only used vertices
    mesh.vertex_attributes = {attr: data[all_used_indices] for attr, data in mesh.vertex_attributes.items()}


@register_model_converter(b"IDST", 44)
@register_model_converter(b"IDST", 45)
@register_model_converter(b"IDST", 46)
@register_model_converter(b"IDST", 47)
@register_model_converter(b"IDST", 49)
def convert_mdl_v49(model_path: Path, buffer: Buffer, content_manager: ContentManager) -> Optional[Model]:
    mdl = MdlV49.from_buffer(buffer)
    vtx_buffer = find_vtx_cm(model_path, content_manager)
    vvd_buffer = content_manager.find_file(model_path.with_suffix(".vvd"))
    if vtx_buffer is None or vvd_buffer is None:
        logger.error(f"Could not find VTX and/or VVD file for {model_path}")
        return None
    vtx = open_vtx(vtx_buffer)
    vvd = Vvd.from_buffer(vvd_buffer)

    mdl_name = path_stem(mdl.header.name)

    skeleton = convert_skeleton(mdl)

    model = Model(mdl_name, skeleton)

    full_material_names = collect_full_material_names([mat.name for mat in mdl.materials], mdl.materials_paths,
                                                      content_manager)
    for material_name, material_path in full_material_names.items():
        model.materials.append(
            Material(material_name, material_path + ".vmt", content_manager.find_material(material_path)))

    for vtx_body_part, body_part in zip(vtx.body_parts, mdl.body_parts):
        vtx_body_part: VtxBodyPart
        body_part: MdlBodyPart
        submodels = []
        for vtx_model, mdl_model in zip(vtx_body_part.models, body_part.models):
            vtx_model: VtxModel
            mdl_model: MdlModel
            lods = []
            if mdl_model.vertex_count == 0:
                submodels.append(NullSubModel())
                continue
            for vtx_lod in vtx_model.model_lods:
                lod_vertices = get_slice(vvd.lod_data[0], mdl_model.vertex_offset, mdl_model.vertex_count)
                vertex_attributes = {
                    "positions": lod_vertices["vertex"],
                    "normals": lod_vertices["normal"],
                    "uv0": lod_vertices["uv"],
                    "blend_weights": lod_vertices["weight"],
                    "blend_indices": lod_vertices["bone_id"],
                }
                strips = []
                shape_keys = {}
                for n, (vtx_mesh, mdl_mesh) in enumerate(zip(vtx_lod.meshes, mdl_model.meshes)):
                    vtx_mesh: VtxMesh
                    mdl_mesh: MdlMesh
                    if not vtx_mesh.strip_groups:
                        continue
                    for mdl_flex in mdl_mesh.flexes:
                        model.has_shape_keys = True
                        flex_name = mdl.flex_names[mdl_flex.flex_desc_index]
                        if flex_name in shape_keys:
                            shape_key = shape_keys[flex_name]
                            shape_key.indices = np.append(shape_key.indices,
                                                          mdl_flex.vertex_animations[
                                                              "index"] + mdl_mesh.vertex_index_start).ravel()
                            shape_key.delta_attributes["positions"] = np.append(shape_key.delta_attributes["positions"],
                                                                                mdl_flex.vertex_animations[
                                                                                    "vertex_delta"]).reshape(-1, 3)
                            shape_key.delta_attributes["normals"] = np.append(shape_key.delta_attributes["normals"],
                                                                              mdl_flex.vertex_animations[
                                                                                  "normal_delta"]).reshape(-1, 3)
                        else:
                            shape_key = ShapeKey(flex_name,
                                                 mdl_flex.vertex_animations[
                                                     "index"].ravel() + mdl_mesh.vertex_index_start,
                                                 {
                                                     "positions": mdl_flex.vertex_animations["vertex_delta"].reshape(-1,
                                                                                                                     3),
                                                     "normals": mdl_flex.vertex_animations["normal_delta"].reshape(-1,
                                                                                                                   3),
                                                 })
                            shape_key.stereo = mdl_flex.partner_index != 0
                            shape_keys[flex_name] = shape_key

                    for strip_group in vtx_mesh.strip_groups:
                        indices = np.add(
                            strip_group.vertexes[strip_group.indices]["original_mesh_vertex_index"].astype(np.uint32),
                            mdl_mesh.vertex_index_start)
                        strips.append((mdl_mesh.material_index, indices.ravel()))
                mesh = Mesh(mdl_model.name, strips, vertex_attributes, list(shape_keys.values()))
                update_mesh_for_lod(mesh)
                lods.append(
                    Lod(
                        vtx_lod.switch_point,
                        mesh
                    )
                )
            submodels.append(LoddedSubModel(mdl_model.name, lods))
        model.bodygroups.append(BodyGroup(body_part.name, submodels))

    for mdl_attachment in mdl.attachments:
        rotation, translation, scale = decompose_matrix_to_rts(np.asarray(mdl_attachment.matrix).reshape(3, 4))
        attachment = Attachment(mdl_attachment.name, AttachmentParentType.SINGLE_BONE,
                                mdl.bones[mdl_attachment.parent_bone].name, translation, rotation)
        model.attachments.append(attachment)

    return model

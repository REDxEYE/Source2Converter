from pathlib import Path

import numpy as np

from SourceIO.library.shared.content_providers.content_manager import ContentManager
from SourceIO.library.source1.dmx.source1_to_dmx import DmxModel2
from SourceIO.library.source1.vmt import VMT
from SourceIO.library.utils import datamodel
from SourceIO.library.utils.datamodel import Vector3, Vector2
from SourceIO.library.utils.s1_keyvalues import KVWriter
from SourceIO.logger import SourceLogMan
from source2converter.materials.material_converter_tags import choose_material_converter, SourceType, GameType
from source2converter.mdl import choose_model_converter
from source2converter.model import NullSubModel, LoddedSubModel
from source2converter.model.skeleton import AttachmentParentType
from source2converter.utils.math_utils import quaternion_to_euler
from source2converter.utils.vmdl import Vmdl, BodyGroupList, BodyGroup, BodyGroupChoice, RenderMeshList, RenderMeshFile, \
    LODGroupList, LODGroup, BoneMarkupList, AnimationList, EmptyAnim, AttachmentList, Attachment
from utils import sanitize_name, normalize_path

log_manager = SourceLogMan()
logger = log_manager.get_logger('S2Conv')

if __name__ == '__main__':
    def main():
        content_path = Path(
            r"D:\SteamLibrary\steamapps\common\Counter-Strike Global Offensive\content\csgo_addons\s2fm")
        cm = ContentManager()
        cm.scan_for_content(r"D:\SteamLibrary\steamapps\common\Half-Life 2\hl2\models")
        model_path = Path("models/combine_soldier.mdl")
        buffer = cm.find_file(model_path)
        ident, version = buffer.read_fmt("4sI")
        cp = cm.get_content_provider_from_asset_path(model_path)
        buffer.seek(0)
        handler = choose_model_converter(ident, version, ((cp.steam_id or None) if cp else None))
        model = handler(model_path, buffer, cm)

        vmdl = Vmdl()
        vmdl_bodygroups = vmdl.append(BodyGroupList())
        vmdl_animation_list = vmdl.append(AnimationList())
        vmdl_animation_list.append(EmptyAnim())
        vmdl_lod_group_list = vmdl.append(LODGroupList())
        vmdl_render_mesh_list = vmdl.append(RenderMeshList())
        vmdl.append(BoneMarkupList())
        lod_groups = {}
        for bodygroup in model.bodygroups:
            vmld_bodygroup = BodyGroup(bodygroup.name)
            vmdl_bodygroups.append(vmld_bodygroup)
            for sub_model in bodygroup.sub_models:
                if isinstance(sub_model, NullSubModel):
                    vmld_bodygroup.append(BodyGroupChoice([]))
                elif isinstance(sub_model, LoddedSubModel):
                    sub_model_name = sanitize_name(sub_model.name)
                    vmdl_bodygroup_choice = BodyGroupChoice([])
                    vmld_bodygroup.append(vmdl_bodygroup_choice)

                    for i, lod in enumerate(sub_model.lods):
                        if i in lod_groups:
                            log_group = lod_groups[i]
                        else:
                            if lod.switch_point < 0:
                                switch_point = 99999999.0
                            else:
                                switch_point = lod.switch_point
                            log_group = lod_groups[i] = LODGroup(switch_point)
                            vmdl_lod_group_list.append(log_group)

                        if i == 0:
                            mesh_filename = sub_model_name
                        else:
                            mesh_filename = f"{sub_model_name}_LOD{i}"
                        vmdl_bodygroup_choice.meshes.append(mesh_filename)
                        dm_model = export_dmx(lod, model, sub_model)
                        model_content_path = normalize_path(model_path.with_suffix(""))

                        log_group.meshes.append(mesh_filename)
                        render_mesh = RenderMeshFile(mesh_filename,
                                                     (model_content_path / (mesh_filename + ".dmx")).as_posix())
                        vmdl_render_mesh_list.append(render_mesh)

                        dmx_output_path = content_path / model_content_path
                        dmx_path = dmx_output_path / (mesh_filename + ".dmx")
                        logger.info(f"Writting mesh file to {dmx_path}")
                        dm_model.save(dmx_path, "binary", 9)
                else:
                    logger.warn("Unknown submodel type")
                    continue
        vmdl_data = vmdl.write()
        with (content_path / model_path.with_suffix(".vmdl")).open("w", encoding="utf8") as f:
            f.write(vmdl_data)

        vmdl_attachtments = vmdl.append(AttachmentList())
        for attachment in model.attachments:
            if attachment.parent_type != AttachmentParentType.SINGLE_BONE:
                logger.warn(f"Non SINGLE_BONE attachments({attachment.name}) not supported")
                continue
            vmdl_attachment = Attachment(attachment.name, attachment.parent_name, attachment.translation,
                                         quaternion_to_euler(attachment.rotation))
            vmdl_attachtments.append(vmdl_attachment)
        for material in model.materials:
            if material.full_path.endswith(".vmt"):
                material_data = VMT(material.buffer, material.full_path)
                material.buffer.seek(0)
                logger.info(f"Processing Source1 material: {material.full_path}")
                converter = choose_material_converter(SourceType.Source1Source, GameType.CS2, material_data.shader,
                                                      model.has_shape_keys)
                if converter is not None:
                    vmat_props, textures = converter(Path(material.full_path), material.buffer, cm)
                    tmp = Path(material.full_path)
                    materials_output_path = content_path / tmp.parent
                    material_save_path = materials_output_path / (tmp.stem + ".vmat")
                    material_save_path.parent.mkdir(parents=True, exist_ok=True)
                    with material_save_path.open('w') as file:
                        file.write('// Generated by Source2Converter\r\n')
                        writer = KVWriter(file)
                        writer.write(('Layer0', vmat_props), 1, True)
                    for texture in textures:
                        texture_save_path = (content_path / texture.filepath)
                        texture_save_path.parent.mkdir(parents=True, exist_ok=True)
                        texture.image.save(texture_save_path)

                else:
                    logger.warn(f"No converter found for {material.full_path} material")


    def export_dmx(lod, model, sub_model):
        dm_model = DmxModel2(model.name)
        attribute_names = dm_model.supported_attributes()
        for material in model.materials:
            dm_model.add_material(sanitize_name(material.name),
                                  normalize_path(material.full_path).with_suffix(""))
        bone_names = []
        if model.skeleton is not None:
            dm_model.add_skeleton(sanitize_name(sub_model.name) + "_skeleton")
            for bone in model.skeleton.bones:
                bone_names.append(bone.name)
                dm_model.add_bone(bone.name, bone.translation, bone.rotation, bone.parent_name)
        mesh = lod.mesh
        dm_mesh = dm_model.add_mesh(sub_model.name, len(mesh.shape_keys) > 0)
        for mat_id, indices in mesh.strips:
            material = model.materials[mat_id]
            dm_model.mesh_add_faceset(dm_mesh, sanitize_name(material.name), indices)
        dm_model.mesh_add_attribute(dm_mesh, "pos", mesh.vertex_attributes["positions"], Vector3)
        dm_model.mesh_add_attribute(dm_mesh, "norm", mesh.vertex_attributes["normals"], Vector3)
        dm_model.mesh_add_attribute(dm_mesh, "texco", mesh.vertex_attributes["uv0"], Vector2)
        tmp_vertices = mesh.vertex_attributes["positions"]
        dimm = tmp_vertices.max() - tmp_vertices.min()
        balance_width = dimm * (1 - (99.3 / 100))
        balance = tmp_vertices[:, 0]
        balance = np.clip((-balance / balance_width / 2) + 0.5, 0, 1)
        dm_model.mesh_add_attribute(dm_mesh, "balance", balance, float)
        flex_controllers = {}
        for shape_key in mesh.shape_keys:
            flex_controller = dm_model.add_flex_controller(shape_key.name, shape_key.stereo, False)
            dm_model.flex_controller_add_delta_name(flex_controller, shape_key.name, 0)
            flex_controllers[shape_key.name] = flex_controller

            vertex_delta_data = dm_model.mesh_add_delta_state(dm_mesh, shape_key.name)

            vertex_delta_data[attribute_names['pos']] = datamodel.make_array(
                shape_key.delta_attributes["positions"], Vector3)
            vertex_delta_data[attribute_names['pos'] + "Indices"] = datamodel.make_array(
                shape_key.indices,
                int)
            vertex_delta_data[attribute_names['norm']] = datamodel.make_array(
                shape_key.delta_attributes["normals"], Vector3)
            vertex_delta_data[attribute_names['norm'] + "Indices"] = datamodel.make_array(
                shape_key.indices,
                int)
        for flex_controller in flex_controllers.values():
            dm_model.flex_controller_finish(flex_controller, len(flex_controller["rawControlNames"]))
        if bone_names:
            dm_model.mesh_add_bone_weights(dm_mesh, bone_names, mesh.vertex_attributes["blend_weights"],
                                           mesh.vertex_attributes["blend_indices"])
        vertex_data = dm_mesh["bindState"]
        vertex_data["flipVCoordinates"] = False
        vertex_data["jointCount"] = 3
        return dm_model


    main()

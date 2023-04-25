import os
from tkinter.filedialog import askdirectory
from subprocess import Popen, PIPE
from typing import Optional, Tuple, List

import numpy as np

from SourceIO.library.shared.content_providers.content_manager import ContentManager
from SourceIO.library.source1.dmx.source1_to_dmx import DmxModel2, get_slice
from SourceIO.library.source1.mdl.structs.bodygroup import BodyPart
from SourceIO.library.source1.mdl.structs.flex import VertexAminationType
from SourceIO.library.source1.mdl.structs.model import Model
from SourceIO.library.source1.vtx import open_vtx
from SourceIO.library.source1.vtx.v7.structs.bodypart import BodyPart as VtxBodyPart
from SourceIO.library.source1.vtx.v7.structs.model import Model as VtxModel
from SourceIO.library.source1.vvd import Vvd
from SourceIO.library.source2.utils.kv3_generator import KV3mdl
from SourceIO.library.utils import FileBuffer, datamodel
from SourceIO.library.utils.path_utilities import find_vtx_cm
from material_converter import convert_material, Material

os.environ['NO_BPY'] = '1'

from pathlib import Path
import argparse
import math

from ctypes import windll
from SourceIO.logger import SLoggingManager
from logging import DEBUG, INFO
from SourceIO.library.source1.mdl.v49.mdl_file import MdlV49

from utils import normalize_path, collect_materials, sanitize_name

k32 = windll.LoadLibrary('kernel32.dll')
setConsoleModeProc = k32.SetConsoleMode
setConsoleModeProc(k32.GetStdHandle(-11), 0x0001 | 0x0002 | 0x0004)


def get_s2_material_path(mat_name, s1_materials):
    for mat, mat_path, _ in s1_materials:
        if mat == mat_name:
            path = normalize_path((Path('materials') / mat_path / mat).with_suffix('.vmat')).resolve()
            return path


def _convert_model(mdl: MdlV49, vvd: Vvd, model: Model, vtx_model: VtxModel, s2_output_path: Path,
                   materials: List[Material]) -> Path:
    print(f'\t\033[94mGenerating DMX file for\033[0m \033[92m"{model.name}" mesh\033[0m')
    model_name = sanitize_name(model.name)
    dm_model = DmxModel2(model_name, 22)
    dm_model.add_skeleton(model_name + "_skeleton")
    content_path = normalize_path(mdl.header.name).with_suffix("")
    output_path = Path("models", content_path, model_name + ".dmx")

    has_flexes = any(mesh.flexes for mesh in model.meshes)

    for bone in mdl.bones:
        dm_model.add_bone(bone.name, bone.position, bone.quat,
                          mdl.bones[bone.parent_bone_id].name if bone.parent_bone_id != -1 else None)

    for material in mdl.materials:
        full_material_path = next(
            filter(lambda a: a[0].as_posix() == sanitize_name(material.name), materials), None)
        if full_material_path is None:
            full_material_path = material.name
        else:
            full_material_path = Path(full_material_path[1], full_material_path[0])
        dm_model.add_material(sanitize_name(material.name), full_material_path)

    if has_flexes:
        flex_controllers = {}
        # for flex_ui_controller in mdl.flex_ui_controllers:
        #     flex_controller = dm_model.add_flex_controller(flex_ui_controller.name, flex_ui_controller.stereo,
        #                                                    False)
        for mesh in model.meshes:
            for flex in mesh.flexes:
                flex_name = mdl.flex_names[flex.flex_desc_index]
                if flex.partner_index != 0:
                    assert flex_name[-1] == "L"
                    flex_name = flex_name[:-1]
                if flex_name in flex_controllers:
                    continue
                flex_controller = dm_model.add_flex_controller(flex_name, flex.partner_index != 0, False)
                # print(flex_ui_controller)
                # for flex_rule in mdl.flex_rules:
                #     print("\t", mdl.flex_names[flex_rule.flex_index], flex_rule)

                # for flex_controller in mdl.flex_controllers:
                #     print("\t", flex_controller)
                dm_model.flex_controller_add_delta_name(flex_controller, flex_name, 0)
                flex_controllers[flex_name] = flex_controller

            for flex_controller in flex_controllers.values():
                dm_model.flex_controller_finish(flex_controller, len(flex_controller["rawControlNames"]))

    bone_names = [bone.name for bone in mdl.bones]
    vertices = vvd.lod_data[0]

    dm_mesh = dm_model.add_mesh(model_name, has_flexes)
    model_vertices = get_slice(vertices, model.vertex_offset, model.vertex_count)

    dm_model.mesh_add_attribute(dm_mesh, "pos", model_vertices["vertex"], datamodel.Vector3)
    dm_model.mesh_add_attribute(dm_mesh, "norm", model_vertices["normal"], datamodel.Vector3)
    dm_model.mesh_add_attribute(dm_mesh, "texco", model_vertices["uv"], datamodel.Vector2)
    dm_model.mesh_add_bone_weights(dm_mesh, bone_names, model_vertices["weight"], model_vertices["bone_id"])

    for mesh, vmesh in zip(model.meshes, vtx_model.model_lods[0].meshes):
        for strip_group in vmesh.strip_groups:
            indices = np.add(strip_group.vertexes[strip_group.indices]["original_mesh_vertex_index"],
                             mesh.vertex_index_start)

            dm_model.mesh_add_faceset(dm_mesh, sanitize_name(mdl.materials[mesh.material_index].name), indices)

    tmp_vertices = model_vertices['vertex']
    if tmp_vertices.size > 0:
        dimm = tmp_vertices.max() - tmp_vertices.min()
        balance_width = dimm * (1 - (99.3 / 100))
        balance = model_vertices['vertex'][:, 0]
        balance = np.clip((-balance / balance_width / 2) + 0.5, 0, 1)
        dm_model.mesh_add_attribute(dm_mesh, "balance", balance, float)

    vertex_data = dm_mesh["bindState"]
    vertex_data["flipVCoordinates"] = False
    vertex_data["jointCount"] = 3

    if has_flexes:
        attribute_names = dm_model.supported_attributes()
        delta_states = {}
        for mesh in model.meshes:
            for flex_ui_controller in mesh.flexes:
                flex_name = mdl.flex_names[flex_ui_controller.flex_desc_index]
                if flex_ui_controller.partner_index != 0:
                    flex_name = flex_name[:-1]
                if flex_name not in delta_states:
                    vertex_delta_data = delta_states[flex_name] = \
                        dm_model.mesh_add_delta_state(dm_mesh, flex_name)
                    vertex_delta_data[attribute_names['pos']] = datamodel.make_array([], datamodel.Vector3)
                    vertex_delta_data[attribute_names['pos'] + "Indices"] = datamodel.make_array([], int)
                    vertex_delta_data[attribute_names['norm']] = datamodel.make_array([], datamodel.Vector3)
                    vertex_delta_data[attribute_names['norm'] + "Indices"] = datamodel.make_array([], int)

                    if flex_ui_controller.vertex_anim_type == VertexAminationType.WRINKLE:
                        vertex_delta_data["vertexFormat"].append(attribute_names["wrinkle"])
                        vertex_delta_data[attribute_names["wrinkle"]] = datamodel.make_array([], float)
                        vertex_delta_data[attribute_names["wrinkle"] + "Indices"] = datamodel.make_array([], int)

        for mesh in model.meshes:
            for flex_ui_controller in mesh.flexes:
                flex_name = mdl.flex_names[flex_ui_controller.flex_desc_index]
                if flex_ui_controller.partner_index != 0:
                    flex_name = flex_name[:-1]
                vertex_delta_data = delta_states[flex_name]
                flex_indices = flex_ui_controller.vertex_animations["index"] + mesh.vertex_index_start
                vertex_delta_data[attribute_names['pos']].extend(
                    map(datamodel.Vector3, flex_ui_controller.vertex_animations["vertex_delta"]))
                vertex_delta_data[attribute_names['pos'] + "Indices"].extend(flex_indices.ravel())

                vertex_delta_data[attribute_names['norm']].extend(
                    map(datamodel.Vector3, flex_ui_controller.vertex_animations["normal_delta"]))
                vertex_delta_data[attribute_names['norm'] + "Indices"].extend(flex_indices.ravel())

                if flex_ui_controller.vertex_anim_type == VertexAminationType.WRINKLE:
                    vertex_delta_data[attribute_names["wrinkle"]].extend(
                        flex_ui_controller.vertex_animations["wrinkle_delta"].ravel())
                    vertex_delta_data[attribute_names["wrinkle"] + "Indices"].extend(flex_indices.ravel())

    dm_model.save(s2_output_path / output_path, "keyvalues2", 1)

    return output_path


def convert_mdl(mdl_path: Path, s2_output_path: Path, sbox_mode: bool = False):
    cm = ContentManager()
    cm.scan_for_content(mdl_path)
    with FileBuffer(mdl_path) as f:
        mdl = MdlV49.from_buffer(f)
    with cm.find_file(mdl_path.with_suffix('.vvd')) as f:
        vvd = Vvd.from_buffer(f)
    with find_vtx_cm(mdl_path, cm) as f:
        vtx = open_vtx(f)

    rel_model_path = Path("models", normalize_path(mdl.header.name))
    content_path = s2_output_path / rel_model_path.with_suffix('')
    os.makedirs(content_path, exist_ok=True)
    s1_materials = collect_materials(mdl)

    print(f'\033[94mDecompiling model \033[92m"{rel_model_path}"\033[0m')

    main_bodypart_guess: Optional[Tuple[BodyPart, VtxBodyPart]] = None

    for bodypart, vtx_bodypart in zip(mdl.body_parts, vtx.body_parts):
        if len(bodypart.models) != 1:
            continue
        for model, vtx_model in zip(bodypart.models, vtx_bodypart.models):
            if not model.meshes:
                continue
            main_bodypart_guess = bodypart, vtx_bodypart
            break

    vmdl = KV3mdl()
    if main_bodypart_guess:
        bodypart, vtx_bodypart = main_bodypart_guess
        dmx_filename = _convert_model(mdl, vvd, bodypart.models[0], vtx_bodypart.models[0], s2_output_path,
                                      s1_materials)
        vmdl.add_render_mesh(sanitize_name(bodypart.name), dmx_filename)

    for bodypart, vtx_bodypart in zip(mdl.body_parts, vtx.body_parts):
        if main_bodypart_guess and main_bodypart_guess[0] == bodypart:
            continue
        for model, vtx_model in zip(bodypart.models, vtx_bodypart.models):
            if not model.meshes:
                continue

            dmx_filename = _convert_model(mdl, vvd, model, vtx_model, s2_output_path, s1_materials)
            vmdl.add_render_mesh(sanitize_name(model.name), dmx_filename)

    for s1_bodygroup in mdl.body_parts:
        if main_bodypart_guess and main_bodypart_guess[0] == s1_bodygroup:
            continue
        if 'clamped' in s1_bodygroup.name:
            continue
        bodygroup = vmdl.add_bodygroup(sanitize_name(s1_bodygroup.name))
        for mesh in s1_bodygroup.models:
            if len(mesh.meshes) == 0 or mesh.name == 'blank':
                vmdl.add_bodygroup_choice(bodygroup, [])
                continue
            vmdl.add_bodygroup_choice(bodygroup, sanitize_name(mesh.name))

    s2_vmodel = (s2_output_path / rel_model_path.with_suffix('.vmdl'))
    with s2_vmodel.open('w') as f:
        f.write(vmdl.dump())

    print('\033[94mConverting materials\033[0m')
    for mat in s1_materials:
        mat_name = normalize_path(mat[0])
        print('\t\033[94mConverting \033[92m"{}"\033[0m'.format(mat_name))
        result, error_message = convert_material(mat, s2_output_path, sbox_mode)
        if result:
            pass
        else:
            print(f'\033[91m{error_message}\033[0m')

    return s2_vmodel


def compile_model(vmdl_path, base_path):
    resource_compiler = base_path.parent.parent.parent / 'game' / 'bin' / 'win64' / 'resourcecompiler.exe'
    if resource_compiler.exists() and resource_compiler.is_file():
        print('\033[92mResourceCompiler Detected\033[0m')
        print(f'\033[94mCompiling model:\033[0m {vmdl_path}')
        pipe = Popen([str(resource_compiler), str(vmdl_path)], stdout=PIPE)
        while True:
            line = pipe.stdout.readline().decode('utf-8')
            if not line:
                break
            print(line.rstrip())


if __name__ == '__main__':

    args = argparse.ArgumentParser(description='Convert Source1 models to Source2')
    args.add_argument('-a', '--addon', type=str, required=False, help='path to source2 add-on folder',
                      dest='s2_addon_path')
    args.add_argument('-m', '--model', type=str, nargs='+', required=False, help='path to source1 model or folder',
                      dest='s1_model_path')
    args.add_argument('-c', '--compile', action='store_const', const=True, default=True, required=False,
                      help='Automatically compile (if resourcecompiler detected)',
                      dest='auto_compile')

    args.add_argument('-s', '--sbox', action='store_const', const=True, default=False, required=False,
                      help='Convert to S&Box format, otherwise converted to HLA format',
                      dest='sbox')
    args.add_argument('-d', '--debug', action='store_const', const=True, help='Enable debug output')
    # args.add_argument('-f', '--with_flex_rules', action='store_const', const=True, help='Enable flex rules conversion')
    args = args.parse_args()

    output_folder = Path(
        args.s2_addon_path or askdirectory(title="Path to Source2 add-on folder: ").replace('"', ''))
    files = args.s1_model_path or [askdirectory(title="Path to Source1 model: ").replace('"', '')]
    if args.debug:
        SLoggingManager().set_logging_level(DEBUG)
    else:
        SLoggingManager().set_logging_level(INFO)

    for file in files:
        file = Path(file)
        if file.is_dir():
            for glob_file in file.rglob('*.mdl'):
                if not glob_file.with_suffix('.vvd').exists():
                    print(f'\033[91mSkipping {glob_file.relative_to(file)} because of missing .vvd file\033[0m')
                    continue
                vmdl_file = convert_mdl(glob_file, output_folder, args.sbox)
                if args.auto_compile:
                    compile_model(vmdl_file, output_folder)
        elif file.is_file() and file.exists():
            vmdl_file = convert_mdl(file, output_folder, args.sbox)
            if args.auto_compile:
                compile_model(vmdl_file, output_folder)

import os
from tkinter.filedialog import askdirectory

from SourceIO.library.source2.utils.kv3_generator import KV3mdl

os.environ['NO_BPY'] = '1'

from pathlib import Path
import argparse
import math

from ctypes import windll

from SourceIO.library.source1.mdl.v49.mdl_file import MdlV49

from SourceIO.library.shared.content_providers.content_manager import ContentManager
from SourceIO.library.source1.mdl.structs.bone import ProceduralBoneType
from SourceIO.library.source1.mdl.structs.jiggle_bone import JiggleRule, JiggleRuleFlags
from SourceIO.library.source1.dmx.source1_to_dmx import ModelDecompiler
from utils import normalize_path, collect_materials, sanitize_name
from material_converter import convert_material
from eyes_converter import EyeConverter

k32 = windll.LoadLibrary('kernel32.dll')
setConsoleModeProc = k32.SetConsoleMode
setConsoleModeProc(k32.GetStdHandle(-11), 0x0001 | 0x0002 | 0x0004)


def get_s2_material_path(mat_name, s1_materials):
    for mat, mat_path, _ in s1_materials:
        if mat == mat_name:
            path = normalize_path((Path('materials') / mat_path / mat).with_suffix('.vmat')).resolve()
            return path


def convert_model(s1_model, s2fm_addon_folder, sbox_mode=False):
    print(f'\033[94mWorking on {s1_model.stem} model\033[0m')
    s1_mdl = MdlV49(s1_model)
    s1_mdl.read()
    eye_conv = EyeConverter()

    content_manager = ContentManager()
    content_manager.scan_for_content(s1_model)

    rel_model_path = content_manager.get_relative_path(s1_model)
    print('\033[94mCollecting materials\033[0m')
    s1_materials = collect_materials(s1_mdl)

    os.makedirs(s2fm_addon_folder / rel_model_path.with_suffix(''), exist_ok=True)

    eyes = eye_conv.process_mdl(s1_mdl, s2fm_addon_folder / rel_model_path.with_suffix(''))

    print('\033[94mDecompiling model\033[0m')
    model_decompiler = ModelDecompiler(s1_model)
    model_decompiler.decompile(remove_eyes=True)
    model_decompiler.save(s2fm_addon_folder / rel_model_path.with_suffix(''))
    s2_vmodel = (s2fm_addon_folder / rel_model_path.with_suffix('.vmdl'))
    os.makedirs(s2_vmodel.parent, exist_ok=True)

    print('\033[94mWriting VMDL\033[0m')
    vmdl = KV3mdl()
    for dmx_model in model_decompiler.dmx_models:
        vmdl.add_render_mesh(sanitize_name(dmx_model.mdl_model.name),
                             normalize_path(
                                 rel_model_path.with_suffix('') / f'{Path(dmx_model.mdl_model.name).stem}.dmx'))

    for eyeball_name, eyeball_path in eyes:
        vmdl.add_render_mesh(sanitize_name(eyeball_name),
                             normalize_path(eyeball_path.relative_to(s2fm_addon_folder)))

    for bone in s1_mdl.bones:
        if bone.procedural_rule_type == ProceduralBoneType.JIGGLE:
            procedural_rule = bone.procedural_rule  # type:JiggleRule
            jiggle_type = 0
            if procedural_rule.flags & JiggleRuleFlags.IS_RIGID:
                jiggle_type = 0
            elif procedural_rule.flags & JiggleRuleFlags.IS_FLEXIBLE:
                jiggle_type = 1
            elif procedural_rule.flags & JiggleRuleFlags.HAS_BASE_SPRING:
                jiggle_type = 2

            jiggle_data = {
                "name": f"{bone.name}_jiggle",
                "jiggle_root_bone": bone.name,
                "jiggle_type": jiggle_type,
                'length': procedural_rule.length,
                'tip_mass': procedural_rule.tip_mass,
                'has_yaw_constraint': bool(procedural_rule.flags & JiggleRuleFlags.HAS_YAW_CONSTRAINT),
                'has_pitch_constraint': bool(procedural_rule.flags & JiggleRuleFlags.HAS_PITCH_CONSTRAINT),
                'has_angle_constraint': bool(procedural_rule.flags & JiggleRuleFlags.HAS_ANGLE_CONSTRAINT),
                'allow_flex_length  ': bool(procedural_rule.flags & JiggleRuleFlags.HAS_LENGTH_CONSTRAINT),

                'invert_axes': bone.position[0] < 0,

                'angle_limit': math.degrees(procedural_rule.angle_limit),
                'max_yaw': procedural_rule.max_yaw,
                'min_yaw': procedural_rule.min_yaw,
                'yaw_bounce': procedural_rule.yaw_bounce,
                'yaw_damping': procedural_rule.yaw_damping or 10,
                'yaw_stiffness': procedural_rule.yaw_stiffness or 10,
                'yaw_friction': procedural_rule.yaw_friction or 10,

                'max_pitch': procedural_rule.max_pitch,
                'min_pitch': procedural_rule.min_pitch,
                'pitch_bounce': procedural_rule.pitch_bounce or 10,
                'pitch_damping': procedural_rule.pitch_damping or 10,
                'pitch_stiffness': procedural_rule.pitch_stiffness or 10,
                'pitch_friction': procedural_rule.pitch_friction or 10,

                'base_left_max': procedural_rule.base_max_left,
                'base_left_min': procedural_rule.base_min_left,
                'base_left_friction': procedural_rule.base_left_friction,

                'base_up_max': procedural_rule.base_max_up,
                'base_up_min': procedural_rule.base_min_up,
                'base_up_friction': procedural_rule.base_up_friction,

                'base_forward_max': procedural_rule.base_min_forward,
                'base_forward_min': procedural_rule.base_min_forward,
                'base_forward_friction': procedural_rule.base_forward_friction,

                'along_stiffness': procedural_rule.along_stiffness / 10,
                'along_damping': procedural_rule.along_damping or 15,

            }
            vmdl.add_jiggle_bone(jiggle_data)

    for s1_bodygroup in s1_mdl.body_parts:
        if 'clamped' in s1_bodygroup.name:
            continue
        bodygroup = vmdl.add_bodygroup(sanitize_name(s1_bodygroup.name))
        for mesh in s1_bodygroup.models:
            if len(mesh.meshes) == 0 or mesh.name == 'blank':
                vmdl.add_bodygroup_choice(bodygroup, [])
                continue
            vmdl.add_bodygroup_choice(bodygroup, sanitize_name(mesh.name))
    reference_skin = s1_mdl.skin_groups[0]

    for n, skin in enumerate(s1_mdl.skin_groups[1:]):
        vmdl_skin = vmdl.add_skin(f'skin_{n}', 'MaterialGroup' if n else 'DefaultMaterialGroup')
        for ref_mat, skin_mat in zip(reference_skin, skin):
            if ref_mat != skin_mat:
                ref_mat = get_s2_material_path(normalize_path(ref_mat), s1_materials)
                skin_mat = get_s2_material_path(normalize_path(skin_mat), s1_materials)
                if ref_mat and skin_mat:
                    vmdl.add_skin_remap(vmdl_skin, ref_mat, skin_mat)
                else:
                    print('\033[91mFailed to create skin!\nMissing source or destination material!\033[0m')

    with s2_vmodel.open('w') as f:
        f.write(vmdl.dump())

    print('\033[94mConverting materials\033[0m')
    for mat in s1_materials:
        mat_name = normalize_path(mat[0])
        print('\033[92mConverting {}\033[0m'.format(mat_name))
        result, error_message = convert_material(mat, s2fm_addon_folder, sbox_mode)
        if result:
            pass
        else:
            print(f'\033[91m{error_message}\033[0m')
    return s2_vmodel


from subprocess import Popen, PIPE


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
                      help='Convert for S&Box',
                      dest='sbox')

    args = args.parse_args()

    output_folder = Path(args.s2_addon_path or askdirectory(title="Path to Source2 add-on folder: ").replace('"', ''))
    files = args.s1_model_path or [askdirectory(title="Path to Source1 model: ").replace('"', '')]

    for file in files:
        file = Path(file)
        if file.is_dir():
            for glob_file in file.rglob('*.mdl'):
                if not glob_file.with_suffix('.vvd').exists():
                    print(f'\033[91mSkipping {glob_file.relative_to(file)} because of missing .vvd file\033[0m')
                    continue
                vmdl_file = convert_model(glob_file, output_folder, args.sbox)
                compile_model(vmdl_file, output_folder)
        elif file.is_file() and file.exists():
            vmdl_file = convert_model(file, output_folder)
            if args.auto_compile:
                compile_model(vmdl_file, output_folder)

import os
import shlex
from ctypes import windll
from pathlib import Path

from material_converter import convert_material

k32 = windll.LoadLibrary('kernel32.dll')
setConsoleModeProc = k32.SetConsoleMode
setConsoleModeProc(k32.GetStdHandle(-11), 0x0001 | 0x0002 | 0x0004)

os.environ['NO_BPY'] = '1'

from PIL import Image, ImageOps
from SourceIO.source1.new_mdl.mdl import Mdl
from SourceIO.source1.new_vvd.vvd import Vvd
from SourceIO.source1.new_vtx.vtx import Vtx

from SourceIO.source2.utils.kv3_generator import KV3mdl
from SourceIO.source1.source1_to_dmx import decompile

from SourceIO.utilities.valve_utils import encode_quotes
from SourceIO.utilities import valve_utils

from utils import normalize_path, collect_materials, sanitize_name

s2fm_addon_folder = Path(input("Source2 addon folder:").replace('"', ''))

s1_model = Path(input("Source1 model:").replace('"', ''))

s1_mdl = Mdl(s1_model)
s1_mdl.read()


def decompile_s1_model(mdl: Mdl, mdl_path: Path, output, gameinfo):
    vvd_path = mdl_path.with_suffix(".vvd")
    vtx_path = mdl_path.with_suffix(".dx90.vtx")
    vvd = Vvd(vvd_path)
    vtx = Vtx(vtx_path)
    vvd.read()
    vtx.read()
    return decompile(mdl, vvd, vtx, output, gameinfo)


refl_range = 0.5

# handle S1 materials
model_name = s1_model.stem
mod_path = valve_utils.get_mod_path(s1_model)
rel_model_path = normalize_path(s1_model.relative_to(mod_path))
gi_path = mod_path / 'gameinfo.txt'
if not gi_path.exists():
    raise FileNotFoundError("Failed to find gameinfo file")
else:
    print('\033[94mFound \033[95mgameinfo.txt\033[94m file\033[0m')
gi = valve_utils.GameInfoFile(gi_path)

print('\033[94mCollecting materials\033[0m')
s1_materials = collect_materials(s1_mdl, gi)

os.makedirs(s2fm_addon_folder / rel_model_path.with_suffix(''), exist_ok=True)

print('\033[94mDecompiling model\033[0m')
mesh_files = decompile_s1_model(s1_mdl, s1_model, s2fm_addon_folder / rel_model_path.with_suffix(''), gi)

s2_vmodel = normalize_path(
    s2fm_addon_folder / rel_model_path.with_suffix("") / Path(model_name).with_suffix('.vmdl'))
os.makedirs(s2_vmodel.parent, exist_ok=True)

print('\033[94mWriting VMDL\033[0m')
vmdl = KV3mdl()
for mesh_name, mesh_path in mesh_files.items():
    vmdl.add_render_mesh(sanitize_name(mesh_name), str(mesh_path.relative_to(s2fm_addon_folder)))

for s1_bodygroup in s1_mdl.body_parts:
    bodygroup = vmdl.add_bodygroup(s1_bodygroup.name)
    for mesh in s1_bodygroup.models:
        if len(mesh.meshes) == 0:
            continue
        vmdl.add_bodygroup_choice(bodygroup, sanitize_name(mesh.name))

with s2_vmodel.open('w') as f:
    f.write(vmdl.dump())


def normalized_parse_line(line):
    """
    Line parser that extracts key value pairs from a line and returns a list of the tokens with escaped quotes.
    """
    # Fix any trailing slashes that are escaping quotes
    if line.endswith('\\"'):
        line = line.rsplit('\\"', 1)
        line = '\\\\"'.join(line)
    elif line.endswith("\\'"):
        line = line.rsplit("\\'", 1)
        line = "\\\\'".join(line)

    lex = shlex.shlex(line, posix=True)
    lex.escapedquotes = '\"\''
    lex.whitespace = ' \n\t='
    lex.wordchars += '|.:/\\+*%$'  # Do not split on these chars
    # Escape all quotes in result
    tokens = [encode_quotes(token) for token in lex]
    tokens[0] = tokens[0].lower()
    if len(tokens) == 1:
        # Key with no value gets empty string as value
        tokens.append('')
    elif len(tokens) > 2:
        # Multiple value tokens, invalid
        raise TypeError
    vals = tokens[1].split(" ")
    if vals and len(vals) > 1:
        a = [val.isnumeric() for val in vals]
        if all(a):
            tokens[1] = list(map(int, vals))
    return tokens

    # with material_file.open('w') as vmat_file:
    #     vmat_file.write('// Converted with SourceIO converter\n\n')
    #     vmat_file.write('Layer0\n{\n\tshader "' + s2_shader + '.vfx"\n\n')
    #
    #     vmat_file.write('}\n')


print('\033[94mConverting materials\033[0m')
for mat in s1_materials:
    print('\033[92mConverting {}\033[0m'.format(mat[0]))
    s2_shader, s2_material = convert_material(mat, s2fm_addon_folder, gi)
    material_file = (s2fm_addon_folder / 'materials' / mat[1] / mat[0]).with_suffix('.vmat')
    with material_file.open('w') as vmat_file:
        vmat_file.write('// Converted with SourceIO converter\n\n')
        vmat_file.write('Layer0\n{\n\tshader "' + s2_shader + '.vfx"\n\n')
        for k, v in s2_material.items():
            if isinstance(v, Path):

                vmat_file.write(f'\t{k} "{str(v)}"\n')
            else:
                vmat_file.write(f'\t{k} {str(v)}\n')
        vmat_file.write('}\n')

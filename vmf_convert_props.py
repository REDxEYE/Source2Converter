import sys
from pathlib import Path
from typing import Set
import os

from convert_s1_to_s2 import convert_model, compile_model

os.environ['NO_BPY'] = '1'

from SourceIO.content_providers.content_manager import ContentManager
from SourceIO.utilities.keyvalues import KVParser
from material_converter import convert_material, Material

used_models: Set[str] = set()

if __name__ == '__main__':
    mod_path = Path(r'F:\SteamLibrary\steamapps\common\Half-Life Alyx\content\hlvr_addons\half_life2')

    ContentManager().scan_for_content(r'D:\GAMES\hl2_beta\hl2')
    with open(r"D:\GAMES\hl2_beta\hl2\maps_src\d1_town\d1_town_01.vmf", 'r') as f:
        for line in f.readlines():
            if 'model' in line:
                line = line.strip('\r\t\n ')
                _, material_name = line.split(' ')
                used_models.add(material_name.replace("\"", ""))

    content_manager = ContentManager()
    for model in used_models:
        model = Path(model)
        full_path = content_manager.find_path(model, extension='.mdl')
        vmdl_file = convert_model(full_path, mod_path)
        compile_model(vmdl_file, mod_path)

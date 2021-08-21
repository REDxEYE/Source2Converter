import sys
from pathlib import Path
from typing import Set
import os

os.environ['NO_BPY'] = '1'

from SourceIO.content_providers.content_manager import ContentManager
from SourceIO.utilities.keyvalues import KVParser
from material_converter import convert_material, Material

used_materials: Set[str] = set()

if __name__ == '__main__':
    ContentManager().scan_for_content(r'D:\GAMES\hl2_beta\hl2')
    with open(r"D:\GAMES\hl2_beta\hl2\maps_src\d1_town\d1_town_02.vmf", 'r') as f:
        for line in f.readlines():
            if 'material' in line:
                line = line.strip('\r\t\n ')
                _, material_name = line.split(' ')
                used_materials.add(material_name.replace("\"", ""))

    content_manager = ContentManager()
    for material in used_materials:
        material = Path(material)
        full_path = content_manager.find_material(material)
        convert_material((material.stem.lower(), str(material.parent).lower(), full_path),
                         Path(r'F:\SteamLibrary\steamapps\common\Half-Life Alyx\content\hlvr_addons\half_life2'))

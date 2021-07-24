from pathlib import Path
from typing import Set
import os

os.environ['NO_BPY'] = '1'

from SourceIO.source_shared.content_manager import ContentManager
from SourceIO.utilities.keyvalues import KVParser
from material_converter import convert_material, Material

if __name__ == '__main__':
    used_materials: Set[str] = set()
    ContentManager().scan_for_content(r'D:\GAMES\hl2_beta\hl2')
    with open(r"D:\GAMES\hl2_beta\hl2\maps_src\aaron\ai_guide1.vmf", 'r') as f:
        kv = KVParser('test', f.read())
        data = {k: v for k, v in kv.parse()}
        for entity in data.get('entity', []):
            pass

        world = data['world']
        for brush in world.get('solid', []):
            for side in brush.get('side', []):
                material = side['material']
                used_materials.add(material)

    content_manager = ContentManager()
    for material in used_materials:
        material = Path(material)
        full_path = content_manager.find_material(material)
        convert_material((material.stem, material.parent, full_path),
                         Path(r'F:\SteamLibrary\steamapps\common\Half-Life Alyx\content\hlvr_addons\s2fm'))

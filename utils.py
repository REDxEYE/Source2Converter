from pathlib import Path

from SourceIO.source1.new_mdl.mdl import Mdl
from SourceIO.utilities.valve_utils import GameInfoFile


def collect_materials(mdl: Mdl, gameinfo: GameInfoFile):
    materials = []

    # sanitize and normalize material names
    for material in mdl.materials:
        for cd_material_path in mdl.materials_paths:
            if cd_material_path in material.name:
                material.name = Path(material.name).stem

    # collect materials
    for material in mdl.materials:
        print(f'\t\033[92mSearching {material.name}\033[0m')
        for cd_material_path in mdl.materials_paths:
            print(f'\t\t\033[92mSearching in {cd_material_path}\033[0m')
            material_full_path = gameinfo.find_material(Path(cd_material_path) / material.name, True)
            if material_full_path:
                materials.append((material.name, cd_material_path, material_full_path))
                break
        else:
            print(f'\033[91mFailed to find {material.name}\033[0m')

    return materials


def remove_ext(path):
    path = Path(path)
    return path.with_suffix("")


def sanitize_name(name):
    return Path(name).stem.replace(' ', '_').replace('-', '_').replace('.', '_')


def normalize_path(path):
    return Path(str(path).lower().replace(' ', '_').replace('-', '_'))

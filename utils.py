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
        for cd_material_path in mdl.materials_paths:
            material_full_path = gameinfo.find_material(Path(cd_material_path) / material.name, True)
            if material_full_path:
                materials.append((material.name, cd_material_path, material_full_path))
                break

    return materials


def remove_ext(path):
    path = Path(path)
    return path.with_suffix("")


def sanitize_name(name):
    return Path(name).stem


def normalize_path(path):
    return Path(str(path).lower())

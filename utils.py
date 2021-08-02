from pathlib import Path

from SourceIO.source_shared.content_manager import ContentManager
from SourceIO.source1.mdl.v49.mdl_file import Mdl


def collect_materials(mdl: Mdl):
    materials = []
    content_manager = ContentManager()

    # collect materials
    for material in mdl.materials:
        for cd_material_path in mdl.materials_paths:
            material_full_path = content_manager.find_material(Path(cd_material_path) / material.name)
            if material_full_path:
                materials.append((normalize_path(material.name), cd_material_path, material_full_path))
                break
        else:
            print(f'\033[91mFailed to find {material.name}\033[0m')
            materials.append((normalize_path(material.name), '', None))

    return materials


def remove_ext(path):
    path = Path(path)
    return path.with_suffix("")


def sanitize_name(name):
    return Path(name).stem.lower().replace(' ', '_').replace('-', '_').replace('.', '_')


def normalize_path(path):
    return Path(str(path).lower().replace(' ', '_').replace('-', '_').strip('/\\'))

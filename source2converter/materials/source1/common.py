from pathlib import Path

import numpy as np
from PIL import Image

from SourceIO.library.shared.content_providers.content_manager import ContentManager
from SourceIO.logger import SourceLogMan
from SourceIO.library.source1.vtf import load_texture as load_vtf
from source2converter.materials.types import ValveTexture

log_manager = SourceLogMan()
logger = log_manager.get_logger('Material converter')


def load_texture(texture_path, content_manager: ContentManager):
    logger.info(f"Loading texture {texture_path}")
    texture_data = content_manager.find_texture(texture_path)
    if texture_path:
        texture_data, width, height = load_vtf(texture_data)
        texture_data = np.flipud(texture_data)
        texture = Image.frombytes("RGBA", (height, width), (texture_data * 255).astype(np.uint8))
        return texture
    else:
        logger.error(f"Texture {texture_path} not found!")
    return None


def write_texture(export_texture_list: list[ValveTexture], image: Image.Image, name: str, content_path: Path,
                  **settings):
    output_path = content_path / (name + ".png")
    export_texture_list.append(ValveTexture(output_path, image, settings))
    return output_path.as_posix()


def write_vector(array):
    return f"[{' '.join(map(str, array))}]"


def ensure_length(arr: list, length, filler):
    if len(arr) < length:
        arr.extend([filler] * (length - len(arr)))
        return arr
    elif len(arr) > length:
        return arr[:length]
    return arr

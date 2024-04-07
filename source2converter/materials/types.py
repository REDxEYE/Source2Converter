from dataclasses import dataclass
from pathlib import Path
from typing import Any

from PIL import Image


class ValveMaterial:
    pass


@dataclass
class ValveTexture:
    filepath: Path
    image: Image.Image
    settings: dict[str, Any]

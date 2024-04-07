from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Callable, Optional

from SourceIO.library.shared.content_providers.content_manager import ContentManager
from SourceIO.library.utils import Buffer
from SourceIO.logger import SourceLogMan
from source2converter.materials.types import ValveMaterial, ValveTexture

log_manager = SourceLogMan()
logger = log_manager.get_logger('MDL Converter Tags')


class SourceType(Enum):
    UnknownSource = "Unknown engine"
    Source1Source = "Source1 engine"


class GameType(Enum):
    UnspecifiedGame = "UnspecifiedGame"
    CS2 = "Counter-Strike 2"
    HLA = "Half-Life: Alyx"


@dataclass(slots=True)
class MaterialConverterTag:
    source: SourceType
    game: GameType
    type: str
    morph_support: bool


MaterialConvertFunction = Callable[[Path, Buffer, ContentManager], tuple[ValveMaterial, list[ValveTexture]]]
MATERIAL_CONVERTERS: list[tuple[MaterialConverterTag, MaterialConvertFunction]] = []


def register_material_converter(source: SourceType, game: GameType, type: str, morph_support: bool = False):
    def inner(func: MaterialConvertFunction) -> MaterialConvertFunction:
        MATERIAL_CONVERTERS.append((MaterialConverterTag(source, game, type, morph_support), func))
        return func

    return inner


def choose_material_converter(source: SourceType, game: GameType, mat_type: str,
                              morph_support: bool = False) -> Optional[MaterialConvertFunction]:
    best_match = None
    best_score = 0  # Start with a score lower than any possible match score

    for handler_tag, handler_func in MATERIAL_CONVERTERS:
        score = 0
        # Check ident and version match
        if handler_tag.source == source and handler_tag.game == game and handler_tag.type == mat_type:
            if morph_support == handler_tag.morph_support:
                score += 2
            score += 2  # Base score for ident and version match

        # Update best match if this handler has a higher score
        if score > best_score:
            best_score = score
            best_match = handler_func
    if best_match is None:
        logger.error(f'Could not find converter from {source.value!r} {mat_type} '
                     f'{"with morph support" if morph_support else "without morph support"} to {game.value!r}')
    return best_match

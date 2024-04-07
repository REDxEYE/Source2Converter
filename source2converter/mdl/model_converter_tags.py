from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional

from SourceIO.library.shared.app_id import SteamAppId
from SourceIO.library.shared.content_providers.content_manager import ContentManager
from SourceIO.library.utils import Buffer
from SourceIO.logger import SourceLogMan
from source2converter.model import Model

log_manager = SourceLogMan()
logger = log_manager.get_logger('MDL Converter Tags')


@dataclass(slots=True)
class ModelConverterTag:
    ident: bytes
    version: int
    steam_id: SteamAppId


ModelConvertFunction = Callable[[Path, Buffer, ContentManager], Model]
MODEL_CONVERTERS: list[tuple[ModelConverterTag, ModelConvertFunction]] = []


def register_model_converter(ident: bytes, version: int, steam_id: Optional[SteamAppId] = None):
    def inner(func: ModelConvertFunction) -> ModelConvertFunction:
        MODEL_CONVERTERS.append((ModelConverterTag(ident, version, steam_id), func))
        return func

    return inner


def choose_model_converter(ident: bytes, version: int,
                           steam_id: Optional[SteamAppId] = None) -> Optional[ModelConvertFunction]:
    best_match = None
    best_score = 0  # Start with a score lower than any possible match score

    for handler_tag, handler_func in MODEL_CONVERTERS:
        score = 0
        # Check ident and version match
        if handler_tag.ident == ident and handler_tag.version == version:
            score += 2  # Base score for ident and version match

            # If steam_id is provided and matches, increase the score
            if steam_id is not None and handler_tag.steam_id == steam_id:
                score += 1  # Additional score for steam_id match

        # Update best match if this handler has a higher score
        if score > best_score:
            best_score = score
            best_match = handler_func
    if best_match is None:
        logger.error(f'Could not find converter for {ident!r} version {version}')
    return best_match

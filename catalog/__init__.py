"""Global catalogue of proven business models from many countries (target market: Czechia)."""

from .americas import MODELS as _AMERICAS
from .asia_pacific_africa import MODELS as _APAC_AFRICA
from .europe_east import MODELS as _EUROPE_EAST
from .europe_west import MODELS as _EUROPE_WEST

GLOBAL_MODELS: list[dict] = _AMERICAS + _EUROPE_WEST + _EUROPE_EAST + _APAC_AFRICA

import typing as t

from .battlesuits import *
from .stigmata import *
from .weapons import *

__all__ = (
    "Battlesuit",
    "StigmataSet",
    "Weapon",
    "AnyModel",
)


AnyModel = t.Union[Battlesuit, StigmataSet, Weapon]

import typing as t

from . import display
from .battlesuits import *
from .stigmata import *
from .weapons import *

__all__ = ("Battlesuit", "StigmataSet", "Weapon", "AnyModel", "display")


AnyModel = t.Union[Battlesuit, StigmataSet, Weapon]

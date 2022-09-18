import typing as t

import pydantic
import wikitextparser

from .. import constants
from . import base

__all__ = ("Battlesuit", "BattlesuitEquipment", "BattlesuitRecommendation")


class BattlesuitEquipment(base.ContentBase):
    """Represents a piece of equipment, equipped on a Battlesuit."""

    name: str
    rarity: int


class BattlesuitRecommendation(base.ContentBase):
    """Represents an equipment recommendation for a battlesuit, including a
    weapon, and T, M, and B stigmata; not necessarily of the same set.
    """

    type: str
    weapon: BattlesuitEquipment
    T: BattlesuitEquipment
    M: BattlesuitEquipment
    B: BattlesuitEquipment
    offensive_ability: str
    functionality: str
    compatibility: str


class Battlesuit(base.ContentBase):  # TODO: skills
    """Represents a battlesuit with all data on the wiki."""

    type: constants.BattlesuitType
    rank: constants.BattlesuitRarity
    name: str = pydantic.Field(alias="battlesuit")
    character: str
    profile: str = ""  # Undefined for augments for whatever reason.
    core_strengths: t.Sequence[constants.CoreStrengthEmoji]
    recommendations: t.Sequence[BattlesuitRecommendation]
    augment: t.Optional[str]
    awakening: t.Optional[str] = pydantic.Field(None, alias="shared")

    @pydantic.validator("core_strengths", pre=True)
    def _parse_core_strengths(cls, value: t.Union[str, t.List[str]]):
        if isinstance(value, list):
            return value
        return value.split(", ") if value else []

    @pydantic.root_validator(pre=True)
    def _pack_recommendations(cls, values: t.Dict[str, t.Any]):
        if "recommendations" in values:
            return values

        values["recommendations"] = recommendations = []
        for category in constants.BattlesuitRecommendation:
            if not (category_data := values.get(category)):
                continue

            results: t.Dict[str, t.Any] = {"type": category.name.title()}

            # Extract equipment recommendations...
            for template in wikitextparser.parse(category_data).templates:
                key = slot.value if (slot := template.get_arg("slot")) else template.name
                results[key] = {
                    "rarity": rarity.value if (rarity := template.get_arg("rarity")) else "0",
                    "name": name.value if (name := template.get_arg("1")) else "...",
                }

            # Extract recommendation scores...
            for score_type in constants.BattlesuitRecommendationType:
                results[score_type] = values[f"{category}_{score_type}"]

            recommendations.append(BattlesuitRecommendation(**results))
        return values

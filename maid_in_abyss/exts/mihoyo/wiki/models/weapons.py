import re
import typing as t

import pydantic

from .. import constants
from . import base

__all__ = ("Weapon", "WeaponSkill", "WeaponStats")


ACTIVE_SKILL_PATTERN = re.compile(r"\[SP: \d+\]\[CD: \d+s\]")


class WeaponStats(base.ContentBase):
    attack: int
    crit: int
    rarity: constants.WeaponRarity

    @property
    def data(self) -> t.Dict[str, str]:
        return {
            "rarity": f"{self.rarity}*",
            "attack": str(self.attack),
            "crit": str(self.crit),
        }


class WeaponSkill(base.ContentBase):
    name: str
    effect: str
    core_strengths: t.Sequence[constants.CoreStrengthEmoji]

    @pydantic.validator("core_strengths", pre=True)
    def _parse_core_strengths(cls, value: t.Union[str, t.List[str]]):
        if isinstance(value, list):
            return value
        return value.split(", ") if value else []

    def is_active(self) -> bool:
        return bool(ACTIVE_SKILL_PATTERN.search(self.effect))


class Weapon(base.ContentBase):

    name: str
    type: str  # can't use constants.WeaponType here because they're oddly inconsistent...
    rarity: constants.WeaponRarity
    # obtain: t.Optional[str] = None
    stats: t.Sequence[WeaponStats]

    description: str
    skills: t.Sequence[WeaponSkill]
    pri_arm: t.Optional[str] = pydantic.Field(None, alias="priArm")
    pri_arm_base: t.Optional[str] = pydantic.Field(None, alias="priArmBase")
    divine_key: bool = False

    @pydantic.root_validator(pre=True)
    def _pack_obtain(cls, values: t.Dict[str, t.Any]):
        base = "obtain"  # all fields that contain source data start with 'obtain'
        if base not in values:
            values[base] = {k.removeprefix(base): v for k, v in values.items() if base in k}
        return values

    @pydantic.root_validator(pre=True)
    def _pack_stats(cls, values: t.Dict[str, t.Any]):
        if "stats" in values:
            return values

        rarities = ("base", "2nd", "3rd", "4th", "5th", "max")
        base_rarity = values["rarity"]

        stats = values["stats"] = []
        for rarity in rarities:
            if not (atk := values.get(f"ATK_{rarity}Rarity")):
                continue

            stats.append(
                WeaponStats(
                    attack=atk,
                    crit=values[f"CRT_{rarity}Rarity"],
                    rarity=constants.WeaponRarity(int(base_rarity) + len(stats)),
                )
            )
        return values

    @pydantic.root_validator(pre=True)
    def _pack_skills(cls, values: t.Dict[str, t.Any]):
        if "skills" in values:
            return values

        values["skills"] = skills = []
        for i in range(1, 5):
            if not (name := values.get(f"s{i}_name")):
                break

            skills.append(
                WeaponSkill(
                    name=name,
                    effect=values[f"s{i}_effect"],
                    core_strengths=values.get(f"s{i}_core_strengths", []),
                )
            )
        return values

    @pydantic.validator("rarity", pre=True)
    def _cast_rarity(cls, rarity: str):
        return int(rarity)

    @property
    def max_rarity(self) -> constants.WeaponRarity:
        return self.stats[-1].rarity

    @property
    def active_skill(self) -> t.Optional[WeaponSkill]:
        if (first := self.skills[0]).is_active():
            return first

    @property
    def passive_skills(self) -> t.Sequence[WeaponSkill]:
        return [skill for skill in self.skills if not skill.is_active()]

    def is_pri_arm(self) -> bool:
        return bool(self.pri_arm_base)

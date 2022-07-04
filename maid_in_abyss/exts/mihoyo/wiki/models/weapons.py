import re
import typing as t

import pydantic

from .. import api_types, constants

__all__ = ("Weapon", "WeaponSkill", "WeaponStat")


ACTIVE_SKILL_PATTERN = re.compile(r"\[SP: \d+\]\[CD: \d+s\]")


class WeaponStat(api_types.ContentBase):
    base: int
    max: int


class WeaponSkill(api_types.ContentBase):
    name: str
    effect: str

    def is_active(self) -> bool:
        return bool(ACTIVE_SKILL_PATTERN.search(self.effect))


class Weapon(api_types.ContentBase):
    rarity: constants.WeaponRarity
    type: constants.WeaponType
    upgradable: bool
    obtain: t.Mapping[str, bool]
    attack: WeaponStat = pydantic.Field(alias="ATK")
    crit: WeaponStat = pydantic.Field(alias="CRT")

    pri_arm_base: str = pydantic.Field(alias="priArmBase")
    description: str
    skills: t.Sequence[WeaponSkill]

    @pydantic.root_validator(pre=True)
    def _pack_obtain(cls, values: t.Dict[str, t.Any]):
        base = "obtain"  # all fields that contain source data start with 'obtain'
        values[base] = {k.removeprefix(base): v for k, v in values.items() if base in k}
        return values

    @pydantic.root_validator(pre=True)
    def _pack_stats(cls, values: t.Dict[str, t.Any]):
        for base in ("ATK", "CRT"):
            values[base] = {
                tier: values[f"{base}_{tier}Rarity"]
                for tier in ("base", "max")
            }
        return values

    @pydantic.root_validator(pre=True)
    def _pack_skills(cls, values: t.Dict[str, t.Any]):
        values["skills"] = skills = []
        for i in range(1, 4):
            if not (name := values.get(f"s{i}_name")):
                break

            skills.append(WeaponSkill(
                name=name,
                effect=values[f"s{i}_effect"],
            ))
        return values

    @pydantic.validator("rarity", pre=True)
    def _cast_rarity(cls, rarity: str):
        return int(rarity)

    @property
    def active_skill(self) -> t.Optional[WeaponSkill]:
        if (first := self.skills[0]).is_active():
            return first

    @property
    def passive_skills(self) -> t.Sequence[WeaponSkill]:
        return [skill for skill in self.skills if not skill.is_active()]

    def is_pri_arm(self) -> bool:
        return bool(self.pri_arm_base)

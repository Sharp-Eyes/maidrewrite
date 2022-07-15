import re
import typing as t

import pydantic

from .. import api_types, constants

__all__ = ("Weapon", "WeaponSkill")


ACTIVE_SKILL_PATTERN = re.compile(r"\[SP: \d+\]\[CD: \d+s\]")


# class WeaponStat(api_types.ContentBase):
#     base: int
#     max: int

#     def display(self) -> str:
#         return f"{self.base} ~ {self.max}"


class WeaponSkill(api_types.ContentBase):
    name: str
    effect: str

    def is_active(self) -> bool:
        return bool(ACTIVE_SKILL_PATTERN.search(self.effect))


class Weapon(api_types.ContentBase):
    name: str
    type: str  # can't use constants.WeaponType here because they're oddly inconsistent...
    rarity: constants.WeaponRarity
    # obtain: t.Optional[str] = None
    attack: int = pydantic.Field(alias="ATK")
    crit: int = pydantic.Field(alias="CRT")

    description: str
    skills: t.Sequence[WeaponSkill]
    pri_arm_base: t.Optional[str] = pydantic.Field(None, alias="priArmBase")
    divine_key: bool = False

    @pydantic.root_validator(pre=True)
    def _pack_obtain(cls, values: t.Dict[str, t.Any]):
        base = "obtain"  # all fields that contain source data start with 'obtain'
        if base not in values:
            values[base] = {k.removeprefix(base): v for k, v in values.items() if base in k}
        return values

    # @pydantic.root_validator(pre=True)
    # def _pack_stats(cls, values: t.Dict[str, t.Any]):
    #     for base in ("ATK", "CRT"):
    #         values[base] = {tier: values[f"{base}_{tier}Rarity"] for tier in ("base", "max")}
    #     return values

    @pydantic.root_validator(pre=True)
    def _pack_skills(cls, values: t.Dict[str, t.Any]):
        if "skills" in values:
            return values

        values["skills"] = skills = []
        for i in range(1, 5):
            if not (name := values.get(f"skill{i}")):
                break

            skills.append(
                WeaponSkill(
                    name=name,
                    effect=values[f"effect{i}"],
                )
            )
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

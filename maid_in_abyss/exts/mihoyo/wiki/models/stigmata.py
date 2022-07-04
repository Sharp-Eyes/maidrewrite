import typing as t

import pydantic

from .. import api_types, constants

__all__ = ("SetBonus", "Stigma", "StigmataSet")


class SetBonus(api_types.ContentBase):
    """Represents a set bonus for a stigmata set."""

    name: str
    effect: str
    number: int


class Stigma(api_types.ContentBase):
    """Represents a singular Stigma. Also contains information about its set."""

    name: str = pydantic.Field(alias="slot_name")
    hp: int = pydantic.Field(alias="HP")
    attack: int = pydantic.Field(alias="ATK")
    defense: int = pydantic.Field(alias="DEF")
    crit: int = pydantic.Field(alias="CRT")
    effect_name: str = pydantic.Field(alias="effectName")
    effect: str

    # Set info
    slot: constants.StigmaSlot
    set_name: str = pydantic.Field(alias="name")
    set_name_2p: t.Optional[str] = pydantic.Field(alias="setEffect2pName")
    set_effect_2p: t.Optional[str] = pydantic.Field(alias="setEffect2p")
    set_name_3p: t.Optional[str] = pydantic.Field(alias="setEffect3pName")
    set_effect_3p: t.Optional[str] = pydantic.Field(alias="setEffect3p")
    rarity: constants.StigmaRarity
    obtain: t.Mapping[str, bool]

    @pydantic.root_validator(pre=True)
    def _pack_obtain(cls, values: dict[str, t.Any]):
        base = "obtain"  # all fields that contain source data start with 'obtain'
        values[base] = {k.removeprefix(base): v for k, v in values.items() if base in k}
        return values

    @pydantic.root_validator(pre=True)
    def _unpack_stig_data(cls, values: t.Dict[str, t.Any]):
        slot = values["slot"]  # used to remove slot prefixes from stat/effect fields
        values = {k.removeprefix(f"slot{slot}_"): v for k, v in values.items()}
        values["slot_name"] = (
            values.get(f"set{slot}") or values.get(f"slot{slot}") or values["name"]
        )
        return values

    @pydantic.validator("rarity", pre=True)
    def _cast_rarity(cls, rarity: str):
        return int(rarity)

    @property
    def set_2p(self) -> t.Optional[SetBonus]:
        """The Stigma's set's 2-set effect. `None` if the set consists of a singular Stigma."""
        if self.set_name_2p and self.set_effect_2p:
            return SetBonus(name=self.set_name_2p, effect=self.set_effect_2p, number=3)
        return None

    @property
    def set_3p(self) -> t.Optional[SetBonus]:
        """The Stigma's set's 3-set effect. `None` if the set is not a 3-piece set."""
        if self.set_name_3p and self.set_effect_3p:
            return SetBonus(name=self.set_name_3p, effect=self.set_effect_3p, number=3)
        return None

    @property
    def set_bonuses(self) -> t.Sequence[SetBonus]:
        """The Stigma's set's set bonuses. Returns a tuple with zero, one or two `SetBonus`es,
        according to how many pieces are in the set.
        """
        return tuple(bonus for bonus in (self.set_2p, self.set_3p) if bonus)


class StigmataSet(api_types.ContentBase):
    """Represents a set of `Stigma`ta. This has full support for mixed sets.

    Any set operations take into account the number of stigmata of a given set
    that are actually present in the `StigmataSet`.
    """

    stigmata: t.List[Stigma] = pydantic.Field(max_items=3)  # one, two or three stigmata

    @pydantic.root_validator(pre=True)
    def _validate_stigs(cls, values: t.Dict[str, t.Any]):
        stigmata: t.Optional[t.Sequence[t.Any]] = values.get("stigmata")
        if stigmata:
            if not all(isinstance(stig, Stigma) for stig in stigmata):
                raise TypeError("All stigmata must be of type `Stigmata`")
        else:
            # Assume we're parsing a set from raw data
            values["stigmata"] = stigmata = tuple(
                Stigma(slot=slot, **values)
                for slot in constants.StigmaSlot
                if f"slot{slot}" in values
            )

        # validate that we have at most one of each slot
        if len({stig.slot for stig in stigmata}) != len(stigmata):
            raise ValueError("A set cannot have multiple stigmata share a slot")
        return values

    # TODO: Maybe delete T, M, B; as they aren't used internally?
    #       They also conflict with 6-piece sets but idk what to do about those yet.
    @property
    def T(self) -> t.Optional[Stigma]:
        """The `Stigma` in the Top slot. `None` if there is none."""
        for stig in self.stigmata:
            if stig.slot is constants.StigmaSlot.TOP:
                return stig
        return None

    @property
    def M(self) -> t.Optional[Stigma]:
        """The `Stigma` in the Middle slot. `None` if there is none."""
        for stig in self.stigmata:
            if stig.slot is constants.StigmaSlot.MIDDLE:
                return stig
        return None

    @property
    def B(self) -> t.Optional[Stigma]:
        """The `Stigma` in the Bottom slot. `None` if there is none."""
        for stig in self.stigmata:
            if stig.slot is constants.StigmaSlot.BOTTOM:
                return stig
        return None

    def get_main_set_with_bonuses(
        self,
    ) -> t.Union[
        t.Tuple[t.Sequence[Stigma], t.Sequence[SetBonus]], 
        tuple[tuple[()], tuple[()]]
    ]:
        """The main set that contributes to the `StigmataSet` set-bonus, and the set-bonuses
        provided by the set.

        - In case of a full set, this returns the full set with 3-piece and 2-piece bonuses;
        - In case of a 2:1 mixed set, this returns the 2-set with 2-piece set bonus;
        - In case of a 1:1:1 mixed set, this returns two empty tuples, as there is no set bonus;
        - In case of a 2-piece non-mixed set, this returns the set with its 2-piece set bonus;
        - In all other cases, this returns two empty tuples.
        """
        counts: dict[t.Sequence[SetBonus], list[Stigma]] = {}
        for stig in self.stigmata:
            set_bonuses = stig.set_bonuses
            if not set_bonuses:
                continue
            counts.setdefault(set_bonuses, []).append(stig)

        if not counts or len(counts) == len(self.stigmata):
            return ((), ())

        bonuses, stigs = max(counts.items(), key=lambda pair: len(pair[1]))
        return tuple(stigs), bonuses[: len(stigs) - 1]  # type: ignore

    @property
    def set_bonuses(self) -> t.Optional[t.Sequence[SetBonus]]:
        """The set bonuses triggered by the `Stigma`ta in this `StigmaSet`,
        `None` if no set bonuses are active.
        """
        _, set_bonuses = self.get_main_set_with_bonuses()
        return set_bonuses or None

    @property
    def main_set(self) -> t.Optional[t.Sequence[Stigma]]:
        """The `Stigma`ta in this set that contribute to this `StigmaSet`'s set bonus,
        `None` if no set bonuses are active.
        """
        stigmata, _ = self.get_main_set_with_bonuses()
        return stigmata or None

    @property
    def name(self) -> t.Optional[str]:
        """The name of the set that contribute to this `StigmaSet`'s set bonus,
        `None` if no set bonuses are active.
        """
        return stigset[0].name if (stigset := self.main_set) else None

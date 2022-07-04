from __future__ import annotations

import enum
import typing


T = typing.TypeVar("T", bound=enum.Enum)


class RequestCategoryEmoji(str, enum.Enum):
    STIGMATA = "<:Stigmata_Generic:914200965136138241>"
    EQUIPMENT = "<:Equipment_Generic:642086143571132420>"
    VALKYRIE = "<:Valkyrie_Generic:909813519103430697>"


class RequestCategory(str, enum.Enum):
    STIGMATA = "Category:Stigmata"
    BATTLESUITS = "Category:Battlesuits"
    WEAPONS = "Category:Weapons"

    @property
    def emoji(self) -> RequestCategoryEmoji:
        """The display emoji belonging to this request category."""
        return RequestCategoryEmoji[self]


class NameValidatableEnum(enum.Enum):

    @classmethod
    def __get_validators__(cls: typing.Type[T]) -> typing.Generator[typing.Callable[[str], T], None, None]:
        yield lambda value: cls[value.upper().replace(" ", "_")]


# Battlesuits

class BattlesuitRarityCategory(str, enum.Enum):
    """Battlesuit rarities as they appear on the wiki"""
    R1 = B = "Category:B-rank_Battlesuits"
    R2 = A = "Category:A-rank_Battlesuits"
    R3 = S = "Category:S-rank_Battlesuits"
    R4 = SS = "Category:SS-rank_Battlesuits"
    R5 = SSS = "Category:SSS-rank_Battlesuits"


class BattlesuitRarityEmoji(str, enum.Enum):
    """Battlesuit emoji as they appear on the wiki"""
    B = "<:Rank_B:643906316716474379>"
    A = "<:Rank_A:643906316317884447>"
    S = "<:Rank_S:643906316422742047>"
    SS = "<:Rank_SS:643906317362266113>"
    SSS = "<:Rank_SSS:643906317781696552>"


class BattlesuitRarity(str, enum.Enum):
    """Battlesuit rarities (ranks) as they appear on the wiki."""
    R1 = B = "B"
    R2 = A = "A"
    R3 = S = "S"
    R4 = SS = "SS"
    R5 = SSS = "SSS"

    @property
    def category(self) -> BattlesuitRarityCategory:
        """The wiki category belonging to this battlesuit rarity."""
        return BattlesuitRarityCategory[self.name]

    @property
    def emoji(self) -> BattlesuitRarityEmoji:
        """The display emoji belonging to this battlesuit rarity."""
        return BattlesuitRarityEmoji[self.name]


class BattlesuitTypeCategory(str, enum.Enum):
    """Battlesuit type categories as they appear on the wiki."""
    BIO = "Category:BIO-type Battlesuits"
    PSY = "Category:PSY-type Battlesuits"
    MECH = "Category:MECH-type Battlesuits"
    QUA = "Category:QUA-type Battlesuits"
    IMG = "Category:IMG-type Battlesuits"


class BattlesuitTypeColour(int, enum.Enum):
    """Display colours for battlesuit types."""
    BIO = 0xFFB833
    PSY = 0xFE46CF
    MECH = 0x2FE0FF
    QUA = 0x9B78FE
    IMG = 0xF1D799


class BattlesuitTypeEmoji(str, enum.Enum):
    """Display emoji for battlesuit types."""
    BIO = "<:Type_BIO:643900338864259072>"
    PSY = "<:Type_PSY:643900338683772939>"
    MECH = "<:Type_MECH:643900338868453417>"
    QUA = "<:Type_QUA:643900338943819777>"
    IMG = "<:Type_IMG:909205004269813773>"


class BattlesuitType(str, enum.Enum):
    """Battlesuit types as they appear on the wiki."""
    BIO = "BIO"
    PSY = "PSY"
    MECH = "MECH"
    QUA = "QUA"
    IMG = "IMG"

    @property
    def colour(self) -> BattlesuitTypeColour:
        """The display colour belonging to this battlesuit type."""
        return BattlesuitTypeColour[self.name]

    @property
    def category(self) -> BattlesuitTypeCategory:
        """The wiki category belonging to this battlesuit type."""
        return BattlesuitTypeCategory[self.name]

    @property
    def emoji(self) -> BattlesuitTypeEmoji:
        """The display emoji belonging to this battlesuit type."""
        return BattlesuitTypeEmoji[self.name]


class BattlesuitCoreStrengthEmoji(str, NameValidatableEnum):
    """Battlesuit core strength identifier emoji.
    
    Unlike normal enums, these are validated by member name instead of value.
    """
    ICE_DMG = "<:Ice_DMG:911355738008453151>"
    FIRE_DMG = "<:Fire_DMG:911355738042007572>"
    LIGHTNING_DMG = "<:Lightning_DMG:911355737832304650>"
    PHYSICAL = "<:Physical:911355737819725875>"

    BURST = "<:Burst:911356972044009532>"
    TIME_MASTERY = "<:Time_Mastery:911355737878462544>"
    GATHER = "<:Gather:911355737819725844>"
    HEAL = "<:Heal:911355737907822592>"
    FAST_ATK = "<:Fast_ATK:911355737756807281>"
    HEAVY_ATK = "<:Heavy_ATK:911355737861681183>"

    FREEZE = "<:Freeze:911355838394929236>"
    IGNITE = "<:Ignite:911355738083954739>"
    BLEED = "<:Bleed:911355737886847026>"
    WEAKEN = "<:Weaken:911355738100748338>"
    IMPAIR = "<:Impair:911355737903603792>"
    STUN = "<:Stun:911355838491402250>"
    PARALYZE = "<:Paralyze:911355737958125639>"
    AERIAL = "<:Aerial:938545043038416936>"

    @classmethod
    def __get_validators__(cls: typing.Type[T]) -> typing.Generator[typing.Callable[[str], T], None, None]:
        yield lambda value: cls[value.upper().replace(" ", "_")]


class BattlesuitRecommendation(str, enum.Enum):
    RECOMMENDED = "BBSrec"
    AUXILIARY = "BBSau"
    UNIVERSAL = "BBSun"
    TRANSITIONAL = "BBStr"


class BattlesuitRecommendationType(str, enum.Enum):
    OFFENSE = "offensive_ability"
    FUNCTIONALITY = "functionality"
    COMPATIBILITY = "compatibility"


# Stigmata

STAR = "<:icon_rarity_star:641631459865526302>"


class StigmaRarityCategory(str, enum.Enum):
    """Stigma rarity categories as they appear on the wiki"""
    R1 = "Category:1-star Stigmata"
    R2 = "Category:2-star Stigmata"
    R3 = "Category:3-star Stigmata"
    R4 = "Category:4-star Stigmata"
    R5 = "Category:5-star Stigmata"


class StigmaRarity(int, enum.Enum):
    """Stigma rarities as they appear on the wiki."""
    R1 = 1
    R2 = 2
    R3 = 3
    R4 = 4
    R5 = 5

    @property
    def category(self) -> StigmaRarityCategory:
        """The wiki category belonging to this stigma rarity."""
        return StigmaRarityCategory[self.name]

    @property
    def emoji(self) -> str:
        """The display emoji belonging to this stigma ratity."""
        return STAR * self


class StigmaSlotEmoji(str, enum.Enum):
    TOP = "<:Stig_T:640937795761733652>"
    MIDDLE = "<:Stig_M:640937795665395734>"
    BOTTOM = "<:Stig_B:640937795103227909>"


class StigmaSlotColour(int, enum.Enum):
    """Display colours for stigmata slots."""
    TOP = 0xFF9279
    MIDDLE = 0x9DAAFE
    BOTTOM = 0xB2C964


class StigmaSlot(str, enum.Enum):
    """Valid equipment slots for stigmata."""
    TOP = "T"
    MIDDLE = "M"
    BOTTOM = "B"

    @property
    def colour(self) -> StigmaSlotColour:
        """The display colour belonging to this stigma slot."""
        return StigmaSlotColour[self.name]

    @property
    def emoji(self) -> StigmaSlotEmoji:
        """The display colour belonging to this stigma slot."""
        return StigmaSlotEmoji[self.name]


# Weapons

class WeaponRarityCategory(str, enum.Enum):
    """Weapon rarity categories as they appear on the wiki."""
    R1 = "Category:1-Star Weapons"
    R2 = "Category:2-Star Weapons"
    R3 = "Category:3-Star Weapons"
    R4 = "Category:4-Star Weapons"
    R5 = "Category:5-Star Weapons"
    R6 = "Category:6-star Weapons"


class WeaponRarity(int, enum.Enum):
    """Weapon rarities as they appear on the wiki"""
    R1 = 1
    R2 = 2
    R3 = 3
    R4 = 4
    R5 = 5
    R6 = 6

    @property
    def category(self) -> WeaponRarityCategory:
        """The wiki category belonging to this weapon rarity."""
        return WeaponRarityCategory[self.name]

    @property
    def emoji(self) -> str:
        return STAR * self


class WeaponCategory(str, enum.Enum):
    """Weapon type categories as they appear on the wiki."""
    PISTOL = "Category:Pistols"
    KATANA = "Category:Katanas"
    CANNON = "Category:Cannons"
    CROSS = "Category:Crosses"
    GREATSWORD = "Category:Greatswords"
    GAUNTLET = "Category:Gauntlets"
    SCYTHE = "Category:Scythes"
    LANCE = "Category:Lances"
    BOW = "Category:Bows"
    CHAKRAM = "Category:Chakrams"


class WeaponType(str, enum.Enum):
    """Weapon types as they appear on the wiki."""
    PISTOL = "Pistols"
    KATANA = "Katanas"
    CANNON = "Cannons"
    CROSS = "Crosses"
    GREATSWORD = "Greatswords"
    GAUNTLET = "Gauntlets"
    SCYTHE = "Scythes"
    LANCE = "Lances"
    BOW = "Bows"
    CHAKRAM = "Chakrams"

    @property
    def category(self) -> WeaponCategory:
        """The wiki category belonging to this weapon type."""
        return WeaponCategory[self.name]


# Display

class Emoji(str, enum.Enum):
    """Emoji used in visualisation of HI3 Wiki-related content.
    
    When used in pydantic models, unlike normal Enums, validation is done by name.
    """
    PASSIVE = "<:Passive:914596917961445416>"
    ACTIVE = "<:Active:914594001565413378>"

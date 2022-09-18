import typing as t
import urllib.parse

import wikitextparser

from maid_in_abyss import utilities

from .. import constants
from . import battlesuits, stigmata, weapons

__all__ = ("prettify_battlesuit", "prettify_stigmata", "prettify_weapon")


# String parsers

LINK_FMT = "Press the title at the top of this embed to visit {name}'s wiki page!"


def truncate(string: str, length: int):
    """Limit a string to a given length"""
    return string if len(string) < length - 5 else string[: length - 5] + "..."


def urlify(string: str, image: bool = False):
    """Convert a string value to a value more likely to be recognized by
    the HI3 wiki. In case of an image, it is most likely any ": " are
    replaced with " - ", so this function handles that, too.
    """
    if image:
        string = string.replace(":", "_-")
    return urllib.parse.quote(string.replace(" ", "_"), safe=r"{}")


def image_link(name: str) -> str:
    """Create an image url by name, linking to the HI3 wiki."""
    return f"{constants.WIKI_BASE}/Special:Redirect/file/{urlify(name, image=True)}.png"


def make_wiki_link(name: str) -> str:
    """Create a page url linking to a HI3 wiki page."""
    return f"{constants.WIKI_BASE}{urlify(name)}"


def make_discord_link(display: str, link: t.Optional[str] = None, from_display: bool = True):
    """Formats a link into markdown syntax for use in discord embeds."""
    if link is None and from_display is True:
        link = make_wiki_link(display)
    return f"[{display}]({link})"


TAG_MAPPING = {
    "inc": ("**", "**"),
    "increase": ("**", "**"),
    "color-blue": ("**", "**"),
    "inco": ("**", "**"),
}


SELF_CLOSING_TAG_MAPPING = {"br": "\n"}


TEMPLATE_MAPPING = {"star": "\N{BLACK STAR}"}


def parse_wiki_str(string: str) -> str:
    """Parse a string with MediaWiki markup and HTML tags to Markdown recognized by discord."""

    # TODO: Possibly refactor this. As-is, this uses the same logic as
    #       wikitextparser uses internally, but I'm not 100% a fan.

    repl: t.Optional[str]

    def replace(
        lst: list[t.Optional[str]], begin: int, end: int, repl: t.Optional[str] = None
    ) -> None:
        lst[begin:end] = [repl] + t.cast(t.List[t.Optional[str]], [None] * (end - begin - 1))

    wt = wikitextparser.parse(string)
    list_str: list[t.Optional[str]] = list(string)

    for em in wt.get_bolds_and_italics():
        span_l, span_h = t.cast(t.Tuple[int, int], em.span)
        assert em._match
        match_l, match_h = em._match.span(1)

        repl = "**" if isinstance(em, wikitextparser.Bold) else "_"
        replace(list_str, span_l, span_l + match_l, repl)
        replace(list_str, span_l + match_h, span_h, repl)

    for tag in wt.get_tags():
        span_l, span_h = t.cast(t.Tuple[int, int], tag.span)
        match_l, match_h = t.cast(t.Match[str], tag._match).span("contents")

        if match_l != -1:  # not a self-closing tag
            repl_l, repl_r = TAG_MAPPING.get(tag.attrs["class"], (None, None))
            replace(list_str, span_l, span_l + match_l, repl_l)
            replace(list_str, span_l + match_h, span_h, repl_r)
        else:  # remove the whole self-closing tag
            repl_single = SELF_CLOSING_TAG_MAPPING.get(tag.name, None)
            replace(list_str, span_l, span_h, repl_single)

    for wikilink in wt.wikilinks:
        span_l, span_h = t.cast(t.Tuple[int, int], wikilink.span)
        if wikilink.wikilinks:
            # TODO: figure out if this is relevant
            replace(list_str, span_l, span_h, "<placeholder1>")  # image

        else:
            assert wikilink._match
            match_l, match_h = wikilink._match.span(4)  # text span

            if match_l != -1 and wikilink.text:
                # Wikilink with display text
                link = make_discord_link(wikilink.text, make_wiki_link(wikilink.target))
                replace(list_str, span_l, span_h, link)

            else:
                # Wikilink
                replace(list_str, span_l, span_h, make_discord_link(wikilink.target))

    for template in wt.templates:
        span_l, span_h = t.cast(t.Tuple[int, int], template.span)
        if not template.templates:
            replace(list_str, span_l, span_h, TEMPLATE_MAPPING.get(template.name))

    return "".join(c for c in list_str if c is not None)


def make_display_rarity(rarity: int, max_rarity: int) -> str:
    return constants.WeaponRarity(rarity).emoji + (max_rarity - rarity) * constants.EMPTY_STAR


# Battlesuits


def make_battlesuit_description(battlesuit: battlesuits.Battlesuit) -> str:
    """Used as fallback for battlesuits without a description. Appears to be the case for augments."""
    return f"{make_discord_link(battlesuit.character)} battlesuit." + (
        f"\n{make_discord_link('Augment Core')} upgrade of {make_discord_link(battlesuit.augment)}"
        if battlesuit.augment
        else ""
    )


def make_battlesuit_header_embed(battlesuit: battlesuits.Battlesuit) -> utilities.FormattableEmbed:
    desc = (
        parse_wiki_str(battlesuit.profile)
        if battlesuit.profile
        else make_battlesuit_description(battlesuit)
    )
    return (
        utilities.FormattableEmbed(
            description=desc,
            color=battlesuit.type.colour,
        )
        .set_author(
            name=(name := battlesuit.name),
            url=make_wiki_link(name),
            icon_url=image_link(f"Valkyrie_{battlesuit.rank}"),
        )
        .set_thumbnail(url=image_link(f"{name}_(Avatar)"))
        .set_footer(text=LINK_FMT.format(name=name))
    )


# TODO: Clean this shit up
def make_battlesuit_info_embed(battlesuit: battlesuits.Battlesuit) -> utilities.FormattableEmbed:
    info_embed = utilities.FormattableEmbed(color=battlesuit.type.colour).add_field(
        name="About:",
        value=(
            " ".join(battlesuit.core_strengths)
            + f"\nType: {battlesuit.type.emoji} {battlesuit.type.name}"
            + f"\nValkyrie: {constants.RequestCategoryEmoji.BATTLESUITS} {make_discord_link(battlesuit.character)}"  # noqa: E501
            + (
                f"\nAugment (of): {constants.RequestCategoryEmoji.BATTLESUITS} {make_discord_link(battlesuit.augment)}"  # noqa: E501
                if battlesuit.augment
                else ""
            )
            + (
                f"\nAwakening (of): {constants.RequestCategoryEmoji.BATTLESUITS} {make_discord_link(battlesuit.awakening)}"  # noqa: E501
                if battlesuit.awakening
                else ""
            )
        ),
        inline=False,
    )
    for recommendation in battlesuit.recommendations:
        info_embed.add_field(
            name=f"{recommendation.type.title()}:",
            value=(
                f"{constants.RequestCategoryEmoji.WEAPONS} {make_discord_link(recommendation.weapon.name)}\n"
                f"{constants.StigmaSlotEmoji.TOP} {make_discord_link(recommendation.T.name)}\n"
                f"{constants.StigmaSlotEmoji.MIDDLE} {make_discord_link(recommendation.M.name)}\n"
                f"{constants.StigmaSlotEmoji.BOTTOM} {make_discord_link(recommendation.B.name)}"
            ),
        )

    return info_embed


def prettify_battlesuit(
    battlesuit: battlesuits.Battlesuit,
) -> t.Tuple[utilities.FormattableEmbed, utilities.FormattableEmbed]:
    return (make_battlesuit_header_embed(battlesuit), make_battlesuit_info_embed(battlesuit))


# Stigmata


def make_stigma_description(
    stigma: stigmata.Stigma, show_rarity: bool = False
) -> t.Tuple[str, str]:
    """Generate the description for a single `Stigma`."""
    effect = parse_wiki_str(stigma.effect)
    description = (f"Rarity: {stigma.rarity.emoji}\n" if show_rarity else "") + effect

    stats = ",\u2003".join(
        f"**{name}**: {stat}"
        for name, stat in (
            ("HP", stigma.hp),
            ("ATK", stigma.attack),
            ("DEF", stigma.defense),
            ("CRT", stigma.crit),
        )
        if stat
    )
    return truncate(description, 1024), stats


def make_stigma_embed(stigma: stigmata.Stigma, show_rarity: bool) -> utilities.FormattableEmbed:
    """Generate a display embed for a single `Stigma`."""
    description, stats = make_stigma_description(stigma, show_rarity)

    return (
        utilities.FormattableEmbed(
            title=stigma.effect_name,
            description=description,
            colour=stigma.slot.colour,
        )
        .add_field(
            name="\u200b",
            value=stats,
        )
        .set_author(
            name=stigma.name,
            url=make_wiki_link(stigma.set_name),
            icon_url=image_link(f"Stigmata_{stigma.slot.name.title()}"),
        )
        .set_thumbnail(url=image_link(f"{stigma.set_name} ({stigma.slot}) (Icon)"))
        .set_footer(text=LINK_FMT.format(name=stigma.set_name))
    )


def make_set_bonus_embed(
    set_bonuses: t.Sequence[stigmata.SetBonus], set_rarity: str
) -> utilities.FormattableEmbed:
    """Generate a display embed for a `StigmataSet`'s set bonuses."""
    set_embed = utilities.FormattableEmbed(description=f"Rarity: {set_rarity}")
    for set_bonus in set_bonuses:
        set_embed.add_field(
            name=set_bonus.name,
            value=parse_wiki_str(set_bonus.effect),
            inline=False,
        )
    return set_embed


def prettify_stigmata(
    stigmata_set: stigmata.StigmataSet,
) -> t.Tuple[utilities.FormattableEmbed, ...]:
    """Generate display embeds for a `StigmataSet`."""
    set_stigmata, set_bonuses = stigmata_set.get_main_set_with_bonuses()

    embeds = [make_stigma_embed(stig, stig not in set_stigmata) for stig in stigmata_set.stigmata]

    if set_bonuses and set_stigmata:
        embeds.append(make_set_bonus_embed(set_bonuses, set_stigmata[0].rarity.emoji))

    return tuple(embeds)


# Weapons


def make_weapon_header_embed(weapon: weapons.Weapon) -> utilities.FormattableEmbed:
    description = (
        "Rarity: {display_rarity}\n\n"
        f"{parse_wiki_str(weapon.description)}\n\n"
        "**ATK**: {stats.attack}\t**CRT**: {stats.crit}"
    )

    if weapon.pri_arm or weapon.pri_arm_base:
        description += (
            f"\n\n**PRI-ARM {'of**:' if weapon.pri_arm_base else '**:'}"
            f"\n{make_discord_link(weapon.pri_arm or weapon.pri_arm_base)}"  # type: ignore
        )

    return (
        utilities.FormattableEmbed(description=description)
        .set_author(
            name=weapon.name,
            url=make_wiki_link(weapon.name),
            icon_url=image_link(f"{weapon.type} (Type)"),
        )
        .set_thumbnail(image_link(f"{weapon.name} ({{rarity}}) (Icon)"))
        .set_footer(text=LINK_FMT.format(name=weapon.name))
    )


def make_weapon_info_embed(weapon: weapons.Weapon) -> utilities.FormattableEmbed:
    info_embed = utilities.FormattableEmbed()
    for skill in weapon.skills:
        icon = (
            constants.WeaponSkillTypeEmoji.ACTIVE
            if skill.is_active()
            else constants.WeaponSkillTypeEmoji.PASSIVE
        )

        field_title = f"{icon} {skill.name}"
        if skill.core_strengths:
            field_title += " " + "".join(skill.core_strengths)

        info_embed.add_field(
            name=field_title,
            value=truncate(parse_wiki_str(skill.effect), 1024),
            inline=False,
        )

    return info_embed


def prettify_weapon(
    weapon: weapons.Weapon,
) -> t.Tuple[utilities.FormattableEmbed, utilities.FormattableEmbed]:
    return (make_weapon_header_embed(weapon), make_weapon_info_embed(weapon))

import typing as t

import disnake
from disnake.ext import components

from maid_in_abyss import bot
from maid_in_abyss.exts.meta import delete

from . import constants, models
from .backend import api, api_types, cache


def build_wikilink_browser_options(
    wikilinks: api_types.WikiLinkDict,
    *,
    back_id: t.Optional[str] = None,
    back_category: t.Optional[str] = None,
) -> t.List[disnake.SelectOption]:
    options: t.List[disnake.SelectOption] = []

    if back_id and back_category:
        options.append(
            disnake.SelectOption(
                label="Back",
                value=f"{back_id}:{back_category}",
                emoji="<:undo:997511439055061002>",
            )
        )

    for page_id, (title, category) in wikilinks.items():
        if page_id == back_id:
            continue

        options.append(
            disnake.SelectOption(
                label=title,
                value=f"{page_id}:{category}",
                emoji=constants.RequestCategory(category).emoji,
            )
        )

    return options


def build_rarity_browser_options(
    min_rarity: int,
    max_rarity: int,
    *,
    current_rarity: t.Optional[int] = None,
    **_: t.Any,  # Ignore extraneous kwargs such that we can just pass **metadata.
) -> t.List[disnake.SelectOption]:
    if current_rarity is None:
        current_rarity = min_rarity

    return [
        disnake.SelectOption(
            default=(rarity == current_rarity),
            label=str(rarity),
            emoji=constants.STAR,
        )
        for rarity in range(min_rarity, max_rarity + 1)
    ]


@components.select_listener(sep="|")  # different separator to support : in category
async def wikilink_browser(
    inter: disnake.MessageInteraction,
    query: str = components.SelectValue("Continue searching...", max_values=1),
    *,
    category: str,
    current_page_id: t.Optional[str],
    author_id: int,
):
    assert isinstance(inter.bot, bot.Maid_in_Abyss)
    assert isinstance(wikilink_browser, components.SelectListener)

    page_id, target_category = query.split(":", 1)

    if author_id != inter.author.id:
        await inter.response.send_message(
            embed=disnake.Embed(
                title="You are not permitted to take this action.",
                description="This wiki prompt is for another captain.",
            ),
            ephemeral=True,
        )
        return

    content, wikilinks, metadata = await api.handle_request(
        target_category,
        page_id,
        session=inter.bot.default_session,
        redis_client=inter.bot.redis,
    )

    message_components = await build_for_content(
        author_id=inter.author.id,
        page_id=page_id,
        current_page_id=current_page_id,
        current_category=category,
        category=target_category,
        wikilinks=wikilinks,
        **metadata,
    )

    # TODO: Remove type-ignore when disnake typings improve (List[Embed] -> Sequence[Embed])
    await inter.response.edit_message(embeds=content, components=message_components)  # type: ignore


@components.select_listener()
async def rarity_browser(
    inter: disnake.MessageInteraction,
    rarity: int = components.SelectValue("View stats at a different rarity...", max_values=1),
    *,
    page_id: str,
    author_id: int,
):
    assert isinstance(inter.bot, bot.Maid_in_Abyss)
    assert isinstance(rarity_browser, components.SelectListener)

    if author_id != inter.author.id:
        await inter.response.send_message(
            embed=disnake.Embed(
                title="You are not permitted to take this action.",
                description="This wiki prompt is for another captain.",
            ),
            ephemeral=True,
        )
        return

    # Try getting from cache...
    async with cache.ExpirePipeline.from_redis_client(inter.bot.redis) as pipe:
        pipe.hmget(
            page_id,
            (
                cache.ContentKind.CONTENT,
                cache.ContentKind.STATS,
                cache.ContentKind.MIN_RARITY,
                cache.ContentKind.MAX_RARITY,
            ),
        )
        data = await pipe.execute()

    if all(data):
        (raw_content, raw_stats, raw_min_rarity, raw_max_rarity), *_ = data
        (header_embed, *info_embeds) = cache.parse_content(raw_content)
        stats = cache.parse_stats(raw_stats)
        min_rarity = int(raw_min_rarity)
        max_rarity = int(raw_max_rarity)

    # Cache failed, try making an api request...
    # We bypass api's utility functions as we don't care about wikilinks for this operation.
    elif data := await api.request_content_revision(inter.bot.default_session, query=page_id):
        weapon = models.Weapon.parse_wikitext(data.content)
        (header_embed, *info_embeds) = models.display.prettify_weapon(weapon)

        stats = weapon.stats
        min_rarity = weapon.rarity
        max_rarity = weapon.max_rarity

    else:
        raise RuntimeError("something something")

    formatted_header = header_embed.format(
        rarity=min_rarity,
        stats=stats[rarity - min_rarity],
        display_rarity=models.display.make_display_rarity(rarity, max_rarity),
    )

    # TODO: Rework this into a build_for_content-derivative that can use existing components
    rows = disnake.ui.ActionRow.rows_from_message(inter.message)
    for row, component in disnake.ui.ActionRow.walk_components(rows):
        if component.custom_id != inter.component.custom_id:
            continue

        row.clear_items()
        row.append_item(
            await rarity_browser.build_component(
                options=build_rarity_browser_options(min_rarity, max_rarity, current_rarity=rarity),
                page_id=page_id,
                author_id=author_id,
            )
        )

        break  # We can only ever interact with one component at a time.

    await inter.response.edit_message(embeds=[formatted_header, *info_embeds], components=rows)


async def build_delete_button(*, user_id: int) -> disnake.ui.Button[None]:
    return await delete.delete_button_listener.build_component(
        user_id=user_id,
        permissions=disnake.Permissions(manage_messages=True),
    )


# TODO: make this less fucky
async def build_for_content(
    *,
    author_id: int,
    category: str,
    page_id: str,
    current_page_id: t.Optional[str] = None,
    current_category: t.Optional[str] = None,
    wikilinks: t.Optional[api_types.WikiLinkDict] = None,
    **metadata: t.Any,
) -> t.Sequence[disnake.ui.MessageUIComponent]:
    components: t.List[disnake.ui.MessageUIComponent] = []

    if wikilinks:
        options = build_wikilink_browser_options(
            wikilinks,
            back_id=current_page_id,
            back_category=current_category,
        )

        if options:
            components.append(
                await wikilink_browser.build_component(
                    options=options,
                    author_id=author_id,
                    category=category,
                    current_page_id=page_id,
                )
            )

    if page_id and category == constants.RequestCategory.WEAPONS:
        components.append(
            await rarity_browser.build_component(
                options=build_rarity_browser_options(**metadata),
                page_id=page_id,
                author_id=author_id,
            )
        )

    components.append(await build_delete_button(user_id=author_id))

    return components

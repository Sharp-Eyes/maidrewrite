import asyncio
import logging
import time
import typing as t

import disnake
from disnake.ext import commands, components

import bot
import utilities
from database.models import hoyo_wiki
from exts.meta import delete

from . import api, constants

__all__ = ("setup", "teardown", "plugin")

LOGGER = logging.getLogger(__name__)


WikiLinkDict = t.Dict[str, t.Tuple[str, str]]


async def build_delete_button(*, user_id: int) -> disnake.ui.Button[None]:
    return await delete.delete_button_listener.build_component(
        user_id=user_id,
        permissions=disnake.Permissions(manage_messages=True),
    )


plugin = utilities.Plugin.with_metadata(
    name="hi3_wiki",
    category="wiki",
)


@commands.is_owner()
@plugin.slash_command(guild_ids=[701039771157397526])
async def cache(inter: disnake.CommandInteraction, clear: bool = False):
    assert isinstance(inter.bot, bot.Maid_in_Abyss)  # cope with inter not being generic over bot

    await inter.response.defer()

    request_base_params: t.Dict[str, t.Any] = {
        "action": "query",
        "format": "json",
        "prop": "categories|redirects",
        "generator": "categorymembers",
        "utf8": 1,
        "cllimit": "max",
        "rdprop": "title",
        "rdlimit": "max",
        "gcmlimit": "max",
    }

    if clear:
        await hoyo_wiki.PageInfo.objects.delete(each=True)
        method = hoyo_wiki.PageInfo.objects.bulk_create
    else:
        method = hoyo_wiki.PageInfo.objects.bulk_update

    categories = (
        (constants.RequestCategory.STIGMATA, constants.StigmaRarityCategory),
        (constants.RequestCategory.BATTLESUITS, constants.BattlesuitRarityCategory),
        (constants.RequestCategory.WEAPONS, constants.WeaponRarityCategory),
    )

    await asyncio.gather(
        *[
            api.fetch_and_store_pages(
                method,
                inter.bot.default_session,
                model_params={"main_category": request_category.value},
                # Request parameters...
                **request_base_params,
                clcategories="|".join(sub_categories),
                gcmtitle=request_category.value,
            )
            for request_category, sub_categories in categories
        ]
    )

    await inter.edit_original_message("Successfully fetched and stored data.")


@plugin.slash_command()
async def wiki(inter: disnake.CommandInteraction):
    ...


@wiki.sub_command()
async def hi3(inter: disnake.CommandInteraction, query: str):
    assert isinstance(inter.bot, bot.Maid_in_Abyss)  # cope

    embeds, wikilinks = await api.fetch_content(
        inter.bot.redis, inter.bot.default_session, query=query
    )

    if wikilinks:
        components: t.List[disnake.ui.MessageUIComponent] = [
            disnake.ui.Select(
                options=build_select_options(wikilinks),
                placeholder="Continue browsing...",
                custom_id=await page_subselector.build_custom_id(
                    author_id=inter.user.id,
                    current_page_id=query,
                ),
            )
        ]
    else:
        components = []

    components.append(await build_delete_button(user_id=inter.user.id))
    await inter.response.send_message(embeds=embeds, components=components)
    return


def make_autocomp_title(record: t.Any):
    return (
        title
        if (title := record.title) == (orig := record.alias_of)
        else f"{orig} \u300C{title}\u300D"
    )


@hi3.autocomplete("query")
async def wiki_search_autocomp(inter: disnake.CommandInteraction, query: str):
    assert isinstance(inter.bot, bot.Maid_in_Abyss)  # cope

    # TODO: Maybe don't rely on the db for this if the bot gets bigger,
    #       but as-is, this query takes ~10 ms (+/- overhead), so it's probably
    #       fast enough for the time being.

    t1 = time.perf_counter()

    records: t.List[t.Any] = await inter.bot.database.fetch_all(
        """--sql
        WITH ranking AS (
            SELECT *,
            title <-> :query as dist,
            RANK() OVER (PARTITION BY alias_of ORDER BY title <-> :query ASC) AS r
            FROM hi3_wiki_pages
        )
        SELECT *
        FROM ranking
        WHERE r=1
        ORDER BY dist ASC
        LIMIT 25;
        """,
        values={"query": query.lower()},
    )

    tdiff = time.perf_counter() - t1
    LOGGER.debug(f"Completed autocomplete query in {tdiff*1000:.3f}ms.")

    return {make_autocomp_title(record): str(record.pageid) for record in records}


def build_select_options(
    wikilinks: WikiLinkDict,
    *,
    back_id: t.Optional[str] = None,
) -> t.List[disnake.SelectOption]:
    options: t.List[disnake.SelectOption] = []

    for page_id, (title, category) in wikilinks.items():
        if page_id == back_id:
            options.insert(
                0,
                disnake.SelectOption(
                    label=f"{title} (Back)",
                    value=page_id,
                    emoji="<:undo:997511439055061002>",
                ),
            )
            back_id = None
            continue

        options.append(
            disnake.SelectOption(
                label=title,
                value=page_id,
                emoji=constants.RequestCategory(category).emoji,
            )
        )

    if back_id is not None:
        options.insert(
            0,
            disnake.SelectOption(
                label="Back",
                value=back_id,
                emoji="<:undo:997511439055061002>",
            ),
        )

    return options


@plugin.listener(components.ListenerType.SELECT)
@components.select_listener()
async def page_subselector(
    inter: disnake.MessageInteraction,
    page_id: str = components.SelectValue("Continue searching...", max_values=1),
    *,
    current_page_id: t.Optional[str],
    author_id: int,
):
    assert isinstance(inter.bot, bot.Maid_in_Abyss)
    assert isinstance(page_subselector, components.SelectListener)

    if author_id != inter.author.id:
        # await inter.response.send_message(
        #     embed=disnake.Embed(
        #         title="You are not permitted to take this action.",
        #         description="This dropdown menu is for another captain.",
        #     ),
        #     ephemeral=True,
        # )
        # return
        raise utilities.exceptions.NotPermitted("This selector is for a different captain...")

    embeds, wikilinks = await api.fetch_content(
        inter.bot.redis,
        inter.bot.default_session,
        query=page_id,
    )

    if options := build_select_options(wikilinks, back_id=current_page_id):
        msg_components: t.List[disnake.ui.MessageUIComponent] = [
            disnake.ui.Select(
                options=options,
                placeholder="Continue browsing...",
                custom_id=await page_subselector.build_custom_id(
                    author_id=inter.user.id,
                    current_page_id=page_id,
                ),
            )
        ]

    else:
        msg_components = []

    msg_components.append(await build_delete_button(user_id=inter.user.id))
    await inter.response.edit_message(embeds=embeds, components=msg_components)


@plugin.listener_error_handler(components.ListenerType.SELECT)
async def on_dropdown_error(
    exc: Exception,
    inter: disnake.MessageInteraction,
    *args: t.Any,
    **kwargs: t.Any,
):
    await inter.response.send_message(str(exc))
    return True


setup, teardown = plugin.create_extension_handlers()

import asyncio
import logging
import time
import typing as t

import disnake
from disnake.ext import commands, components

from maid_in_abyss import bot, utilities
from maid_in_abyss.database.models import hoyo_wiki

from . import constants, interactivity
from .backend import api

__all__ = ("setup", "teardown", "plugin")

LOGGER = logging.getLogger(__name__)


WikiLinkDict = t.Dict[str, t.Tuple[str, str]]


plugin = utilities.Plugin.with_metadata(
    name="hi3_wiki",
    category="wiki",
)


@commands.is_owner()
@plugin.slash_command(guild_ids=[701039771157397526], name="cache")
async def cache_(inter: disnake.CommandInteraction, clear: bool = False):
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

    page_id, category = query.split(":", 1)

    content, wikilinks, metadata = await api.handle_request(
        category,
        page_id,
        session=inter.bot.default_session,
        redis_client=inter.bot.redis,
    )

    message_components = await interactivity.build_for_content(
        author_id=inter.author.id,
        page_id=page_id,
        category=category,
        wikilinks=wikilinks,
        **metadata,
    )

    # TODO: remove type ignore when disnake typings become more lenient (List -> Sequence/Collection)
    await inter.response.send_message(embeds=content, components=message_components)  # type: ignore


def make_autocomp_title(record: t.Any):
    return (
        title
        if (title := record.title) == (original_title := record.alias_of)
        else f"{original_title} \u300C{title}\u300D"
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

    return {
        make_autocomp_title(record): f"{record.pageid}:{record.main_category}" for record in records
    }


plugin.add_listeners(
    interactivity.wikilink_browser,
    interactivity.rarity_browser,
    event=components.ListenerType.SELECT,
)


setup, teardown = plugin.create_extension_handlers()

import asyncio
import logging
import time
import typing as t

import aiohttp
import bot
import disnake
import utilities
from database.models import hoyo_wiki

from . import api, api_types, constants, interface, models

__all__ = ("setup", "teardown", "plugin")

LOGGER = logging.Logger(__name__)

plugin = utilities.Plugin.with_metadata(
    name="hi3_wiki",
    category="Wiki",
    slash_command_attrs={"guild_ids": [701039771157397526]},
)


def safe_key(key: str):
    return key.lower().replace(" ", "_")


async def _fetch_unique_pages(
    session: aiohttp.ClientSession,
    *,
    request_base_params: t.Dict[str, str],
    model_base_params: t.Optional[t.Dict[str, t.Any]] = None,
    **request_params: str,
) -> t.AsyncGenerator[t.Dict[str, t.Any], t.Any]:
    titles: t.Set[t.Dict[str, t.Any]] = set()
    async for page in api.WikiRequest(
        session, model=api_types.PageInfoValidator, params=request_base_params | request_params
    ):
        for alias_data in page.unpack_aliases(base_params=model_base_params or {}):
            if (title := alias_data["title"]) in titles:
                continue

            titles.add(title)
            yield alias_data


async def _fetch_and_store_pages(
    method: t.Callable[[t.List[hoyo_wiki.PageInfo]], t.Coroutine[t.Any, t.Any, None]],
    session: aiohttp.ClientSession,
    *,
    request_base_params: t.Dict[str, t.Any],
    model_base_params: t.Optional[t.Dict[str, t.Any]] = None,
    **request_params: t.Any,
):
    await method(
        [
            hoyo_wiki.PageInfo.construct(**page_data)
            async for page_data in _fetch_unique_pages(
                session,
                request_base_params=request_base_params,
                model_base_params=model_base_params,
                **request_params,
            )
        ]
    )


@plugin.slash_command()
async def cache(inter: disnake.CommandInteraction, clear: bool = False):
    assert isinstance(inter.bot, bot.Maid_in_Abyss)  # cope with inter not being generic over bot

    await inter.response.defer()

    base_params: t.Dict[str, t.Any] = {
        "action": "query",
        "format": "json",
        "prop": "categories|redirects",
        "generator": "categorymembers",
        "utf8": 1,
        "cllimit": "max",
        "clcategories": ...,
        "rdprop": "title",
        "rdlimit": "max",
        "gcmtitle": ...,
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
            _fetch_and_store_pages(
                method,
                inter.bot.default_session,
                request_base_params=base_params,
                model_base_params={"category": request_category},
                clcategories="|".join(sub_categories),
                gcmtitle=request_category.value,
            )
            for request_category, sub_categories in categories
        ]
    )

    await inter.edit_original_message("Successfully fetched and stored data.")


@plugin.slash_command()
async def readcache(inter: disnake.CommandInteraction, query: str):
    assert isinstance(inter.bot, bot.Maid_in_Abyss)  # cope

    page_params = {
        "action": "query",
        "format": "json",
        "prop": "revisions",
        "pageids": query,
        "rvprop": "content",
        "rvslots": "main",
    }

    async for page in api.WikiRequest(
        inter.bot.default_session,
        model=api_types.PageContentValidator,
        params=page_params,
    ):
        revision_data = api.wikitext_to_dict(page.revision.content)

        if "battlesuit" in revision_data:
            battlesuit = models.Battlesuit.parse_obj(revision_data)
            embeds = interface.display.prettify_battlesuit(battlesuit)

        elif {"slotT", "slotM", "slotB"}.intersection(revision_data):
            stigmata = models.StigmataSet.parse_obj(revision_data)
            embeds = interface.display.prettify_stigmata(stigmata)

        elif {"ATK", "CRT"}.issubset(revision_data):
            weapon = models.Weapon.parse_obj(revision_data)
            embeds = interface.display.prettify_weapon(weapon)

        else:
            print(list(revision_data.keys()))
            await inter.send(str(revision_data)[:2000])
            return

        await inter.send(embeds=embeds)
        return


def make_autocomp_title(record: t.Any):
    return (
        title
        if (title := record.title) == (orig := record.alias_of)
        else f"{orig} \u300C{title}\u300D"
    )


@readcache.autocomplete("query")
async def wiki_search_autocomp(inter: disnake.CommandInteraction, query: str):
    assert isinstance(inter.bot, bot.Maid_in_Abyss)  # cope

    # TODO: Maybe don't rely on the db for this if the bot gets bigger,
    #       but as-is, this query takes ~3 ms (+ overhead), so it's probably
    #       fast enough for the time being.

    t1 = time.perf_counter()

    records: t.List[t.Any] = await inter.bot.database.fetch_all(
        """--sql
        SELECT * FROM (
            SELECT DISTINCT ON (alias_of)
                pageid,
                title,
                alias_of,
                title <-> :query AS dist
            FROM hi3_wiki_pages
        ) tmp
        ORDER BY dist ASC
        LIMIT 25;
        """,
        values={"query": query.lower()},
    )

    tdiff = time.perf_counter() - t1
    LOGGER.info(f"Completed autocomplete query in {tdiff:.3f}ms.")
    print(f"Completed autocomplete query in {tdiff*1000:.3f}ms.")

    return {make_autocomp_title(record): str(record.pageid) for record in records}


setup, teardown = plugin.create_extension_handlers()

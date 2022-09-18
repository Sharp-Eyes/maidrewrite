from __future__ import annotations

import logging
import typing as t

import aiohttp
import pydantic
import redis.asyncio
import wikitextparser

from maid_in_abyss import utilities
from maid_in_abyss.database.models import hoyo_wiki

from .. import constants, models
from . import api_types, cache

LOGGER = logging.getLogger(__name__)


T = t.TypeVar("T")
MaybeWikilink = t.Union[str, wikitextparser.WikiLink]


class WikiRequest(t.AsyncIterator[T]):

    _iterator: t.Iterator[t.Dict[str, t.Any]]

    def __init__(
        self,
        session: aiohttp.ClientSession,
        *,
        model: t.Callable[..., T],
        params: t.Dict[str, str],
    ):
        self.session = session
        self.model = model

        self._params = params
        self._iterator = iter(())
        self._continue = {}
        self._done = False

    @property
    def params(self) -> t.Dict[str, str]:
        return self._params | self._continue

    async def get_chunk(self) -> t.Dict[str, t.Any]:
        async with self.session.get(constants.API_BASE, params=self.params) as response:
            response.raise_for_status()
            data: api_types.AnyResponse = await response.json()

        assert data  # type: ignore  # How is this possibly unbound???

        if "batchcomplete" in data:
            self._done = True

        if "warnings" in data:
            logging.warn(
                "Encountered one or more warnings in API request to {url}: {warnings}".format(
                    url=response.url,
                    warnings=", ".join(
                        f"{item}={warn['*']}"
                        for item, warn in data["warnings"].items()
                    ),  # fmt: skip
                )
            )

        self._continue = data.get("continue", {})
        return data["query"]["pages"]

    async def __anext__(self) -> T:
        try:
            value = next(self._iterator)

        except StopIteration:
            if self._done:
                raise StopAsyncIteration

            chunk = await self.get_chunk()
            self._iterator = iter(chunk.values())
            value = next(self._iterator)

        try:
            return self.model(**value)
        except pydantic.ValidationError as e:
            # This is fully expected to happen for a group of poorly placed categories.
            # Logging these is not really of any benefit, and any warnings that could
            # lead to unexpected/unwanted errors are already logged.
            # Therefore, this can be safely ignored, and the next value can be returned.
            LOGGER.warning(
                "Encountered {num} validation errors while parsing model {model.__name__}: {value}".format(
                    num=len(e.errors()),
                    model=self.model,
                    value=value,
                )
            )
            return await self.__anext__()


# Page-info processing


async def fetch_unique_pages(
    session: aiohttp.ClientSession,
    **request_params: str,
) -> t.AsyncGenerator[t.Dict[str, t.Any], t.Any]:
    titles: t.Set[t.Dict[str, t.Any]] = set()
    async for page in WikiRequest(
        session, model=api_types.PageInfoValidator, params=request_params
    ):
        for alias_data in page.unpack_aliases():
            if (title := alias_data["title"]) in titles:
                continue

            titles.add(title)
            yield alias_data


async def fetch_and_store_pages(
    method: t.Callable[[t.List[hoyo_wiki.PageInfo]], t.Coroutine[t.Any, t.Any, None]],
    session: aiohttp.ClientSession,
    *,
    model_params: t.Optional[t.Dict[str, t.Any]] = None,
    **request_params: t.Any,
):
    if model_params is None:
        model_params = {}

    await method(
        [
            hoyo_wiki.PageInfo.construct(**page_data, **model_params)
            async for page_data in fetch_unique_pages(session, **request_params)
        ]
    )


# Page content processing


async def validate_wikilinks(
    wikilinks: t.Sequence[MaybeWikilink],
) -> t.Sequence[hoyo_wiki.PageInfo]:
    return await (
        hoyo_wiki.PageInfo.objects.filter(
            title__in=[
                link.title if isinstance(link, wikitextparser.WikiLink) else link
                for link in wikilinks
            ]
        ).all()
    )


async def request_content_revision(
    session: aiohttp.ClientSession, *, query: str
) -> api_types.RevisionValidator:

    page_params = {
        "action": "query",
        "format": "json",
        "prop": "revisions|categories",
        "pageids": query,
        "rvprop": "content",
        "rvslots": "main",
        "clcategories": "|".join(constants.RequestCategory),
    }

    async for page in WikiRequest(  # TODO: Provide method to get only a single page.
        session,
        model=api_types.PageContentValidator,
        params=page_params,
    ):
        return page.revision

    raise RuntimeError("PLACEHOLDER")  # TODO: remove when the above todo is resolved


async def request_battlesuit(
    session: aiohttp.ClientSession, *, query: str
) -> t.Tuple[
    models.Battlesuit,
    api_types.WikiLinkDict,
    t.Tuple[utilities.FormattableEmbed, utilities.FormattableEmbed],
]:
    revision = await request_content_revision(session, query=query)

    battlesuit = models.Battlesuit.parse_wikitext(revision.content)

    raw_wikilinks = t.cast(t.List[MaybeWikilink], revision.content.wikilinks)
    for rec in battlesuit.recommendations:
        raw_wikilinks.extend(field.name for field in [rec.weapon, rec.T, rec.M, rec.B])

    wikilinks = {
        str(ref.pageid): (ref.title, ref.main_category)
        for ref in await validate_wikilinks(raw_wikilinks)
    }

    content = models.display.prettify_battlesuit(battlesuit)

    return battlesuit, wikilinks, content


async def handle_battlesuit_request(
    page_id: str,
    *,
    session: aiohttp.ClientSession,
    redis_client: redis.asyncio.Redis[t.Any],
) -> t.Tuple[t.List[utilities.FormattableEmbed], api_types.WikiLinkDict, t.Mapping[str, t.Any]]:
    async with cache.ExpirePipeline.from_redis_client(redis_client) as pipe:
        pipe.hmget(page_id, (cache.ContentKind.CONTENT, cache.ContentKind.WIKILINKS))
        data = await pipe.execute()

    if all(data):
        (raw_content, raw_wikilinks), *_ = data
        content = cache.parse_content(raw_content)
        wikilinks = cache.parse_wikilinks(raw_wikilinks)

    elif data := await request_battlesuit(session, query=page_id):
        _, wikilinks, content = data  # _ is the battlesuit, see comment below.

        await cache.set_battlesuit(
            redis_client,
            page_id,
            content=content,
            wikilinks=wikilinks,
            # battlesuit=battlesuit,  # Currently not required elsewhere, and is thus not cached.
        )

    else:
        raise RuntimeError(f"Both cache and wiki page lookup for page id {page_id} failed.")

    # TODO: remove list call when disnake typings become more lenient.
    return list(content), wikilinks, {}


async def request_stigmata(
    session: aiohttp.ClientSession, *, query: str
) -> t.Tuple[
    models.StigmataSet,
    api_types.WikiLinkDict,
    t.Tuple[utilities.FormattableEmbed, utilities.FormattableEmbed],
]:
    revision = await request_content_revision(session, query=query)

    stigmata = models.StigmataSet.parse_wikitext(revision.content)

    wikilinks = {
        str(ref.pageid): (ref.title, ref.main_category)
        for ref in await validate_wikilinks(revision.content.wikilinks)
    }

    content = models.display.prettify_stigmata(stigmata)

    return stigmata, wikilinks, content


async def handle_stigmata_request(
    page_id: str,
    *,
    session: aiohttp.ClientSession,
    redis_client: redis.asyncio.Redis[t.Any],
) -> t.Tuple[t.List[utilities.FormattableEmbed], api_types.WikiLinkDict, t.Mapping[str, t.Any]]:
    async with cache.ExpirePipeline.from_redis_client(redis_client) as pipe:
        pipe.hmget(page_id, (cache.ContentKind.CONTENT, cache.ContentKind.WIKILINKS))
        data = await pipe.execute()

    if all(data):
        (raw_content, raw_wikilinks), *_ = data
        content = cache.parse_content(raw_content)
        wikilinks = cache.parse_wikilinks(raw_wikilinks)

    elif data := await request_stigmata(session, query=page_id):
        _, wikilinks, content = data  # _ are the stigmata, see comment below.

        await cache.set_stigmata(
            redis_client,
            page_id,
            content=content,
            wikilinks=wikilinks,
            # stigmata=stigmata,  # Currently not required elsewhere, and are thus not cached.
        )

    else:
        raise RuntimeError(f"Both cache and wiki page lookup for page id {page_id} failed.")

    # TODO: remove list call when disnake typings become more lenient.
    return list(content), wikilinks, {}


async def request_weapon(
    session: aiohttp.ClientSession, *, query: str
) -> t.Tuple[
    models.Weapon,
    api_types.WikiLinkDict,
    t.Tuple[utilities.FormattableEmbed, utilities.FormattableEmbed],
]:
    revision = await request_content_revision(session, query=query)

    weapon = models.Weapon.parse_wikitext(revision.content)

    raw_wikilinks = t.cast(t.List[MaybeWikilink], revision.content.wikilinks)
    if weapon.pri_arm:
        raw_wikilinks.append(weapon.pri_arm)
    elif weapon.pri_arm_base:
        raw_wikilinks.append(weapon.pri_arm_base)

    wikilinks = {
        str(ref.pageid): (ref.title, ref.main_category)
        for ref in await validate_wikilinks(raw_wikilinks)
    }

    content = models.display.prettify_weapon(weapon)

    return weapon, wikilinks, content


async def handle_weapon_request(
    page_id: str,
    *,
    session: aiohttp.ClientSession,
    redis_client: redis.asyncio.Redis[t.Any],
) -> t.Tuple[t.List[utilities.FormattableEmbed], api_types.WikiLinkDict, t.Mapping[str, t.Any]]:
    async with cache.ExpirePipeline.from_redis_client(redis_client) as pipe:
        pipe.hmget(
            page_id,
            (
                cache.ContentKind.CONTENT,
                cache.ContentKind.WIKILINKS,
                cache.ContentKind.STATS,
                cache.ContentKind.MIN_RARITY,
                cache.ContentKind.MAX_RARITY,
            ),
        )
        data = await pipe.execute()

    if all(data):
        (raw_content, raw_wikilinks, raw_stats, raw_min_rarity, raw_max_rarity), *_ = data
        content = cache.parse_content(raw_content)
        wikilinks = cache.parse_wikilinks(raw_wikilinks)
        stats = cache.parse_stats(raw_stats)
        min_rarity = int(raw_min_rarity)
        max_rarity = int(raw_max_rarity)

    elif data := await request_weapon(session, query=page_id):
        weapon, wikilinks, content = data

        stats = weapon.stats
        min_rarity = weapon.rarity
        max_rarity = weapon.max_rarity

        await cache.set_weapon(
            redis_client,
            page_id,
            content=content,
            wikilinks=wikilinks,
            weapon=weapon,
        )

    else:
        raise RuntimeError(f"Both cache and wiki page lookup for page id {page_id} failed.")

    (header_embed, *info_embeds) = content

    formatted_header = header_embed.format(
        rarity=min_rarity,
        stats=stats[0],
        display_rarity=models.display.make_display_rarity(min_rarity, max_rarity),
    )

    return (
        [formatted_header, *info_embeds],
        wikilinks,
        {"stats": stats, "min_rarity": min_rarity, "max_rarity": max_rarity},
    )


async def handle_request(
    category: str,
    page_id: str,
    *,
    session: aiohttp.ClientSession,
    redis_client: redis.asyncio.Redis[t.Any],
) -> t.Tuple[t.List[utilities.FormattableEmbed], api_types.WikiLinkDict, t.Mapping[str, t.Any]]:
    if category == constants.RequestCategory.BATTLESUITS:
        request = handle_battlesuit_request

    elif category == constants.RequestCategory.STIGMATA:
        request = handle_stigmata_request

    elif category == constants.RequestCategory.WEAPONS:
        request = handle_weapon_request

    else:
        raise ValueError(
            f"Expected category to be one of {', '.join(constants.RequestCategory)},"
            f" got {category}."
        )

    return await request(page_id, session=session, redis_client=redis_client)

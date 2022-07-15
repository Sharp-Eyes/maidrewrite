from __future__ import annotations

import asyncio
import logging
import typing as t

import aiohttp
import disnake
import pydantic
import redis.asyncio
import wikitextparser

import utilities
from database.models import hoyo_wiki

from . import api_types, constants, display, models

LOGGER = logging.getLogger(__name__)


T = t.TypeVar("T")

MaybeWikilink = t.Union[str, wikitextparser.WikiLink]
WikiLinkDict = t.Dict[str, t.Tuple[str, str]]


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
                "Encountered {num} validation errors while parsing model {model.__name__}".format(
                    num=len(e.errors()),
                    model=self.model,
                )
            )
            return await self.__anext__()


def wikitext_to_dict(wikitext: wikitextparser.WikiText) -> dict[str, str]:
    return {
        argument.name.strip(): argument.value.strip()
        for template in wikitext.templates
        for argument in template.arguments
        if not template.ancestors()  # Avoid nested arguments
    }


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


def parse_revision_content(
    revision_data: t.Dict[str, t.Any]
) -> t.Tuple[t.Union[models.Battlesuit, models.StigmataSet, models.Weapon], t.List[disnake.Embed]]:
    if "battlesuit" in revision_data:
        content = models.Battlesuit.parse_obj(revision_data)
        embeds = display.prettify_battlesuit(content)

    elif {"slotT", "slotM", "slotB"}.intersection(revision_data):
        content = models.StigmataSet.parse_obj(revision_data)
        embeds = display.prettify_stigmata(content)

    elif {"ATK", "CRT"}.issubset(revision_data):
        content = models.Weapon.parse_obj(revision_data)
        embeds = display.prettify_weapon(content)

    else:
        raise Exception  # TODO: Provide custom exception.

    return content, embeds


async def validate_wikilinks(*wikilinks: MaybeWikilink) -> t.Sequence[hoyo_wiki.PageInfo]:
    return await (
        hoyo_wiki.PageInfo.objects.filter(
            title__in=[
                link.title if isinstance(link, wikitextparser.WikiLink) else link
                for link in wikilinks
            ]
        ).all()
    )


async def request_content(
    session: aiohttp.ClientSession,
    *,
    query: str,
) -> t.Optional[t.Tuple[t.List[disnake.Embed], WikiLinkDict]]:
    page_params = {
        "action": "query",
        "format": "json",
        "prop": "revisions",
        "pageids": query,
        "rvprop": "content",
        "rvslots": "main",
    }

    async for page in WikiRequest(  # TODO: Provide method to get only a single page.
        session,
        model=api_types.PageContentValidator,
        params=page_params,
    ):
        revision_data = wikitext_to_dict(page.revision.content)

        content, embeds = parse_revision_content(revision_data)

        raw_wikilinks = t.cast(t.List[MaybeWikilink], page.revision.content.wikilinks)

        if isinstance(content, models.Battlesuit):
            for rec in content.recommendations:
                raw_wikilinks.extend(field.name for field in [rec.weapon, rec.T, rec.M, rec.B])

        wikilink_refs = await validate_wikilinks(*raw_wikilinks)
        wikilinks = {str(ref.pageid): (ref.title, ref.main_category) for ref in wikilink_refs}

        return embeds, wikilinks

    return None


async def cache_read_content(
    redis: redis.asyncio.Redis[t.Any],
    *,
    key: str,
) -> t.Optional[t.Tuple[t.List[disnake.Embed], WikiLinkDict]]:
    cached = await redis.hgetall(key)
    if not cached:
        return None

    LOGGER.info(f"Hit cache for key `{key}`")

    content = [disnake.Embed.from_dict(embed) for embed in utilities.json_loads(cached["content"])]
    wikilinks: WikiLinkDict = utilities.json_loads(cached["wikilinks"])

    # Refresh TTL
    asyncio.create_task(redis.expire(key, 120))
    return content, wikilinks


async def cache_write_content(
    redis: redis.asyncio.Redis[t.Any],
    *,
    key: str,
    content: t.Sequence[disnake.Embed],
    wikilinks: WikiLinkDict,
) -> None:
    await redis.hset(
        key,
        mapping={
            "type": type(content).__name__,
            "content": utilities.json_dumps([embed.to_dict() for embed in content]),
            "wikilinks": utilities.json_dumps(wikilinks),
        },
    )
    await redis.expire(key, 120)


async def fetch_content(
    redis: redis.asyncio.Redis[t.Any],
    session: aiohttp.ClientSession,
    *,
    query: str,
) -> t.Tuple[t.List[disnake.Embed], WikiLinkDict]:
    if data := await cache_read_content(redis, key=query):
        return data

    elif data := await request_content(session, query=query):
        content, wikilinks = data
        asyncio.create_task(
            cache_write_content(redis, key=query, content=content, wikilinks=wikilinks)
        )
        return data

    raise Exception  # TODO: Provide custom exception.

from __future__ import annotations

import enum
import logging
import typing as t

import disnake
import pydantic
import redis.asyncio
import redis.asyncio.client

from maid_in_abyss import utilities

from .. import constants, models
from . import api_types

__all__ = (
    "CacheKeyError",
    "ExpirePipeline",
    "set_battlesuit",
    "set_stigmata",
    "set_weapon",
    "parse_stats",
    "get_stats",
    "parse_content",
    "get_content",
    "parse_wikilinks",
    "get_wikilinks",
)


LOGGER = logging.getLogger(__name__)


if t.TYPE_CHECKING:
    Redis = redis.asyncio.Redis[t.Any]
    Pipeline = redis.asyncio.client.Pipeline[t.Any]
    PipeT = t.TypeVar("PipeT", bound=Pipeline)

else:
    # Cope with redis typing issues...
    Pipeline = redis.asyncio.client.Pipeline


class ContentKind(str, enum.Enum):
    CATEGORY = "category"
    CONTENT = "content"
    WIKILINKS = "wikilinks"
    STATS = "stats"
    MIN_RARITY = "rarity"
    MAX_RARITY = "max_rarity"


class CacheKeyError(KeyError):
    def __init__(self, kind: str, key: str):
        self.key = key
        super().__init__(f"Could not find cached {kind} for key {key}.")


class ExpirePipeline(Pipeline):
    CACHE_EXPIRE_TIME = 300  # seconds

    @classmethod
    def from_redis_client(cls, redis_client: Redis):
        return cls(
            redis_client.connection_pool,
            redis_client.response_callbacks,
            True,
            None,
        )

    async def execute(self, raise_on_error: bool = ...) -> t.List[t.Any]:
        to_expire: t.Set[str] = set()  # All keys that appear in the pipe.
        expired: t.Set[str] = set()  # All keys that already are expired by the pipe.
        for (command, key, *_), _ in self.command_stack:
            if command == "EXPIRE":
                expired.add(key)
            else:
                to_expire.add(key)

        for key in to_expire - expired:  # Expire keys that have not had their expiration set.
            super().expire(key, self.CACHE_EXPIRE_TIME)

        return t.cast(t.List[t.Any], await super().execute(raise_on_error))


def dump_content(content: t.Sequence[disnake.Embed]) -> str:
    return utilities.json_dumps([embed.to_dict() for embed in content])


def dump_stats(stats: t.Sequence[models.WeaponStats]) -> str:
    return utilities.json_dumps([stat.dict() for stat in stats])


async def set_battlesuit(
    redis_client: Redis,
    key: str,
    *,
    content: t.Sequence[disnake.Embed],
    wikilinks: api_types.WikiLinkDict,
):
    async with ExpirePipeline.from_redis_client(redis_client) as pipe:
        pipe.hset(
            key,
            mapping={
                ContentKind.CATEGORY: constants.RequestCategory.BATTLESUITS,
                ContentKind.CONTENT: dump_content(content),
                ContentKind.WIKILINKS: utilities.json_dumps(wikilinks),
            },
        )
        await pipe.execute()


async def set_stigmata(
    redis_client: Redis,
    key: str,
    *,
    content: t.Sequence[disnake.Embed],
    wikilinks: api_types.WikiLinkDict,
):
    async with ExpirePipeline.from_redis_client(redis_client) as pipe:
        pipe.hset(
            key,
            mapping={
                ContentKind.CATEGORY: constants.RequestCategory.STIGMATA,
                ContentKind.CONTENT: dump_content(content),
                ContentKind.WIKILINKS: utilities.json_dumps(wikilinks),
            },
        )
        await pipe.execute()


async def set_weapon(
    redis_client: Redis,
    key: str,
    *,
    content: t.Sequence[disnake.Embed],
    wikilinks: api_types.WikiLinkDict,
    weapon: models.Weapon,
):
    async with ExpirePipeline.from_redis_client(redis_client) as pipe:
        pipe.hset(
            key,
            mapping={
                ContentKind.CATEGORY: constants.RequestCategory.WEAPONS,
                ContentKind.CONTENT: dump_content(content),
                ContentKind.WIKILINKS: utilities.json_dumps(wikilinks),
                ContentKind.STATS: dump_stats(weapon.stats),
                ContentKind.MIN_RARITY: str(weapon.rarity.value),
                ContentKind.MAX_RARITY: str(weapon.max_rarity.value),
            },
        )
        await pipe.execute()


def parse_stats(stats_json: str) -> t.Sequence[models.WeaponStats]:
    return pydantic.parse_raw_as(t.List[models.WeaponStats], stats_json)


async def get_stats(redis_client: Redis, key: str) -> t.Sequence[models.WeaponStats]:
    async with ExpirePipeline.from_redis_client(redis_client) as pipe:
        pipe.hget(key, ContentKind.STATS)
        raw_stats, _ = await pipe.execute()

    if not raw_stats:
        raise CacheKeyError(ContentKind.STATS, key)

    return parse_stats(raw_stats)


async def get_rarities(redis_client: Redis, key: str):
    async with ExpirePipeline.from_redis_client(redis_client) as pipe:
        pipe.hmget(key, ContentKind.MIN_RARITY)
        (raw_min_rarity, raw_max_rarity), *_ = await pipe.execute()

    if not raw_min_rarity or not raw_max_rarity:
        raise CacheKeyError(f"{ContentKind.MIN_RARITY} and {ContentKind.MAX_RARITY}", key)

    return int(raw_min_rarity), int(raw_max_rarity)


def parse_content(embed_json: str) -> t.List[utilities.FormattableEmbed]:
    return list(map(utilities.FormattableEmbed.from_dict, utilities.json_loads(embed_json)))


async def get_content(redis_client: Redis, key: str):
    async with ExpirePipeline.from_redis_client(redis_client) as pipe:
        pipe.hget(key, ContentKind.CONTENT)
        raw_content, _ = await pipe.execute()

    if not raw_content:
        raise CacheKeyError(ContentKind.CONTENT, key)

    return parse_content(raw_content)


def parse_wikilinks(wikilink_json: str) -> api_types.WikiLinkDict:
    return utilities.json_loads(wikilink_json)


async def get_wikilinks(redis_client: Redis, key: str) -> api_types.WikiLinkDict:
    async with ExpirePipeline.from_redis_client(redis_client) as pipe:
        pipe.hget(key, ContentKind.WIKILINKS)
        raw_wikilinks, _ = await pipe.execute()

    if not raw_wikilinks:
        raise CacheKeyError(ContentKind.WIKILINKS, key)

    return parse_wikilinks(raw_wikilinks)

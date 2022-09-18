from __future__ import annotations

import asyncio
import logging
import typing as t

import aiohttp
import redis.asyncio
import sqlalchemy
import uvloop
from disnake.ext import commands

from . import bot, constants, database, log

log.setup()
LOGGER = logging.getLogger(__name__)


async def create_client_session():
    session = aiohttp.ClientSession()
    ...  # logging?
    return session


def create_redis_session(use_fakeredis: bool) -> redis.asyncio.Redis[t.Any]:
    url = constants.RedisConfig.URL
    if use_fakeredis:
        import fakeredis.aioredis

        session = fakeredis.aioredis.FakeRedis.from_url(url, decode_responses=True)
    else:
        connection_pool = redis.asyncio.BlockingConnectionPool.from_url(url, decode_responses=True)
        session: redis.asyncio.Redis[t.Any] = redis.asyncio.Redis(connection_pool=connection_pool)

    LOGGER.debug(f"Started redis session at {url}")
    return session


@commands.is_owner()
@commands.command(name="reload", aliases=["r"])
async def reload_(
    ctx: commands.Context[bot.Maid_in_Abyss], plugin: str = "exts.mihoyo.wiki.plugin"
):
    ctx.bot.reload_extension(plugin)
    await ctx.send(f"Successfully reloaded plugin {plugin}!")


async def main():
    maid_in_abyss = bot.Maid_in_Abyss(
        commands.when_mentioned,
        redis=create_redis_session(constants.RedisConfig.USE_FAKEREDIS),
        database=database.meta.database,
        session=await create_client_session(),
    )

    database.meta.metadata.create_all(sqlalchemy.create_engine(constants.DBConfig.URL))
    await maid_in_abyss.database.connect()

    maid_in_abyss.add_command(reload_)
    maid_in_abyss.load_extension(".exts.mihoyo.wiki.plugin", package="maid_in_abyss")
    maid_in_abyss.load_extension(".exts.meta.eval", package="maid_in_abyss")
    maid_in_abyss.load_extension(".exts.meta.logging", package="maid_in_abyss")
    maid_in_abyss.load_extension(".exts.meta.delete", package="maid_in_abyss")

    await maid_in_abyss.start(constants.BotConfig.TOKEN)


if __name__ == "__main__":
    uvloop.install()
    asyncio.run(main())

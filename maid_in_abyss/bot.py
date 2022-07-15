from __future__ import annotations

import typing as t

import aiohttp
import databases
import redis.asyncio
from disnake.ext import commands

from utilities import plugin


class Maid_in_Abyss(commands.Bot):
    def __init__(
        self,
        command_prefix: t.Callable[..., t.List[str]] = commands.when_mentioned,
        *,
        redis: redis.asyncio.Redis[t.Any],
        database: databases.Database,
        session: aiohttp.ClientSession,
        **kwargs: t.Any,
    ):
        super().__init__(command_prefix, **kwargs)
        self.redis = redis
        self.database = database
        self.default_session = session

    async def load_plugin(self, plugin: plugin.Plugin) -> None:
        await plugin.load(self)

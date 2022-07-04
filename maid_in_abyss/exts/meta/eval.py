import ast
import asyncio
import enum
import inspect
import io
import logging
import re
import traceback
import aiohttp
import typing as t

import databases
import disnake
from disnake.ext import commands

import bot
import utilities

LOGGER = logging.getLogger(__name__)


_T_contra = t.TypeVar("_T_contra", contravariant=True)

class SupportsWrite(t.Protocol[_T_contra]):
    def write(self, __s: _T_contra) -> object: ...


class AllowedLang(str, enum.Enum):
    PYTHON = "py"
    POSTGRES = "postgres"


CODEBLOCK_PATTERN = re.compile(
    fr"```(?P<lang>{'|'.join(AllowedLang)})\s*\n(?P<code>.*?)\n?```",
    flags=re.DOTALL | re.MULTILINE
)
SELECT_QUERY_PATTERN = re.compile(r"\s*SELECT", flags=re.IGNORECASE)


plugin = utilities.Plugin.with_metadata(
    name="eval",
    category="meta",
)


def _make_print_proxy(file_proxy: SupportsWrite[str]):
    def _proxied_print(
        *values: object,
        sep: t.Optional[str] = ...,
        end: t.Optional[str] = ...,
        file: t.Optional[SupportsWrite[str]] = ...
    ):
        print(
            *values,
            sep=" " if sep is Ellipsis else sep,
            end="\n" if end is Ellipsis else end,
            file=file_proxy if file is Ellipsis else file,
        )
    return _proxied_print


async def _evaluate_py(code: str, namespace: t.Dict[str, t.Any]) -> str:
    out = io.StringIO()

    try:
        compiled = compile(code, "__eval__", "exec", flags=ast.PyCF_ALLOW_TOP_LEVEL_AWAIT)
        evaluated = eval(compiled, namespace | {"print": _make_print_proxy(out)})
        if compiled.co_flags & inspect.CO_COROUTINE:
            await evaluated

    except Exception:
        traceback.print_exc(file=out)

    return out.getvalue()


async def _evaluate_postgres(query: str, database: databases.Database) -> str:
    is_select_query = SELECT_QUERY_PATTERN.match(query)
    try:
        if is_select_query:
            return "\n".join(
                repr(record._mapping)  # pyright: ignore[reportUnknownArgumentType]
                for record in await database.fetch_all(query)
            )
        
        return str(await database.execute(query))

    except Exception:
        return traceback.format_exc()


def _create_namespace(ctx: commands.Context[bot.Maid_in_Abyss]) -> t.Dict[str, t.Any]:
    return {
        # Items...
        "bot": ctx.bot,
        "ctx": ctx,
        "message": ctx.message,
        "author": ctx.author,
        "channel": ctx.channel,
        "guild": ctx.guild,
        "me": ctx.me,
        "db": ctx.bot.database,
        "redis": ctx.bot.redis,
        "session": ctx.bot.default_session,
        # Modules...
        "asyncio": asyncio,
        "aiohttp": aiohttp,
        "disnake": disnake,
        "commands": commands,
    }


@plugin.command("eval")
async def evaluate(ctx: commands.Context[bot.Maid_in_Abyss], *, input_: str):
    match = CODEBLOCK_PATTERN.search(input_)

    async with ctx.typing():
        if not match:
            out = await _evaluate_py(input_, _create_namespace(ctx))

        else:
            code_attrs = match.groupdict()
            lang = AllowedLang(code_attrs["lang"])

            if lang is AllowedLang.PYTHON:
                out = await _evaluate_py(code_attrs["code"], _create_namespace(ctx))

            else: 
                out = await _evaluate_postgres(code_attrs["code"], ctx.bot.database)

    if not out:
        await ctx.reply("```\nNo output.```")
        return

    if len(out) > 1992:
        out = out[:1989] + "..."
    out = f"```\n{out}\n```"

    await ctx.reply(out)


setup, teardown = plugin.create_extension_handlers()
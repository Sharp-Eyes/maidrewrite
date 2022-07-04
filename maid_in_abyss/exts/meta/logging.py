import logging
import typing as t

import bot
import disnake
import utilities
from disnake.ext import commands

LOGGER = logging.getLogger(__name__)


plugin = utilities.Plugin.with_metadata(
    name="logging",
    category="meta",
)


@plugin.listener()
async def on_command(ctx: commands.Context[bot.Maid_in_Abyss]) -> None:
    """Log context command invocation."""
    command = t.cast(commands.Command[t.Any, t.Any, t.Any], ctx.command)
    lines = ctx.message.content.split("\n")

    LOGGER.info(
        "command {command!s} {author!s} ({author.id}) in {channel!s} ({channel.id}): {content}".format(
            author=ctx.author,
            channel=ctx.channel,
            command=command,
            content=lines[0] + (" ..." if len(lines) > 1 else ""),
        )
    )


@plugin.listener()
async def on_command_completion(ctx: commands.Context[bot.Maid_in_Abyss]) -> None:
    """Log a successful context command completion."""
    command = t.cast(commands.Command[t.Any, t.Any, t.Any], ctx.command)
    LOGGER.info(
        "command {command!s} by {author} ({author.id}) has completed!".format(
            command=command,
            author=ctx.author,
        )
    )


@commands.Cog.listener()
async def on_slash_command(inter: disnake.ApplicationCommandInteraction) -> None:
    """Log slash command invocation."""
    spl = str(inter.filled_options).replace("\n", " ")
    spl = spl.split("\n")

    if inter.application_command is disnake.utils.MISSING:
        return

    LOGGER.info(
        "Slash command `{command!s}` by {author!s} ({author.id}) in {channel!s} ({channel.id}): {content}".format(  # noqa: E501
            author=inter.author,
            channel=inter.channel,
            command=inter.application_command.qualified_name,
            content=spl[0] + (" ..." if len(spl) > 1 else ""),
        )
    )


@commands.Cog.listener()
async def on_slash_command_completion(inter: disnake.ApplicationCommandInteraction) -> None:
    """Log a successful slash command completion."""
    LOGGER.info(
        "slash command `{command}` by {author} has completed!".format(
            command=inter.application_command.qualified_name,
            author=inter.author,
        )
    )


setup, teardown = plugin.create_extension_handlers()

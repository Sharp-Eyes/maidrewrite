import typing as t

import disnake
import genshin as hoyo
from disnake.ext import commands, components

import bot


class HoyolabInterface(commands.Cog):

    def __init__(self, bot_: bot.Maid_in_Abyss):
        self.bot = bot_

    @commands.slash_command()
    async def hoyolab(self, inter: disnake.CommandInteraction):
        ...

    @hoyolab.sub_command()
    async def auth(): ...


def setup(bot_: bot.Maid_in_Abyss):
    bot_.add_cog(HoyolabInterface(bot_))
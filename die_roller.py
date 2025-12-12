import re

import requests

from pathlib import Path

dices_folder = Path.cwd().resolve() / "dices"


import discord
from discord.ext import commands

URL = "https://www.random.org/integers/?num=1&min=1&max=6&col=5&base=10&format=plain"

embed = discord.Embed(
        color=discord.Colour.red()
    )


class DiceRoller(commands.Cog):
    def __init__(self, bot):
        self.bot = bot


    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot:
            return
        
        if message.content.lower() == "rolar":
            value = roll_die()

            file = discord.File(f"{dices_folder}/dice_{value}.gif", filename=f"dice_{value}.gif")
            embed.set_image(url=f"attachment://dice_{value}.gif")
            await message.reply(file=file, embed=embed) 


def roll_die() -> int:

    number = requests.get(URL)
    return int(number.text)


def setup(bot):
    bot.add_cog(DiceRoller(bot))
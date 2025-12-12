import discord
from discord.ext import commands

from dotenv import load_dotenv
import os

load_dotenv()

intents = discord.Intents.default()
intents.members = True
intents.message_content = (
    True  # < This may give you `read-only` warning, just ignore it.
)

class rpgBot(commands.Bot):
    async def on_ready(self):
        print('Logged in as')
        print(self.user.name)

bot = rpgBot(command_prefix="!", intents=intents, default_command_contexts={discord.InteractionContextType.guild}, help_command=None) # the bot can only execute commands in the guild and not in dm

bot.load_extension('music')
bot.load_extension('die_roller')

bot.run(os.getenv("TOKEN"))
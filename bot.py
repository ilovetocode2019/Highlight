import discord
from discord.ext import commands

import json
import asyncpg
import logging

logger = logging.getLogger("discord")
logger.setLevel(logging.INFO)

logging.basicConfig(

    level = logging.INFO,
    format = "(%(asctime)s) %(levelname)s %(message)s",
    datefmt="%m/%d/%y - %H:%M:%S %Z" 
)

def get_prefix(client, msg):
    return commands.when_mentioned(client, msg)

class HighlightBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix=get_prefix, intents=discord.Intents.all())

        with open("config.json", "r") as f:
            self.config = json.load(f)
        
        self.cogs_to_add = ["cogs.meta", "cogs.highlight", "cogs.events"]

        self.loop.create_task(self.load_cogs())
        self.loop.create_task(self.prepare_bot())

    async def load_cogs(self):
        bot.remove_command("help")

        self.load_extension("debug_cog")
        self.get_command("debug").hidden = True

        for cog in self.cogs_to_add:
            self.load_extension(cog)

    async def prepare_bot(self):
        self.db = await asyncpg.create_pool(self.config["sql"])
        
        await self.db.execute('''
            CREATE TABLE IF NOT EXISTS words(
                userid bigint,
                guildid bigint,
                word text
            )
        ''')

        await self.db.execute('''
           CREATE TABLE IF NOT EXISTS blocks(
               userid bigint,
               blockedid bigint
           )
        ''')

        await self.db.execute('''
            CREATE TABLE IF NOT EXISTS settings(
                userid bigint,
                disabled bool,
                timezone int
            )
        ''')

        await self.db.execute('''
            CREATE TABLE IF NOT EXISTS todo(
                userid bigint,
                time int,
                event text
            )
        ''')

        self.cached_words = []
        for row in await self.db.fetch("SELECT word FROM words"):
            if row[0] not in self.cached_words:
                self.cached_words.append(row[0])
        
    async def on_ready(self):
        logging.info(f"Logged in as {self.user.name} - {self.user.id}")
    def run(self):
        super().run(self.config["token"])
        

bot = HighlightBot()
bot.run()

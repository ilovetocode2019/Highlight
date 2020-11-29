import discord
from discord.ext import commands

import json
import asyncpg
import logging
import datetime
import aiohttp

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
        intents = discord.Intents.all()
        intents.presences = False
        super().__init__(command_prefix=get_prefix, description="I DM you if I find one of your words in the chat", intents=intents)

        with open("config.json", "r") as f:
            self.config = json.load(f)
        
        self.cogs_to_add = ["cogs.meta", "cogs.admin", "cogs.highlight"]
        self.startup_time = datetime.datetime.utcnow()

        self.loop.create_task(self.load_cogs())
        self.loop.create_task(self.prepare_bot())

    async def load_cogs(self):
        bot.remove_command("help")

        self.load_extension("jishaku")
        self.get_command("jishaku")

        for cog in self.cogs_to_add:
            self.load_extension(cog)

    async def prepare_bot(self):
        async def init(conn):
            await conn.set_type_codec(
                "jsonb",
                schema="pg_catalog",
                encoder=json.dumps,
                decoder=json.loads,
                format="text",
            )

        self.db = await asyncpg.create_pool(self.config["sql"], init=init)
        self.session = aiohttp.ClientSession()

        query = """CREATE TABLE IF NOT EXISTS words (
                   userid BIGINT,
                   guildid BIGINT,
                   word TEXT
                   );

                   CREATE TABLE IF NOT EXISTS settings (
                   userid BIGINT PRIMARY KEY,
                   disabled BOOL,
                   timezone INT,
                   blocked_users BIGINT ARRAY,
                   blocked_channels BIGINT ARRAY
                   );

                """
        await self.db.execute(query)

        self.cached_words = []
        for row in await self.db.fetch("SELECT word FROM words"):
            if row[0] not in self.cached_words:
                self.cached_words.append(row[0])

    async def on_ready(self):
        logging.info(f"Logged in as {self.user.name} - {self.user.id}")
        self.console = self.get_channel(self.config["console"])

    def run(self):
        super().run(self.config["token"])
        

bot = HighlightBot()
bot.run()

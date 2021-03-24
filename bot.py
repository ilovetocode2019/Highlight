import discord
from discord.ext import commands

import aiohttp
import asyncpg
import datetime
import json
import logging

log = logging.getLogger("highlight")
logging.basicConfig(level=logging.INFO, format="(%(asctime)s) %(levelname)s %(message)s", datefmt="%m/%d/%y - %H:%M:%S %Z")

extensions = [
    "cogs.admin",
    "cogs.highlight",
    "cogs.meta",
    "cogs.timers"
]

class HighlightBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents(guilds=True, messages=True, reactions=True)
        super().__init__(command_prefix=commands.when_mentioned, description="I DM you if I find one of your words in the chat", intents=intents)

        self.uptime = datetime.datetime.utcnow()
        self.support_server_link = "https://discord.gg/eHxvStNJb7"

        self.load_extension("jishaku")
        self.get_cog("Jishaku").hidden = True

        for extension in extensions:
            try:
                self.load_extension(extension)
            except Exception as exc:
                log.error("Couldn't load extension %s", extension, exc_info=exc)

    async def create_pool(self):
        async def init(connection): await connection.set_type_codec("jsonb", schema="pg_catalog", encoder=json.dumps, decoder=json.loads, format="text")
        self.db = await asyncpg.create_pool(self.config.database_uri, init=init)

        with open("schema.sql") as file:
            schema = file.read()
            await self.db.execute(schema)

        query = """SELECT *
                   FROM words;
                """
        words = await self.db.fetch(query)
        self.cached_words = [word["word"] for word in set(words)]

    async def on_connect(self):
        if not hasattr(self, "session"):
            self.session = aiohttp.ClientSession()

        if not hasattr(self, "db"):
            await self.create_pool()

    async def on_ready(self):
        log.info(f"Logged in as {self.user.name} - {self.user.id}")
        self.console = self.get_channel(self.config.console)

    def run(self):
        super().run(self.config.token)

    @discord.utils.cached_property
    def config(self):
        return __import__("config")

bot = HighlightBot()
bot.run()

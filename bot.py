import discord
from discord.ext import commands

import aiohttp
import datetime
import json
import logging

import asyncpg
import yaml

log = logging.getLogger("highlight")
logging.basicConfig(
    level=logging.INFO,
    format="(%(asctime)s) %(levelname)s %(message)s",
    datefmt="%m/%d/%y - %H:%M:%S %Z"
)

extensions = [
    "cogs.admin",
    "cogs.highlight",
    "cogs.meta",
    "cogs.timers"
]


class OptionMissing(Exception):
    pass


class InvalidOption(Exception):
    pass


class HighlightBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents(guilds=True, members=True, messages=True, reactions=True, guild_typing=True, message_content=True)
        allowed_mentions = discord.AllowedMentions(everyone=False, users=False, roles=False)
        super().__init__(command_prefix=commands.when_mentioned, description="I DM you if I find one of your words in the chat", intents=intents, allowed_mentions=allowed_mentions, case_insensitive=True)

        self.uptime = datetime.datetime.utcnow()
        self.support_server_invite = "https://discord.gg/vxeHZbd3Zf"
        self.config = self.load_config()

    async def setup_hook(self):
        log.info("Loading Jishaku")
        await self.load_extension("jishaku")

        log.info("Loading extensions")
        for extension in extensions:
            try:
                await self.load_extension(extension)
            except Exception as exc:
                log.error("Couldn't load extension %s", extension, exc_info=exc)

        log.info("Connecting with database")
        async def init(connection): await connection.set_type_codec("jsonb", schema="pg_catalog", encoder=json.dumps, decoder=json.loads, format="text")
        self.db = await asyncpg.create_pool(self.config["database-uri"], init=init)

        with open("schema.sql") as file:
            schema = file.read()
            await self.db.execute(schema)

        log.info("Preparing highlight word cache")
        query = """SELECT *
                   FROM words;
                """
        cached_words = await self.db.fetch(query)
        self.cached_words = [dict(cached_word) for cached_word in cached_words]

    def load_config(self):
        with open("config.yml") as file:
            config = yaml.safe_load(file)

        if "token" not in config:
            raise OptionMissing("A Discord API token is required to run the bot, but was not found in config.yml")
        elif "database-uri" not in config:
            raise OptionMissing("A database URI is required for functionality, but was not found in config.yml")

        if "console" not in config:
            config["console"] = None

        if not isinstance(config["token"], str):
            raise InvalidOption("The Discord API token must be a string")
        elif not isinstance(config["database-uri"], str):
            raise InvalidOption("The database URI must be a string")

        return config

    async def on_ready(self):
        log.info(f"Logged in as {self.user.name} - {self.user.id}")
        self.console = self.get_channel(self.config["console"])

    async def close(self):
        await super().close()
        await self.db.close()

    def run(self):
        super().run(self.config["token"])


bot = HighlightBot()
bot.run()

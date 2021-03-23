import discord
from discord.ext import commands

import json
import asyncpg
import logging
import datetime
import aiohttp

import config

log = logging.getLogger("highlight")
logging.basicConfig(level=logging.INFO, format="(%(asctime)s) %(levelname)s %(message)s", datefmt="%m/%d/%y - %H:%M:%S %Z")

def get_prefix(client, message):
    return commands.when_mentioned(client, message)

class HighlightBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents(guilds=True, messages=True, reactions=True)
        super().__init__(command_prefix=get_prefix, description="I DM you if I find one of your words in the chat", intents=intents)
        self.loop.create_task(self.prepare_bot())

        log.info("Loading extensions")
        self.cogs_to_add = ["cogs.meta", "cogs.admin", "cogs.highlight", "cogs.timers"]
        self.load_extension("jishaku")
        for cog in self.cogs_to_add:
            self.load_extension(cog)

        self.startup_time = datetime.datetime.utcnow()
        self.support_server_link = "https://discord.gg/eHxvStNJb7"

    async def prepare_bot(self):
        log.info("Creating aiohttp session")
        self.session = aiohttp.ClientSession()

        log.info("Connecting to database")

        async def init(conn):
            await conn.set_type_codec("jsonb", schema="pg_catalog", encoder=json.dumps, decoder=json.loads, format="text")
        self.db = await asyncpg.create_pool(config.database_uri, init=init)

        log.info("Initiating database")

        query = """CREATE TABLE IF NOT EXISTS words (
                   user_id BIGINT,
                   guild_id BIGINT,
                   word TEXT
                   );

                   CREATE TABLE IF NOT EXISTS settings (
                   user_id BIGINT PRIMARY KEY,
                   disabled BOOL,
                   timezone INT,
                   blocked_users BIGINT ARRAY,
                   blocked_channels BIGINT ARRAY
                   );

                   CREATE TABLE IF NOT EXISTS timers (
                   id SERIAL PRIMARY KEY,
                   user_id BIGINT,
                   event TEXT,
                   time TIMESTAMP,
                   extra jsonb DEFAULT ('{}'::jsonb),
                   created_at TIMESTAMP DEFAULT (now() at time zone 'utc')
                   );

                   CREATE TABLE IF NOT EXISTS highlights (
                   guild_id BIGINT,
                   channel_id BIGINT,
                   message_id BIGINT,
                   author_id BIGINT,
                   user_id BIGINT,
                   word TEXT,
                   invoked_at TEXT
                   );

                   CREATE UNIQUE INDEX IF NOT EXISTS unique_words_index ON words (user_id, guild_id, word);
                """
        await self.db.execute(query)

        log.info("Preparing highlight word cached")

        query = """SELECT *
                   FROM words;
                """
        words = await self.db.fetch(query)

        cached_words = []
        for word in words:
            if word["word"] not in cached_words:
                cached_words.append(word["word"])

        self.cached_words = cached_words

    async def on_ready(self):
        log.info(f"Logged in as {self.user.name} - {self.user.id}")
        self.console = self.get_channel(config.console)

    def run(self):
        super().run(config.token)
        
bot = HighlightBot()
bot.run()

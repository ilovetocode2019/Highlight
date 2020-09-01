import discord
from discord.ext import commands
from discord.ext import tasks

import datetime
import asyncio

class Events(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.events_loop.start()

    def cog_unload(self):
        self.events_loop.cancel()

    async def dispatch_todo(self, wait, row):
        await asyncio.sleep(wait)

        if row[2] == "enable":
            await self.bot.db.execute("DELETE FROM todo WHERE todo.userid=$1 AND Todo.event=$2", row[0], "enable")
            await self.bot.db.execute("UPDATE settings SET disabled=$1 WHERE settings.userid=$2", False, row[0])

    @tasks.loop(minutes=1)
    async def events_loop(self):
        now = datetime.datetime.timestamp(datetime.datetime.now())
        now = int(now)

        todo = await self.bot.db.fetch("SELECT * FROM todo")

        for x in todo:
            if x[1]-now < 60:
                await self.dispatch_todo(x[1]-now, x)

    @events_loop.before_loop
    async def before_events_loop(self):
        await self.bot.wait_until_ready()

def setup(bot):
    bot.add_cog(Events(bot))

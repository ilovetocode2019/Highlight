import discord
from discord.ext import commands

import datetime
import dateparser
import humanize
import asyncio
import re

class Highlight(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener("on_message")
    async def on_message(self, message):
        if message.author.bot:
            return

        # Loop through the trigger words and run send_highlight if the tigger word is in the message
        sent = []
        for word in self.bot.cached_words:
            if self.word_in_message(word, message.content.lower()):
                rows = await self.bot.db.fetch("SELECT * FROM words WHERE words.word=$1 AND words.guildid=$2", word, message.guild.id)

                blocks = await self.bot.db.fetch("SELECT userid FROM blocks WHERE blocks.blockedid=$1", message.author.id)
                for row in rows:
                    is_blocked = False
                    for block in blocks:
                        if block[0] == row[0]:
                            is_blocked = True
                    if not is_blocked and row[0] not in sent:
                        self.bot.loop.create_task(self.send_highlight(message, row))
                        sent.append(row[0])

    async def send_highlight(self, message, row):
        # Select all the users who have blocked the message sender
        user = message.guild.get_member(int(row[0]))

        # Get the settings for the user
        settings_row = await self.bot.db.fetchrow("SELECT * FROM settings WHERE settings.userid=$1", user.id)

        if not settings_row:
            settings_row = [str(user.id), False, 0]

        # Make sure the user is not blocked
        # Make sure the user has not disabled highlight
        # Make sure the user to be highlighted can view the channel
        # Make sure the user to be highlighted is not the sender
        if not settings_row[1] and user.id in [member.id for member in message.channel.members] and user != message.author:

            utc = ""
            if settings_row[2] == 0:
                utc = " UTC"

            # Create the embed for the highlight
            em = discord.Embed(timestamp=datetime.datetime.now(), description=f"You got highlighted in {message.channel.mention}\n\n")
            em.set_author(name=message.author.display_name, icon_url=message.author.avatar_url)
            em.description += "\n\n".join([f"> {x.author} at {(x.created_at+datetime.timedelta(hours=settings_row[2])).strftime(f'%H:%M:%S{utc}')}: {x.content}" for x in reversed((await message.channel.history(limit=3).flatten())[1:])])

            # Get the position of the word in the message
            span = re.search(row[2], message.content.lower()).span()

            msg = discord.utils.escape_markdown(message.content[:span[0]])
            msg += f"**{discord.utils.escape_markdown(message.content[span[0]:span[1]])}**"
            msg += discord.utils.escape_markdown(message.content[span[1]:])

            # Add the trigger message to the embed
            em.description += f"\n\n> {message.author} at {(message.created_at+datetime.timedelta(hours=settings_row[2])).strftime(f'%H:%M:%S{utc}')}: {msg}"

            def check(ms):
                return ms.channel.id == message.channel.id

            try:
                # Wait for 10 seconds to see if any new messages should be added to the embed
                ms = await self.bot.wait_for("message", check=check, timeout=10)

                # To not trigger the highlight if the user replys to the tigger message
                if ms.author.id == user.id:
                    return

                # Add the new message to the embed
                em.description += f"\n\n> {ms.author} at {(ms.created_at+datetime.timedelta(hours=settings_row[2])).strftime(f'%H:%M:%S{utc}')}: {ms.content}"

            except asyncio.TimeoutError:
                pass

            em.add_field(name="Jump", value=f"[Click]({message.jump_url})")

            # Send the message
            await user.send(embed=em)

    def word_in_message(self, word, message):
        # Get the word in the message
        match = re.search(word, message)

        # Return False if the word is not in the message
        if not match:
            return False

        span = match.span()

        start = span[0]-1
        end = span[1]

        if start >= 0:
            # If the charecter before the word is not a space, return False
            if message[start] != " ":
                return False

        return True

    @commands.guild_only()
    @commands.command(name="add", description="Add a highlight word")
    async def add(self, ctx, *, word):
        word = word.lower()

        query = """SELECT COUNT(*)
                   FROM words
                   WHERE words.userid=$1 AND words.guildid=$2 AND words.word=$3;
                """
        if (await self.bot.db.fetchrow(query, ctx.author.id, ctx.guild.id, word))["count"]:
            await ctx.send("❌ You already have that word", delete_after=10)
            try:
                await ctx.message.delete()
            except:
                pass

            return

        query = """INSERT INTO words (userid, guildid, word)
                   VALUES ($1, $2, $3);
                """
        await self.bot.db.execute(query, ctx.author.id, ctx.guild.id, word)

        if word not in self.bot.cached_words:
            self.bot.cached_words.append(word)
        
        await ctx.send("✅ Words updated", delete_after=10)
        try:
           await ctx.message.delete()
        except:
            pass

    @commands.guild_only()
    @commands.command(name="remove", description="Remove a highlight word")
    async def remove(self, ctx, *, word):
        query = """DELETE FROM words
                   WHERE words.userid=$1 AND words.guildid=$2 AND words.word=$3;
                """
        result = await self.bot.db.execute(query, ctx.author.id, ctx.guild.id, word)

        if result == "DELETE 0":
            await ctx.send("❌ This word is not registered", delete_after=10)
            try:
                await ctx.message.delete()
            except discord.HTTPException:
                pass
            return

        await ctx.send("✅ Words updated", delete_after=10)
        try:
           await ctx.message.delete()
        except:
            pass

    @commands.guild_only()
    @commands.command(name="clear", description="Clear your highlight list")
    async def clear(self, ctx):
        query = """DELETE FROM words
                   WHERE words.userid=$1 AND words.guildid=$2;
                """
        await self.bot.db.execute(query, ctx.author.id, ctx.guild.id)

        await ctx.send("✅ Your highlight list has been cleared", delete_after=5)
        try:
            await ctx.message.delete()
        except:
            pass

    @commands.guild_only()
    @commands.command(name="show", description="View your words for the current server")
    async def show(self, ctx):
        query = """SELECT * FROM words
                   WHERE words.userid=$1 AND words.guildid=$2;
                """
        rows = await self.bot.db.fetch(query, ctx.author.id, ctx.guild.id)

        if not rows:
            await ctx.send("❌ No words for this guild", delete_after=15)
            try:
                await ctx.message.delete()
            except:
                pass

            return

        em = discord.Embed()
        em.set_author(name=ctx.author.display_name, icon_url=ctx.author.avatar_url)

        em.description = ""
        for row in rows:
            em.description += f"\n{row['word']}"

        await ctx.send(embed=em, delete_after=15)
        try:
           await ctx.message.delete()
        except:
            pass

    @commands.command(name="block", description="Block a user from highlighting you")
    async def block(self, ctx, *, user: discord.Member):
        query = """SELECT COUNT(*)
                   FROM blocks
                   WHERE blocks.userid=$1
                   AND blocks.blockedid=$2;
                """
        if (await self.bot.db.fetchrow(query, ctx.author.id, user.id))["count"] != 0:
            await ctx.send("❌ This user is already blocked", delete_after=10)

            try:
                await ctx.message.delete()
            except discord.HTTPException:
                pass

            return

        query = """INSERT INTO blocks (userid, blockedid)
                   VALUES ($1, $2);
                """
        await self.bot.db.execute(query, ctx.author.id, user.id)

        await ctx.send(f"🚫 Blocked {user.display_name}", delete_after=10)
        try:
            await ctx.message.delete()
        except discord.HTTPException:
            pass

    @commands.command(name="unblock", description="Unblock a user from highlighting you")
    async def unblock(self, ctx, *, user: discord.Member):
        query = """DELETE FROM blocks
                   WHERE blocks.userid=$1 AND blocks.blockedid=$2;
                """
        result = await self.bot.db.execute(query, ctx.author.id, user.id)

        if result == "DELETE 0":
            await ctx.send("❌ This user is not blocked", delete_after=10)
            try:
                await ctx.message.delete()
            except:
                pass

            return

        await ctx.send(f"✅ Unblocked {user.display_name}", delete_after=10)  
        try:
            await ctx.message.delete()
        except:
            pass

    @commands.command(name="blocked", description="View your blocked list")
    async def blocked(self, ctx):
        query = """SELECT *
                   FROM blocks
                   WHERE blocks.userid=$1;
                """
        rows = await self.bot.db.fetch(query, ctx.author.id)

        if not rows:
            await ctx.send("❌ You have no blocked users", delete_after=10)
            try:
                await ctx.message.delete()
            except:
                pass

            return

        em = discord.Embed()
        em.set_author(name=ctx.author.display_name, icon_url=ctx.author.avatar_url)

        em.description = ""
        for row in rows:
            user = self.bot.get_user(int(row["blockedid"]))
            em.description += f"\n{user.name}"

        await ctx.send(embed=em, delete_after=15)
        try:
            await ctx.message.delete()
        except:
            pass

    @commands.command(name="enable", description="Enable highlight")
    async def enable(self, ctx):
        query = """INSERT INTO settings (userid, disabled, timezone)
                   VALUES ($1, $2, $3)
                   ON CONFLICT (userid)
                   DO UPDATE SET disabled=$2;
                """
        await self.bot.db.execute(query, ctx.author.id, False, 0)

        await ctx.send("✅ Highlight has been enabled", delete_after=10)

        try:
            await ctx.message.delete()
        except:
            pass

    @commands.command(name="disable", description="Disable highlight", aliases=["dnd"])
    async def disable(self, ctx):
        query = """INSERT INTO settings (userid, disabled, timezone)
                   VALUES ($1, $2, $3)
                   ON CONFLICT (userid)
                   DO UPDATE SET disabled=$2;
                """
        await self.bot.db.execute(query, ctx.author.id, True, 0)

        await ctx.send(f"✅ Highlight has been disabled", delete_after=10)

        try:
            await ctx.message.delete()
        except:
            pass

    @commands.command(name="timezone", description="Set your timezone")
    async def timezone(self, ctx, timezone: int):
        query = """INSERT INTO settings (userid, disabled, timezone)
                   VALUES ($1, $2, $3)
                   ON CONFLICT (userid)
                   DO UPDATE SET timezone=$3;
                """
        await self.bot.db.execute(query, ctx.author.id, False, timezone)

        await ctx.send("✅ Timezone saved", delete_after=10)
        try:
            await ctx.message.delete()
        except:
            pass

    @commands.command(name="settings", description="Display your settings")
    async def info(self, ctx):

        query = """SELECT *
                   FROM settings
                   WHERE settings.userid=$1;
                """
        settings = await self.bot.db.fetchrow(query, ctx.author.id)

        if not settings:
            await ctx.send("You have default settings")
            try:
                await ctx.message.delete()
            except:
                pass

            return

        em = discord.Embed()
        em.set_author(name=ctx.author.display_name, icon_url=ctx.author.avatar_url)

        if settings["disabled"]:
            em.description = "Highlight is currently disabled"

        em.add_field(name="Timezone", value=settings["timezone"])

        await ctx.send(embed=em, delete_after=15)
        try:
            await ctx.message.delete()
        except:
            pass

def setup(bot):
    bot.add_cog(Highlight(bot))

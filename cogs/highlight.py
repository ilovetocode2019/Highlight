import discord
from discord.ext import commands, menus

import datetime
import asyncio
import re
import typing

class Confirm(menus.Menu):
    def __init__(self, msg):
        super().__init__(timeout=30.0, delete_message_after=True)
        self.msg = msg
        self.result = None

    async def send_initial_message(self, ctx, channel):
        return await channel.send(self.msg)

    @menus.button('\N{WHITE HEAVY CHECK MARK}')
    async def do_confirm(self, payload):
        self.result = True
        self.stop()

    @menus.button('\N{CROSS MARK}')
    async def do_deny(self, payload):
        self.result = False
        self.stop()

    async def prompt(self, ctx):
        await self.start(ctx, wait=True)
        return self.result

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
                query = """SELECT *
                           FROM words
                           WHERE words.word=$1 AND words.guildid=$2;
                        """
                row = await self.bot.db.fetchrow(query, word, message.guild.id)

                if row["userid"] not in sent:
                    self.bot.loop.create_task(self.send_highlight(message, row))
                    sent.append(row[0])

    async def send_highlight(self, message, row):
        user = message.guild.get_member(int(row["userid"]))

        # Get the settings for the user
        query = """SELECT *
                   FROM settings
                   WHERE settings.userid=$1;
                """
        settings_row = await self.bot.db.fetchrow(query, user.id)

        if not settings_row:
            settings_row = {"userid": user.id, "disabled": False, "timezone": 0, "blocked_users": [], "blocked_channels": []}

        # Make sure the user to be highlighted has not disabled highlight
        # Make sure the user to be highlighted can view the channel
        # Make sure the user to be highlighted has not blocked the channel or sender
        # Make sure the user to be highlighted is not the sender
        if settings_row["disabled"]:
            return
        if user.id not in [member.id for member in message.channel.members]:
            return
        if message.channel.id in settings_row["blocked_channels"] or message.author.id in settings_row["blocked_users"]:
            return
        if user.id == message.author.id:
            return

        utc = ""
        if settings_row["timezone"] == 0:
            utc = " UTC"

        # Create the embed for the highlight
        em = discord.Embed(timestamp=datetime.datetime.now(), description=f"You got highlighted in {message.channel.mention}\n\n", color=discord.Color.blurple())
        em.set_author(name=message.author.display_name, icon_url=message.author.avatar_url)
        em.description += "\n\n".join([f"> {x.author} at {(x.created_at+datetime.timedelta(hours=settings_row[2])).strftime(f'%H:%M:%S{utc}')}: {x.content}" for x in reversed((await message.channel.history(limit=3).flatten())[1:])])

        # Get the position of the word in the message
        span = re.search(row["word"], message.content.lower()).span()

        msg = discord.utils.escape_markdown(message.content[:span[0]])
        msg += f"**{discord.utils.escape_markdown(message.content[span[0]:span[1]])}**"
        msg += discord.utils.escape_markdown(message.content[span[1]:])

        # Add the trigger message to the embed
        em.description += f"\n\n> {message.author} at {(message.created_at+datetime.timedelta(hours=settings_row['timezone'])).strftime(f'%H:%M:%S{utc}')}: {msg}"

        def check(ms):
            return ms.channel.id == message.channel.id

        try:
            # Wait for 10 seconds to see if any new messages should be added to the embed
            ms = await self.bot.wait_for("message", check=check, timeout=10)

            # To not trigger the highlight if the user replys to the tigger message
            if ms.author.id == user.id:
                return

            # Add the new message to the embed
            em.description += f"\n\n> {ms.author} at {(ms.created_at+datetime.timedelta(hours=settings_row['timezone'])).strftime(f'%H:%M:%S{utc}')}: {ms.content}"

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
        else:
            query = """INSERT INTO words (userid, guildid, word)
                    VALUES ($1, $2, $3);
                    """
            await self.bot.db.execute(query, ctx.author.id, ctx.guild.id, word)

            if word not in self.bot.cached_words:
                self.bot.cached_words.append(word)
            
            await ctx.send("✅ Words updated", delete_after=10)

        try:
           await ctx.message.delete()
        except discord.HTTPException:
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
        else:
            await ctx.send("✅ Words updated", delete_after=10)

        try:
           await ctx.message.delete()
        except discord.HTTPException:
            pass

    @commands.guild_only()
    @commands.command(name="clear", description="Clear your highlight list")
    async def clear(self, ctx):
        query = """DELETE FROM words
                   WHERE words.userid=$1 AND words.guildid=$2;
                """
        await self.bot.db.execute(query, ctx.author.id, ctx.guild.id)

        await ctx.send("✅ Your highlight list has been cleared", delete_after=10)
        try:
            await ctx.message.delete()
        except discord.HTTPException:
            pass

    @commands.guild_only()
    @commands.command(name="transfer", description="Transfer your words from another server", usage="<server id>", aliases=["import"])
    async def transfer(self, ctx, guild_id: int):
        query = """SELECT *
                   FROM words
                   WHERE words.userid=$1 AND (words.guildid=$2 OR words.guildid=$3);
                """
        words = await self.bot.db.fetch(query, ctx.author.id, guild_id, ctx.guild.id)

        to_transfer = []
        for word in words:
            if word["guildid"] == guild_id and word["word"] not in [x["word"] for x in words if x["guildid"] == ctx.guild.id]:
                to_transfer.append({"userid": ctx.author.id, "guildid": ctx.guild.id, "word": word["word"]})

        if not to_transfer:
            await ctx.send("❌ You have no words to transfer from this server", delete_after=10)
        else:
            query = """INSERT INTO words (userid, guildid, word)
                    SELECT x.userid, x.guildid, x.word
                    FROM jsonb_to_recordset($1::jsonb) AS
                    x(userid BIGINT, guildid BIGINT, word TEXT);
                    """

            await self.bot.db.execute(query, to_transfer)
            await ctx.send("✅ Your highlight words have been transferred to this server", delete_after=10)

        try:
            await ctx.message.delete()
        except discord.HTTPException:
            pass

    @commands.guild_only()
    @commands.command(name="show", description="View your words for the current server")
    async def show(self, ctx):
        query = """SELECT * FROM words
                   WHERE words.userid=$1 AND words.guildid=$2;
                """
        rows = await self.bot.db.fetch(query, ctx.author.id, ctx.guild.id)

        if not rows:
            await ctx.send("❌ No words for this server", delete_after=15)
        else:
            em = discord.Embed(title="Highlight Words", color=discord.Color.blurple())
            em.set_author(name=ctx.author.display_name, icon_url=ctx.author.avatar_url)

            em.description = ""
            for row in rows:
                em.description += f"\n{row['word']}"

            await ctx.send(embed=em, delete_after=15)

        try:
           await ctx.message.delete()
        except discord.HTTPException:
            pass

    @commands.command(name="block", description="Block a user or channel", usage="<user or channel>", aliases=["ignore", "mute"])
    async def block(self, ctx, *, user: typing.Union[discord.User, discord.TextChannel]):
        query = """SELECT *
                   FROM settings
                   WHERE settings.userid=$1;
                """
        settings = await self.bot.db.fetchrow(query, ctx.author.id)

        if isinstance(user, discord.User):
            if settings:
                if user.id in settings["blocked_users"]:
                    await ctx.send("❌ This user is already blocked", delete_after=10)
                else:
                    settings["blocked_users"].append(user.id)
                    query = """UPDATE settings
                               SET blocked_users=$1
                               WHERE settings.userid=$2;
                            """
                    await self.bot.db.execute(query, settings["blocked_users"], ctx.author.id)
                    await ctx.send(f"🚫 Blocked {user.display_name}", delete_after=10)
            else:
                query = """INSERT INTO settings (userid, disabled, timezone, blocked_users, blocked_channels)
                           VALUES ($1, $2, $3, $4, $5);
                        """
                await self.bot.db.execute(query, ctx.author.id, False, 0, [user.id], [])
        else:
            if settings:
                if user.id in settings["blocked_channels"]:
                    await ctx.send("❌ This channel is already blocked", delete_after=10)
                else:
                    settings["blocked_channels"].append(user.id)
                    query = """UPDATE settings
                               SET blocked_channels=$1
                               WHERE settings.userid=$2;
                            """
                    await self.bot.db.execute(query, settings["blocked_channels"], ctx.author.id)
                    await ctx.send(f"🚫 Blocked {user.mention}", delete_after=10)
            else:
                query = """INSERT INTO settings (userid, disabled, timezone, blocked_users, blocked_channels)
                           VALUES ($1, $2, $3, $4, $5);
                        """
                await self.bot.db.execute(query, ctx.author.id, False, 0, [], [user.ids])

        try:
            await ctx.message.delete()
        except discord.HTTPException:
            pass

    @commands.command(name="unblock", description="Unblock a user or channel", usage="<use or channel>", aliases=["unmute"])
    async def unblock(self, ctx, *, user: typing.Union[discord.User, discord.TextChannel]):
        query = """SELECT *
                   FROM settings
                   WHERE settings.userid=$1;
                """
        settings = await self.bot.db.fetchrow(query, ctx.author.id)

        if isinstance(user, discord.User):

            if settings:
                if user.id not in settings["blocked_users"]:
                    await ctx.send("❌ This user is not blocked", delete_after=10)
                else:
                    settings["blocked_users"].remove(user.id)
                    query = """UPDATE settings
                               SET blocked_users=$1
                               WHERE settings.userid=$2;
                            """
                    await self.bot.db.execute(query, settings["blocked_users"], ctx.author.id)
                    await ctx.send(f"✅ Unblocked {user.display_name}", delete_after=10)
            else:
                await ctx.send("❌ This user is not blocked", delete_after=10)

        else:

            if settings:
                if user.id not in settings["blocked_channels"]:
                    await ctx.send("❌ This channel is not blocked", delete_after=10)
                else:
                    settings["blocked_channels"].remove(user.id)
                    query = """UPDATE settings
                               SET blocked_channels=$1
                               WHERE settings.userid=$2;
                            """
                    await self.bot.db.execute(query, settings["blocked_channels"], ctx.author.id)
                    await ctx.send(f"✅ Unblocked {user.mention}", delete_after=10)
            else:
                await ctx.send("❌ This channel is not blocked")

        try:
            await ctx.message.delete()
        except discord.HTTPException:
            pass

    @commands.group(name="blocked", description="View your blocked list", invoke_without_command=True)
    async def blocked(self, ctx):
        query = """SELECT *
                   FROM settings
                   WHERE settings.userid=$1;
                """
        settings = await self.bot.db.fetchrow(query, ctx.author.id)

        if not settings or (not settings["blocked_channels"] and not settings["blocked_users"]):
            await ctx.send("❌ You have no channnels or users blocked", delete_after=10)
        else:
            em = discord.Embed(color=discord.Color.blurple())
            em.set_author(name=ctx.author.display_name, icon_url=ctx.author.avatar_url)

            users = []
            for user_id in settings["blocked_users"]:
                user = self.bot.get_user(user_id)
                users.append(user.mention if user else f"User with ID of {user_id}")
            if users:
                em.add_field(name="Blocked Users", value="\n".join(users))

            channels = []
            for channel_id in settings["blocked_channels"]:
                channel = self.bot.get_channel(channel_id)
                channels.append(channel.mention if channel else f"Channel with ID of {channel_id}")
            if channels:
                em.add_field(name="Blocked Channels", value="\n".join(channels))

            await ctx.send(embed=em, delete_after=15)
        try:
            await ctx.message.delete()
        except discord.HTTPException:
            pass

    @blocked.command(name="clear", description="Clear your blocked list")
    async def blocked_clear(self, ctx):
        result = await Confirm("Are you sure you want to do this? I will forget all your blocked users and channels").prompt(ctx)
        if result:
            query = """UPDATE settings
                       SET blocked_users=$1, blocked_channels=$2
                       WHERE settings.userid=$3;
                    """
            await self.bot.db.execute(query, [], [], ctx.author.id)

            await ctx.send("✅ Your blocked list has been cleared")

        try:
            await ctx.message.delete()
        except discord.HTTPException:
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
        except discord.HTTPException:
            pass

    @commands.command(name="disable", description="Disable highlight", aliases=["dnd"])
    async def disable(self, ctx):
        query = """INSERT INTO settings (userid, disabled, timezone, blocked_users, blocked_channels)
                   VALUES ($1, $2, $3, $4, $5)
                   ON CONFLICT (userid)
                   DO UPDATE SET disabled=$2;
                """
        await self.bot.db.execute(query, ctx.author.id, True, 0, [], [])

        await ctx.send(f"✅ Highlight has been disabled", delete_after=10)

        try:
            await ctx.message.delete()
        except discord.HTTPException:
            pass

    @commands.command(name="timezone", description="Set your timezone")
    async def timezone(self, ctx, timezone: int):
        query = """INSERT INTO settings (userid, disabled, timezone, blocked_users, blocked_channels)
                   VALUES ($1, $2, $3, $4, $5)
                   ON CONFLICT (userid)
                   DO UPDATE SET timezone=$3;
                """
        await self.bot.db.execute(query, ctx.author.id, False, timezone, [], [])

        await ctx.send("✅ Timezone saved", delete_after=10)
        try:
            await ctx.message.delete()
        except discord.HTTPException:
            pass

    @commands.command(name="settings", description="Display your settings")
    async def info(self, ctx):
        query = """SELECT *
                   FROM settings
                   WHERE settings.userid=$1;
                """
        settings = await self.bot.db.fetchrow(query, ctx.author.id)

        if not settings:
            await ctx.send("You have default settings", delete_after=15)
        else:
            em = discord.Embed(title="Highlight Settings", color=discord.Color.blurple())
            em.set_author(name=ctx.author.display_name, icon_url=ctx.author.avatar_url)

            if settings["disabled"]:
                em.description = "Highlight is currently disabled"

            em.add_field(name="Timezone", value=settings["timezone"])

            await ctx.send(embed=em, delete_after=15)

        try:
            await ctx.message.delete()
        except discord.HTTPException:
            pass

    @commands.command(name="forget", description="Delete all your information")
    async def forget(self, ctx):
        result = await Confirm("Are you sure you want to do this? I will forget your words, blocked list, and configuration").prompt(ctx)
        if result:
            query = """DELETE FROM words
                       WHERE words.userid=$1;
                    """
            await self.bot.db.execute(query, ctx.author.id)

            quey = """DELETE FROM settings
                      WHERE settings.userid=$1;
                    """
            await self.bot.db.execute(query, ctx.author.id)

            await ctx.send("✅ Successfully deleted your information", delete_after=10)

        try:
            await ctx.message.delete()
        except discord.HTTPException:
            pass

def setup(bot):
    bot.add_cog(Highlight(bot))

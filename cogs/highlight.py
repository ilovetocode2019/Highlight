import discord
from discord.ext import commands, menus

import datetime
import asyncio
import re
import typing
import dateparser
import humanize
import logging

class Confirm(menus.Menu):
    def __init__(self, msg):
        super().__init__(timeout=30.0, delete_message_after=True)
        self.msg = msg
        self.result = None

    async def send_initial_message(self, ctx, channel):
        return await channel.send(self.msg)

    @menus.button("\N{WHITE HEAVY CHECK MARK}")
    async def do_confirm(self, payload):
        self.result = True
        self.stop()

    @menus.button("\N{CROSS MARK}")
    async def do_deny(self, payload):
        self.result = False
        self.stop()

    async def prompt(self, ctx):
        await self.start(ctx, wait=True)
        return self.result

class TimeConverter(commands.Converter):
    async def convert(self, ctx, arg):
        try:
            if not arg.startswith("in") and not arg.startswith("at"):
                arg = f"in {arg}"
            time = dateparser.parse(arg, settings={"TIMEZONE": "UTC"})
        except:
            raise commands.BadArgument("Failed to parse time")
        if not time:
            raise commands.BadArgument("Failed to parse time")
        return time

log = logging.getLogger("cogs.highlight")

class Highlight(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener("on_message")
    async def on_message(self, message):
        if message.author.bot:
            return

        sent = []
        for word in self.bot.cached_words:
            if self.word_in_message(word, message.content.lower()):
                query = """SELECT *
                           FROM words
                           WHERE words.word=$1 AND words.guild_id=$2;
                        """
                rows = await self.bot.db.fetch(query, word, message.guild.id)

                if not rows:
                    continue

                # Somehow the guild isn't chunked
                if not message.guild.chunked:
                    log.warning("Guild ID %s is not chunked. Chunking guild now.", message.guild.id)
                    await message.guild.chunk(cache=True)

                for row in rows:
                    if row["user_id"] not in sent:
                        self.bot.loop.create_task(self.send_highlight(message, row))
                        sent.append(row["user_id"])

    async def send_highlight(self, message, row):
        member = message.guild.get_member(row["user_id"])
        # Member probably left
        if not member:
            log.info("Received a highlight for user ID %s (guild ID %s) but member is None. Member probably left guild.", row["user_id"], row["guild_id"])
            return

        # Get the settings for the user
        query = """SELECT *
                   FROM settings
                   WHERE settings.user_id=$1;
                """
        settings_row = await self.bot.db.fetchrow(query, member.id)

        if not settings_row:
            settings_row = {"user_id": member.id, "disabled": False, "timezone": 0, "blocked_users": [], "blocked_channels": []}

        # Make sure the user has not disabled highlight, can view the channel, has not blocked the author or channel, is not the author
        if settings_row["disabled"]:
            return
        if member.id not in [member.id for member in message.channel.members]:
            return
        if message.channel.id in settings_row["blocked_channels"] or message.author.id in settings_row["blocked_users"]:
            return
        if member.id == message.author.id:
            return

        utc = ""
        if settings_row["timezone"] == 0:
            utc = " UTC"

        # Create the embed for the highlight
        em = discord.Embed(timestamp=datetime.datetime.now(), description=f"You got highlighted in {message.channel.mention}\n\n", color=discord.Color.blurple())
        em.set_author(name=message.author.display_name, icon_url=message.author.avatar_url)
        em.description += "\n\n".join([f"> {x.author} at {(x.created_at+datetime.timedelta(hours=settings_row['timezone'])).strftime(f'%H:%M:%S{utc}')}: {x.content}" for x in reversed((await message.channel.history(limit=3).flatten())[1:])])

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

            # Don't trigger the highlight if the user replies to the tigger message
            if ms.author.id == member.id:
                return

            # Add the new message to the embed
            em.description += f"\n\n> {ms.author} at {(ms.created_at+datetime.timedelta(hours=settings_row['timezone'])).strftime(f'%H:%M:%S{utc}')}: {ms.content}"

        except asyncio.TimeoutError:
            pass

        em.add_field(name="Jump", value=f"[Click]({message.jump_url})")

        try:
            await member.send(embed=em)
        except discord.Forbidden:
            log.warning("Forbidden to send highlight message to user ID %s. DMs probably disabled.", member.id)

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

    async def can_dm(self, user):
        try:
            await user.send()
        except discord.HTTPException as exc:
            if exc.code == 50006:
                return True
            elif exc.code == 50007:
                return False
            else:
                raise

    @commands.guild_only()
    @commands.command(name="add", description="Add a highlight word")
    async def add(self, ctx, *, word):
        word = word.lower()
        can_dm = await self.can_dm(ctx.author)

        if not can_dm:
            await ctx.send(":x: You need to enable DMs", delete_after=5)
        elif f"<@!{self.bot.user.id}>" in word:
            await ctx.send(":x: Your highlight word can't mention me", delete_after=5)
        elif len(word) < 2:
            await ctx.send(":x: Your word must be at least 2 characters", delete_after=5)
        elif len(word) > 20:
            await ctx.send(":x: Your word cannot be bigger than 20 characters", delete_after=5)

        else:
            query = """SELECT COUNT(*)
                       FROM words
                       WHERE words.user_id=$1 AND words.guild_id=$2 AND words.word=$3;
                    """
            if (await self.bot.db.fetchrow(query, ctx.author.id, ctx.guild.id, word))["count"]:
                await ctx.send(":x: You already have that word", delete_after=5)
            else:
                query = """INSERT INTO words (user_id, guild_id, word)
                           VALUES ($1, $2, $3);
                        """
                await self.bot.db.execute(query, ctx.author.id, ctx.guild.id, word)

                if word not in self.bot.cached_words:
                    self.bot.cached_words.append(word)

                await ctx.send(":white_check_mark: Words updated", delete_after=5)

        try:
           await ctx.message.delete()
        except discord.HTTPException:
            pass

    @commands.guild_only()
    @commands.command(name="remove", description="Remove a highlight word")
    async def remove(self, ctx, *, word):
        query = """DELETE FROM words
                   WHERE words.user_id=$1 AND words.guild_id=$2 AND words.word=$3;
                """
        result = await self.bot.db.execute(query, ctx.author.id, ctx.guild.id, word)

        if result == "DELETE 0":
            await ctx.send(":x: This word is not registered", delete_after=5)
        else:
            await ctx.send(":white_check_mark: Words updated", delete_after=5)

        try:
           await ctx.message.delete()
        except discord.HTTPException:
            pass

    @commands.guild_only()
    @commands.command(name="clear", description="Clear your highlight list")
    async def clear(self, ctx):
        result = await Confirm("Are you sure you want to clear your word list for this server?").prompt(ctx)

        if result:
            query = """DELETE FROM words
                       WHERE words.user_id=$1 AND words.guild_id=$2;
                    """
            await self.bot.db.execute(query, ctx.author.id, ctx.guild.id)

            await ctx.send(":white_check_mark: Your highlight list has been cleared", delete_after=5)
        else:
            await ctx.send(":x: Aborting", delete_after=5)
        try:
            await ctx.message.delete()
        except discord.HTTPException:
            pass

    @commands.guild_only()
    @commands.command(name="transfer", description="Transfer your words from another server", usage="<server id>", aliases=["import"])
    async def transfer(self, ctx, guild_id: int):
        query = """SELECT *
                   FROM words
                   WHERE words.user_id=$1 AND (words.guild_id=$2 OR words.guild_id=$3);
                """
        words = await self.bot.db.fetch(query, ctx.author.id, guild_id, ctx.guild.id)

        to_transfer = []
        for word in words:
            if word["guild_id"] == guild_id and word["word"] not in [x["word"] for x in words if x["guild_id"] == ctx.guild.id]:
                to_transfer.append({"user_id": ctx.author.id, "guild_id": ctx.guild.id, "word": word["word"]})

        if not to_transfer:
            await ctx.send(":x: You have no words to transfer from this server", delete_after=5)
        else:
            query = """INSERT INTO words (user_id, guild_id, word)
                       SELECT x.user_id, x.guild_id, x.word
                       FROM jsonb_to_recordset($1::jsonb) AS
                       x(user_id BIGINT, guild_id BIGINT, word TEXT);
                    """

            await self.bot.db.execute(query, to_transfer)
            await ctx.send(":white_check_mark: Your highlight list has been imported", delete_after=5)

        try:
            await ctx.message.delete()
        except discord.HTTPException:
            pass

    @commands.guild_only()
    @commands.command(name="show", description="View your words for the current server")
    async def show(self, ctx):
        query = """SELECT * FROM words
                   WHERE words.user_id=$1 AND words.guild_id=$2;
                """
        rows = await self.bot.db.fetch(query, ctx.author.id, ctx.guild.id)

        if not rows:
            await ctx.send("You have no words for this server", delete_after=10)
        else:
            em = discord.Embed(title="Highlight Words", color=discord.Color.blurple())
            em.set_author(name=ctx.author.display_name, icon_url=ctx.author.avatar_url)

            em.description = ""
            for row in rows:
                em.description += f"\n{row['word']}"

            await ctx.send(embed=em, delete_after=10)

        try:
           await ctx.message.delete()
        except discord.HTTPException:
            pass

    @commands.command(name="block", description="Block a user or channel", usage="<user or channel>", aliases=["ignore", "mute"])
    async def block(self, ctx, *, user: typing.Union[discord.User, discord.TextChannel]):
        query = """SELECT *
                   FROM settings
                   WHERE settings.user_id=$1;
                """
        settings = await self.bot.db.fetchrow(query, ctx.author.id)

        if isinstance(user, discord.User):
            if settings:
                if user.id in settings["blocked_users"]:
                    await ctx.send(":x: This user is already blocked", delete_after=5)
                else:
                    settings["blocked_users"].append(user.id)
                    query = """UPDATE settings
                               SET blocked_users=$1
                               WHERE settings.user_id=$2;
                            """
                    await self.bot.db.execute(query, settings["blocked_users"], ctx.author.id)
                    await ctx.send(f":no_entry_sign: Blocked {user.display_name}", delete_after=5)
            else:
                query = """INSERT INTO settings (user_id, disabled, timezone, blocked_users, blocked_channels)
                           VALUES ($1, $2, $3, $4, $5);
                        """
                await self.bot.db.execute(query, ctx.author.id, False, 0, [user.id], [])
        else:
            if settings:
                if user.id in settings["blocked_channels"]:
                    await ctx.send(":x: This channel is already blocked", delete_after=5)
                else:
                    settings["blocked_channels"].append(user.id)
                    query = """UPDATE settings
                               SET blocked_channels=$1
                               WHERE settings.user_id=$2;
                            """
                    await self.bot.db.execute(query, settings["blocked_channels"], ctx.author.id)
                    await ctx.send(f":no_entry_sign: Blocked {user.mention}", delete_after=5)
            else:
                query = """INSERT INTO settings (user_id, disabled, timezone, blocked_users, blocked_channels)
                           VALUES ($1, $2, $3, $4, $5);
                        """
                await self.bot.db.execute(query, ctx.author.id, False, 0, [], [user.id])

        try:
            await ctx.message.delete()
        except discord.HTTPException:
            pass

    @commands.command(name="unblock", description="Unblock a user or channel", usage="<use or channel>", aliases=["unmute"])
    async def unblock(self, ctx, *, user: typing.Union[discord.User, discord.TextChannel]):
        query = """SELECT *
                   FROM settings
                   WHERE settings.user_id=$1;
                """
        settings = await self.bot.db.fetchrow(query, ctx.author.id)

        if isinstance(user, discord.User):

            if settings:
                if user.id not in settings["blocked_users"]:
                    await ctx.send(":x: This user is not blocked", delete_after=5)
                else:
                    settings["blocked_users"].remove(user.id)
                    query = """UPDATE settings
                               SET blocked_users=$1
                               WHERE settings.user_id=$2;
                            """
                    await self.bot.db.execute(query, settings["blocked_users"], ctx.author.id)
                    await ctx.send(f":white_check_mark: Unblocked {user.display_name}", delete_after=5)
            else:
                await ctx.send(":x: This user is not blocked", delete_after=5)

        else:

            if settings:
                if user.id not in settings["blocked_channels"]:
                    await ctx.send(":x: This channel is not blocked", delete_after=5)
                else:
                    settings["blocked_channels"].remove(user.id)
                    query = """UPDATE settings
                               SET blocked_channels=$1
                               WHERE settings.user_id=$2;
                            """
                    await self.bot.db.execute(query, settings["blocked_channels"], ctx.author.id)
                    await ctx.send(f":white_check_mark: Unblocked {user.mention}", delete_after=5)
            else:
                await ctx.send(":x: This channel is not blocked")

        try:
            await ctx.message.delete()
        except discord.HTTPException:
            pass

    @commands.group(name="blocked", description="View your blocked list", invoke_without_command=True)
    async def blocked(self, ctx):
        query = """SELECT *
                   FROM settings
                   WHERE settings.user_id=$1;
                """
        settings = await self.bot.db.fetchrow(query, ctx.author.id)

        if not settings or (not settings["blocked_channels"] and not settings["blocked_users"]):
            await ctx.send(":x: You have no channnels or users blocked", delete_after=5)
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

            await ctx.send(embed=em, delete_after=10)
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
                       WHERE settings.user_id=$3;
                    """
            await self.bot.db.execute(query, [], [], ctx.author.id)

            await ctx.send(":white_check_mark: Your blocked list has been cleared")

        try:
            await ctx.message.delete()
        except discord.HTTPException:
            pass

    @commands.command(name="enable", description="Enable highlight")
    async def enable(self, ctx):
        await self.bot.get_cog("Timers").cancel_timer(ctx.author.id, "disable")

        query = """INSERT INTO settings (user_id, disabled, timezone, blocked_users, blocked_channels)
                   VALUES ($1, $2, $3, $4, $5)
                   ON CONFLICT (user_id)
                   DO UPDATE SET disabled=$2;
                """
        await self.bot.db.execute(query, ctx.author.id, False, 0, [], [])

        await ctx.send(":white_check_mark: Highlight has been enabled", delete_after=5)

        try:
            await ctx.message.delete()
        except discord.HTTPException:
            pass

    @commands.command(name="disable", description="Disable highlight", aliases=["dnd"])
    async def disable(self, ctx, *, time: TimeConverter = None):
        await self.bot.get_cog("Timers").cancel_timer(ctx.author.id, "disable")

        query = """INSERT INTO settings (user_id, disabled, timezone, blocked_users, blocked_channels)
                   VALUES ($1, $2, $3, $4, $5)
                   ON CONFLICT (user_id)
                   DO UPDATE SET disabled=$2;
                """
        await self.bot.db.execute(query, ctx.author.id, True, 0, [], [])

        if time:
            await self.bot.get_cog("Timers").create_timer(ctx.author.id, "disabled", time, {})

        await ctx.send(f":white_check_mark: Highlight has been disabled {f'for {humanize.naturaldelta(time-datetime.datetime.utcnow())}' if time else ''}", delete_after=5)

        try:
            await ctx.message.delete()
        except discord.HTTPException:
            pass

    @commands.command(name="timezone", description="Set your timezone")
    async def timezone(self, ctx, timezone: int = None):
        if timezone:
            query = """INSERT INTO settings (user_id, disabled, timezone, blocked_users, blocked_channels)
                       VALUES ($1, $2, $3, $4, $5)
                       ON CONFLICT (user_id)
                       DO UPDATE SET timezone=$3;
                    """

            await self.bot.db.execute(query, ctx.author.id, False, timezone, [], [])
            await ctx.send(":white_check_mark: Timezone saved", delete_after=5)

        else:
            query = """SELECT *
                       FROM settings
                       WHERE settings.user_id=$1;
                    """
            settings = await self.bot.db.fetchrow(query, ctx.author.id)
            if settings:
                await ctx.send(f"Your current timezone is `{settings['timezone']}`", delete_after=10)
            else:
                await ctx.send(f"Your current timezone is `{0}`", delete_after=10)

        try:
            await ctx.message.delete()
        except discord.HTTPException:
            pass

    @commands.command(name="forget", description="Delete all your information")
    async def forget(self, ctx):
        result = await Confirm("Are you sure you want to do this? I will forget your words, blocked list, and settings").prompt(ctx)
        if result:
            query = """DELETE FROM words
                       WHERE words.user_id=$1;
                    """
            await self.bot.db.execute(query, ctx.author.id)

            query = """DELETE FROM settings
                       WHERE settings.user_id=$1;
                    """
            await self.bot.db.execute(query, ctx.author.id)

            await ctx.send(":white_check_mark: Successfully deleted your information", delete_after=5)
        else:
            await ctx.send(":x: Aborting", delete_after=5)

        try:
            await ctx.message.delete()
        except discord.HTTPException:
            pass

    @commands.Cog.listener()
    async def on_disabled_complete(self, timer):
        query = """INSERT INTO settings (user_id, disabled, timezone)
                   VALUES ($1, $2, $3)
                   ON CONFLICT (user_id)
                   DO UPDATE SET disabled=$2;
                """
        await self.bot.db.execute(query, timer["user_id"], False, 0)


def setup(bot):
    bot.add_cog(Highlight(bot))

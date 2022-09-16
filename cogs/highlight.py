import asyncio
import datetime
import logging
import re
import typing

import asyncpg
import dateparser
import humanize
import discord
from discord import app_commands
from discord.ext import commands, menus, tasks

from .utils import formats, menus

log = logging.getLogger("cogs.highlight")

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

class JumpBackView(discord.ui.View):
    def __init__(self, jump_url):
        super().__init__()
        self.add_item(discord.ui.Button(url=jump_url, label="Go to Message"))

class ServerSelect(discord.ui.Select):
    def __init__(self, guilds):
        options = [discord.SelectOption(label=guild.name, value=guild.id) for guild in guilds]
        super().__init__(placeholder="Choose a server to import highlight words from", min_values=1, max_values=1, options=options)

    async def callback(self, interaction):
        await interaction.response.defer()

class TransferWordsView(discord.ui.View):
    def __init__(self, bot, user, guilds):
        super().__init__()
        self.bot = bot
        self.user = user

        self.server_select_menu = ServerSelect(guilds)
        self.add_item(self.server_select_menu)

        self.blocked._fallback_command.wrapped.cog = self # Temporary fix for discord.py bug

    @discord.ui.button(label="Transfer", style=discord.ButtonStyle.success)
    async def transfer(self, interaction, button):
        options = self.server_select_menu.values

        if not options:
            return await interaction.response.send_message("No server is selected. Select one from the menu before transfering.", ephemeral=True)

        guild_id = int(options[0])

        query = """SELECT *
                   FROM words
                   WHERE words.user_id=$1 AND (words.guild_id=$2 OR words.guild_id=$3);
                """
        words = await self.bot.db.fetch(query, interaction.user.id, guild_id, interaction.guild_id)
        words = [dict(word) for word in words]

        to_transfer = []
        for word in words:
            if word["guild_id"] == guild_id and word["word"] not in [word["word"] for word in words if word["guild_id"] == interaction.guild_id]:
                word["guild_id"] = interaction.guild_id
                to_transfer.append(word)

        if to_transfer:
            query = """INSERT INTO words (user_id, guild_id, word)
                       SELECT x.user_id, x.guild_id, x.word
                       FROM jsonb_to_recordset($1::jsonb) AS
                       x(user_id BIGINT, guild_id BIGINT, word TEXT);
                    """

            await self.bot.db.execute(query, to_transfer)

            guild = self.bot.get_guild(guild_id)
            await interaction.response.edit_message(content=f":white_check_mark: Imported {formats.plural(len(to_transfer)):highlight word} from `{discord.utils.escape_markdown(guild.name)}`", view=None)
        else:
            await interaction.response.send_message(content="You have no words to transfer from that server.", ephemeral=True)

        for transfered in to_transfer:
            self.bot.cached_words.append(transfered)

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.danger)
    async def cancel(self, interaction, button):
        self.disable_buttons()
        await interaction.response.edit_message(view=self)

    def disable_buttons(self):
        for item in self.children:
            item.disabled = True

    async def on_timeout(self):
        self.disable_buttons()
        await self.message.edit(view=self)

class Highlight(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self._highlight_batch = []
        self._batch_lock = asyncio.Lock()

        self.bulk_insert_loop.add_exception_type(asyncpg.PostgresConnectionError)
        self.bulk_insert_loop.start()

    async def cog_unload(self):
        log.info("Stopping bulk insert loop")
        self.bulk_insert_loop.stop()
        await self.bulk_insert()

    @commands.Cog.listener("on_message")
    async def check_highlights(self, message):
        if not message.guild:
            return
        if message.author.bot:
            return

        # Search for any possible highlights inside the message

        notified_users = []
        possible_words = [word for word in self.bot.cached_words if word["guild_id"] == message.guild.id]

        for possible_word in possible_words:
            # Check if the highlight is in the message
            # Also use regex to make sure it doesn't have false positives
            escaped = re.escape(possible_word["word"])
            match = re.match(r"^(?:.+ )?(?:\W*)({word})(?:[{word}]*)(?:\W+|[(?:'|\")s]*)(?: .+)?$".format(word=escaped), message.content, re.I)

            # Trigger the highlight if there's a match
            # Also ignore the trigger if the user was already notified for a word in this message
            if match and possible_word["user_id"] not in notified_users:
                notified_users.append(possible_word["user_id"])
                self.bot.dispatch(f"highlight", message, possible_word, match.group(1))

    # The following three listeners send a user activity to the on_highlight_trigger function
    # This way the user has time to indicate that they saw the message and we do not need to highlight them
    @commands.Cog.listener()
    async def on_message(self, message):
        self.bot.dispatch("user_activity", message.channel, message.author)

    @commands.Cog.listener()
    async def on_typing(self, channel, user, when):
        self.bot.dispatch("user_activity", channel, user)

    @commands.Cog.listener()
    async def on_reaction_add(self, reaction, user):
        self.bot.dispatch("user_activity", reaction.message.channel, user)

    @commands.Cog.listener()
    async def on_highlight(self, message, word, text):
        try:
            member = await message.guild.fetch_member(word["user_id"])
        except discord.NotFound:
            log.info("Unknown user ID %s (guild ID %s)", word["user_id"], word["guild_id"])
            return

        query = """SELECT *
                   FROM settings
                   WHERE settings.user_id=$1;
                """
        settings = await self.bot.db.fetchrow(query, member.id)
        if not settings:
            settings = {"user_id": member.id, "disabled": False, "blocked_users": [], "blocked_channels": []}

        # Make sure the user has highlight enabled, the actually has access to the message/channel, and the author isn't blocked
        if member.id == message.author.id or settings["disabled"]:
            return
        if not message.channel.permissions_for(member).read_messages:
            return
        if message.channel.id in settings["blocked_channels"] or message.author.id in settings["blocked_users"]:
            return

        # Prepare highlight message
        initial_description = f"In {message.channel.mention} for `{discord.utils.escape_markdown(message.guild.name)}` you were highlighted with the word **{discord.utils.escape_markdown(word['word'])}**\n\n"

        em = discord.Embed(timestamp=message.created_at, color=discord.Color.blurple())
        em.set_author(name=message.author.display_name, icon_url=message.author.display_avatar.url)
        em.set_footer(text="Triggered")

        span = re.search(re.escape(word["word"]), message.content.lower()).span()

        if len(message.content) > 2000:
            if span[1] > 2000:
                end = min(200, span[0]-1)
                content = f"{discord.utils.escape_markdown(message.content[:end])}... **{discord.utils.escape_mentions(messae.content)}** ..."
            else:
                content = discord.utils.escape_markdown(message.content[:2000])
        else:
            content = discord.utils.escape_markdown(message.content[:span[0]])
            content += f"**{discord.utils.escape_markdown(text)}**"
            content += discord.utils.escape_markdown(message.content[span[1]:])

        timestamp = message.created_at.timestamp()
        em.description = f"<t:{int(timestamp)}:t> {discord.utils.escape_markdown(str(message.author))}: {content}"

        try:
            messages = []
            async for ms in message.channel.history(limit=3, before=message):
                content = f"{ms.content[:50]}{'...' if len(ms.content) > 50 else ''}"
                timestamp = ms.created_at.timestamp()

                text = f"<t:{int(timestamp)}:t> {discord.utils.escape_markdown(str(ms.author))}: {discord.utils.escape_markdown(content)}\n"

                if len(initial_description + em.description + text) <= 4096:
                    em.description = text + em.description
        except discord.HTTPException:
            pass

        em.description = initial_description + em.description

        # Wait to make sure the user isn't active in the channel (message sent, typing started, or reaction added)
        try:
            await self.bot.wait_for("user_activity", check=lambda channel, user: message.channel == channel and user == member, timeout=10)
            return
        except asyncio.TimeoutError:
            pass

        try:
            await member.send(embed=em, view=JumpBackView(message.jump_url))

            self._highlight_batch.append(
                {
                    "guild_id": message.guild.id,
                    "channel_id": message.channel.id,
                    "message_id": message.id,
                    "author_id": message.author.id,
                    "user_id": word["user_id"],
                    "word": word["word"],
                    "invoked_at": message.created_at.isoformat()
                }
            )
        except discord.Forbidden:
            log.warning("Forbidden to DM user ID %s (guild ID %s)", member.id, message.guild.id)

    @commands.hybrid_command(name="add", description="Add a word to your highlight word list")
    @commands.guild_only()
    async def add(self, ctx, *, word):

        try:
            await ctx.author.send()
        except discord.HTTPException as exc:
            if exc.code == 50007:
                await ctx.send("You need to have DMs enabled for highlight notifications to work.", delete_after=5, ephemeral=True)

        word = word.lower()

        if discord.utils.escape_mentions(word) != word:
            await ctx.send("Your highlight word cannot contain any mentions.", delete_after=5, ephemeral=True)
        elif len(word) < 2:
            await ctx.send("Your highlight word must contain at least 2 characters.", delete_after=5, ephemeral=True)
        elif len(word) > 20:
            await ctx.send("Your highlight word cannot contain more than 20 characters.", delete_after=5, ephemeral=True)
        else:
            try:
                query = """INSERT INTO words (user_id, guild_id, word)
                           VALUES ($1, $2, $3);
                        """
                await self.bot.db.execute(query, ctx.author.id, ctx.guild.id, word)

                self.bot.cached_words.append({"user_id": ctx.author.id, "guild_id": ctx.guild.id, "word": word})
                await ctx.send(f":white_check_mark: Added `{word}` to your highlight list.", delete_after=5, ephemeral=True)
            except asyncpg.UniqueViolationError:
                await ctx.send("You cannot add the same highlight word multiple times.", delete_after=5, ephemeral=True)

    @commands.hybrid_command(name="remove", description="Remove a word from your highlight word list")
    @commands.guild_only()
    async def remove(self, ctx, *, word):
        word = word.lower()

        query = """DELETE FROM words
                   WHERE words.user_id=$1 AND words.guild_id=$2 AND words.word=$3;
                """
        result = await self.bot.db.execute(query, ctx.author.id, ctx.guild.id, word)

        if result == "DELETE 0":
            await ctx.send("This word is not registered as a highlight word.", delete_after=5, ephemeral=True)
        else:
            await ctx.send(f":white_check_mark: Removed `{word}` from your highlight list.", delete_after=5, ephemeral=True)

        # Remove word from the cache, so we don't trigger deleted highlights
        for cached_word in self.bot.cached_words:
            if cached_word["user_id"] == ctx.author.id and cached_word["guild_id"] == ctx.guild.id and cached_word["word"] == word:
                self.bot.cached_words.remove(cached_word)

    @commands.hybrid_command(name="show", description="See all your highlight wo", aliases=["words", "list"])
    @commands.guild_only()
    async def show(self, ctx):
        words = [cached_word for cached_word in self.bot.cached_words if cached_word["user_id"] == ctx.author.id and cached_word["guild_id"] == ctx.guild.id]

        if not words:
            await ctx.send("You have no highlight words in this server.", delete_after=10, ephemeral=True)
        else:
            em = discord.Embed(title="Highlight Words", color=discord.Color.blurple())
            em.set_author(name=ctx.author.display_name, icon_url=ctx.author.display_avatar.url)

            em.description = ""
            for word in words:
                em.description += f"\n{word['word']}"

            await ctx.send(embed=em, delete_after=10, ephemeral=True)

    @commands.hybrid_command(name="clear", description="Clear your highlight words in this server")
    @commands.guild_only()
    async def clear(self, ctx):
        query = """DELETE FROM words
                    WHERE words.user_id=$1 AND words.guild_id=$2;
                """
        result = await self.bot.db.execute(query, ctx.author.id, ctx.guild.id)

        await ctx.send(f":white_check_mark: Your highlight list has been cleared in this server.", delete_after=5, ephemeral=True)

        for cached_word in self.bot.cached_words:
            if cached_word["user_id"] == ctx.author.id and cached_word["guild_id"] == ctx.guild.id:
                self.bot.cached_words.remove(cached_word)

    @commands.command(name="transfer", description="Import your highlight words from another server", usage="<server ID>", aliases=["import"])
    @commands.guild_only()
    async def transfer(self, ctx, guild_id: int):
        if guild_id == ctx.guild.id:
            return await ctx.send("You cannot import words from this guild, it must be another guild.", delete_after=5)
        query = """SELECT *
                   FROM words
                   WHERE words.user_id=$1 AND (words.guild_id=$2 OR words.guild_id=$3);
                """
        words = await self.bot.db.fetch(query, ctx.author.id, guild_id, ctx.guild.id)
        words = [dict(word) for word in words]

        to_transfer = []
        for word in words:
            if word["guild_id"] == guild_id and word["word"] not in [word["word"] for word in words if word["guild_id"] == ctx.guild.id]:
                word["guild_id"] = ctx.guild.id
                to_transfer.append(word)

        if to_transfer:
            query = """INSERT INTO words (user_id, guild_id, word)
                       SELECT x.user_id, x.guild_id, x.word
                       FROM jsonb_to_recordset($1::jsonb) AS
                       x(user_id BIGINT, guild_id BIGINT, word TEXT);
                    """

            await self.bot.db.execute(query, to_transfer)
            await ctx.send(f":white_check_mark: Imported {formats.plural(len(to_transfer)):highlight word} from that server.", delete_after=5)
        else:
            await ctx.send("You have no words to transfer from this server.", delete_after=5)

        for transfered in to_transfer:
            self.bot.cached_words.append(transfered)

    @app_commands.command(name="transfer", description="Import your highlight words from another server")
    @commands.guild_only()
    async def slash_transfer(self, interaction):
        guilds = [guild for guild in self.bot.guilds if interaction.user in guild.members and interaction.guild != guild]

        if not guilds:
            return await interaction.response.send_message("I don't see any servers I share with you, other than this one.", ephemeral=True)

        view = TransferWordsView(self.bot, interaction.user, guilds)
        await interaction.response.send_message(view=view, ephemeral=True)
        view.message = await interaction.original_response()

    async def do_block(self, user_id, entity):
        query = """SELECT *
                   FROM settings
                   WHERE settings.user_id=$1;
                """
        settings = await self.bot.db.fetchrow(query, user_id)

        if isinstance(entity, discord.User) or isinstance(entity, discord.Member):
            if settings:
                if entity.id in settings["blocked_users"]:
                    return "This user is already blocked."
                else:
                    settings["blocked_users"].append(entity.id)
                    query = """UPDATE settings
                               SET blocked_users=$1
                               WHERE settings.user_id=$2;
                            """
                    await self.bot.db.execute(query, settings["blocked_users"], user_id)
                    return f":no_entry_sign: Blocked `{entity}`."
            else:
                query = """INSERT INTO settings (user_id, disabled, blocked_users, blocked_channels)
                           VALUES ($1, $2, $3, $4);
                        """
                await self.bot.db.execute(query, user_id, False, [entity.id], [])
                return f":no_entry_sign: Blocked `{entity.display_name}`."

        elif isinstance(entity, discord.TextChannel):
            if settings:
                if entity.id in settings["blocked_channels"]:
                    return "This channel is already blocked."

                else:
                    settings["blocked_channels"].append(entity.id)
                    query = """UPDATE settings
                               SET blocked_channels=$1
                               WHERE settings.user_id=$2;
                            """
                    await self.bot.db.execute(query, settings["blocked_channels"], user_id)
                    return f":no_entry_sign: Blocked {entity.mention}."
            else:
                query = """INSERT INTO settings (user_id, disabled, blocked_users, blocked_channels)
                           VALUES ($1, $2, $3, $4);
                        """
                await self.bot.db.execute(query, user_id, False, [], [entity.id])
                return f":no_entry_sign: Blocked `{entity.mention}`."

    async def do_unblock(self, user_id, entity):
        query = """SELECT *
                   FROM settings
                   WHERE settings.user_id=$1;
                """
        settings = await self.bot.db.fetchrow(query, user_id)

        if isinstance(entity, discord.User) or isinstance(entity, discord.Member):
            if settings:
                if entity.id not in settings["blocked_users"]:
                    return "This user is not blocked."
                else:
                    settings["blocked_users"].remove(entity.id)
                    query = """UPDATE settings
                               SET blocked_users=$1
                               WHERE settings.user_id=$2;
                            """
                    await self.bot.db.execute(query, settings["blocked_users"], user_id)
                    return f":white_check_mark: Unblocked `{entity}`."
            else:
                return "This user is not blocked."

        elif isinstance(entity, discord.TextChannel):
            if settings:
                if entity.id not in settings["blocked_channels"]:
                    return "This channel is not blocked."
                else:
                    settings["blocked_channels"].remove(entity.id)
                    query = """UPDATE settings
                               SET blocked_channels=$1
                               WHERE settings.user_id=$2;
                            """
                    await self.bot.db.execute(query, settings["blocked_channels"], user_id)
                    return f":white_check_mark: Unblocked {entity.mention}."
            else:
                return "This channel is not blocked."

    # Block and unblock text commands
    @commands.hybrid_group(name="block", description="Block a user or channel", usage="<user or channel>", aliases=["ignore", "mute"], invoke_without_command=True)
    @commands.guild_only()
    async def block(self, ctx, *, entity):
        try:
            entity = await commands.MemberConverter().convert(ctx, entity)
        except commands.BadArgument:
            try:
                entity = await commands.TextChannelConverter().convert(ctx, entity)
            except commands.BadArgument:
                return await ctx.send(f"Channel or user {entity} not found.")

        result = await self.do_block(ctx.author.id, entity)
        await ctx.send(result, delete_after=5)

    @commands.hybrid_group(name="unblock", description="Unblock a user or channel", usage="<user or channel>", aliases=["unmute"], invoke_without_command=True)
    @commands.guild_only()
    async def unblock(self, ctx, *, entity):
        try:
            entity = await commands.MemberConverter().convert(ctx, entity)
        except commands.BadArgument:
            try:
                entity = await commands.TextChannelConverter().convert(ctx, entity)
            except commands.BadArgument:
                return await ctx.send(f"Channel or user {entity} not found.")

        result = await self.do_unblock(ctx.author.id, entity)
        await ctx.send(result, delete_after=5)

    # Block and unblock slash commands
    @block.app_command.command(name="user", description="Block a user")
    async def slash_block_user(self, interaction, user: discord.Member):
        result = await self.do_block(interaction.user.id, user)
        await interaction.response.send_message(result, ephemeral=True)

    @block.app_command.command(name="channel", description="Block a channel")
    async def slash_block_channel(self, interaction, channel: discord.TextChannel):
        result = await self.do_block(interaction.user.id, channel)
        await interaction.response.send_message(result, ephemeral=True)

    @unblock.app_command.command(name="user", description="Unblock a user")
    async def slash_unblock_user(self, interaction, user: discord.Member):
        result = await self.do_unblock(interaction.user.id, user)
        await interaction.response.send_message(result, ephemeral=True)

    @unblock.app_command.command(name="channel", description="Unblock a channel")
    async def slash_unblock_channel(self, interaction, channel: discord.TextChannel):
        result = await self.do_unblock(interaction.user.id, channel)
        await interaction.response.send_message(result, ephemeral=True)

    @commands.hybrid_group(name="blocked", fallback="show", description="View your blocked list", invoke_without_command=True)
    @commands.guild_only()
    async def blocked(self, ctx):
        query = """SELECT *
                   FROM settings
                   WHERE settings.user_id=$1;
                """
        settings = await self.bot.db.fetchrow(query, ctx.author.id)

        if not settings or (not settings["blocked_channels"] and not settings["blocked_users"]):
            await ctx.send("You have no blocked users or channels.", delete_after=5, ephemeral=True)
        else:
            em = discord.Embed(color=discord.Color.blurple())
            em.set_author(name=ctx.author.display_name, icon_url=ctx.author.display_avatar.url)

            users = []
            for user_id in settings["blocked_users"]:
                user = await self.bot.fetch_user(user_id)
                guilds = [f"`{guild.name}`" for guild in self.bot.guilds if user in guild.members and ctx.author in guild.members]

                if user and guilds:
                    users.append(f"{user.mention} - {formats.join(guilds, last='and')}")

            if users:
                em.add_field(name="Blocked Users", value="\n".join(users))

            channels = []
            for channel_id in settings["blocked_channels"]:
                channel = self.bot.get_channel(channel_id) and user in channel.guild
                if channel:
                    channels.append(channel.mention)

            if channels:
                em.add_field(name="Blocked Channels", value="\n".join(channels))

            await ctx.send(embed=em, delete_after=10, ephemeral=True)

    @blocked.command(name="clear", description="Clear your blocked list")
    @commands.guild_only()
    async def blocked_clear(self, ctx):
        query = """UPDATE settings
                   SET blocked_users=$1, blocked_channels=$2
                   WHERE settings.user_id=$3;
                """
        await self.bot.db.execute(query, [], [], ctx.author.id)

        await ctx.send(f":white_check_mark: Your blocked list has been cleared.", ephemeral=True)

    @commands.hybrid_command(name="enable", description="Enable highlight")
    @commands.guild_only()
    async def enable(self, ctx):
        timers = self.bot.get_cog("Timers")
        await timers.cancel_timer(ctx.author.id, "disable")

        query = """INSERT INTO settings (user_id, disabled, blocked_users, blocked_channels)
                   VALUES ($1, $2, $3, $4)
                   ON CONFLICT (user_id)
                   DO UPDATE SET disabled=$2;
                """
        await self.bot.db.execute(query, ctx.author.id, False, [], [])

        await ctx.send(":white_check_mark: Highlight has been enabled.", delete_after=5, ephemeral=True)

    @commands.hybrid_command(name="disable", description="Disable highlight", aliases=["dnd"])
    async def disable(self, ctx, *, duration: TimeConverter = None):
        timers = self.bot.get_cog("Timers")
        await timers.cancel_timer(ctx.author.id, "disable")

        query = """INSERT INTO settings (user_id, disabled, blocked_users, blocked_channels)
                   VALUES ($1, $2, $3, $4)
                   ON CONFLICT (user_id)
                   DO UPDATE SET disabled=$2;
                """
        await self.bot.db.execute(query, ctx.author.id, True, [], [])

        query = """DELETE FROM timers
                   WHERE timers.event='disabled' AND timers.data=$2;
                """

        if duration:
            await timers.create_timer(ctx.author.id, "disabled", duration, {})

            timestamp = duration.replace(tzinfo=datetime.timezone.utc).timestamp()
            await ctx.send(f":no_entry_sign: Highlight has been disabled {f'until <t:{int(timestamp)}:F>'}.", delete_after=5, ephemeral=True)
        else:
            await ctx.send(":no_entry_sign: Highlight has been disabled until you enable it again.", delete_after=5, ephemeral=True)

    @commands.hybrid_command(name="stats", description="View stats about the bot")
    async def stats(self, ctx):
        highlights = await self.bot.db.fetch("SELECT * FROM highlights;")

        em = discord.Embed(title="Highlight Stats", color=discord.Color.blurple())
        em.add_field(name="Total Highlights", value=len(highlights))
        em.add_field(name="Total Highlights Here", value=len([highlight for highlight in highlights if highlight["guild_id"] == ctx.guild.id]))
        await ctx.send(embed=em)

    @add.after_invoke
    @remove.after_invoke
    @clear.after_invoke
    @transfer.after_invoke
    @show.after_invoke
    @block.after_invoke
    @unblock.after_invoke
    @blocked.after_invoke
    @blocked_clear.after_invoke
    @enable.after_invoke
    @disable.after_invoke
    async def privacy(self, ctx):
        if ctx.interaction:
            return

        try:
            await ctx.message.delete()
        except discord.HTTPException:
            pass

    @commands.Cog.listener()
    async def on_disabled_complete(self, timer):
        query = """INSERT INTO settings (user_id, disabled)
                   VALUES ($1, $2)
                   ON CONFLICT (user_id)
                   DO UPDATE SET disabled=$2;
                """
        await self.bot.db.execute(query, timer["user_id"], False)

    async def bulk_insert(self):
        query = """INSERT INTO highlights (guild_id, channel_id, message_id, author_id, user_id, word, invoked_at)
                   SELECT x.guild_id, x.channel_id, x.message_id, x.author_id, x.user_id, x.word, x.invoked_at
                   FROM jsonb_to_recordset($1::jsonb) AS
                   x(guild_id BIGINT, channel_id BIGINT, message_id BIGINT, author_id BIGINT, user_id BIGINT, word TEXT, invoked_at TEXT)
                """
        if self._highlight_batch:
            await self.bot.db.execute(query, self._highlight_batch)
            total = len(self._highlight_batch)
            self._highlight_batch.clear()

    @tasks.loop(seconds=20)
    async def bulk_insert_loop(self):
        async with self._batch_lock:
            await self.bulk_insert()

    @bulk_insert_loop.before_loop
    async def before_bulk_insert_loop(self):
        if not self.bot.is_ready():
            log.info("Waiting to start bulk insert loop")
            await self.bot.wait_until_ready()

        log.info("Starting bulk insert loop")

async def setup(bot):
    await bot.add_cog(Highlight(bot))

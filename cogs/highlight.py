import discord
from discord.ext import commands

import datetime
import dateparser
import asyncio
import re

class Highlight(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener("on_message")
    async def on_message(self, message):
        if message.author.bot:
            return

        rows = None
        for word in self.bot.cached_words:
            if self.word_in_message(word, message.content.lower()):
                rows = await self.bot.db.fetch("SELECT * FROM words WHERE words.word=$1 AND words.guildid=$2", word, str(message.guild.id))
                self.bot.loop.create_task(self.send_highlight(message, rows))

    async def send_highlight(self, message, rows):
        blocks = await self.bot.db.fetch("SELECT userid FROM blocks WHERE blocks.blockedid=$1", str(message.author.id))

        for row in rows:
            is_blocked = False
            for block in blocks:
                if block[0] == row[0]:
                    is_blocked = True
                    break

            user = message.guild.get_member(int(row[0]))
            settings_row = await self.bot.db.fetchrow("SELECT * FROM settings WHERE settings.userid=$1", str(user.id))

            if not settings_row:
                settings_row = [str(user.id), False, 0]

            if not is_blocked and not settings_row[1] and user.id in [member.id for member in message.channel.members]:
                if user != message.author:

                    utc = ""
                    if settings_row[2] == 0:
                        utc = " UTC"
                    
                    em = discord.Embed(timestamp=datetime.datetime.now(), description=f"You got highlighted in {message.channel.mention}\n\n")
                    em.set_author(name=message.author.display_name, icon_url=message.author.avatar_url)
                    em.description += "\n\n".join([f"> {x.author} at {(x.created_at+datetime.timedelta(hours=settings_row[2])).strftime(f'%H:%M:%S{utc}')}: {x.content}" for x in await message.channel.history(limit=3).flatten()])

                    span = re.search(row[2], message.content).span()

                    msg = message.content[:span[0]]
                    msg += f"**{row[2]}**"
                    msg += message.content[span[1]:]
                    em.description += f"\n\n> {message.author} at {(message.created_at+datetime.timedelta(hours=settings_row[2])).strftime(f'%H:%M:%S{utc}')}: {msg}"
                    
                    def check(ms):
                        return ms.channel.id == message.channel.id
                    
                    try:
                        ms = await self.bot.wait_for("message", check=check, timeout=10)
                        if ms.author.id == user.id:
                            return
                        
                        em.description += f"\n\n> {ms.author} at {ms.created_at.strftime('%H:%M:%S UTC')}: {ms.content}"

                    except asyncio.TimeoutError:
                        pass

                    link = f"https://discord.com/channels/{message.guild.id}/{message.channel.id}/{message.id}"
                    em.add_field(name="Jump", value=f"[Click]({link})")
                    await user.send(embed=em)
    
    def word_in_message(self, word, message):
        match = re.search(word, message)

        if not match:
            return False
        
        span = match.span()
        
        start = span[0]-1
        end = span[1]

        if start >= 0:
            if message[start] != " ":
                return False

        if end < len(message):
            if message[end] != " " and message[end] not in [",", ".", "'"]:
                return False

            elif message[end] == "'":
                if end+1 < len(message):
                    if message[end+1] != "s":
                        return False

                    elif end+2 < len(message):
                        if message[end+2] != " ":
                            return False

        return True

    def parse_time(self, time):
        if not time:
            return time

        if not time.startswith("at") and not time.startswith("in"):
            time = f"in {time}"
        failed = False
        try:
            time = dateparser.parse(time, settings={'TIMEZONE': 'UTC'})
        except:
            failed = True
        
        if not failed and time:
            time = time.replace(tzinfo=datetime.timezone.utc).timestamp()

        return time


    @commands.guild_only()
    @commands.command(name="add", description="Adds a word (words guild specific)", usage="[word]")
    async def add(self, ctx, *, word):
        word = word.lower()

        if (await self.bot.db.fetch("SELECT COUNT(*) FROM words WHERE words.userid=$1 AND words.guildid=$2 AND words.word=$3", str(ctx.author.id), str(ctx.guild.id), word))[0][0]:
            await ctx.send("❌ You already have that word", delete_after=10)

            await asyncio.sleep(10)
            try:
                await ctx.message.delete()
            except:
                pass

            return

        await self.bot.db.execute("INSERT INTO words (userid, guildid, word) VALUES ($1, $2, $3)", str(ctx.author.id), str(ctx.guild.id), word)

        if word not in self.bot.cached_words:
            self.bot.cached_words.append(word)
        
        await ctx.send("✅ Words updated", delete_after=10)

        await asyncio.sleep(10)
        try:
           await ctx.message.delete()
        except:
            pass
    
    @commands.guild_only()
    @commands.command(name="remove", description="Removes a word (words guild specific)", usage="[word]")
    async def remove(self, ctx, *, word):
        await self.bot.db.execute("DELETE FROM words WHERE words.word=$1 AND words.userid=$2 AND words.guildid=$3", word, str(ctx.author.id), str(ctx.guild.id))

        await ctx.send("✅ Words updated", delete_after=10)

        await asyncio.sleep(10)
        try:
           await ctx.message.delete()
        except:
            pass

    @commands.guild_only()
    @commands.command(name="show", description="Show your words for the guild")
    async def show(self, ctx):
        rows = await self.bot.db.fetch("SELECT word FROM words WHERE words.userid=$1 AND words.guildid=$2", str(ctx.author.id), str(ctx.guild.id))

        if len(rows) == 0:
            await ctx.send("❌ No words for this guild", delete_after=15)

            await asyncio.sleep(10)
            try:
                await ctx.message.delete()
            except:
                pass

            return

        em = discord.Embed()
        em.set_author(name=ctx.author.display_name, icon_url=ctx.author.avatar_url)
        
        em.description = ""
        for row in rows:
            em.description += f"\n{row[0]}"

        await ctx.send(embed=em, delete_after=15)

        await asyncio.sleep(10)
        try:
           await ctx.message.delete()
        except:
            pass

    @commands.command(name="block", description="Block a user from highlighting you (globally)", usage="[user]")
    async def block(self, ctx, *, user: discord.Member):
        if (await self.bot.db.fetch("SELECT COUNT(*) FROM blocks WHERE blocks.userid=$1 AND blocks.blockedid=$2", str(ctx.author.id), str(user.id)))[0][0] != 0:
            await ctx.send("❌ This user is already blocked", delete_after=10)

            await asyncio.sleep(10)
            try:
                await ctx.message.delete()
            except:
                pass

            return

        await self.bot.db.execute("INSERT INTO blocks (userid, blockedid) VALUES ($1, $2)", str(ctx.author.id), str(user.id))

        await ctx.send(f"🚫 Blocked {user.display_name}", delete_after=10)

        await asyncio.sleep(10)
        try:
           await ctx.message.delete()
        except:
            pass
    
    @commands.command(name="unblock", description="Unblock a user from highlighting you (globally)")
    async def unblock(self, ctx, *, user: discord.Member):
        if (await self.bot.db.fetch("SELECT COUNT(*) FROM blocks WHERE blocks.userid=$1 AND blocks.blockedid=$2", str(ctx.author.id), str(user.id)))[0][0] == 0:
            await ctx.send("❌ This user is not blocked", delete_after=10)

            await asyncio.sleep(10)
            try:
                await ctx.message.delete()
            except:
                pass

            return

        await self.bot.db.execute("DELETE FROM blocks WHERE blocks.userid=$1 AND blocks.blockedid=$2", str(ctx.author.id), str(user.id))

        await ctx.send(f"✅ Unblocked {user.display_name}", delete_after=10)  

        await asyncio.sleep(10)
        try:
            await ctx.message.delete()
        except:
            pass
    
    @commands.command(name="blocked", description="Shows your blocked list")
    async def blocked(self, ctx):
        rows = await self.bot.db.fetch("SELECT * FROM blocks WHERE blocks.userid=$1", str(ctx.author.id))

        if len(rows) == 0:
            await ctx.send("❌ You have no blocked users", delete_after=10)

            await asyncio.sleep(10)
            try:
                await ctx.message.delete()
            except:
                pass

            return

        em = discord.Embed()
        em.set_author(name=ctx.author.display_name, icon_url=ctx.author.avatar_url)

        em.description = ""
        for row in rows:
            user = self.bot.get_user(int(row[1]))
            em.description += f"\n{user.name}"

        await ctx.send(embed=em, delete_after=15)

        await asyncio.sleep(10)
        try:
            await ctx.message.delete()
        except:
            pass

    @commands.command(name="enable", description="Enable highlight")
    async def enable(self, ctx):
        row = await self.bot.db.fetchrow("SELECT * FROM settings WHERE settings.userid=$1", str(ctx.author.id))

        if not row:
            await ctx.send("❌ Already enabled", delete_after=10)

            await asyncio.sleep(10)
            try:
                await ctx.message.delete()
            except:
                pass

            return

        else:
            if not row[1]:
                return await ctx.send("❌ Already enabled", delete_after=10)

                await asyncio.sleep(10)
                try:
                    await ctx.message.delete()
                except:
                    pass
            
            else:
                await self.bot.db.execute("UPDATE settings SET disabled=$1 WHERE settings.userid=$2", False, str(ctx.author.id))

        await ctx.send("✅ Highlight has been enabled", delete_after=10)

        await self.bot.db.execute("DELETE FROM todo WHERE todo.userid=$1 AND todo.event=$2", str(ctx.author.id), "enable")

        await asyncio.sleep(10)
        try:
            await ctx.message.delete()
        except:
            pass

    @commands.command(name="disable", description="Disable highlight", aliases=["dnd"])
    async def disable(self, ctx, *, time=None):
        parsed_time = self.parse_time(time)
        if time and not parsed_time:
            await ctx.send("❌ I couldn't parse your time, sorry", delete_after=10)

            await asyncio.sleep(10)
            try:
                await ctx.message.delete()
            except:
                pass

            return

        row = await self.bot.db.fetchrow("SELECT * FROM settings WHERE settings.userid=$1", str(ctx.author.id))

        if not row:
            await self.bot.db.execute("INSERT INTO settings (userid, disabled, timezone) VALUES ($1, $2, $3)", str(ctx.author.id), True, 0)
        
        else:
            if row[1]:
                await ctx.send("❌ Already disabled", delete_after=10)

                await asyncio.sleep(10)
                try:
                    await ctx.message.delete()
                except:
                    pass

                return
            
            else:
                await self.bot.db.execute("UPDATE settings SET disabled=$1 WHERE settings.userid=$2", True, str(ctx.author.id))
        
        await ctx.send("✅ Highlight has been disabled", delete_after=10)

        if parsed_time:
            await self.bot.db.execute("INSERT into todo (userid, time, event) VALUES ($1, $2, $3)", str(ctx.author.id), parsed_time, "enable")

        await asyncio.sleep(10)
        try:
            await ctx.message.delete()
        except:
            pass        

    @commands.command(name="timezone", description="Set your timezone", usage="[timezone]")
    async def timezone(self, ctx, timezone: int):
        if (await self.bot.db.fetch("SELECT COUNT(*) FROM settings WHERE settings.userid=$1", str(ctx.author.id)))[0][0] == 0:
            await self.bot.db.execute("INSERT INTO settings (userid, disabled, timezone) VALUES ($1, $2, $3)", str(ctx.author.id), False, timezone)
        
        else:
            await self.bot.db.execute("UPDATE settings SET timezone=$1 WHERE settings.userid=$2", timezone, str(ctx.author.id))

        await ctx.send("✅ Timezone saved", delete_after=10)

        await asyncio.sleep(10)
        try:
            await ctx.message.delete()
        except:
            pass

    @commands.command(name="info", description="Display info about your settings")
    async def info(self, ctx):

        settings = await self.bot.db.fetchrow("SELECT * FROM settings WHERE settings.userid=$1", str(ctx.author.id))
        
        if not settings:
            await ctx.send("You have default settings")

            await asyncio.sleep(10)
            try:
                await ctx.message.delete()
            except:
                pass

            return

        em = discord.Embed()
        em.set_author(name=ctx.author.display_name, icon_url=ctx.author.avatar_url)
        
        if settings[1]:
            em.description = "Highlight is currently disabled"

        em.add_field(name="Timezone", value=settings[2])

        await ctx.send(embed=em, delete_after=15)

        await asyncio.sleep(10)
        try:
            await ctx.message.delete()
        except:
            pass

def setup(bot):
    bot.add_cog(Highlight(bot))
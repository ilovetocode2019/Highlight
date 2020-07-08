import discord
from discord.ext import commands

import datetime
import asyncio

class Highlight(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener("on_message")
    async def on_message(self, message):
        if message.author.id == self.bot.user.id:
            return

        rows = None
        for word in self.bot.cached_words:
            if word in message.content:
                rows = await self.bot.db.fetch("SELECT * FROM words WHERE words.word=$1 AND words.guildid=$2", word, str(message.guild.id))
        
        if not rows or len(rows) == 0:
            return
        
        blocks = await self.bot.db.fetch("SELECT userid FROM blocks WHERE blocks.blockedid=$1", str(message.author.id))

        for row in rows:
            is_blocked = False
            for block in blocks:
                if block[0] == row[0]:
                    is_blocked = True
                    break

            if not is_blocked:
                user = message.guild.get_member(int(row[0]))
                if user != message.author:
                    em = discord.Embed(timestamp=datetime.datetime.now(), description=f"You got highlighted in {message.channel.mention}\n\n")
                    em.set_author(name=message.author.display_name, icon_url=message.author.avatar_url)
                    em.description += "\n\n".join([f"> {x.author} at {x.created_at.strftime('%H:%M:%S UTC')}: {x.content}" for x in await message.channel.history(limit=3).flatten()])
                    em.description += f"\n\n> {message.author} at {message.created_at.strftime('%H:%M:%S UTC')}: {message.content}"
                    link = f"https://discord.com/channels/{message.guild.id}/{message.channel.id}/{message.id}"
                    em.add_field(name="Jump", value=f"[Click]({link})")
                    await user.send(embed=em)
    
    @commands.guild_only()
    @commands.command(name="add", description="Adds a word (words guild specific)", usage="[word]")
    async def add(self, ctx, *, word):
        if (await self.bot.db.fetch("SELECT COUNT(*) FROM words WHERE words.userid=$1 AND words.guildid=$2 AND words.word=$3", str(ctx.author.id), str(ctx.guild.id), word))[0][0]:
            return await ctx.send("❌ You already have that word")
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
            return await ctx.send("❌ No words for this guild")

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
            return await ctx.send("This user is already blocked")

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
            return await ctx.send("This user is not blocked")

        await self.bot.db.execute("DELETE FROM blocks WHERE blocks.userid=$1 AND blocks.blockedid=$2", str(ctx.author.id), str(user.id))

        await ctx.send(f"✅ Unblocked {user.display_name}", delete_after=10)  

        await asyncio.sleep(10)
        try:
            await ctx.message.delete()
        except:
            pass

def setup(bot):
    bot.add_cog(Highlight(bot))
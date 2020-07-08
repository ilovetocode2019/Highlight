import discord
from discord.ext import commands

import traceback
import sys

class Meta(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="help", description="Help for highlight bot")
    async def help(self, ctx):
        em = discord.Embed(title="Highlight Help", description="Everything about highlight bot", color=discord.Colour.blurple())
        for command in self.bot.commands:
            if not command.hidden:
                em.add_field(name=command.name, value=command.description or "No description", inline=False)

        await ctx.send(embed=em)

    @commands.Cog.listener("on_command_error")
    async def on_command_error(self, ctx, e):
        error = "".join(traceback.format_exception(type(e), e, e.__traceback__, 1))
        print("Ignoring exception in command {}:".format(ctx.command), file=sys.stderr)
        traceback.print_exception(type(e), e, e.__traceback__, file=sys.stderr)
        
        if isinstance(e, discord.ext.commands.errors.CheckFailure):
            return
        elif isinstance(e, discord.ext.commands.errors.MissingRequiredArgument):
            return await ctx.send(f":x: You are missing a argument: `{e.param}`")
        elif isinstance(e, discord.ext.commands.errors.BadArgument):
            return await ctx.send(":x: You are giving a bad argument")
        elif isinstance(e, discord.ext.commands.errors.CommandOnCooldown):
            return await ctx.send(f"You are on cooldown. Try again in {e.retry_after} seconds")
        elif isinstance(e, discord.ext.commands.errors.CommandNotFound):
            return
        
        em = discord.Embed(title=":warning: Error :warning:", description=f"```{str(e)}```")

        await ctx.send(embed=em)

def setup(bot):
    bot.add_cog(Meta(bot))
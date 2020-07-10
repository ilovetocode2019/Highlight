import discord
from discord.ext import commands

import traceback
import sys

class Meta(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="help", description="Help for highlight bot", usage="<command>")
    async def help(self, ctx, command=None):
        if not command:
            em = discord.Embed(title="Highlight Help", description="I DM you if I see one of your words in the chat. I ignore the message if you reply.", color=discord.Colour.blurple())
            for x in self.bot.commands:
                if not x.hidden:
                    em.add_field(name=x.name, value=x.description or "No description", inline=False)
            em.set_footer(text=f"Use '@{self.bot.user} help [command]' for more info on a command")
        
        else:
            x = self.bot.get_command(name=command)
            if not x or x.hidden:
                return await ctx.send("❌ Command not found")

            em = discord.Embed(title=f"{x.name} {x.usage or ''}", description=f"{x.description or 'No description'}", color=discord.Colour.blurple())
            em.add_field(name="Aliases", value=", ".join(x.aliases) or "No aliases")
        await ctx.send(embed=em)

    @commands.command(name="invite", description="Get a invite link to add me to your server")
    async def invite(self, ctx):
        perms = discord.Permissions.none()
        perms.manage_messages = True
        await ctx.send(f"<{discord.utils.oauth_url(self.bot.user.id, permissions=perms)}>")

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
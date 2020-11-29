import discord
from discord.ext import commands

import traceback
import sys
import datetime
import humanize

class HighlightHelpCommand(commands.HelpCommand):
    async def send_bot_help(self, mapping):
        ctx = self.context
        bot = ctx.bot

        em = discord.Embed(title=f"{bot.user.name} Help", description=f"{bot.description}\n\n", color=discord.Color.blurple())
        em.set_thumbnail(url=bot.user.avatar_url)

        commands = await self.filter_commands(bot.commands)
        for command in commands:
            em.description += f"`{self.get_command_signature(command)}` {f'- {command.description}' if command.description else ''}\n"

        await ctx.send(embed=em)

    async def send_cog_help(self, cog):
        ctx = self.context
        bot = ctx.bot

        em = discord.Embed(title=f"{bot.user.name} Help", description=f"{bot.description}\n\n", color=discord.Color.blurple())
        em.set_thumbnail(url=bot.user.avatar_url)

        commands = await self.filter_commands(cog.get_commands())
        for command in commands:
            em.description += f"`{self.get_command_signature(command)}` {f'- {command.description}' if command.description else ''}\n"

        await ctx.send(embed=em)

    async def send_command_help(self, command):
        ctx = self.context
        bot = ctx.bot

        em = discord.Embed(title=command.name, description=command.description or "")
        em.set_thumbnail(url=bot.user.avatar_url)

        if command.aliases:
            em.description += f"\nAliases: {', '.join(command.aliases)}"

        await ctx.send(embed=em)

    async def send_group_help(self, group):
        ctx = self.context
        bot = ctx.bot

        em = discord.Embed(title=group.name, description=group.description or "")
        em.set_thumbnail(url=bot.user.avatar_url)

        if group.aliases:
            em.description += f"\nAliases: {', '.join(group.aliases)}\n"

        commands = await self.filter_commands(group.commands)
        for command in commands:
            em.description += f"`{self.get_command_signature(command)}` {f'- {command.description}' if command.description else ''}\n"

        await ctx.send(embed=em)


class Meta(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

        self._original_help_command = bot.help_command
        bot.help_command = HighlightHelpCommand()
        bot.help_command.cog = self

    def cog_unload(self):
        self.bot.help_command = self._original_help_command

    @commands.command(name="invite", description="Get a invite link to add me to your server")
    async def invite(self, ctx):
        perms = discord.Permissions.none()
        perms.manage_messages = True
        await ctx.send(f"<{discord.utils.oauth_url(self.bot.user.id, permissions=perms)}>")

    @commands.command(name="ping", description="Check my latency")
    async def ping(self, ctx):
        await ctx.send(f"My latency is {int(self.bot.latency*1000)}ms")

    @commands.command(name="uptime", description="Check my uptime")
    async def uptime(self, ctx):
        delta = datetime.datetime.utcnow()-self.bot.startup_time
        await ctx.send(f"I started up {humanize.naturaldelta(delta)} ago")

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

        if isinstance(e, commands.CommandInvokeError):
            em = discord.Embed(title=":warning: Error", description="", color=discord.Color.gold(), timestamp=datetime.datetime.utcnow())
            em.description += f"\nCommand: `{ctx.command}`"
            em.description += f"\nLink: [Jump]({ctx.message.jump_url})"
            em.description += f"\n\n```py\n{e}```\n"

            await self.bot.console.send(embed=em)

def setup(bot):
    bot.add_cog(Meta(bot))

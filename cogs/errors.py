import discord
from discord.ext import commands

# ── Colors ──────────────────────────────────────────────────
RED    = 0xFFBFEA
ORANGE = 0xFFBFEA
YELLOW = 0xFFBFEA
DARK   = 0xFFBFEA

# ── Custom Emojis ────────────────────────────────────────────
CROSS = "<:cross:1514194117985570888>"
TICK  = "<:tick:1514194122192191569>"
ARROW = "<:right:1513879374741639248>"
WARN  = "<:Warn:1513884025998020638>"


class Errors(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    def _base_embed(self, title: str, description: str, color: int, ctx) -> discord.Embed:
        """Returns a styled embed with bot pfp as thumbnail."""
        embed = discord.Embed(
            title=title,
            description=description,
            color=color
        )
        embed.set_thumbnail(url=self.bot.user.display_avatar.url)
        embed.set_footer(
            text=f"Triggered by {ctx.author}",
            icon_url=ctx.author.display_avatar.url
        )
        return embed

    async def send_error(self, ctx, description: str, title: str = "Error", color: int = RED):
        embed = self._base_embed(f"{CROSS}  {title}", description, color, ctx)
        await ctx.reply(embed=embed, mention_author=False)

    async def send_warning(self, ctx, description: str, title: str = "Warning"):
        embed = self._base_embed(f"{WARN}  {title}", description, YELLOW, ctx)
        await ctx.reply(embed=embed, mention_author=False)

    # ── Main Error Listener ──────────────────────────────────
    @commands.Cog.listener()
    async def on_command_error(self, ctx, error):

        if hasattr(ctx.command, "on_error"):
            return

        error = getattr(error, "original", error)

        # ── Silent ignore ────────────────────────────────────
        if isinstance(error, commands.CommandNotFound):
            return

        # ── Permissions ──────────────────────────────────────
        elif isinstance(error, commands.MissingPermissions):
            perms = "\n".join(
                f"{ARROW} `{p.replace('_', ' ').title()}`"
                for p in error.missing_permissions
            )
            return await self.send_error(
                ctx,
                f"You don't have the required permissions to run this command.\n\n**Missing:**\n{perms}",
                title="Missing Permissions"
            )

        elif isinstance(error, commands.BotMissingPermissions):
            perms = "\n".join(
                f"{ARROW} `{p.replace('_', ' ').title()}`"
                for p in error.missing_permissions
            )
            return await self.send_error(
                ctx,
                f"I'm missing some permissions needed to execute this command.\n\n**Required:**\n{perms}",
                title="Bot Missing Permissions"
            )

        # ── Arguments ────────────────────────────────────────
        elif isinstance(error, commands.MissingRequiredArgument):
            return await self.send_error(
                ctx,
                f"A required argument was not provided.\n\n{ARROW} **Missing:** `{error.param.name}`\n\n"
                f"Use `help {ctx.command}` to see correct usage.",
                title="Missing Argument"
            )

        elif isinstance(error, commands.BadArgument):
            return await self.send_error(
                ctx,
                f"One or more arguments are invalid.\n\n"
                f"Use `help {ctx.command}` to see correct usage.",
                title="Invalid Argument"
            )

        elif isinstance(error, commands.BadUnionArgument):
            return await self.send_error(
                ctx,
                f"Could not convert `{error.param.name}` to a valid value.\n\n"
                f"Use `help {ctx.command}` to see correct usage.",
                title="Invalid Value"
            )

        # ── Not Found ────────────────────────────────────────
        elif isinstance(error, commands.MemberNotFound):
            return await self.send_error(
                ctx,
                f"Couldn't find that member in this server.\n\n"
                f"{ARROW} Make sure you mentioned them correctly.",
                title="Member Not Found"
            )

        elif isinstance(error, commands.UserNotFound):
            return await self.send_error(
                ctx,
                f"Couldn't find that user.\n\n"
                f"{ARROW} Try using their ID instead.",
                title="User Not Found"
            )

        elif isinstance(error, commands.RoleNotFound):
            return await self.send_error(
                ctx,
                f"Couldn't find that role in this server.\n\n"
                f"{ARROW} Make sure the role name or ID is correct.",
                title="Role Not Found"
            )

        elif isinstance(error, commands.ChannelNotFound):
            return await self.send_error(
                ctx,
                f"Couldn't find that channel.\n\n"
                f"{ARROW} Make sure you mentioned it correctly.",
                title="Channel Not Found"
            )

        elif isinstance(error, commands.MessageNotFound):
            return await self.send_error(
                ctx,
                f"Couldn't find that message.\n\n"
                f"{ARROW} It may have been deleted.",
                title="Message Not Found"
            )

        # ── Cooldown ─────────────────────────────────────────
        elif isinstance(error, commands.CommandOnCooldown):
            return await self.send_warning(
                ctx,
                f"You're using commands too fast!\n\n"
                f"{ARROW} Try again in **{round(error.retry_after, 1)}s**.",
                title="Slow Down!"
            )

        # ── Access ───────────────────────────────────────────
        elif isinstance(error, commands.NotOwner):
            return await self.send_error(
                ctx,
                f"Only the **bot owner** can use this command.",
                title="Owner Only"
            )

        elif isinstance(error, commands.NoPrivateMessage):
            return await self.send_error(
                ctx,
                f"This command can only be used inside a **server**, not in DMs.",
                title="Server Only"
            )

        elif isinstance(error, commands.PrivateMessageOnly):
            return await self.send_error(
                ctx,
                f"This command can only be used in **DMs**.",
                title="DM Only"
            )

        elif isinstance(error, commands.NSFWChannelRequired):
            return await self.send_error(
                ctx,
                f"This command requires an **NSFW channel**.\n\n"
                f"{ARROW} Head to an age-restricted channel and try again.",
                title="NSFW Required"
            )

        # ── Unexpected ───────────────────────────────────────
        print(f"[ERROR] Command: {ctx.command} | Error: {error}")

        embed = self._base_embed(
            title=f"{CROSS}  Unexpected Error",
            description=(
                f"Something went wrong while running `{ctx.command}`.\n\n"
                f"{ARROW} This has been logged. Please try again later."
            ),
            color=DARK,
            ctx=ctx
        )
        await ctx.reply(embed=embed, mention_author=False)


async def setup(bot):
    await bot.add_cog(Errors(bot))
import discord
from discord.ext import commands, tasks
from discord import app_commands
from datetime import datetime


EMBED_COLOR = 0xFFFFFF
BRAND_COLOR = 0xFFB6C1
SUCCESS_COLOR = 0x57F287
ERROR_COLOR = 0xFFBFEA
WARNING_COLOR = 0xFFBFEA
INFO_COLOR = 0x5865F2

YOUTUBE_URL = "https://drive.google.com/drive/folders/1fJjL-w0f9FEenJoiZCkRaq8NPHVWxIjw"

PASTELSTAR = "🌟"
LEAF = "🍀"
CROSS = "❌"
TICK = "✅"
ARROW = "⏩"
WARN = "🚨"

SEC_CONFIG = "🌀"
SEC_WHITELIST = "◽"
SEC_RESTRICT = "🚧"
SEC_AI = "✨"

PLACEHOLDERS = {
    "{user}": lambda member, guild: member.mention,
    "{username}": lambda member, guild: str(member),
    "{displayname}": lambda member, guild: member.display_name,
    "{server}": lambda member, guild: guild.name,
    "{membercount}": lambda member, guild: str(guild.member_count),
    "{userid}": lambda member, guild: str(member.id),
    "{joined}": lambda member, guild: discord.utils.format_dt(member.joined_at or datetime.utcnow(), style="D"),
    "{created}": lambda member, guild: discord.utils.format_dt(member.created_at, style="D"),
}


def resolve_placeholders(text: str, member: discord.Member, guild: discord.Guild) -> str:
    if not text:
        return text
    for token, resolver in PLACEHOLDERS.items():
        if token in text:
            text = text.replace(token, resolver(member, guild))
    return text


def placeholder_list() -> str:
    descriptions = {
        "{user}": "Mentions the user  →  @Yuvraj",
        "{username}": "Full username       →  Yuvraj#0001",
        "{displayname}": "Server nickname     →  Yuvraj",
        "{server}": "Server name         →  My Awesome Server",
        "{membercount}": "Total member count  →  1,234",
        "{userid}": "User's Discord ID   →  123456789",
        "{joined}": "Join date           →  June 11, 2026",
        "{created}": "Account created     →  January 1, 2020",
    }
    return "\n".join(f"`{k}` — {v}" for k, v in descriptions.items())


def make_embed(
    title: str = None,
    description: str = None,
    color: int = BRAND_COLOR,
    footer: str = None,
    thumbnail: str = None,
    image: str = None,
    author_name: str = None,
    author_icon: str = None,
    timestamp: bool = False,
    fields: list = None,
) -> discord.Embed:
    embed = discord.Embed(title=title, description=description, color=color)
    if timestamp:
        embed.timestamp = datetime.utcnow()
    if footer:
        embed.set_footer(text=footer)
    if thumbnail:
        embed.set_thumbnail(url=thumbnail)
    if image:
        embed.set_image(url=image)
    if author_name:
        embed.set_author(name=author_name, icon_url=author_icon or discord.embeds.EmptyEmbed)
    if fields:
        for name, value, inline in fields:
            embed.add_field(name=name, value=value, inline=inline)
    return embed


def success_embed(description: str, title: str = f"{TICK}  Success") -> discord.Embed:
    return make_embed(title=title, description=description, color=SUCCESS_COLOR)


def error_embed(description: str, title: str = f"{CROSS}  Error") -> discord.Embed:
    return make_embed(title=title, description=description, color=ERROR_COLOR)


def info_embed(description: str, title: str = f"{PASTELSTAR}  Info") -> discord.Embed:
    return make_embed(title=title, description=description, color=INFO_COLOR)


def is_admin(member: discord.Member) -> bool:
    return member.guild_permissions.administrator


def build_index_embed(bot: commands.Bot) -> discord.Embed:
    embed = discord.Embed(color=EMBED_COLOR)
    embed.add_field(
        name=f"{PASTELSTAR}  Welcome to Shouffle",
        value=(
            "Use `/` or `?` for existing commands information. "
            "See all the commands by selecting drop-down menu or visit support server for any kind of guidance"
        ),
        inline=False,
    )
    embed.add_field(
        name=f"{PASTELSTAR} Additional Info",
        value=(
            f"> - [Support Server](<https://discord.gg/Jgkrre2GW>)\n"
            f"> - [Beginner Tutorials]({YOUTUBE_URL})"
        ),
        inline=False,
    )
    if bot.user and bot.user.avatar:
        embed.set_thumbnail(url=bot.user.avatar.url)
    return embed


def build_general_utility_embed() -> discord.Embed:
    embed = discord.Embed(
        title=f"{PASTELSTAR}  General & Utility Commands",
        color=EMBED_COLOR,
    )
    embed.add_field(
        name="Regular commands",
        value="ping, uptime, userinfo, serverinfo, roleinfo, membercount, inviteinfo, emojiinfo, avatar, banner, 8ball, roll, coinflip, choose, calculate, say, embed, poll, snipe, steal, afk, afkremove, stick, stickremove, autoresponder, removeresponder, listresponders, gcreate, gend, greroll, kick, ban, softban, unban, mute, unmute, deafen, undeafen, warn, warns, clearwarns, purge, slowmode, nick, lock, unlock, roleadd, roleremove, mediaonly, unmediaonly",
        inline=False,
    )
    embed.add_field(
        name="Alias",
        value="whois, ui, si, timeout, untimeout, rr",
        inline=False,
    )
    embed.set_footer(text="Developed by Yuvraj Ab")
    return embed


def build_server_management_embed() -> discord.Embed:
    embed = discord.Embed(
        title=f"{PASTELSTAR}  Server Management Commands",
        color=EMBED_COLOR,
    )
    embed.add_field(
        name="Setup Commands",
        value="ticketsetup, ticketconfig, ticketadd, ticketremove, ticketlist, ticketclose, welcomesetup, welcomeconfig, welcomechannel, welcometest, vcsetup, vcpanel, vcban, botlogs enable, botlogs disable, reactionrole, reactionroleconfig etc",
        inline=False,
    )
    embed.set_footer(text="Crafted by Yuvraj ab")
    return embed


def build_security_embed() -> discord.Embed:
    embed = discord.Embed(
        title="✦  Shouffle Security",
        description=(
            "Take full control of your server's safety with **Shouffle Security** — "
            "a premium protection system built for serious communities.\n\u200b"
        ),
        color=0xB0C4DE,
    )
    embed.add_field(
        name="What's Included",
        value=(
            f"> {SEC_CONFIG}  **Password-protected dashboard for full control**\n"
            f"> {SEC_WHITELIST}  **Smart whitelist for trusted members**\n"
            f"> {SEC_RESTRICT}  **Auto protection against raids & abuse**\n"
            f"> {SEC_AI}  **AI-powered message scanning in real time**"
        ),
        inline=False,
    )
    embed.add_field(
        name="Pricing",
        value="> Starting at just **₹49 / month** — cancel anytime.",
        inline=False,
    )
    embed.add_field(
        name="Get Started",
        value="> Protect your server with the cost of 1 burger",
        inline=False,
    )
    embed.set_footer(text="Shouffle Premium")
    return embed


class HelpDropdown(discord.ui.Select):
    def __init__(self):
        options = [
            discord.SelectOption(
                label="General & Utility",
                description="Help, ping, giveaways, AFK, and more",
                emoji="<:pastelstar:1517787024306733206>",
                value="general",
            ),
            discord.SelectOption(
                label="Server Management",
                description="Moderation, logging, automod, tickets, and more",
                emoji="<:leaf:1515660279944319006>",
                value="server",
            ),
            discord.SelectOption(
                label="Dynamic Security",
                description="AI scanning, raid protection, whitelists & more",
                emoji="<:securityconfig:1519799386736033812>",
                value="security",
            ),
        ]
        super().__init__(
            placeholder="Browse command categories...",
            min_values=1,
            max_values=1,
            options=options,
        )

    async def callback(self, interaction: discord.Interaction):
        if self.values[0] == "general":
            embed = build_general_utility_embed()
            await interaction.response.edit_message(embed=embed, view=self.view)
        elif self.values[0] == "server":
            embed = build_server_management_embed()
            await interaction.response.edit_message(embed=embed, view=self.view)
        else:
            embed = build_security_embed()
            view = SecurityHelpView(self.view.index_embed)
            await interaction.response.edit_message(embed=embed, view=view)


class HelpView(discord.ui.View):
    def __init__(self, index_embed: discord.Embed):
        super().__init__(timeout=120)
        self.index_embed = index_embed
        self.add_item(HelpDropdown())

    @discord.ui.button(label="Home", style=discord.ButtonStyle.secondary, emoji="🏠", row=1)
    async def home_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(embed=self.index_embed, view=self)


class SecurityHelpView(discord.ui.View):
    def __init__(self, index_embed: discord.Embed):
        super().__init__(timeout=120)
        self.index_embed = index_embed
        self.add_item(HelpDropdown())
        self.add_item(
            discord.ui.Button(
                label="Unlock Security",
                style=discord.ButtonStyle.link,
                url="https://example.com/buy",
                emoji="<:securityconfig:1519799386736033812>",
                row=1,
            )
        )

    @discord.ui.button(label="Home", style=discord.ButtonStyle.secondary, emoji="🏠", row=1)
    async def home_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(embed=self.index_embed, view=HelpView(self.index_embed))


class Help(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    def build_help(self, bot: commands.Bot):
        embed = build_index_embed(bot)
        view = HelpView(embed)
        return embed, view

    @commands.command(name="help")
    async def help_prefix(self, ctx: commands.Context):
        embed, view = self.build_help(ctx.bot)
        await ctx.send(embed=embed, view=view)

    @app_commands.command(name="help", description="Learn how to use Shouffle")
    async def help_slash(self, interaction: discord.Interaction):
        embed, view = self.build_help(interaction.client)
        await interaction.response.send_message(embed=embed, view=view)


class Status(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.current_status = 0
        self.statuses = [
            discord.Activity(type=discord.ActivityType.listening, name="Made with Love and Safety"),
            discord.Game(name="Developed by Yuvraj Ab"),
            discord.Activity(type=discord.ActivityType.watching, name="Commands List /help"),
        ]

    @commands.Cog.listener()
    async def on_ready(self):
        if not self.rotate_status.is_running():
            self.rotate_status.start()
        print("Status system loaded.")

    @tasks.loop(seconds=15)
    async def rotate_status(self):
        await self.bot.change_presence(
            status=discord.Status.online,
            activity=self.statuses[self.current_status],
        )
        self.current_status = (self.current_status + 1) % len(self.statuses)

    @rotate_status.before_loop
    async def before_rotate_status(self):
        await self.bot.wait_until_ready()


class Errors(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    def _base_embed(self, title: str, description: str, color: int, ctx) -> discord.Embed:
        embed = discord.Embed(title=title, description=description, color=color)
        embed.set_thumbnail(url=self.bot.user.display_avatar.url)
        embed.set_footer(
            text=f"Triggered by {ctx.author}",
            icon_url=ctx.author.display_avatar.url,
        )
        return embed

    async def send_error(self, ctx, description: str, title: str = "Error", color: int = ERROR_COLOR):
        embed = self._base_embed(f"{CROSS}  {title}", description, color, ctx)
        await ctx.reply(embed=embed, mention_author=False)

    async def send_warning(self, ctx, description: str, title: str = "Warning"):
        embed = self._base_embed(f"{WARN}  {title}", description, WARNING_COLOR, ctx)
        await ctx.reply(embed=embed, mention_author=False)

    @commands.Cog.listener()
    async def on_command_error(self, ctx, error):
        if hasattr(ctx.command, "on_error"):
            return

        error = getattr(error, "original", error)

        if isinstance(error, commands.CommandNotFound):
            return

        elif isinstance(error, commands.MissingPermissions):
            perms = "\n".join(
                f"{ARROW} `{p.replace('_', ' ').title()}`"
                for p in error.missing_permissions
            )
            return await self.send_error(
                ctx,
                f"You don't have the required permissions to run this command.\n\n**Missing:**\n{perms}",
                title="Missing Permissions",
            )

        elif isinstance(error, commands.BotMissingPermissions):
            perms = "\n".join(
                f"{ARROW} `{p.replace('_', ' ').title()}`"
                for p in error.missing_permissions
            )
            return await self.send_error(
                ctx,
                f"I'm missing some permissions needed to execute this command.\n\n**Required:**\n{perms}",
                title="Bot Missing Permissions",
            )

        elif isinstance(error, commands.MissingRequiredArgument):
            return await self.send_error(
                ctx,
                f"A required argument was not provided.\n\n{ARROW} **Missing:** `{error.param.name}`\n\n"
                f"Use `help {ctx.command}` to see correct usage.",
                title="Missing Argument",
            )

        elif isinstance(error, commands.BadArgument):
            return await self.send_error(
                ctx,
                f"One or more arguments are invalid.\n\nUse `help {ctx.command}` to see correct usage.",
                title="Invalid Argument",
            )

        elif isinstance(error, commands.BadUnionArgument):
            return await self.send_error(
                ctx,
                f"Could not convert `{error.param.name}` to a valid value.\n\nUse `help {ctx.command}` to see correct usage.",
                title="Invalid Value",
            )

        elif isinstance(error, commands.MemberNotFound):
            return await self.send_error(
                ctx,
                f"Couldn't find that member in this server.\n\n{ARROW} Make sure you mentioned them correctly.",
                title="Member Not Found",
            )

        elif isinstance(error, commands.UserNotFound):
            return await self.send_error(
                ctx,
                f"Couldn't find that user.\n\n{ARROW} Try using their ID instead.",
                title="User Not Found",
            )

        elif isinstance(error, commands.RoleNotFound):
            return await self.send_error(
                ctx,
                f"Couldn't find that role in this server.\n\n{ARROW} Make sure the role name or ID is correct.",
                title="Role Not Found",
            )

        elif isinstance(error, commands.ChannelNotFound):
            return await self.send_error(
                ctx,
                f"Couldn't find that channel.\n\n{ARROW} Make sure you mentioned it correctly.",
                title="Channel Not Found",
            )

        elif isinstance(error, commands.MessageNotFound):
            return await self.send_error(
                ctx,
                f"Couldn't find that message.\n\n{ARROW} It may have been deleted.",
                title="Message Not Found",
            )

        elif isinstance(error, commands.CommandOnCooldown):
            return await self.send_warning(
                ctx,
                f"You're using commands too fast!\n\n{ARROW} Try again in **{round(error.retry_after, 1)}s**.",
                title="Slow Down!",
            )

        elif isinstance(error, commands.NotOwner):
            return await self.send_error(
                ctx,
                f"Only the **bot owner** can use this command.",
                title="Owner Only",
            )

        elif isinstance(error, commands.NoPrivateMessage):
            return await self.send_error(
                ctx,
                f"This command can only be used inside a **server**, not in DMs.",
                title="Server Only",
            )

        elif isinstance(error, commands.PrivateMessageOnly):
            return await self.send_error(
                ctx,
                f"This command can only be used in **DMs**.",
                title="DM Only",
            )

        elif isinstance(error, commands.NSFWChannelRequired):
            return await self.send_error(
                ctx,
                f"This command requires an **NSFW channel**.\n\n{ARROW} Head to an age-restricted channel and try again.",
                title="NSFW Required",
            )

        print(f"[ERROR] Command: {ctx.command} | Error: {error}")

        embed = self._base_embed(
            title=f"{CROSS}  Unexpected Error",
            description=(
                f"Something went wrong while running `{ctx.command}`.\n\n"
                f"{ARROW} This has been logged. Please try again later."
            ),
            color=ERROR_COLOR,
            ctx=ctx,
        )
        await ctx.reply(embed=embed, mention_author=False)


async def setup(bot: commands.Bot):
    await bot.add_cog(Help(bot))
    await bot.add_cog(Status(bot))
    await bot.add_cog(Errors(bot))

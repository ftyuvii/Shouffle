import asyncio
import json
import os
import random
import re
from datetime import datetime, timedelta, timezone

import aiohttp
import discord
from discord import app_commands
from discord.ext import commands, tasks

COLOUR      = 0xFFBFEA
COLOUR_OK   = 0xFFBFEA
COLOUR_ERR  = 0xFFBFEA
COLOUR_WARN = 0xFFBFEA

DATA_DIR      = "data"
AFK_FILE      = os.path.join(DATA_DIR, "afk.json")
STICKY_FILE   = os.path.join(DATA_DIR, "sticky.json")
GIVEAWAY_FILE = os.path.join(DATA_DIR, "giveaways.json")
AR_FILE       = os.path.join(DATA_DIR, "autoresponders.json")
MEDIA_FILE    = os.path.join(DATA_DIR, "mediaonly.json")


def _ensure_data_dir() -> None:
    os.makedirs(DATA_DIR, exist_ok=True)


def _load(path: str, default=None):
    if default is None:
        default = {}
    if not os.path.exists(path):
        return default
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def _save(path: str, data) -> None:
    _ensure_data_dir()
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def parse_time(s: str) -> int:
    units = {"s": 1, "m": 60, "h": 3600, "d": 86400}
    s = s.strip().lower()
    if s and s[-1] in units:
        try:
            return int(s[:-1]) * units[s[-1]]
        except ValueError:
            pass
    return -1


def fmt_time(seconds: int) -> str:
    d, r = divmod(int(seconds), 86400)
    h, r = divmod(r, 3600)
    m, s = divmod(r, 60)
    parts = []
    if d:
        parts.append(f"{d}d")
    if h:
        parts.append(f"{h}h")
    if m:
        parts.append(f"{m}m")
    if s:
        parts.append(f"{s}s")
    return " ".join(parts) or "0s"


class General(commands.Cog):

    _snipe_cache: dict[int, dict] = {}
    _start_time: datetime = datetime.now(timezone.utc)

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        _ensure_data_dir()
        self._afk: dict       = _load(AFK_FILE)
        self._sticky: dict    = _load(STICKY_FILE)
        self._giveaways: dict = _load(GIVEAWAY_FILE)
        self._check_giveaways.start()

    def cog_unload(self) -> None:
        self._check_giveaways.cancel()

    def _embed(
        self,
        title: str = None,
        description: str = None,
        colour: int = COLOUR,
        *,
        thumbnail: str = None,
        image: str = None,
        requester: discord.Member = None,
        timestamp: datetime = None,
    ) -> discord.Embed:
        e = discord.Embed(title=title, description=description, color=colour)
        if timestamp:
            e.timestamp = timestamp
        if thumbnail:
            e.set_thumbnail(url=thumbnail)
        if image:
            e.set_image(url=image)
        bot_avatar = self.bot.user.display_avatar.url if self.bot.user else None
        if requester and bot_avatar:
            e.set_footer(
                text=f"{self.bot.user.name} • Requested by {requester}",
                icon_url=bot_avatar,
            )
        elif bot_avatar:
            e.set_footer(text=self.bot.user.name, icon_url=bot_avatar)
        return e

    def _err(self, description: str) -> discord.Embed:
        return self._embed(
            description=f"<:cross:1514194117985570888> {description}",
            colour=COLOUR_ERR,
        )

    def _ok(self, title: str, description: str = None) -> discord.Embed:
        return self._embed(
            title=f"<:tick:1514194122192191569> {title}",
            description=description,
            colour=COLOUR_OK,
        )

    @commands.command(name="ping")
    async def ping(self, ctx: commands.Context) -> None:
        latency = round(self.bot.latency * 1000)
        bar = "█" * min(latency // 20, 10) + "░" * (10 - min(latency // 20, 10))
        colour = COLOUR_OK if latency < 100 else (COLOUR_WARN if latency < 200 else COLOUR_ERR)
        e = self._embed(
            "<:Bot:1514196657644765205> Pong!",
            f"**<:rightarrow:1515660270557466685> Latency:** `{latency}ms`\n"
            f"**<:rightarrow:1515660270557466685> API:** `{round(self.bot.latency * 1000)}ms`\n"
            f"`{bar}`",
            colour=colour,
            requester=ctx.author,
        )
        await ctx.send(embed=e)

    @app_commands.command(name="ping", description="Check the bot's latency.")
    async def ping_slash(self, interaction: discord.Interaction) -> None:
        latency = round(self.bot.latency * 1000)
        bar = "█" * min(latency // 20, 10) + "░" * (10 - min(latency // 20, 10))
        colour = COLOUR_OK if latency < 100 else (COLOUR_WARN if latency < 200 else COLOUR_ERR)
        e = self._embed(
            "<:Bot:1514196657644765205> Pong!",
            f"**<:rightarrow:1515660270557466685> Latency:** `{latency}ms`\n"
            f"**<:rightarrow:1515660270557466685> API:** `{round(self.bot.latency * 1000)}ms`\n"
            f"`{bar}`",
            colour=colour,
            requester=interaction.user,
        )
        await interaction.response.send_message(embed=e)

    @commands.command(name="uptime")
    async def uptime(self, ctx: commands.Context) -> None:
        delta = datetime.now(timezone.utc) - General._start_time
        await ctx.send(embed=self._embed(
            description=f"<:leaf:1515660279944319006> Online for **{fmt_time(int(delta.total_seconds()))}**",
            colour=COLOUR_OK,
            requester=ctx.author,
        ))

    @app_commands.command(name="uptime", description="See how long the bot has been online.")
    async def uptime_slash(self, interaction: discord.Interaction) -> None:
        delta = datetime.now(timezone.utc) - General._start_time
        await interaction.response.send_message(embed=self._embed(
            description=f"<:leaf:1515660279944319006> Online for **{fmt_time(int(delta.total_seconds()))}**",
            colour=COLOUR_OK,
            requester=interaction.user,
        ))

    @commands.command(name="botinfo", aliases=["about"])
    async def botinfo(self, ctx: commands.Context) -> None:
        bot = self.bot
        e = discord.Embed(title=f"<:Bot:1514196657644765205> {bot.user}", color=COLOUR)
        if bot.user.avatar:
            e.set_thumbnail(url=bot.user.avatar.url)
        e.add_field(name="<:Home:1514196660228718713> Servers",  value=len(bot.guilds),                                                                              inline=True)
        e.add_field(name="<:Communie:1514196655233040455> Users",    value=sum(g.member_count or 0 for g in bot.guilds),                                                 inline=True)
        e.add_field(name="<:rightarrow:1515660270557466685> Latency",  value=f"{round(bot.latency * 1000)}ms",                                                             inline=True)
        e.add_field(name="<:leaf:1515660279944319006> Uptime",   value=fmt_time(int((datetime.now(timezone.utc) - General._start_time).total_seconds())),            inline=True)
        e.add_field(name="<:Python:1513879400544731236> Library",  value=f"discord.py {discord.__version__}",                                                          inline=True)
        await ctx.send(embed=e)

    @app_commands.command(name="botinfo", description="View information about the bot.")
    async def botinfo_slash(self, interaction: discord.Interaction) -> None:
        bot = self.bot
        e = discord.Embed(title=f"<:Bot:1514196657644765205> {bot.user}", color=COLOUR)
        if bot.user.avatar:
            e.set_thumbnail(url=bot.user.avatar.url)
        e.add_field(name="<:Home:1514196660228718713> Servers",  value=len(bot.guilds),                                                                              inline=True)
        e.add_field(name="<:Communie:1514196655233040455> Users",    value=sum(g.member_count or 0 for g in bot.guilds),                                                 inline=True)
        e.add_field(name="<:rightarrow:1515660270557466685> Latency",  value=f"{round(bot.latency * 1000)}ms",                                                             inline=True)
        e.add_field(name="<:leaf:1515660279944319006> Uptime",   value=fmt_time(int((datetime.now(timezone.utc) - General._start_time).total_seconds())),            inline=True)
        e.add_field(name="<:Python:1513879400544731236> Library",  value=f"discord.py {discord.__version__}",                                                          inline=True)
        await interaction.response.send_message(embed=e)

    @commands.command(name="roleinfo", aliases=["ri"])
    @commands.guild_only()
    async def roleinfo(self, ctx: commands.Context, *, role: discord.Role) -> None:
        e = discord.Embed(title=f"<:shield:1515660276270239804> {role.name}", color=role.color)
        e.add_field(name="ID",          value=role.id,                                        inline=True)
        e.add_field(name="Color",       value=str(role.color),                                inline=True)
        e.add_field(name="Members",     value=len(role.members),                              inline=True)
        e.add_field(name="Mentionable", value="Yes" if role.mentionable else "No",            inline=True)
        e.add_field(name="Hoisted",     value="Yes" if role.hoist else "No",                  inline=True)
        e.add_field(name="Position",    value=role.position,                                  inline=True)
        e.add_field(name="Created",     value=discord.utils.format_dt(role.created_at, "R"),  inline=True)
        await ctx.send(embed=e)

    @app_commands.command(name="roleinfo", description="View information about a role.")
    @app_commands.guild_only()
    async def roleinfo_slash(self, interaction: discord.Interaction, role: discord.Role) -> None:
        e = discord.Embed(title=f"<:shield:1515660276270239804> {role.name}", color=role.color)
        e.add_field(name="ID",          value=role.id,                                        inline=True)
        e.add_field(name="Color",       value=str(role.color),                                inline=True)
        e.add_field(name="Members",     value=len(role.members),                              inline=True)
        e.add_field(name="Mentionable", value="Yes" if role.mentionable else "No",            inline=True)
        e.add_field(name="Hoisted",     value="Yes" if role.hoist else "No",                  inline=True)
        e.add_field(name="Position",    value=role.position,                                  inline=True)
        e.add_field(name="Created",     value=discord.utils.format_dt(role.created_at, "R"),  inline=True)
        await interaction.response.send_message(embed=e)

    @commands.command(name="membercount", aliases=["mc", "members"])
    @commands.guild_only()
    async def member_count(self, ctx: commands.Context) -> None:
        guild = ctx.guild
        await guild.chunk()
        total  = guild.member_count
        humans = sum(1 for m in guild.members if not m.bot)
        bots   = sum(1 for m in guild.members if m.bot)
        online = sum(1 for m in guild.members if m.status != discord.Status.offline)
        e = discord.Embed(title=f"📊 {guild.name} — Member Count", color=COLOUR)
        e.add_field(name="👥 Total",  value=f"**{total}**",  inline=True)
        e.add_field(name="🧑 Humans", value=f"**{humans}**", inline=True)
        e.add_field(name="🤖 Bots",   value=f"**{bots}**",   inline=True)
        e.add_field(name="🟢 Online", value=f"**{online}**", inline=True)
        if guild.icon:
            e.set_thumbnail(url=guild.icon.url)
        await ctx.send(embed=e)

    @app_commands.command(name="membercount", description="View the member count for this server.")
    @app_commands.guild_only()
    async def member_count_slash(self, interaction: discord.Interaction) -> None:
        guild = interaction.guild
        await guild.chunk()
        total  = guild.member_count
        humans = sum(1 for m in guild.members if not m.bot)
        bots   = sum(1 for m in guild.members if m.bot)
        online = sum(1 for m in guild.members if m.status != discord.Status.offline)
        e = discord.Embed(title=f"📊 {guild.name} — Member Count", color=COLOUR)
        e.add_field(name="👥 Total",  value=f"**{total}**",  inline=True)
        e.add_field(name="🧑 Humans", value=f"**{humans}**", inline=True)
        e.add_field(name="🤖 Bots",   value=f"**{bots}**",   inline=True)
        e.add_field(name="🟢 Online", value=f"**{online}**", inline=True)
        if guild.icon:
            e.set_thumbnail(url=guild.icon.url)
        await interaction.response.send_message(embed=e)

    @commands.command(name="inviteinfo", aliases=["invites"])
    @commands.guild_only()
    @commands.has_permissions(manage_guild=True)
    async def inviteinfo(self, ctx: commands.Context) -> None:
        invites = await ctx.guild.invites()
        if not invites:
            await ctx.send(embed=self._err("No active invites found."))
            return
        lines = []
        for inv in sorted(invites, key=lambda i: i.uses or 0, reverse=True)[:15]:
            inviter = inv.inviter.mention if inv.inviter else "Unknown"
            lines.append(f"`{inv.code}` — by {inviter} — **{inv.uses}** uses")
        await ctx.send(embed=self._embed(
            title=f"<:infoicon:1515660285850157137> Invites for {ctx.guild.name}",
            description="\n".join(lines),
            requester=ctx.author,
        ))

    @app_commands.command(name="inviteinfo", description="List active invites for this server.")
    @app_commands.guild_only()
    @app_commands.default_permissions(manage_guild=True)
    async def inviteinfo_slash(self, interaction: discord.Interaction) -> None:
        invites = await interaction.guild.invites()
        if not invites:
            await interaction.response.send_message(embed=self._err("No active invites found."), ephemeral=True)
            return
        lines = []
        for inv in sorted(invites, key=lambda i: i.uses or 0, reverse=True)[:15]:
            inviter = inv.inviter.mention if inv.inviter else "Unknown"
            lines.append(f"`{inv.code}` — by {inviter} — **{inv.uses}** uses")
        await interaction.response.send_message(embed=self._embed(
            title=f"<:infoicon:1515660285850157137> Invites for {interaction.guild.name}",
            description="\n".join(lines),
            requester=interaction.user,
        ))

    @commands.command(name="avatar", aliases=["av", "pfp"])
    async def avatar(self, ctx: commands.Context, member: discord.Member = None) -> None:
        m = member or ctx.author
        e = self._embed(
            f"<:cloud:1515660282771542016> {m.display_name}'s Avatar",
            image=m.display_avatar.url,
            requester=ctx.author,
        )
        e.description = (
            f"[PNG]({m.display_avatar.replace(format='png').url}) • "
            f"[JPG]({m.display_avatar.replace(format='jpg').url}) • "
            f"[WEBP]({m.display_avatar.replace(format='webp').url})"
        )
        await ctx.send(embed=e)

    @app_commands.command(name="avatar", description="View a member's avatar.")
    async def avatar_slash(self, interaction: discord.Interaction, member: discord.Member = None) -> None:
        m = member or interaction.user
        e = self._embed(
            f"<:cloud:1515660282771542016> {m.display_name}'s Avatar",
            image=m.display_avatar.url,
            requester=interaction.user,
        )
        e.description = (
            f"[PNG]({m.display_avatar.replace(format='png').url}) • "
            f"[JPG]({m.display_avatar.replace(format='jpg').url}) • "
            f"[WEBP]({m.display_avatar.replace(format='webp').url})"
        )
        await interaction.response.send_message(embed=e)

    @commands.command(name="banner")
    async def banner(self, ctx: commands.Context, member: discord.Member = None) -> None:
        m = member or ctx.author
        user = await self.bot.fetch_user(m.id)
        if not user.banner:
            await ctx.send(embed=self._err(f"<:warnicon:1515660263129350155> {m.mention} doesn't have a banner set."))
            return
        e = self._embed(
            f"<:cloud:1515660282771542016> {m.display_name}'s Banner",
            image=user.banner.url,
            requester=ctx.author,
        )
        await ctx.send(embed=e)

    @app_commands.command(name="banner", description="View a member's banner.")
    async def banner_slash(self, interaction: discord.Interaction, member: discord.Member = None) -> None:
        m = member or interaction.user
        user = await self.bot.fetch_user(m.id)
        if not user.banner:
            await interaction.response.send_message(embed=self._err(f"<:warnicon:1515660263129350155> {m.mention} doesn't have a banner set."), ephemeral=True)
            return
        e = self._embed(
            f"<:cloud:1515660282771542016> {m.display_name}'s Banner",
            image=user.banner.url,
            requester=interaction.user,
        )
        await interaction.response.send_message(embed=e)

    @commands.command(name="say")
    @commands.has_permissions(manage_messages=True)
    async def say(self, ctx: commands.Context, *, message: str) -> None:
        try:
            await ctx.message.delete()
        except discord.Forbidden:
            pass
        await ctx.send(message)

    @app_commands.command(name="say", description="Make the bot send a message.")
    @app_commands.default_permissions(manage_messages=True)
    async def say_slash(self, interaction: discord.Interaction, message: str) -> None:
        await interaction.response.send_message("✅ Sent!", ephemeral=True)
        await interaction.channel.send(message)

    @commands.command(name="embed")
    @commands.has_permissions(manage_messages=True)
    async def embed_cmd(self, ctx: commands.Context, *, text: str) -> None:
        try:
            await ctx.message.delete()
        except discord.Forbidden:
            pass
        if "|" in text:
            title, _, desc = text.partition("|")
            e = discord.Embed(title=title.strip(), description=desc.strip(), color=COLOUR)
        else:
            e = discord.Embed(description=text.strip(), color=COLOUR)
        bot_avatar = self.bot.user.display_avatar.url if self.bot.user else None
        if bot_avatar:
            e.set_footer(text=self.bot.user.name, icon_url=bot_avatar)
        await ctx.send(embed=e)

    @app_commands.command(name="embed", description="Send an embed. Use 'Title | Description' or just text.")
    @app_commands.default_permissions(manage_messages=True)
    async def embed_slash(self, interaction: discord.Interaction, text: str) -> None:
        if "|" in text:
            title, _, desc = text.partition("|")
            e = discord.Embed(title=title.strip(), description=desc.strip(), color=COLOUR)
        else:
            e = discord.Embed(description=text.strip(), color=COLOUR)
        bot_avatar = self.bot.user.display_avatar.url if self.bot.user else None
        if bot_avatar:
            e.set_footer(text=self.bot.user.name, icon_url=bot_avatar)
        await interaction.response.send_message("✅ Sent!", ephemeral=True)
        await interaction.channel.send(embed=e)

    @commands.command(name="roll")
    async def roll(self, ctx: commands.Context, dice: str = "1d6") -> None:
        match = re.fullmatch(r"(\d+)d(\d+)", dice.lower())
        if not match:
            await ctx.send(embed=self._err("Use format like `2d6` or `1d20`."))
            return
        count, sides = int(match.group(1)), int(match.group(2))
        if not (1 <= count <= 25) or sides < 2:
            await ctx.send(embed=self._err("Dice: 1–25 dice, 2+ sides."))
            return
        rolls  = [random.randint(1, sides) for _ in range(count)]
        total  = sum(rolls)
        detail = " + ".join(f"`{r}`" for r in rolls)
        await ctx.send(embed=self._embed(
            "🎲 Dice Roll",
            f"**Dice:** `{dice}`\n**Rolls:** {detail}\n**Total:** **{total}**",
            requester=ctx.author,
        ))

    @app_commands.command(name="roll", description="Roll dice. Default is 1d6.")
    async def roll_slash(self, interaction: discord.Interaction, dice: str = "1d6") -> None:
        match = re.fullmatch(r"(\d+)d(\d+)", dice.lower())
        if not match:
            await interaction.response.send_message(embed=self._err("Use format like `2d6` or `1d20`."), ephemeral=True)
            return
        count, sides = int(match.group(1)), int(match.group(2))
        if not (1 <= count <= 25) or sides < 2:
            await interaction.response.send_message(embed=self._err("Dice: 1–25 dice, 2+ sides."), ephemeral=True)
            return
        rolls  = [random.randint(1, sides) for _ in range(count)]
        total  = sum(rolls)
        detail = " + ".join(f"`{r}`" for r in rolls)
        await interaction.response.send_message(embed=self._embed(
            "🎲 Dice Roll",
            f"**Dice:** `{dice}`\n**Rolls:** {detail}\n**Total:** **{total}**",
            requester=interaction.user,
        ))

    @commands.command(name="coinflip", aliases=["flip", "coin"])
    async def coinflip(self, ctx: commands.Context) -> None:
        result = random.choice(["Heads 🪙", "Tails 🪙"])
        await ctx.send(embed=self._embed("🪙 Coin Flip", f"**Result:** {result}", requester=ctx.author))

    @app_commands.command(name="coinflip", description="Flip a coin.")
    async def coinflip_slash(self, interaction: discord.Interaction) -> None:
        result = random.choice(["Heads 🪙", "Tails 🪙"])
        await interaction.response.send_message(embed=self._embed("🪙 Coin Flip", f"**Result:** {result}", requester=interaction.user))

    @commands.command(name="choose", aliases=["pick"])
    async def choose(self, ctx: commands.Context, *, options: str) -> None:
        sep     = "|" if "|" in options else ","
        choices = [o.strip() for o in options.split(sep) if o.strip()]
        if len(choices) < 2:
            await ctx.send(embed=self._err("Provide at least 2 options separated by `|` or `,`."))
            return
        picked = random.choice(choices)
        await ctx.send(embed=self._embed(
            "🎯 Decision Made",
            f"**Options:** {', '.join(f'`{c}`' for c in choices)}\n**I choose:** **{picked}**",
            requester=ctx.author,
        ))

    @app_commands.command(name="choose", description="Choose between options separated by | or ,")
    async def choose_slash(self, interaction: discord.Interaction, options: str) -> None:
        sep     = "|" if "|" in options else ","
        choices = [o.strip() for o in options.split(sep) if o.strip()]
        if len(choices) < 2:
            await interaction.response.send_message(embed=self._err("Provide at least 2 options separated by `|` or `,`."), ephemeral=True)
            return
        picked = random.choice(choices)
        await interaction.response.send_message(embed=self._embed(
            "🎯 Decision Made",
            f"**Options:** {', '.join(f'`{c}`' for c in choices)}\n**I choose:** **{picked}**",
            requester=interaction.user,
        ))

    @commands.command(name="poll")
    async def poll(self, ctx: commands.Context, *, question: str) -> None:
        e = discord.Embed(
            title="📊 Poll",
            description=question,
            color=COLOUR,
            timestamp=datetime.now(timezone.utc),
        )
        e.set_footer(
            text=f"Poll by {ctx.author.display_name}",
            icon_url=ctx.author.display_avatar.url,
        )
        msg = await ctx.send(embed=e)
        await msg.add_reaction("✅")
        await msg.add_reaction("❌")
        try:
            await ctx.message.delete()
        except discord.Forbidden:
            pass

    @app_commands.command(name="poll", description="Create a poll with ✅ and ❌ reactions.")
    async def poll_slash(self, interaction: discord.Interaction, question: str) -> None:
        e = discord.Embed(
            title="📊 Poll",
            description=question,
            color=COLOUR,
            timestamp=datetime.now(timezone.utc),
        )
        e.set_footer(
            text=f"Poll by {interaction.user.display_name}",
            icon_url=interaction.user.display_avatar.url,
        )
        await interaction.response.send_message(embed=e)
        msg = await interaction.original_response()
        await msg.add_reaction("✅")
        await msg.add_reaction("❌")

    @commands.command(name="8ball", aliases=["eightball"])
    async def eightball(self, ctx: commands.Context, *, question: str) -> None:
        responses = [
            "It is certain.", "Without a doubt.", "Yes, definitely.",
            "You may rely on it.", "As I see it, yes.", "Most likely.",
            "Outlook good.", "Signs point to yes.",
            "Reply hazy, try again.", "Ask again later.",
            "Better not tell you now.", "Cannot predict now.", "Concentrate and ask again.",
            "Don't count on it.", "My reply is no.",
            "My sources say no.", "Outlook not so good.", "Very doubtful.",
        ]
        answer   = random.choice(responses)
        positive = any(w in answer.lower() for w in ["yes", "certain", "good", "likely", "definitely"])
        negative = any(w in answer.lower() for w in ["no", "doubtful", "don't", "not"])
        colour   = COLOUR_OK if positive else (COLOUR_ERR if negative else COLOUR_WARN)
        e = discord.Embed(color=colour)
        e.add_field(name="🎱 Question", value=question, inline=False)
        e.add_field(name="Answer",      value=f"*{answer}*", inline=False)
        await ctx.send(embed=e)

    @app_commands.command(name="8ball", description="Ask the magic 8-ball a question.")
    async def eightball_slash(self, interaction: discord.Interaction, question: str) -> None:
        responses = [
            "It is certain.", "Without a doubt.", "Yes, definitely.",
            "You may rely on it.", "As I see it, yes.", "Most likely.",
            "Outlook good.", "Signs point to yes.",
            "Reply hazy, try again.", "Ask again later.",
            "Better not tell you now.", "Cannot predict now.", "Concentrate and ask again.",
            "Don't count on it.", "My reply is no.",
            "My sources say no.", "Outlook not so good.", "Very doubtful.",
        ]
        answer   = random.choice(responses)
        positive = any(w in answer.lower() for w in ["yes", "certain", "good", "likely", "definitely"])
        negative = any(w in answer.lower() for w in ["no", "doubtful", "don't", "not"])
        colour   = COLOUR_OK if positive else (COLOUR_ERR if negative else COLOUR_WARN)
        e = discord.Embed(color=colour)
        e.add_field(name="🎱 Question", value=question, inline=False)
        e.add_field(name="Answer",      value=f"*{answer}*", inline=False)
        await interaction.response.send_message(embed=e)

    @commands.command(name="calculate", aliases=["calc"])
    async def calculate(self, ctx: commands.Context, *, expression: str) -> None:
        if not re.fullmatch(r"[\d\s\+\-\*\/\.\(\)%]+", expression):
            await ctx.send(embed=self._err("Only basic math operators allowed (`+ - * / ( ) %`)."))
            return
        try:
            result = eval(expression, {"__builtins__": {}})
            await ctx.send(embed=self._embed(
                "🧮 Calculator",
                f"**Expression:** `{expression}`\n**Result:** `{result}`",
                requester=ctx.author,
            ))
        except Exception:
            await ctx.send(embed=self._err("Could not evaluate that expression."))

    @app_commands.command(name="calculate", description="Calculate a math expression.")
    async def calculate_slash(self, interaction: discord.Interaction, expression: str) -> None:
        if not re.fullmatch(r"[\d\s\+\-\*\/\.\(\)%]+", expression):
            await interaction.response.send_message(embed=self._err("Only basic math operators allowed (`+ - * / ( ) %`)."), ephemeral=True)
            return
        try:
            result = eval(expression, {"__builtins__": {}})
            await interaction.response.send_message(embed=self._embed(
                "🧮 Calculator",
                f"**Expression:** `{expression}`\n**Result:** `{result}`",
                requester=interaction.user,
            ))
        except Exception:
            await interaction.response.send_message(embed=self._err("Could not evaluate that expression."), ephemeral=True)

    @commands.command(name="snipe")
    @commands.guild_only()
    @commands.has_permissions(manage_messages=True)
    async def snipe(self, ctx: commands.Context) -> None:
        data = General._snipe_cache.get(ctx.channel.id)
        if not data:
            await ctx.send("<:warnicon:1515660263129350155> Nothing to snipe here.", delete_after=6)
            return
        e = discord.Embed(
            description=data["content"],
            color=COLOUR_ERR,
            timestamp=datetime.fromisoformat(data["time"]),
        )
        e.set_author(name=data["author"], icon_url=data["avatar"])
        e.set_footer(text="Deleted message")
        await ctx.send(embed=e)

    @app_commands.command(name="snipe", description="View the last deleted message in this channel.")
    @app_commands.guild_only()
    @app_commands.default_permissions(manage_messages=True)
    async def snipe_slash(self, interaction: discord.Interaction) -> None:
        data = General._snipe_cache.get(interaction.channel.id)
        if not data:
            await interaction.response.send_message("<:warnicon:1515660263129350155> Nothing to snipe here.", ephemeral=True)
            return
        e = discord.Embed(
            description=data["content"],
            color=COLOUR_ERR,
            timestamp=datetime.fromisoformat(data["time"]),
        )
        e.set_author(name=data["author"], icon_url=data["avatar"])
        e.set_footer(text="Deleted message")
        await interaction.response.send_message(embed=e)

    @commands.command(name="steal")
    @commands.has_permissions(manage_emojis_and_stickers=True)
    async def steal(self, ctx: commands.Context, *, name: str = None) -> None:
        if not ctx.message.reference:
            await ctx.send(embed=self._err("Reply to a message containing a custom emoji."))
            return
        ref = await ctx.channel.fetch_message(ctx.message.reference.message_id)
        match = re.search(r"<(a?):(\w+):(\d+)>", ref.content)
        if not match:
            await ctx.send(embed=self._err("No custom emoji found in that message."))
            return
        animated   = bool(match.group(1))
        emoji_name = name or match.group(2)
        emoji_id   = match.group(3)
        ext        = "gif" if animated else "png"
        url        = f"https://cdn.discordapp.com/emojis/{emoji_id}.{ext}"
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as resp:
                if resp.status != 200:
                    await ctx.send(embed=self._err("Failed to download the emoji."))
                    return
                image = await resp.read()
        try:
            emoji = await ctx.guild.create_custom_emoji(name=emoji_name, image=image)
        except discord.HTTPException as exc:
            await ctx.send(embed=self._err(f"Failed to add emoji: {exc}"))
            return
        await ctx.send(embed=self._ok("<:tick:1514194122192191569> Emoji Stolen!", f"Added {emoji} as `:{emoji.name}:`"))

    @app_commands.command(name="steal", description="Steal an emoji by its ID.")
    @app_commands.default_permissions(manage_emojis_and_stickers=True)
    async def steal_slash(self, interaction: discord.Interaction, emoji_id: str, name: str = None) -> None:
        match = re.fullmatch(r"<(a?):(\w+):(\d+)>", emoji_id.strip())
        if match:
            animated   = bool(match.group(1))
            emoji_name = name or match.group(2)
            eid        = match.group(3)
        else:
            digits = re.sub(r"\D", "", emoji_id)
            if not digits:
                await interaction.response.send_message(embed=self._err("Provide a valid emoji or emoji ID."), ephemeral=True)
                return
            animated   = False
            emoji_name = name or "stolen_emoji"
            eid        = digits
        ext = "gif" if animated else "png"
        url = f"https://cdn.discordapp.com/emojis/{eid}.{ext}"
        await interaction.response.defer()
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as resp:
                if resp.status != 200:
                    await interaction.followup.send(embed=self._err("Failed to download the emoji."), ephemeral=True)
                    return
                image = await resp.read()
        try:
            emoji = await interaction.guild.create_custom_emoji(name=emoji_name, image=image)
        except discord.HTTPException as exc:
            await interaction.followup.send(embed=self._err(f"Failed to add emoji: {exc}"), ephemeral=True)
            return
        await interaction.followup.send(embed=self._ok("<:tick:1514194122192191569> Emoji Stolen!", f"Added {emoji} as `:{emoji.name}:`"))

    @commands.command(name="emojiinfo")
    async def emojiinfo(self, ctx: commands.Context, emoji: discord.Emoji) -> None:
        ts = int(emoji.created_at.timestamp())
        e = self._embed(
            "<:infoicon:1515660285850157137> Emoji Info",
            f"**Name:** `:{emoji.name}:`\n"
            f"**ID:** `{emoji.id}`\n"
            f"**Animated:** {'Yes' if emoji.animated else 'No'}\n"
            f"**Created:** <t:{ts}:R>\n"
            f"**URL:** [Click here]({emoji.url})",
            thumbnail=emoji.url,
            requester=ctx.author,
        )
        await ctx.send(embed=e)

    @app_commands.command(name="emojiinfo", description="View info about a custom emoji.")
    async def emojiinfo_slash(self, interaction: discord.Interaction, emoji: str) -> None:
        match = re.fullmatch(r"<(a?):(\w+):(\d+)>", emoji.strip())
        if not match:
            await interaction.response.send_message(embed=self._err("Please provide a valid custom emoji."), ephemeral=True)
            return
        animated   = bool(match.group(1))
        emoji_name = match.group(2)
        emoji_id   = int(match.group(3))
        ext        = "gif" if animated else "png"
        url        = f"https://cdn.discordapp.com/emojis/{emoji_id}.{ext}"
        ts         = discord.utils.snowflake_time(emoji_id)
        e = self._embed(
            "<:infoicon:1515660285850157137> Emoji Info",
            f"**Name:** `:{emoji_name}:`\n"
            f"**ID:** `{emoji_id}`\n"
            f"**Animated:** {'Yes' if animated else 'No'}\n"
            f"**Created:** <t:{int(ts.timestamp())}:R>\n"
            f"**URL:** [Click here]({url})",
            thumbnail=url,
            requester=interaction.user,
        )
        await interaction.response.send_message(embed=e)

    @commands.command(name="afk")
    @commands.guild_only()
    async def afk(self, ctx: commands.Context, *, reason: str = "AFK") -> None:
        gid = str(ctx.guild.id)
        uid = str(ctx.author.id)
        self._afk.setdefault(gid, {})[uid] = {
            "reason":        reason,
            "time":          datetime.now(timezone.utc).isoformat(),
            "original_nick": ctx.author.nick,
        }
        _save(AFK_FILE, self._afk)
        try:
            await ctx.author.edit(nick=f"[AFK] {ctx.author.display_name[:28]}")
        except discord.Forbidden:
            pass
        await ctx.send(embed=discord.Embed(
            description=f"<:warnicon:1515660263129350155> **{ctx.author.display_name}** is now AFK\n> {reason}",
            color=COLOUR_WARN,
        ))

    @app_commands.command(name="afk", description="Set yourself as AFK with an optional reason.")
    @app_commands.guild_only()
    async def afk_slash(self, interaction: discord.Interaction, reason: str = "AFK") -> None:
        gid = str(interaction.guild.id)
        uid = str(interaction.user.id)
        self._afk.setdefault(gid, {})[uid] = {
            "reason":        reason,
            "time":          datetime.now(timezone.utc).isoformat(),
            "original_nick": interaction.user.nick if isinstance(interaction.user, discord.Member) else None,
        }
        _save(AFK_FILE, self._afk)
        try:
            await interaction.user.edit(nick=f"[AFK] {interaction.user.display_name[:28]}")
        except discord.Forbidden:
            pass
        await interaction.response.send_message(embed=discord.Embed(
            description=f"<:warnicon:1515660263129350155> **{interaction.user.display_name}** is now AFK\n> {reason}",
            color=COLOUR_WARN,
        ))

    @commands.command(name="afkremove", aliases=["unafk"])
    @commands.guild_only()
    async def afk_remove(self, ctx: commands.Context) -> None:
        gid = str(ctx.guild.id)
        uid = str(ctx.author.id)
        if gid not in self._afk or uid not in self._afk[gid]:
            await ctx.send("❌ You are not AFK.", delete_after=5)
            return
        original_nick = self._afk[gid][uid].get("original_nick")
        del self._afk[gid][uid]
        _save(AFK_FILE, self._afk)
        await self._restore_nick(ctx.author, original_nick)
        await ctx.send(embed=discord.Embed(
            description=f"✅ **{ctx.author.display_name}** is no longer AFK.",
            color=COLOUR_OK,
        ), delete_after=8)

    @app_commands.command(name="afkremove", description="Remove your AFK status.")
    @app_commands.guild_only()
    async def afk_remove_slash(self, interaction: discord.Interaction) -> None:
        gid = str(interaction.guild.id)
        uid = str(interaction.user.id)
        if gid not in self._afk or uid not in self._afk[gid]:
            await interaction.response.send_message("❌ You are not AFK.", ephemeral=True)
            return
        original_nick = self._afk[gid][uid].get("original_nick")
        del self._afk[gid][uid]
        _save(AFK_FILE, self._afk)
        await self._restore_nick(interaction.user, original_nick)
        await interaction.response.send_message(embed=discord.Embed(
            description=f"✅ **{interaction.user.display_name}** is no longer AFK.",
            color=COLOUR_OK,
        ))

    async def _restore_nick(self, member: discord.Member, original_nick: str = None) -> None:
        try:
            await member.edit(nick=original_nick)
        except discord.Forbidden:
            pass

    @commands.command(name="stick")
    @commands.guild_only()
    @commands.has_permissions(manage_messages=True)
    async def stick(self, ctx: commands.Context, *, message: str = None) -> None:
        if message is None:
            await ctx.send("❓ Usage: `!stick <message>` or `!stick remove`")
            return
        if message.strip().lower() == "remove":
            await self.stick_remove(ctx)
            return
        cid = str(ctx.channel.id)
        if cid in self._sticky and self._sticky[cid].get("msg_id"):
            try:
                old = await ctx.channel.fetch_message(self._sticky[cid]["msg_id"])
                await old.delete()
            except (discord.NotFound, discord.Forbidden):
                pass
        e = discord.Embed(description=message, color=COLOUR)
        e.set_footer(text="📌 Sticky Message")
        sent = await ctx.channel.send(embed=e)
        self._sticky[cid] = {"message": message, "msg_id": sent.id}
        _save(STICKY_FILE, self._sticky)
        confirm = discord.Embed(
            description=f"📌 Sticky set in {ctx.channel.mention}. Use `!stick remove` to unpin.",
            color=COLOUR_OK,
        )
        await ctx.send(embed=confirm, delete_after=8)
        try:
            await ctx.message.delete()
        except discord.Forbidden:
            pass

    @app_commands.command(name="stick", description="Set a sticky message in this channel.")
    @app_commands.guild_only()
    @app_commands.default_permissions(manage_messages=True)
    async def stick_slash(self, interaction: discord.Interaction, message: str) -> None:
        cid = str(interaction.channel.id)
        if cid in self._sticky and self._sticky[cid].get("msg_id"):
            try:
                old = await interaction.channel.fetch_message(self._sticky[cid]["msg_id"])
                await old.delete()
            except (discord.NotFound, discord.Forbidden):
                pass
        e = discord.Embed(description=message, color=COLOUR)
        e.set_footer(text="📌 Sticky Message")
        await interaction.response.send_message("✅ Sticky message set!", ephemeral=True)
        sent = await interaction.channel.send(embed=e)
        self._sticky[cid] = {"message": message, "msg_id": sent.id}
        _save(STICKY_FILE, self._sticky)

    @commands.command(name="stickremove", aliases=["unstick"])
    @commands.guild_only()
    @commands.has_permissions(manage_messages=True)
    async def stick_remove(self, ctx: commands.Context) -> None:
        cid = str(ctx.channel.id)
        if cid not in self._sticky:
            await ctx.send("❌ No sticky message in this channel.", delete_after=5)
            return
        if self._sticky[cid].get("msg_id"):
            try:
                old = await ctx.channel.fetch_message(self._sticky[cid]["msg_id"])
                await old.delete()
            except (discord.NotFound, discord.Forbidden):
                pass
        del self._sticky[cid]
        _save(STICKY_FILE, self._sticky)
        await ctx.send(embed=discord.Embed(
            description=f"🗑️ Sticky message removed from {ctx.channel.mention}.",
            color=COLOUR_ERR,
        ), delete_after=8)

    @app_commands.command(name="stickremove", description="Remove the sticky message in this channel.")
    @app_commands.guild_only()
    @app_commands.default_permissions(manage_messages=True)
    async def stick_remove_slash(self, interaction: discord.Interaction) -> None:
        cid = str(interaction.channel.id)
        if cid not in self._sticky:
            await interaction.response.send_message("❌ No sticky message in this channel.", ephemeral=True)
            return
        if self._sticky[cid].get("msg_id"):
            try:
                old = await interaction.channel.fetch_message(self._sticky[cid]["msg_id"])
                await old.delete()
            except (discord.NotFound, discord.Forbidden):
                pass
        del self._sticky[cid]
        _save(STICKY_FILE, self._sticky)
        await interaction.response.send_message(embed=discord.Embed(
            description=f"🗑️ Sticky message removed from {interaction.channel.mention}.",
            color=COLOUR_ERR,
        ))

    @commands.command(name="autoresponder", aliases=["ar"])
    @commands.guild_only()
    @commands.has_permissions(administrator=True)
    async def autoresponder(self, ctx: commands.Context, trigger: str, *, response: str) -> None:
        data = _load(AR_FILE)
        data.setdefault(str(ctx.guild.id), {})[trigger.lower()] = response
        _save(AR_FILE, data)
        await ctx.send(embed=self._ok(
            "<:tick:1514194122192191569> Autoresponder Added",
            f"**Trigger:** `{trigger}`\n**Response:** {response}",
        ))

    @app_commands.command(name="autoresponder", description="Add an autoresponder trigger and response.")
    @app_commands.guild_only()
    @app_commands.default_permissions(administrator=True)
    async def autoresponder_slash(self, interaction: discord.Interaction, trigger: str, response: str) -> None:
        data = _load(AR_FILE)
        data.setdefault(str(interaction.guild.id), {})[trigger.lower()] = response
        _save(AR_FILE, data)
        await interaction.response.send_message(embed=self._ok(
            "<:tick:1514194122192191569> Autoresponder Added",
            f"**Trigger:** `{trigger}`\n**Response:** {response}",
        ))

    @commands.command(name="removeresponder", aliases=["removear"])
    @commands.guild_only()
    @commands.has_permissions(administrator=True)
    async def removeresponder(self, ctx: commands.Context, *, trigger: str) -> None:
        data     = _load(AR_FILE)
        guild_id = str(ctx.guild.id)
        if guild_id not in data or trigger.lower() not in data[guild_id]:
            await ctx.send(embed=self._err(f"No autoresponder found for `{trigger}`."))
            return
        del data[guild_id][trigger.lower()]
        _save(AR_FILE, data)
        await ctx.send(embed=self._ok("<:tick:1514194122192191569> Autoresponder Removed", f"Removed trigger: `{trigger}`"))

    @app_commands.command(name="removeresponder", description="Remove an autoresponder by trigger.")
    @app_commands.guild_only()
    @app_commands.default_permissions(administrator=True)
    async def removeresponder_slash(self, interaction: discord.Interaction, trigger: str) -> None:
        data     = _load(AR_FILE)
        guild_id = str(interaction.guild.id)
        if guild_id not in data or trigger.lower() not in data[guild_id]:
            await interaction.response.send_message(embed=self._err(f"No autoresponder found for `{trigger}`."), ephemeral=True)
            return
        del data[guild_id][trigger.lower()]
        _save(AR_FILE, data)
        await interaction.response.send_message(embed=self._ok("<:tick:1514194122192191569> Autoresponder Removed", f"Removed trigger: `{trigger}`"))

    @commands.command(name="listresponders", aliases=["listar", "responders"])
    @commands.guild_only()
    @commands.has_permissions(administrator=True)
    async def listresponders(self, ctx: commands.Context) -> None:
        data       = _load(AR_FILE)
        responders = data.get(str(ctx.guild.id), {})
        if not responders:
            await ctx.send(embed=self._err("No autoresponders set up yet."))
            return
        lines = [f"`{i+1}.` **{trig}** → {resp}" for i, (trig, resp) in enumerate(responders.items())]
        await ctx.send(embed=self._embed("<:infoicon:1515660285850157137> Autoresponders", "\n".join(lines), requester=ctx.author))

    @app_commands.command(name="listresponders", description="List all autoresponders for this server.")
    @app_commands.guild_only()
    @app_commands.default_permissions(administrator=True)
    async def listresponders_slash(self, interaction: discord.Interaction) -> None:
        data       = _load(AR_FILE)
        responders = data.get(str(interaction.guild.id), {})
        if not responders:
            await interaction.response.send_message(embed=self._err("No autoresponders set up yet."), ephemeral=True)
            return
        lines = [f"`{i+1}.` **{trig}** → {resp}" for i, (trig, resp) in enumerate(responders.items())]
        await interaction.response.send_message(embed=self._embed("<:infoicon:1515660285850157137> Autoresponders", "\n".join(lines), requester=interaction.user))

    @commands.command(name="mediaonly")
    @commands.guild_only()
    @commands.has_permissions(manage_channels=True)
    async def mediaonly(self, ctx: commands.Context, channel: discord.TextChannel) -> None:
        data     = _load(MEDIA_FILE)
        guild_id = str(ctx.guild.id)
        data.setdefault(guild_id, [])
        if channel.id in data[guild_id]:
            await ctx.send(embed=self._err(f"{channel.mention} is already media-only."))
            return
        data[guild_id].append(channel.id)
        _save(MEDIA_FILE, data)
        await ctx.send(embed=self._ok(
            "<:shield:1515660276270239804> Media-Only Enabled",
            f"{channel.mention} is now **media-only**.",
        ))

    @app_commands.command(name="mediaonly", description="Make a channel media-only.")
    @app_commands.guild_only()
    @app_commands.default_permissions(manage_channels=True)
    async def mediaonly_slash(self, interaction: discord.Interaction, channel: discord.TextChannel) -> None:
        data     = _load(MEDIA_FILE)
        guild_id = str(interaction.guild.id)
        data.setdefault(guild_id, [])
        if channel.id in data[guild_id]:
            await interaction.response.send_message(embed=self._err(f"{channel.mention} is already media-only."), ephemeral=True)
            return
        data[guild_id].append(channel.id)
        _save(MEDIA_FILE, data)
        await interaction.response.send_message(embed=self._ok(
            "<:shield:1515660276270239804> Media-Only Enabled",
            f"{channel.mention} is now **media-only**.",
        ))

    @commands.command(name="unmediaonly")
    @commands.guild_only()
    @commands.has_permissions(manage_channels=True)
    async def unmediaonly(self, ctx: commands.Context, channel: discord.TextChannel) -> None:
        data     = _load(MEDIA_FILE)
        guild_id = str(ctx.guild.id)
        if guild_id not in data or channel.id not in data[guild_id]:
            await ctx.send(embed=self._err(f"{channel.mention} is not a media-only channel."))
            return
        data[guild_id].remove(channel.id)
        _save(MEDIA_FILE, data)
        await ctx.send(embed=self._ok("<:cross:1514194117985570888> Media-Only Disabled", f"{channel.mention} is no longer media-only."))

    @app_commands.command(name="unmediaonly", description="Remove media-only restriction from a channel.")
    @app_commands.guild_only()
    @app_commands.default_permissions(manage_channels=True)
    async def unmediaonly_slash(self, interaction: discord.Interaction, channel: discord.TextChannel) -> None:
        data     = _load(MEDIA_FILE)
        guild_id = str(interaction.guild.id)
        if guild_id not in data or channel.id not in data[guild_id]:
            await interaction.response.send_message(embed=self._err(f"{channel.mention} is not a media-only channel."), ephemeral=True)
            return
        data[guild_id].remove(channel.id)
        _save(MEDIA_FILE, data)
        await interaction.response.send_message(embed=self._ok("<:cross:1514194117985570888> Media-Only Disabled", f"{channel.mention} is no longer media-only."))

    @commands.command(name="gcreate", aliases=["giveaway", "gstart"])
    @commands.guild_only()
    @commands.has_permissions(manage_guild=True)
    async def gcreate(self, ctx: commands.Context) -> None:

        def check(m: discord.Message) -> bool:
            return m.author == ctx.author and m.channel == ctx.channel

        async def ask(prompt: str) -> str | None:
            e = discord.Embed(description=prompt, color=COLOUR_WARN)
            e.set_footer(text="Type your answer below • Type 'cancel' to abort")
            await ctx.send(embed=e)
            try:
                msg = await self.bot.wait_for("message", check=check, timeout=60)
                return None if msg.content.strip().lower() == "cancel" else msg.content.strip()
            except asyncio.TimeoutError:
                return None

        await ctx.send(embed=discord.Embed(
            title="🎉 Giveaway Setup",
            description="Let's create a giveaway! Answer the next questions.\nType `cancel` at any time to stop.",
            color=0xF39C12,
        ))

        ch_raw = await ask("<:infoicon:1515660285850157137> **Step 1/5** — Which channel? Mention it, e.g. `#giveaways`")
        if not ch_raw:
            await ctx.send("❌ Giveaway cancelled.", delete_after=5)
            return
        try:
            channel_id = int(re.sub(r"[<>#]", "", ch_raw))
            channel    = ctx.guild.get_channel(channel_id)
            assert isinstance(channel, discord.TextChannel)
        except Exception:
            await ctx.send("❌ Invalid channel.", delete_after=5)
            return

        dur_raw = await ask("<:leaf:1515660279944319006> **Step 2/5** — Duration? e.g. `30s`, `10m`, `2h`, `1d`")
        if not dur_raw:
            await ctx.send("❌ Giveaway cancelled.", delete_after=5)
            return
        seconds = parse_time(dur_raw)
        if seconds <= 0:
            await ctx.send("❌ Invalid duration. Use `10m`, `1h`, `2d` etc.", delete_after=5)
            return

        win_raw = await ask("<:tick:1514194122192191569> **Step 3/5** — How many winners? (1–20)")
        if not win_raw:
            await ctx.send("❌ Giveaway cancelled.", delete_after=5)
            return
        try:
            winners = max(1, min(20, int(win_raw)))
        except ValueError:
            await ctx.send("❌ Invalid number.", delete_after=5)
            return

        prize = await ask("<:Home:1514196660228718713> **Step 4/5** — What is the prize?")
        if not prize:
            await ctx.send("❌ Giveaway cancelled.", delete_after=5)
            return

        role_raw = await ask("<:shield:1515660276270239804> **Step 5/5** — Required role to enter? (mention a role or type `none`)")
        if role_raw is None:
            await ctx.send("❌ Giveaway cancelled.", delete_after=5)
            return
        req_role_id = None
        if role_raw.lower() not in ("none", "no", "-"):
            try:
                req_role_id = int(re.sub(r"[<>@& ]", "", role_raw))
                assert ctx.guild.get_role(req_role_id) is not None
            except Exception:
                await ctx.send("⚠️ Role not found, proceeding without requirement.")
                req_role_id = None

        ends_at = datetime.now(timezone.utc) + timedelta(seconds=seconds)
        embed   = self._giveaway_embed(prize, winners, ends_at, ctx.author, req_role_id, ctx.guild)
        msg     = await channel.send("🎉 **GIVEAWAY** 🎉", embed=embed)
        await msg.add_reaction("🎉")

        self._giveaways[str(msg.id)] = {
            "channel_id": channel.id,
            "guild_id":   ctx.guild.id,
            "prize":      prize,
            "winners":    winners,
            "host_id":    ctx.author.id,
            "ends_at":    ends_at.isoformat(),
            "req_role":   req_role_id,
            "ended":      False,
        }
        _save(GIVEAWAY_FILE, self._giveaways)

        await ctx.send(embed=discord.Embed(
            description=f"✅ Giveaway started in {channel.mention}! Ends in **{fmt_time(seconds)}**.\n"
                        f"Use `!gend {msg.id}` to end early.",
            color=COLOUR_OK,
        ))

    @app_commands.command(name="gcreate", description="Start a giveaway with a guided setup.")
    @app_commands.guild_only()
    @app_commands.default_permissions(manage_guild=True)
    async def gcreate_slash(
        self,
        interaction: discord.Interaction,
        channel: discord.TextChannel,
        duration: str,
        winners: int,
        prize: str,
        required_role: discord.Role = None,
    ) -> None:
        seconds = parse_time(duration)
        if seconds <= 0:
            await interaction.response.send_message("❌ Invalid duration. Use `10m`, `1h`, `2d` etc.", ephemeral=True)
            return
        winners = max(1, min(20, winners))
        req_role_id = required_role.id if required_role else None
        ends_at = datetime.now(timezone.utc) + timedelta(seconds=seconds)
        embed   = self._giveaway_embed(prize, winners, ends_at, interaction.user, req_role_id, interaction.guild)
        msg     = await channel.send("🎉 **GIVEAWAY** 🎉", embed=embed)
        await msg.add_reaction("🎉")
        self._giveaways[str(msg.id)] = {
            "channel_id": channel.id,
            "guild_id":   interaction.guild.id,
            "prize":      prize,
            "winners":    winners,
            "host_id":    interaction.user.id,
            "ends_at":    ends_at.isoformat(),
            "req_role":   req_role_id,
            "ended":      False,
        }
        _save(GIVEAWAY_FILE, self._giveaways)
        await interaction.response.send_message(embed=discord.Embed(
            description=f"✅ Giveaway started in {channel.mention}! Ends in **{fmt_time(seconds)}**.",
            color=COLOUR_OK,
        ), ephemeral=True)

    def _giveaway_embed(self, prize, winners, ends_at, host, req_role_id, guild) -> discord.Embed:
        e = discord.Embed(title=f"🎁 {prize}", color=COLOUR_WARN, timestamp=ends_at)
        e.add_field(name="Winners",   value=str(winners), inline=True)
        e.add_field(name="Hosted by", value=host.mention, inline=True)
        if req_role_id:
            role = guild.get_role(req_role_id)
            e.add_field(name="Required Role", value=role.mention if role else "Unknown", inline=True)
        e.add_field(name="React with", value="🎉 to enter!", inline=False)
        e.set_footer(text="Ends at")
        return e

    @commands.command(name="gend", aliases=["giveawayend", "endgiveaway"])
    @commands.guild_only()
    @commands.has_permissions(manage_guild=True)
    async def gend(self, ctx: commands.Context, message_id: int) -> None:
        key = str(message_id)
        if key not in self._giveaways:
            await ctx.send("❌ Giveaway not found.", delete_after=8)
            return
        if self._giveaways[key]["ended"]:
            await ctx.send("⚠️ That giveaway already ended.", delete_after=8)
            return
        await self._end_giveaway(key)
        await ctx.send("✅ Giveaway ended!", delete_after=5)

    @app_commands.command(name="gend", description="End a giveaway early by message ID.")
    @app_commands.guild_only()
    @app_commands.default_permissions(manage_guild=True)
    async def gend_slash(self, interaction: discord.Interaction, message_id: str) -> None:
        key = message_id.strip()
        if key not in self._giveaways:
            await interaction.response.send_message("❌ Giveaway not found.", ephemeral=True)
            return
        if self._giveaways[key]["ended"]:
            await interaction.response.send_message("⚠️ That giveaway already ended.", ephemeral=True)
            return
        await interaction.response.send_message("✅ Giveaway ended!", ephemeral=True)
        await self._end_giveaway(key)

    @commands.command(name="greroll", aliases=["giveawayreroll"])
    @commands.guild_only()
    @commands.has_permissions(manage_guild=True)
    async def greroll(self, ctx: commands.Context, message_id: int) -> None:
        key = str(message_id)
        if key not in self._giveaways:
            await ctx.send("❌ Giveaway not found.", delete_after=8)
            return
        gdata = self._giveaways[key]
        if not gdata["ended"]:
            await ctx.send("⚠️ Giveaway hasn't ended yet.", delete_after=8)
            return
        channel = self.bot.get_channel(gdata["channel_id"])
        if not channel:
            await ctx.send("❌ Channel not found.", delete_after=8)
            return
        try:
            gmsg = await channel.fetch_message(int(key))
        except discord.NotFound:
            await ctx.send("❌ Original message deleted.", delete_after=8)
            return
        guild   = self.bot.get_guild(gdata["guild_id"])
        winners = await self._pick_winners(gmsg, gdata["winners"], gdata.get("req_role"), guild)
        if winners:
            await channel.send(f"🔁 **Reroll!** New winner(s): {' '.join(w.mention for w in winners)} 🎉")
        else:
            await channel.send("❌ No valid entries found for reroll.")

    @app_commands.command(name="greroll", description="Reroll a giveaway by message ID.")
    @app_commands.guild_only()
    @app_commands.default_permissions(manage_guild=True)
    async def greroll_slash(self, interaction: discord.Interaction, message_id: str) -> None:
        key = message_id.strip()
        if key not in self._giveaways:
            await interaction.response.send_message("❌ Giveaway not found.", ephemeral=True)
            return
        gdata = self._giveaways[key]
        if not gdata["ended"]:
            await interaction.response.send_message("⚠️ Giveaway hasn't ended yet.", ephemeral=True)
            return
        channel = self.bot.get_channel(gdata["channel_id"])
        if not channel:
            await interaction.response.send_message("❌ Channel not found.", ephemeral=True)
            return
        await interaction.response.defer(ephemeral=True)
        try:
            gmsg = await channel.fetch_message(int(key))
        except discord.NotFound:
            await interaction.followup.send("❌ Original message deleted.", ephemeral=True)
            return
        guild   = self.bot.get_guild(gdata["guild_id"])
        winners = await self._pick_winners(gmsg, gdata["winners"], gdata.get("req_role"), guild)
        if winners:
            await channel.send(f"🔁 **Reroll!** New winner(s): {' '.join(w.mention for w in winners)} 🎉")
            await interaction.followup.send("✅ Rerolled!", ephemeral=True)
        else:
            await channel.send("❌ No valid entries found for reroll.")
            await interaction.followup.send("❌ No valid entries found.", ephemeral=True)

    async def _pick_winners(
        self,
        msg: discord.Message,
        count: int,
        req_role_id,
        guild: discord.Guild | None,
    ) -> list[discord.Member]:
        try:
            reaction = discord.utils.get(msg.reactions, emoji="🎉")
            if not reaction:
                return []
            users = [u async for u in reaction.users() if not u.bot]
        except Exception:
            return []
        if req_role_id and guild:
            role = guild.get_role(req_role_id)
            if role:
                users = [u for u in users if isinstance(u, discord.Member) and role in u.roles]
        return random.sample(users, min(count, len(users))) if users else []

    async def _end_giveaway(self, key: str) -> None:
        gdata = self._giveaways.get(key)
        if not gdata or gdata["ended"]:
            return
        gdata["ended"] = True
        _save(GIVEAWAY_FILE, self._giveaways)
        channel = self.bot.get_channel(gdata["channel_id"])
        if not channel:
            return
        try:
            msg = await channel.fetch_message(int(key))
        except discord.NotFound:
            return
        guild   = self.bot.get_guild(gdata["guild_id"])
        host    = guild.get_member(gdata["host_id"]) if guild else None
        winners = await self._pick_winners(msg, gdata["winners"], gdata.get("req_role"), guild)
        ended_embed = discord.Embed(
            title=f"🎁 {gdata['prize']} (Ended)",
            color=0x95A5A6,
            timestamp=datetime.now(timezone.utc),
        )
        ended_embed.add_field(name="Winners",   value=str(gdata["winners"]),               inline=True)
        ended_embed.add_field(name="Hosted by", value=host.mention if host else "Unknown", inline=True)
        ended_embed.add_field(
            name="🏆 Won by",
            value=" ".join(w.mention for w in winners) if winners else "No valid entries",
            inline=False,
        )
        ended_embed.set_footer(text="Giveaway ended")
        try:
            await msg.edit(embed=ended_embed)
        except discord.Forbidden:
            pass
        if winners:
            mentions = " ".join(w.mention for w in winners)
            await channel.send(
                f"🎉 Congratulations {mentions}! You won **{gdata['prize']}**!\n"
                f"Hosted by {host.mention if host else 'Unknown'}"
            )
        else:
            await channel.send(f"😢 No valid entries for **{gdata['prize']}**. No winners.")

    @tasks.loop(seconds=15)
    async def _check_giveaways(self) -> None:
        now = datetime.now(timezone.utc)
        for key, gdata in list(self._giveaways.items()):
            if gdata["ended"]:
                continue
            if now >= datetime.fromisoformat(gdata["ends_at"]):
                await self._end_giveaway(key)

    @_check_giveaways.before_loop
    async def _before_check(self) -> None:
        await self.bot.wait_until_ready()

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message) -> None:
        if message.author.bot or not message.guild:
            return

        ctx = await self.bot.get_context(message)
        gid = str(message.guild.id)
        uid = str(message.author.id)

        media_data = _load(MEDIA_FILE)
        if (
            gid in media_data
            and message.channel.id in media_data[gid]
            and not message.attachments
            and not message.embeds
        ):
            try:
                await message.delete()
                await message.channel.send(
                    f"{message.author.mention} Only media is allowed in this channel.",
                    delete_after=5,
                )
            except discord.Forbidden:
                pass
            return

        if not ctx.valid:
            if gid in self._afk and uid in self._afk[gid]:
                original_nick = self._afk[gid][uid].get("original_nick")
                del self._afk[gid][uid]
                _save(AFK_FILE, self._afk)
                await self._restore_nick(message.author, original_nick)
                await message.channel.send(embed=discord.Embed(
                    description=f"<:tick:1514194122192191569> Welcome back **{message.author.display_name}**! AFK removed.",
                    color=COLOUR_OK,
                ), delete_after=8)

        if gid in self._afk and message.mentions:
            for mentioned in message.mentions:
                mid = str(mentioned.id)
                if mid in self._afk[gid]:
                    info  = self._afk[gid][mid]
                    since = datetime.fromisoformat(info["time"])
                    ago   = fmt_time(int((datetime.now(timezone.utc) - since).total_seconds()))
                    await message.channel.send(embed=discord.Embed(
                        description=(
                            f"<:warnicon:1515660263129350155> **{mentioned.display_name}** is AFK\n"
                            f"> {info['reason']}\n"
                            f"*Since {ago} ago*"
                        ),
                        color=COLOUR_WARN,
                    ), delete_after=15)

        cid = str(message.channel.id)
        if cid in self._sticky:
            if ctx.valid:
                return
            entry = self._sticky[cid]
            if entry.get("msg_id"):
                try:
                    old = await message.channel.fetch_message(entry["msg_id"])
                    await old.delete()
                except (discord.NotFound, discord.Forbidden):
                    pass
            e = discord.Embed(description=entry["message"], color=COLOUR)
            e.set_footer(text="📌 Sticky Message")
            sent = await message.channel.send(embed=e)
            entry["msg_id"] = sent.id
            _save(STICKY_FILE, self._sticky)

        ar_data  = _load(AR_FILE)
        response = ar_data.get(gid, {}).get(message.content.lower())
        if response:
            await message.channel.send(response)

    @commands.Cog.listener()
    async def on_message_delete(self, message: discord.Message) -> None:
        if message.author.bot or not message.guild:
            return
        General._snipe_cache[message.channel.id] = {
            "content": message.content or "[No text content]",
            "author":  str(message.author),
            "avatar":  str(message.author.display_avatar.url),
            "time":    datetime.now(timezone.utc).isoformat(),
        }


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(General(bot))
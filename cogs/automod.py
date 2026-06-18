import discord
from discord.ext import commands
import json
import os
import re
import asyncio
from datetime import datetime, timezone

AUTOMOD_FILE = "data/automod.json"

COLORS = {
    "success": 0x2ECC71,
    "error": 0xE74C3C,
    "warning": 0xF39C12,
    "info": 0x5865F2,
    "neutral": 0x2C2F33,
}

SPAM_PATTERNS = [
    r"(discord\.gg|discord\.com/invite)/[a-zA-Z0-9]+",
    r"https?://[^\s]+",
]

BAD_WORDS = []

MAX_MENTIONS = 5
MAX_CAPS_PERCENT = 70
MAX_REPEATED_CHARS = 6
MAX_MESSAGES_PER_SECOND = 5


def load_data() -> dict:
    if not os.path.exists("data"):
        os.makedirs("data")
    if not os.path.exists(AUTOMOD_FILE):
        with open(AUTOMOD_FILE, "w") as f:
            json.dump({}, f)
        return {}
    with open(AUTOMOD_FILE, "r") as f:
        return json.load(f)


def save_data(data: dict) -> None:
    if not os.path.exists("data"):
        os.makedirs("data")
    with open(AUTOMOD_FILE, "w") as f:
        json.dump(data, f, indent=4)


def get_guild_data(guild_id: int) -> dict:
    data = load_data()
    gid = str(guild_id)
    if gid not in data:
        data[gid] = {
            "enabled": False,
            "whitelist": [],
            "log_channel": None,
            "config": {
                "anti_spam": True,
                "anti_invite": True,
                "anti_mention_spam": True,
                "anti_caps": True,
                "anti_repeated_chars": True,
                "bad_words": True,
            },
        }
        save_data(data)
    return data[gid]


def update_guild_data(guild_id: int, guild_data: dict) -> None:
    data = load_data()
    data[str(guild_id)] = guild_data
    save_data(data)


def build_embed(
    title: str,
    description: str,
    color: int,
    fields: list[tuple] = None,
    footer: str = None,
    thumbnail: str = None,
) -> discord.Embed:
    embed = discord.Embed(
        title=title,
        description=description,
        color=color,
        timestamp=datetime.now(timezone.utc),
    )
    if fields:
        for name, value, inline in fields:
            embed.add_field(name=name, value=value, inline=inline)
    if footer:
        embed.set_footer(text=footer)
    if thumbnail:
        embed.set_thumbnail(url=thumbnail)
    return embed


class AutoMod(commands.Cog, name="AutoMod"):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.message_cache: dict[int, list[float]] = {}

    @commands.group(name="automod", invoke_without_command=True)
    @commands.has_permissions(manage_guild=True)
    async def automod(self, ctx: commands.Context):
        guild_data = get_guild_data(ctx.guild.id)
        status = "✅ Enabled" if guild_data["enabled"] else "❌ Disabled"
        cfg = guild_data["config"]
        whitelist_count = len(guild_data["whitelist"])

        fields = [
            ("Status", status, True),
            ("Whitelisted Users", str(whitelist_count), True),
            ("\u200b", "\u200b", True),
            (
                "Active Filters",
                (
                    f"{'✅' if cfg['anti_spam'] else '❌'} Anti-Spam\n"
                    f"{'✅' if cfg['anti_invite'] else '❌'} Anti-Invite\n"
                    f"{'✅' if cfg['anti_mention_spam'] else '❌'} Mention Spam\n"
                    f"{'✅' if cfg['anti_caps'] else '❌'} Excessive Caps\n"
                    f"{'✅' if cfg['anti_repeated_chars'] else '❌'} Repeated Characters\n"
                    f"{'✅' if cfg['bad_words'] else '❌'} Bad Words"
                ),
                False,
            ),
            (
                "Commands",
                (
                    "`?automod enable` — Enable AutoMod\n"
                    "`?automod disable` — Disable AutoMod\n"
                    "`?automod config` — Configure filters\n"
                    "`?automod whitelist @user` — Whitelist a user\n"
                    "`?automod whitelist show` — View whitelisted users\n"
                    "`?automod unwhitelist @user` — Remove from whitelist"
                ),
                False,
            ),
        ]

        embed = build_embed(
            title="🛡️ AutoMod System",
            description="Automated moderation system overview for this server.",
            color=COLORS["info"],
            fields=fields,
            footer=f"Requested by {ctx.author} • {ctx.guild.name}",
            thumbnail=ctx.guild.icon.url if ctx.guild.icon else None,
        )
        await ctx.send(embed=embed)

    @automod.command(name="enable")
    @commands.has_permissions(manage_guild=True)
    async def automod_enable(self, ctx: commands.Context):
        guild_data = get_guild_data(ctx.guild.id)

        if guild_data["enabled"]:
            embed = build_embed(
                title="🛡️ AutoMod Already Active",
                description="The AutoMod system is already enabled on this server.",
                color=COLORS["warning"],
                footer=f"Requested by {ctx.author}",
            )
            await ctx.send(embed=embed)
            return

        guild_data["enabled"] = True
        update_guild_data(ctx.guild.id, guild_data)

        embed = build_embed(
            title="✅ AutoMod Enabled",
            description=(
                "The AutoMod system has been successfully **enabled**.\n\n"
                "All configured filters are now actively monitoring this server.\n"
                "Use `?automod config` to customize filter settings."
            ),
            color=COLORS["success"],
            fields=[
                ("Activated By", ctx.author.mention, True),
                ("Server", ctx.guild.name, True),
            ],
            footer=f"{ctx.guild.name} • AutoMod System",
        )
        await ctx.send(embed=embed)

    @automod.command(name="disable")
    @commands.has_permissions(manage_guild=True)
    async def automod_disable(self, ctx: commands.Context):
        guild_data = get_guild_data(ctx.guild.id)

        if not guild_data["enabled"]:
            embed = build_embed(
                title="🛡️ AutoMod Already Inactive",
                description="The AutoMod system is already disabled on this server.",
                color=COLORS["warning"],
                footer=f"Requested by {ctx.author}",
            )
            await ctx.send(embed=embed)
            return

        guild_data["enabled"] = False
        update_guild_data(ctx.guild.id, guild_data)

        embed = build_embed(
            title="❌ AutoMod Disabled",
            description=(
                "The AutoMod system has been **disabled**.\n\n"
                "No filters are currently active. Use `?automod enable` to re-enable."
            ),
            color=COLORS["error"],
            fields=[
                ("Deactivated By", ctx.author.mention, True),
                ("Server", ctx.guild.name, True),
            ],
            footer=f"{ctx.guild.name} • AutoMod System",
        )
        await ctx.send(embed=embed)

    @automod.command(name="config")
    @commands.has_permissions(manage_guild=True)
    async def automod_config(self, ctx: commands.Context):
        guild_data = get_guild_data(ctx.guild.id)
        cfg = guild_data["config"]

        filter_keys = {
            "1": ("anti_spam", "Anti-Spam"),
            "2": ("anti_invite", "Anti-Invite Links"),
            "3": ("anti_mention_spam", "Mention Spam"),
            "4": ("anti_caps", "Excessive Caps"),
            "5": ("anti_repeated_chars", "Repeated Characters"),
            "6": ("bad_words", "Bad Words Filter"),
        }

        current_status = "\n".join(
            f"`[{num}]` {'✅' if cfg[key] else '❌'} {label}"
            for num, (key, label) in filter_keys.items()
        )

        embed = build_embed(
            title="⚙️ AutoMod Configuration",
            description=(
                "React or type the number of a filter to toggle it on or off.\n"
                "Type the number in chat within **30 seconds** to toggle.\n\n"
                + current_status
            ),
            color=COLORS["info"],
            fields=[
                ("Instructions", "Send a number `1–6` to toggle the corresponding filter.", False)
            ],
            footer=f"Requested by {ctx.author} • Times out in 30s",
        )

        config_msg = await ctx.send(embed=embed)

        def check(m: discord.Message):
            return (
                m.author == ctx.author
                and m.channel == ctx.channel
                and m.content in filter_keys
            )

        try:
            response = await self.bot.wait_for("message", timeout=30.0, check=check)
        except asyncio.TimeoutError:
            timeout_embed = build_embed(
                title="⏱️ Configuration Timed Out",
                description="No input was received within 30 seconds. No changes were made.",
                color=COLORS["neutral"],
                footer=f"Requested by {ctx.author}",
            )
            await config_msg.edit(embed=timeout_embed)
            return

        key, label = filter_keys[response.content]
        cfg[key] = not cfg[key]
        guild_data["config"] = cfg
        update_guild_data(ctx.guild.id, guild_data)

        state = "enabled" if cfg[key] else "disabled"
        color = COLORS["success"] if cfg[key] else COLORS["error"]
        icon = "✅" if cfg[key] else "❌"

        result_embed = build_embed(
            title=f"{icon} Filter Updated",
            description=f"The **{label}** filter has been **{state}**.",
            color=color,
            fields=[
                ("Modified By", ctx.author.mention, True),
                ("Filter", label, True),
                ("New State", state.capitalize(), True),
            ],
            footer=f"{ctx.guild.name} • AutoMod Configuration",
        )
        await config_msg.edit(embed=result_embed)

        try:
            await response.delete()
        except (discord.Forbidden, discord.NotFound):
            pass

    @automod.command(name="whitelist")
    @commands.has_permissions(manage_guild=True)
    async def automod_whitelist(self, ctx: commands.Context, target: str = None, member: discord.Member = None):
        if target == "show":
            await self._whitelist_show(ctx)
            return

        if target is None and member is None:
            embed = build_embed(
                title="⚠️ Missing Argument",
                description=(
                    "Please mention a user to whitelist or use `show` to view the whitelist.\n\n"
                    "**Usage:**\n"
                    "`?automod whitelist @user` — Whitelist a member\n"
                    "`?automod whitelist show` — View all whitelisted members"
                ),
                color=COLORS["warning"],
                footer=f"Requested by {ctx.author}",
            )
            await ctx.send(embed=embed)
            return

        resolved_member = member
        if resolved_member is None and ctx.message.mentions:
            resolved_member = ctx.message.mentions[0]

        if resolved_member is None:
            embed = build_embed(
                title="⚠️ Invalid User",
                description="Please mention a valid server member to whitelist.",
                color=COLORS["error"],
                footer=f"Requested by {ctx.author}",
            )
            await ctx.send(embed=embed)
            return

        guild_data = get_guild_data(ctx.guild.id)

        if resolved_member.id in guild_data["whitelist"]:
            embed = build_embed(
                title="⚠️ Already Whitelisted",
                description=f"{resolved_member.mention} is already on the AutoMod whitelist.",
                color=COLORS["warning"],
                footer=f"Requested by {ctx.author}",
            )
            await ctx.send(embed=embed)
            return

        guild_data["whitelist"].append(resolved_member.id)
        update_guild_data(ctx.guild.id, guild_data)

        embed = build_embed(
            title="✅ User Whitelisted",
            description=f"{resolved_member.mention} has been added to the AutoMod whitelist.\nAutoMod will no longer act on their messages.",
            color=COLORS["success"],
            fields=[
                ("User", f"{resolved_member} ({resolved_member.id})", True),
                ("Whitelisted By", ctx.author.mention, True),
                ("Total Whitelisted", str(len(guild_data["whitelist"])), True),
            ],
            footer=f"{ctx.guild.name} • AutoMod Whitelist",
            thumbnail=resolved_member.display_avatar.url,
        )
        await ctx.send(embed=embed)

    async def _whitelist_show(self, ctx: commands.Context):
        guild_data = get_guild_data(ctx.guild.id)
        whitelist = guild_data["whitelist"]

        if not whitelist:
            embed = build_embed(
                title="📋 AutoMod Whitelist",
                description="No users are currently whitelisted. Use `?automod whitelist @user` to add one.",
                color=COLORS["neutral"],
                footer=f"{ctx.guild.name} • AutoMod Whitelist",
            )
            await ctx.send(embed=embed)
            return

        entries = []
        for uid in whitelist:
            member = ctx.guild.get_member(uid)
            if member:
                entries.append(f"• {member.mention} — `{member}` (`{uid}`)")
            else:
                entries.append(f"• Unknown User — `{uid}`")

        embed = build_embed(
            title="📋 AutoMod Whitelist",
            description="\n".join(entries),
            color=COLORS["info"],
            fields=[("Total Whitelisted", str(len(whitelist)), True)],
            footer=f"{ctx.guild.name} • AutoMod Whitelist",
        )
        await ctx.send(embed=embed)

    @automod.command(name="unwhitelist")
    @commands.has_permissions(manage_guild=True)
    async def automod_unwhitelist(self, ctx: commands.Context, member: discord.Member = None):
        if member is None and ctx.message.mentions:
            member = ctx.message.mentions[0]

        if member is None:
            embed = build_embed(
                title="⚠️ Missing Argument",
                description="Please mention a valid server member to remove from the whitelist.\n\n**Usage:** `?automod unwhitelist @user`",
                color=COLORS["warning"],
                footer=f"Requested by {ctx.author}",
            )
            await ctx.send(embed=embed)
            return

        guild_data = get_guild_data(ctx.guild.id)

        if member.id not in guild_data["whitelist"]:
            embed = build_embed(
                title="⚠️ Not Whitelisted",
                description=f"{member.mention} is not on the AutoMod whitelist.",
                color=COLORS["warning"],
                footer=f"Requested by {ctx.author}",
            )
            await ctx.send(embed=embed)
            return

        guild_data["whitelist"].remove(member.id)
        update_guild_data(ctx.guild.id, guild_data)

        embed = build_embed(
            title="✅ User Unwhitelisted",
            description=f"{member.mention} has been removed from the AutoMod whitelist.\nAutoMod will now monitor their messages.",
            color=COLORS["success"],
            fields=[
                ("User", f"{member} ({member.id})", True),
                ("Removed By", ctx.author.mention, True),
                ("Remaining Whitelisted", str(len(guild_data["whitelist"])), True),
            ],
            footer=f"{ctx.guild.name} • AutoMod Whitelist",
            thumbnail=member.display_avatar.url,
        )
        await ctx.send(embed=embed)

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot:
            return
        if not message.guild:
            return

        guild_data = get_guild_data(message.guild.id)

        if not guild_data["enabled"]:
            return
        if message.author.id in guild_data["whitelist"]:
            return

        cfg = guild_data["config"]

        if cfg["anti_spam"] and await self._check_spam(message):
            return
        if cfg["anti_invite"] and await self._check_invite(message):
            return
        if cfg["anti_mention_spam"] and await self._check_mention_spam(message):
            return
        if cfg["anti_caps"] and await self._check_caps(message):
            return
        if cfg["anti_repeated_chars"] and await self._check_repeated_chars(message):
            return
        if cfg["bad_words"] and await self._check_bad_words(message):
            return

    async def _delete_and_warn(
        self,
        message: discord.Message,
        title: str,
        reason: str,
    ):
        try:
            await message.delete()
        except (discord.Forbidden, discord.NotFound):
            pass

        embed = build_embed(
            title=f"🛡️ {title}",
            description=reason,
            color=COLORS["error"],
            fields=[("User", message.author.mention, True), ("Channel", message.channel.mention, True)],
            footer="AutoMod System • Message Removed",
        )

        try:
            warn_msg = await message.channel.send(embed=embed)
            await asyncio.sleep(5)
            await warn_msg.delete()
        except (discord.Forbidden, discord.NotFound):
            pass

    async def _check_spam(self, message: discord.Message) -> bool:
        uid = message.author.id
        now = message.created_at.timestamp()

        if uid not in self.message_cache:
            self.message_cache[uid] = []

        self.message_cache[uid] = [t for t in self.message_cache[uid] if now - t < 5]
        self.message_cache[uid].append(now)

        if len(self.message_cache[uid]) > MAX_MESSAGES_PER_SECOND:
            await self._delete_and_warn(
                message,
                "Spam Detected",
                f"{message.author.mention}, you are sending messages too quickly. Please slow down.",
            )
            self.message_cache[uid] = []
            return True
        return False

    async def _check_invite(self, message: discord.Message) -> bool:
        invite_pattern = re.compile(
            r"(discord\.gg|discord\.com/invite|discordapp\.com/invite)/[a-zA-Z0-9\-]+"
        )
        if invite_pattern.search(message.content):
            await self._delete_and_warn(
                message,
                "Invite Link Removed",
                f"{message.author.mention}, posting Discord invite links is not permitted in this server.",
            )
            return True
        return False

    async def _check_mention_spam(self, message: discord.Message) -> bool:
        if len(message.mentions) >= MAX_MENTIONS:
            await self._delete_and_warn(
                message,
                "Mention Spam Detected",
                f"{message.author.mention}, you mentioned too many users at once. Please avoid mass mentions.",
            )
            return True
        return False

    async def _check_caps(self, message: discord.Message) -> bool:
        content = message.content
        if len(content) < 10:
            return False
        letters = [c for c in content if c.isalpha()]
        if not letters:
            return False
        caps_ratio = sum(1 for c in letters if c.isupper()) / len(letters) * 100
        if caps_ratio >= MAX_CAPS_PERCENT:
            await self._delete_and_warn(
                message,
                "Excessive Caps Detected",
                f"{message.author.mention}, please avoid using excessive capital letters.",
            )
            return True
        return False

    async def _check_repeated_chars(self, message: discord.Message) -> bool:
        pattern = re.compile(r"(.)\1{" + str(MAX_REPEATED_CHARS) + r",}")
        if pattern.search(message.content):
            await self._delete_and_warn(
                message,
                "Repeated Characters Detected",
                f"{message.author.mention}, please avoid repeating the same characters excessively.",
            )
            return True
        return False

    async def _check_bad_words(self, message: discord.Message) -> bool:
        if not BAD_WORDS:
            return False
        content_lower = message.content.lower()
        for word in BAD_WORDS:
            if re.search(r"\b" + re.escape(word.lower()) + r"\b", content_lower):
                await self._delete_and_warn(
                    message,
                    "Prohibited Language",
                    f"{message.author.mention}, your message contained prohibited language and was removed.",
                )
                return True
        return False

    @automod.error
    @automod_enable.error
    @automod_disable.error
    @automod_config.error
    @automod_whitelist.error
    @automod_unwhitelist.error
    async def automod_error(self, ctx: commands.Context, error: commands.CommandError):
        if isinstance(error, commands.MissingPermissions):
            embed = build_embed(
                title="🔒 Access Denied",
                description="You require the **Manage Server** permission to use AutoMod commands.",
                color=COLORS["error"],
                footer=f"Requested by {ctx.author}",
            )
            await ctx.send(embed=embed)
        elif isinstance(error, commands.MemberNotFound):
            embed = build_embed(
                title="⚠️ Member Not Found",
                description="The specified member could not be found. Please mention a valid server member.",
                color=COLORS["warning"],
                footer=f"Requested by {ctx.author}",
            )
            await ctx.send(embed=embed)
        elif isinstance(error, commands.BotMissingPermissions):
            embed = build_embed(
                title="⚠️ Bot Missing Permissions",
                description="I am missing required permissions to perform this action. Please check my role permissions.",
                color=COLORS["error"],
                footer=f"Requested by {ctx.author}",
            )
            await ctx.send(embed=embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(AutoMod(bot))

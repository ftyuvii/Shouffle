import discord
from discord.ext import commands
from discord import app_commands
from datetime import timedelta
from typing import Optional, Tuple
import json
import os
import re

COLOUR    = 0xFFBFEA
WARN_FILE = "warnings.json"


def load_warns() -> dict:
    if not os.path.exists(WARN_FILE):
        return {}
    try:
        with open(WARN_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def save_warns(data: dict) -> None:
    with open(WARN_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4)


def parse_time(time_str: str) -> timedelta:
    match = re.fullmatch(r"(\d+)([smhd])", time_str.lower())
    if not match:
        raise ValueError("Invalid time format")
    value, unit = match.groups()
    return {
        "s": timedelta(seconds=int(value)),
        "m": timedelta(minutes=int(value)),
        "h": timedelta(hours=int(value)),
        "d": timedelta(days=int(value)),
    }[unit]


def format_duration(td: timedelta) -> str:
    total = int(td.total_seconds())
    days, rem        = divmod(total, 86400)
    hours, rem       = divmod(rem, 3600)
    minutes, seconds = divmod(rem, 60)
    parts = []
    if days:    parts.append(f"{days}d")
    if hours:   parts.append(f"{hours}h")
    if minutes: parts.append(f"{minutes}m")
    if seconds: parts.append(f"{seconds}s")
    return " ".join(parts) or "0s"


class Moderation(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot   = bot
        self.warns = load_warns()

    def build_embed(self, title: str, description: str,
                    thumbnail_url: Optional[str] = None) -> discord.Embed:
        e = discord.Embed(title=title, description=description, color=COLOUR)
        if thumbnail_url:
            e.set_thumbnail(url=thumbnail_url)
        if self.bot.user:
            e.set_footer(
                text=self.bot.user.name,
                icon_url=self.bot.user.display_avatar.url
            )
        return e

    def can_moderate(self, actor: discord.Member,
                     target: discord.Member, guild: discord.Guild) -> Tuple[bool, str]:
        if target == actor:
            return False, "You cannot moderate yourself."
        if guild.owner_id and target.id == guild.owner_id:
            return False, "You cannot moderate the server owner."
        if target.top_role >= actor.top_role and actor.id != guild.owner_id:
            return False, "That member has an equal or higher role than you."
        if target.top_role >= guild.me.top_role:
            return False, "My highest role is not above that member's role."
        return True, ""

    # ------------------------------------------------------------------ KICK

    @commands.command()
    @commands.has_permissions(kick_members=True)
    async def kick(self, ctx: commands.Context, member: discord.Member, *,
                   reason: str = "No reason provided"):
        ok, msg = self.can_moderate(ctx.author, member, ctx.guild)
        if not ok:
            return await ctx.send(embed=self.build_embed("<:cross:1514194117985570888> Action Blocked", msg))
        await member.kick(reason=reason)
        await ctx.send(embed=self.build_embed(
            "<:Kick:1513884038203703486> Member Kicked",
            f"**User:** {member.mention}\n"
            f"**<:right:1513879374741639248> Reason:** {reason}\n"
            f"**<:right:1513879374741639248> Moderator:** {ctx.author.mention}",
            thumbnail_url=member.display_avatar.url
        ))

    @app_commands.command(name="kick", description="Kick a member from the server")
    @app_commands.describe(member="Member to kick", reason="Reason for kick")
    @app_commands.default_permissions(kick_members=True)
    async def kick_slash(self, interaction: discord.Interaction, member: discord.Member,
                         reason: str = "No reason provided"):
        ok, msg = self.can_moderate(interaction.user, member, interaction.guild)
        if not ok:
            return await interaction.response.send_message(
                embed=self.build_embed("<:cross:1514194117985570888> Action Blocked", msg), ephemeral=True)
        await member.kick(reason=reason)
        await interaction.response.send_message(embed=self.build_embed(
            "<:Kick:1513884038203703486> Member Kicked",
            f"**User:** {member.mention}\n"
            f"**<:right:1513879374741639248> Reason:** {reason}\n"
            f"**<:right:1513879374741639248> Moderator:** {interaction.user.mention}",
            thumbnail_url=member.display_avatar.url
        ))

    # ------------------------------------------------------------------- BAN

    @commands.command()
    @commands.has_permissions(ban_members=True)
    async def ban(self, ctx: commands.Context, member: discord.Member, *,
                  reason: str = "No reason provided"):
        ok, msg = self.can_moderate(ctx.author, member, ctx.guild)
        if not ok:
            return await ctx.send(embed=self.build_embed("<:Warn:1513884025998020638> Action Blocked", msg))
        await member.ban(reason=reason, delete_message_seconds=0)
        await ctx.send(embed=self.build_embed(
            "<:Ban:1513884034088960172> Member Banned",
            f"**User:** {member.mention}\n"
            f"**<:right:1513879374741639248> Reason:** {reason}\n"
            f"**<:right:1513879374741639248> Moderator:** {ctx.author.mention}",
            thumbnail_url=member.display_avatar.url
        ))

    @app_commands.command(name="ban", description="Ban a member from the server")
    @app_commands.describe(member="Member to ban", reason="Reason for ban")
    @app_commands.default_permissions(ban_members=True)
    async def ban_slash(self, interaction: discord.Interaction, member: discord.Member,
                        reason: str = "No reason provided"):
        ok, msg = self.can_moderate(interaction.user, member, interaction.guild)
        if not ok:
            return await interaction.response.send_message(
                embed=self.build_embed("<:Warn:1513884025998020638> Action Blocked", msg), ephemeral=True)
        await member.ban(reason=reason, delete_message_seconds=0)
        await interaction.response.send_message(embed=self.build_embed(
            "<:Ban:1513884034088960172> Member Banned",
            f"**User:** {member.mention}\n"
            f"**<:right:1513879374741639248> Reason:** {reason}\n"
            f"**<:right:1513879374741639248> Moderator:** {interaction.user.mention}",
            thumbnail_url=member.display_avatar.url
        ))

    # --------------------------------------------------------------- SOFTBAN

    @commands.command()
    @commands.has_permissions(ban_members=True)
    async def softban(self, ctx: commands.Context, member: discord.Member, *,
                      reason: str = "No reason provided"):
        ok, msg = self.can_moderate(ctx.author, member, ctx.guild)
        if not ok:
            return await ctx.send(embed=self.build_embed("<:Warn:1513884025998020638> Action Blocked", msg))
        avatar, name, uid = member.display_avatar.url, str(member), member.id
        await member.ban(reason=f"Softban: {reason}", delete_message_seconds=604800)
        await ctx.guild.unban(discord.Object(id=uid), reason="Softban unban")
        await ctx.send(embed=self.build_embed(
            "<:Ban:1513884034088960172> Member Soft-Banned",
            f"**User:** {name} (`{uid}`)\n"
            f"**<:right:1513879374741639248> Reason:** {reason}\n"
            f"**<:right:1513879374741639248> Moderator:** {ctx.author.mention}\n"
            f"**<:right:1513879374741639248> Note:** Messages deleted, member may rejoin.",
            thumbnail_url=avatar
        ))

    @app_commands.command(name="softban", description="Softban a member (ban + unban, clears messages)")
    @app_commands.describe(member="Member to softban", reason="Reason for softban")
    @app_commands.default_permissions(ban_members=True)
    async def softban_slash(self, interaction: discord.Interaction, member: discord.Member,
                            reason: str = "No reason provided"):
        ok, msg = self.can_moderate(interaction.user, member, interaction.guild)
        if not ok:
            return await interaction.response.send_message(
                embed=self.build_embed("<:Warn:1513884025998020638> Action Blocked", msg), ephemeral=True)
        avatar, name, uid = member.display_avatar.url, str(member), member.id
        await member.ban(reason=f"Softban: {reason}", delete_message_seconds=604800)
        await interaction.guild.unban(discord.Object(id=uid), reason="Softban unban")
        await interaction.response.send_message(embed=self.build_embed(
            "<:Ban:1513884034088960172> Member Soft-Banned",
            f"**User:** {name} (`{uid}`)\n"
            f"**<:right:1513879374741639248> Reason:** {reason}\n"
            f"**<:right:1513879374741639248> Moderator:** {interaction.user.mention}\n"
            f"**<:right:1513879374741639248> Note:** Messages deleted, member may rejoin.",
            thumbnail_url=avatar
        ))

    # --------------------------------------------------------------- UNBAN

    @commands.command()
    @commands.has_permissions(ban_members=True)
    async def unban(self, ctx: commands.Context, user_id: int):
        try:
            user = await self.bot.fetch_user(user_id)
        except discord.NotFound:
            return await ctx.send(embed=self.build_embed(
                "<:cross:1514194117985570888> User Not Found", f"No user found with ID `{user_id}`."))
        try:
            await ctx.guild.unban(user)
        except discord.NotFound:
            return await ctx.send(embed=self.build_embed(
                "<:cross:1514194117985570888> Not Banned", f"`{user}` is not banned in this server."))
        await ctx.send(embed=self.build_embed(
            "<:tick:1514194122192191569> User Unbanned",
            f"**User:** {user.mention}\n"
            f"**<:right:1513879374741639248> ID:** `{user.id}`\n"
            f"**<:right:1513879374741639248> Moderator:** {ctx.author.mention}",
            thumbnail_url=user.display_avatar.url
        ))

    @app_commands.command(name="unban", description="Unban a user by their ID")
    @app_commands.describe(user_id="User ID to unban")
    @app_commands.default_permissions(ban_members=True)
    async def unban_slash(self, interaction: discord.Interaction, user_id: str):
        try:
            user = await self.bot.fetch_user(int(user_id))
        except (discord.NotFound, ValueError):
            return await interaction.response.send_message(
                embed=self.build_embed("<:cross:1514194117985570888> User Not Found",
                                       f"No user found with ID `{user_id}`."), ephemeral=True)
        try:
            await interaction.guild.unban(user)
        except discord.NotFound:
            return await interaction.response.send_message(
                embed=self.build_embed("<:cross:1514194117985570888> Not Banned",
                                       f"`{user}` is not banned in this server."), ephemeral=True)
        await interaction.response.send_message(embed=self.build_embed(
            "<:tick:1514194122192191569> User Unbanned",
            f"**User:** {user.mention}\n"
            f"**<:right:1513879374741639248> ID:** `{user.id}`\n"
            f"**<:right:1513879374741639248> Moderator:** {interaction.user.mention}",
            thumbnail_url=user.display_avatar.url
        ))

    # ------------------------------------------------------------------ MUTE

    @commands.command(aliases=["timeout"])
    @commands.has_permissions(moderate_members=True)
    async def mute(self, ctx: commands.Context, member: discord.Member,
                   duration: str, *, reason: str = "No reason provided"):
        ok, msg = self.can_moderate(ctx.author, member, ctx.guild)
        if not ok:
            return await ctx.send(embed=self.build_embed("<:cross:1514194117985570888> Action Blocked", msg))
        try:
            td = parse_time(duration)
        except ValueError:
            return await ctx.send(embed=self.build_embed(
                "<:cross:1514194117985570888> Invalid Time", "Use formats like `30s`, `10m`, `2h`, `1d`."))
        await member.timeout(td, reason=reason)
        await ctx.send(embed=self.build_embed(
            "<:tick:1514194122192191569> Member Timed Out",
            f"**User:** {member.mention}\n"
            f"**<:right:1513879374741639248> Duration:** {format_duration(td)}\n"
            f"**<:right:1513879374741639248> Reason:** {reason}\n"
            f"**<:right:1513879374741639248> Moderator:** {ctx.author.mention}",
            thumbnail_url=member.display_avatar.url
        ))

    @app_commands.command(name="mute", description="Timeout a member")
    @app_commands.describe(member="Member to mute", duration="Duration e.g. 10m, 2h, 1d", reason="Reason")
    @app_commands.default_permissions(moderate_members=True)
    async def mute_slash(self, interaction: discord.Interaction, member: discord.Member,
                         duration: str, reason: str = "No reason provided"):
        ok, msg = self.can_moderate(interaction.user, member, interaction.guild)
        if not ok:
            return await interaction.response.send_message(
                embed=self.build_embed("<:cross:1514194117985570888> Action Blocked", msg), ephemeral=True)
        try:
            td = parse_time(duration)
        except ValueError:
            return await interaction.response.send_message(
                embed=self.build_embed("<:cross:1514194117985570888> Invalid Time",
                                       "Use formats like `30s`, `10m`, `2h`, `1d`."), ephemeral=True)
        await member.timeout(td, reason=reason)
        await interaction.response.send_message(embed=self.build_embed(
            "<:tick:1514194122192191569> Member Timed Out",
            f"**User:** {member.mention}\n"
            f"**<:right:1513879374741639248> Duration:** {format_duration(td)}\n"
            f"**<:right:1513879374741639248> Reason:** {reason}\n"
            f"**<:right:1513879374741639248> Moderator:** {interaction.user.mention}",
            thumbnail_url=member.display_avatar.url
        ))

    # ---------------------------------------------------------------- UNMUTE

    @commands.command(aliases=["untimeout"])
    @commands.has_permissions(moderate_members=True)
    async def unmute(self, ctx: commands.Context, member: discord.Member):
        await member.timeout(None)
        await ctx.send(embed=self.build_embed(
            "<:tick:1514194122192191569> Member Unmuted",
            f"**User:** {member.mention}\n"
            f"**<:right:1513879374741639248> Status:** Timeout removed — can speak again.\n"
            f"**<:right:1513879374741639248> Moderator:** {ctx.author.mention}",
            thumbnail_url=member.display_avatar.url
        ))

    @app_commands.command(name="unmute", description="Remove timeout from a member")
    @app_commands.describe(member="Member to unmute")
    @app_commands.default_permissions(moderate_members=True)
    async def unmute_slash(self, interaction: discord.Interaction, member: discord.Member):
        await member.timeout(None)
        await interaction.response.send_message(embed=self.build_embed(
            "<:tick:1514194122192191569> Member Unmuted",
            f"**User:** {member.mention}\n"
            f"**<:right:1513879374741639248> Status:** Timeout removed — can speak again.\n"
            f"**<:right:1513879374741639248> Moderator:** {interaction.user.mention}",
            thumbnail_url=member.display_avatar.url
        ))

    # ------------------------------------------------------------------ NICK

    @commands.command()
    @commands.has_permissions(manage_nicknames=True)
    async def nick(self, ctx: commands.Context, member: discord.Member, *,
                   nickname: Optional[str] = None):
        ok, msg = self.can_moderate(ctx.author, member, ctx.guild)
        if not ok:
            return await ctx.send(embed=self.build_embed("<:Warn:1513884025998020638> Action Blocked", msg))
        old_name = member.display_name
        await member.edit(nick=nickname)
        await ctx.send(embed=self.build_embed(
            "<:tick:1514194122192191569> Nickname Updated",
            f"**User:** {member.mention}\n"
            f"**<:right:1513879374741639248> Old:** `{old_name}`\n"
            f"**<:right:1513879374741639248> New:** `{nickname or 'Reset'}`\n"
            f"**<:right:1513879374741639248> Moderator:** {ctx.author.mention}",
            thumbnail_url=member.display_avatar.url
        ))

    @app_commands.command(name="nick", description="Change or reset a member's nickname")
    @app_commands.describe(member="Target member", nickname="New nickname (leave blank to reset)")
    @app_commands.default_permissions(manage_nicknames=True)
    async def nick_slash(self, interaction: discord.Interaction, member: discord.Member,
                         nickname: Optional[str] = None):
        ok, msg = self.can_moderate(interaction.user, member, interaction.guild)
        if not ok:
            return await interaction.response.send_message(
                embed=self.build_embed("<:Warn:1513884025998020638> Action Blocked", msg), ephemeral=True)
        old_name = member.display_name
        await member.edit(nick=nickname)
        await interaction.response.send_message(embed=self.build_embed(
            "<:tick:1514194122192191569> Nickname Updated",
            f"**User:** {member.mention}\n"
            f"**<:right:1513879374741639248> Old:** `{old_name}`\n"
            f"**<:right:1513879374741639248> New:** `{nickname or 'Reset'}`\n"
            f"**<:right:1513879374741639248> Moderator:** {interaction.user.mention}",
            thumbnail_url=member.display_avatar.url
        ))

    # ------------------------------------------------------------------ WARN

    @commands.command()
    @commands.has_permissions(kick_members=True)
    async def warn(self, ctx: commands.Context, member: discord.Member, *,
                   reason: str = "No reason provided"):
        ok, msg = self.can_moderate(ctx.author, member, ctx.guild)
        if not ok:
            return await ctx.send(embed=self.build_embed("<:Warn:1513884025998020638> Action Blocked", msg))
        gid, uid = str(ctx.guild.id), str(member.id)
        self.warns.setdefault(gid, {}).setdefault(uid, [])
        self.warns[gid][uid].append(reason)
        save_warns(self.warns)
        count = len(self.warns[gid][uid])
        await ctx.send(embed=self.build_embed(
            "<:Warn:1513884025998020638> Warning Issued",
            f"**User:** {member.mention}\n"
            f"**<:right:1513879374741639248> Reason:** {reason}\n"
            f"**<:right:1513879374741639248> Warnings:** {count}/5\n"
            f"**<:right:1513879374741639248> Moderator:** {ctx.author.mention}",
            thumbnail_url=member.display_avatar.url
        ))
        if count >= 5:
            await member.ban(reason="Auto-ban: reached 5 warnings")
            self.warns[gid][uid] = []
            save_warns(self.warns)
            await ctx.send(embed=self.build_embed(
                "⛔ Auto-Ban", f"{member.mention} has been banned for reaching **5 warnings**."))

    @app_commands.command(name="warn", description="Warn a member")
    @app_commands.describe(member="Member to warn", reason="Reason for warning")
    @app_commands.default_permissions(kick_members=True)
    async def warn_slash(self, interaction: discord.Interaction, member: discord.Member,
                         reason: str = "No reason provided"):
        ok, msg = self.can_moderate(interaction.user, member, interaction.guild)
        if not ok:
            return await interaction.response.send_message(
                embed=self.build_embed("<:Warn:1513884025998020638> Action Blocked", msg), ephemeral=True)
        gid, uid = str(interaction.guild.id), str(member.id)
        self.warns.setdefault(gid, {}).setdefault(uid, [])
        self.warns[gid][uid].append(reason)
        save_warns(self.warns)
        count = len(self.warns[gid][uid])
        await interaction.response.send_message(embed=self.build_embed(
            "<:Warn:1513884025998020638> Warning Issued",
            f"**User:** {member.mention}\n"
            f"**<:right:1513879374741639248> Reason:** {reason}\n"
            f"**<:right:1513879374741639248> Warnings:** {count}/5\n"
            f"**<:right:1513879374741639248> Moderator:** {interaction.user.mention}",
            thumbnail_url=member.display_avatar.url
        ))
        if count >= 5:
            await member.ban(reason="Auto-ban: reached 5 warnings")
            self.warns[gid][uid] = []
            save_warns(self.warns)
            await interaction.followup.send(embed=self.build_embed(
                "⛔ Auto-Ban", f"{member.mention} has been banned for reaching **5 warnings**."))

    # ----------------------------------------------------------------- WARNS

    @commands.command()
    async def warns(self, ctx: commands.Context, member: discord.Member):
        gid, uid  = str(ctx.guild.id), str(member.id)
        warn_list = self.warns.get(gid, {}).get(uid, [])
        if not warn_list:
            return await ctx.send(embed=self.build_embed(
                "📋 Warnings", f"{member.mention} has no warnings.",
                thumbnail_url=member.display_avatar.url))
        text = "\n".join(f"`{i+1}.` {w}" for i, w in enumerate(warn_list))
        await ctx.send(embed=self.build_embed(
            f"📋 Warning History — {member.display_name}", text,
            thumbnail_url=member.display_avatar.url))

    @app_commands.command(name="warns", description="View warnings of a member")
    @app_commands.describe(member="Member to check")
    async def warns_slash(self, interaction: discord.Interaction, member: discord.Member):
        gid, uid  = str(interaction.guild.id), str(member.id)
        warn_list = self.warns.get(gid, {}).get(uid, [])
        if not warn_list:
            return await interaction.response.send_message(embed=self.build_embed(
                "📋 Warnings", f"{member.mention} has no warnings.",
                thumbnail_url=member.display_avatar.url))
        text = "\n".join(f"`{i+1}.` {w}" for i, w in enumerate(warn_list))
        await interaction.response.send_message(embed=self.build_embed(
            f"📋 Warning History — {member.display_name}", text,
            thumbnail_url=member.display_avatar.url))

    # ------------------------------------------------------------ CLEARWARNS

    @commands.command()
    @commands.has_permissions(kick_members=True)
    async def clearwarns(self, ctx: commands.Context, member: discord.Member):
        gid, uid = str(ctx.guild.id), str(member.id)
        self.warns.setdefault(gid, {})[uid] = []
        save_warns(self.warns)
        await ctx.send(embed=self.build_embed(
            "<:tick:1514194122192191569> Warnings Cleared",
            f"All warnings for {member.mention} have been removed.\n"
            f"**<:right:1513879374741639248> Moderator:** {ctx.author.mention}",
            thumbnail_url=member.display_avatar.url
        ))

    @app_commands.command(name="clearwarns", description="Clear all warnings of a member")
    @app_commands.describe(member="Member whose warnings to clear")
    @app_commands.default_permissions(kick_members=True)
    async def clearwarns_slash(self, interaction: discord.Interaction, member: discord.Member):
        gid, uid = str(interaction.guild.id), str(member.id)
        self.warns.setdefault(gid, {})[uid] = []
        save_warns(self.warns)
        await interaction.response.send_message(embed=self.build_embed(
            "<:tick:1514194122192191569> Warnings Cleared",
            f"All warnings for {member.mention} have been removed.\n"
            f"**<:right:1513879374741639248> Moderator:** {interaction.user.mention}",
            thumbnail_url=member.display_avatar.url
        ))

    # ------------------------------------------------------------------ LOCK

    @commands.command()
    @commands.has_permissions(manage_channels=True)
    async def lock(self, ctx: commands.Context):
        overwrite = ctx.channel.overwrites_for(ctx.guild.default_role)
        overwrite.send_messages = False
        await ctx.channel.set_permissions(ctx.guild.default_role, overwrite=overwrite)
        await ctx.send(embed=self.build_embed(
            "<:tick:1514194122192191569> Channel Locked",
            f"**<:right:1513879374741639248>** {ctx.channel.mention} has been **locked**.\n"
            f"**<:right:1513879374741639248> Moderator:** {ctx.author.mention}"
        ))

    @app_commands.command(name="lock", description="Lock the current channel")
    @app_commands.default_permissions(manage_channels=True)
    async def lock_slash(self, interaction: discord.Interaction):
        channel = interaction.channel
        overwrite = channel.overwrites_for(interaction.guild.default_role)
        overwrite.send_messages = False
        await channel.set_permissions(interaction.guild.default_role, overwrite=overwrite)
        await interaction.response.send_message(embed=self.build_embed(
            "<:tick:1514194122192191569> Channel Locked",
            f"**<:right:1513879374741639248>** {channel.mention} has been **locked**.\n"
            f"**<:right:1513879374741639248> Moderator:** {interaction.user.mention}"
        ))

    # ---------------------------------------------------------------- UNLOCK

    @commands.command()
    @commands.has_permissions(manage_channels=True)
    async def unlock(self, ctx: commands.Context):
        overwrite = ctx.channel.overwrites_for(ctx.guild.default_role)
        overwrite.send_messages = None
        await ctx.channel.set_permissions(ctx.guild.default_role, overwrite=overwrite)
        await ctx.send(embed=self.build_embed(
            "<:Lock:1513884030276206662> Channel Unlocked",
            f"**<:right:1513879374741639248>** {ctx.channel.mention} has been **unlocked**.\n"
            f"**<:right:1513879374741639248> Moderator:** {ctx.author.mention}"
        ))

    @app_commands.command(name="unlock", description="Unlock the current channel")
    @app_commands.default_permissions(manage_channels=True)
    async def unlock_slash(self, interaction: discord.Interaction):
        channel = interaction.channel
        overwrite = channel.overwrites_for(interaction.guild.default_role)
        overwrite.send_messages = None
        await channel.set_permissions(interaction.guild.default_role, overwrite=overwrite)
        await interaction.response.send_message(embed=self.build_embed(
            "<:Lock:1513884030276206662> Channel Unlocked",
            f"**<:right:1513879374741639248>** {channel.mention} has been **unlocked**.\n"
            f"**<:right:1513879374741639248> Moderator:** {interaction.user.mention}"
        ))

    # --------------------------------------------------------------- SLOWMODE

    @commands.command()
    @commands.has_permissions(manage_channels=True)
    async def slowmode(self, ctx: commands.Context, seconds: int):
        if not 0 <= seconds <= 21600:
            return await ctx.send(embed=self.build_embed(
                "<:cross:1514194117985570888> Invalid Value",
                "Slowmode must be between `0` and `21600` seconds."))
        await ctx.channel.edit(slowmode_delay=seconds)
        desc = (f"Slowmode disabled in {ctx.channel.mention}." if seconds == 0 else
                f"Slowmode set to **{seconds}s** in {ctx.channel.mention}.\n"
                f"**<:right:1513879374741639248> Moderator:** {ctx.author.mention}")
        await ctx.send(embed=self.build_embed("<:tick:1514194122192191569> Slowmode Updated", desc))

    @app_commands.command(name="slowmode", description="Set slowmode for the current channel")
    @app_commands.describe(seconds="Slowmode delay in seconds (0 to disable, max 21600)")
    @app_commands.default_permissions(manage_channels=True)
    async def slowmode_slash(self, interaction: discord.Interaction, seconds: int):
        if not 0 <= seconds <= 21600:
            return await interaction.response.send_message(
                embed=self.build_embed("<:cross:1514194117985570888> Invalid Value",
                                       "Slowmode must be between `0` and `21600` seconds."), ephemeral=True)
        await interaction.channel.edit(slowmode_delay=seconds)
        desc = (f"Slowmode disabled in {interaction.channel.mention}." if seconds == 0 else
                f"Slowmode set to **{seconds}s** in {interaction.channel.mention}.\n"
                f"**<:right:1513879374741639248> Moderator:** {interaction.user.mention}")
        await interaction.response.send_message(
            embed=self.build_embed("<:tick:1514194122192191569> Slowmode Updated", desc))

    # ----------------------------------------------------------------- PURGE

    @commands.command()
    @commands.has_permissions(manage_messages=True)
    async def purge(self, ctx: commands.Context, amount: int):
        if amount < 1:
            return await ctx.send(embed=self.build_embed(
                "<:Warn:1513884025998020638> Invalid Amount", "Amount must be greater than `0`."))
        deleted = await ctx.channel.purge(limit=amount + 1)
        msg = await ctx.send(embed=self.build_embed(
            "<:cat:1513885435221508227> Purge Complete",
            f"Deleted **{len(deleted) - 1}** messages in {ctx.channel.mention}."))
        await msg.delete(delay=3)

    @app_commands.command(name="purge", description="Delete a number of messages from this channel")
    @app_commands.describe(amount="Number of messages to delete")
    @app_commands.default_permissions(manage_messages=True)
    async def purge_slash(self, interaction: discord.Interaction, amount: int):
        if amount < 1:
            return await interaction.response.send_message(
                embed=self.build_embed("<:Warn:1513884025998020638> Invalid Amount",
                                       "Amount must be greater than `0`."), ephemeral=True)
        await interaction.response.defer(ephemeral=True)
        deleted = await interaction.channel.purge(limit=amount)
        await interaction.followup.send(embed=self.build_embed(
            "<:cat:1513885435221508227> Purge Complete",
            f"Deleted **{len(deleted)}** messages in {interaction.channel.mention}."), ephemeral=True)

    # --------------------------------------------------------------- ROLEADD

    @commands.command()
    @commands.has_permissions(manage_roles=True)
    async def roleadd(self, ctx: commands.Context, member: discord.Member, *, role: discord.Role):
        if role >= ctx.guild.me.top_role:
            return await ctx.send(embed=self.build_embed(
                "<:cross:1514194117985570888> Permission Error",
                "I cannot assign a role equal to or higher than my own."))
        if role in member.roles:
            return await ctx.send(embed=self.build_embed(
                "<:Warn:1513884025998020638> Already Assigned",
                f"{member.mention} already has the {role.mention} role."))
        await member.add_roles(role, reason=f"Role added by {ctx.author}")
        await ctx.send(embed=self.build_embed(
            "<:tick:1514194122192191569> Role Added",
            f"**User:** {member.mention}\n"
            f"**<:right:1513879374741639248> Role:** {role.mention}\n"
            f"**<:right:1513879374741639248> Moderator:** {ctx.author.mention}",
            thumbnail_url=member.display_avatar.url
        ))

    @app_commands.command(name="roleadd", description="Add a role to a member")
    @app_commands.describe(member="Target member", role="Role to add")
    @app_commands.default_permissions(manage_roles=True)
    async def roleadd_slash(self, interaction: discord.Interaction,
                            member: discord.Member, role: discord.Role):
        if role >= interaction.guild.me.top_role:
            return await interaction.response.send_message(
                embed=self.build_embed("<:cross:1514194117985570888> Permission Error",
                                       "I cannot assign a role equal to or higher than my own."), ephemeral=True)
        if role in member.roles:
            return await interaction.response.send_message(
                embed=self.build_embed("<:Warn:1513884025998020638> Already Assigned",
                                       f"{member.mention} already has the {role.mention} role."), ephemeral=True)
        await member.add_roles(role, reason=f"Role added by {interaction.user}")
        await interaction.response.send_message(embed=self.build_embed(
            "<:tick:1514194122192191569> Role Added",
            f"**User:** {member.mention}\n"
            f"**<:right:1513879374741639248> Role:** {role.mention}\n"
            f"**<:right:1513879374741639248> Moderator:** {interaction.user.mention}",
            thumbnail_url=member.display_avatar.url
        ))

    # ------------------------------------------------------------ ROLEREMOVE

    @commands.command()
    @commands.has_permissions(manage_roles=True)
    async def roleremove(self, ctx: commands.Context, member: discord.Member, *, role: discord.Role):
        if role >= ctx.guild.me.top_role:
            return await ctx.send(embed=self.build_embed(
                "<:cross:1514194117985570888> Permission Error",
                "I cannot remove a role equal to or higher than my own."))
        if role not in member.roles:
            return await ctx.send(embed=self.build_embed(
                "<:Warn:1513884025998020638> Not Assigned",
                f"{member.mention} does not have the {role.mention} role."))
        await member.remove_roles(role, reason=f"Role removed by {ctx.author}")
        await ctx.send(embed=self.build_embed(
            "<:tick:1514194122192191569> Role Removed",
            f"**User:** {member.mention}\n"
            f"**<:right:1513879374741639248> Role:** {role.mention}\n"
            f"**<:right:1513879374741639248> Moderator:** {ctx.author.mention}",
            thumbnail_url=member.display_avatar.url
        ))

    @app_commands.command(name="roleremove", description="Remove a role from a member")
    @app_commands.describe(member="Target member", role="Role to remove")
    @app_commands.default_permissions(manage_roles=True)
    async def roleremove_slash(self, interaction: discord.Interaction,
                               member: discord.Member, role: discord.Role):
        if role >= interaction.guild.me.top_role:
            return await interaction.response.send_message(
                embed=self.build_embed("<:cross:1514194117985570888> Permission Error",
                                       "I cannot remove a role equal to or higher than my own."), ephemeral=True)
        if role not in member.roles:
            return await interaction.response.send_message(
                embed=self.build_embed("<:Warn:1513884025998020638> Not Assigned",
                                       f"{member.mention} does not have the {role.mention} role."), ephemeral=True)
        await member.remove_roles(role, reason=f"Role removed by {interaction.user}")
        await interaction.response.send_message(embed=self.build_embed(
            "<:tick:1514194122192191569> Role Removed",
            f"**User:** {member.mention}\n"
            f"**<:right:1513879374741639248> Role:** {role.mention}\n"
            f"**<:right:1513879374741639248> Moderator:** {interaction.user.mention}",
            thumbnail_url=member.display_avatar.url
        ))

    # --------------------------------------------------------------- DEAFEN

    @commands.command()
    @commands.has_permissions(deafen_members=True)
    async def deafen(self, ctx: commands.Context, member: discord.Member, *,
                     reason: str = "No reason provided"):
        ok, msg = self.can_moderate(ctx.author, member, ctx.guild)
        if not ok:
            return await ctx.send(embed=self.build_embed("<:cross:1514194117985570888> Action Blocked", msg))
        if not member.voice:
            return await ctx.send(embed=self.build_embed(
                "<:Warn:1513884025998020638> Not in Voice", f"{member.mention} is not in a voice channel."))
        await member.edit(deafen=True, reason=reason)
        await ctx.send(embed=self.build_embed(
            "<:tick:1514194122192191569> Member Deafened",
            f"**User:** {member.mention}\n"
            f"**<:right:1513879374741639248> Reason:** {reason}\n"
            f"**<:right:1513879374741639248> Moderator:** {ctx.author.mention}",
            thumbnail_url=member.display_avatar.url
        ))

    @app_commands.command(name="deafen", description="Server-deafen a member in voice")
    @app_commands.describe(member="Member to deafen", reason="Reason")
    @app_commands.default_permissions(deafen_members=True)
    async def deafen_slash(self, interaction: discord.Interaction, member: discord.Member,
                           reason: str = "No reason provided"):
        ok, msg = self.can_moderate(interaction.user, member, interaction.guild)
        if not ok:
            return await interaction.response.send_message(
                embed=self.build_embed("<:cross:1514194117985570888> Action Blocked", msg), ephemeral=True)
        if not member.voice:
            return await interaction.response.send_message(
                embed=self.build_embed("<:Warn:1513884025998020638> Not in Voice",
                                       f"{member.mention} is not in a voice channel."), ephemeral=True)
        await member.edit(deafen=True, reason=reason)
        await interaction.response.send_message(embed=self.build_embed(
            "<:tick:1514194122192191569> Member Deafened",
            f"**User:** {member.mention}\n"
            f"**<:right:1513879374741639248> Reason:** {reason}\n"
            f"**<:right:1513879374741639248> Moderator:** {interaction.user.mention}",
            thumbnail_url=member.display_avatar.url
        ))

    # ------------------------------------------------------------- UNDEAFEN

    @commands.command()
    @commands.has_permissions(deafen_members=True)
    async def undeafen(self, ctx: commands.Context, member: discord.Member):
        if not member.voice:
            return await ctx.send(embed=self.build_embed(
                "<:Warn:1513884025998020638> Not in Voice", f"{member.mention} is not in a voice channel."))
        await member.edit(deafen=False)
        await ctx.send(embed=self.build_embed(
            "<:tick:1514194122192191569> Member Undeafened",
            f"**User:** {member.mention}\n"
            f"**<:right:1513879374741639248> Status:** Can now hear audio.\n"
            f"**<:right:1513879374741639248> Moderator:** {ctx.author.mention}",
            thumbnail_url=member.display_avatar.url
        ))

    @app_commands.command(name="undeafen", description="Remove server-deafen from a member")
    @app_commands.describe(member="Member to undeafen")
    @app_commands.default_permissions(deafen_members=True)
    async def undeafen_slash(self, interaction: discord.Interaction, member: discord.Member):
        if not member.voice:
            return await interaction.response.send_message(
                embed=self.build_embed("<:Warn:1513884025998020638> Not in Voice",
                                       f"{member.mention} is not in a voice channel."), ephemeral=True)
        await member.edit(deafen=False)
        await interaction.response.send_message(embed=self.build_embed(
            "<:tick:1514194122192191569> Member Undeafened",
            f"**User:** {member.mention}\n"
            f"**<:right:1513879374741639248> Status:** Can now hear audio.\n"
            f"**<:right:1513879374741639248> Moderator:** {interaction.user.mention}",
            thumbnail_url=member.display_avatar.url
        ))

    # ---------------------------------------------------------------- VCBAN

    @commands.command()
    @commands.has_permissions(move_members=True)
    async def vcban(self, ctx: commands.Context, member: discord.Member, *,
                    reason: str = "No reason provided"):
        ok, msg = self.can_moderate(ctx.author, member, ctx.guild)
        if not ok:
            return await ctx.send(embed=self.build_embed("<:cross:1514194117985570888> Action Blocked", msg))
        if not member.voice:
            return await ctx.send(embed=self.build_embed(
                "<:Warn:1513884025998020638> Not in Voice", f"{member.mention} is not in a voice channel."))
        await member.move_to(None, reason=reason)
        await ctx.send(embed=self.build_embed(
            "<:Kick:1513884038203703486> Disconnected from Voice",
            f"**User:** {member.mention}\n"
            f"**<:right:1513879374741639248> Reason:** {reason}\n"
            f"**<:right:1513879374741639248> Moderator:** {ctx.author.mention}",
            thumbnail_url=member.display_avatar.url
        ))

    @app_commands.command(name="vcban", description="Disconnect a member from voice channel")
    @app_commands.describe(member="Member to disconnect", reason="Reason")
    @app_commands.default_permissions(move_members=True)
    async def vcban_slash(self, interaction: discord.Interaction, member: discord.Member,
                          reason: str = "No reason provided"):
        ok, msg = self.can_moderate(interaction.user, member, interaction.guild)
        if not ok:
            return await interaction.response.send_message(
                embed=self.build_embed("<:cross:1514194117985570888> Action Blocked", msg), ephemeral=True)
        if not member.voice:
            return await interaction.response.send_message(
                embed=self.build_embed("<:Warn:1513884025998020638> Not in Voice",
                                       f"{member.mention} is not in a voice channel."), ephemeral=True)
        await member.move_to(None, reason=reason)
        await interaction.response.send_message(embed=self.build_embed(
            "<:Kick:1513884038203703486> Disconnected from Voice",
            f"**User:** {member.mention}\n"
            f"**<:right:1513879374741639248> Reason:** {reason}\n"
            f"**<:right:1513879374741639248> Moderator:** {interaction.user.mention}",
            thumbnail_url=member.display_avatar.url
        ))

    # --------------------------------------------------------------- USERINFO

    @commands.command(aliases=["ui", "whois"])
    async def userinfo(self, ctx: commands.Context, member: Optional[discord.Member] = None):
        member    = member or ctx.author
        joined    = discord.utils.format_dt(member.joined_at, "D") if member.joined_at else "Unknown"
        created   = discord.utils.format_dt(member.created_at, "D")
        roles     = [r.mention for r in reversed(member.roles) if r != ctx.guild.default_role]
        roles_str = " ".join(roles) if roles else "`None`"
        status    = str(member.status).title() if hasattr(member, "status") else "Unknown"
        await ctx.send(embed=self.build_embed(
            f"👤 User Info — {member.display_name}",
            f"**User:** {member.mention}\n"
            f"**<:right:1513879374741639248> ID:** `{member.id}`\n"
            f"**<:right:1513879374741639248> Status:** {status}\n"
            f"**<:right:1513879374741639248> Account Created:** {created}\n"
            f"**<:right:1513879374741639248> Joined Server:** {joined}\n"
            f"**<:right:1513879374741639248> Roles [{len(roles)}]:** {roles_str}",
            thumbnail_url=member.display_avatar.url
        ))

    @app_commands.command(name="userinfo", description="Get information about a member")
    @app_commands.describe(member="Member to check (leave blank for yourself)")
    async def userinfo_slash(self, interaction: discord.Interaction,
                             member: Optional[discord.Member] = None):
        member    = member or interaction.user
        joined    = discord.utils.format_dt(member.joined_at, "D") if member.joined_at else "Unknown"
        created   = discord.utils.format_dt(member.created_at, "D")
        roles     = [r.mention for r in reversed(member.roles) if r != interaction.guild.default_role]
        roles_str = " ".join(roles) if roles else "`None`"
        status    = str(member.status).title() if hasattr(member, "status") else "Unknown"
        await interaction.response.send_message(embed=self.build_embed(
            f"👤 User Info — {member.display_name}",
            f"**User:** {member.mention}\n"
            f"**<:right:1513879374741639248> ID:** `{member.id}`\n"
            f"**<:right:1513879374741639248> Status:** {status}\n"
            f"**<:right:1513879374741639248> Account Created:** {created}\n"
            f"**<:right:1513879374741639248> Joined Server:** {joined}\n"
            f"**<:right:1513879374741639248> Roles [{len(roles)}]:** {roles_str}",
            thumbnail_url=member.display_avatar.url
        ))

    # ------------------------------------------------------------- SERVERINFO

    @commands.command(aliases=["si"])
    async def serverinfo(self, ctx: commands.Context):
        guild   = ctx.guild
        created = discord.utils.format_dt(guild.created_at, "D")
        owner   = guild.owner.mention if guild.owner else "`Unknown`"
        await ctx.send(embed=self.build_embed(
            f"🏠 Server Info — {guild.name}",
            f"**<:right:1513879374741639248> Owner:** {owner}\n"
            f"**<:right:1513879374741639248> Members:** {guild.member_count}\n"
            f"**<:right:1513879374741639248> Channels:** {len(guild.channels)}\n"
            f"**<:right:1513879374741639248> Roles:** {len(guild.roles)}\n"
            f"**<:right:1513879374741639248> Created:** {created}\n"
            f"**<:right:1513879374741639248> ID:** `{guild.id}`",
            thumbnail_url=guild.icon.url if guild.icon else None
        ))

    @app_commands.command(name="serverinfo", description="Get information about this server")
    async def serverinfo_slash(self, interaction: discord.Interaction):
        guild   = interaction.guild
        created = discord.utils.format_dt(guild.created_at, "D")
        owner   = guild.owner.mention if guild.owner else "`Unknown`"
        await interaction.response.send_message(embed=self.build_embed(
            f"🏠 Server Info — {guild.name}",
            f"**<:right:1513879374741639248> Owner:** {owner}\n"
            f"**<:right:1513879374741639248> Members:** {guild.member_count}\n"
            f"**<:right:1513879374741639248> Channels:** {len(guild.channels)}\n"
            f"**<:right:1513879374741639248> Roles:** {len(guild.roles)}\n"
            f"**<:right:1513879374741639248> Created:** {created}\n"
            f"**<:right:1513879374741639248> ID:** `{guild.id}`",
            thumbnail_url=guild.icon.url if guild.icon else None
        ))


async def setup(bot: commands.Bot):
    await bot.add_cog(Moderation(bot))
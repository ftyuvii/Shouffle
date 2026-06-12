import discord
from discord.ext import commands
from datetime import timedelta
from typing import Tuple, Optional
import json
import os
import re

COLOUR    = 0xADD8E6
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
    days, rem   = divmod(total, 86400)
    hours, rem  = divmod(rem, 3600)
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

    def can_moderate(self, ctx: commands.Context,
                     member: discord.Member) -> Tuple[bool, str]:
        if member == ctx.author:
            return False, "You cannot moderate yourself."
        if ctx.guild.owner_id and member.id == ctx.guild.owner_id:
            return False, "You cannot moderate the server owner."
        if member.top_role >= ctx.author.top_role and ctx.author.id != ctx.guild.owner_id:
            return False, "That member has an equal or higher role than you."
        if member.top_role >= ctx.guild.me.top_role:
            return False, "My highest role is not above that member's role."
        return True, ""

    @commands.command()
    @commands.has_permissions(kick_members=True)
    async def kick(self, ctx: commands.Context, member: discord.Member, *,
                   reason: str = "No reason provided"):
        ok, msg = self.can_moderate(ctx, member)
        if not ok:
            return await ctx.send(embed=self.build_embed(
                "<:cross:1514194117985570888> Action Blocked", msg))

        await member.kick(reason=reason)
        await ctx.send(embed=self.build_embed(
            "<:Kick:1513884038203703486> Member Kicked",
            f"**User:** {member.mention}\n"
            f"**<:right:1513879374741639248> Reason:** {reason}\n"
            f"**<:right:1513879374741639248> Moderator:** {ctx.author.mention}",
            thumbnail_url=member.display_avatar.url
        ))

    @commands.command()
    @commands.has_permissions(ban_members=True)
    async def ban(self, ctx: commands.Context, member: discord.Member, *,
                  reason: str = "No reason provided"):
        ok, msg = self.can_moderate(ctx, member)
        if not ok:
            return await ctx.send(embed=self.build_embed(
                "<:Warn:1513884025998020638> Action Blocked", msg))

        await member.ban(reason=reason, delete_message_seconds=0)
        await ctx.send(embed=self.build_embed(
            "<:Ban:1513884034088960172> Member Banned",
            f"**User:** {member.mention}\n"
            f"**<:right:1513879374741639248> Reason:** {reason}\n"
            f"**<:right:1513879374741639248> Moderator:** {ctx.author.mention}",
            thumbnail_url=member.display_avatar.url
        ))

    @commands.command()
    @commands.has_permissions(ban_members=True)
    async def softban(self, ctx: commands.Context, member: discord.Member, *,
                      reason: str = "No reason provided"):
        ok, msg = self.can_moderate(ctx, member)
        if not ok:
            return await ctx.send(embed=self.build_embed(
                "<:Warn:1513884025998020638> Action Blocked", msg))

        avatar = member.display_avatar.url
        name   = str(member)
        uid    = member.id

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

    @commands.command()
    @commands.has_permissions(ban_members=True)
    async def unban(self, ctx: commands.Context, user_id: int):
        try:
            user = await self.bot.fetch_user(user_id)
        except discord.NotFound:
            return await ctx.send(embed=self.build_embed(
                "<:cross:1514194117985570888> User Not Found",
                f"No user found with ID `{user_id}`."
            ))

        try:
            await ctx.guild.unban(user)
        except discord.NotFound:
            return await ctx.send(embed=self.build_embed(
                "<:cross:1514194117985570888> Not Banned",
                f"`{user}` is not banned in this server."
            ))

        await ctx.send(embed=self.build_embed(
            "<:tick:1514194122192191569> User Unbanned",
            f"**User:** {user.mention}\n"
            f"**<:right:1513879374741639248> ID:** `{user.id}`\n"
            f"**<:right:1513879374741639248> Moderator:** {ctx.author.mention}",
            thumbnail_url=user.display_avatar.url
        ))

    @commands.command(aliases=["timeout"])
    @commands.has_permissions(moderate_members=True)
    async def mute(self, ctx: commands.Context, member: discord.Member,
                   duration: str, *, reason: str = "No reason provided"):
        ok, msg = self.can_moderate(ctx, member)
        if not ok:
            return await ctx.send(embed=self.build_embed(
                "<:cross:1514194117985570888> Action Blocked", msg))

        try:
            td = parse_time(duration)
        except ValueError:
            return await ctx.send(embed=self.build_embed(
                "<:cross:1514194117985570888> Invalid Time",
                "Use formats like `30s`, `10m`, `2h`, `1d`."
            ))

        await member.timeout(td, reason=reason)
        await ctx.send(embed=self.build_embed(
            "<:tick:1514194122192191569> Member Timed Out",
            f"**User:** {member.mention}\n"
            f"**<:right:1513879374741639248> Duration:** {format_duration(td)}\n"
            f"**<:right:1513879374741639248> Reason:** {reason}\n"
            f"**<:right:1513879374741639248> Moderator:** {ctx.author.mention}",
            thumbnail_url=member.display_avatar.url
        ))

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

    @commands.command()
    @commands.has_permissions(manage_nicknames=True)
    async def nick(self, ctx: commands.Context, member: discord.Member, *,
                   nickname: Optional[str] = None):
        ok, msg = self.can_moderate(ctx, member)
        if not ok:
            return await ctx.send(embed=self.build_embed(
                "<:Warn:1513884025998020638> Action Blocked", msg))

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

    @commands.command()
    @commands.has_permissions(kick_members=True)
    async def warn(self, ctx: commands.Context, member: discord.Member, *,
                   reason: str = "No reason provided"):
        ok, msg = self.can_moderate(ctx, member)
        if not ok:
            return await ctx.send(embed=self.build_embed(
                "<:Warn:1513884025998020638> Action Blocked", msg))

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
                "⛔ Auto-Ban",
                f"{member.mention} has been banned for reaching **5 warnings**."
            ))

    @commands.command()
    async def warns(self, ctx: commands.Context, member: discord.Member):
        gid, uid  = str(ctx.guild.id), str(member.id)
        warn_list = self.warns.get(gid, {}).get(uid, [])

        if not warn_list:
            return await ctx.send(embed=self.build_embed(
                "📋 Warnings",
                f"{member.mention} has no warnings.",
                thumbnail_url=member.display_avatar.url
            ))

        text = "\n".join(f"`{i+1}.` {w}" for i, w in enumerate(warn_list))
        await ctx.send(embed=self.build_embed(
            f"📋 Warning History — {member.display_name}",
            text,
            thumbnail_url=member.display_avatar.url
        ))

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

    @commands.command()
    @commands.has_permissions(manage_channels=True)
    async def slowmode(self, ctx: commands.Context, seconds: int):
        if not 0 <= seconds <= 21600:
            return await ctx.send(embed=self.build_embed(
                "<:cross:1514194117985570888> Invalid Value",
                "Slowmode must be between `0` and `21600` seconds."
            ))

        await ctx.channel.edit(slowmode_delay=seconds)

        if seconds == 0:
            desc = f"Slowmode disabled in {ctx.channel.mention}."
        else:
            desc = (
                f"Slowmode set to **{seconds}s** in {ctx.channel.mention}.\n"
                f"**<:right:1513879374741639248> Moderator:** {ctx.author.mention}"
            )

        await ctx.send(embed=self.build_embed(
            "<:tick:1514194122192191569> Slowmode Updated", desc))

    @commands.command()
    @commands.has_permissions(manage_messages=True)
    async def purge(self, ctx: commands.Context, amount: int):
        if amount < 1:
            return await ctx.send(embed=self.build_embed(
                "<:Warn:1513884025998020638> Invalid Amount",
                "Amount must be greater than `0`."
            ))

        deleted = await ctx.channel.purge(limit=amount + 1)
        msg = await ctx.send(embed=self.build_embed(
            "<:cat:1513885435221508227> Purge Complete",
            f"Deleted **{len(deleted) - 1}** messages in {ctx.channel.mention}."
        ))
        await msg.delete(delay=3)

    @commands.command()
    @commands.has_permissions(manage_roles=True)
    async def roleadd(self, ctx: commands.Context, member: discord.Member, *,
                      role: discord.Role):
        if role >= ctx.guild.me.top_role:
            return await ctx.send(embed=self.build_embed(
                "<:cross:1514194117985570888> Permission Error",
                "I cannot assign a role equal to or higher than my own."
            ))
        if role in member.roles:
            return await ctx.send(embed=self.build_embed(
                "<:Warn:1513884025998020638> Already Assigned",
                f"{member.mention} already has the {role.mention} role."
            ))

        await member.add_roles(role, reason=f"Role added by {ctx.author}")
        await ctx.send(embed=self.build_embed(
            "<:tick:1514194122192191569> Role Added",
            f"**User:** {member.mention}\n"
            f"**<:right:1513879374741639248> Role:** {role.mention}\n"
            f"**<:right:1513879374741639248> Moderator:** {ctx.author.mention}",
            thumbnail_url=member.display_avatar.url
        ))

    @commands.command()
    @commands.has_permissions(manage_roles=True)
    async def roleremove(self, ctx: commands.Context, member: discord.Member, *,
                         role: discord.Role):
        if role >= ctx.guild.me.top_role:
            return await ctx.send(embed=self.build_embed(
                "<:cross:1514194117985570888> Permission Error",
                "I cannot remove a role equal to or higher than my own."
            ))
        if role not in member.roles:
            return await ctx.send(embed=self.build_embed(
                "<:Warn:1513884025998020638> Not Assigned",
                f"{member.mention} does not have the {role.mention} role."
            ))

        await member.remove_roles(role, reason=f"Role removed by {ctx.author}")
        await ctx.send(embed=self.build_embed(
            "<:tick:1514194122192191569> Role Removed",
            f"**User:** {member.mention}\n"
            f"**<:right:1513879374741639248> Role:** {role.mention}\n"
            f"**<:right:1513879374741639248> Moderator:** {ctx.author.mention}",
            thumbnail_url=member.display_avatar.url
        ))

    @commands.command()
    @commands.has_permissions(deafen_members=True)
    async def deafen(self, ctx: commands.Context, member: discord.Member, *,
                     reason: str = "No reason provided"):
        ok, msg = self.can_moderate(ctx, member)
        if not ok:
            return await ctx.send(embed=self.build_embed(
                "<:cross:1514194117985570888> Action Blocked", msg))

        if not member.voice:
            return await ctx.send(embed=self.build_embed(
                "<:Warn:1513884025998020638> Not in Voice",
                f"{member.mention} is not in a voice channel."
            ))

        await member.edit(deafen=True, reason=reason)
        await ctx.send(embed=self.build_embed(
            "<:tick:1514194122192191569> Member Deafened",
            f"**User:** {member.mention}\n"
            f"**<:right:1513879374741639248> Reason:** {reason}\n"
            f"**<:right:1513879374741639248> Moderator:** {ctx.author.mention}",
            thumbnail_url=member.display_avatar.url
        ))

    @commands.command()
    @commands.has_permissions(deafen_members=True)
    async def undeafen(self, ctx: commands.Context, member: discord.Member):
        if not member.voice:
            return await ctx.send(embed=self.build_embed(
                "<:Warn:1513884025998020638> Not in Voice",
                f"{member.mention} is not in a voice channel."
            ))

        await member.edit(deafen=False)
        await ctx.send(embed=self.build_embed(
            "<:tick:1514194122192191569> Member Undeafened",
            f"**User:** {member.mention}\n"
            f"**<:right:1513879374741639248> Status:** Can now hear audio.\n"
            f"**<:right:1513879374741639248> Moderator:** {ctx.author.mention}",
            thumbnail_url=member.display_avatar.url
        ))

    @commands.command()
    @commands.has_permissions(move_members=True)
    async def vcban(self, ctx: commands.Context, member: discord.Member, *,
                    reason: str = "No reason provided"):
        ok, msg = self.can_moderate(ctx, member)
        if not ok:
            return await ctx.send(embed=self.build_embed(
                "<:cross:1514194117985570888> Action Blocked", msg))

        if not member.voice:
            return await ctx.send(embed=self.build_embed(
                "<:Warn:1513884025998020638> Not in Voice",
                f"{member.mention} is not in a voice channel."
            ))

        await member.move_to(None, reason=reason)
        await ctx.send(embed=self.build_embed(
            "<:Kick:1513884038203703486> Disconnected from Voice",
            f"**User:** {member.mention}\n"
            f"**<:right:1513879374741639248> Reason:** {reason}\n"
            f"**<:right:1513879374741639248> Moderator:** {ctx.author.mention}",
            thumbnail_url=member.display_avatar.url
        ))

    @commands.command(aliases=["ui", "whois"])
    async def userinfo(self, ctx: commands.Context, member: Optional[discord.Member] = None):
        member = member or ctx.author

        joined    = discord.utils.format_dt(member.joined_at, "D") if member.joined_at else "Unknown"
        created   = discord.utils.format_dt(member.created_at, "D")
        roles     = [r.mention for r in reversed(member.roles) if r != ctx.guild.default_role]
        roles_str = " ".join(roles) if roles else "`None`"
        status    = str(member.status).title() if hasattr(member, "status") else "Unknown"

        embed = self.build_embed(
            f"👤 User Info — {member.display_name}",
            f"**User:** {member.mention}\n"
            f"**<:right:1513879374741639248> ID:** `{member.id}`\n"
            f"**<:right:1513879374741639248> Status:** {status}\n"
            f"**<:right:1513879374741639248> Account Created:** {created}\n"
            f"**<:right:1513879374741639248> Joined Server:** {joined}\n"
            f"**<:right:1513879374741639248> Roles [{len(roles)}]:** {roles_str}",
            thumbnail_url=member.display_avatar.url,
        )
        await ctx.send(embed=embed)

    @commands.command(aliases=["si"])
    async def serverinfo(self, ctx: commands.Context):
        guild   = ctx.guild
        created = discord.utils.format_dt(guild.created_at, "D")
        owner   = guild.owner.mention if guild.owner else "`Unknown`"

        embed = self.build_embed(
            f"🏠 Server Info — {guild.name}",
            f"**<:right:1513879374741639248> Owner:** {owner}\n"
            f"**<:right:1513879374741639248> Members:** {guild.member_count}\n"
            f"**<:right:1513879374741639248> Channels:** {len(guild.channels)}\n"
            f"**<:right:1513879374741639248> Roles:** {len(guild.roles)}\n"
            f"**<:right:1513879374741639248> Created:** {created}\n"
            f"**<:right:1513879374741639248> ID:** `{guild.id}`",
            thumbnail_url=guild.icon.url if guild.icon else None,
        )
        await ctx.send(embed=embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(Moderation(bot))

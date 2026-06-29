import discord
from discord.ext import commands
from discord import app_commands
from datetime import timedelta
from typing import Optional, Tuple
import json
import os
import re
import random
import asyncio

COLOUR    = 0xFFBFEA
WARN_FILE = "data/warnings.json"
INV_FILE  = "data/invites.json"

RESTRICT     = "<:restrict:1519939088998989824>"
ARROW        = "<:rightarrow:1515660270557466685>"
STAR         = "<:pastelstar:1517787024306733206>"
TICK         = "<:tick:1514194122192191569>"
CROSS        = "<:cross:1514194117985570888>"
WARN         = "<:warnicon:1515660263129350155>"
LEAF         = "<:leaf:1515660279944319006>"

FOOTERS = [
    "crafted with love by yuvraj • Shouffle",
    "join our support server for any issues!",
    "thanks for using Shouffle ✨",
    "powered by Shouffle Developments",
    "Shouffle • keeping servers in order",
    "need help? join the Shouffle support server!",
    "made by yuvraj • Shouffle Developments",
    "Shouffle • your server's best friend",
]


def random_footer() -> str:
    return random.choice(FOOTERS)


def load_json(path: str) -> dict:
    if not os.path.exists(path):
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def save_json(path: str, data: dict) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
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


TEMPVC_DATA_FILE = "data/tempvc_data.json"


def tvc_load_data() -> dict:
    if os.path.exists(TEMPVC_DATA_FILE):
        with open(TEMPVC_DATA_FILE, "r") as f:
            return json.load(f)
    return {}


def tvc_save_data(data: dict):
    os.makedirs(os.path.dirname(TEMPVC_DATA_FILE), exist_ok=True)
    with open(TEMPVC_DATA_FILE, "w") as f:
        json.dump(data, f, indent=2)


def get_guild_config(guild_id: int) -> dict | None:
    return tvc_load_data().get(str(guild_id))


def set_guild_config(guild_id: int, config: dict):
    data = tvc_load_data()
    data[str(guild_id)] = config
    tvc_save_data(data)


def get_temp_channels(guild_id: int) -> dict:
    data = tvc_load_data()
    return data.get(f"temp_{guild_id}", {})


def set_temp_channels(guild_id: int, channels: dict):
    data = tvc_load_data()
    data[f"temp_{guild_id}"] = channels
    tvc_save_data(data)


DEFAULT_PANEL_IMAGE = "https://i.ibb.co/dsr5DvVf/file-00000000939c7207ad49279b063c85f6.png"


class VCControlPanel(discord.ui.View):

    def __init__(self):
        super().__init__(timeout=None)

    async def _get_owner_vc(self, interaction: discord.Interaction) -> discord.VoiceChannel | None:
        temp = get_temp_channels(interaction.guild_id)
        for ch_id, owner_id in temp.items():
            if owner_id == interaction.user.id:
                ch = interaction.guild.get_channel(int(ch_id))
                if ch:
                    return ch
        await interaction.response.send_message(
            "❌ You don't own a temporary voice channel right now.",
            ephemeral=True
        )
        return None

    @discord.ui.button(label="🔒 Lock", style=discord.ButtonStyle.danger,
                       custom_id="tvc:lock", row=0)
    async def lock(self, interaction: discord.Interaction, button: discord.ui.Button):
        vc = await self._get_owner_vc(interaction)
        if not vc:
            return
        overwrite = vc.overwrites_for(interaction.guild.default_role)
        overwrite.connect = False
        await vc.set_permissions(interaction.guild.default_role, overwrite=overwrite)
        await interaction.response.send_message("🔒 Channel **locked**.", ephemeral=True)

    @discord.ui.button(label="🔓 Unlock", style=discord.ButtonStyle.success,
                       custom_id="tvc:unlock", row=0)
    async def unlock(self, interaction: discord.Interaction, button: discord.ui.Button):
        vc = await self._get_owner_vc(interaction)
        if not vc:
            return
        overwrite = vc.overwrites_for(interaction.guild.default_role)
        overwrite.connect = True
        await vc.set_permissions(interaction.guild.default_role, overwrite=overwrite)
        await interaction.response.send_message("🔓 Channel **unlocked**.", ephemeral=True)

    @discord.ui.button(label="👻 Hide", style=discord.ButtonStyle.secondary,
                       custom_id="tvc:hide", row=0)
    async def hide(self, interaction: discord.Interaction, button: discord.ui.Button):
        vc = await self._get_owner_vc(interaction)
        if not vc:
            return
        overwrite = vc.overwrites_for(interaction.guild.default_role)
        overwrite.view_channel = False
        await vc.set_permissions(interaction.guild.default_role, overwrite=overwrite)
        await interaction.response.send_message("👻 Channel **hidden**.", ephemeral=True)

    @discord.ui.button(label="👁️ Reveal", style=discord.ButtonStyle.secondary,
                       custom_id="tvc:reveal", row=0)
    async def reveal(self, interaction: discord.Interaction, button: discord.ui.Button):
        vc = await self._get_owner_vc(interaction)
        if not vc:
            return
        overwrite = vc.overwrites_for(interaction.guild.default_role)
        overwrite.view_channel = True
        await vc.set_permissions(interaction.guild.default_role, overwrite=overwrite)
        await interaction.response.send_message("👁️ Channel **visible** to everyone.", ephemeral=True)

    @discord.ui.button(label="✏️ Rename", style=discord.ButtonStyle.primary,
                       custom_id="tvc:rename", row=1)
    async def rename(self, interaction: discord.Interaction, button: discord.ui.Button):
        vc = await self._get_owner_vc(interaction)
        if not vc:
            return
        modal = RenameModal(vc)
        await interaction.response.send_modal(modal)

    @discord.ui.button(label="👥 User Limit", style=discord.ButtonStyle.primary,
                       custom_id="tvc:limit", row=1)
    async def user_limit(self, interaction: discord.Interaction, button: discord.ui.Button):
        vc = await self._get_owner_vc(interaction)
        if not vc:
            return
        modal = LimitModal(vc)
        await interaction.response.send_modal(modal)

    @discord.ui.button(label="✅ Permit", style=discord.ButtonStyle.success,
                       custom_id="tvc:permit", row=1)
    async def permit(self, interaction: discord.Interaction, button: discord.ui.Button):
        vc = await self._get_owner_vc(interaction)
        if not vc:
            return
        modal = PermitModal(vc, allow=True)
        await interaction.response.send_modal(modal)

    @discord.ui.button(label="⛔ Reject", style=discord.ButtonStyle.danger,
                       custom_id="tvc:reject", row=1)
    async def reject(self, interaction: discord.Interaction, button: discord.ui.Button):
        vc = await self._get_owner_vc(interaction)
        if not vc:
            return
        modal = PermitModal(vc, allow=False)
        await interaction.response.send_modal(modal)

    @discord.ui.button(label="👑 Transfer", style=discord.ButtonStyle.primary,
                       custom_id="tvc:transfer", row=2)
    async def transfer(self, interaction: discord.Interaction, button: discord.ui.Button):
        vc = await self._get_owner_vc(interaction)
        if not vc:
            return
        modal = TransferModal(vc, interaction.guild_id)
        await interaction.response.send_modal(modal)

    @discord.ui.button(label="🔇 Mute All", style=discord.ButtonStyle.danger,
                       custom_id="tvc:muteall", row=2)
    async def mute_all(self, interaction: discord.Interaction, button: discord.ui.Button):
        vc = await self._get_owner_vc(interaction)
        if not vc:
            return
        count = 0
        for member in vc.members:
            if member != interaction.user and not member.bot:
                try:
                    await member.edit(mute=True)
                    count += 1
                except Exception:
                    pass
        await interaction.response.send_message(
            f"🔇 Muted **{count}** member(s).", ephemeral=True
        )

    @discord.ui.button(label="🔊 Unmute All", style=discord.ButtonStyle.success,
                       custom_id="tvc:unmuteall", row=2)
    async def unmute_all(self, interaction: discord.Interaction, button: discord.ui.Button):
        vc = await self._get_owner_vc(interaction)
        if not vc:
            return
        count = 0
        for member in vc.members:
            if not member.bot:
                try:
                    await member.edit(mute=False)
                    count += 1
                except Exception:
                    pass
        await interaction.response.send_message(
            f"🔊 Unmuted **{count}** member(s).", ephemeral=True
        )

    @discord.ui.button(label="🗑️ Delete", style=discord.ButtonStyle.danger,
                       custom_id="tvc:delete", row=2)
    async def delete_vc(self, interaction: discord.Interaction, button: discord.ui.Button):
        vc = await self._get_owner_vc(interaction)
        if not vc:
            return
        temp = get_temp_channels(interaction.guild_id)
        temp.pop(str(vc.id), None)
        set_temp_channels(interaction.guild_id, temp)
        await vc.delete(reason="Owner deleted via control panel.")
        await interaction.response.send_message("🗑️ Your channel has been deleted.", ephemeral=True)


class RenameModal(discord.ui.Modal, title="✏️ Rename Your Voice Channel"):
    name = discord.ui.TextInput(label="New Channel Name", max_length=100,
                                placeholder="e.g. 🎮 Gaming Lounge")

    def __init__(self, vc: discord.VoiceChannel):
        super().__init__()
        self.vc = vc

    async def on_submit(self, interaction: discord.Interaction):
        await self.vc.edit(name=self.name.value)
        await interaction.response.send_message(
            f"✏️ Channel renamed to **{self.name.value}**.", ephemeral=True
        )


class LimitModal(discord.ui.Modal, title="👥 Set User Limit"):
    limit = discord.ui.TextInput(label="User Limit (0 = unlimited)", max_length=2,
                                 placeholder="e.g. 5")

    def __init__(self, vc: discord.VoiceChannel):
        super().__init__()
        self.vc = vc

    async def on_submit(self, interaction: discord.Interaction):
        try:
            val = int(self.limit.value)
            if not 0 <= val <= 99:
                raise ValueError
        except ValueError:
            return await interaction.response.send_message(
                "❌ Enter a number between 0 and 99.", ephemeral=True
            )
        await self.vc.edit(user_limit=val)
        label = f"**{val}**" if val else "**unlimited**"
        await interaction.response.send_message(f"👥 User limit set to {label}.", ephemeral=True)


class PermitModal(discord.ui.Modal):
    user_input = discord.ui.TextInput(label="Username or User ID",
                                      placeholder="e.g. CoolUser#1234 or 123456789")

    def __init__(self, vc: discord.VoiceChannel, allow: bool):
        title = "✅ Permit a User" if allow else "⛔ Reject a User"
        super().__init__(title=title)
        self.vc = vc
        self.allow = allow

    async def on_submit(self, interaction: discord.Interaction):
        raw = self.user_input.value.strip()
        member = None
        if raw.isdigit():
            member = interaction.guild.get_member(int(raw))
        if not member:
            member = discord.utils.find(
                lambda m: str(m) == raw or m.name == raw or m.display_name == raw,
                interaction.guild.members
            )
        if not member:
            return await interaction.response.send_message("❌ User not found.", ephemeral=True)

        overwrite = self.vc.overwrites_for(member)
        if self.allow:
            overwrite.connect = True
            overwrite.view_channel = True
            action = f"✅ **{member.display_name}** can now join your channel."
        else:
            overwrite.connect = False
            action = f"⛔ **{member.display_name}** is now rejected from your channel."
            if member in self.vc.members:
                try:
                    await member.move_to(None)
                except Exception:
                    pass

        await self.vc.set_permissions(member, overwrite=overwrite)
        await interaction.response.send_message(action, ephemeral=True)


class TransferModal(discord.ui.Modal, title="👑 Transfer Ownership"):
    user_input = discord.ui.TextInput(label="New Owner (Username or User ID)",
                                      placeholder="e.g. CoolUser#1234 or 123456789")

    def __init__(self, vc: discord.VoiceChannel, guild_id: int):
        super().__init__()
        self.vc = vc
        self.guild_id = guild_id

    async def on_submit(self, interaction: discord.Interaction):
        raw = self.user_input.value.strip()
        member = None
        if raw.isdigit():
            member = interaction.guild.get_member(int(raw))
        if not member:
            member = discord.utils.find(
                lambda m: str(m) == raw or m.name == raw or m.display_name == raw,
                interaction.guild.members
            )
        if not member:
            return await interaction.response.send_message("❌ User not found.", ephemeral=True)
        if member.bot:
            return await interaction.response.send_message("❌ Cannot transfer to a bot.", ephemeral=True)

        temp = get_temp_channels(self.guild_id)
        temp[str(self.vc.id)] = member.id
        set_temp_channels(self.guild_id, temp)
        await interaction.response.send_message(
            f"👑 Ownership of **{self.vc.name}** transferred to **{member.display_name}**.",
            ephemeral=True
        )


class SetupModal(discord.ui.Modal, title="🎙️ Temporary VC Setup"):
    category_name = discord.ui.TextInput(
        label="Category Name",
        placeholder="e.g. 🔊 Voice Channels",
        default="🔊 Voice Channels",
        max_length=100
    )

    def __init__(self, cog):
        super().__init__()
        self.cog = cog

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        guild = interaction.guild

        cat_name = self.category_name.value.strip()
        category = discord.utils.get(guild.categories, name=cat_name)
        if not category:
            category = await guild.create_category(cat_name)

        chat_ch = discord.utils.get(guild.text_channels, name="audio-interface")
        if not chat_ch:
            chat_ch = await guild.create_text_channel(
                "audio-interface",
                category=category,
                topic="🎛️ Control your temporary voice channel here."
            )

        create_vc = discord.utils.get(guild.voice_channels, name="➕ Create VC")
        if not create_vc:
            create_vc = await guild.create_voice_channel(
                "➕ Create VC",
                category=category
            )

        set_guild_config(guild.id, {
            "category_id": category.id,
            "chat_channel_id": chat_ch.id,
            "create_vc_id": create_vc.id,
        })

        await self.cog.post_panel(chat_ch)

        await interaction.followup.send(
            f"✅ **Temporary VC system is live!**\n"
            f"📁 Category → `{category.name}`\n"
            f"💬 Control Panel → {chat_ch.mention}\n"
            f"🔊 Join-to-create → {create_vc.mention}",
            ephemeral=True
        )


class Moderation(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot     = bot
        self.warns   = load_json(WARN_FILE)
        self.invites = load_json(INV_FILE)

    def build_embed(self, title: str, description: str,
                    thumbnail_url: Optional[str] = None) -> discord.Embed:
        e = discord.Embed(title=title, description=description, color=COLOUR)
        if thumbnail_url:
            e.set_thumbnail(url=thumbnail_url)
        footer_text = random_footer()
        if self.bot.user:
            e.set_footer(
                text=footer_text,
                icon_url=self.bot.user.display_avatar.url
            )
        else:
            e.set_footer(text=footer_text)
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

    @commands.command()
    @commands.has_permissions(kick_members=True)
    async def kick(self, ctx: commands.Context, member: discord.Member, *,
                   reason: str = "No reason provided"):
        ok, msg = self.can_moderate(ctx.author, member, ctx.guild)
        if not ok:
            return await ctx.send(embed=self.build_embed(f"{CROSS} Action Blocked", msg))
        await member.kick(reason=reason)
        await ctx.send(embed=self.build_embed(
            f"{RESTRICT} Member Kicked",
            f"**User:** {member.mention}\n"
            f"**{ARROW} Reason:** {reason}\n"
            f"**{ARROW} Moderator:** {ctx.author.mention}",
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
                embed=self.build_embed(f"{CROSS} Action Blocked", msg), ephemeral=True)
        await member.kick(reason=reason)
        await interaction.response.send_message(embed=self.build_embed(
            f"{RESTRICT} Member Kicked",
            f"**User:** {member.mention}\n"
            f"**{ARROW} Reason:** {reason}\n"
            f"**{ARROW} Moderator:** {interaction.user.mention}",
            thumbnail_url=member.display_avatar.url
        ))

    @commands.command()
    @commands.has_permissions(ban_members=True)
    async def ban(self, ctx: commands.Context, member: discord.Member, *,
                  reason: str = "No reason provided"):
        ok, msg = self.can_moderate(ctx.author, member, ctx.guild)
        if not ok:
            return await ctx.send(embed=self.build_embed(f"{WARN} Action Blocked", msg))
        await member.ban(reason=reason, delete_message_seconds=0)
        await ctx.send(embed=self.build_embed(
            f"{RESTRICT} Member Banned",
            f"**User:** {member.mention}\n"
            f"**{ARROW} Reason:** {reason}\n"
            f"**{ARROW} Moderator:** {ctx.author.mention}",
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
                embed=self.build_embed(f"{WARN} Action Blocked", msg), ephemeral=True)
        await member.ban(reason=reason, delete_message_seconds=0)
        await interaction.response.send_message(embed=self.build_embed(
            f"{RESTRICT} Member Banned",
            f"**User:** {member.mention}\n"
            f"**{ARROW} Reason:** {reason}\n"
            f"**{ARROW} Moderator:** {interaction.user.mention}",
            thumbnail_url=member.display_avatar.url
        ))

    @commands.command()
    @commands.has_permissions(ban_members=True)
    async def softban(self, ctx: commands.Context, member: discord.Member, *,
                      reason: str = "No reason provided"):
        ok, msg = self.can_moderate(ctx.author, member, ctx.guild)
        if not ok:
            return await ctx.send(embed=self.build_embed(f"{WARN} Action Blocked", msg))
        avatar, name, uid = member.display_avatar.url, str(member), member.id
        await member.ban(reason=f"Softban: {reason}", delete_message_seconds=604800)
        await ctx.guild.unban(discord.Object(id=uid), reason="Softban unban")
        await ctx.send(embed=self.build_embed(
            f"{RESTRICT} Member Soft-Banned",
            f"**User:** {name} (`{uid}`)\n"
            f"**{ARROW} Reason:** {reason}\n"
            f"**{ARROW} Moderator:** {ctx.author.mention}\n"
            f"**{ARROW} Note:** Messages deleted, member may rejoin.",
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
                embed=self.build_embed(f"{WARN} Action Blocked", msg), ephemeral=True)
        avatar, name, uid = member.display_avatar.url, str(member), member.id
        await member.ban(reason=f"Softban: {reason}", delete_message_seconds=604800)
        await interaction.guild.unban(discord.Object(id=uid), reason="Softban unban")
        await interaction.response.send_message(embed=self.build_embed(
            f"{RESTRICT} Member Soft-Banned",
            f"**User:** {name} (`{uid}`)\n"
            f"**{ARROW} Reason:** {reason}\n"
            f"**{ARROW} Moderator:** {interaction.user.mention}\n"
            f"**{ARROW} Note:** Messages deleted, member may rejoin.",
            thumbnail_url=avatar
        ))

    @commands.command()
    @commands.has_permissions(ban_members=True)
    async def unban(self, ctx: commands.Context, user_id: int):
        try:
            user = await self.bot.fetch_user(user_id)
        except discord.NotFound:
            return await ctx.send(embed=self.build_embed(
                f"{CROSS} User Not Found", f"No user found with ID `{user_id}`."))
        try:
            await ctx.guild.unban(user)
        except discord.NotFound:
            return await ctx.send(embed=self.build_embed(
                f"{CROSS} Not Banned", f"`{user}` is not banned in this server."))
        await ctx.send(embed=self.build_embed(
            f"{TICK} User Unbanned",
            f"**User:** {user.mention}\n"
            f"**{ARROW} ID:** `{user.id}`\n"
            f"**{ARROW} Moderator:** {ctx.author.mention}",
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
                embed=self.build_embed(f"{CROSS} User Not Found",
                                       f"No user found with ID `{user_id}`."), ephemeral=True)
        try:
            await interaction.guild.unban(user)
        except discord.NotFound:
            return await interaction.response.send_message(
                embed=self.build_embed(f"{CROSS} Not Banned",
                                       f"`{user}` is not banned in this server."), ephemeral=True)
        await interaction.response.send_message(embed=self.build_embed(
            f"{TICK} User Unbanned",
            f"**User:** {user.mention}\n"
            f"**{ARROW} ID:** `{user.id}`\n"
            f"**{ARROW} Moderator:** {interaction.user.mention}",
            thumbnail_url=user.display_avatar.url
        ))

    @commands.command(aliases=["timeout"])
    @commands.has_permissions(moderate_members=True)
    async def mute(self, ctx: commands.Context, member: discord.Member,
                   duration: str, *, reason: str = "No reason provided"):
        ok, msg = self.can_moderate(ctx.author, member, ctx.guild)
        if not ok:
            return await ctx.send(embed=self.build_embed(f"{CROSS} Action Blocked", msg))
        try:
            td = parse_time(duration)
        except ValueError:
            return await ctx.send(embed=self.build_embed(
                f"{CROSS} Invalid Time", "Use formats like `30s`, `10m`, `2h`, `1d`."))
        await member.timeout(td, reason=reason)
        await ctx.send(embed=self.build_embed(
            f"{WARN} Member Timed Out",
            f"**User:** {member.mention}\n"
            f"**{ARROW} Duration:** {format_duration(td)}\n"
            f"**{ARROW} Reason:** {reason}\n"
            f"**{ARROW} Moderator:** {ctx.author.mention}",
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
                embed=self.build_embed(f"{CROSS} Action Blocked", msg), ephemeral=True)
        try:
            td = parse_time(duration)
        except ValueError:
            return await interaction.response.send_message(
                embed=self.build_embed(f"{CROSS} Invalid Time",
                                       "Use formats like `30s`, `10m`, `2h`, `1d`."), ephemeral=True)
        await member.timeout(td, reason=reason)
        await interaction.response.send_message(embed=self.build_embed(
            f"{WARN} Member Timed Out",
            f"**User:** {member.mention}\n"
            f"**{ARROW} Duration:** {format_duration(td)}\n"
            f"**{ARROW} Reason:** {reason}\n"
            f"**{ARROW} Moderator:** {interaction.user.mention}",
            thumbnail_url=member.display_avatar.url
        ))

    @commands.command(aliases=["untimeout"])
    @commands.has_permissions(moderate_members=True)
    async def unmute(self, ctx: commands.Context, member: discord.Member):
        await member.timeout(None)
        await ctx.send(embed=self.build_embed(
            f"{TICK} Member Unmuted",
            f"**User:** {member.mention}\n"
            f"**{ARROW} Status:** Timeout removed — can speak again.\n"
            f"**{ARROW} Moderator:** {ctx.author.mention}",
            thumbnail_url=member.display_avatar.url
        ))

    @app_commands.command(name="unmute", description="Remove timeout from a member")
    @app_commands.describe(member="Member to unmute")
    @app_commands.default_permissions(moderate_members=True)
    async def unmute_slash(self, interaction: discord.Interaction, member: discord.Member):
        await member.timeout(None)
        await interaction.response.send_message(embed=self.build_embed(
            f"{TICK} Member Unmuted",
            f"**User:** {member.mention}\n"
            f"**{ARROW} Status:** Timeout removed — can speak again.\n"
            f"**{ARROW} Moderator:** {interaction.user.mention}",
            thumbnail_url=member.display_avatar.url
        ))

    @commands.command()
    @commands.has_permissions(manage_nicknames=True)
    async def nick(self, ctx: commands.Context, member: discord.Member, *,
                   nickname: Optional[str] = None):
        ok, msg = self.can_moderate(ctx.author, member, ctx.guild)
        if not ok:
            return await ctx.send(embed=self.build_embed(f"{WARN} Action Blocked", msg))
        old_name = member.display_name
        await member.edit(nick=nickname)
        await ctx.send(embed=self.build_embed(
            f"{TICK} Nickname Updated",
            f"**User:** {member.mention}\n"
            f"**{ARROW} Old:** `{old_name}`\n"
            f"**{ARROW} New:** `{nickname or 'Reset'}`\n"
            f"**{ARROW} Moderator:** {ctx.author.mention}",
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
                embed=self.build_embed(f"{WARN} Action Blocked", msg), ephemeral=True)
        old_name = member.display_name
        await member.edit(nick=nickname)
        await interaction.response.send_message(embed=self.build_embed(
            f"{TICK} Nickname Updated",
            f"**User:** {member.mention}\n"
            f"**{ARROW} Old:** `{old_name}`\n"
            f"**{ARROW} New:** `{nickname or 'Reset'}`\n"
            f"**{ARROW} Moderator:** {interaction.user.mention}",
            thumbnail_url=member.display_avatar.url
        ))

    @commands.command()
    @commands.has_permissions(kick_members=True)
    async def warn(self, ctx: commands.Context, member: discord.Member, *,
                   reason: str = "No reason provided"):
        ok, msg = self.can_moderate(ctx.author, member, ctx.guild)
        if not ok:
            return await ctx.send(embed=self.build_embed(f"{WARN} Action Blocked", msg))
        gid, uid = str(ctx.guild.id), str(member.id)
        self.warns.setdefault(gid, {}).setdefault(uid, [])
        self.warns[gid][uid].append(reason)
        save_json(WARN_FILE, self.warns)
        count = len(self.warns[gid][uid])
        await ctx.send(embed=self.build_embed(
            f"{WARN} Warning Issued",
            f"**User:** {member.mention}\n"
            f"**{ARROW} Reason:** {reason}\n"
            f"**{ARROW} Warnings:** {count}/5\n"
            f"**{ARROW} Moderator:** {ctx.author.mention}",
            thumbnail_url=member.display_avatar.url
        ))
        if count >= 5:
            await member.ban(reason="Auto-ban: reached 5 warnings")
            self.warns[gid][uid] = []
            save_json(WARN_FILE, self.warns)
            await ctx.send(embed=self.build_embed(
                f"{RESTRICT} Auto-Ban",
                f"{member.mention} has been banned for reaching **5 warnings**."))

    @app_commands.command(name="warn", description="Warn a member")
    @app_commands.describe(member="Member to warn", reason="Reason for warning")
    @app_commands.default_permissions(kick_members=True)
    async def warn_slash(self, interaction: discord.Interaction, member: discord.Member,
                         reason: str = "No reason provided"):
        ok, msg = self.can_moderate(interaction.user, member, interaction.guild)
        if not ok:
            return await interaction.response.send_message(
                embed=self.build_embed(f"{WARN} Action Blocked", msg), ephemeral=True)
        gid, uid = str(interaction.guild.id), str(member.id)
        self.warns.setdefault(gid, {}).setdefault(uid, [])
        self.warns[gid][uid].append(reason)
        save_json(WARN_FILE, self.warns)
        count = len(self.warns[gid][uid])
        await interaction.response.send_message(embed=self.build_embed(
            f"{WARN} Warning Issued",
            f"**User:** {member.mention}\n"
            f"**{ARROW} Reason:** {reason}\n"
            f"**{ARROW} Warnings:** {count}/5\n"
            f"**{ARROW} Moderator:** {interaction.user.mention}",
            thumbnail_url=member.display_avatar.url
        ))
        if count >= 5:
            await member.ban(reason="Auto-ban: reached 5 warnings")
            self.warns[gid][uid] = []
            save_json(WARN_FILE, self.warns)
            await interaction.followup.send(embed=self.build_embed(
                f"{RESTRICT} Auto-Ban",
                f"{member.mention} has been banned for reaching **5 warnings**."))

    @commands.command()
    async def warns(self, ctx: commands.Context, member: discord.Member):
        gid, uid  = str(ctx.guild.id), str(member.id)
        warn_list = self.warns.get(gid, {}).get(uid, [])
        if not warn_list:
            return await ctx.send(embed=self.build_embed(
                f"{LEAF} Warnings",
                f"{member.mention} has no warnings. Clean record {TICK}",
                thumbnail_url=member.display_avatar.url))
        text = "\n".join(f"`{i+1}.` {w}" for i, w in enumerate(warn_list))
        await ctx.send(embed=self.build_embed(
            f"{WARN} Warning History — {member.display_name}", text,
            thumbnail_url=member.display_avatar.url))

    @app_commands.command(name="warns", description="View warnings of a member")
    @app_commands.describe(member="Member to check")
    async def warns_slash(self, interaction: discord.Interaction, member: discord.Member):
        gid, uid  = str(interaction.guild.id), str(member.id)
        warn_list = self.warns.get(gid, {}).get(uid, [])
        if not warn_list:
            return await interaction.response.send_message(embed=self.build_embed(
                f"{LEAF} Warnings",
                f"{member.mention} has no warnings. Clean record {TICK}",
                thumbnail_url=member.display_avatar.url))
        text = "\n".join(f"`{i+1}.` {w}" for i, w in enumerate(warn_list))
        await interaction.response.send_message(embed=self.build_embed(
            f"{WARN} Warning History — {member.display_name}", text,
            thumbnail_url=member.display_avatar.url))

    @commands.command()
    @commands.has_permissions(kick_members=True)
    async def clearwarns(self, ctx: commands.Context, member: discord.Member):
        gid, uid = str(ctx.guild.id), str(member.id)
        self.warns.setdefault(gid, {})[uid] = []
        save_json(WARN_FILE, self.warns)
        await ctx.send(embed=self.build_embed(
            f"{TICK} Warnings Cleared",
            f"All warnings for {member.mention} have been removed.\n"
            f"**{ARROW} Moderator:** {ctx.author.mention}",
            thumbnail_url=member.display_avatar.url
        ))

    @app_commands.command(name="clearwarns", description="Clear all warnings of a member")
    @app_commands.describe(member="Member whose warnings to clear")
    @app_commands.default_permissions(kick_members=True)
    async def clearwarns_slash(self, interaction: discord.Interaction, member: discord.Member):
        gid, uid = str(interaction.guild.id), str(member.id)
        self.warns.setdefault(gid, {})[uid] = []
        save_json(WARN_FILE, self.warns)
        await interaction.response.send_message(embed=self.build_embed(
            f"{TICK} Warnings Cleared",
            f"All warnings for {member.mention} have been removed.\n"
            f"**{ARROW} Moderator:** {interaction.user.mention}",
            thumbnail_url=member.display_avatar.url
        ))

    @commands.command()
    @commands.has_permissions(manage_channels=True)
    async def lock(self, ctx: commands.Context):
        overwrite = ctx.channel.overwrites_for(ctx.guild.default_role)
        overwrite.send_messages = False
        await ctx.channel.set_permissions(ctx.guild.default_role, overwrite=overwrite)
        await ctx.send(embed=self.build_embed(
            f"{RESTRICT} Channel Locked",
            f"**{ARROW}** {ctx.channel.mention} has been **locked**.\n"
            f"**{ARROW} Moderator:** {ctx.author.mention}"
        ))

    @app_commands.command(name="lock", description="Lock the current channel")
    @app_commands.default_permissions(manage_channels=True)
    async def lock_slash(self, interaction: discord.Interaction):
        channel = interaction.channel
        overwrite = channel.overwrites_for(interaction.guild.default_role)
        overwrite.send_messages = False
        await channel.set_permissions(interaction.guild.default_role, overwrite=overwrite)
        await interaction.response.send_message(embed=self.build_embed(
            f"{RESTRICT} Channel Locked",
            f"**{ARROW}** {channel.mention} has been **locked**.\n"
            f"**{ARROW} Moderator:** {interaction.user.mention}"
        ))

    @commands.command()
    @commands.has_permissions(manage_channels=True)
    async def unlock(self, ctx: commands.Context):
        overwrite = ctx.channel.overwrites_for(ctx.guild.default_role)
        overwrite.send_messages = None
        await ctx.channel.set_permissions(ctx.guild.default_role, overwrite=overwrite)
        await ctx.send(embed=self.build_embed(
            f"{TICK} Channel Unlocked",
            f"**{ARROW}** {ctx.channel.mention} has been **unlocked**.\n"
            f"**{ARROW} Moderator:** {ctx.author.mention}"
        ))

    @app_commands.command(name="unlock", description="Unlock the current channel")
    @app_commands.default_permissions(manage_channels=True)
    async def unlock_slash(self, interaction: discord.Interaction):
        channel = interaction.channel
        overwrite = channel.overwrites_for(interaction.guild.default_role)
        overwrite.send_messages = None
        await channel.set_permissions(interaction.guild.default_role, overwrite=overwrite)
        await interaction.response.send_message(embed=self.build_embed(
            f"{TICK} Channel Unlocked",
            f"**{ARROW}** {channel.mention} has been **unlocked**.\n"
            f"**{ARROW} Moderator:** {interaction.user.mention}"
        ))

    @commands.command()
    @commands.has_permissions(manage_channels=True)
    async def hide(self, ctx: commands.Context, channel: Optional[discord.TextChannel] = None):
        channel = channel or ctx.channel
        overwrite = channel.overwrites_for(ctx.guild.default_role)
        overwrite.view_channel = False
        await channel.set_permissions(ctx.guild.default_role, overwrite=overwrite)
        await ctx.send(embed=self.build_embed(
            f"{RESTRICT} Channel Hidden",
            f"**{ARROW}** {channel.mention} is now **hidden** from everyone.\n"
            f"**{ARROW} Moderator:** {ctx.author.mention}"
        ))

    @app_commands.command(name="hide", description="Hide a channel from everyone")
    @app_commands.describe(channel="Channel to hide (defaults to current)")
    @app_commands.default_permissions(manage_channels=True)
    async def hide_slash(self, interaction: discord.Interaction,
                         channel: Optional[discord.TextChannel] = None):
        channel = channel or interaction.channel
        overwrite = channel.overwrites_for(interaction.guild.default_role)
        overwrite.view_channel = False
        await channel.set_permissions(interaction.guild.default_role, overwrite=overwrite)
        await interaction.response.send_message(embed=self.build_embed(
            f"{RESTRICT} Channel Hidden",
            f"**{ARROW}** {channel.mention} is now **hidden** from everyone.\n"
            f"**{ARROW} Moderator:** {interaction.user.mention}"
        ))

    @commands.command()
    @commands.has_permissions(manage_channels=True)
    async def unhide(self, ctx: commands.Context, channel: Optional[discord.TextChannel] = None):
        channel = channel or ctx.channel
        overwrite = channel.overwrites_for(ctx.guild.default_role)
        overwrite.view_channel = None
        await channel.set_permissions(ctx.guild.default_role, overwrite=overwrite)
        await ctx.send(embed=self.build_embed(
            f"{TICK} Channel Visible",
            f"**{ARROW}** {channel.mention} is now **visible** to everyone.\n"
            f"**{ARROW} Moderator:** {ctx.author.mention}"
        ))

    @app_commands.command(name="unhide", description="Make a hidden channel visible again")
    @app_commands.describe(channel="Channel to unhide (defaults to current)")
    @app_commands.default_permissions(manage_channels=True)
    async def unhide_slash(self, interaction: discord.Interaction,
                           channel: Optional[discord.TextChannel] = None):
        channel = channel or interaction.channel
        overwrite = channel.overwrites_for(interaction.guild.default_role)
        overwrite.view_channel = None
        await channel.set_permissions(interaction.guild.default_role, overwrite=overwrite)
        await interaction.response.send_message(embed=self.build_embed(
            f"{TICK} Channel Visible",
            f"**{ARROW}** {channel.mention} is now **visible** to everyone.\n"
            f"**{ARROW} Moderator:** {interaction.user.mention}"
        ))

    @commands.command()
    @commands.has_permissions(manage_channels=True)
    async def slowmode(self, ctx: commands.Context, seconds: int):
        if not 0 <= seconds <= 21600:
            return await ctx.send(embed=self.build_embed(
                f"{CROSS} Invalid Value",
                "Slowmode must be between `0` and `21600` seconds."))
        await ctx.channel.edit(slowmode_delay=seconds)
        desc = (f"Slowmode disabled in {ctx.channel.mention}." if seconds == 0 else
                f"Slowmode set to **{seconds}s** in {ctx.channel.mention}.\n"
                f"**{ARROW} Moderator:** {ctx.author.mention}")
        await ctx.send(embed=self.build_embed(f"{TICK} Slowmode Updated", desc))

    @app_commands.command(name="slowmode", description="Set slowmode for the current channel")
    @app_commands.describe(seconds="Slowmode delay in seconds (0 to disable, max 21600)")
    @app_commands.default_permissions(manage_channels=True)
    async def slowmode_slash(self, interaction: discord.Interaction, seconds: int):
        if not 0 <= seconds <= 21600:
            return await interaction.response.send_message(
                embed=self.build_embed(f"{CROSS} Invalid Value",
                                       "Slowmode must be between `0` and `21600` seconds."), ephemeral=True)
        await interaction.channel.edit(slowmode_delay=seconds)
        desc = (f"Slowmode disabled in {interaction.channel.mention}." if seconds == 0 else
                f"Slowmode set to **{seconds}s** in {interaction.channel.mention}.\n"
                f"**{ARROW} Moderator:** {interaction.user.mention}")
        await interaction.response.send_message(
            embed=self.build_embed(f"{TICK} Slowmode Updated", desc))

    @commands.command()
    @commands.has_permissions(manage_messages=True)
    async def purge(self, ctx: commands.Context, amount: int):
        if amount < 1:
            return await ctx.send(embed=self.build_embed(
                f"{WARN} Invalid Amount", "Amount must be greater than `0`."))
        deleted = await ctx.channel.purge(limit=amount + 1)
        msg = await ctx.send(embed=self.build_embed(
            f"{TICK} Purge Complete",
            f"Deleted **{len(deleted) - 1}** messages in {ctx.channel.mention}."))
        await msg.delete(delay=3)

    @app_commands.command(name="purge", description="Delete a number of messages from this channel")
    @app_commands.describe(amount="Number of messages to delete")
    @app_commands.default_permissions(manage_messages=True)
    async def purge_slash(self, interaction: discord.Interaction, amount: int):
        if amount < 1:
            return await interaction.response.send_message(
                embed=self.build_embed(f"{WARN} Invalid Amount",
                                       "Amount must be greater than `0`."), ephemeral=True)
        await interaction.response.defer(ephemeral=True)
        deleted = await interaction.channel.purge(limit=amount)
        await interaction.followup.send(embed=self.build_embed(
            f"{TICK} Purge Complete",
            f"Deleted **{len(deleted)}** messages in {interaction.channel.mention}."), ephemeral=True)

    @commands.command()
    @commands.has_permissions(manage_roles=True)
    async def roleadd(self, ctx: commands.Context, member: discord.Member, *, role: discord.Role):
        if role >= ctx.guild.me.top_role:
            return await ctx.send(embed=self.build_embed(
                f"{CROSS} Permission Error",
                "I cannot assign a role equal to or higher than my own."))
        if role in member.roles:
            return await ctx.send(embed=self.build_embed(
                f"{WARN} Already Assigned",
                f"{member.mention} already has the {role.mention} role."))
        await member.add_roles(role, reason=f"Role added by {ctx.author}")
        await ctx.send(embed=self.build_embed(
            f"{TICK} Role Added",
            f"**User:** {member.mention}\n"
            f"**{ARROW} Role:** {role.mention}\n"
            f"**{ARROW} Moderator:** {ctx.author.mention}",
            thumbnail_url=member.display_avatar.url
        ))

    @app_commands.command(name="roleadd", description="Add a role to a member")
    @app_commands.describe(member="Target member", role="Role to add")
    @app_commands.default_permissions(manage_roles=True)
    async def roleadd_slash(self, interaction: discord.Interaction,
                            member: discord.Member, role: discord.Role):
        if role >= interaction.guild.me.top_role:
            return await interaction.response.send_message(
                embed=self.build_embed(f"{CROSS} Permission Error",
                                       "I cannot assign a role equal to or higher than my own."), ephemeral=True)
        if role in member.roles:
            return await interaction.response.send_message(
                embed=self.build_embed(f"{WARN} Already Assigned",
                                       f"{member.mention} already has the {role.mention} role."), ephemeral=True)
        await member.add_roles(role, reason=f"Role added by {interaction.user}")
        await interaction.response.send_message(embed=self.build_embed(
            f"{TICK} Role Added",
            f"**User:** {member.mention}\n"
            f"**{ARROW} Role:** {role.mention}\n"
            f"**{ARROW} Moderator:** {interaction.user.mention}",
            thumbnail_url=member.display_avatar.url
        ))

    @commands.command()
    @commands.has_permissions(manage_roles=True)
    async def roleremove(self, ctx: commands.Context, member: discord.Member, *, role: discord.Role):
        if role >= ctx.guild.me.top_role:
            return await ctx.send(embed=self.build_embed(
                f"{CROSS} Permission Error",
                "I cannot remove a role equal to or higher than my own."))
        if role not in member.roles:
            return await ctx.send(embed=self.build_embed(
                f"{WARN} Not Assigned",
                f"{member.mention} does not have the {role.mention} role."))
        await member.remove_roles(role, reason=f"Role removed by {ctx.author}")
        await ctx.send(embed=self.build_embed(
            f"{TICK} Role Removed",
            f"**User:** {member.mention}\n"
            f"**{ARROW} Role:** {role.mention}\n"
            f"**{ARROW} Moderator:** {ctx.author.mention}",
            thumbnail_url=member.display_avatar.url
        ))

    @app_commands.command(name="roleremove", description="Remove a role from a member")
    @app_commands.describe(member="Target member", role="Role to remove")
    @app_commands.default_permissions(manage_roles=True)
    async def roleremove_slash(self, interaction: discord.Interaction,
                               member: discord.Member, role: discord.Role):
        if role >= interaction.guild.me.top_role:
            return await interaction.response.send_message(
                embed=self.build_embed(f"{CROSS} Permission Error",
                                       "I cannot remove a role equal to or higher than my own."), ephemeral=True)
        if role not in member.roles:
            return await interaction.response.send_message(
                embed=self.build_embed(f"{WARN} Not Assigned",
                                       f"{member.mention} does not have the {role.mention} role."), ephemeral=True)
        await member.remove_roles(role, reason=f"Role removed by {interaction.user}")
        await interaction.response.send_message(embed=self.build_embed(
            f"{TICK} Role Removed",
            f"**User:** {member.mention}\n"
            f"**{ARROW} Role:** {role.mention}\n"
            f"**{ARROW} Moderator:** {interaction.user.mention}",
            thumbnail_url=member.display_avatar.url
        ))

    @commands.command()
    @commands.has_permissions(deafen_members=True)
    async def deafen(self, ctx: commands.Context, member: discord.Member, *,
                     reason: str = "No reason provided"):
        ok, msg = self.can_moderate(ctx.author, member, ctx.guild)
        if not ok:
            return await ctx.send(embed=self.build_embed(f"{CROSS} Action Blocked", msg))
        if not member.voice:
            return await ctx.send(embed=self.build_embed(
                f"{WARN} Not in Voice", f"{member.mention} is not in a voice channel."))
        await member.edit(deafen=True, reason=reason)
        await ctx.send(embed=self.build_embed(
            f"{RESTRICT} Member Deafened",
            f"**User:** {member.mention}\n"
            f"**{ARROW} Reason:** {reason}\n"
            f"**{ARROW} Moderator:** {ctx.author.mention}",
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
                embed=self.build_embed(f"{CROSS} Action Blocked", msg), ephemeral=True)
        if not member.voice:
            return await interaction.response.send_message(
                embed=self.build_embed(f"{WARN} Not in Voice",
                                       f"{member.mention} is not in a voice channel."), ephemeral=True)
        await member.edit(deafen=True, reason=reason)
        await interaction.response.send_message(embed=self.build_embed(
            f"{RESTRICT} Member Deafened",
            f"**User:** {member.mention}\n"
            f"**{ARROW} Reason:** {reason}\n"
            f"**{ARROW} Moderator:** {interaction.user.mention}",
            thumbnail_url=member.display_avatar.url
        ))

    @commands.command()
    @commands.has_permissions(deafen_members=True)
    async def undeafen(self, ctx: commands.Context, member: discord.Member):
        if not member.voice:
            return await ctx.send(embed=self.build_embed(
                f"{WARN} Not in Voice", f"{member.mention} is not in a voice channel."))
        await member.edit(deafen=False)
        await ctx.send(embed=self.build_embed(
            f"{TICK} Member Undeafened",
            f"**User:** {member.mention}\n"
            f"**{ARROW} Status:** Can now hear audio.\n"
            f"**{ARROW} Moderator:** {ctx.author.mention}",
            thumbnail_url=member.display_avatar.url
        ))

    @app_commands.command(name="undeafen", description="Remove server-deafen from a member")
    @app_commands.describe(member="Member to undeafen")
    @app_commands.default_permissions(deafen_members=True)
    async def undeafen_slash(self, interaction: discord.Interaction, member: discord.Member):
        if not member.voice:
            return await interaction.response.send_message(
                embed=self.build_embed(f"{WARN} Not in Voice",
                                       f"{member.mention} is not in a voice channel."), ephemeral=True)
        await member.edit(deafen=False)
        await interaction.response.send_message(embed=self.build_embed(
            f"{TICK} Member Undeafened",
            f"**User:** {member.mention}\n"
            f"**{ARROW} Status:** Can now hear audio.\n"
            f"**{ARROW} Moderator:** {interaction.user.mention}",
            thumbnail_url=member.display_avatar.url
        ))

    @commands.command()
    @commands.has_permissions(move_members=True)
    async def vcban(self, ctx: commands.Context, member: discord.Member, *,
                    reason: str = "No reason provided"):
        ok, msg = self.can_moderate(ctx.author, member, ctx.guild)
        if not ok:
            return await ctx.send(embed=self.build_embed(f"{CROSS} Action Blocked", msg))
        if not member.voice:
            return await ctx.send(embed=self.build_embed(
                f"{WARN} Not in Voice", f"{member.mention} is not in a voice channel."))
        await member.move_to(None, reason=reason)
        await ctx.send(embed=self.build_embed(
            f"{RESTRICT} Disconnected from Voice",
            f"**User:** {member.mention}\n"
            f"**{ARROW} Reason:** {reason}\n"
            f"**{ARROW} Moderator:** {ctx.author.mention}",
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
                embed=self.build_embed(f"{CROSS} Action Blocked", msg), ephemeral=True)
        if not member.voice:
            return await interaction.response.send_message(
                embed=self.build_embed(f"{WARN} Not in Voice",
                                       f"{member.mention} is not in a voice channel."), ephemeral=True)
        await member.move_to(None, reason=reason)
        await interaction.response.send_message(embed=self.build_embed(
            f"{RESTRICT} Disconnected from Voice",
            f"**User:** {member.mention}\n"
            f"**{ARROW} Reason:** {reason}\n"
            f"**{ARROW} Moderator:** {interaction.user.mention}",
            thumbnail_url=member.display_avatar.url
        ))

    @commands.command(aliases=["ui", "whois"])
    async def userinfo(self, ctx: commands.Context, member: Optional[discord.Member] = None):
        member    = member or ctx.author
        joined    = discord.utils.format_dt(member.joined_at, "D") if member.joined_at else "Unknown"
        created   = discord.utils.format_dt(member.created_at, "D")
        roles     = [r.mention for r in reversed(member.roles) if r != ctx.guild.default_role]
        roles_str = " ".join(roles) if roles else "`None`"
        status    = str(member.status).title() if hasattr(member, "status") else "Unknown"
        await ctx.send(embed=self.build_embed(
            f"{STAR} User Info — {member.display_name}",
            f"**User:** {member.mention}\n"
            f"**{ARROW} ID:** `{member.id}`\n"
            f"**{ARROW} Status:** {status}\n"
            f"**{ARROW} Account Created:** {created}\n"
            f"**{ARROW} Joined Server:** {joined}\n"
            f"**{ARROW} Roles [{len(roles)}]:** {roles_str}",
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
            f"{STAR} User Info — {member.display_name}",
            f"**User:** {member.mention}\n"
            f"**{ARROW} ID:** `{member.id}`\n"
            f"**{ARROW} Status:** {status}\n"
            f"**{ARROW} Account Created:** {created}\n"
            f"**{ARROW} Joined Server:** {joined}\n"
            f"**{ARROW} Roles [{len(roles)}]:** {roles_str}",
            thumbnail_url=member.display_avatar.url
        ))

    @commands.command(aliases=["si"])
    async def serverinfo(self, ctx: commands.Context):
        guild   = ctx.guild
        created = discord.utils.format_dt(guild.created_at, "D")
        owner   = guild.owner.mention if guild.owner else "`Unknown`"
        bots    = sum(1 for m in guild.members if m.bot)
        humans  = guild.member_count - bots
        await ctx.send(embed=self.build_embed(
            f"{STAR} Server Info — {guild.name}",
            f"**{ARROW} Owner:** {owner}\n"
            f"**{ARROW} Members:** {guild.member_count} ({humans} humans, {bots} bots)\n"
            f"**{ARROW} Channels:** {len(guild.channels)}\n"
            f"**{ARROW} Roles:** {len(guild.roles)}\n"
            f"**{ARROW} Created:** {created}\n"
            f"**{ARROW} ID:** `{guild.id}`\n"
            f"**{ARROW} Boost Level:** {guild.premium_tier} ({guild.premium_subscription_count} boosts)",
            thumbnail_url=guild.icon.url if guild.icon else None
        ))

    @app_commands.command(name="serverinfo", description="Get information about this server")
    async def serverinfo_slash(self, interaction: discord.Interaction):
        guild   = interaction.guild
        created = discord.utils.format_dt(guild.created_at, "D")
        owner   = guild.owner.mention if guild.owner else "`Unknown`"
        bots    = sum(1 for m in guild.members if m.bot)
        humans  = guild.member_count - bots
        await interaction.response.send_message(embed=self.build_embed(
            f"{STAR} Server Info — {guild.name}",
            f"**{ARROW} Owner:** {owner}\n"
            f"**{ARROW} Members:** {guild.member_count} ({humans} humans, {bots} bots)\n"
            f"**{ARROW} Channels:** {len(guild.channels)}\n"
            f"**{ARROW} Roles:** {len(guild.roles)}\n"
            f"**{ARROW} Created:** {created}\n"
            f"**{ARROW} ID:** `{guild.id}`\n"
            f"**{ARROW} Boost Level:** {guild.premium_tier} ({guild.premium_subscription_count} boosts)",
            thumbnail_url=guild.icon.url if guild.icon else None
        ))

    @commands.command(aliases=["i"])
    async def invites(self, ctx: commands.Context, member: Optional[discord.Member] = None):
        member = member or ctx.author
        gid    = str(ctx.guild.id)
        uid    = str(member.id)
        data   = self.invites.get(gid, {}).get(uid, {})
        total  = data.get("total", 0)
        left   = data.get("left", 0)
        fake   = data.get("fake", 0)
        real   = max(0, total - left - fake)
        await ctx.send(embed=self.build_embed(
            f"{LEAF} Invites — {member.display_name}",
            f"**{ARROW} Total Invites:** `{total}`\n"
            f"**{ARROW} Real:** `{real}`\n"
            f"**{ARROW} Left:** `{left}`\n"
            f"**{ARROW} Fake/Bonus:** `{fake}`",
            thumbnail_url=member.display_avatar.url
        ))

    @app_commands.command(name="invites", description="Check invite count for a member")
    @app_commands.describe(member="Member to check (leave blank for yourself)")
    async def invites_slash(self, interaction: discord.Interaction,
                            member: Optional[discord.Member] = None):
        member = member or interaction.user
        gid    = str(interaction.guild.id)
        uid    = str(member.id)
        data   = self.invites.get(gid, {}).get(uid, {})
        total  = data.get("total", 0)
        left   = data.get("left", 0)
        fake   = data.get("fake", 0)
        real   = max(0, total - left - fake)
        await interaction.response.send_message(embed=self.build_embed(
            f"{LEAF} Invites — {member.display_name}",
            f"**{ARROW} Total Invites:** `{total}`\n"
            f"**{ARROW} Real:** `{real}`\n"
            f"**{ARROW} Left:** `{left}`\n"
            f"**{ARROW} Fake/Bonus:** `{fake}`",
            thumbnail_url=member.display_avatar.url
        ))

    @commands.command()
    @commands.has_permissions(manage_guild=True)
    async def resetinv(self, ctx: commands.Context, member: discord.Member):
        gid = str(ctx.guild.id)
        uid = str(member.id)
        self.invites.setdefault(gid, {})[uid] = {"total": 0, "left": 0, "fake": 0}
        save_json(INV_FILE, self.invites)
        await ctx.send(embed=self.build_embed(
            f"{TICK} Invites Reset",
            f"**{ARROW} User:** {member.mention}\n"
            f"**{ARROW} All invite counts have been reset to `0`.**\n"
            f"**{ARROW} Moderator:** {ctx.author.mention}",
            thumbnail_url=member.display_avatar.url
        ))

    @app_commands.command(name="resetinv", description="Reset a member's invite count to zero")
    @app_commands.describe(member="Member whose invites to reset")
    @app_commands.default_permissions(manage_guild=True)
    async def resetinv_slash(self, interaction: discord.Interaction, member: discord.Member):
        gid = str(interaction.guild.id)
        uid = str(member.id)
        self.invites.setdefault(gid, {})[uid] = {"total": 0, "left": 0, "fake": 0}
        save_json(INV_FILE, self.invites)
        await interaction.response.send_message(embed=self.build_embed(
            f"{TICK} Invites Reset",
            f"**{ARROW} User:** {member.mention}\n"
            f"**{ARROW} All invite counts have been reset to `0`.**\n"
            f"**{ARROW} Moderator:** {interaction.user.mention}",
            thumbnail_url=member.display_avatar.url
        ))

    @commands.command()
    @commands.has_permissions(ban_members=True)
    async def banid(self, ctx: commands.Context, user_id: int, *,
                    reason: str = "No reason provided"):
        try:
            user = await self.bot.fetch_user(user_id)
        except discord.NotFound:
            return await ctx.send(embed=self.build_embed(
                f"{CROSS} User Not Found", f"No user found with ID `{user_id}`."))
        try:
            await ctx.guild.ban(user, reason=reason, delete_message_seconds=0)
        except discord.Forbidden:
            return await ctx.send(embed=self.build_embed(
                f"{CROSS} Permission Error", "I don't have permission to ban that user."))
        await ctx.send(embed=self.build_embed(
            f"{RESTRICT} User Banned by ID",
            f"**User:** {user} (`{user.id}`)\n"
            f"**{ARROW} Reason:** {reason}\n"
            f"**{ARROW} Moderator:** {ctx.author.mention}",
            thumbnail_url=user.display_avatar.url
        ))

    @app_commands.command(name="banid", description="Ban a user by their ID (even if not in server)")
    @app_commands.describe(user_id="User ID to ban", reason="Reason for ban")
    @app_commands.default_permissions(ban_members=True)
    async def banid_slash(self, interaction: discord.Interaction, user_id: str,
                          reason: str = "No reason provided"):
        try:
            user = await self.bot.fetch_user(int(user_id))
        except (discord.NotFound, ValueError):
            return await interaction.response.send_message(
                embed=self.build_embed(f"{CROSS} User Not Found",
                                       f"No user found with ID `{user_id}`."), ephemeral=True)
        try:
            await interaction.guild.ban(user, reason=reason, delete_message_seconds=0)
        except discord.Forbidden:
            return await interaction.response.send_message(
                embed=self.build_embed(f"{CROSS} Permission Error",
                                       "I don't have permission to ban that user."), ephemeral=True)
        await interaction.response.send_message(embed=self.build_embed(
            f"{RESTRICT} User Banned by ID",
            f"**User:** {user} (`{user.id}`)\n"
            f"**{ARROW} Reason:** {reason}\n"
            f"**{ARROW} Moderator:** {interaction.user.mention}",
            thumbnail_url=user.display_avatar.url
        ))

    @commands.command()
    @commands.has_permissions(ban_members=True)
    @commands.guild_only()
    async def massban(self, ctx: commands.Context, *, ids: str):
        raw = [i.strip() for i in ids.split() if i.strip().isdigit()]
        if not raw:
            return await ctx.send(embed=self.build_embed(
                f"{CROSS} Invalid Input",
                "Provide at least one user ID. Example: `?massban 123456 789012`"))
        banned, failed = [], []
        for uid in raw:
            try:
                user = await self.bot.fetch_user(int(uid))
                await ctx.guild.ban(user, reason=f"Massban by {ctx.author}", delete_message_seconds=0)
                banned.append(f"`{uid}`")
            except Exception:
                failed.append(f"`{uid}`")
        desc = f"**{ARROW} Banned ({len(banned)}):** {', '.join(banned) or 'None'}\n"
        if failed:
            desc += f"**{ARROW} Failed ({len(failed)}):** {', '.join(failed)}\n"
        desc += f"**{ARROW} Moderator:** {ctx.author.mention}"
        await ctx.send(embed=self.build_embed(f"{RESTRICT} Mass Ban Complete", desc))

    @app_commands.command(name="massban", description="Ban multiple users by ID at once")
    @app_commands.describe(ids="Space-separated list of user IDs to ban")
    @app_commands.default_permissions(ban_members=True)
    async def massban_slash(self, interaction: discord.Interaction, ids: str):
        raw = [i.strip() for i in ids.split() if i.strip().isdigit()]
        if not raw:
            return await interaction.response.send_message(
                embed=self.build_embed(f"{CROSS} Invalid Input",
                                       "Provide at least one user ID."), ephemeral=True)
        await interaction.response.defer()
        banned, failed = [], []
        for uid in raw:
            try:
                user = await self.bot.fetch_user(int(uid))
                await interaction.guild.ban(user, reason=f"Massban by {interaction.user}",
                                            delete_message_seconds=0)
                banned.append(f"`{uid}`")
            except Exception:
                failed.append(f"`{uid}`")
        desc = f"**{ARROW} Banned ({len(banned)}):** {', '.join(banned) or 'None'}\n"
        if failed:
            desc += f"**{ARROW} Failed ({len(failed)}):** {', '.join(failed)}\n"
        desc += f"**{ARROW} Moderator:** {interaction.user.mention}"
        await interaction.followup.send(embed=self.build_embed(f"{RESTRICT} Mass Ban Complete", desc))

    @commands.command()
    @commands.has_permissions(manage_roles=True)
    async def strip(self, ctx: commands.Context, member: discord.Member):
        ok, msg = self.can_moderate(ctx.author, member, ctx.guild)
        if not ok:
            return await ctx.send(embed=self.build_embed(f"{CROSS} Action Blocked", msg))
        removable = [r for r in member.roles if r != ctx.guild.default_role
                     and r < ctx.guild.me.top_role and r < ctx.author.top_role]
        if not removable:
            return await ctx.send(embed=self.build_embed(
                f"{WARN} Nothing to Strip",
                f"{member.mention} has no roles I can remove."))
        await member.remove_roles(*removable, reason=f"Roles stripped by {ctx.author}")
        names = ", ".join(r.name for r in removable)
        await ctx.send(embed=self.build_embed(
            f"{TICK} Roles Stripped",
            f"**User:** {member.mention}\n"
            f"**{ARROW} Removed:** {names}\n"
            f"**{ARROW} Moderator:** {ctx.author.mention}",
            thumbnail_url=member.display_avatar.url
        ))

    @app_commands.command(name="strip", description="Remove all assignable roles from a member")
    @app_commands.describe(member="Member to strip roles from")
    @app_commands.default_permissions(manage_roles=True)
    async def strip_slash(self, interaction: discord.Interaction, member: discord.Member):
        ok, msg = self.can_moderate(interaction.user, member, interaction.guild)
        if not ok:
            return await interaction.response.send_message(
                embed=self.build_embed(f"{CROSS} Action Blocked", msg), ephemeral=True)
        removable = [r for r in member.roles if r != interaction.guild.default_role
                     and r < interaction.guild.me.top_role and r < interaction.user.top_role]
        if not removable:
            return await interaction.response.send_message(
                embed=self.build_embed(f"{WARN} Nothing to Strip",
                                       f"{member.mention} has no roles I can remove."), ephemeral=True)
        await member.remove_roles(*removable, reason=f"Roles stripped by {interaction.user}")
        names = ", ".join(r.name for r in removable)
        await interaction.response.send_message(embed=self.build_embed(
            f"{TICK} Roles Stripped",
            f"**User:** {member.mention}\n"
            f"**{ARROW} Removed:** {names}\n"
            f"**{ARROW} Moderator:** {interaction.user.mention}",
            thumbnail_url=member.display_avatar.url
        ))

    @commands.command(aliases=["ann"])
    @commands.has_permissions(manage_messages=True)
    async def announce(self, ctx: commands.Context, channel: discord.TextChannel, *, message: str):
        e = discord.Embed(description=message, color=COLOUR)
        e.set_author(name=ctx.guild.name,
                     icon_url=ctx.guild.icon.url if ctx.guild.icon else discord.Embed.Empty)
        footer_text = random_footer()
        if self.bot.user:
            e.set_footer(text=footer_text, icon_url=self.bot.user.display_avatar.url)
        else:
            e.set_footer(text=footer_text)
        await channel.send(embed=e)
        await ctx.send(embed=self.build_embed(
            f"{TICK} Announcement Sent",
            f"Message delivered to {channel.mention}."))

    @app_commands.command(name="announce", description="Send an announcement to a channel")
    @app_commands.describe(channel="Target channel", message="Announcement message")
    @app_commands.default_permissions(manage_messages=True)
    async def announce_slash(self, interaction: discord.Interaction,
                             channel: discord.TextChannel, message: str):
        e = discord.Embed(description=message, color=COLOUR)
        e.set_author(name=interaction.guild.name,
                     icon_url=interaction.guild.icon.url if interaction.guild.icon else discord.Embed.Empty)
        footer_text = random_footer()
        if self.bot.user:
            e.set_footer(text=footer_text, icon_url=self.bot.user.display_avatar.url)
        else:
            e.set_footer(text=footer_text)
        await channel.send(embed=e)
        await interaction.response.send_message(embed=self.build_embed(
            f"{TICK} Announcement Sent",
            f"Message delivered to {channel.mention}."), ephemeral=True)

    @commands.command()
    @commands.has_permissions(move_members=True)
    async def move(self, ctx: commands.Context, member: discord.Member,
                   channel: discord.VoiceChannel):
        if not member.voice:
            return await ctx.send(embed=self.build_embed(
                f"{WARN} Not in Voice", f"{member.mention} is not in a voice channel."))
        await member.move_to(channel, reason=f"Moved by {ctx.author}")
        await ctx.send(embed=self.build_embed(
            f"{TICK} Member Moved",
            f"**User:** {member.mention}\n"
            f"**{ARROW} Channel:** {channel.mention}\n"
            f"**{ARROW} Moderator:** {ctx.author.mention}",
            thumbnail_url=member.display_avatar.url
        ))

    @app_commands.command(name="move", description="Move a member to a voice channel")
    @app_commands.describe(member="Member to move", channel="Target voice channel")
    @app_commands.default_permissions(move_members=True)
    async def move_slash(self, interaction: discord.Interaction,
                         member: discord.Member, channel: discord.VoiceChannel):
        if not member.voice:
            return await interaction.response.send_message(
                embed=self.build_embed(f"{WARN} Not in Voice",
                                       f"{member.mention} is not in a voice channel."), ephemeral=True)
        await member.move_to(channel, reason=f"Moved by {interaction.user}")
        await interaction.response.send_message(embed=self.build_embed(
            f"{TICK} Member Moved",
            f"**User:** {member.mention}\n"
            f"**{ARROW} Channel:** {channel.mention}\n"
            f"**{ARROW} Moderator:** {interaction.user.mention}",
            thumbnail_url=member.display_avatar.url
        ))

    @kick.error
    @ban.error
    @softban.error
    @unban.error
    @mute.error
    @unmute.error
    @nick.error
    @warn.error
    @clearwarns.error
    @lock.error
    @unlock.error
    @hide.error
    @unhide.error
    @slowmode.error
    @purge.error
    @roleadd.error
    @roleremove.error
    @deafen.error
    @undeafen.error
    @vcban.error
    @resetinv.error
    @massban.error
    @strip.error
    @announce.error
    @move.error
    async def mod_error(self, ctx: commands.Context, error: commands.CommandError):
        if isinstance(error, commands.MissingPermissions):
            perms = ", ".join(f"`{p}`" for p in error.missing_permissions)
            return await ctx.send(embed=self.build_embed(
                f"{CROSS} Missing Permissions",
                f"You need {perms} to run this command."))
        if isinstance(error, commands.BotMissingPermissions):
            perms = ", ".join(f"`{p}`" for p in error.missing_permissions)
            return await ctx.send(embed=self.build_embed(
                f"{CROSS} Bot Missing Permissions",
                f"I need {perms} to perform this action."))
        if isinstance(error, commands.MemberNotFound):
            return await ctx.send(embed=self.build_embed(
                f"{CROSS} Member Not Found",
                "That member could not be found. Check the name or ID."))
        if isinstance(error, commands.BadArgument):
            return await ctx.send(embed=self.build_embed(
                f"{WARN} Bad Argument",
                f"Invalid input. Use `?help {ctx.command}` to see usage."))
        if isinstance(error, commands.MissingRequiredArgument):
            return await ctx.send(embed=self.build_embed(
                f"{WARN} Missing Argument",
                f"`{error.param.name}` is required. Use `?help {ctx.command}` to see usage."))


class TempVC(commands.Cog):

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def cog_load(self):
        self.bot.add_view(VCControlPanel())

    async def post_panel(self, channel: discord.TextChannel):
        async for msg in channel.history(limit=20):
            if msg.author == self.bot.user:
                try:
                    await msg.delete()
                except Exception:
                    pass

        embed = discord.Embed(
            title="🎛️  Voice Channel Controller",
            description="Join **➕ Create VC** to get your own private room.\nUse the buttons below to manage your channel.",
            color=0xFFB6C1
        )

        embed.set_image(url=DEFAULT_PANEL_IMAGE)
        embed.set_thumbnail(url=self.bot.user.display_avatar.url)
        embed.set_footer(text="Your channel auto-deletes when empty.")

        await channel.send(embed=embed, view=VCControlPanel())

    @commands.command(name="vcsetup")
    @commands.has_permissions(administrator=True)
    async def vcsetup_prefix(self, ctx: commands.Context):
        modal_trigger = discord.ui.View()

        async def open_modal(interaction: discord.Interaction):
            await interaction.response.send_modal(SetupModal(self))

        btn = discord.ui.Button(label="⚙️ Open Setup", style=discord.ButtonStyle.primary)
        btn.callback = open_modal
        modal_trigger.add_item(btn)

        await ctx.send(
            "Click the button below to configure the Temporary VC system.",
            view=modal_trigger,
            delete_after=60
        )

    @app_commands.command(name="vcsetup", description="Admin: set up the Temporary VC system.")
    @app_commands.default_permissions(administrator=True)
    async def vcsetup_slash(self, interaction: discord.Interaction):
        await interaction.response.send_modal(SetupModal(self))

    @commands.Cog.listener()
    async def on_voice_state_update(
        self,
        member: discord.Member,
        before: discord.VoiceState,
        after: discord.VoiceState
    ):
        config = get_guild_config(member.guild.id)
        if not config:
            return

        create_vc_id = config.get("create_vc_id")
        category_id = config.get("category_id")
        temp = get_temp_channels(member.guild.id)

        if after.channel and after.channel.id == create_vc_id:
            category = member.guild.get_channel(category_id)

            new_vc = await member.guild.create_voice_channel(
                name=f"🎙️ {member.display_name}'s Room",
                category=category,
                reason="Temporary VC created"
            )

            await new_vc.set_permissions(member,
                manage_channels=True,
                connect=True,
                speak=True,
                move_members=True,
                mute_members=True,
                deafen_members=True
            )

            try:
                await member.move_to(new_vc)
            except discord.HTTPException:
                pass

            temp[str(new_vc.id)] = member.id
            set_temp_channels(member.guild.id, temp)

        if before.channel and str(before.channel.id) in temp:
            await asyncio.sleep(1)
            ch = member.guild.get_channel(before.channel.id)
            if ch and len(ch.members) == 0:
                temp = get_temp_channels(member.guild.id)
                temp.pop(str(ch.id), None)
                set_temp_channels(member.guild.id, temp)
                try:
                    await ch.delete(reason="Temporary VC empty — auto-deleted.")
                except discord.NotFound:
                    pass

    @app_commands.command(name="vcpanel", description="Resend the VC control panel (admin).")
    @app_commands.default_permissions(administrator=True)
    async def vcpanel_slash(self, interaction: discord.Interaction):
        config = get_guild_config(interaction.guild_id)
        if not config:
            return await interaction.response.send_message(
                "❌ Run `/vcsetup` first.", ephemeral=True
            )
        ch = interaction.guild.get_channel(config["chat_channel_id"])
        if not ch:
            return await interaction.response.send_message(
                "❌ Panel channel not found. Run `/vcsetup` again.", ephemeral=True
            )
        await self.post_panel(ch)
        await interaction.response.send_message("✅ Panel refreshed!", ephemeral=True)

    @commands.command(name="vcpanel")
    @commands.has_permissions(administrator=True)
    async def vcpanel_prefix(self, ctx: commands.Context):
        config = get_guild_config(ctx.guild.id)
        if not config:
            return await ctx.send("❌ Run `vcsetup` first.")
        ch = ctx.guild.get_channel(config["chat_channel_id"])
        if not ch:
            return await ctx.send("❌ Panel channel not found. Run `vcsetup` again.")
        await self.post_panel(ch)
        await ctx.send("✅ Panel refreshed!", delete_after=5)


async def setup(bot: commands.Bot):
    await bot.add_cog(Moderation(bot))
    await bot.add_cog(TempVC(bot))

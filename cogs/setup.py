from __future__ import annotations

import asyncio
import io
import json
import os
from datetime import datetime

import discord
from discord import app_commands
from discord.ext import commands

from cogs.core import (
    BRAND_COLOR,
    error_embed,
    make_embed,
    success_embed,
)

E_TICKET    = "<:pastelstar:1517787024306733206>"
E_TICK      = "<:tick:1514194122192191569>"
E_CROSS     = "<:cross:1514194117985570888>"
E_WARN      = "<:warnicon:1515660263129350155>"
E_ARROW     = "<:rightarrow:1515660270557466685>"
E_LEAF      = "<:leaf:1515660279944319006>"
E_RESTRICT  = "<:restrict:1519939088998989824>"

PANELS_FILE  = "data/ticket_panels.json"
TICKETS_FILE = "data/tickets.json"
WELCOME_FILE = "data/welcome_data.json"


def load_json(path: str) -> dict:
    if not os.path.exists(path):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as f:
            json.dump({}, f)
    with open(path, "r") as f:
        return json.load(f)


def save_json(path: str, data: dict) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        json.dump(data, f, indent=4)


def get_panels() -> dict:
    return load_json(PANELS_FILE)


def save_panels(data: dict) -> None:
    save_json(PANELS_FILE, data)


def get_tickets() -> dict:
    return load_json(TICKETS_FILE)


def save_tickets(data: dict) -> None:
    save_json(TICKETS_FILE, data)


def _load_welcome() -> dict:
    return load_json(WELCOME_FILE)


def _save_welcome(data: dict) -> None:
    save_json(WELCOME_FILE, data)


def build_panel_embed(panel_data: dict) -> discord.Embed:
    embed = discord.Embed(
        title=panel_data.get("panel_title", "Support"),
        description=panel_data.get("panel_description", "Click below to open a ticket."),
        color=panel_data.get("color", 0x5865F2),
        timestamp=datetime.utcnow(),
    )
    if panel_data.get("thumbnail_url"):
        embed.set_thumbnail(url=panel_data["thumbnail_url"])
    embed.set_footer(text=panel_data.get("footer_text", "Ticket System"))
    return embed


def build_config_embed(panel_id: str, panel_data: dict, guild: discord.Guild) -> discord.Embed:
    category   = guild.get_channel(panel_data.get("category_id", 0))
    role       = guild.get_role(panel_data.get("support_role_id", 0))
    log_ch_id  = panel_data.get("log_channel_id")
    color      = panel_data.get("color", 0x5865F2)

    embed = discord.Embed(
        title=f"{E_RESTRICT}  Panel Config",
        color=color,
        timestamp=datetime.utcnow(),
    )
    embed.add_field(name="Panel ID",         value=f"`{panel_id}`",                                    inline=False)
    embed.add_field(name="📌 Title",          value=panel_data.get("panel_title", "N/A"),               inline=True)
    embed.add_field(name=f"{E_TICKET} Button", value=panel_data.get("button_label", "N/A"),             inline=True)
    embed.add_field(name="📂 Category",       value=category.mention if category else "❌ Not found",   inline=True)
    embed.add_field(name="🛡️ Support Role",   value=role.mention if role else "❌ Not found",           inline=True)
    embed.add_field(name="📋 Log Channel",    value=f"<#{log_ch_id}>" if log_ch_id else "Not set",      inline=True)
    embed.add_field(name="🎨 Color",          value=f"`#{hex(color)[2:].upper()}`",                     inline=True)
    embed.add_field(name="📝 Footer",         value=panel_data.get("footer_text", "N/A"),               inline=True)

    if panel_data.get("channel_id") and panel_data.get("message_id"):
        link = f"https://discord.com/channels/{panel_data['guild_id']}/{panel_data['channel_id']}/{panel_data['message_id']}"
        embed.add_field(name="🔗 Panel Message", value=f"[Jump to panel]({link})", inline=False)

    return embed


def resolve(text: str, member: discord.Member, guild: discord.Guild) -> str:
    if not text:
        return text
    avatar = member.display_avatar.url if member else (guild.icon.url if guild.icon else "")
    replacements = {
        "{user}":        member.mention if member else "",
        "{username}":    str(member) if member else "",
        "{displayname}": member.display_name if member else "",
        "{server}":      guild.name,
        "{membercount}": str(guild.member_count),
        "{userid}":      str(member.id) if member else "",
        "{joined}":      discord.utils.format_dt(member.joined_at or datetime.utcnow(), "D") if member else "",
        "{created}":     discord.utils.format_dt(member.created_at, "D") if member else "",
        "{user-avatar}": avatar,
    }
    for token, value in replacements.items():
        text = text.replace(token, value)
    return text


def build_welcome_embed(cfg: dict, member: discord.Member, guild: discord.Guild) -> discord.Embed:
    color = BRAND_COLOR
    try:
        raw = cfg.get("color", "")
        if raw:
            color = int(raw.lstrip("0x").lstrip("#"), 16)
    except (ValueError, AttributeError):
        color = BRAND_COLOR

    title       = resolve(cfg.get("title", ""), member, guild)
    desc        = resolve(
        cfg.get("description", f"👋 Welcome {{user}} to **{{server}}**!\nYou are member **#{{membercount}}**."),
        member, guild,
    )
    author_text = resolve(cfg.get("author", f"Welcome to {guild.name}!"), member, guild)
    footer_text = resolve(
        cfg.get("footer", f"{guild.name} • Member #{guild.member_count}"),
        member, guild,
    )

    embed = discord.Embed(title=title or None, description=desc, color=color)
    embed.set_author(
        name=author_text,
        icon_url=guild.icon.url if guild.icon else discord.embeds.EmptyEmbed,
    )
    embed.set_footer(text=footer_text)

    if cfg.get("show_timestamp", True):
        embed.timestamp = datetime.utcnow()

    thumb_url = cfg.get("thumbnail_url", "").strip()
    if thumb_url:
        embed.set_thumbnail(url=resolve(thumb_url, member, guild))
    elif cfg.get("show_thumbnail", True):
        embed.set_thumbnail(url=member.display_avatar.url)

    image_url = cfg.get("image_url", "").strip()
    if image_url:
        embed.set_image(url=resolve(image_url, member, guild))
    elif cfg.get("show_banner") and guild.banner:
        embed.set_image(url=guild.banner.url)

    return embed


class InteractionCtxWrapper:
    def __init__(self, interaction: discord.Interaction):
        self.interaction = interaction
        self.author      = interaction.user
        self.channel     = interaction.channel
        self.guild       = interaction.guild
        self.bot         = interaction.client
        self._responded  = False

    async def send(self, *args, **kwargs):
        if not self._responded:
            self._responded = True
            await self.interaction.response.send_message(*args, **kwargs)
            return await self.interaction.original_response()
        else:
            return await self.interaction.followup.send(*args, **kwargs)


class _FakeCtx:
    def __init__(self, interaction: discord.Interaction):
        self.author = interaction.user
        self.guild  = interaction.guild


class TicketOpenView(discord.ui.View):
    def __init__(self, panel_id: str, button_label: str = "Open a Ticket"):
        super().__init__(timeout=None)
        self.add_item(TicketOpenButton(panel_id, button_label))


class TicketOpenButton(discord.ui.Button):
    def __init__(self, panel_id: str, label: str):
        super().__init__(
            label=label,
            style=discord.ButtonStyle.primary,
            emoji=E_TICKET,
            custom_id=f"ticket_open:{panel_id}",
        )
        self.panel_id = panel_id

    async def callback(self, interaction: discord.Interaction):
        panels = get_panels()
        panel  = panels.get(self.panel_id)
        if not panel:
            return await interaction.response.send_message(f"{E_CROSS} Panel not found.", ephemeral=True)

        tickets  = get_tickets()
        guild_id = str(interaction.guild.id)
        user_id  = str(interaction.user.id)
        key      = f"{guild_id}_{user_id}"

        if key in tickets and tickets[key].get("open"):
            ch = interaction.guild.get_channel(tickets[key]["channel_id"])
            if ch:
                return await interaction.response.send_message(
                    f"{E_CROSS} You already have an open ticket: {ch.mention}", ephemeral=True
                )

        category     = interaction.guild.get_channel(panel["category_id"])
        support_role = interaction.guild.get_role(panel["support_role_id"])

        if not category:
            return await interaction.response.send_message(
                f"{E_CROSS} Ticket category not found. Contact an admin.", ephemeral=True
            )

        overwrites = {
            interaction.guild.default_role: discord.PermissionOverwrite(view_channel=False),
            interaction.user: discord.PermissionOverwrite(
                view_channel=True, send_messages=True,
                read_message_history=True, attach_files=True, embed_links=True,
            ),
            interaction.guild.me: discord.PermissionOverwrite(
                view_channel=True, send_messages=True,
                manage_channels=True, read_message_history=True, manage_messages=True,
            ),
        }
        if support_role:
            overwrites[support_role] = discord.PermissionOverwrite(
                view_channel=True, send_messages=True,
                read_message_history=True, manage_messages=True,
            )

        ticket_count = sum(1 for k in tickets if k.startswith(guild_id))
        channel_name = f"ticket-{interaction.user.name.lower().replace(' ', '-')}-{ticket_count + 1}"

        await interaction.response.defer(ephemeral=True)

        channel = await interaction.guild.create_text_channel(
            name=channel_name,
            category=category,
            overwrites=overwrites,
            reason=f"Ticket opened by {interaction.user}",
        )

        tickets[key] = {
            "open":          True,
            "channel_id":    channel.id,
            "panel_id":      self.panel_id,
            "opened_at":     datetime.utcnow().isoformat(),
            "opened_by":     interaction.user.id,
            "ticket_number": ticket_count + 1,
        }
        save_tickets(tickets)

        welcome_embed = discord.Embed(
            title=f"{E_TICKET}  Ticket #{ticket_count + 1}",
            description=(
                f"Hey {interaction.user.mention}, welcome! 👋\n\n"
                f"Please describe your issue and our support team will assist you shortly.\n\n"
                f"**Opened:** <t:{int(datetime.utcnow().timestamp())}:F>\n"
                f"**Panel:** {panel['panel_title']}"
            ),
            color=panel.get("color", 0x5865F2),
            timestamp=datetime.utcnow(),
        )
        welcome_embed.set_author(
            name=interaction.user.display_name,
            icon_url=interaction.user.display_avatar.url,
        )
        if panel.get("thumbnail_url"):
            welcome_embed.set_thumbnail(url=panel["thumbnail_url"])
        welcome_embed.set_footer(
            text=panel.get("footer_text", "Ticket System"),
            icon_url=interaction.guild.icon.url if interaction.guild.icon else None,
        )

        mention_str = interaction.user.mention
        if support_role:
            mention_str += f" | {support_role.mention}"

        view = TicketControlView(self.panel_id, interaction.user.id)
        await channel.send(content=mention_str, embed=welcome_embed, view=view)

        log_channel_id = panel.get("log_channel_id")
        if log_channel_id:
            log_ch = interaction.guild.get_channel(log_channel_id)
            if log_ch:
                log_embed = discord.Embed(
                    title=f"{E_LEAF} Ticket Opened",
                    color=0x57F287,
                    timestamp=datetime.utcnow(),
                )
                log_embed.add_field(name="User",    value=f"{interaction.user.mention} (`{interaction.user.id}`)", inline=True)
                log_embed.add_field(name="Channel", value=channel.mention,                                          inline=True)
                log_embed.add_field(name="Panel",   value=panel["panel_title"],                                     inline=True)
                log_embed.set_thumbnail(url=interaction.user.display_avatar.url)
                log_embed.set_footer(text=f"Ticket #{ticket_count + 1}")
                await log_ch.send(embed=log_embed)

        await interaction.followup.send(f"{E_TICK} Ticket created: {channel.mention}", ephemeral=True)


class TicketControlView(discord.ui.View):
    def __init__(self, panel_id: str, opener_id: int):
        super().__init__(timeout=None)
        self.add_item(TicketCloseButton(panel_id, opener_id))
        self.add_item(TicketClaimButton(panel_id))
        self.add_item(TicketTranscriptButton(panel_id))


class TicketCloseButton(discord.ui.Button):
    def __init__(self, panel_id: str, opener_id: int):
        super().__init__(
            label="Close Ticket",
            style=discord.ButtonStyle.danger,
            emoji=E_RESTRICT,
            custom_id=f"ticket_close:{panel_id}:{opener_id}",
        )
        self.panel_id  = panel_id
        self.opener_id = int(opener_id)

    async def callback(self, interaction: discord.Interaction):
        panels       = get_panels()
        panel        = panels.get(self.panel_id, {})
        support_role = interaction.guild.get_role(panel.get("support_role_id", 0))

        is_staff  = (support_role and support_role in interaction.user.roles) or interaction.user.guild_permissions.administrator
        is_opener = interaction.user.id == self.opener_id

        if not (is_staff or is_opener):
            return await interaction.response.send_message(
                f"{E_CROSS} You don't have permission to close this ticket.", ephemeral=True
            )

        embed = discord.Embed(
            title=f"{E_RESTRICT} Close this ticket?",
            description=f"Requested by {interaction.user.mention}\n\nThis will save a transcript and delete the channel.",
            color=0xED4245,
            timestamp=datetime.utcnow(),
        )
        await interaction.response.send_message(
            embed=embed,
            view=TicketCloseConfirmView(self.panel_id, self.opener_id),
        )


class TicketCloseConfirmView(discord.ui.View):
    def __init__(self, panel_id: str, opener_id: int):
        super().__init__(timeout=60)
        self.panel_id  = panel_id
        self.opener_id = opener_id

    @discord.ui.button(label="Confirm Close", style=discord.ButtonStyle.danger, emoji="✅")
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        panels       = get_panels()
        panel        = panels.get(self.panel_id, {})
        support_role = interaction.guild.get_role(panel.get("support_role_id", 0))

        is_staff  = (support_role and support_role in interaction.user.roles) or interaction.user.guild_permissions.administrator
        is_opener = interaction.user.id == self.opener_id

        if not (is_staff or is_opener):
            return await interaction.response.send_message(f"{E_CROSS} You can't do that.", ephemeral=True)

        tickets     = get_tickets()
        guild_id    = str(interaction.guild.id)
        opener_key  = f"{guild_id}_{self.opener_id}"
        ticket_data = tickets.get(opener_key, {})

        lines = []
        async for message in interaction.channel.history(limit=500, oldest_first=True):
            if not message.author.bot:
                ts = message.created_at.strftime("%Y-%m-%d %H:%M:%S")
                lines.append(f"[{ts}] {message.author.display_name}: {message.content}")

        transcript_text = "\n".join(lines) if lines else "No messages."

        closed_embed = discord.Embed(
            title=f"{E_RESTRICT} Ticket Closed",
            description=f"Closed by {interaction.user.mention}\nDeleting in **5 seconds**...",
            color=0xED4245,
            timestamp=datetime.utcnow(),
        )
        closed_embed.set_footer(text=panel.get("footer_text", "Ticket System"))
        await interaction.response.edit_message(embed=closed_embed, view=None)

        log_channel_id = panel.get("log_channel_id")
        if log_channel_id:
            log_ch = interaction.guild.get_channel(log_channel_id)
            if log_ch:
                opener    = interaction.guild.get_member(self.opener_id)
                log_embed = discord.Embed(
                    title=f"{E_RESTRICT} Ticket Closed",
                    color=0xED4245,
                    timestamp=datetime.utcnow(),
                )
                log_embed.add_field(name="Closed By", value=interaction.user.mention,   inline=True)
                log_embed.add_field(name="Opened By", value=f"<@{self.opener_id}>",     inline=True)
                log_embed.add_field(name="Panel",     value=panel.get("panel_title", "Unknown"), inline=True)

                opened_at = ticket_data.get("opened_at")
                if opened_at:
                    log_embed.add_field(
                        name="Opened At",
                        value=f"<t:{int(datetime.fromisoformat(opened_at).timestamp())}:F>",
                        inline=False,
                    )
                if opener:
                    log_embed.set_thumbnail(url=opener.display_avatar.url)

                await log_ch.send(embed=log_embed)
                if lines:
                    await log_ch.send(
                        file=discord.File(
                            fp=io.StringIO(transcript_text),
                            filename=f"transcript-{interaction.channel.name}.txt",
                        )
                    )

        if opener_key in tickets:
            tickets[opener_key]["open"] = False
            save_tickets(tickets)

        await asyncio.sleep(5)
        await interaction.channel.delete(reason=f"Ticket closed by {interaction.user}")
        self.stop()

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.secondary, emoji="✖️")
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(content="↩️ Cancelled.", embed=None, view=None)
        self.stop()


class TicketClaimButton(discord.ui.Button):
    def __init__(self, panel_id: str):
        super().__init__(
            label="Claim",
            style=discord.ButtonStyle.success,
            emoji=E_ARROW,
            custom_id=f"ticket_claim:{panel_id}",
        )
        self.panel_id = panel_id

    async def callback(self, interaction: discord.Interaction):
        panels       = get_panels()
        panel        = panels.get(self.panel_id, {})
        support_role = interaction.guild.get_role(panel.get("support_role_id", 0))

        is_staff = (support_role and support_role in interaction.user.roles) or interaction.user.guild_permissions.administrator
        if not is_staff:
            return await interaction.response.send_message(
                f"{E_CROSS} Only support staff can claim tickets.", ephemeral=True
            )

        embed = discord.Embed(
            description=f"{E_TICK} Ticket claimed by {interaction.user.mention}",
            color=0x57F287,
            timestamp=datetime.utcnow(),
        )
        await interaction.response.send_message(embed=embed)
        self.label    = f"Claimed by {interaction.user.display_name}"
        self.style    = discord.ButtonStyle.secondary
        self.disabled = True
        await interaction.message.edit(view=self.view)


class TicketTranscriptButton(discord.ui.Button):
    def __init__(self, panel_id: str):
        super().__init__(
            label="Transcript",
            style=discord.ButtonStyle.secondary,
            emoji=E_LEAF,
            custom_id=f"ticket_transcript:{panel_id}",
        )
        self.panel_id = panel_id

    async def callback(self, interaction: discord.Interaction):
        panels       = get_panels()
        panel        = panels.get(self.panel_id, {})
        support_role = interaction.guild.get_role(panel.get("support_role_id", 0))

        is_staff = (support_role and support_role in interaction.user.roles) or interaction.user.guild_permissions.administrator
        if not is_staff:
            return await interaction.response.send_message(
                f"{E_CROSS} Only support staff can pull transcripts.", ephemeral=True
            )

        await interaction.response.defer(ephemeral=True)
        lines = []
        async for msg in interaction.channel.history(limit=500, oldest_first=True):
            if not msg.author.bot:
                ts = msg.created_at.strftime("%Y-%m-%d %H:%M:%S")
                lines.append(f"[{ts}] {msg.author.display_name}: {msg.content}")

        text = "\n".join(lines) if lines else "No messages."
        await interaction.followup.send(
            file=discord.File(fp=io.StringIO(text), filename=f"transcript-{interaction.channel.name}.txt"),
            ephemeral=True,
        )


class TicketConfigView(discord.ui.View):
    def __init__(self, ctx, panel_id: str, panel_data: dict):
        super().__init__(timeout=120)
        self.ctx        = ctx
        self.panel_id   = panel_id
        self.panel_data = panel_data

    @discord.ui.button(label="Edit Panel", style=discord.ButtonStyle.primary, emoji="✏️")
    async def edit_panel(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.ctx.author:
            return await interaction.response.send_message("Not your config session.", ephemeral=True)
        await interaction.response.send_message(
            embed=discord.Embed(description="✏️ Starting edit session in chat...", color=0x5865F2),
            ephemeral=True,
        )
        await run_ticket_setup(self.ctx, edit_panel_id=self.panel_id)
        self.stop()

    @discord.ui.button(label="Delete Panel", style=discord.ButtonStyle.danger, emoji="🗑️")
    async def delete_panel(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.ctx.author:
            return await interaction.response.send_message("Not your config session.", ephemeral=True)
        confirm_view = TicketDeleteConfirmView(self.ctx, self.panel_id, self.panel_data)
        await interaction.response.send_message(
            embed=discord.Embed(
                title=f"{E_WARN} Delete Panel?",
                description="This will remove the panel and delete the posted message. This cannot be undone.",
                color=0xED4245,
            ),
            view=confirm_view,
            ephemeral=True,
        )
        self.stop()


class TicketDeleteConfirmView(discord.ui.View):
    def __init__(self, ctx, panel_id: str, panel_data: dict):
        super().__init__(timeout=60)
        self.ctx        = ctx
        self.panel_id   = panel_id
        self.panel_data = panel_data

    @discord.ui.button(label="Yes, Delete", style=discord.ButtonStyle.danger, emoji="🗑️")
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.ctx.author:
            return await interaction.response.send_message("Not your config session.", ephemeral=True)
        panels = get_panels()
        panel  = panels.get(self.panel_id)
        if panel:
            ch = interaction.guild.get_channel(panel.get("channel_id", 0))
            if ch and panel.get("message_id"):
                try:
                    msg = await ch.fetch_message(panel["message_id"])
                    await msg.delete()
                except Exception:
                    pass
            del panels[self.panel_id]
            save_panels(panels)
        await interaction.response.edit_message(
            embed=discord.Embed(description=f"{E_TICK} Panel deleted.", color=0x57F287),
            view=None,
        )
        self.stop()

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.secondary, emoji="✖️")
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(
            embed=discord.Embed(description="↩️ Cancelled.", color=0x5865F2),
            view=None,
        )
        self.stop()


class TicketPostConfirmView(discord.ui.View):
    def __init__(self, ctx, edit_panel_id, panel_data: dict, preview_msg: discord.Message):
        super().__init__(timeout=120)
        self.ctx           = ctx
        self.edit_panel_id = edit_panel_id
        self.panel_data    = panel_data
        self.preview_msg   = preview_msg

    @discord.ui.button(label="Post Panel", style=discord.ButtonStyle.success, emoji="📨")
    async def post(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.ctx.author:
            return await interaction.response.send_message("Not your setup.", ephemeral=True)

        panels = get_panels()

        if self.edit_panel_id and self.edit_panel_id in panels:
            panel_id = self.edit_panel_id
            old      = panels[panel_id]
            if old.get("channel_id") and old.get("message_id"):
                ch = interaction.guild.get_channel(old["channel_id"])
                if ch:
                    try:
                        old_msg = await ch.fetch_message(old["message_id"])
                        await old_msg.delete()
                    except Exception:
                        pass
        else:
            panel_id = f"{interaction.guild.id}_{int(datetime.utcnow().timestamp())}"

        embed = build_panel_embed(self.panel_data)
        view  = TicketOpenView(panel_id, self.panel_data["button_label"])
        sent  = await interaction.channel.send(embed=embed, view=view)

        self.panel_data["channel_id"] = interaction.channel.id
        self.panel_data["message_id"] = sent.id
        panels[panel_id] = self.panel_data
        save_panels(panels)

        try:
            await self.preview_msg.delete()
        except Exception:
            pass

        await interaction.response.edit_message(
            content=None,
            embed=discord.Embed(
                description=f"{E_TICK} Panel posted! ID: `{panel_id}`",
                color=0x57F287,
            ),
            view=None,
        )
        self.stop()

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.danger, emoji="✖️")
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.ctx.author:
            return await interaction.response.send_message("Not your setup.", ephemeral=True)
        try:
            await self.preview_msg.delete()
        except Exception:
            pass
        await interaction.response.edit_message(
            embed=discord.Embed(description=f"{E_CROSS} Setup cancelled.", color=0xED4245),
            view=None,
        )
        self.stop()


async def run_ticket_setup(ctx, edit_panel_id=None):
    bot      = ctx.bot
    guild    = ctx.guild
    total    = 9
    existing = {}

    if edit_panel_id:
        panels   = get_panels()
        existing = panels.get(edit_panel_id, {})

    async def ask_step(title: str, desc: str, step: int, timeout: int = 60):
        embed = discord.Embed(
            title=f"Step {step}/{total} — {title}",
            description=desc,
            color=0x5865F2,
        )
        embed.set_footer(text="Type 'cancel' to stop setup • Type 'skip' for optional fields")
        msg = await ctx.send(embed=embed)

        def check(m):
            return m.author == ctx.author and m.channel == ctx.channel

        try:
            reply = await bot.wait_for("message", check=check, timeout=timeout)
            try:
                await reply.delete()
            except Exception:
                pass
            await msg.delete()
            if reply.content.strip().lower() == "cancel":
                await ctx.send(embed=discord.Embed(description=f"{E_CROSS} Setup cancelled.", color=0xED4245))
                return None
            return reply.content.strip()
        except asyncio.TimeoutError:
            await msg.delete()
            await ctx.send(embed=discord.Embed(description=f"{E_WARN} Timed out. Run the command again.", color=0xED4245))
            return None

    panel_title = await ask_step(
        "Panel Title",
        f"What should the **title** of your ticket panel be?\n\n"
        f"{'> Current: `' + existing.get('panel_title', '') + '`' if existing else '> Example: `Support Center`'}",
        1,
    )
    if panel_title is None:
        return
    if panel_title.lower() == "skip" and existing.get("panel_title"):
        panel_title = existing["panel_title"]

    panel_description = await ask_step(
        "Panel Description",
        f"What should the **description** say? This appears on the panel embed.\n\n"
        f"{'> Current: `' + existing.get('panel_description', '')[:60] + '...`' if existing else '> Example: `Click below to open a support ticket.`'}",
        2,
    )
    if panel_description is None:
        return
    if panel_description.lower() == "skip" and existing.get("panel_description"):
        panel_description = existing["panel_description"]

    button_label = await ask_step(
        "Button Label",
        f"What should the **open ticket button** say?\n\n"
        f"{'> Current: `' + existing.get('button_label', '') + '`' if existing else '> Example: `Open a Ticket` or `Create Support Ticket`'}",
        3,
    )
    if button_label is None:
        return
    if button_label.lower() == "skip" and existing.get("button_label"):
        button_label = existing["button_label"]

    category_val = await ask_step(
        "Ticket Category",
        "**Mention or paste the ID** of the category where tickets should be created.\n\n"
        "> Right-click the category → Copy ID\n"
        "> Or just paste the raw number",
        4,
    )
    if category_val is None:
        return

    category_id  = None
    cat_id_str   = category_val.strip().replace("<#", "").replace(">", "")
    if cat_id_str.isdigit():
        cat = guild.get_channel(int(cat_id_str))
        if cat and isinstance(cat, discord.CategoryChannel):
            category_id = cat.id
    if not category_id:
        await ctx.send(embed=discord.Embed(
            description=f"{E_CROSS} Couldn't find that category. Make sure it's a category, not a channel.",
            color=0xED4245,
        ))
        return

    role_val = await ask_step(
        "Support Role",
        "**Mention or paste the ID** of your support/staff role.\n\n"
        "> Mention it like `@Support` or paste the role ID",
        5,
    )
    if role_val is None:
        return

    support_role_id = None
    role_str        = role_val.strip().replace("<@&", "").replace(">", "")
    if role_str.isdigit():
        role = guild.get_role(int(role_str))
        if role:
            support_role_id = role.id
    if not support_role_id:
        await ctx.send(embed=discord.Embed(
            description=f"{E_CROSS} Couldn't find that role. Try mentioning it or use the role ID.",
            color=0xED4245,
        ))
        return

    log_val = await ask_step(
        "Log Channel (Optional)",
        "**Mention the channel** where ticket logs should be sent.\n\n"
        "> Example: `#ticket-logs`\n> Type `skip` to skip this",
        6,
    )
    if log_val is None:
        return

    log_channel_id = existing.get("log_channel_id")
    if log_val.lower() != "skip":
        log_str = log_val.strip().replace("<#", "").replace(">", "")
        if log_str.isdigit():
            lch = guild.get_channel(int(log_str))
            if lch:
                log_channel_id = lch.id

    color_val = await ask_step(
        "Embed Color (Optional)",
        "Send a **hex color code** for the panel embed.\n\n"
        "> Example: `#5865F2` or `FF0000`\n> Type `skip` to use default",
        7,
    )
    if color_val is None:
        return

    color = existing.get("color", 0x5865F2)
    if color_val.lower() != "skip":
        try:
            color = int(color_val.strip().lstrip("#"), 16)
        except ValueError:
            await ctx.send(embed=discord.Embed(description=f"{E_WARN} Invalid color, using default.", color=0x5865F2))

    footer_val = await ask_step(
        "Footer Text (Optional)",
        f"What should the **footer** say on embeds?\n\n"
        f"{'> Current: `' + existing.get('footer_text', '') + '`' if existing else '> Example: `Ticket System • Server Name`'}\n> Type `skip` to keep default",
        8,
    )
    if footer_val is None:
        return

    footer_text = existing.get("footer_text", "Ticket System")
    if footer_val.lower() != "skip":
        footer_text = footer_val

    thumbnail_val = await ask_step(
        "Thumbnail Image URL (Optional)",
        "Paste an **image URL** to show as thumbnail on the panel.\n\n"
        "> Type `skip` to not use one",
        9,
    )
    if thumbnail_val is None:
        return

    thumbnail_url = existing.get("thumbnail_url", "")
    if thumbnail_val.lower() != "skip":
        thumbnail_url = thumbnail_val

    panel_data = {
        "guild_id":        guild.id,
        "panel_title":     panel_title,
        "panel_description": panel_description,
        "button_label":    button_label,
        "category_id":     category_id,
        "support_role_id": support_role_id,
        "log_channel_id":  log_channel_id,
        "color":           color,
        "footer_text":     footer_text,
        "thumbnail_url":   thumbnail_url,
        "channel_id":      existing.get("channel_id"),
        "message_id":      existing.get("message_id"),
    }

    preview_embed = build_panel_embed(panel_data)
    await ctx.send(
        embed=discord.Embed(
            title=f"{E_TICK} Setup Complete — Preview",
            description="Here's how your panel will look. Click **Post Panel** to send it here, or **Cancel** to abort.",
            color=color,
        )
    )
    panel_preview = await ctx.send(embed=preview_embed)
    confirm_view  = TicketPostConfirmView(ctx, edit_panel_id, panel_data, panel_preview)
    await ctx.send(view=confirm_view)


class WelcomeSetupView(discord.ui.View):
    def __init__(self, cog: "Setup", ctx, config: dict):
        super().__init__(timeout=300)
        self.cog    = cog
        self.ctx    = ctx
        self.config = config
        self.msg: discord.Message | None = None
        self._sync_toggle_buttons()

    def _sync_toggle_buttons(self):
        cfg = self.config
        for item in self.children:
            if not isinstance(item, discord.ui.Button):
                continue
            name = item.custom_id or ""
            if "btn_ping" in name:
                on         = cfg.get("ping_on_join", False)
                item.label = "🔔 Ping: ON" if on else "🔔 Ping: OFF"
                item.style = discord.ButtonStyle.success if on else discord.ButtonStyle.secondary
            elif "btn_dm_toggle" in name:
                on         = cfg.get("dm_on_join", False)
                item.label = "✉️ DM: ON" if on else "✉️ DM: OFF"
                item.style = discord.ButtonStyle.success if on else discord.ButtonStyle.secondary
            elif "btn_timestamp" in name:
                on         = cfg.get("show_timestamp", True)
                item.label = "🕒 Timestamp: ON" if on else "🕒 Timestamp: OFF"
                item.style = discord.ButtonStyle.success if on else discord.ButtonStyle.secondary

    def _panel_embed(self) -> discord.Embed:
        cfg          = self.config
        desc         = cfg.get("description", "not set")
        desc_preview = (desc[:52] + "…") if len(desc) > 52 else desc
        thumb_val    = cfg.get("thumbnail_url") or ("avatar" if cfg.get("show_thumbnail", True) else "off")
        image_val    = cfg.get("image_url")     or ("banner" if cfg.get("show_banner") else "off")
        ping_val     = f"{E_TICK} on" if cfg.get("ping_on_join", False) else f"{E_CROSS} off"
        dm_val       = f"{E_TICK} on" if cfg.get("dm_on_join",   False) else f"{E_CROSS} off"
        ts_val       = f"{E_TICK} on" if cfg.get("show_timestamp", True) else f"{E_CROSS} off"
        ch_val       = f"<#{cfg['channel_id']}>" if cfg.get("channel_id") else "`not set`"

        lines = [
            f"**Title**         `{cfg.get('title') or 'not set'}`",
            f"**Description**   `{desc_preview}`",
            f"**Color**         `{cfg.get('color') or hex(BRAND_COLOR)}`",
            f"**Author**        `{cfg.get('author') or 'not set'}`",
            f"**Footer**        `{cfg.get('footer') or 'not set'}`",
            f"**Thumbnail**     `{thumb_val}`",
            f"**Image/Banner**  `{image_val}`",
            f"**Ping on Join**  {ping_val}",
            f"**DM on Join**    {dm_val}",
            f"**Timestamp**     {ts_val}",
            f"**Channel**       {ch_val}",
            "",
            "**Placeholders:** `{user}` `{server}` `{membercount}`",
            "`{username}` `{displayname}` `{userid}` `{user-avatar}`",
        ]
        return make_embed(
            title=f"{E_LEAF}  Welcome Setup Panel",
            description="\n".join(lines),
            color=BRAND_COLOR,
            footer="Use the buttons below to edit  •  panel times out in 5 min",
        )

    def _preview_embed(self) -> discord.Embed:
        return build_welcome_embed(self.config, self.ctx.author, self.ctx.guild)

    async def _refresh(self, interaction: discord.Interaction):
        self._sync_toggle_buttons()
        await interaction.response.edit_message(
            embeds=[self._panel_embed(), self._preview_embed()],
            view=self,
        )

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.ctx.author.id:
            await interaction.response.send_message("This panel isn't yours!", ephemeral=True)
            return False
        return True

    @discord.ui.button(label="📝 Title", style=discord.ButtonStyle.secondary, row=0, custom_id="btn_title")
    async def btn_title(self, interaction: discord.Interaction, _: discord.ui.Button):
        await interaction.response.send_modal(
            WelcomeFieldModal(self, "title", "Embed Title", "e.g.  Welcome to {server}!", single_line=True)
        )

    @discord.ui.button(label="📄 Description", style=discord.ButtonStyle.secondary, row=0, custom_id="btn_desc")
    async def btn_desc(self, interaction: discord.Interaction, _: discord.ui.Button):
        await interaction.response.send_modal(
            WelcomeFieldModal(self, "description", "Embed Description",
                              "👋 Welcome {user} to **{server}**!\nYou are member **#{membercount}**.",
                              single_line=False)
        )

    @discord.ui.button(label="🎨 Color", style=discord.ButtonStyle.secondary, row=0, custom_id="btn_color")
    async def btn_color(self, interaction: discord.Interaction, _: discord.ui.Button):
        await interaction.response.send_modal(
            WelcomeFieldModal(self, "color", "Embed Color (hex)", "e.g.  5865F2  or  #5865F2", single_line=True)
        )

    @discord.ui.button(label="✍️ Author", style=discord.ButtonStyle.secondary, row=0, custom_id="btn_author")
    async def btn_author(self, interaction: discord.Interaction, _: discord.ui.Button):
        await interaction.response.send_modal(
            WelcomeFieldModal(self, "author", "Author Text", "e.g.  Welcome to {server}!", single_line=True)
        )

    @discord.ui.button(label="🔻 Footer", style=discord.ButtonStyle.secondary, row=1, custom_id="btn_footer")
    async def btn_footer(self, interaction: discord.Interaction, _: discord.ui.Button):
        await interaction.response.send_modal(
            WelcomeFieldModal(self, "footer", "Footer Text", "e.g.  {server} • Member #{membercount}", single_line=True)
        )

    @discord.ui.button(label="🖼️ Thumbnail", style=discord.ButtonStyle.primary, row=1, custom_id="btn_thumb")
    async def btn_thumb(self, interaction: discord.Interaction, _: discord.ui.Button):
        await interaction.response.send_modal(
            WelcomeImageModal(self, field="thumbnail_url", toggle_field="show_thumbnail",
                              title="Thumbnail Image",
                              placeholder="URL or {user-avatar} — leave blank to toggle on/off")
        )

    @discord.ui.button(label="🏞️ Image/Banner", style=discord.ButtonStyle.primary, row=1, custom_id="btn_banner")
    async def btn_banner(self, interaction: discord.Interaction, _: discord.ui.Button):
        await interaction.response.send_modal(
            WelcomeImageModal(self, field="image_url", toggle_field="show_banner",
                              title="Large Image / Banner",
                              placeholder="URL or {user-avatar} — leave blank to toggle server banner")
        )

    @discord.ui.button(label="✉️ DM Message", style=discord.ButtonStyle.secondary, row=1, custom_id="btn_dm_msg")
    async def btn_dm_msg(self, interaction: discord.Interaction, _: discord.ui.Button):
        await interaction.response.send_modal(
            WelcomeFieldModal(self, "dm_message", "DM Message",
                              "e.g.  Welcome to {server}, {displayname}! 🎉",
                              single_line=False)
        )

    @discord.ui.button(label="🔔 Ping: OFF", style=discord.ButtonStyle.secondary, row=2, custom_id="btn_ping")
    async def btn_ping(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.config["ping_on_join"] = not self.config.get("ping_on_join", False)
        await self._refresh(interaction)

    @discord.ui.button(label="✉️ DM: OFF", style=discord.ButtonStyle.secondary, row=2, custom_id="btn_dm_toggle")
    async def btn_dm_toggle(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.config["dm_on_join"] = not self.config.get("dm_on_join", False)
        await self._refresh(interaction)

    @discord.ui.button(label="🕒 Timestamp: ON", style=discord.ButtonStyle.success, row=2, custom_id="btn_timestamp")
    async def btn_timestamp(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.config["show_timestamp"] = not self.config.get("show_timestamp", True)
        await self._refresh(interaction)

    @discord.ui.button(label="💾 Save & Finish", style=discord.ButtonStyle.success, row=3, custom_id="btn_save")
    async def btn_save(self, interaction: discord.Interaction, _: discord.ui.Button):
        data = _load_welcome()
        data[str(self.ctx.guild.id)] = self.config
        _save_welcome(data)
        self.stop()
        for item in self.children:
            item.disabled = True
        tip = (
            "Run `?welcomechannel #channel` or `/welcome channel` to activate welcoming."
            if not self.config.get("channel_id")
            else "Members will now be welcomed automatically ✅"
        )
        await interaction.response.edit_message(
            embeds=[success_embed(f"Welcome setup saved!\n{tip}")],
            view=self,
        )

    @discord.ui.button(label="🔄 Reset All", style=discord.ButtonStyle.danger, row=3, custom_id="btn_reset")
    async def btn_reset(self, interaction: discord.Interaction, _: discord.ui.Button):
        channel_id = self.config.get("channel_id")
        self.config.clear()
        if channel_id:
            self.config["channel_id"] = channel_id
        await self._refresh(interaction)

    @discord.ui.button(label="❌ Cancel", style=discord.ButtonStyle.danger, row=3, custom_id="btn_cancel")
    async def btn_cancel(self, interaction: discord.Interaction, _: discord.ui.Button):
        self.stop()
        await interaction.response.edit_message(
            embeds=[error_embed("Setup cancelled. No changes were saved.")],
            view=None,
        )


class WelcomeFieldModal(discord.ui.Modal):
    def __init__(self, parent: WelcomeSetupView, field: str, title: str, placeholder: str, single_line: bool):
        super().__init__(title=title)
        self.parent = parent
        self.field  = field
        self.input  = discord.ui.TextInput(
            label=title,
            placeholder=placeholder,
            style=discord.TextStyle.short if single_line else discord.TextStyle.paragraph,
            required=False,
            default=parent.config.get(field, ""),
            max_length=256 if single_line else 2000,
        )
        self.add_item(self.input)

    async def on_submit(self, interaction: discord.Interaction):
        val = self.input.value.strip()
        if self.field == "color" and val:
            val = val.lstrip("#").lstrip("0x").lstrip("0X")
            try:
                int(val, 16)
                val = "0x" + val.upper()
            except ValueError:
                await interaction.response.send_message(
                    f"{E_CROSS} Invalid hex color. Try `5865F2` or `#5865F2`.", ephemeral=True
                )
                return
        self.parent.config[self.field] = val
        await self.parent._refresh(interaction)


class WelcomeImageModal(discord.ui.Modal):
    def __init__(self, parent: WelcomeSetupView, field: str, toggle_field: str, title: str, placeholder: str):
        super().__init__(title=title)
        self.parent       = parent
        self.field        = field
        self.toggle_field = toggle_field
        self.input        = discord.ui.TextInput(
            label="Image URL  (or leave blank to toggle)",
            placeholder=placeholder,
            style=discord.TextStyle.short,
            required=False,
            default=parent.config.get(field, ""),
            max_length=500,
        )
        self.add_item(self.input)

    async def on_submit(self, interaction: discord.Interaction):
        val = self.input.value.strip()
        if val:
            self.parent.config[self.field]        = val
            self.parent.config[self.toggle_field] = False
        else:
            self.parent.config[self.field]        = ""
            self.parent.config[self.toggle_field] = not self.parent.config.get(self.toggle_field, False)
        await self.parent._refresh(interaction)


class WelcomeConfigView(discord.ui.View):
    def __init__(self, cog: "Setup", ctx, config: dict):
        super().__init__(timeout=120)
        self.cog    = cog
        self.ctx    = ctx
        self.config = config

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.ctx.author.id:
            await interaction.response.send_message("This panel isn't yours!", ephemeral=True)
            return False
        return True

    @discord.ui.button(label="✏️ Edit Setup", style=discord.ButtonStyle.primary)
    async def btn_edit(self, interaction: discord.Interaction, _: discord.ui.Button):
        self.stop()
        view = WelcomeSetupView(self.cog, self.ctx, self.config)
        await interaction.response.edit_message(
            embeds=[view._panel_embed(), view._preview_embed()],
            view=view,
        )

    @discord.ui.button(label="🗑️ Delete Setup", style=discord.ButtonStyle.danger)
    async def btn_delete(self, interaction: discord.Interaction, _: discord.ui.Button):
        data = _load_welcome()
        data.pop(str(self.ctx.guild.id), None)
        _save_welcome(data)
        self.stop()
        await interaction.response.edit_message(
            embeds=[success_embed("Welcome setup deleted.\nRun `?welcomesetup` or `/welcome setup` to create a new one.")],
            view=None,
        )


class Setup(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    welcome_group = app_commands.Group(
        name="welcome",
        description="Welcome system commands",
        default_permissions=discord.Permissions(administrator=True),
        guild_only=True,
    )

    @commands.Cog.listener()
    async def on_ready(self):
        panels = get_panels()
        for panel_id, panel_data in panels.items():
            self.bot.add_view(TicketOpenView(panel_id, panel_data.get("button_label", "Open a Ticket")))

        tickets = get_tickets()
        for key, ticket in tickets.items():
            if ticket.get("open"):
                self.bot.add_view(TicketControlView(ticket.get("panel_id", ""), ticket.get("opened_by", 0)))

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        data = _load_welcome()
        cfg  = data.get(str(member.guild.id))
        if not cfg or not cfg.get("channel_id"):
            return

        channel = member.guild.get_channel(int(cfg["channel_id"]))
        if not channel:
            return

        embed = build_welcome_embed(cfg, member, member.guild)
        ping  = member.mention if cfg.get("ping_on_join", False) else None
        await channel.send(content=ping, embed=embed)

        if cfg.get("dm_on_join", False):
            dm_text = cfg.get("dm_message", "") or f"👋 Welcome to **{member.guild.name}**, {member.display_name}!\nEnjoy your stay."
            dm_text = resolve(dm_text, member, member.guild)
            try:
                dm_embed = make_embed(
                    description=dm_text,
                    color=BRAND_COLOR,
                    thumbnail=member.guild.icon.url if member.guild.icon else None,
                    footer=member.guild.name,
                )
                await member.send(embed=dm_embed)
            except discord.Forbidden:
                pass

    @commands.command(name="ticketsetup")
    @commands.has_permissions(administrator=True)
    async def ticket_setup(self, ctx: commands.Context):
        intro = discord.Embed(
            title=f"{E_TICKET}  Ticket Panel Setup",
            description=(
                "Let's set up your ticket panel step by step.\n\n"
                "I'll ask you **9 quick questions** in chat.\n"
                "Just type your answers — no copying IDs in a rush!\n\n"
                "> Type `cancel` at any step to stop.\n"
                "> Type `skip` on optional fields to skip them."
            ),
            color=0x5865F2,
            timestamp=datetime.utcnow(),
        )
        intro.set_footer(text=f"Started by {ctx.author.display_name}", icon_url=ctx.author.display_avatar.url)
        await ctx.send(embed=intro)
        await asyncio.sleep(1)
        await run_ticket_setup(ctx)

    @app_commands.command(name="ticketsetup", description="Set up a ticket panel (step-by-step)")
    @app_commands.default_permissions(administrator=True)
    async def ticket_setup_slash(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=False)
        await interaction.followup.send(
            embed=discord.Embed(
                title=f"{E_TICKET}  Ticket Panel Setup",
                description=(
                    "Let's set up your ticket panel step by step.\n\n"
                    "I'll ask you **9 quick questions** in chat.\n"
                    "Just type your answers — no copying IDs in a rush!\n\n"
                    "> Type `cancel` at any step to stop.\n"
                    "> Type `skip` on optional fields to skip them."
                ),
                color=0x5865F2,
                timestamp=datetime.utcnow(),
            )
        )
        await asyncio.sleep(1)
        ctx              = InteractionCtxWrapper(interaction)
        ctx._responded   = True
        await run_ticket_setup(ctx)

    @commands.command(name="ticketconfig")
    @commands.has_permissions(administrator=True)
    async def ticket_config(self, ctx: commands.Context, panel_id: str = None):
        panels       = get_panels()
        guild_panels = {k: v for k, v in panels.items() if v.get("guild_id") == ctx.guild.id}

        if not guild_panels:
            return await ctx.send(embed=discord.Embed(
                description=f"{E_CROSS} No panels found. Use `?ticketsetup` to create one.",
                color=0xED4245,
            ))

        if not panel_id:
            embed = discord.Embed(
                title=f"{E_RESTRICT}  Ticket Config",
                description="Use `?ticketconfig <panel_id>` to manage a panel.\n\n**Your panels:**",
                color=0x5865F2,
                timestamp=datetime.utcnow(),
            )
            for pid, pdata in guild_panels.items():
                ch_id = pdata.get("channel_id")
                embed.add_field(
                    name=pdata.get("panel_title", "Untitled"),
                    value=f"ID: `{pid}`\nChannel: {f'<#{ch_id}>' if ch_id else 'Not set'}",
                    inline=True,
                )
            return await ctx.send(embed=embed)

        panel = guild_panels.get(panel_id)
        if not panel:
            return await ctx.send(embed=discord.Embed(
                description=f"{E_CROSS} Panel `{panel_id}` not found in this server.",
                color=0xED4245,
            ))

        embed = build_config_embed(panel_id, panel, ctx.guild)
        view  = TicketConfigView(ctx, panel_id, panel)
        await ctx.send(embed=embed, view=view)

    @app_commands.command(name="ticketconfig", description="View or manage a ticket panel")
    @app_commands.describe(panel_id="Panel ID to manage (leave blank to list all)")
    @app_commands.default_permissions(administrator=True)
    async def ticket_config_slash(self, interaction: discord.Interaction, panel_id: str = None):
        panels       = get_panels()
        guild_panels = {k: v for k, v in panels.items() if v.get("guild_id") == interaction.guild.id}

        if not guild_panels:
            return await interaction.response.send_message(embed=discord.Embed(
                description=f"{E_CROSS} No panels found. Use `/ticketsetup` to create one.",
                color=0xED4245,
            ), ephemeral=True)

        if not panel_id:
            embed = discord.Embed(
                title=f"{E_RESTRICT}  Ticket Config",
                description="Use `/ticketconfig <panel_id>` to manage a panel.\n\n**Your panels:**",
                color=0x5865F2,
                timestamp=datetime.utcnow(),
            )
            for pid, pdata in guild_panels.items():
                ch_id = pdata.get("channel_id")
                embed.add_field(
                    name=pdata.get("panel_title", "Untitled"),
                    value=f"ID: `{pid}`\nChannel: {f'<#{ch_id}>' if ch_id else 'Not set'}",
                    inline=True,
                )
            return await interaction.response.send_message(embed=embed, ephemeral=True)

        panel = guild_panels.get(panel_id)
        if not panel:
            return await interaction.response.send_message(embed=discord.Embed(
                description=f"{E_CROSS} Panel `{panel_id}` not found in this server.",
                color=0xED4245,
            ), ephemeral=True)

        embed = build_config_embed(panel_id, panel, interaction.guild)
        ctx   = InteractionCtxWrapper(interaction)
        view  = TicketConfigView(ctx, panel_id, panel)
        await interaction.response.send_message(embed=embed, view=view)

    @commands.command(name="ticketclose")
    async def ticket_close(self, ctx: commands.Context):
        tickets      = get_tickets()
        ticket_entry = None

        for key, data in tickets.items():
            if data.get("channel_id") == ctx.channel.id and data.get("open"):
                ticket_entry = data
                break

        if not ticket_entry:
            return await ctx.send(embed=discord.Embed(
                description=f"{E_CROSS} This is not an active ticket channel.", color=0xED4245
            ))

        panel_id     = ticket_entry.get("panel_id", "")
        panels       = get_panels()
        panel        = panels.get(panel_id, {})
        support_role = ctx.guild.get_role(panel.get("support_role_id", 0))

        is_staff  = (support_role and support_role in ctx.author.roles) or ctx.author.guild_permissions.administrator
        is_opener = ctx.author.id == ticket_entry.get("opened_by")

        if not (is_staff or is_opener):
            return await ctx.send(embed=discord.Embed(
                description=f"{E_CROSS} You don't have permission to close this ticket.", color=0xED4245
            ))

        embed = discord.Embed(
            title=f"{E_RESTRICT} Close this ticket?",
            description=f"Requested by {ctx.author.mention}",
            color=0xED4245,
            timestamp=datetime.utcnow(),
        )
        view = TicketCloseConfirmView(panel_id, ticket_entry.get("opened_by"))
        await ctx.send(embed=embed, view=view)

    @app_commands.command(name="ticketclose", description="Close the current ticket channel")
    async def ticket_close_slash(self, interaction: discord.Interaction):
        tickets      = get_tickets()
        ticket_entry = None

        for key, data in tickets.items():
            if data.get("channel_id") == interaction.channel.id and data.get("open"):
                ticket_entry = data
                break

        if not ticket_entry:
            return await interaction.response.send_message(
                embed=discord.Embed(description=f"{E_CROSS} This is not an active ticket channel.", color=0xED4245),
                ephemeral=True,
            )

        panel_id     = ticket_entry.get("panel_id", "")
        panels       = get_panels()
        panel        = panels.get(panel_id, {})
        support_role = interaction.guild.get_role(panel.get("support_role_id", 0))

        is_staff  = (support_role and support_role in interaction.user.roles) or interaction.user.guild_permissions.administrator
        is_opener = interaction.user.id == ticket_entry.get("opened_by")

        if not (is_staff or is_opener):
            return await interaction.response.send_message(
                embed=discord.Embed(description=f"{E_CROSS} You don't have permission to close this ticket.", color=0xED4245),
                ephemeral=True,
            )

        embed = discord.Embed(
            title=f"{E_RESTRICT} Close this ticket?",
            description=f"Requested by {interaction.user.mention}",
            color=0xED4245,
            timestamp=datetime.utcnow(),
        )
        view = TicketCloseConfirmView(panel_id, ticket_entry.get("opened_by"))
        await interaction.response.send_message(embed=embed, view=view)

    @commands.command(name="ticketadd")
    @commands.has_permissions(manage_channels=True)
    async def ticket_add(self, ctx: commands.Context, member: discord.Member):
        tickets = get_tickets()
        if not any(d.get("channel_id") == ctx.channel.id and d.get("open") for d in tickets.values()):
            return await ctx.send(embed=discord.Embed(
                description=f"{E_CROSS} This is not an active ticket channel.", color=0xED4245
            ))
        await ctx.channel.set_permissions(member, view_channel=True, send_messages=True, read_message_history=True)
        await ctx.send(embed=discord.Embed(description=f"{E_TICK} {member.mention} added to this ticket.", color=0x57F287))

    @app_commands.command(name="ticketadd", description="Add a member to the current ticket")
    @app_commands.describe(member="Member to add")
    @app_commands.default_permissions(manage_channels=True)
    async def ticket_add_slash(self, interaction: discord.Interaction, member: discord.Member):
        tickets = get_tickets()
        if not any(d.get("channel_id") == interaction.channel.id and d.get("open") for d in tickets.values()):
            return await interaction.response.send_message(
                embed=discord.Embed(description=f"{E_CROSS} This is not an active ticket channel.", color=0xED4245),
                ephemeral=True,
            )
        await interaction.channel.set_permissions(member, view_channel=True, send_messages=True, read_message_history=True)
        await interaction.response.send_message(
            embed=discord.Embed(description=f"{E_TICK} {member.mention} added to this ticket.", color=0x57F287)
        )

    @commands.command(name="ticketremove")
    @commands.has_permissions(manage_channels=True)
    async def ticket_remove(self, ctx: commands.Context, member: discord.Member):
        tickets = get_tickets()
        if not any(d.get("channel_id") == ctx.channel.id and d.get("open") for d in tickets.values()):
            return await ctx.send(embed=discord.Embed(
                description=f"{E_CROSS} This is not an active ticket channel.", color=0xED4245
            ))
        await ctx.channel.set_permissions(member, overwrite=None)
        await ctx.send(embed=discord.Embed(description=f"{E_TICK} {member.mention} removed from this ticket.", color=0xED4245))

    @app_commands.command(name="ticketremove", description="Remove a member from the current ticket")
    @app_commands.describe(member="Member to remove")
    @app_commands.default_permissions(manage_channels=True)
    async def ticket_remove_slash(self, interaction: discord.Interaction, member: discord.Member):
        tickets = get_tickets()
        if not any(d.get("channel_id") == interaction.channel.id and d.get("open") for d in tickets.values()):
            return await interaction.response.send_message(
                embed=discord.Embed(description=f"{E_CROSS} This is not an active ticket channel.", color=0xED4245),
                ephemeral=True,
            )
        await interaction.channel.set_permissions(member, overwrite=None)
        await interaction.response.send_message(
            embed=discord.Embed(description=f"{E_TICK} {member.mention} removed from this ticket.", color=0xED4245)
        )

    @commands.command(name="ticketlist")
    @commands.has_permissions(manage_channels=True)
    async def ticket_list(self, ctx: commands.Context):
        tickets      = get_tickets()
        guild_id     = str(ctx.guild.id)
        open_tickets = [d for k, d in tickets.items() if k.startswith(guild_id) and d.get("open")]

        if not open_tickets:
            return await ctx.send(embed=discord.Embed(description=f"{E_LEAF} No open tickets right now.", color=0x5865F2))

        embed = discord.Embed(
            title=f"{E_TICKET} Open Tickets — {len(open_tickets)}",
            color=0x5865F2,
            timestamp=datetime.utcnow(),
        )
        for t in open_tickets[:25]:
            ch       = ctx.guild.get_channel(t.get("channel_id", 0))
            opener   = ctx.guild.get_member(t.get("opened_by", 0))
            opened_at = t.get("opened_at", "")
            ts       = f"<t:{int(datetime.fromisoformat(opened_at).timestamp())}:R>" if opened_at else "Unknown"
            embed.add_field(
                name=ch.name if ch else "Unknown",
                value=f"By: {opener.mention if opener else 'Unknown'}\nOpened: {ts}",
                inline=True,
            )
        await ctx.send(embed=embed)

    @app_commands.command(name="ticketlist", description="List all open tickets in this server")
    @app_commands.default_permissions(manage_channels=True)
    async def ticket_list_slash(self, interaction: discord.Interaction):
        tickets      = get_tickets()
        guild_id     = str(interaction.guild.id)
        open_tickets = [d for k, d in tickets.items() if k.startswith(guild_id) and d.get("open")]

        if not open_tickets:
            return await interaction.response.send_message(
                embed=discord.Embed(description=f"{E_LEAF} No open tickets right now.", color=0x5865F2),
                ephemeral=True,
            )

        embed = discord.Embed(
            title=f"{E_TICKET} Open Tickets — {len(open_tickets)}",
            color=0x5865F2,
            timestamp=datetime.utcnow(),
        )
        for t in open_tickets[:25]:
            ch        = interaction.guild.get_channel(t.get("channel_id", 0))
            opener    = interaction.guild.get_member(t.get("opened_by", 0))
            opened_at = t.get("opened_at", "")
            ts        = f"<t:{int(datetime.fromisoformat(opened_at).timestamp())}:R>" if opened_at else "Unknown"
            embed.add_field(
                name=ch.name if ch else "Unknown",
                value=f"By: {opener.mention if opener else 'Unknown'}\nOpened: {ts}",
                inline=True,
            )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @commands.command(name="welcomesetup")
    @commands.has_permissions(administrator=True)
    @commands.guild_only()
    async def welcomesetup(self, ctx: commands.Context):
        data   = _load_welcome()
        config = data.get(str(ctx.guild.id), {})
        view   = WelcomeSetupView(self, ctx, config)
        view.msg = await ctx.send(
            embeds=[view._panel_embed(), view._preview_embed()],
            view=view,
        )

    @commands.command(name="welcomechannel")
    @commands.has_permissions(administrator=True)
    @commands.guild_only()
    async def welcomechannel(self, ctx: commands.Context, channel: discord.TextChannel):
        data = _load_welcome()
        cfg  = data.setdefault(str(ctx.guild.id), {})
        cfg["channel_id"] = channel.id
        _save_welcome(data)
        await ctx.send(embed=success_embed(
            f"Welcome channel set to {channel.mention}!\n"
            f"Run `?welcomesetup` to customise the embed."
        ))

    @commands.command(name="welcomeconfig")
    @commands.has_permissions(administrator=True)
    @commands.guild_only()
    async def welcomeconfig(self, ctx: commands.Context):
        data = _load_welcome()
        cfg  = data.get(str(ctx.guild.id))

        if not cfg:
            await ctx.send(embed=error_embed("No welcome setup found.\nRun `?welcomesetup` to create one."))
            return

        ch    = f"<#{cfg['channel_id']}>" if cfg.get("channel_id") else "`not set`"
        desc  = cfg.get("description", "not set")
        thumb = cfg.get("thumbnail_url") or ("avatar" if cfg.get("show_thumbnail", True) else "off")
        img   = cfg.get("image_url")     or ("banner" if cfg.get("show_banner") else "off")
        ping  = f"{E_TICK} on" if cfg.get("ping_on_join",  False) else f"{E_CROSS} off"
        dm    = f"{E_TICK} on" if cfg.get("dm_on_join",    False) else f"{E_CROSS} off"
        ts    = f"{E_TICK} on" if cfg.get("show_timestamp", True) else f"{E_CROSS} off"

        lines = [
            f"**Channel**       {ch}",
            f"**Title**         `{cfg.get('title') or 'not set'}`",
            f"**Color**         `{cfg.get('color') or hex(BRAND_COLOR)}`",
            f"**Author**        `{cfg.get('author') or 'not set'}`",
            f"**Footer**        `{cfg.get('footer') or 'not set'}`",
            f"**Thumbnail**     `{thumb}`",
            f"**Image**         `{img}`",
            f"**Ping on Join**  {ping}",
            f"**DM on Join**    {dm}",
            f"**Timestamp**     {ts}",
            "",
            "**Description:**",
            f"`{(desc[:200] + '…') if len(desc) > 200 else desc}`",
        ]

        view = WelcomeConfigView(self, ctx, cfg)
        await ctx.send(
            embeds=[
                make_embed(
                    title=f"{E_LEAF}  Welcome Config",
                    description="\n".join(lines),
                    color=BRAND_COLOR,
                ),
                build_welcome_embed(cfg, ctx.author, ctx.guild),
            ],
            view=view,
        )

    @commands.command(name="welcometest")
    @commands.has_permissions(administrator=True)
    @commands.guild_only()
    async def welcometest(self, ctx: commands.Context):
        data = _load_welcome()
        cfg  = data.get(str(ctx.guild.id))

        if not cfg:
            await ctx.send(embed=error_embed("No welcome setup found.\nRun `?welcomesetup` to create one."))
            return

        embed = build_welcome_embed(cfg, ctx.author, ctx.guild)
        ping  = ctx.author.mention if cfg.get("ping_on_join", False) else None
        await ctx.send(content=ping, embed=embed)

    @welcome_group.command(name="setup", description="Open the interactive welcome setup panel")
    @app_commands.checks.has_permissions(administrator=True)
    async def slash_welcomesetup(self, interaction: discord.Interaction):
        data   = _load_welcome()
        config = data.get(str(interaction.guild.id), {})
        ctx    = _FakeCtx(interaction)
        view   = WelcomeSetupView(self, ctx, config)
        await interaction.response.send_message(
            embeds=[view._panel_embed(), view._preview_embed()],
            view=view,
        )

    @welcome_group.command(name="channel", description="Set the channel where welcome messages are sent")
    @app_commands.describe(channel="The text channel to send welcome messages in")
    @app_commands.checks.has_permissions(administrator=True)
    async def slash_welcomechannel(self, interaction: discord.Interaction, channel: discord.TextChannel):
        data = _load_welcome()
        cfg  = data.setdefault(str(interaction.guild.id), {})
        cfg["channel_id"] = channel.id
        _save_welcome(data)
        await interaction.response.send_message(
            embed=success_embed(
                f"Welcome channel set to {channel.mention}!\n"
                f"Run `/welcome setup` to customise the embed."
            ),
            ephemeral=True,
        )

    @welcome_group.command(name="config", description="View the current welcome configuration")
    @app_commands.checks.has_permissions(administrator=True)
    async def slash_welcomeconfig(self, interaction: discord.Interaction):
        data = _load_welcome()
        cfg  = data.get(str(interaction.guild.id))

        if not cfg:
            await interaction.response.send_message(
                embed=error_embed("No welcome setup found.\nRun `/welcome setup` to create one."),
                ephemeral=True,
            )
            return

        ch    = f"<#{cfg['channel_id']}>" if cfg.get("channel_id") else "`not set`"
        desc  = cfg.get("description", "not set")
        thumb = cfg.get("thumbnail_url") or ("avatar" if cfg.get("show_thumbnail", True) else "off")
        img   = cfg.get("image_url")     or ("banner" if cfg.get("show_banner") else "off")
        ping  = f"{E_TICK} on" if cfg.get("ping_on_join",  False) else f"{E_CROSS} off"
        dm    = f"{E_TICK} on" if cfg.get("dm_on_join",    False) else f"{E_CROSS} off"
        ts    = f"{E_TICK} on" if cfg.get("show_timestamp", True) else f"{E_CROSS} off"

        lines = [
            f"**Channel**       {ch}",
            f"**Title**         `{cfg.get('title') or 'not set'}`",
            f"**Color**         `{cfg.get('color') or hex(BRAND_COLOR)}`",
            f"**Author**        `{cfg.get('author') or 'not set'}`",
            f"**Footer**        `{cfg.get('footer') or 'not set'}`",
            f"**Thumbnail**     `{thumb}`",
            f"**Image**         `{img}`",
            f"**Ping on Join**  {ping}",
            f"**DM on Join**    {dm}",
            f"**Timestamp**     {ts}",
            "",
            "**Description:**",
            f"`{(desc[:200] + '…') if len(desc) > 200 else desc}`",
        ]

        ctx  = _FakeCtx(interaction)
        view = WelcomeConfigView(self, ctx, cfg)
        await interaction.response.send_message(
            embeds=[
                make_embed(
                    title=f"{E_LEAF}  Welcome Config",
                    description="\n".join(lines),
                    color=BRAND_COLOR,
                ),
                build_welcome_embed(cfg, interaction.user, interaction.guild),
            ],
            view=view,
        )

    @welcome_group.command(name="test", description="Send a test welcome message using your profile")
    @app_commands.checks.has_permissions(administrator=True)
    async def slash_welcometest(self, interaction: discord.Interaction):
        data = _load_welcome()
        cfg  = data.get(str(interaction.guild.id))

        if not cfg:
            await interaction.response.send_message(
                embed=error_embed("No welcome setup found.\nRun `/welcome setup` to create one."),
                ephemeral=True,
            )
            return

        embed = build_welcome_embed(cfg, interaction.user, interaction.guild)
        ping  = interaction.user.mention if cfg.get("ping_on_join", False) else None
        await interaction.response.send_message(content=ping, embed=embed)

    @ticket_setup.error
    @ticket_config.error
    async def admin_error(self, ctx: commands.Context, error):
        if isinstance(error, commands.MissingPermissions):
            await ctx.send(embed=discord.Embed(
                description=f"{E_CROSS} You need **Administrator** permission for this.", color=0xED4245
            ))


async def setup(bot: commands.Bot):
    await bot.add_cog(Setup(bot))

from __future__ import annotations

import json
import os
import discord
from discord import app_commands
from discord.ext import commands
from datetime import datetime

from cogs.utils import (
    make_embed,
    success_embed,
    error_embed,
    BRAND_COLOR,
)

DATA_FILE = "welcome_data.json"


def _load() -> dict:
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r") as f:
            return json.load(f)
    return {}


def _save(data: dict) -> None:
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=2)


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
        cfg.get("description", "👋 Welcome {user} to **{server}**!\nYou are member **#{membercount}**."),
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


class _FakeCtx:
    """Thin shim so Views built around commands.Context work with interactions."""
    def __init__(self, interaction: discord.Interaction):
        self.author = interaction.user
        self.guild  = interaction.guild


class SetupView(discord.ui.View):

    def __init__(self, cog: "Welcome", ctx, config: dict):
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
                on = cfg.get("ping_on_join", False)
                item.label = "🔔 Ping: ON" if on else "🔔 Ping: OFF"
                item.style = discord.ButtonStyle.success if on else discord.ButtonStyle.secondary

            elif "btn_dm_toggle" in name:
                on = cfg.get("dm_on_join", False)
                item.label = "✉️ DM: ON" if on else "✉️ DM: OFF"
                item.style = discord.ButtonStyle.success if on else discord.ButtonStyle.secondary

            elif "btn_timestamp" in name:
                on = cfg.get("show_timestamp", True)
                item.label = "🕒 Timestamp: ON" if on else "🕒 Timestamp: OFF"
                item.style = discord.ButtonStyle.success if on else discord.ButtonStyle.secondary

    def _panel_embed(self) -> discord.Embed:
        cfg          = self.config
        desc         = cfg.get("description", "not set")
        desc_preview = (desc[:52] + "…") if len(desc) > 52 else desc
        thumb_val    = cfg.get("thumbnail_url") or ("avatar" if cfg.get("show_thumbnail", True) else "off")
        image_val    = cfg.get("image_url")     or ("banner" if cfg.get("show_banner") else "off")
        ping_val     = "✅ on" if cfg.get("ping_on_join", False) else "❌ off"
        dm_val       = "✅ on" if cfg.get("dm_on_join",   False) else "❌ off"
        ts_val       = "✅ on" if cfg.get("show_timestamp", True) else "❌ off"
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
            title="🎨  Welcome Setup Panel",
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
            FieldModal(self, "title", "Embed Title", "e.g.  Welcome to {server}!", single_line=True)
        )

    @discord.ui.button(label="📄 Description", style=discord.ButtonStyle.secondary, row=0, custom_id="btn_desc")
    async def btn_desc(self, interaction: discord.Interaction, _: discord.ui.Button):
        await interaction.response.send_modal(
            FieldModal(self, "description", "Embed Description",
                       "👋 Welcome {user} to **{server}**!\nYou are member **#{membercount}**.",
                       single_line=False)
        )

    @discord.ui.button(label="🎨 Color", style=discord.ButtonStyle.secondary, row=0, custom_id="btn_color")
    async def btn_color(self, interaction: discord.Interaction, _: discord.ui.Button):
        await interaction.response.send_modal(
            FieldModal(self, "color", "Embed Color (hex)", "e.g.  5865F2  or  #5865F2", single_line=True)
        )

    @discord.ui.button(label="✍️ Author", style=discord.ButtonStyle.secondary, row=0, custom_id="btn_author")
    async def btn_author(self, interaction: discord.Interaction, _: discord.ui.Button):
        await interaction.response.send_modal(
            FieldModal(self, "author", "Author Text", "e.g.  Welcome to {server}!", single_line=True)
        )

    @discord.ui.button(label="🔻 Footer", style=discord.ButtonStyle.secondary, row=1, custom_id="btn_footer")
    async def btn_footer(self, interaction: discord.Interaction, _: discord.ui.Button):
        await interaction.response.send_modal(
            FieldModal(self, "footer", "Footer Text", "e.g.  {server} • Member #{membercount}", single_line=True)
        )

    @discord.ui.button(label="🖼️ Thumbnail", style=discord.ButtonStyle.primary, row=1, custom_id="btn_thumb")
    async def btn_thumb(self, interaction: discord.Interaction, _: discord.ui.Button):
        await interaction.response.send_modal(
            ImageModal(self, field="thumbnail_url", toggle_field="show_thumbnail",
                       title="Thumbnail Image",
                       placeholder="URL or {user-avatar} — leave blank to toggle on/off")
        )

    @discord.ui.button(label="🏞️ Image/Banner", style=discord.ButtonStyle.primary, row=1, custom_id="btn_banner")
    async def btn_banner(self, interaction: discord.Interaction, _: discord.ui.Button):
        await interaction.response.send_modal(
            ImageModal(self, field="image_url", toggle_field="show_banner",
                       title="Large Image / Banner",
                       placeholder="URL or {user-avatar} — leave blank to toggle server banner")
        )

    @discord.ui.button(label="✉️ DM Message", style=discord.ButtonStyle.secondary, row=1, custom_id="btn_dm_msg")
    async def btn_dm_msg(self, interaction: discord.Interaction, _: discord.ui.Button):
        await interaction.response.send_modal(
            FieldModal(self, "dm_message", "DM Message",
                       "e.g.  Welcome to {server}, {displayname}! 🎉",
                       single_line=False)
        )

    @discord.ui.button(label="🔔 Ping: OFF", style=discord.ButtonStyle.secondary, row=2, custom_id="btn_ping")
    async def btn_ping(self, interaction: discord.Interaction, button: discord.ui.Button):
        current = self.config.get("ping_on_join", False)
        self.config["ping_on_join"] = not current
        await self._refresh(interaction)

    @discord.ui.button(label="✉️ DM: OFF", style=discord.ButtonStyle.secondary, row=2, custom_id="btn_dm_toggle")
    async def btn_dm_toggle(self, interaction: discord.Interaction, button: discord.ui.Button):
        current = self.config.get("dm_on_join", False)
        self.config["dm_on_join"] = not current
        await self._refresh(interaction)

    @discord.ui.button(label="🕒 Timestamp: ON", style=discord.ButtonStyle.success, row=2, custom_id="btn_timestamp")
    async def btn_timestamp(self, interaction: discord.Interaction, button: discord.ui.Button):
        current = self.config.get("show_timestamp", True)
        self.config["show_timestamp"] = not current
        await self._refresh(interaction)

    @discord.ui.button(label="💾 Save & Finish", style=discord.ButtonStyle.success, row=3, custom_id="btn_save")
    async def btn_save(self, interaction: discord.Interaction, _: discord.ui.Button):
        data = _load()
        data[str(self.ctx.guild.id)] = self.config
        _save(data)
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


class FieldModal(discord.ui.Modal):
    def __init__(self, parent: SetupView, field: str, title: str, placeholder: str, single_line: bool):
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
                    "❌ Invalid hex color. Try `5865F2` or `#5865F2`.", ephemeral=True
                )
                return
        self.parent.config[self.field] = val
        await self.parent._refresh(interaction)


class ImageModal(discord.ui.Modal):
    def __init__(self, parent: SetupView, field: str, toggle_field: str, title: str, placeholder: str):
        super().__init__(title=title)
        self.parent       = parent
        self.field        = field
        self.toggle_field = toggle_field
        self.input = discord.ui.TextInput(
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


class ConfigView(discord.ui.View):
    def __init__(self, cog: "Welcome", ctx, config: dict):
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
        view = SetupView(self.cog, self.ctx, self.config)
        await interaction.response.edit_message(
            embeds=[view._panel_embed(), view._preview_embed()],
            view=view,
        )

    @discord.ui.button(label="🗑️ Delete Setup", style=discord.ButtonStyle.danger)
    async def btn_delete(self, interaction: discord.Interaction, _: discord.ui.Button):
        data = _load()
        data.pop(str(self.ctx.guild.id), None)
        _save(data)
        self.stop()
        await interaction.response.edit_message(
            embeds=[success_embed("Welcome setup deleted.\nRun `?welcomesetup` or `/welcome setup` to create a new one.")],
            view=None,
        )


class Welcome(commands.Cog):

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    welcome_group = app_commands.Group(
        name="welcome",
        description="Welcome system commands",
        default_permissions=discord.Permissions(administrator=True),
        guild_only=True,
    )

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        data = _load()
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

    # ── Prefix commands ────────────────────────────────────────────────────────

    @commands.command(name="welcomesetup")
    @commands.has_permissions(administrator=True)
    @commands.guild_only()
    async def welcomesetup(self, ctx: commands.Context):
        data   = _load()
        config = data.get(str(ctx.guild.id), {})
        view   = SetupView(self, ctx, config)
        view.msg = await ctx.send(
            embeds=[view._panel_embed(), view._preview_embed()],
            view=view,
        )

    @commands.command(name="welcomechannel")
    @commands.has_permissions(administrator=True)
    @commands.guild_only()
    async def welcomechannel(self, ctx: commands.Context, channel: discord.TextChannel):
        data = _load()
        cfg  = data.setdefault(str(ctx.guild.id), {})
        cfg["channel_id"] = channel.id
        _save(data)
        await ctx.send(embed=success_embed(
            f"Welcome channel set to {channel.mention}!\n"
            f"Run `?welcomesetup` to customise the embed."
        ))

    @commands.command(name="welcomeconfig")
    @commands.has_permissions(administrator=True)
    @commands.guild_only()
    async def welcomeconfig(self, ctx: commands.Context):
        data = _load()
        cfg  = data.get(str(ctx.guild.id))

        if not cfg:
            await ctx.send(embed=error_embed("No welcome setup found.\nRun `?welcomesetup` to create one."))
            return

        ch    = f"<#{cfg['channel_id']}>" if cfg.get("channel_id") else "`not set`"
        desc  = cfg.get("description", "not set")
        thumb = cfg.get("thumbnail_url") or ("avatar" if cfg.get("show_thumbnail", True) else "off")
        img   = cfg.get("image_url")     or ("banner" if cfg.get("show_banner") else "off")
        ping  = "✅ on" if cfg.get("ping_on_join",  False) else "❌ off"
        dm    = "✅ on" if cfg.get("dm_on_join",    False) else "❌ off"
        ts    = "✅ on" if cfg.get("show_timestamp", True) else "❌ off"

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

        view = ConfigView(self, ctx, cfg)
        await ctx.send(
            embeds=[
                make_embed(
                    title="📋  Welcome Config",
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
        data = _load()
        cfg  = data.get(str(ctx.guild.id))

        if not cfg:
            await ctx.send(embed=error_embed(
                "No welcome setup found.\nRun `?welcomesetup` to create one."
            ))
            return

        embed = build_welcome_embed(cfg, ctx.author, ctx.guild)
        ping  = ctx.author.mention if cfg.get("ping_on_join", False) else None
        await ctx.send(content=ping, embed=embed)

    # ── Slash commands ─────────────────────────────────────────────────────────

    @welcome_group.command(name="setup", description="Open the interactive welcome setup panel")
    @app_commands.checks.has_permissions(administrator=True)
    async def slash_welcomesetup(self, interaction: discord.Interaction):
        data   = _load()
        config = data.get(str(interaction.guild.id), {})
        ctx    = _FakeCtx(interaction)
        view   = SetupView(self, ctx, config)
        await interaction.response.send_message(
            embeds=[view._panel_embed(), view._preview_embed()],
            view=view,
        )

    @welcome_group.command(name="channel", description="Set the channel where welcome messages are sent")
    @app_commands.describe(channel="The text channel to send welcome messages in")
    @app_commands.checks.has_permissions(administrator=True)
    async def slash_welcomechannel(self, interaction: discord.Interaction, channel: discord.TextChannel):
        data = _load()
        cfg  = data.setdefault(str(interaction.guild.id), {})
        cfg["channel_id"] = channel.id
        _save(data)
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
        data = _load()
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
        ping  = "✅ on" if cfg.get("ping_on_join",  False) else "❌ off"
        dm    = "✅ on" if cfg.get("dm_on_join",    False) else "❌ off"
        ts    = "✅ on" if cfg.get("show_timestamp", True) else "❌ off"

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
        view = ConfigView(self, ctx, cfg)
        await interaction.response.send_message(
            embeds=[
                make_embed(
                    title="📋  Welcome Config",
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
        data = _load()
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


async def setup(bot: commands.Bot):
    await bot.add_cog(Welcome(bot))

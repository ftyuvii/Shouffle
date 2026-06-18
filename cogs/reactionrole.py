"""
reactionrole.py  —  Shouffle Bot
Carl Bot / Dyno-style reaction role system.

Panel Modes
───────────
  normal     — toggle: react to get, unreact to remove  (default)
  unique     — only one role from this panel at a time (radio button)
  verify     — react to get, cannot remove by unreacting
  reversed   — react to REMOVE a role you already have
  binding    — react to get, role is permanent (no removal ever)

Commands
────────
  Prefix  │ Slash          │ Description
  ────────┼────────────────┼──────────────────────────────────────
  ?rr     │ /rr            │ Help overview
  ?rr create │ /rr create  │ Create a new panel
  ?rr add    │ /rr add     │ Add emoji→role entry to a panel
  ?rr remove │ /rr remove  │ Remove an emoji→role entry
  ?rr edit   │ /rr edit    │ Edit panel title / description / mode
  ?rr delete │ /rr delete  │ Delete a panel entirely
  ?rr list   │ /rr list    │ List all panels in this server
  ?rr info   │ /rr info    │ Show full details of one panel
  ?rr limit  │ /rr limit   │ Set max roles a user can pick from a panel
  ?rr dm     │ /rr dm      │ Toggle DM notifications for a panel
"""

from __future__ import annotations

import asyncio
import os
from typing import Optional

import aiosqlite
import discord
from discord import app_commands
from discord.ext import commands

# ─────────────────────────────────────────────────────────────────────────────
# Constants
# ─────────────────────────────────────────────────────────────────────────────

DB_PATH = "shouffle.db"

PINK    = 0xFF69B4
RED     = 0xFF4444
GREEN   = 0x57F287
YELLOW  = 0xFEE75C
DARK    = 0x2B2D31

MODES = ["normal", "unique", "verify", "reversed", "binding"]

MODE_DESC = {
    "normal":   "React to get a role, unreact to remove it.",
    "unique":   "Only one role from this panel at a time (radio button style).",
    "verify":   "React to get a role — unreacting does **not** remove it.",
    "reversed": "React to **remove** a role you already have.",
    "binding":  "React to get a role permanently — it can never be removed via reactions.",
}

# ─────────────────────────────────────────────────────────────────────────────
# Database
# ─────────────────────────────────────────────────────────────────────────────

async def init_db() -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.executescript("""
            CREATE TABLE IF NOT EXISTS rr_panels (
                guild_id    INTEGER NOT NULL,
                channel_id  INTEGER NOT NULL,
                message_id  INTEGER NOT NULL,
                title       TEXT    NOT NULL,
                description TEXT    DEFAULT '',
                mode        TEXT    NOT NULL DEFAULT 'normal',
                max_roles   INTEGER NOT NULL DEFAULT 0,
                dm_notify   INTEGER NOT NULL DEFAULT 0,
                PRIMARY KEY (guild_id, message_id)
            );

            CREATE TABLE IF NOT EXISTS rr_entries (
                guild_id    INTEGER NOT NULL,
                message_id  INTEGER NOT NULL,
                emoji       TEXT    NOT NULL,
                role_id     INTEGER NOT NULL,
                label       TEXT    DEFAULT '',
                PRIMARY KEY (guild_id, message_id, emoji)
            );
        """)
        await db.commit()


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def admin_only():
    async def predicate(ctx: commands.Context) -> bool:
        if not ctx.author.guild_permissions.administrator:
            raise commands.MissingPermissions(["administrator"])
        return True
    return commands.check(predicate)


def err_embed(title: str, desc: str) -> discord.Embed:
    return discord.Embed(title=f"✗  {title}", description=desc, color=RED)


def ok_embed(title: str, desc: str) -> discord.Embed:
    return discord.Embed(title=f"✓  {title}", description=desc, color=GREEN)


def info_embed(title: str, desc: str) -> discord.Embed:
    return discord.Embed(title=title, description=desc, color=PINK)


async def fetch_panel(guild_id: int, message_id: int) -> Optional[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM rr_panels WHERE guild_id = ? AND message_id = ?",
            (guild_id, message_id),
        ) as cur:
            row = await cur.fetchone()
    return dict(row) if row else None


async def fetch_entries(guild_id: int, message_id: int) -> list[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM rr_entries WHERE guild_id = ? AND message_id = ? ORDER BY rowid",
            (guild_id, message_id),
        ) as cur:
            rows = await cur.fetchall()
    return [dict(r) for r in rows]


async def fetch_all_panels(guild_id: int) -> list[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM rr_panels WHERE guild_id = ? ORDER BY message_id",
            (guild_id,),
        ) as cur:
            rows = await cur.fetchall()
    return [dict(r) for r in rows]


def build_panel_embed(panel: dict, entries: list[dict]) -> discord.Embed:
    embed = discord.Embed(title=panel["title"], color=PINK)

    if panel.get("description"):
        embed.description = panel["description"]

    mode = panel.get("mode", "normal")
    mode_tag = {
        "normal":   "🔄  Normal",
        "unique":   "🔘  Unique  (one role at a time)",
        "verify":   "✅  Verify  (react to keep)",
        "reversed": "🔁  Reversed  (react to remove)",
        "binding":  "🔒  Binding  (permanent)",
    }.get(mode, mode.capitalize())

    if entries:
        lines = []
        for e in entries:
            label = f"  —  {e['label']}" if e.get("label") else ""
            lines.append(f"{e['emoji']}  →  <@&{e['role_id']}>{label}")
        embed.add_field(name="Roles", value="\n".join(lines), inline=False)
    else:
        embed.add_field(name="Roles", value="*No roles added yet.*", inline=False)

    if panel.get("max_roles", 0) > 0:
        embed.add_field(name="Limit", value=f"Max **{panel['max_roles']}** role(s) per user", inline=True)

    embed.add_field(name="Mode", value=mode_tag, inline=True)
    embed.set_footer(text="React to a emoji below to receive your role.")
    return embed


# ─────────────────────────────────────────────────────────────────────────────
# Confirm View  (used for destructive actions)
# ─────────────────────────────────────────────────────────────────────────────

class ConfirmView(discord.ui.View):
    def __init__(self, author_id: int):
        super().__init__(timeout=30)
        self.author_id = author_id
        self.value: Optional[bool] = None

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.author_id:
            await interaction.response.send_message("Not your confirmation.", ephemeral=True)
            return False
        return True

    @discord.ui.button(label="Confirm", style=discord.ButtonStyle.danger)
    async def confirm(self, interaction: discord.Interaction, _: discord.ui.Button):
        self.value = True
        self.stop()
        await interaction.response.defer()

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.secondary)
    async def cancel(self, interaction: discord.Interaction, _: discord.ui.Button):
        self.value = False
        self.stop()
        await interaction.response.defer()


# ─────────────────────────────────────────────────────────────────────────────
# Core Logic  (shared between prefix & slash)
# ─────────────────────────────────────────────────────────────────────────────

class RRCore:
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def _get_panel_message(
        self, guild: discord.Guild, panel: dict
    ) -> Optional[discord.Message]:
        channel = guild.get_channel(panel["channel_id"])
        if not channel:
            return None
        try:
            return await channel.fetch_message(panel["message_id"])
        except (discord.NotFound, discord.Forbidden):
            return None

    async def refresh_panel(self, guild: discord.Guild, message_id: int) -> None:
        panel = await fetch_panel(guild.id, message_id)
        if not panel:
            return
        entries = await fetch_entries(guild.id, message_id)
        msg = await self._get_panel_message(guild, panel)
        if msg:
            await msg.edit(embed=build_panel_embed(panel, entries))

    # ── create ────────────────────────────────────────────────────

    async def create(
        self,
        guild: discord.Guild,
        channel: discord.TextChannel,
        title: str,
        description: str,
        mode: str,
        send,
    ) -> None:
        if mode not in MODES:
            await send(embed=err_embed("Invalid Mode", f"Mode must be one of: {', '.join(f'`{m}`' for m in MODES)}"), ephemeral=True)
            return

        embed = build_panel_embed(
            {"title": title, "description": description, "mode": mode, "max_roles": 0},
            [],
        )
        try:
            panel_msg = await channel.send(embed=embed)
        except discord.Forbidden:
            await send(embed=err_embed("No Permission", f"I can't send messages in {channel.mention}."), ephemeral=True)
            return

        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                """INSERT OR REPLACE INTO rr_panels
                   (guild_id, channel_id, message_id, title, description, mode, max_roles, dm_notify)
                   VALUES (?,?,?,?,?,?,0,0)""",
                (guild.id, channel.id, panel_msg.id, title, description, mode),
            )
            await db.commit()

        confirm = ok_embed(
            "Panel Created",
            (
                f"Panel posted in {channel.mention}\n"
                f"**Message ID:** `{panel_msg.id}`\n"
                f"**Mode:** `{mode}`\n\n"
                f"Add roles with:\n"
                f"`?rr add {panel_msg.id} <emoji> <@role>`\n"
                f"or  `/rr add`"
            ),
        )
        await send(embed=confirm)

    # ── add entry ─────────────────────────────────────────────────

    async def add_entry(
        self,
        guild: discord.Guild,
        message_id: int,
        emoji: str,
        role: discord.Role,
        label: str,
        send,
    ) -> None:
        panel = await fetch_panel(guild.id, message_id)
        if not panel:
            await send(embed=err_embed("Panel Not Found", f"No panel with ID `{message_id}`. Use `?rr list` to see all panels."), ephemeral=True)
            return

        if role.managed or role >= guild.me.top_role:
            await send(embed=err_embed("Role Hierarchy", f"{role.mention} is above my highest role or is managed. I can't assign it."), ephemeral=True)
            return

        entries = await fetch_entries(guild.id, message_id)
        if any(e["emoji"] == emoji for e in entries):
            await send(embed=err_embed("Duplicate Emoji", f"{emoji} is already used on this panel."), ephemeral=True)
            return
        if any(e["role_id"] == role.id for e in entries):
            await send(embed=err_embed("Duplicate Role", f"{role.mention} is already on this panel."), ephemeral=True)
            return
        if len(entries) >= 20:
            await send(embed=err_embed("Panel Full", "A panel can have a maximum of **20** entries (Discord reaction limit)."), ephemeral=True)
            return

        channel = guild.get_channel(panel["channel_id"])
        if not channel:
            await send(embed=err_embed("Channel Not Found", "The panel's channel no longer exists."), ephemeral=True)
            return

        try:
            msg = await channel.fetch_message(message_id)
            await msg.add_reaction(emoji)
        except discord.HTTPException as exc:
            await send(embed=err_embed("Invalid Emoji", f"Could not react with that emoji.\n```{exc}```"), ephemeral=True)
            return

        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                "INSERT OR REPLACE INTO rr_entries (guild_id, message_id, emoji, role_id, label) VALUES (?,?,?,?,?)",
                (guild.id, message_id, emoji, role.id, label),
            )
            await db.commit()

        await self.refresh_panel(guild, message_id)
        await send(embed=ok_embed("Entry Added", f"{emoji}  →  {role.mention}" + (f"\nLabel: *{label}*" if label else "")))

    # ── remove entry ──────────────────────────────────────────────

    async def remove_entry(
        self, guild: discord.Guild, message_id: int, emoji: str, send
    ) -> None:
        panel = await fetch_panel(guild.id, message_id)
        if not panel:
            await send(embed=err_embed("Panel Not Found", f"No panel with ID `{message_id}`."), ephemeral=True)
            return

        entries = await fetch_entries(guild.id, message_id)
        entry = next((e for e in entries if e["emoji"] == emoji), None)
        if not entry:
            await send(embed=err_embed("Not Found", f"{emoji} is not on panel `{message_id}`."), ephemeral=True)
            return

        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                "DELETE FROM rr_entries WHERE guild_id = ? AND message_id = ? AND emoji = ?",
                (guild.id, message_id, emoji),
            )
            await db.commit()

        channel = guild.get_channel(panel["channel_id"])
        if channel:
            try:
                msg = await channel.fetch_message(message_id)
                await msg.clear_reaction(emoji)
            except (discord.NotFound, discord.HTTPException):
                pass

        await self.refresh_panel(guild, message_id)
        await send(embed=ok_embed("Entry Removed", f"{emoji}  →  <@&{entry['role_id']}> removed from panel `{message_id}`."))

    # ── edit panel ────────────────────────────────────────────────

    async def edit_panel(
        self,
        guild: discord.Guild,
        message_id: int,
        title: Optional[str],
        description: Optional[str],
        mode: Optional[str],
        send,
    ) -> None:
        panel = await fetch_panel(guild.id, message_id)
        if not panel:
            await send(embed=err_embed("Panel Not Found", f"No panel with ID `{message_id}`."), ephemeral=True)
            return

        if mode and mode not in MODES:
            await send(embed=err_embed("Invalid Mode", f"Mode must be one of: {', '.join(f'`{m}`' for m in MODES)}"), ephemeral=True)
            return

        new_title = title or panel["title"]
        new_desc  = description if description is not None else panel["description"]
        new_mode  = mode or panel["mode"]

        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                "UPDATE rr_panels SET title=?, description=?, mode=? WHERE guild_id=? AND message_id=?",
                (new_title, new_desc, new_mode, guild.id, message_id),
            )
            await db.commit()

        await self.refresh_panel(guild, message_id)
        await send(embed=ok_embed("Panel Updated", f"Panel `{message_id}` updated.\n**Title:** {new_title}\n**Mode:** `{new_mode}`"))

    # ── set limit ─────────────────────────────────────────────────

    async def set_limit(
        self, guild: discord.Guild, message_id: int, limit: int, send
    ) -> None:
        panel = await fetch_panel(guild.id, message_id)
        if not panel:
            await send(embed=err_embed("Panel Not Found", f"No panel with ID `{message_id}`."), ephemeral=True)
            return

        if limit < 0:
            await send(embed=err_embed("Invalid Limit", "Limit must be 0 (unlimited) or a positive number."), ephemeral=True)
            return

        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                "UPDATE rr_panels SET max_roles=? WHERE guild_id=? AND message_id=?",
                (limit, guild.id, message_id),
            )
            await db.commit()

        await self.refresh_panel(guild, message_id)
        desc = f"Users can now pick **{limit}** role(s) from panel `{message_id}`." if limit > 0 else f"No role limit on panel `{message_id}`."
        await send(embed=ok_embed("Limit Updated", desc))

    # ── toggle DM ─────────────────────────────────────────────────

    async def toggle_dm(
        self, guild: discord.Guild, message_id: int, send
    ) -> None:
        panel = await fetch_panel(guild.id, message_id)
        if not panel:
            await send(embed=err_embed("Panel Not Found", f"No panel with ID `{message_id}`."), ephemeral=True)
            return

        new_val = 0 if panel["dm_notify"] else 1
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                "UPDATE rr_panels SET dm_notify=? WHERE guild_id=? AND message_id=?",
                (new_val, guild.id, message_id),
            )
            await db.commit()

        state = "**enabled**" if new_val else "**disabled**"
        await send(embed=ok_embed("DM Notifications", f"DM notifications {state} for panel `{message_id}`."))

    # ── delete panel ──────────────────────────────────────────────

    async def delete_panel(
        self, guild: discord.Guild, message_id: int, author_id: int, send_confirm, send_result
    ) -> None:
        panel = await fetch_panel(guild.id, message_id)
        if not panel:
            await send_result(embed=err_embed("Panel Not Found", f"No panel with ID `{message_id}`."), ephemeral=True)
            return

        view = ConfirmView(author_id)
        confirm_embed = discord.Embed(
            title="⚠  Delete Panel?",
            description=(
                f"This will permanently delete panel `{message_id}` (**{panel['title']}**) "
                f"and all its entries.\n\nThis action **cannot** be undone."
            ),
            color=YELLOW,
        )
        msg = await send_confirm(embed=confirm_embed, view=view)
        await view.wait()

        if not view.value:
            await msg.edit(embed=info_embed("Cancelled", "Panel deletion cancelled."), view=None)
            return

        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("DELETE FROM rr_panels  WHERE guild_id=? AND message_id=?", (guild.id, message_id))
            await db.execute("DELETE FROM rr_entries WHERE guild_id=? AND message_id=?", (guild.id, message_id))
            await db.commit()

        channel = guild.get_channel(panel["channel_id"])
        if channel:
            try:
                pm = await channel.fetch_message(message_id)
                await pm.delete()
            except (discord.NotFound, discord.HTTPException):
                pass

        await msg.edit(embed=ok_embed("Panel Deleted", f"Panel `{message_id}` (**{panel['title']}**) has been deleted."), view=None)

    # ── list panels ───────────────────────────────────────────────

    async def list_panels(self, guild: discord.Guild, send) -> None:
        panels = await fetch_all_panels(guild.id)
        if not panels:
            await send(embed=info_embed("No Panels", "This server has no reaction role panels yet.\nCreate one with `?rr create` or `/rr create`."))
            return

        embed = discord.Embed(title="Reaction Role Panels", color=PINK)
        embed.set_footer(text=f"{len(panels)} panel(s) in this server")

        for p in panels:
            channel = guild.get_channel(p["channel_id"])
            ch_str  = channel.mention if channel else f"<#{p['channel_id']}> *(deleted)*"
            entries = await fetch_entries(guild.id, p["message_id"])
            embed.add_field(
                name=f"{p['title']}  —  `{p['message_id']}`",
                value=(
                    f"Channel: {ch_str}\n"
                    f"Mode: `{p['mode']}`  •  Entries: `{len(entries)}`"
                    + (f"  •  Max: `{p['max_roles']}`" if p["max_roles"] > 0 else "")
                    + (f"  •  DM: on" if p["dm_notify"] else "")
                ),
                inline=False,
            )
        await send(embed=embed)

    # ── panel info ────────────────────────────────────────────────

    async def panel_info(self, guild: discord.Guild, message_id: int, send) -> None:
        panel = await fetch_panel(guild.id, message_id)
        if not panel:
            await send(embed=err_embed("Panel Not Found", f"No panel with ID `{message_id}`."), ephemeral=True)
            return

        entries = await fetch_entries(guild.id, message_id)
        channel = guild.get_channel(panel["channel_id"])
        ch_str  = channel.mention if channel else f"<#{panel['channel_id']}> *(deleted)*"

        embed = discord.Embed(title=f"Panel Info  —  {panel['title']}", color=PINK)
        embed.add_field(name="Channel",     value=ch_str,              inline=True)
        embed.add_field(name="Message ID",  value=f"`{message_id}`",   inline=True)
        embed.add_field(name="Mode",        value=f"`{panel['mode']}`", inline=True)
        embed.add_field(name="Max Roles",   value=panel["max_roles"] or "Unlimited", inline=True)
        embed.add_field(name="DM Notify",   value="On" if panel["dm_notify"] else "Off", inline=True)
        embed.add_field(name="Entries",     value=str(len(entries)), inline=True)

        if entries:
            lines = [f"{e['emoji']}  →  <@&{e['role_id']}>" + (f"  *('{e['label']}')*" if e.get("label") else "") for e in entries]
            embed.add_field(name="Role Entries", value="\n".join(lines), inline=False)

        embed.add_field(name="Mode Info", value=MODE_DESC.get(panel["mode"], ""), inline=False)
        await send(embed=embed)


# ─────────────────────────────────────────────────────────────────────────────
# Cog
# ─────────────────────────────────────────────────────────────────────────────

class ReactionRole(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.core = RRCore(bot)
        asyncio.get_event_loop().create_task(init_db())

    # ── Reaction listeners ────────────────────────────────────────

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload: discord.RawReactionActionEvent):
        if not payload.guild_id or payload.user_id == self.bot.user.id:
            return

        emoji = str(payload.emoji)
        panel = await fetch_panel(payload.guild_id, payload.message_id)
        if not panel:
            return

        entries = await fetch_entries(payload.guild_id, payload.message_id)
        entry   = next((e for e in entries if e["emoji"] == emoji), None)
        if not entry:
            return

        guild  = self.bot.get_guild(payload.guild_id)
        if not guild:
            return
        member = guild.get_member(payload.user_id) or await guild.fetch_member(payload.user_id)
        if not member or member.bot:
            return

        role = guild.get_role(entry["role_id"])
        if not role:
            return

        mode = panel["mode"]

        # reversed: react removes the role
        if mode == "reversed":
            if role in member.roles:
                try:
                    await member.remove_roles(role, reason="Reaction Role (reversed)")
                    await self._dm(member, panel, role, added=False)
                except discord.Forbidden:
                    pass
            return

        # unique: remove all other panel roles first
        if mode == "unique":
            other_role_ids = {e["role_id"] for e in entries if e["emoji"] != emoji}
            roles_to_remove = [guild.get_role(rid) for rid in other_role_ids if guild.get_role(rid) in member.roles]
            if roles_to_remove:
                try:
                    await member.remove_roles(*roles_to_remove, reason="Reaction Role (unique — replaced)")
                except discord.Forbidden:
                    pass

        # max_roles check
        max_r = panel.get("max_roles", 0)
        if max_r > 0 and mode not in ("unique",):
            panel_role_ids = {e["role_id"] for e in entries}
            current_count  = sum(1 for r in member.roles if r.id in panel_role_ids)
            if current_count >= max_r and role not in member.roles:
                channel = guild.get_channel(panel["channel_id"])
                if channel:
                    try:
                        msg = await channel.fetch_message(payload.message_id)
                        await msg.remove_reaction(payload.emoji, member)
                    except (discord.NotFound, discord.HTTPException, discord.Forbidden):
                        pass
                return

        if role not in member.roles:
            try:
                await member.add_roles(role, reason=f"Reaction Role ({mode})")
                await self._dm(member, panel, role, added=True)
            except discord.Forbidden:
                pass

    @commands.Cog.listener()
    async def on_raw_reaction_remove(self, payload: discord.RawReactionActionEvent):
        if not payload.guild_id or payload.user_id == self.bot.user.id:
            return

        emoji = str(payload.emoji)
        panel = await fetch_panel(payload.guild_id, payload.message_id)
        if not panel:
            return

        mode = panel["mode"]
        if mode in ("verify", "binding", "reversed"):
            return

        entries = await fetch_entries(payload.guild_id, payload.message_id)
        entry   = next((e for e in entries if e["emoji"] == emoji), None)
        if not entry:
            return

        guild  = self.bot.get_guild(payload.guild_id)
        if not guild:
            return
        member = guild.get_member(payload.user_id) or await guild.fetch_member(payload.user_id)
        if not member or member.bot:
            return

        role = guild.get_role(entry["role_id"])
        if not role:
            return

        if role in member.roles:
            try:
                await member.remove_roles(role, reason=f"Reaction Role removed ({mode})")
                await self._dm(member, panel, role, added=False)
            except discord.Forbidden:
                pass

    async def _dm(self, member: discord.Member, panel: dict, role: discord.Role, added: bool) -> None:
        if not panel.get("dm_notify"):
            return
        action = "assigned" if added else "removed"
        color  = GREEN if added else RED
        embed  = discord.Embed(
            title=f"Role {action.capitalize()}",
            description=f"The role **{role.name}** has been **{action}** in **{member.guild.name}**.",
            color=color,
        )
        embed.set_footer(text=f"Panel: {panel['title']}")
        try:
            await member.send(embed=embed)
        except (discord.Forbidden, discord.HTTPException):
            pass

    # ─────────────────────────────────────────────────────────────
    # PREFIX COMMANDS
    # ─────────────────────────────────────────────────────────────

    @commands.group(name="rr", invoke_without_command=True)
    @admin_only()
    async def rr(self, ctx: commands.Context):
        embed = discord.Embed(title="Reaction Roles — Command Reference", color=PINK)
        embed.description = (
            "**Setup**\n"
            "`?rr create <#channel> <mode> <title>` — Create a panel\n"
            "`?rr add <id> <emoji> <@role> [label]` — Add a role entry\n"
            "`?rr remove <id> <emoji>` — Remove a role entry\n"
            "`?rr edit <id> [title] [desc] [mode]` — Edit panel settings\n"
            "`?rr limit <id> <number>` — Max roles per user (0 = unlimited)\n"
            "`?rr dm <id>` — Toggle DM notifications\n\n"
            "**Management**\n"
            "`?rr delete <id>` — Delete a panel\n"
            "`?rr list` — List all panels\n"
            "`?rr info <id>` — Detailed panel info\n\n"
            "**Modes:** `normal` `unique` `verify` `reversed` `binding`"
        )
        embed.set_footer(text="Only Administrators can use these commands.")
        await ctx.send(embed=embed)

    @rr.command(name="create")
    @admin_only()
    async def rr_create(self, ctx: commands.Context, channel: discord.TextChannel, mode: str, *, title: str):
        await self.core.create(ctx.guild, channel, title, "", mode, ctx.send)

    @rr.command(name="add")
    @admin_only()
    async def rr_add(self, ctx: commands.Context, message_id: int, emoji: str, role: discord.Role, *, label: str = ""):
        await self.core.add_entry(ctx.guild, message_id, emoji, role, label, ctx.send)

    @rr.command(name="remove")
    @admin_only()
    async def rr_remove(self, ctx: commands.Context, message_id: int, emoji: str):
        await self.core.remove_entry(ctx.guild, message_id, emoji, ctx.send)

    @rr.command(name="edit")
    @admin_only()
    async def rr_edit(self, ctx: commands.Context, message_id: int, title: Optional[str] = None, description: Optional[str] = None, mode: Optional[str] = None):
        await self.core.edit_panel(ctx.guild, message_id, title, description, mode, ctx.send)

    @rr.command(name="limit")
    @admin_only()
    async def rr_limit(self, ctx: commands.Context, message_id: int, limit: int):
        await self.core.set_limit(ctx.guild, message_id, limit, ctx.send)

    @rr.command(name="dm")
    @admin_only()
    async def rr_dm(self, ctx: commands.Context, message_id: int):
        await self.core.toggle_dm(ctx.guild, message_id, ctx.send)

    @rr.command(name="delete")
    @admin_only()
    async def rr_delete(self, ctx: commands.Context, message_id: int):
        async def send_confirm(**kw):
            return await ctx.send(**kw)
        await self.core.delete_panel(ctx.guild, message_id, ctx.author.id, send_confirm, ctx.send)

    @rr.command(name="list")
    @admin_only()
    async def rr_list(self, ctx: commands.Context):
        await self.core.list_panels(ctx.guild, ctx.send)

    @rr.command(name="info")
    @admin_only()
    async def rr_info(self, ctx: commands.Context, message_id: int):
        await self.core.panel_info(ctx.guild, message_id, ctx.send)

    # ─────────────────────────────────────────────────────────────
    # PREFIX ERROR HANDLER
    # ─────────────────────────────────────────────────────────────

    @rr.error
    async def rr_error(self, ctx: commands.Context, error):
        if isinstance(error, commands.CheckFailure):
            await ctx.send(embed=err_embed("Access Denied", "You need **Administrator** to manage reaction roles."))
        elif isinstance(error, commands.MissingRequiredArgument):
            await ctx.send(embed=err_embed("Missing Argument", f"`{error.param.name}` is required. Use `?rr` for help."))
        elif isinstance(error, commands.BadArgument):
            await ctx.send(embed=err_embed("Bad Argument", str(error)))
        elif isinstance(error, commands.ChannelNotFound):
            await ctx.send(embed=err_embed("Channel Not Found", "That channel doesn't exist or I can't see it."))
        elif isinstance(error, commands.RoleNotFound):
            await ctx.send(embed=err_embed("Role Not Found", "That role doesn't exist."))

    # ─────────────────────────────────────────────────────────────
    # SLASH COMMANDS
    # ─────────────────────────────────────────────────────────────

    rr_slash = app_commands.Group(
        name="rr",
        description="Reaction role management — Admin only",
        default_permissions=discord.Permissions(administrator=True),
    )

    @rr_slash.command(name="create", description="Create a new reaction role panel")
    @app_commands.describe(
        channel="Channel to post the panel in",
        mode="Panel behaviour mode",
        title="Panel title shown in the embed",
        description="Optional panel description",
    )
    @app_commands.choices(mode=[app_commands.Choice(name=m, value=m) for m in MODES])
    async def slash_create(
        self,
        interaction: discord.Interaction,
        channel: discord.TextChannel,
        title: str,
        mode: app_commands.Choice[str] = None,
        description: Optional[str] = "",
    ):
        await interaction.response.defer(ephemeral=True)
        chosen_mode = mode.value if mode else "normal"
        await self.core.create(interaction.guild, channel, title, description or "", chosen_mode,
                               lambda **kw: interaction.followup.send(**kw))

    @rr_slash.command(name="add", description="Add an emoji → role entry to a panel")
    @app_commands.describe(
        message_id="Message ID of the panel",
        emoji="Emoji users react with",
        role="Role to assign",
        label="Optional short label shown beside the role",
    )
    async def slash_add(
        self,
        interaction: discord.Interaction,
        message_id: str,
        emoji: str,
        role: discord.Role,
        label: Optional[str] = "",
    ):
        await interaction.response.defer(ephemeral=True)
        try:
            mid = int(message_id)
        except ValueError:
            await interaction.followup.send(embed=err_embed("Invalid ID", "Message ID must be a number."), ephemeral=True)
            return
        await self.core.add_entry(interaction.guild, mid, emoji, role, label or "",
                                  lambda **kw: interaction.followup.send(**kw))

    @rr_slash.command(name="remove", description="Remove an emoji → role entry from a panel")
    @app_commands.describe(message_id="Message ID of the panel", emoji="Emoji to remove")
    async def slash_remove(self, interaction: discord.Interaction, message_id: str, emoji: str):
        await interaction.response.defer(ephemeral=True)
        try:
            mid = int(message_id)
        except ValueError:
            await interaction.followup.send(embed=err_embed("Invalid ID", "Message ID must be a number."), ephemeral=True)
            return
        await self.core.remove_entry(interaction.guild, mid, emoji,
                                     lambda **kw: interaction.followup.send(**kw))

    @rr_slash.command(name="edit", description="Edit a panel's title, description or mode")
    @app_commands.describe(
        message_id="Message ID of the panel",
        title="New title (leave blank to keep current)",
        description="New description (leave blank to keep current)",
        mode="New mode",
    )
    @app_commands.choices(mode=[app_commands.Choice(name=m, value=m) for m in MODES])
    async def slash_edit(
        self,
        interaction: discord.Interaction,
        message_id: str,
        title: Optional[str] = None,
        description: Optional[str] = None,
        mode: app_commands.Choice[str] = None,
    ):
        await interaction.response.defer(ephemeral=True)
        try:
            mid = int(message_id)
        except ValueError:
            await interaction.followup.send(embed=err_embed("Invalid ID", "Message ID must be a number."), ephemeral=True)
            return
        await self.core.edit_panel(interaction.guild, mid, title, description, mode.value if mode else None,
                                   lambda **kw: interaction.followup.send(**kw))

    @rr_slash.command(name="limit", description="Set max roles a user can pick from a panel (0 = unlimited)")
    @app_commands.describe(message_id="Message ID of the panel", limit="Max roles (0 = unlimited)")
    async def slash_limit(self, interaction: discord.Interaction, message_id: str, limit: int):
        await interaction.response.defer(ephemeral=True)
        try:
            mid = int(message_id)
        except ValueError:
            await interaction.followup.send(embed=err_embed("Invalid ID", "Message ID must be a number."), ephemeral=True)
            return
        await self.core.set_limit(interaction.guild, mid, limit,
                                  lambda **kw: interaction.followup.send(**kw))

    @rr_slash.command(name="dm", description="Toggle DM notifications when users get/lose a role from this panel")
    @app_commands.describe(message_id="Message ID of the panel")
    async def slash_dm(self, interaction: discord.Interaction, message_id: str):
        await interaction.response.defer(ephemeral=True)
        try:
            mid = int(message_id)
        except ValueError:
            await interaction.followup.send(embed=err_embed("Invalid ID", "Message ID must be a number."), ephemeral=True)
            return
        await self.core.toggle_dm(interaction.guild, mid,
                                  lambda **kw: interaction.followup.send(**kw))

    @rr_slash.command(name="delete", description="Delete a reaction role panel entirely")
    @app_commands.describe(message_id="Message ID of the panel to delete")
    async def slash_delete(self, interaction: discord.Interaction, message_id: str):
        await interaction.response.defer(ephemeral=True)
        try:
            mid = int(message_id)
        except ValueError:
            await interaction.followup.send(embed=err_embed("Invalid ID", "Message ID must be a number."), ephemeral=True)
            return

        async def send_confirm(**kw):
            return await interaction.followup.send(**kw)

        await self.core.delete_panel(interaction.guild, mid, interaction.user.id, send_confirm, send_confirm)

    @rr_slash.command(name="list", description="List all reaction role panels in this server")
    async def slash_list(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        await self.core.list_panels(interaction.guild,
                                    lambda **kw: interaction.followup.send(**kw))

    @rr_slash.command(name="info", description="Show full details of a reaction role panel")
    @app_commands.describe(message_id="Message ID of the panel")
    async def slash_info(self, interaction: discord.Interaction, message_id: str):
        await interaction.response.defer(ephemeral=True)
        try:
            mid = int(message_id)
        except ValueError:
            await interaction.followup.send(embed=err_embed("Invalid ID", "Message ID must be a number."), ephemeral=True)
            return
        await self.core.panel_info(interaction.guild, mid,
                                   lambda **kw: interaction.followup.send(**kw))


# ─────────────────────────────────────────────────────────────────────────────
# Setup
# ─────────────────────────────────────────────────────────────────────────────

async def setup(bot: commands.Bot):
    cog = ReactionRole(bot)
    bot.tree.add_command(cog.rr_slash)
    await bot.add_cog(cog)

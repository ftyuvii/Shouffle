from __future__ import annotations

from typing import Optional

import aiosqlite
import discord
from discord import app_commands
from discord.ext import commands

DB_PATH = "shouffle.db"
PINK    = 0xFFB6C1
RED     = 0xFFBFEA
GREEN   = 0x57F287
YELLOW  = 0xFEE75C

PASTELSTAR = "🌟"
LEAF       = "🌿"

MODES = ["normal", "unique", "verify", "reversed", "binding"]

MODE_INFO = {
    "normal":   ("🔄", "Normal",   "React to get a role, unreact to remove it."),
    "unique":   ("🔘", "Unique",   "Only one role from this panel at a time."),
    "verify":   ("✅", "Verify",   "React to get a role — unreacting does NOT remove it."),
    "reversed": ("🔁", "Reversed", "React to REMOVE a role you already have."),
    "binding":  ("🔒", "Binding",  "React to get a role permanently — can never be removed."),
}


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
                guild_id   INTEGER NOT NULL,
                message_id INTEGER NOT NULL,
                emoji      TEXT    NOT NULL,
                role_id    INTEGER NOT NULL,
                label      TEXT    DEFAULT '',
                PRIMARY KEY (guild_id, message_id, emoji)
            );
            CREATE TABLE IF NOT EXISTS autorole (
                guild_id INTEGER PRIMARY KEY,
                role_id  INTEGER NOT NULL
            );
        """)
        await db.commit()


async def fetch_panel(guild_id: int, message_id: int) -> Optional[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM rr_panels WHERE guild_id=? AND message_id=?",
            (guild_id, message_id),
        ) as cur:
            row = await cur.fetchone()
    return dict(row) if row else None


async def fetch_entries(guild_id: int, message_id: int) -> list[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM rr_entries WHERE guild_id=? AND message_id=? ORDER BY rowid",
            (guild_id, message_id),
        ) as cur:
            rows = await cur.fetchall()
    return [dict(r) for r in rows]


async def fetch_all_panels(guild_id: int) -> list[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM rr_panels WHERE guild_id=? ORDER BY message_id",
            (guild_id,),
        ) as cur:
            rows = await cur.fetchall()
    return [dict(r) for r in rows]


async def fetch_autorole(guild_id: int) -> Optional[int]:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT role_id FROM autorole WHERE guild_id=?", (guild_id,)
        ) as cur:
            row = await cur.fetchone()
    return row[0] if row else None


def build_panel_embed(panel: dict, entries: list[dict]) -> discord.Embed:
    embed = discord.Embed(title=panel["title"], color=PINK)
    if panel.get("description"):
        embed.description = panel["description"]

    mode = panel.get("mode", "normal")
    icon, label, _ = MODE_INFO.get(mode, ("🔄", mode.capitalize(), ""))
    mode_tag = f"{icon}  {label}"

    if entries:
        lines = []
        for e in entries:
            suffix = f"  —  *{e['label']}*" if e.get("label") else ""
            lines.append(f"{e['emoji']}  →  <@&{e['role_id']}>{suffix}")
        embed.add_field(name=f"{PASTELSTAR} Roles", value="\n".join(lines), inline=False)
    else:
        embed.add_field(name=f"{PASTELSTAR} Roles", value="*No roles added yet.*", inline=False)

    if panel.get("max_roles", 0) > 0:
        embed.add_field(name="Limit", value=f"Max **{panel['max_roles']}** role(s) per user", inline=True)

    embed.add_field(name="Mode", value=mode_tag, inline=True)
    embed.set_footer(text="Raze Developments • Shouffle")
    return embed


def err_embed(title: str, desc: str) -> discord.Embed:
    return discord.Embed(title=f"✗  {title}", description=desc, color=RED)


def ok_embed(title: str, desc: str) -> discord.Embed:
    return discord.Embed(title=f"✓  {title}", description=desc, color=GREEN)


def info_embed(title: str, desc: str) -> discord.Embed:
    return discord.Embed(title=f"{PASTELSTAR}  {title}", description=desc, color=PINK)


async def _refresh_panel_message(bot: commands.Bot, guild: discord.Guild, message_id: int) -> None:
    panel = await fetch_panel(guild.id, message_id)
    if not panel:
        return
    channel = guild.get_channel(panel["channel_id"])
    if not channel:
        return
    try:
        msg = await channel.fetch_message(message_id)
        entries = await fetch_entries(guild.id, message_id)
        await msg.edit(embed=build_panel_embed(panel, entries))
    except (discord.NotFound, discord.Forbidden):
        pass


async def _dm_member(member: discord.Member, panel: dict, role: discord.Role, added: bool) -> None:
    if not panel.get("dm_notify"):
        return
    action = "assigned" if added else "removed"
    embed = discord.Embed(
        title=f"Role {action.capitalize()}",
        description=f"The role **{role.name}** has been **{action}** in **{member.guild.name}**.",
        color=GREEN if added else RED,
    )
    embed.set_footer(text=f"Panel: {panel['title']}")
    try:
        await member.send(embed=embed)
    except (discord.Forbidden, discord.HTTPException):
        pass


class PanelTitleModal(discord.ui.Modal, title="Panel Details"):
    panel_title = discord.ui.TextInput(
        label="Panel Title",
        placeholder="e.g. Pick Your Roles",
        max_length=100,
    )
    panel_desc = discord.ui.TextInput(
        label="Panel Description (optional)",
        placeholder="e.g. React below to choose your roles!",
        required=False,
        style=discord.TextStyle.paragraph,
        max_length=300,
    )

    def __init__(self, view: SetupView):
        super().__init__()
        self.setup_view = view

    async def on_submit(self, interaction: discord.Interaction):
        self.setup_view.panel_title = self.panel_title.value.strip()
        self.setup_view.panel_desc  = (self.panel_desc.value or "").strip()
        await interaction.response.edit_message(
            embed=self.setup_view.build_progress_embed(),
            view=self.setup_view,
        )


class AddEntryModal(discord.ui.Modal, title="Add Role Entry"):
    emoji_input = discord.ui.TextInput(
        label="Emoji",
        placeholder="e.g. 🎮 or <:custom:123456789>",
        max_length=100,
    )
    role_input = discord.ui.TextInput(
        label="Role ID",
        placeholder="Right-click a role → Copy ID",
        max_length=20,
    )
    label_input = discord.ui.TextInput(
        label="Label (optional)",
        placeholder="e.g. Gamer, Artist …",
        required=False,
        max_length=50,
    )

    def __init__(self, view: SetupView):
        super().__init__()
        self.setup_view = view

    async def on_submit(self, interaction: discord.Interaction):
        emoji = self.emoji_input.value.strip()
        label = (self.label_input.value or "").strip()

        try:
            role_id = int(self.role_input.value.strip())
        except ValueError:
            await interaction.response.send_message(
                embed=err_embed("Invalid Role ID", "Role ID must be a number. Enable Dev Mode → right-click role → Copy ID."),
                ephemeral=True,
            )
            return

        role = interaction.guild.get_role(role_id)
        if not role:
            await interaction.response.send_message(
                embed=err_embed("Role Not Found", f"No role with ID `{role_id}` found in this server."),
                ephemeral=True,
            )
            return

        if role.managed or role >= interaction.guild.me.top_role:
            await interaction.response.send_message(
                embed=err_embed("Role Hierarchy", f"{role.mention} is above my highest role or is managed."),
                ephemeral=True,
            )
            return

        if any(e[0] == emoji for e in self.setup_view.entries):
            await interaction.response.send_message(
                embed=err_embed("Duplicate Emoji", f"{emoji} is already added."),
                ephemeral=True,
            )
            return

        if any(e[1] == role_id for e in self.setup_view.entries):
            await interaction.response.send_message(
                embed=err_embed("Duplicate Role", f"{role.mention} is already added."),
                ephemeral=True,
            )
            return

        if len(self.setup_view.entries) >= 20:
            await interaction.response.send_message(
                embed=err_embed("Panel Full", "Maximum of 20 entries allowed (Discord reaction limit)."),
                ephemeral=True,
            )
            return

        self.setup_view.entries.append((emoji, role_id, label))
        await interaction.response.edit_message(
            embed=self.setup_view.build_progress_embed(),
            view=self.setup_view,
        )


class ModeSelectView(discord.ui.View):
    def __init__(self, setup_view: SetupView):
        super().__init__(timeout=120)
        self.setup_view = setup_view

    @discord.ui.select(
        placeholder="Choose a panel mode...",
        options=[
            discord.SelectOption(
                label="Normal",
                value="normal",
                emoji="🔄",
                description="React = get role, unreact = remove role",
            ),
            discord.SelectOption(
                label="Unique",
                value="unique",
                emoji="🔘",
                description="Only one role from this panel at a time",
            ),
            discord.SelectOption(
                label="Verify",
                value="verify",
                emoji="✅",
                description="React to get role permanently (can't be removed by unreacting)",
            ),
            discord.SelectOption(
                label="Reversed",
                value="reversed",
                emoji="🔁",
                description="React to REMOVE a role you already have",
            ),
            discord.SelectOption(
                label="Binding",
                value="binding",
                emoji="🔒",
                description="React to get a role — permanent, can never be removed",
            ),
        ],
    )
    async def mode_select(self, interaction: discord.Interaction, select: discord.ui.Select):
        self.setup_view.panel_mode = select.values[0]
        await interaction.response.edit_message(
            embed=self.setup_view.build_progress_embed(),
            view=self.setup_view,
        )


class ChannelSelectView(discord.ui.View):
    def __init__(self, setup_view: SetupView):
        super().__init__(timeout=120)
        self.setup_view = setup_view

    @discord.ui.select(
        cls=discord.ui.ChannelSelect,
        placeholder="Select a channel for the panel...",
        channel_types=[discord.ChannelType.text],
    )
    async def channel_select(self, interaction: discord.Interaction, select: discord.ui.ChannelSelect):
        self.setup_view.target_channel_id = select.values[0].id
        await interaction.response.edit_message(
            embed=self.setup_view.build_progress_embed(),
            view=self.setup_view,
        )


class SetupView(discord.ui.View):
    def __init__(self, author_id: int, bot: commands.Bot, guild: discord.Guild):
        super().__init__(timeout=300)
        self.author_id         = author_id
        self.bot               = bot
        self.guild             = guild
        self.panel_title:    str       = ""
        self.panel_desc:     str       = ""
        self.panel_mode:     str       = "normal"
        self.target_channel_id: Optional[int] = None
        self.max_roles:      int       = 0
        self.dm_notify:      bool      = False
        self.entries:        list      = []

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.author_id:
            await interaction.response.send_message("This setup panel isn't yours.", ephemeral=True)
            return False
        return True

    def build_progress_embed(self) -> discord.Embed:
        embed = discord.Embed(
            title=f"{PASTELSTAR}  Reaction Role Setup",
            color=PINK,
        )

        title_val   = f"`{self.panel_title}`" if self.panel_title else "*Not set*"
        channel_val = f"<#{self.target_channel_id}>" if self.target_channel_id else "*Not set*"
        icon, label, _ = MODE_INFO.get(self.panel_mode, ("🔄", "Normal", ""))
        mode_val    = f"{icon} {label}"
        max_val     = f"**{self.max_roles}**" if self.max_roles > 0 else "Unlimited"
        dm_val      = "Enabled ✅" if self.dm_notify else "Disabled ❌"

        embed.add_field(name="Title",   value=title_val,   inline=True)
        embed.add_field(name="Channel", value=channel_val, inline=True)
        embed.add_field(name="Mode",    value=mode_val,    inline=True)
        embed.add_field(name="Max Roles per User", value=max_val, inline=True)
        embed.add_field(name="DM Notifications",   value=dm_val,  inline=True)
        embed.add_field(name="\u200b", value="\u200b", inline=True)

        if self.entries:
            lines = []
            for emoji, role_id, label in self.entries:
                suffix = f"  —  *{label}*" if label else ""
                lines.append(f"{emoji}  →  <@&{role_id}>{suffix}")
            embed.add_field(name=f"{LEAF} Role Entries ({len(self.entries)})", value="\n".join(lines), inline=False)
        else:
            embed.add_field(name=f"{LEAF} Role Entries", value="*None yet — use Add Role below*", inline=False)

        ready = self.panel_title and self.target_channel_id and self.entries
        embed.set_footer(text="✅ Ready to post  •  Raze Developments • Shouffle" if ready else "Fill in Title, Channel and at least one Role to post  •  Shouffle")
        return embed

    @discord.ui.button(label="Set Title & Description", style=discord.ButtonStyle.primary, emoji=f"{PASTELSTAR}", row=0)
    async def set_title(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(PanelTitleModal(self))

    @discord.ui.button(label="Select Channel", style=discord.ButtonStyle.primary, emoji="📌", row=0)
    async def select_channel(self, interaction: discord.Interaction, button: discord.ui.Button):
        view = ChannelSelectView(self)
        await interaction.response.send_message(
            embed=discord.Embed(description="Select the channel to post the panel in.", color=PINK),
            view=view,
            ephemeral=True,
        )

    @discord.ui.button(label="Set Mode", style=discord.ButtonStyle.secondary, emoji="⚙️", row=0)
    async def set_mode(self, interaction: discord.Interaction, button: discord.ui.Button):
        view = ModeSelectView(self)
        await interaction.response.send_message(
            embed=discord.Embed(
                title="Panel Mode",
                description=(
                    "**Normal** — React = get, unreact = remove\n"
                    "**Unique** — Only one role at a time\n"
                    "**Verify** — React = get (unreacting won't remove)\n"
                    "**Reversed** — React = remove a role you have\n"
                    "**Binding** — React = permanent role"
                ),
                color=PINK,
            ),
            view=view,
            ephemeral=True,
        )

    @discord.ui.button(label="Add Role", style=discord.ButtonStyle.success, emoji="➕", row=1)
    async def add_role(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(AddEntryModal(self))

    @discord.ui.button(label="Remove Last Role", style=discord.ButtonStyle.danger, emoji="➖", row=1)
    async def remove_last_role(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self.entries:
            await interaction.response.send_message(
                embed=err_embed("Nothing to Remove", "No role entries added yet."),
                ephemeral=True,
            )
            return
        removed = self.entries.pop()
        await interaction.response.edit_message(
            embed=self.build_progress_embed(),
            view=self,
        )

    @discord.ui.button(label="Toggle DM Notify", style=discord.ButtonStyle.secondary, emoji="🔔", row=1)
    async def toggle_dm(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.dm_notify = not self.dm_notify
        await interaction.response.edit_message(
            embed=self.build_progress_embed(),
            view=self,
        )

    @discord.ui.button(label="Set Max Roles", style=discord.ButtonStyle.secondary, emoji="🔢", row=2)
    async def set_max(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(MaxRolesModal(self))

    @discord.ui.button(label="Post Panel", style=discord.ButtonStyle.success, emoji="🚀", row=2)
    async def post_panel(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self.panel_title:
            await interaction.response.send_message(
                embed=err_embed("Missing Title", "Set a panel title before posting."),
                ephemeral=True,
            )
            return
        if not self.target_channel_id:
            await interaction.response.send_message(
                embed=err_embed("Missing Channel", "Select a channel before posting."),
                ephemeral=True,
            )
            return
        if not self.entries:
            await interaction.response.send_message(
                embed=err_embed("No Roles", "Add at least one role entry before posting."),
                ephemeral=True,
            )
            return

        channel = interaction.guild.get_channel(self.target_channel_id)
        if not channel:
            await interaction.response.send_message(
                embed=err_embed("Channel Not Found", "The selected channel no longer exists."),
                ephemeral=True,
            )
            return

        panel_data = {
            "title": self.panel_title,
            "description": self.panel_desc,
            "mode": self.panel_mode,
            "max_roles": self.max_roles,
            "dm_notify": int(self.dm_notify),
        }
        entry_dicts = [{"emoji": e[0], "role_id": e[1], "label": e[2]} for e in self.entries]

        try:
            panel_msg = await channel.send(embed=build_panel_embed(panel_data, entry_dicts))
        except discord.Forbidden:
            await interaction.response.send_message(
                embed=err_embed("No Permission", f"I can't send messages in {channel.mention}."),
                ephemeral=True,
            )
            return

        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                """INSERT OR REPLACE INTO rr_panels
                   (guild_id, channel_id, message_id, title, description, mode, max_roles, dm_notify)
                   VALUES (?,?,?,?,?,?,?,?)""",
                (
                    interaction.guild.id,
                    channel.id,
                    panel_msg.id,
                    self.panel_title,
                    self.panel_desc,
                    self.panel_mode,
                    self.max_roles,
                    int(self.dm_notify),
                ),
            )
            for emoji, role_id, label in self.entries:
                await db.execute(
                    "INSERT OR REPLACE INTO rr_entries (guild_id, message_id, emoji, role_id, label) VALUES (?,?,?,?,?)",
                    (interaction.guild.id, panel_msg.id, emoji, role_id, label),
                )
            await db.commit()

        for emoji, role_id, label in self.entries:
            try:
                await panel_msg.add_reaction(emoji)
            except discord.HTTPException:
                pass

        self.stop()
        done_embed = discord.Embed(
            title=f"{PASTELSTAR}  Panel Posted!",
            description=(
                f"Your reaction role panel has been posted in {channel.mention}\n\n"
                f"**Message ID:** `{panel_msg.id}`\n"
                f"**Mode:** {MODE_INFO[self.panel_mode][0]} {MODE_INFO[self.panel_mode][1]}\n"
                f"**Entries:** {len(self.entries)}\n\n"
                f"Use `?reactionroleconfig` to edit this panel anytime."
            ),
            color=GREEN,
        )
        done_embed.set_footer(text="Raze Developments • Shouffle")
        await interaction.response.edit_message(embed=done_embed, view=None)

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.danger, emoji="✖", row=2)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.stop()
        await interaction.response.edit_message(
            embed=discord.Embed(description="Setup cancelled.", color=RED),
            view=None,
        )


class MaxRolesModal(discord.ui.Modal, title="Set Max Roles"):
    max_input = discord.ui.TextInput(
        label="Max roles per user (0 = unlimited)",
        placeholder="e.g. 2",
        max_length=2,
    )

    def __init__(self, view: SetupView):
        super().__init__()
        self.setup_view = view

    async def on_submit(self, interaction: discord.Interaction):
        try:
            val = int(self.max_input.value.strip())
            if val < 0:
                raise ValueError
        except ValueError:
            await interaction.response.send_message(
                embed=err_embed("Invalid Value", "Enter 0 (unlimited) or a positive number."),
                ephemeral=True,
            )
            return
        self.setup_view.max_roles = val
        await interaction.response.edit_message(
            embed=self.setup_view.build_progress_embed(),
            view=self.setup_view,
        )


class ConfigView(discord.ui.View):
    def __init__(self, author_id: int, bot: commands.Bot, guild: discord.Guild, panels: list[dict]):
        super().__init__(timeout=300)
        self.author_id = author_id
        self.bot       = bot
        self.guild     = guild
        self.panels    = panels
        self.selected_panel: Optional[dict] = None
        self._build_panel_select()

    def _build_panel_select(self):
        options = []
        for p in self.panels[:25]:
            channel = self.guild.get_channel(p["channel_id"])
            ch_name = f"#{channel.name}" if channel else "deleted-channel"
            options.append(
                discord.SelectOption(
                    label=p["title"][:50],
                    value=str(p["message_id"]),
                    description=f"{ch_name}  •  {p['mode']}  •  ID: {p['message_id']}",
                    emoji=f"{PASTELSTAR}",
                )
            )
        select = discord.ui.Select(
            placeholder="Select a panel to configure...",
            options=options,
            row=0,
        )
        select.callback = self._panel_selected
        self.add_item(select)

    async def _panel_selected(self, interaction: discord.Interaction):
        msg_id = int(interaction.data["values"][0])
        self.selected_panel = next((p for p in self.panels if p["message_id"] == msg_id), None)
        await interaction.response.edit_message(
            embed=await self.build_config_embed(interaction.guild),
            view=self,
        )

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.author_id:
            await interaction.response.send_message("This config panel isn't yours.", ephemeral=True)
            return False
        return True

    async def build_config_embed(self, guild: discord.Guild) -> discord.Embed:
        if not self.selected_panel:
            embed = discord.Embed(
                title=f"{PASTELSTAR}  Reaction Role Config",
                description="Select a panel from the dropdown above to manage it.",
                color=PINK,
            )
            embed.set_footer(text="Raze Developments • Shouffle")
            return embed

        p = self.selected_panel
        entries  = await fetch_entries(guild.id, p["message_id"])
        channel  = guild.get_channel(p["channel_id"])
        ch_str   = channel.mention if channel else f"<#{p['channel_id']}> *(deleted)*"
        icon, label, _ = MODE_INFO.get(p["mode"], ("🔄", "Normal", ""))

        embed = discord.Embed(title=f"{PASTELSTAR}  {p['title']}", color=PINK)
        embed.add_field(name="Channel",    value=ch_str,                                        inline=True)
        embed.add_field(name="Message ID", value=f"`{p['message_id']}`",                        inline=True)
        embed.add_field(name="Mode",       value=f"{icon} {label}",                             inline=True)
        embed.add_field(name="Max Roles",  value=str(p["max_roles"]) if p["max_roles"] else "Unlimited", inline=True)
        embed.add_field(name="DM Notify",  value="On ✅" if p["dm_notify"] else "Off ❌",       inline=True)
        embed.add_field(name="Entries",    value=str(len(entries)),                              inline=True)

        if entries:
            lines = [
                f"{e['emoji']}  →  <@&{e['role_id']}>" + (f"  *({e['label']})*" if e.get("label") else "")
                for e in entries
            ]
            embed.add_field(name=f"{LEAF} Role Entries", value="\n".join(lines), inline=False)

        embed.set_footer(text="Raze Developments • Shouffle")
        return embed

    @discord.ui.button(label="Edit Title / Desc", style=discord.ButtonStyle.primary, emoji="✏️", row=1)
    async def edit_title(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self.selected_panel:
            await interaction.response.send_message(embed=err_embed("No Panel", "Select a panel first."), ephemeral=True)
            return
        await interaction.response.send_modal(ConfigTitleModal(self, interaction.guild))

    @discord.ui.button(label="Change Mode", style=discord.ButtonStyle.secondary, emoji="⚙️", row=1)
    async def change_mode(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self.selected_panel:
            await interaction.response.send_message(embed=err_embed("No Panel", "Select a panel first."), ephemeral=True)
            return
        view = ConfigModeSelect(self, interaction.guild)
        await interaction.response.send_message(
            embed=discord.Embed(description="Select the new mode for this panel.", color=PINK),
            view=view,
            ephemeral=True,
        )

    @discord.ui.button(label="Add Role Entry", style=discord.ButtonStyle.success, emoji="➕", row=1)
    async def add_entry(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self.selected_panel:
            await interaction.response.send_message(embed=err_embed("No Panel", "Select a panel first."), ephemeral=True)
            return
        await interaction.response.send_modal(ConfigAddEntryModal(self, interaction.guild))

    @discord.ui.button(label="Remove Role Entry", style=discord.ButtonStyle.danger, emoji="➖", row=2)
    async def remove_entry(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self.selected_panel:
            await interaction.response.send_message(embed=err_embed("No Panel", "Select a panel first."), ephemeral=True)
            return
        await interaction.response.send_modal(ConfigRemoveEntryModal(self, interaction.guild))

    @discord.ui.button(label="Set Max Roles", style=discord.ButtonStyle.secondary, emoji="🔢", row=2)
    async def set_max(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self.selected_panel:
            await interaction.response.send_message(embed=err_embed("No Panel", "Select a panel first."), ephemeral=True)
            return
        await interaction.response.send_modal(ConfigMaxRolesModal(self, interaction.guild))

    @discord.ui.button(label="Toggle DM Notify", style=discord.ButtonStyle.secondary, emoji="🔔", row=2)
    async def toggle_dm(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self.selected_panel:
            await interaction.response.send_message(embed=err_embed("No Panel", "Select a panel first."), ephemeral=True)
            return
        p = self.selected_panel
        new_val = 0 if p["dm_notify"] else 1
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                "UPDATE rr_panels SET dm_notify=? WHERE guild_id=? AND message_id=?",
                (new_val, interaction.guild.id, p["message_id"]),
            )
            await db.commit()
        self.selected_panel = await fetch_panel(interaction.guild.id, p["message_id"])
        self.panels = await fetch_all_panels(interaction.guild.id)
        await interaction.response.edit_message(
            embed=await self.build_config_embed(interaction.guild),
            view=self,
        )

    @discord.ui.button(label="Delete Panel", style=discord.ButtonStyle.danger, emoji="🗑️", row=3)
    async def delete_panel(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self.selected_panel:
            await interaction.response.send_message(embed=err_embed("No Panel", "Select a panel first."), ephemeral=True)
            return
        view = ConfirmDeleteView(self, interaction.guild)
        await interaction.response.send_message(
            embed=discord.Embed(
                title="⚠️  Delete Panel?",
                description=(
                    f"This will permanently delete **{self.selected_panel['title']}** "
                    f"(`{self.selected_panel['message_id']}`) and all its entries.\n\n"
                    "This action **cannot** be undone."
                ),
                color=YELLOW,
            ),
            view=view,
            ephemeral=True,
        )

    @discord.ui.button(label="Close", style=discord.ButtonStyle.secondary, emoji="✖", row=3)
    async def close(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.stop()
        await interaction.response.edit_message(
            embed=discord.Embed(description="Config panel closed.", color=RED),
            view=None,
        )


class ConfigTitleModal(discord.ui.Modal, title="Edit Panel Title / Description"):
    new_title = discord.ui.TextInput(label="New Title", max_length=100)
    new_desc  = discord.ui.TextInput(
        label="New Description (optional)",
        required=False,
        style=discord.TextStyle.paragraph,
        max_length=300,
    )

    def __init__(self, config_view: ConfigView, guild: discord.Guild):
        super().__init__()
        self.config_view = config_view
        self.guild       = guild
        self.new_title.default = config_view.selected_panel["title"]
        self.new_desc.default  = config_view.selected_panel.get("description", "")

    async def on_submit(self, interaction: discord.Interaction):
        p = self.config_view.selected_panel
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                "UPDATE rr_panels SET title=?, description=? WHERE guild_id=? AND message_id=?",
                (self.new_title.value.strip(), (self.new_desc.value or "").strip(), self.guild.id, p["message_id"]),
            )
            await db.commit()
        await _refresh_panel_message(self.config_view.bot, self.guild, p["message_id"])
        self.config_view.selected_panel = await fetch_panel(self.guild.id, p["message_id"])
        self.config_view.panels = await fetch_all_panels(self.guild.id)
        await interaction.response.edit_message(
            embed=await self.config_view.build_config_embed(self.guild),
            view=self.config_view,
        )


class ConfigModeSelect(discord.ui.View):
    def __init__(self, config_view: ConfigView, guild: discord.Guild):
        super().__init__(timeout=60)
        self.config_view = config_view
        self.guild       = guild

    @discord.ui.select(
        placeholder="Choose new mode...",
        options=[
            discord.SelectOption(label="Normal",   value="normal",   emoji="🔄"),
            discord.SelectOption(label="Unique",   value="unique",   emoji="🔘"),
            discord.SelectOption(label="Verify",   value="verify",   emoji="✅"),
            discord.SelectOption(label="Reversed", value="reversed", emoji="🔁"),
            discord.SelectOption(label="Binding",  value="binding",  emoji="🔒"),
        ],
    )
    async def select(self, interaction: discord.Interaction, select: discord.ui.Select):
        p = self.config_view.selected_panel
        new_mode = select.values[0]
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                "UPDATE rr_panels SET mode=? WHERE guild_id=? AND message_id=?",
                (new_mode, self.guild.id, p["message_id"]),
            )
            await db.commit()
        await _refresh_panel_message(self.config_view.bot, self.guild, p["message_id"])
        self.config_view.selected_panel = await fetch_panel(self.guild.id, p["message_id"])
        self.config_view.panels = await fetch_all_panels(self.guild.id)
        await interaction.response.edit_message(
            embed=discord.Embed(description=f"Mode updated to **{new_mode}**.", color=GREEN),
            view=None,
        )
        original = interaction.message
        if original:
            try:
                await original.edit(
                    embed=await self.config_view.build_config_embed(self.guild),
                    view=self.config_view,
                )
            except Exception:
                pass


class ConfigAddEntryModal(discord.ui.Modal, title="Add Role Entry"):
    emoji_input = discord.ui.TextInput(label="Emoji", max_length=100)
    role_input  = discord.ui.TextInput(label="Role ID", max_length=20)
    label_input = discord.ui.TextInput(label="Label (optional)", required=False, max_length=50)

    def __init__(self, config_view: ConfigView, guild: discord.Guild):
        super().__init__()
        self.config_view = config_view
        self.guild       = guild

    async def on_submit(self, interaction: discord.Interaction):
        emoji = self.emoji_input.value.strip()
        label = (self.label_input.value or "").strip()

        try:
            role_id = int(self.role_input.value.strip())
        except ValueError:
            await interaction.response.send_message(embed=err_embed("Invalid Role ID", "Must be a number."), ephemeral=True)
            return

        role = self.guild.get_role(role_id)
        if not role:
            await interaction.response.send_message(embed=err_embed("Role Not Found", f"No role with ID `{role_id}`."), ephemeral=True)
            return

        if role.managed or role >= self.guild.me.top_role:
            await interaction.response.send_message(embed=err_embed("Role Hierarchy", f"{role.mention} is above my highest role or is managed."), ephemeral=True)
            return

        p = self.config_view.selected_panel
        entries = await fetch_entries(self.guild.id, p["message_id"])

        if any(e["emoji"] == emoji for e in entries):
            await interaction.response.send_message(embed=err_embed("Duplicate Emoji", f"{emoji} is already on this panel."), ephemeral=True)
            return
        if any(e["role_id"] == role_id for e in entries):
            await interaction.response.send_message(embed=err_embed("Duplicate Role", f"{role.mention} is already on this panel."), ephemeral=True)
            return
        if len(entries) >= 20:
            await interaction.response.send_message(embed=err_embed("Panel Full", "Maximum 20 entries per panel."), ephemeral=True)
            return

        channel = self.guild.get_channel(p["channel_id"])
        if channel:
            try:
                msg = await channel.fetch_message(p["message_id"])
                await msg.add_reaction(emoji)
            except discord.HTTPException:
                await interaction.response.send_message(embed=err_embed("Invalid Emoji", "Could not react with that emoji."), ephemeral=True)
                return

        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                "INSERT OR REPLACE INTO rr_entries (guild_id, message_id, emoji, role_id, label) VALUES (?,?,?,?,?)",
                (self.guild.id, p["message_id"], emoji, role_id, label),
            )
            await db.commit()

        await _refresh_panel_message(self.config_view.bot, self.guild, p["message_id"])
        self.config_view.selected_panel = await fetch_panel(self.guild.id, p["message_id"])
        await interaction.response.edit_message(
            embed=await self.config_view.build_config_embed(self.guild),
            view=self.config_view,
        )


class ConfigRemoveEntryModal(discord.ui.Modal, title="Remove Role Entry"):
    emoji_input = discord.ui.TextInput(label="Emoji to remove", max_length=100)

    def __init__(self, config_view: ConfigView, guild: discord.Guild):
        super().__init__()
        self.config_view = config_view
        self.guild       = guild

    async def on_submit(self, interaction: discord.Interaction):
        emoji = self.emoji_input.value.strip()
        p = self.config_view.selected_panel
        entries = await fetch_entries(self.guild.id, p["message_id"])
        entry = next((e for e in entries if e["emoji"] == emoji), None)

        if not entry:
            await interaction.response.send_message(embed=err_embed("Not Found", f"{emoji} is not on this panel."), ephemeral=True)
            return

        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                "DELETE FROM rr_entries WHERE guild_id=? AND message_id=? AND emoji=?",
                (self.guild.id, p["message_id"], emoji),
            )
            await db.commit()

        channel = self.guild.get_channel(p["channel_id"])
        if channel:
            try:
                msg = await channel.fetch_message(p["message_id"])
                await msg.clear_reaction(emoji)
            except (discord.NotFound, discord.HTTPException):
                pass

        await _refresh_panel_message(self.config_view.bot, self.guild, p["message_id"])
        self.config_view.selected_panel = await fetch_panel(self.guild.id, p["message_id"])
        await interaction.response.edit_message(
            embed=await self.config_view.build_config_embed(self.guild),
            view=self.config_view,
        )


class ConfigMaxRolesModal(discord.ui.Modal, title="Set Max Roles Per User"):
    max_input = discord.ui.TextInput(label="Max roles (0 = unlimited)", max_length=2)

    def __init__(self, config_view: ConfigView, guild: discord.Guild):
        super().__init__()
        self.config_view = config_view
        self.guild       = guild
        self.max_input.default = str(config_view.selected_panel.get("max_roles", 0))

    async def on_submit(self, interaction: discord.Interaction):
        try:
            val = int(self.max_input.value.strip())
            if val < 0:
                raise ValueError
        except ValueError:
            await interaction.response.send_message(embed=err_embed("Invalid Value", "Enter 0 or a positive number."), ephemeral=True)
            return

        p = self.config_view.selected_panel
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                "UPDATE rr_panels SET max_roles=? WHERE guild_id=? AND message_id=?",
                (val, self.guild.id, p["message_id"]),
            )
            await db.commit()

        await _refresh_panel_message(self.config_view.bot, self.guild, p["message_id"])
        self.config_view.selected_panel = await fetch_panel(self.guild.id, p["message_id"])
        self.config_view.panels = await fetch_all_panels(self.guild.id)
        await interaction.response.edit_message(
            embed=await self.config_view.build_config_embed(self.guild),
            view=self.config_view,
        )


class ConfirmDeleteView(discord.ui.View):
    def __init__(self, config_view: ConfigView, guild: discord.Guild):
        super().__init__(timeout=30)
        self.config_view = config_view
        self.guild       = guild

    @discord.ui.button(label="Yes, Delete", style=discord.ButtonStyle.danger)
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        p = self.config_view.selected_panel
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("DELETE FROM rr_panels  WHERE guild_id=? AND message_id=?", (self.guild.id, p["message_id"]))
            await db.execute("DELETE FROM rr_entries WHERE guild_id=? AND message_id=?", (self.guild.id, p["message_id"]))
            await db.commit()

        channel = self.guild.get_channel(p["channel_id"])
        if channel:
            try:
                msg = await channel.fetch_message(p["message_id"])
                await msg.delete()
            except (discord.NotFound, discord.HTTPException):
                pass

        self.config_view.selected_panel = None
        self.config_view.panels = await fetch_all_panels(self.guild.id)
        self.stop()
        await interaction.response.edit_message(
            embed=discord.Embed(description=f"Panel **{p['title']}** deleted.", color=GREEN),
            view=None,
        )

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.secondary)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.stop()
        await interaction.response.edit_message(
            embed=discord.Embed(description="Deletion cancelled.", color=RED),
            view=None,
        )


class ReactionRole(commands.Cog, name="ReactionRole"):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        bot.loop.create_task(init_db())

    @commands.command(name="reactionrole", aliases=["rr"])
    @commands.has_permissions(administrator=True)
    async def reactionrole_prefix(self, ctx: commands.Context):
        view  = SetupView(ctx.author.id, self.bot, ctx.guild)
        embed = view.build_progress_embed()
        await ctx.send(embed=embed, view=view)

    @app_commands.command(name="reactionrole", description="Set up a reaction role panel")
    @app_commands.default_permissions(administrator=True)
    async def reactionrole_slash(self, interaction: discord.Interaction):
        view  = SetupView(interaction.user.id, self.bot, interaction.guild)
        embed = view.build_progress_embed()
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

    @commands.command(name="reactionroleconfig", aliases=["rrconfig"])
    @commands.has_permissions(administrator=True)
    async def rrconfig_prefix(self, ctx: commands.Context):
        panels = await fetch_all_panels(ctx.guild.id)
        if not panels:
            await ctx.send(embed=err_embed("No Panels", "No reaction role panels found. Use `?reactionrole` to create one."))
            return
        view  = ConfigView(ctx.author.id, self.bot, ctx.guild, panels)
        embed = await view.build_config_embed(ctx.guild)
        await ctx.send(embed=embed, view=view)

    @app_commands.command(name="reactionroleconfig", description="Edit an existing reaction role panel")
    @app_commands.default_permissions(administrator=True)
    async def rrconfig_slash(self, interaction: discord.Interaction):
        panels = await fetch_all_panels(interaction.guild.id)
        if not panels:
            await interaction.response.send_message(
                embed=err_embed("No Panels", "No reaction role panels found. Use `/reactionrole` to create one."),
                ephemeral=True,
            )
            return
        view  = ConfigView(interaction.user.id, self.bot, interaction.guild, panels)
        embed = await view.build_config_embed(interaction.guild)
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member) -> None:
        if member.bot:
            return
        role_id = await fetch_autorole(member.guild.id)
        if not role_id:
            return
        role = member.guild.get_role(role_id)
        if role and role < member.guild.me.top_role:
            try:
                await member.add_roles(role, reason="Autorole")
            except discord.Forbidden:
                pass

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload: discord.RawReactionActionEvent) -> None:
        if not payload.guild_id or payload.user_id == self.bot.user.id:
            return

        emoji  = str(payload.emoji)
        panel  = await fetch_panel(payload.guild_id, payload.message_id)
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

        if mode == "reversed":
            if role in member.roles:
                try:
                    await member.remove_roles(role, reason="Reaction Role (reversed)")
                    await _dm_member(member, panel, role, added=False)
                except discord.Forbidden:
                    pass
            return

        if mode == "unique":
            other_ids     = {e["role_id"] for e in entries if e["emoji"] != emoji}
            roles_to_drop = [guild.get_role(rid) for rid in other_ids if guild.get_role(rid) in member.roles]
            if roles_to_drop:
                try:
                    await member.remove_roles(*roles_to_drop, reason="Reaction Role (unique)")
                except discord.Forbidden:
                    pass

        max_r = panel.get("max_roles", 0)
        if max_r > 0 and mode != "unique":
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
                await _dm_member(member, panel, role, added=True)
            except discord.Forbidden:
                pass

    @commands.Cog.listener()
    async def on_raw_reaction_remove(self, payload: discord.RawReactionActionEvent) -> None:
        if not payload.guild_id or payload.user_id == self.bot.user.id:
            return

        emoji = str(payload.emoji)
        panel = await fetch_panel(payload.guild_id, payload.message_id)
        if not panel:
            return

        if panel["mode"] in ("verify", "binding", "reversed"):
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
                await member.remove_roles(role, reason=f"Reaction Role removed ({panel['mode']})")
                await _dm_member(member, panel, role, added=False)
            except discord.Forbidden:
                pass


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(ReactionRole(bot))

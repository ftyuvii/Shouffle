import discord
from discord.ext import commands
from discord import app_commands
import aiosqlite
import asyncio
import json
import hashlib
import time
import re
import aiohttp
from datetime import datetime, timezone, timedelta
from io import BytesIO

PINK   = 0xFFB6C1
RED    = 0xFF4444
GREEN  = 0x57F287
YELLOW = 0xFFD700
DARK   = 0x2B2D31

OWNER_ID = 907180055615123456
DB       = "shouffle.db"

E_CONFIG   = "🌀"
E_CROSS    = "❌"
E_TICK     = "✅"
E_WHITE    = "◽"
E_DL       = "♐"
E_RESTRICT = "🚧"
E_STAR     = "✨"
E_LEAF     = "🍀"

SPAM_THRESHOLD        = 6
SPAM_WINDOW           = 5
RAID_JOIN_THRESHOLD   = 8
RAID_JOIN_WINDOW      = 10
MUTE_DURATION_SPAM    = 300
MUTE_DURATION_WORD    = 300
MUTE_DURATION_MENTION = 120
MASS_MENTION_LIMIT    = 5

PUNISH_BAN  = "ban"
PUNISH_MUTE = "mute"
PUNISH_KICK = "kick"

SAFE_ACTIONS = {
    discord.AuditLogAction.message_delete,
    discord.AuditLogAction.message_bulk_delete,
    discord.AuditLogAction.message_pin,
    discord.AuditLogAction.message_unpin,
    discord.AuditLogAction.invite_create,
    discord.AuditLogAction.invite_delete,
    discord.AuditLogAction.emoji_create,
    discord.AuditLogAction.emoji_update,
    discord.AuditLogAction.emoji_delete,
    discord.AuditLogAction.sticker_create,
    discord.AuditLogAction.sticker_update,
    discord.AuditLogAction.sticker_delete,
    discord.AuditLogAction.thread_create,
    discord.AuditLogAction.thread_update,
    discord.AuditLogAction.thread_delete,
    discord.AuditLogAction.automod_rule_create,
    discord.AuditLogAction.automod_rule_update,
    discord.AuditLogAction.automod_rule_delete,
}

TRIGGER_MAP = {
    discord.AuditLogAction.ban:                (PUNISH_BAN,  "Unauthorized ban action"),
    discord.AuditLogAction.kick:               (PUNISH_BAN,  "Unauthorized kick action"),
    discord.AuditLogAction.member_role_update: (PUNISH_MUTE, "Unauthorized role modification"),
    discord.AuditLogAction.channel_delete:     (PUNISH_BAN,  "Unauthorized channel deletion"),
    discord.AuditLogAction.channel_create:     (PUNISH_BAN,  "Unauthorized channel creation"),
    discord.AuditLogAction.channel_update:     (PUNISH_MUTE, "Unauthorized channel modification"),
    discord.AuditLogAction.role_delete:        (PUNISH_BAN,  "Unauthorized role deletion"),
    discord.AuditLogAction.role_create:        (PUNISH_BAN,  "Unauthorized role creation"),
    discord.AuditLogAction.role_update:        (PUNISH_MUTE, "Unauthorized role modification"),
    discord.AuditLogAction.guild_update:       (PUNISH_BAN,  "Unauthorized server modification"),
    discord.AuditLogAction.webhook_create:     (PUNISH_BAN,  "Unauthorized webhook creation"),
    discord.AuditLogAction.webhook_delete:     (PUNISH_BAN,  "Unauthorized webhook deletion"),
    discord.AuditLogAction.webhook_update:     (PUNISH_MUTE, "Unauthorized webhook modification"),
    discord.AuditLogAction.member_disconnect:  (PUNISH_MUTE, "Unauthorized member disconnect"),
    discord.AuditLogAction.member_move:        (PUNISH_MUTE, "Unauthorized member move in VC"),
    discord.AuditLogAction.bot_add:            (PUNISH_BAN,  "Unauthorized bot addition"),
    discord.AuditLogAction.integration_create: (PUNISH_BAN,  "Unauthorized integration added"),
}


def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()


class SecurityDB:
    @staticmethod
    async def setup():
        async with aiosqlite.connect(DB) as db:
            await db.execute("""
                CREATE TABLE IF NOT EXISTS security_guilds (
                    guild_id        INTEGER PRIMARY KEY,
                    password_hash   TEXT NOT NULL,
                    enabled         INTEGER DEFAULT 1,
                    logs_channel_id INTEGER,
                    webhook_url     TEXT,
                    anti_spam       INTEGER DEFAULT 1,
                    anti_raid       INTEGER DEFAULT 1,
                    anti_mention    INTEGER DEFAULT 1,
                    word_filter     INTEGER DEFAULT 1,
                    created_at      INTEGER
                )
            """)
            await db.execute("""
                CREATE TABLE IF NOT EXISTS security_whitelist (
                    guild_id INTEGER,
                    user_id  INTEGER,
                    PRIMARY KEY (guild_id, user_id)
                )
            """)
            await db.execute("""
                CREATE TABLE IF NOT EXISTS security_banned_words (
                    guild_id INTEGER,
                    word     TEXT,
                    PRIMARY KEY (guild_id, word)
                )
            """)
            await db.execute("""
                CREATE TABLE IF NOT EXISTS security_actions (
                    id         INTEGER PRIMARY KEY AUTOINCREMENT,
                    guild_id   INTEGER,
                    target_id  INTEGER,
                    action     TEXT,
                    reason     TEXT,
                    moderator  TEXT,
                    timestamp  INTEGER
                )
            """)
            for col in ["anti_spam", "anti_raid", "anti_mention", "word_filter"]:
                try:
                    await db.execute(f"ALTER TABLE security_guilds ADD COLUMN {col} INTEGER DEFAULT 1")
                except Exception:
                    pass
            await db.commit()

    @staticmethod
    async def get_guild(guild_id: int):
        async with aiosqlite.connect(DB) as db:
            async with db.execute("SELECT * FROM security_guilds WHERE guild_id = ?", (guild_id,)) as cur:
                row = await cur.fetchone()
                if not row:
                    return None
                cols = [d[0] for d in cur.description]
                return dict(zip(cols, row))

    @staticmethod
    async def create_guild(guild_id: int, password: str):
        async with aiosqlite.connect(DB) as db:
            await db.execute(
                "INSERT OR IGNORE INTO security_guilds (guild_id, password_hash, enabled, anti_spam, anti_raid, anti_mention, word_filter, created_at) VALUES (?, ?, 1, 1, 1, 1, 1, ?)",
                (guild_id, hash_password(password), int(time.time()))
            )
            await db.commit()

    @staticmethod
    async def delete_guild(guild_id: int):
        async with aiosqlite.connect(DB) as db:
            await db.execute("DELETE FROM security_guilds WHERE guild_id = ?", (guild_id,))
            await db.execute("DELETE FROM security_whitelist WHERE guild_id = ?", (guild_id,))
            await db.execute("DELETE FROM security_banned_words WHERE guild_id = ?", (guild_id,))
            await db.execute("DELETE FROM security_actions WHERE guild_id = ?", (guild_id,))
            await db.commit()

    @staticmethod
    async def update_guild(guild_id: int, **kwargs):
        cols = ", ".join(f"{k} = ?" for k in kwargs)
        vals = list(kwargs.values()) + [guild_id]
        async with aiosqlite.connect(DB) as db:
            await db.execute(f"UPDATE security_guilds SET {cols} WHERE guild_id = ?", vals)
            await db.commit()

    @staticmethod
    async def is_whitelisted(guild_id: int, user_id: int) -> bool:
        async with aiosqlite.connect(DB) as db:
            async with db.execute(
                "SELECT 1 FROM security_whitelist WHERE guild_id = ? AND user_id = ?", (guild_id, user_id)
            ) as cur:
                return await cur.fetchone() is not None

    @staticmethod
    async def whitelist_add(guild_id: int, user_id: int):
        async with aiosqlite.connect(DB) as db:
            await db.execute(
                "INSERT OR IGNORE INTO security_whitelist (guild_id, user_id) VALUES (?, ?)", (guild_id, user_id)
            )
            await db.commit()

    @staticmethod
    async def whitelist_remove(guild_id: int, user_id: int):
        async with aiosqlite.connect(DB) as db:
            await db.execute(
                "DELETE FROM security_whitelist WHERE guild_id = ? AND user_id = ?", (guild_id, user_id)
            )
            await db.commit()

    @staticmethod
    async def whitelist_list(guild_id: int):
        async with aiosqlite.connect(DB) as db:
            async with db.execute(
                "SELECT user_id FROM security_whitelist WHERE guild_id = ?", (guild_id,)
            ) as cur:
                return [r[0] for r in await cur.fetchall()]

    @staticmethod
    async def add_banned_word(guild_id: int, word: str):
        async with aiosqlite.connect(DB) as db:
            await db.execute(
                "INSERT OR IGNORE INTO security_banned_words (guild_id, word) VALUES (?, ?)",
                (guild_id, word.lower().strip())
            )
            await db.commit()

    @staticmethod
    async def remove_banned_word(guild_id: int, word: str):
        async with aiosqlite.connect(DB) as db:
            await db.execute(
                "DELETE FROM security_banned_words WHERE guild_id = ? AND word = ?",
                (guild_id, word.lower().strip())
            )
            await db.commit()

    @staticmethod
    async def get_banned_words(guild_id: int) -> list[str]:
        async with aiosqlite.connect(DB) as db:
            async with db.execute(
                "SELECT word FROM security_banned_words WHERE guild_id = ?", (guild_id,)
            ) as cur:
                return [r[0] for r in await cur.fetchall()]

    @staticmethod
    async def log_action(guild_id: int, target_id: int, action: str, reason: str, moderator: str):
        async with aiosqlite.connect(DB) as db:
            await db.execute(
                "INSERT INTO security_actions (guild_id, target_id, action, reason, moderator, timestamp) VALUES (?, ?, ?, ?, ?, ?)",
                (guild_id, target_id, action, reason, moderator, int(time.time()))
            )
            await db.commit()

    @staticmethod
    async def get_actions(guild_id: int):
        async with aiosqlite.connect(DB) as db:
            async with db.execute(
                "SELECT target_id, action, reason, moderator, timestamp FROM security_actions WHERE guild_id = ? ORDER BY timestamp DESC LIMIT 200",
                (guild_id,)
            ) as cur:
                rows = await cur.fetchall()
                return [
                    {"target_id": r[0], "action": r[1], "reason": r[2], "moderator": r[3], "timestamp": r[4]}
                    for r in rows
                ]


class SetupPasswordModal(discord.ui.Modal, title="Create Security Password"):
    password = discord.ui.TextInput(
        label="New Password",
        placeholder="Choose a strong password (min 6 chars)",
        style=discord.TextStyle.short,
        min_length=6,
        max_length=64
    )
    confirm = discord.ui.TextInput(
        label="Confirm Password",
        placeholder="Re-enter your password",
        style=discord.TextStyle.short,
        min_length=6,
        max_length=64
    )

    def __init__(self, cog):
        super().__init__()
        self.cog = cog

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        if self.password.value != self.confirm.value:
            await interaction.followup.send(
                embed=discord.Embed(description=f"{E_CROSS} Passwords do not match.", color=RED),
                ephemeral=True
            )
            return
        guild_data = await SecurityDB.get_guild(interaction.guild.id)
        if guild_data:
            await interaction.followup.send(
                embed=discord.Embed(description=f"{E_CROSS} Security already set up. Log in instead.", color=RED),
                ephemeral=True
            )
            return
        await SecurityDB.create_guild(interaction.guild.id, self.password.value)
        await SecurityDB.whitelist_add(interaction.guild.id, interaction.user.id)
        if interaction.client.user:
            await SecurityDB.whitelist_add(interaction.guild.id, interaction.client.user.id)
        for admin_member in interaction.guild.members:
            if admin_member.guild_permissions.administrator and not admin_member.bot:
                await SecurityDB.whitelist_add(interaction.guild.id, admin_member.id)
        embed = discord.Embed(
            title=f"{E_CONFIG} Security Activated",
            description=(
                f"Your server is now protected by **Shouffle Security**.\n\n"
                f"{E_TICK} Password set successfully\n"
                f"{E_WHITE} All admins auto-whitelisted\n"
                f"{E_RESTRICT} Anti-raid, spam & word filter active\n"
                f"{E_LEAF} Backgrounds system also activated"
            ),
            color=GREEN
        )
        embed.set_footer(text="Shouffle Security • Raze Developments")
        await interaction.followup.send(embed=embed, ephemeral=True)
        fresh_data = await SecurityDB.get_guild(interaction.guild.id)
        await self.cog.open_dashboard(interaction, guild_data=fresh_data)
        bg_cog = interaction.client.get_cog("Backgrounds")
        if bg_cog:
            await bg_cog.on_security_enable(interaction.guild)


class PasswordModal(discord.ui.Modal, title="Security Dashboard Login"):
    password = discord.ui.TextInput(
        label="Password",
        placeholder="Enter your security password",
        style=discord.TextStyle.short,
        min_length=4,
        max_length=64
    )

    def __init__(self, cog):
        super().__init__()
        self.cog = cog

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        guild_data = await SecurityDB.get_guild(interaction.guild.id)
        if not guild_data:
            await interaction.followup.send(
                embed=discord.Embed(description=f"{E_CROSS} No security setup found.", color=RED),
                ephemeral=True
            )
            return
        if guild_data["password_hash"] != hash_password(self.password.value):
            await interaction.followup.send(
                embed=discord.Embed(description=f"{E_CROSS} Incorrect password.", color=RED),
                ephemeral=True
            )
            return
        await self.cog.open_dashboard(interaction, guild_data=guild_data)


class WhitelistModal(discord.ui.Modal, title="Whitelist User"):
    user_id = discord.ui.TextInput(
        label="User ID",
        placeholder="Enter the user's Discord ID",
        style=discord.TextStyle.short,
        min_length=17,
        max_length=20
    )

    def __init__(self, cog, mode="add"):
        super().__init__()
        self.cog = cog
        self.mode = mode

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        try:
            uid = int(self.user_id.value)
        except ValueError:
            await interaction.followup.send(
                embed=discord.Embed(description=f"{E_CROSS} Invalid user ID.", color=RED),
                ephemeral=True
            )
            return
        if self.mode == "add":
            await SecurityDB.whitelist_add(interaction.guild.id, uid)
            await interaction.followup.send(
                embed=discord.Embed(description=f"{E_WHITE} <@{uid}> has been whitelisted.", color=GREEN),
                ephemeral=True
            )
        else:
            if interaction.client.user and uid == interaction.client.user.id:
                await interaction.followup.send(
                    embed=discord.Embed(description=f"{E_CROSS} Cannot remove the bot from the whitelist.", color=RED),
                    ephemeral=True
                )
                return
            await SecurityDB.whitelist_remove(interaction.guild.id, uid)
            await interaction.followup.send(
                embed=discord.Embed(description=f"{E_CROSS} <@{uid}> removed from whitelist.", color=RED),
                ephemeral=True
            )


class LogsChannelModal(discord.ui.Modal, title="Set Logs Channel"):
    channel_id = discord.ui.TextInput(
        label="Channel ID",
        placeholder="Enter the channel ID for security logs",
        style=discord.TextStyle.short,
        min_length=17,
        max_length=20
    )

    def __init__(self, cog):
        super().__init__()
        self.cog = cog

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        try:
            cid = int(self.channel_id.value)
        except ValueError:
            await interaction.followup.send(
                embed=discord.Embed(description=f"{E_CROSS} Invalid channel ID.", color=RED),
                ephemeral=True
            )
            return
        channel = interaction.guild.get_channel(cid)
        if not channel or not isinstance(channel, discord.TextChannel):
            await interaction.followup.send(
                embed=discord.Embed(description=f"{E_CROSS} Channel not found.", color=RED),
                ephemeral=True
            )
            return
        try:
            webhook = await self.cog.get_or_create_webhook(channel)
            await SecurityDB.update_guild(interaction.guild.id, logs_channel_id=cid, webhook_url=webhook.url)
        except discord.Forbidden:
            await interaction.followup.send(
                embed=discord.Embed(description=f"{E_CROSS} I need **Manage Webhooks** permission in that channel.", color=RED),
                ephemeral=True
            )
            return
        await interaction.followup.send(
            embed=discord.Embed(
                description=f"{E_TICK} Security logs will now be sent to {channel.mention}.",
                color=GREEN
            ),
            ephemeral=True
        )


class ChangePasswordModal(discord.ui.Modal, title="Change Security Password"):
    old_pw = discord.ui.TextInput(
        label="Current Password",
        placeholder="Enter your current password",
        style=discord.TextStyle.short,
        min_length=4,
        max_length=64
    )
    new_pw = discord.ui.TextInput(
        label="New Password",
        placeholder="Enter your new password (min 6 chars)",
        style=discord.TextStyle.short,
        min_length=6,
        max_length=64
    )
    confirm = discord.ui.TextInput(
        label="Confirm New Password",
        placeholder="Re-enter new password",
        style=discord.TextStyle.short,
        min_length=6,
        max_length=64
    )

    def __init__(self, cog):
        super().__init__()
        self.cog = cog

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        guild_data = await SecurityDB.get_guild(interaction.guild.id)
        if not guild_data:
            await interaction.followup.send(
                embed=discord.Embed(description=f"{E_CROSS} No security setup found.", color=RED),
                ephemeral=True
            )
            return
        if guild_data["password_hash"] != hash_password(self.old_pw.value):
            await interaction.followup.send(
                embed=discord.Embed(description=f"{E_CROSS} Current password is incorrect.", color=RED),
                ephemeral=True
            )
            return
        if self.new_pw.value != self.confirm.value:
            await interaction.followup.send(
                embed=discord.Embed(description=f"{E_CROSS} New passwords do not match.", color=RED),
                ephemeral=True
            )
            return
        await SecurityDB.update_guild(interaction.guild.id, password_hash=hash_password(self.new_pw.value))
        await interaction.followup.send(
            embed=discord.Embed(description=f"{E_TICK} Password updated successfully.", color=GREEN),
            ephemeral=True
        )


class WordFilterModal(discord.ui.Modal, title="Word Filter"):
    word = discord.ui.TextInput(
        label="Word",
        placeholder="Enter the word to add or remove",
        style=discord.TextStyle.short,
        min_length=1,
        max_length=50
    )

    def __init__(self, cog, mode="add"):
        super().__init__()
        self.cog = cog
        self.mode = mode

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        w = self.word.value.strip().lower()
        if not w:
            await interaction.followup.send(
                embed=discord.Embed(description=f"{E_CROSS} Invalid word.", color=RED),
                ephemeral=True
            )
            return
        if self.mode == "add":
            await SecurityDB.add_banned_word(interaction.guild.id, w)
            await interaction.followup.send(
                embed=discord.Embed(description=f"{E_RESTRICT} `{w}` added to word filter.", color=GREEN),
                ephemeral=True
            )
        else:
            await SecurityDB.remove_banned_word(interaction.guild.id, w)
            await interaction.followup.send(
                embed=discord.Embed(description=f"{E_TICK} `{w}` removed from word filter.", color=PINK),
                ephemeral=True
            )


class ResetSecurityModal(discord.ui.Modal, title="Reset Security"):
    confirm_text = discord.ui.TextInput(
        label='Type "RESET" to confirm',
        placeholder="RESET",
        style=discord.TextStyle.short,
        min_length=5,
        max_length=5
    )
    password = discord.ui.TextInput(
        label="Current Password",
        placeholder="Enter your security password",
        style=discord.TextStyle.short,
        min_length=4,
        max_length=64
    )

    def __init__(self, cog):
        super().__init__()
        self.cog = cog

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        if self.confirm_text.value.upper() != "RESET":
            await interaction.followup.send(
                embed=discord.Embed(description=f"{E_CROSS} Confirmation text incorrect.", color=RED),
                ephemeral=True
            )
            return
        guild_data = await SecurityDB.get_guild(interaction.guild.id)
        if not guild_data or guild_data["password_hash"] != hash_password(self.password.value):
            await interaction.followup.send(
                embed=discord.Embed(description=f"{E_CROSS} Incorrect password.", color=RED),
                ephemeral=True
            )
            return
        await SecurityDB.delete_guild(interaction.guild.id)
        embed = discord.Embed(
            title=f"{E_CROSS} Security Reset",
            description="All security data for this server has been cleared. Run `?security` to set up again.",
            color=RED
        )
        embed.set_footer(text="Shouffle Security • Raze Developments")
        await interaction.followup.send(embed=embed, ephemeral=True)
        bg_cog = interaction.client.get_cog("Backgrounds")
        if bg_cog:
            await bg_cog.on_security_disable(interaction.guild)


class DashboardView(discord.ui.View):
    def __init__(self, cog, guild_data: dict):
        super().__init__(timeout=300)
        self.cog = cog
        self.guild_data = guild_data
        self._build_buttons()

    def _build_buttons(self):
        enabled      = bool(self.guild_data.get("enabled", 1))
        anti_spam    = bool(self.guild_data.get("anti_spam", 1))
        anti_raid    = bool(self.guild_data.get("anti_raid", 1))
        anti_mention = bool(self.guild_data.get("anti_mention", 1))
        word_filter  = bool(self.guild_data.get("word_filter", 1))

        toggle_label = "Disable Security" if enabled else "Enable Security"
        toggle_emoji = E_CROSS if enabled else E_TICK
        toggle_style = discord.ButtonStyle.danger if enabled else discord.ButtonStyle.success

        rows = [
            [
                ("Whitelist User",    E_WHITE,    discord.ButtonStyle.secondary, "wl_add"),
                ("Unwhitelist",       E_RESTRICT, discord.ButtonStyle.secondary, "wl_remove"),
                ("View Whitelist",    E_WHITE,    discord.ButtonStyle.secondary, "wl_list"),
                ("Set Logs Channel",  E_CONFIG,   discord.ButtonStyle.secondary, "set_logs"),
                ("Download Logs",     E_DL,       discord.ButtonStyle.secondary, "dl_logs"),
            ],
            [
                (f"Anti-Spam: {'ON' if anti_spam else 'OFF'}",        E_RESTRICT, discord.ButtonStyle.success if anti_spam else discord.ButtonStyle.danger, "toggle_spam"),
                (f"Anti-Raid: {'ON' if anti_raid else 'OFF'}",        E_RESTRICT, discord.ButtonStyle.success if anti_raid else discord.ButtonStyle.danger, "toggle_raid"),
                (f"Anti-Mention: {'ON' if anti_mention else 'OFF'}",  E_RESTRICT, discord.ButtonStyle.success if anti_mention else discord.ButtonStyle.danger, "toggle_mention"),
                (f"Word Filter: {'ON' if word_filter else 'OFF'}",    E_RESTRICT, discord.ButtonStyle.success if word_filter else discord.ButtonStyle.danger, "toggle_words"),
            ],
            [
                ("Add Banned Word",    E_RESTRICT, discord.ButtonStyle.secondary, "word_add"),
                ("Remove Banned Word", E_TICK,     discord.ButtonStyle.secondary, "word_remove"),
                ("View Banned Words",  E_LEAF,     discord.ButtonStyle.secondary, "word_list"),
                ("Change Password",    E_CONFIG,   discord.ButtonStyle.secondary, "change_pw"),
                (toggle_label,         toggle_emoji, toggle_style,                "toggle"),
            ],
            [
                ("Reset Security",     E_CROSS,    discord.ButtonStyle.danger,    "reset"),
            ],
        ]

        dispatch = {
            "wl_add":        self._wl_add,
            "wl_remove":     self._wl_remove,
            "wl_list":       self._wl_list,
            "set_logs":      self._set_logs,
            "dl_logs":       self._dl_logs,
            "toggle_spam":   self._toggle_spam,
            "toggle_raid":   self._toggle_raid,
            "toggle_mention":self._toggle_mention,
            "toggle_words":  self._toggle_words,
            "word_add":      self._word_add,
            "word_remove":   self._word_remove,
            "word_list":     self._word_list,
            "change_pw":     self._change_pw,
            "toggle":        self._toggle,
            "reset":         self._reset,
        }

        for row_idx, row in enumerate(rows):
            for label, emoji, style, cid in row:
                btn = discord.ui.Button(label=label, emoji=emoji, style=style, custom_id=cid, row=row_idx)
                btn.callback = dispatch[cid]
                self.add_item(btn)

    async def _wl_add(self, interaction: discord.Interaction):
        await interaction.response.send_modal(WhitelistModal(self.cog, mode="add"))

    async def _wl_remove(self, interaction: discord.Interaction):
        await interaction.response.send_modal(WhitelistModal(self.cog, mode="remove"))

    async def _wl_list(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        users = await SecurityDB.whitelist_list(interaction.guild.id)
        if not users:
            desc = f"{E_WHITE} No users are whitelisted."
        else:
            desc = "\n".join(f"{E_TICK} <@{uid}>" for uid in users[:30])
            if len(users) > 30:
                desc += f"\n*...and {len(users) - 30} more*"
        embed = discord.Embed(title=f"{E_WHITE} Whitelist", description=desc, color=PINK)
        embed.set_footer(text="Shouffle Security • Raze Developments")
        await interaction.followup.send(embed=embed, ephemeral=True)

    async def _set_logs(self, interaction: discord.Interaction):
        await interaction.response.send_modal(LogsChannelModal(self.cog))

    async def _dl_logs(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        actions = await SecurityDB.get_actions(interaction.guild.id)
        data = json.dumps(actions, indent=2)
        buf = BytesIO(data.encode())
        buf.seek(0)
        file = discord.File(buf, filename=f"security_logs_{interaction.guild.id}.json")
        await interaction.followup.send(
            embed=discord.Embed(description=f"{E_DL} Security log exported.", color=PINK),
            file=file,
            ephemeral=True
        )

    async def _toggle_flag(self, interaction: discord.Interaction, col: str, label: str):
        await interaction.response.defer(ephemeral=True)
        data = await SecurityDB.get_guild(interaction.guild.id)
        current = bool(data.get(col, 1))
        new_val = not current
        await SecurityDB.update_guild(interaction.guild.id, **{col: int(new_val)})
        status = f"{E_TICK} **{label}** enabled." if new_val else f"{E_CROSS} **{label}** disabled."
        await interaction.followup.send(
            embed=discord.Embed(description=status, color=GREEN if new_val else RED),
            ephemeral=True
        )

    async def _toggle_spam(self, interaction: discord.Interaction):
        await self._toggle_flag(interaction, "anti_spam", "Anti-Spam")

    async def _toggle_raid(self, interaction: discord.Interaction):
        await self._toggle_flag(interaction, "anti_raid", "Anti-Raid")

    async def _toggle_mention(self, interaction: discord.Interaction):
        await self._toggle_flag(interaction, "anti_mention", "Anti-Mention")

    async def _toggle_words(self, interaction: discord.Interaction):
        await self._toggle_flag(interaction, "word_filter", "Word Filter")

    async def _word_add(self, interaction: discord.Interaction):
        await interaction.response.send_modal(WordFilterModal(self.cog, mode="add"))

    async def _word_remove(self, interaction: discord.Interaction):
        await interaction.response.send_modal(WordFilterModal(self.cog, mode="remove"))

    async def _word_list(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        words = await SecurityDB.get_banned_words(interaction.guild.id)
        if not words:
            desc = f"{E_RESTRICT} No custom banned words set."
        else:
            desc = " • ".join(f"`{w}`" for w in words[:60])
            if len(words) > 60:
                desc += f"\n*...and {len(words) - 60} more*"
        embed = discord.Embed(title=f"{E_RESTRICT} Banned Words", description=desc, color=PINK)
        embed.set_footer(text="Shouffle Security • Raze Developments")
        await interaction.followup.send(embed=embed, ephemeral=True)

    async def _change_pw(self, interaction: discord.Interaction):
        await interaction.response.send_modal(ChangePasswordModal(self.cog))

    async def _toggle(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        data = await SecurityDB.get_guild(interaction.guild.id)
        current = bool(data.get("enabled", 1))
        new_state = not current
        await SecurityDB.update_guild(interaction.guild.id, enabled=int(new_state))
        status = f"{E_TICK} Security **enabled**." if new_state else f"{E_CROSS} Security **disabled**."
        if not new_state:
            bg_cog = interaction.client.get_cog("Backgrounds")
            if bg_cog:
                await bg_cog.on_security_disable(interaction.guild)
        else:
            bg_cog = interaction.client.get_cog("Backgrounds")
            if bg_cog:
                await bg_cog.on_security_enable(interaction.guild)
        await interaction.followup.send(
            embed=discord.Embed(description=status, color=GREEN if new_state else RED),
            ephemeral=True
        )

    async def _reset(self, interaction: discord.Interaction):
        await interaction.response.send_modal(ResetSecurityModal(self.cog))


class Security(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot                        = bot
        self.spam_tracker: dict[int, dict[int, list[float]]] = {}
        self.raid_tracker: dict[int, list[float]]            = {}
        self.raid_active:  dict[int, bool]                   = {}
        self.recent_audit_actions: dict[int, set[int]]       = {}
        self.bot.loop.create_task(SecurityDB.setup())

    async def cog_unload(self):
        pass

    def _match_word(self, content: str, words: list[str]) -> bool:
        lowered = content.lower()
        for word in words:
            pattern = re.compile(rf"(?<![a-z0-9]){re.escape(word)}(?![a-z0-9])", re.IGNORECASE)
            if pattern.search(lowered):
                return True
        return False

    def _has_mass_mentions(self, message: discord.Message) -> bool:
        total = len(message.mentions) + len(message.role_mentions)
        return total >= MASS_MENTION_LIMIT

    async def get_or_create_webhook(self, channel: discord.TextChannel) -> discord.Webhook:
        for wh in await channel.webhooks():
            if wh.name == "Shouffle Security":
                return wh
        return await channel.create_webhook(
            name="Shouffle Security",
            avatar=await self.bot.user.display_avatar.read() if self.bot.user else None
        )

    async def send_security_log(self, guild: discord.Guild, embed: discord.Embed):
        data = await SecurityDB.get_guild(guild.id)
        if not data or not data.get("webhook_url"):
            return
        try:
            async with aiohttp.ClientSession() as session:
                wh = discord.Webhook.from_url(data["webhook_url"], session=session)
                await wh.send(
                    embed=embed,
                    username="Shouffle Security",
                    avatar_url=self.bot.user.display_avatar.url if self.bot.user else None
                )
        except Exception:
            pass

    def build_log_embed(self, title: str, fields: list[tuple], color: int = RED) -> discord.Embed:
        embed = discord.Embed(title=title, color=color, timestamp=datetime.now(timezone.utc))
        for name, value, inline in fields:
            embed.add_field(name=name, value=value, inline=inline)
        embed.set_footer(text="Shouffle Security • Raze Developments")
        return embed

    async def is_protected(self, guild: discord.Guild, user_id: int) -> bool:
        data = await SecurityDB.get_guild(guild.id)
        if not data or not data.get("enabled"):
            return False
        if self.bot.user and user_id == self.bot.user.id:
            return False
        if await SecurityDB.is_whitelisted(guild.id, user_id):
            return False
        return True

    async def check_spam(self, guild_id: int, user_id: int) -> bool:
        now = time.time()
        self.spam_tracker.setdefault(guild_id, {}).setdefault(user_id, [])
        timestamps = [t for t in self.spam_tracker[guild_id][user_id] if now - t < SPAM_WINDOW]
        timestamps.append(now)
        self.spam_tracker[guild_id][user_id] = timestamps
        return len(timestamps) >= SPAM_THRESHOLD

    async def check_raid(self, guild_id: int) -> bool:
        now = time.time()
        self.raid_tracker.setdefault(guild_id, [])
        joins = [t for t in self.raid_tracker[guild_id] if now - t < RAID_JOIN_WINDOW]
        joins.append(now)
        self.raid_tracker[guild_id] = joins
        return len(joins) >= RAID_JOIN_THRESHOLD

    async def punish(self, guild: discord.Guild, member: discord.Member, action: str, reason: str):
        bot_member = guild.get_member(self.bot.user.id)
        if not bot_member:
            return
        if member.top_role >= bot_member.top_role:
            return
        if member.guild_permissions.administrator:
            return

        try:
            if action == PUNISH_BAN:
                if not bot_member.guild_permissions.ban_members:
                    return
                await member.ban(reason=f"[Shouffle Security] {reason}", delete_message_days=0)
            elif action == PUNISH_KICK:
                if not bot_member.guild_permissions.kick_members:
                    return
                await member.kick(reason=f"[Shouffle Security] {reason}")
            elif action == PUNISH_MUTE:
                until = datetime.now(timezone.utc) + timedelta(seconds=MUTE_DURATION_SPAM)
                await member.timeout(until, reason=f"[Shouffle Security] {reason}")
        except (discord.Forbidden, discord.HTTPException):
            return

        await SecurityDB.log_action(guild.id, member.id, action, reason, str(self.bot.user))
        embed = self.build_log_embed(
            title=f"{E_CROSS} Security Action — {action.upper()}",
            fields=[
                ("User",   f"<@{member.id}> `{member.id}`", True),
                ("Action", action.upper(),                   True),
                ("Reason", reason,                           False),
            ],
            color=RED
        )
        await self.send_security_log(guild, embed)

    async def mute_temp(self, guild: discord.Guild, member: discord.Member, seconds: int, reason: str):
        bot_member = guild.get_member(self.bot.user.id)
        if not bot_member:
            return
        if member.top_role >= bot_member.top_role:
            return
        if member.guild_permissions.administrator:
            return
        try:
            until = datetime.now(timezone.utc) + timedelta(seconds=seconds)
            await member.timeout(until, reason=f"[Shouffle Security] {reason}")
        except (discord.Forbidden, discord.HTTPException):
            return
        await SecurityDB.log_action(guild.id, member.id, "mute", reason, str(self.bot.user))
        embed = self.build_log_embed(
            title=f"{E_RESTRICT} Temporary Mute",
            fields=[
                ("User",     f"<@{member.id}> `{member.id}`", True),
                ("Duration", f"{seconds}s",                   True),
                ("Reason",   reason,                          False),
            ],
            color=YELLOW
        )
        await self.send_security_log(guild, embed)

    async def open_dashboard(self, interaction: discord.Interaction, guild_data: dict):
        enabled      = bool(guild_data.get("enabled", 1))
        anti_spam    = bool(guild_data.get("anti_spam", 1))
        anti_raid    = bool(guild_data.get("anti_raid", 1))
        anti_mention = bool(guild_data.get("anti_mention", 1))
        word_filter  = bool(guild_data.get("word_filter", 1))
        logs_ch      = f"<#{guild_data['logs_channel_id']}>" if guild_data.get("logs_channel_id") else "Not set"
        wl_count     = len(await SecurityDB.whitelist_list(interaction.guild.id))
        word_count   = len(await SecurityDB.get_banned_words(interaction.guild.id))

        def flag(v): return f"{E_TICK} ON" if v else f"{E_CROSS} OFF"

        embed = discord.Embed(
            title=f"{E_CONFIG} Security Dashboard",
            description=(
                f"{E_STAR} Welcome to **Shouffle Security** — your server's protection hub.\n\n"
                f"**Status** — {flag(enabled)}\n"
                f"{E_CONFIG} **Logs Channel** — {logs_ch}\n\n"
                f"**Modules**\n"
                f"{E_RESTRICT} Anti-Spam — {flag(anti_spam)}\n"
                f"{E_RESTRICT} Anti-Raid — {flag(anti_raid)}\n"
                f"{E_RESTRICT} Anti-Mention — {flag(anti_mention)}\n"
                f"{E_RESTRICT} Word Filter — {flag(word_filter)}\n\n"
                f"{E_WHITE} **Whitelisted Users** — `{wl_count}`\n"
                f"{E_LEAF} **Banned Words** — `{word_count}`"
            ),
            color=PINK
        )
        embed.set_footer(text="Shouffle Security • Raze Developments")
        view = DashboardView(self, guild_data)
        await interaction.followup.send(embed=embed, view=view, ephemeral=True)

    @commands.command(name="security")
    @commands.has_permissions(administrator=True)
    async def security_prefix(self, ctx: commands.Context):
        try:
            await ctx.message.delete()
        except discord.NotFound:
            pass
        guild_data = await SecurityDB.get_guild(ctx.guild.id)
        if not guild_data:
            embed = discord.Embed(
                title=f"{E_CONFIG} Shouffle Security Setup",
                description=(
                    f"{E_STAR} Protect your server with **Shouffle Security**.\n\n"
                    f"{E_TICK} Password-protected dashboard\n"
                    f"{E_WHITE} Whitelist trusted members\n"
                    f"{E_RESTRICT} Anti-raid & spam protection\n"
                    f"{E_LEAF} Manual word filter\n"
                    f"{E_CONFIG} Audit log enforcement"
                ),
                color=PINK
            )
            embed.set_footer(text="Shouffle Security • Raze Developments")
            view = discord.ui.View(timeout=120)
            btn = discord.ui.Button(label="Set Up Security", emoji=E_CONFIG, style=discord.ButtonStyle.blurple)

            async def setup_cb(interaction: discord.Interaction):
                if interaction.user.id != ctx.author.id:
                    await interaction.response.send_message(
                        embed=discord.Embed(description=f"{E_CROSS} Only the command invoker can do this.", color=RED),
                        ephemeral=True
                    )
                    return
                await interaction.response.send_modal(SetupPasswordModal(self))

            btn.callback = setup_cb
            view.add_item(btn)
            await ctx.send(embed=embed, view=view, delete_after=120)
        else:
            embed = discord.Embed(
                title=f"{E_CONFIG} Shouffle Security",
                description=f"{E_STAR} Enter your password to access the dashboard.",
                color=PINK
            )
            embed.set_footer(text="Shouffle Security • Raze Developments")
            view = discord.ui.View(timeout=120)
            btn = discord.ui.Button(label="Open Dashboard", emoji=E_CONFIG, style=discord.ButtonStyle.blurple)

            async def login_cb(interaction: discord.Interaction):
                if interaction.user.id != ctx.author.id:
                    await interaction.response.send_message(
                        embed=discord.Embed(description=f"{E_CROSS} Only the command invoker can do this.", color=RED),
                        ephemeral=True
                    )
                    return
                await interaction.response.send_modal(PasswordModal(self))

            btn.callback = login_cb
            view.add_item(btn)
            await ctx.send(embed=embed, view=view, delete_after=120)

    @app_commands.command(name="security", description="Open the Shouffle Security dashboard")
    @app_commands.default_permissions(administrator=True)
    async def security_slash(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        guild_data = await SecurityDB.get_guild(interaction.guild.id)
        if not guild_data:
            embed = discord.Embed(
                title=f"{E_CONFIG} Shouffle Security Setup",
                description=(
                    f"{E_STAR} Protect your server with **Shouffle Security**.\n\n"
                    f"{E_TICK} Password-protected dashboard\n"
                    f"{E_WHITE} Whitelist trusted members\n"
                    f"{E_RESTRICT} Anti-raid & spam protection\n"
                    f"{E_LEAF} Manual word filter\n"
                    f"{E_CONFIG} Audit log enforcement"
                ),
                color=PINK
            )
            embed.set_footer(text="Shouffle Security • Raze Developments")
            view = discord.ui.View(timeout=120)
            btn = discord.ui.Button(label="Set Up Security", emoji=E_CONFIG, style=discord.ButtonStyle.blurple)

            async def setup_cb(i: discord.Interaction):
                await i.response.send_modal(SetupPasswordModal(self))

            btn.callback = setup_cb
            view.add_item(btn)
            await interaction.followup.send(embed=embed, view=view, ephemeral=True)
        else:
            embed = discord.Embed(
                title=f"{E_CONFIG} Shouffle Security",
                description=f"{E_STAR} Enter your password to access the dashboard.",
                color=PINK
            )
            embed.set_footer(text="Shouffle Security • Raze Developments")
            view = discord.ui.View(timeout=120)
            btn = discord.ui.Button(label="Open Dashboard", emoji=E_CONFIG, style=discord.ButtonStyle.blurple)

            async def login_cb(i: discord.Interaction):
                await i.response.send_modal(PasswordModal(self))

            btn.callback = login_cb
            view.add_item(btn)
            await interaction.followup.send(embed=embed, view=view, ephemeral=True)

    @commands.Cog.listener()
    async def on_guild_remove(self, guild: discord.Guild):
        await SecurityDB.delete_guild(guild.id)

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        if self.bot.user and member.id == self.bot.user.id:
            return

        data = await SecurityDB.get_guild(member.guild.id)
        if not data or not data.get("enabled"):
            return

        if data.get("anti_raid"):
            is_raid = await self.check_raid(member.guild.id)
            if is_raid:
                if not self.raid_active.get(member.guild.id):
                    self.raid_active[member.guild.id] = True
                    embed = self.build_log_embed(
                        title=f"{E_RESTRICT} Raid Detected",
                        fields=[
                            ("Threshold", f"{RAID_JOIN_THRESHOLD} joins in {RAID_JOIN_WINDOW}s", True),
                            ("Status",    "Lockdown active",                                     True),
                            ("Action",    "New unwhitelisted members will be kicked",            False),
                        ],
                        color=RED
                    )
                    await self.send_security_log(member.guild, embed)
                    asyncio.get_event_loop().call_later(
                        60, lambda: self.raid_active.update({member.guild.id: False})
                    )

                if not await SecurityDB.is_whitelisted(member.guild.id, member.id):
                    try:
                        await member.kick(reason="[Shouffle Security] Raid protection active")
                    except (discord.Forbidden, discord.HTTPException):
                        pass
                    await SecurityDB.log_action(member.guild.id, member.id, "kick", "Raid protection", str(self.bot.user))
                    return

        if member.guild_permissions.administrator and not await SecurityDB.is_whitelisted(member.guild.id, member.id):
            await SecurityDB.whitelist_add(member.guild.id, member.id)

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if not message.guild or message.author.bot:
            return
        if not isinstance(message.author, discord.Member):
            return
        if not await self.is_protected(message.guild, message.author.id):
            return

        guild_data = await SecurityDB.get_guild(message.guild.id)
        if not guild_data:
            return

        if guild_data.get("anti_spam") and await self.check_spam(message.guild.id, message.author.id):
            await self.mute_temp(message.guild, message.author, MUTE_DURATION_SPAM, "Spam detected")
            try:
                await message.delete()
            except discord.NotFound:
                pass
            embed = self.build_log_embed(
                title=f"{E_RESTRICT} Spam Detected",
                fields=[
                    ("User",    f"<@{message.author.id}> `{message.author.id}`", True),
                    ("Channel", message.channel.mention,                          True),
                    ("Action",  f"Muted for {MUTE_DURATION_SPAM}s",              False),
                ],
                color=YELLOW
            )
            await self.send_security_log(message.guild, embed)
            return

        if guild_data.get("anti_mention") and self._has_mass_mentions(message):
            await self.mute_temp(message.guild, message.author, MUTE_DURATION_MENTION, "Mass mention spam")
            try:
                await message.delete()
            except discord.NotFound:
                pass
            embed = self.build_log_embed(
                title=f"{E_RESTRICT} Mass Mention Detected",
                fields=[
                    ("User",     f"<@{message.author.id}> `{message.author.id}`",     True),
                    ("Mentions", str(len(message.mentions) + len(message.role_mentions)), True),
                    ("Action",   f"Muted for {MUTE_DURATION_MENTION}s",                False),
                ],
                color=YELLOW
            )
            await self.send_security_log(message.guild, embed)
            return

        if guild_data.get("word_filter"):
            banned_words = await SecurityDB.get_banned_words(message.guild.id)
            if banned_words and self._match_word(message.content, banned_words):
                await self.mute_temp(message.guild, message.author, MUTE_DURATION_WORD, "Banned word detected")
                try:
                    await message.delete()
                except discord.NotFound:
                    pass
                embed = self.build_log_embed(
                    title=f"{E_RESTRICT} Banned Word Detected",
                    fields=[
                        ("User",    f"<@{message.author.id}> `{message.author.id}`", True),
                        ("Channel", message.channel.mention,                          True),
                        ("Action",  f"Muted for {MUTE_DURATION_WORD}s",              False),
                    ],
                    color=YELLOW
                )
                await self.send_security_log(message.guild, embed)
                return

    @commands.Cog.listener()
    async def on_audit_log_entry_create(self, entry: discord.AuditLogEntry):
        guild = entry.guild
        if not entry.user or entry.user.bot:
            return

        if entry.action in SAFE_ACTIONS:
            return

        if not await self.is_protected(guild, entry.user.id):
            return

        if not isinstance(entry.user, discord.Member):
            return

        key = (entry.user.id, int(entry.action), int(time.time() // 2))
        seen = self.recent_audit_actions.setdefault(guild.id, set())
        if key in seen:
            return
        seen.add(key)
        asyncio.get_event_loop().call_later(4, lambda: seen.discard(key))

        result = TRIGGER_MAP.get(entry.action)
        if not result:
            return

        action, reason = result
        target_info = ""
        if hasattr(entry, "target") and entry.target:
            target_info = f" on `{getattr(entry.target, 'name', entry.target)}`"

        await self.punish(guild, entry.user, action, f"{reason}{target_info}")


async def setup(bot: commands.Bot):
    await bot.add_cog(Security(bot))

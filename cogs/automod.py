import discord
from discord.ext import commands
from discord import app_commands
import aiosqlite
import re
import asyncio
from datetime import datetime, timezone, timedelta
from typing import Optional

DB_PATH = "data/shouffle.db"

COLORS = {
    "success": 0x2ECC71,
    "error":   0xE74C3C,
    "warning": 0xF39C12,
    "info":    0x5865F2,
    "neutral": 0x2C2F33,
    "action":  0x992D22,
}

PUNISHMENTS = ["none", "warn", "timeout", "kick", "ban"]

FILTER_META = {
    "anti_spam":           ("Anti-Spam",             "Deletes messages sent too rapidly by the same user."),
    "anti_invite":         ("Anti-Invite Links",     "Removes Discord invite links posted in chat."),
    "anti_links":          ("Anti-Links",            "Blocks all external URLs (overrides anti-invite when on)."),
    "anti_mention_spam":   ("Mention Spam",          "Removes messages that ping an excessive number of users."),
    "anti_caps":           ("Excessive Caps",        "Removes messages that are mostly uppercase letters."),
    "anti_repeated_chars": ("Repeated Characters",   "Removes messages with long runs of the same character."),
    "bad_words":           ("Bad Words Filter",      "Removes messages containing words on the blocked list."),
    "anti_zalgo":          ("Zalgo Text",            "Strips messages containing heavy Unicode zalgo characters."),
    "anti_massmention":    ("Mass Mention",          "Blocks @everyone and @here pings from non-moderators."),
}

DEFAULT_CONFIG = {
    "enabled":              False,
    "log_channel":          None,
    "anti_spam":            True,
    "anti_spam_threshold":  5,
    "anti_spam_window":     5,
    "anti_invite":          True,
    "anti_links":           False,
    "anti_mention_spam":    True,
    "max_mentions":         5,
    "anti_caps":            True,
    "caps_percent":         70,
    "anti_repeated_chars":  True,
    "max_repeated":         6,
    "bad_words":            True,
    "anti_zalgo":           True,
    "anti_massmention":     True,
    "punishment":           "warn",
    "timeout_duration":     10,
    "warn_threshold_timeout": 3,
    "warn_threshold_kick":    5,
    "warn_threshold_ban":     7,
    "auto_escalate":          True,
}


def build_embed(
    title: str,
    description: str,
    color: int,
    fields: list = None,
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


class ConfigView(discord.ui.View):
    def __init__(self, cog: "AutoMod", guild: discord.Guild, cfg: dict):
        super().__init__(timeout=120)
        self.cog = cog
        self.guild = guild
        self.cfg = cfg
        self.page = "main"
        self._build_main()

    def _build_main(self):
        self.clear_items()
        self.page = "main"

        toggle_label = "🔴 Disable AutoMod" if self.cfg.get("enabled") else "🟢 Enable AutoMod"
        toggle_style = discord.ButtonStyle.danger if self.cfg.get("enabled") else discord.ButtonStyle.success

        btn_toggle = discord.ui.Button(label=toggle_label, style=toggle_style, row=0)
        btn_toggle.callback = self._toggle_enabled
        self.add_item(btn_toggle)

        btn_filters = discord.ui.Button(label="⚙️ Filters", style=discord.ButtonStyle.primary, row=0)
        btn_filters.callback = self._open_filters
        self.add_item(btn_filters)

        btn_thresholds = discord.ui.Button(label="📊 Thresholds", style=discord.ButtonStyle.primary, row=0)
        btn_thresholds.callback = self._open_thresholds
        self.add_item(btn_thresholds)

        btn_punishment = discord.ui.Button(label="⚖️ Punishment", style=discord.ButtonStyle.primary, row=1)
        btn_punishment.callback = self._open_punishment
        self.add_item(btn_punishment)

        btn_escalation = discord.ui.Button(label="📈 Escalation", style=discord.ButtonStyle.primary, row=1)
        btn_escalation.callback = self._open_escalation
        self.add_item(btn_escalation)

        btn_whitelist = discord.ui.Button(label="🛡️ Whitelist", style=discord.ButtonStyle.secondary, row=1)
        btn_whitelist.callback = self._open_whitelist
        self.add_item(btn_whitelist)

    def _build_back_button(self):
        btn_back = discord.ui.Button(label="← Back", style=discord.ButtonStyle.secondary, row=4)
        btn_back.callback = self._go_back
        self.add_item(btn_back)

    async def _refresh_cfg(self):
        self.cfg = await self.cog._get_config(self.guild.id)

    async def _toggle_enabled(self, interaction: discord.Interaction):
        await self._refresh_cfg()
        new_val = 0 if self.cfg.get("enabled") else 1
        await self.cog._set_config(self.guild.id, enabled=new_val)
        await self._refresh_cfg()
        self._build_main()
        embed = self._main_embed()
        await interaction.response.edit_message(embed=embed, view=self)

    async def _go_back(self, interaction: discord.Interaction):
        await self._refresh_cfg()
        self._build_main()
        embed = self._main_embed()
        await interaction.response.edit_message(embed=embed, view=self)

    async def _open_filters(self, interaction: discord.Interaction):
        await self._refresh_cfg()
        self.clear_items()
        self.page = "filters"

        row_idx = 0
        col_idx = 0
        for key, (label, _) in FILTER_META.items():
            is_on = bool(self.cfg.get(key))
            style = discord.ButtonStyle.success if is_on else discord.ButtonStyle.danger
            short = label[:20]
            btn = discord.ui.Button(label=short, style=style, row=row_idx)

            def make_cb(k=key):
                async def cb(itr: discord.Interaction):
                    await self._refresh_cfg()
                    cur = bool(self.cfg.get(k))
                    await self.cog._set_config(self.guild.id, **{k: 0 if cur else 1})
                    await self._refresh_cfg()
                    await self._open_filters(itr)
                return cb

            btn.callback = make_cb()
            self.add_item(btn)
            col_idx += 1
            if col_idx >= 4:
                col_idx = 0
                row_idx += 1

        self._build_back_button()
        embed = build_embed(
            "⚙️ Filter Settings",
            "Click a filter to toggle it on/off. **Green = On**, **Red = Off**.",
            COLORS["info"],
            fields=[
                (label, f"{'✅ On' if self.cfg.get(k) else '❌ Off'}\n*{desc[:60]}*", True)
                for k, (label, desc) in FILTER_META.items()
            ],
            footer=f"{self.guild.name} • AutoMod Filters",
        )
        await interaction.response.edit_message(embed=embed, view=self)

    async def _open_thresholds(self, interaction: discord.Interaction):
        await self._refresh_cfg()
        self.clear_items()
        self.page = "thresholds"

        thresholds = [
            ("spam_threshold", "anti_spam_threshold", "Spam Msg Count", 2, 30),
            ("spam_window",    "anti_spam_window",    "Spam Window (s)", 2, 30),
            ("max_mentions",   "max_mentions",        "Max Mentions",   2, 20),
            ("caps_percent",   "caps_percent",        "Caps % Trigger", 10, 100),
            ("max_repeated",   "max_repeated",        "Repeat Chars",   2, 20),
        ]

        for row_i, (_, col, label, mn, mx) in enumerate(thresholds):
            cur_val = int(self.cfg.get(col, mn))

            btn_dec = discord.ui.Button(label=f"−", style=discord.ButtonStyle.secondary, row=row_i)
            btn_val = discord.ui.Button(
                label=f"{label}: {cur_val}", style=discord.ButtonStyle.primary, disabled=True, row=row_i
            )
            btn_inc = discord.ui.Button(label=f"+", style=discord.ButtonStyle.secondary, row=row_i)

            def make_dec(c=col, mi=mn):
                async def cb(itr: discord.Interaction):
                    await self._refresh_cfg()
                    v = max(mi, int(self.cfg.get(c, mi)) - 1)
                    await self.cog._set_config(self.guild.id, **{c: v})
                    await self._open_thresholds(itr)
                return cb

            def make_inc(c=col, ma=mx):
                async def cb(itr: discord.Interaction):
                    await self._refresh_cfg()
                    v = min(ma, int(self.cfg.get(c, ma)) + 1)
                    await self.cog._set_config(self.guild.id, **{c: v})
                    await self._open_thresholds(itr)
                return cb

            btn_dec.callback = make_dec()
            btn_inc.callback = make_inc()
            self.add_item(btn_dec)
            self.add_item(btn_val)
            self.add_item(btn_inc)

        self._build_back_button()
        embed = build_embed(
            "📊 Threshold Settings",
            "Adjust detection thresholds with **−** and **+**.",
            COLORS["info"],
            fields=[
                (label, f"Current: **{int(self.cfg.get(col, mn))}** (range {mn}–{mx})", False)
                for _, col, label, mn, mx in thresholds
            ],
            footer=f"{self.guild.name} • AutoMod Thresholds",
        )
        await interaction.response.edit_message(embed=embed, view=self)

    async def _open_punishment(self, interaction: discord.Interaction):
        await self._refresh_cfg()
        self.clear_items()
        self.page = "punishment"

        punishments = ["none", "warn", "timeout", "kick", "ban"]
        current = str(self.cfg.get("punishment", "warn"))

        for i, p in enumerate(punishments):
            style = discord.ButtonStyle.success if p == current else discord.ButtonStyle.secondary
            btn = discord.ui.Button(label=p.capitalize(), style=style, row=0)

            def make_cb(pval=p):
                async def cb(itr: discord.Interaction):
                    await self.cog._set_config(self.guild.id, punishment=pval)
                    await self._open_punishment(itr)
                return cb

            btn.callback = make_cb()
            self.add_item(btn)

        timeout_dur = int(self.cfg.get("timeout_duration", 10))
        btn_td_dec = discord.ui.Button(label="− Timeout", style=discord.ButtonStyle.secondary, row=1)
        btn_td_val = discord.ui.Button(
            label=f"Timeout: {timeout_dur}m", style=discord.ButtonStyle.primary, disabled=True, row=1
        )
        btn_td_inc = discord.ui.Button(label="+ Timeout", style=discord.ButtonStyle.secondary, row=1)

        async def dec_timeout(itr: discord.Interaction):
            await self._refresh_cfg()
            v = max(1, int(self.cfg.get("timeout_duration", 10)) - 5)
            await self.cog._set_config(self.guild.id, timeout_duration=v)
            await self._open_punishment(itr)

        async def inc_timeout(itr: discord.Interaction):
            await self._refresh_cfg()
            v = min(40320, int(self.cfg.get("timeout_duration", 10)) + 5)
            await self.cog._set_config(self.guild.id, timeout_duration=v)
            await self._open_punishment(itr)

        btn_td_dec.callback = dec_timeout
        btn_td_val.callback = lambda i: i.response.defer()
        btn_td_inc.callback = inc_timeout
        self.add_item(btn_td_dec)
        self.add_item(btn_td_val)
        self.add_item(btn_td_inc)

        self._build_back_button()

        pun_desc = {
            "none": "Messages are deleted silently.",
            "warn": "User receives a DM warning. Escalates based on warn count.",
            "timeout": f"User is timed out for **{timeout_dur} minutes**.",
            "kick": "User is removed from the server.",
            "ban": "User is permanently banned.",
        }
        embed = build_embed(
            "⚖️ Punishment Settings",
            f"Select the base punishment. Auto-escalation overrides this based on warn count.\n\n"
            + "\n".join(f"**{p.capitalize()}** — {d}" for p, d in pun_desc.items()),
            COLORS["info"],
            fields=[("Current Punishment", f"**{current.capitalize()}**", True),
                    ("Timeout Duration", f"**{timeout_dur} minutes**", True)],
            footer=f"{self.guild.name} • AutoMod Punishment",
        )
        await interaction.response.edit_message(embed=embed, view=self)

    async def _open_escalation(self, interaction: discord.Interaction):
        await self._refresh_cfg()
        self.clear_items()
        self.page = "escalation"

        auto_on = bool(self.cfg.get("auto_escalate", True))
        t_timeout = int(self.cfg.get("warn_threshold_timeout", 3))
        t_kick    = int(self.cfg.get("warn_threshold_kick", 5))
        t_ban     = int(self.cfg.get("warn_threshold_ban", 7))

        btn_toggle = discord.ui.Button(
            label="✅ Auto-Escalate: ON" if auto_on else "❌ Auto-Escalate: OFF",
            style=discord.ButtonStyle.success if auto_on else discord.ButtonStyle.danger,
            row=0,
        )
        async def toggle_escalate(itr: discord.Interaction):
            await self.cog._set_config(self.guild.id, auto_escalate=0 if auto_on else 1)
            await self._open_escalation(itr)
        btn_toggle.callback = toggle_escalate
        self.add_item(btn_toggle)

        escalation_settings = [
            ("warn_threshold_timeout", "Warns → Timeout", t_timeout, 1, 20),
            ("warn_threshold_kick",    "Warns → Kick",    t_kick,    1, 30),
            ("warn_threshold_ban",     "Warns → Ban",     t_ban,     1, 50),
        ]

        for row_i, (col, label, cur_val, mn, mx) in enumerate(escalation_settings, start=1):
            btn_dec = discord.ui.Button(label="−", style=discord.ButtonStyle.secondary, row=row_i)
            btn_val = discord.ui.Button(
                label=f"{label}: {cur_val}", style=discord.ButtonStyle.primary, disabled=True, row=row_i
            )
            btn_inc = discord.ui.Button(label="+", style=discord.ButtonStyle.secondary, row=row_i)

            def make_dec(c=col, mi=mn):
                async def cb(itr: discord.Interaction):
                    await self._refresh_cfg()
                    v = max(mi, int(self.cfg.get(c, mi)) - 1)
                    await self.cog._set_config(self.guild.id, **{c: v})
                    await self._open_escalation(itr)
                return cb

            def make_inc(c=col, ma=mx):
                async def cb(itr: discord.Interaction):
                    await self._refresh_cfg()
                    v = min(ma, int(self.cfg.get(c, ma)) + 1)
                    await self.cog._set_config(self.guild.id, **{c: v})
                    await self._open_escalation(itr)
                return cb

            btn_dec.callback = make_dec()
            btn_inc.callback = make_inc()
            self.add_item(btn_dec)
            self.add_item(btn_val)
            self.add_item(btn_inc)

        self._build_back_button()
        embed = build_embed(
            "📈 Auto-Escalation",
            "When a user accumulates enough warns, the punishment automatically escalates.\n"
            "Each step overrides the base punishment.",
            COLORS["info"],
            fields=[
                ("Auto-Escalation", "✅ Enabled" if auto_on else "❌ Disabled", False),
                ("Timeout Trigger", f"**{t_timeout}** warns", True),
                ("Kick Trigger",    f"**{t_kick}** warns",    True),
                ("Ban Trigger",     f"**{t_ban}** warns",     True),
            ],
            footer=f"{self.guild.name} • AutoMod Escalation",
        )
        await interaction.response.edit_message(embed=embed, view=self)

    async def _open_whitelist(self, interaction: discord.Interaction):
        await self._refresh_cfg()
        whitelist = await self.cog._get_whitelist(self.guild.id)
        self.clear_items()
        self.page = "whitelist"

        async def remove_user(itr: discord.Interaction):
            modal = WhitelistModal(self.cog, self.guild, "user", "remove")
            await itr.response.send_modal(modal)

        async def add_user(itr: discord.Interaction):
            modal = WhitelistModal(self.cog, self.guild, "user", "add")
            await itr.response.send_modal(modal)

        async def remove_role(itr: discord.Interaction):
            modal = WhitelistModal(self.cog, self.guild, "role", "remove")
            await itr.response.send_modal(modal)

        async def add_role(itr: discord.Interaction):
            modal = WhitelistModal(self.cog, self.guild, "role", "add")
            await itr.response.send_modal(modal)

        async def remove_channel(itr: discord.Interaction):
            modal = WhitelistModal(self.cog, self.guild, "channel", "remove")
            await itr.response.send_modal(modal)

        async def add_channel(itr: discord.Interaction):
            modal = WhitelistModal(self.cog, self.guild, "channel", "add")
            await itr.response.send_modal(modal)

        b_add_u = discord.ui.Button(label="+ User",    style=discord.ButtonStyle.success,   row=0)
        b_rem_u = discord.ui.Button(label="− User",    style=discord.ButtonStyle.danger,    row=0)
        b_add_r = discord.ui.Button(label="+ Role",    style=discord.ButtonStyle.success,   row=1)
        b_rem_r = discord.ui.Button(label="− Role",    style=discord.ButtonStyle.danger,    row=1)
        b_add_c = discord.ui.Button(label="+ Channel", style=discord.ButtonStyle.success,   row=2)
        b_rem_c = discord.ui.Button(label="− Channel", style=discord.ButtonStyle.danger,    row=2)

        b_add_u.callback = add_user
        b_rem_u.callback = remove_user
        b_add_r.callback = add_role
        b_rem_r.callback = remove_role
        b_add_c.callback = add_channel
        b_rem_c.callback = remove_channel

        for b in (b_add_u, b_rem_u, b_add_r, b_rem_r, b_add_c, b_rem_c):
            self.add_item(b)

        self._build_back_button()

        def fmt(ids, getter):
            if not ids:
                return "None"
            lines = []
            for i in ids:
                obj = getter(i)
                lines.append(obj.mention if obj else f"`{i}`")
            return "\n".join(lines[:10]) + (f"\n+{len(ids)-10} more" if len(ids) > 10 else "")

        embed = build_embed(
            "🛡️ AutoMod Whitelist",
            "Whitelisted entities are fully exempt from all AutoMod checks.\nUse the buttons to add or remove entries.",
            COLORS["info"],
            fields=[
                ("Users",    fmt(whitelist["user"],    self.guild.get_member),  True),
                ("Roles",    fmt(whitelist["role"],    self.guild.get_role),    True),
                ("Channels", fmt(whitelist["channel"], self.guild.get_channel), True),
            ],
            footer=f"{self.guild.name} • AutoMod Whitelist",
        )
        await interaction.response.edit_message(embed=embed, view=self)

    def _main_embed(self) -> discord.Embed:
        status = "✅ Enabled" if self.cfg.get("enabled") else "❌ Disabled"
        punishment = str(self.cfg.get("punishment", "warn")).capitalize()
        escalate = "✅ On" if self.cfg.get("auto_escalate", True) else "❌ Off"
        filters_on = sum(1 for k in FILTER_META if self.cfg.get(k))
        return build_embed(
            "🛡️ AutoMod Configuration",
            "Use the buttons below to configure every aspect of AutoMod.\nAll changes are saved instantly.",
            COLORS["info"],
            fields=[
                ("Status",          status,                                True),
                ("Base Punishment", punishment,                            True),
                ("Auto-Escalate",   escalate,                              True),
                ("Active Filters",  f"{filters_on}/{len(FILTER_META)}",   True),
                ("Timeout → Kick → Ban",
                 f"At **{self.cfg.get('warn_threshold_timeout',3)}** / "
                 f"**{self.cfg.get('warn_threshold_kick',5)}** / "
                 f"**{self.cfg.get('warn_threshold_ban',7)}** warns", True),
            ],
            footer=f"{self.guild.name} • AutoMod Config",
            thumbnail=self.guild.icon.url if self.guild.icon else None,
        )

    async def on_timeout(self):
        try:
            self.clear_items()
        except Exception:
            pass


class WhitelistModal(discord.ui.Modal):
    entry = discord.ui.TextInput(
        label="Enter ID (user/role/channel)",
        placeholder="Paste the numeric Discord ID here",
        max_length=20,
    )

    def __init__(self, cog: "AutoMod", guild: discord.Guild, entity_type: str, action: str):
        super().__init__(title=f"{'Add to' if action == 'add' else 'Remove from'} Whitelist ({entity_type})")
        self.cog = cog
        self.guild = guild
        self.entity_type = entity_type
        self.action = action

    async def on_submit(self, interaction: discord.Interaction):
        raw = self.entry.value.strip()
        if not raw.isdigit():
            await interaction.response.send_message(
                embed=build_embed("❌ Invalid ID", "Please enter a valid numeric Discord ID.", COLORS["error"]),
                ephemeral=True,
            )
            return
        eid = int(raw)
        async with aiosqlite.connect(DB_PATH) as db:
            if self.action == "add":
                await db.execute(
                    "INSERT OR IGNORE INTO automod_whitelist (guild_id, entity_id, entity_type) VALUES (?, ?, ?)",
                    (self.guild.id, eid, self.entity_type),
                )
            else:
                await db.execute(
                    "DELETE FROM automod_whitelist WHERE guild_id = ? AND entity_id = ?",
                    (self.guild.id, eid),
                )
            await db.commit()
        verb = "added to" if self.action == "add" else "removed from"
        await interaction.response.send_message(
            embed=build_embed(
                "✅ Whitelist Updated",
                f"ID `{eid}` ({self.entity_type}) has been {verb} the whitelist.",
                COLORS["success"],
            ),
            ephemeral=True,
        )


class AutoMod(commands.Cog, name="AutoMod"):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.message_cache: dict[int, list[float]] = {}

    async def cog_load(self):
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("""
                CREATE TABLE IF NOT EXISTS automod_config (
                    guild_id                 INTEGER PRIMARY KEY,
                    enabled                  INTEGER DEFAULT 0,
                    log_channel              INTEGER,
                    anti_spam                INTEGER DEFAULT 1,
                    anti_spam_threshold      INTEGER DEFAULT 5,
                    anti_spam_window         INTEGER DEFAULT 5,
                    anti_invite              INTEGER DEFAULT 1,
                    anti_links               INTEGER DEFAULT 0,
                    anti_mention_spam        INTEGER DEFAULT 1,
                    max_mentions             INTEGER DEFAULT 5,
                    anti_caps                INTEGER DEFAULT 1,
                    caps_percent             INTEGER DEFAULT 70,
                    anti_repeated_chars      INTEGER DEFAULT 1,
                    max_repeated             INTEGER DEFAULT 6,
                    bad_words                INTEGER DEFAULT 1,
                    anti_zalgo               INTEGER DEFAULT 1,
                    anti_massmention         INTEGER DEFAULT 1,
                    punishment               TEXT DEFAULT 'warn',
                    timeout_duration         INTEGER DEFAULT 10,
                    warn_threshold_timeout   INTEGER DEFAULT 3,
                    warn_threshold_kick      INTEGER DEFAULT 5,
                    warn_threshold_ban       INTEGER DEFAULT 7,
                    auto_escalate            INTEGER DEFAULT 1
                )
            """)
            await db.execute("""
                CREATE TABLE IF NOT EXISTS automod_bad_words (
                    guild_id INTEGER,
                    word     TEXT,
                    PRIMARY KEY (guild_id, word)
                )
            """)
            await db.execute("""
                CREATE TABLE IF NOT EXISTS automod_global_words (
                    word TEXT PRIMARY KEY
                )
            """)
            await db.execute("""
                CREATE TABLE IF NOT EXISTS automod_whitelist (
                    guild_id    INTEGER,
                    entity_id   INTEGER,
                    entity_type TEXT,
                    PRIMARY KEY (guild_id, entity_id)
                )
            """)
            await db.execute("""
                CREATE TABLE IF NOT EXISTS automod_warns (
                    guild_id INTEGER,
                    user_id  INTEGER,
                    count    INTEGER DEFAULT 0,
                    PRIMARY KEY (guild_id, user_id)
                )
            """)
            await db.commit()

    async def _get_config(self, guild_id: int) -> dict:
        async with aiosqlite.connect(DB_PATH) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT * FROM automod_config WHERE guild_id = ?", (guild_id,)
            ) as cursor:
                row = await cursor.fetchone()
        if row is None:
            async with aiosqlite.connect(DB_PATH) as db:
                await db.execute(
                    "INSERT OR IGNORE INTO automod_config (guild_id) VALUES (?)", (guild_id,)
                )
                await db.commit()
            return dict(DEFAULT_CONFIG)
        return dict(row)

    async def _set_config(self, guild_id: int, **kwargs):
        cols = ", ".join(f"{k} = ?" for k in kwargs)
        vals = list(kwargs.values()) + [guild_id]
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                f"UPDATE automod_config SET {cols} WHERE guild_id = ?", vals
            )
            await db.commit()

    async def _get_bad_words(self, guild_id: int) -> list:
        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute(
                "SELECT word FROM automod_bad_words WHERE guild_id = ?", (guild_id,)
            ) as cursor:
                guild_words = [r[0] for r in await cursor.fetchall()]
            async with db.execute("SELECT word FROM automod_global_words") as cursor:
                global_words = [r[0] for r in await cursor.fetchall()]
        return list(set(guild_words + global_words))

    async def _get_whitelist(self, guild_id: int) -> dict:
        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute(
                "SELECT entity_id, entity_type FROM automod_whitelist WHERE guild_id = ?",
                (guild_id,),
            ) as cursor:
                rows = await cursor.fetchall()
        result = {"user": [], "role": [], "channel": []}
        for eid, etype in rows:
            result.setdefault(etype, []).append(eid)
        return result

    async def _get_warn_count(self, guild_id: int, user_id: int) -> int:
        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute(
                "SELECT count FROM automod_warns WHERE guild_id = ? AND user_id = ?",
                (guild_id, user_id),
            ) as cursor:
                row = await cursor.fetchone()
        return row[0] if row else 0

    async def _increment_warn(self, guild_id: int, user_id: int) -> int:
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                """INSERT INTO automod_warns (guild_id, user_id, count) VALUES (?, ?, 1)
                   ON CONFLICT(guild_id, user_id) DO UPDATE SET count = count + 1""",
                (guild_id, user_id),
            )
            await db.commit()
        return await self._get_warn_count(guild_id, user_id)

    async def _send_log(self, guild: discord.Guild, cfg: dict, embed: discord.Embed):
        log_id = cfg.get("log_channel")
        if not log_id:
            return
        channel = guild.get_channel(int(log_id))
        if channel:
            try:
                await channel.send(embed=embed)
            except (discord.Forbidden, discord.HTTPException):
                pass

    async def _apply_punishment(self, message: discord.Message, cfg: dict, violation: str):
        guild = message.guild
        member = message.author

        try:
            await message.delete()
        except (discord.Forbidden, discord.NotFound):
            pass

        base_punishment = cfg.get("punishment", "warn")
        auto_escalate = bool(cfg.get("auto_escalate", True))

        warn_count = await self._increment_warn(guild.id, member.id)

        effective_punishment = base_punishment

        if auto_escalate:
            t_ban     = int(cfg.get("warn_threshold_ban",     7))
            t_kick    = int(cfg.get("warn_threshold_kick",    5))
            t_timeout = int(cfg.get("warn_threshold_timeout", 3))

            if warn_count >= t_ban:
                effective_punishment = "ban"
            elif warn_count >= t_kick:
                effective_punishment = "kick"
            elif warn_count >= t_timeout:
                effective_punishment = "timeout"
            elif base_punishment == "none":
                effective_punishment = "none"

        action_taken = "Message Deleted"

        if effective_punishment == "warn":
            action_taken = f"Warned (#{warn_count})"
            try:
                await member.send(embed=build_embed(
                    "⚠️ AutoMod Warning",
                    f"You received a warning in **{guild.name}**.\n\n"
                    f"**Reason:** {violation}\n"
                    f"**Total Warnings:** {warn_count}",
                    COLORS["warning"],
                    footer="Continued violations will result in escalating punishments.",
                ))
            except discord.Forbidden:
                pass

        elif effective_punishment == "timeout":
            duration = int(cfg.get("timeout_duration", 10))
            until = datetime.now(timezone.utc) + timedelta(minutes=duration)
            try:
                await member.timeout(until, reason=f"AutoMod: {violation}")
                action_taken = f"Timed out {duration}m (Warn #{warn_count})"
                try:
                    await member.send(embed=build_embed(
                        "🔇 You've Been Timed Out",
                        f"**Server:** {guild.name}\n**Reason:** {violation}\n"
                        f"**Duration:** {duration} minutes\n**Total Warnings:** {warn_count}",
                        COLORS["warning"],
                        footer="Further violations may result in a kick or ban.",
                    ))
                except discord.Forbidden:
                    pass
            except (discord.Forbidden, discord.HTTPException):
                action_taken = "Timeout Failed (Missing Perms)"

        elif effective_punishment == "kick":
            try:
                try:
                    await member.send(embed=build_embed(
                        "👢 You've Been Kicked",
                        f"**Server:** {guild.name}\n**Reason:** {violation}\n"
                        f"**Total Warnings:** {warn_count}",
                        COLORS["error"],
                        footer="You may rejoin, but further violations may result in a ban.",
                    ))
                except discord.Forbidden:
                    pass
                await member.kick(reason=f"AutoMod: {violation} (Warn #{warn_count})")
                action_taken = f"Kicked (Warn #{warn_count})"
            except (discord.Forbidden, discord.HTTPException):
                action_taken = "Kick Failed (Missing Perms)"

        elif effective_punishment == "ban":
            try:
                try:
                    await member.send(embed=build_embed(
                        "🔨 You've Been Banned",
                        f"**Server:** {guild.name}\n**Reason:** {violation}\n"
                        f"**Total Warnings:** {warn_count}",
                        COLORS["error"],
                        footer="This action is permanent.",
                    ))
                except discord.Forbidden:
                    pass
                await member.ban(reason=f"AutoMod: {violation} (Warn #{warn_count})", delete_message_days=1)
                action_taken = f"Banned (Warn #{warn_count})"
            except (discord.Forbidden, discord.HTTPException):
                action_taken = "Ban Failed (Missing Perms)"

        if effective_punishment != "none":
            notice_embed = build_embed(
                "🛡️ AutoMod Action",
                f"{member.mention}, your message was removed.\n**Reason:** {violation}",
                COLORS["error"],
                fields=[
                    ("Action", action_taken, True),
                    ("Channel", message.channel.mention, True),
                    ("Warnings", str(warn_count), True),
                ],
                footer="AutoMod System",
            )
            try:
                notice = await message.channel.send(embed=notice_embed)
                await asyncio.sleep(6)
                await notice.delete()
            except (discord.Forbidden, discord.NotFound, discord.HTTPException):
                pass

        log_embed = build_embed(
            "🛡️ AutoMod Log",
            f"**Violation:** {violation}",
            COLORS["action"],
            fields=[
                ("User",    f"{member.mention} (`{member.id}`)", True),
                ("Channel", message.channel.mention,             True),
                ("Action",  action_taken,                        True),
                ("Warns",   str(warn_count),                     True),
                ("Message", f"```{message.content[:300] or '[empty]'}```", False),
            ],
            footer=f"{guild.name} • AutoMod",
            thumbnail=member.display_avatar.url,
        )
        await self._send_log(guild, cfg, log_embed)

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot or not message.guild:
            return

        cfg = await self._get_config(message.guild.id)
        if not cfg.get("enabled"):
            return

        whitelist = await self._get_whitelist(message.guild.id)
        if message.author.id in whitelist["user"]:
            return
        if message.channel.id in whitelist["channel"]:
            return
        if any(rid in whitelist["role"] for rid in [r.id for r in message.author.roles]):
            return
        if message.author.guild_permissions.administrator:
            return

        checks = [
            ("anti_spam",           self._check_spam),
            ("anti_invite",         self._check_invite),
            ("anti_links",          self._check_links),
            ("anti_mention_spam",   self._check_mention_spam),
            ("anti_massmention",    self._check_mass_mention),
            ("anti_caps",           self._check_caps),
            ("anti_repeated_chars", self._check_repeated_chars),
            ("anti_zalgo",          self._check_zalgo),
            ("bad_words",           self._check_bad_words),
        ]

        for key, func in checks:
            if cfg.get(key):
                if await func(message, cfg):
                    return

    async def _check_spam(self, message: discord.Message, cfg: dict) -> bool:
        uid = message.author.id
        now = message.created_at.timestamp()
        window = int(cfg.get("anti_spam_window", 5))
        threshold = int(cfg.get("anti_spam_threshold", 5))
        if uid not in self.message_cache:
            self.message_cache[uid] = []
        self.message_cache[uid] = [t for t in self.message_cache[uid] if now - t < window]
        self.message_cache[uid].append(now)
        if len(self.message_cache[uid]) > threshold:
            self.message_cache[uid] = []
            await self._apply_punishment(message, cfg, "Message spam detected")
            return True
        return False

    async def _check_invite(self, message: discord.Message, cfg: dict) -> bool:
        if cfg.get("anti_links"):
            return False
        pattern = re.compile(
            r"(discord\.gg|discord\.com/invite|discordapp\.com/invite)/[a-zA-Z0-9\-]+"
        )
        if pattern.search(message.content):
            await self._apply_punishment(message, cfg, "Discord invite link posted")
            return True
        return False

    async def _check_links(self, message: discord.Message, cfg: dict) -> bool:
        if re.search(r"https?://[^\s]+", message.content):
            await self._apply_punishment(message, cfg, "External link posted")
            return True
        return False

    async def _check_mention_spam(self, message: discord.Message, cfg: dict) -> bool:
        limit = int(cfg.get("max_mentions", 5))
        if len(message.mentions) >= limit:
            await self._apply_punishment(message, cfg, f"Excessive mentions ({len(message.mentions)})")
            return True
        return False

    async def _check_mass_mention(self, message: discord.Message, cfg: dict) -> bool:
        if message.mention_everyone:
            if not message.author.guild_permissions.mention_everyone:
                await self._apply_punishment(message, cfg, "Unauthorized @everyone / @here mention")
                return True
        return False

    async def _check_caps(self, message: discord.Message, cfg: dict) -> bool:
        content = message.content
        if len(content) < 10:
            return False
        letters = [c for c in content if c.isalpha()]
        if not letters:
            return False
        ratio = sum(1 for c in letters if c.isupper()) / len(letters) * 100
        if ratio >= int(cfg.get("caps_percent", 70)):
            await self._apply_punishment(message, cfg, f"Excessive caps ({int(ratio)}%)")
            return True
        return False

    async def _check_repeated_chars(self, message: discord.Message, cfg: dict) -> bool:
        limit = int(cfg.get("max_repeated", 6))
        if re.search(r"(.)\1{" + str(limit) + r",}", message.content):
            await self._apply_punishment(message, cfg, "Repeated character spam")
            return True
        return False

    async def _check_zalgo(self, message: discord.Message, cfg: dict) -> bool:
        if re.search(
            r"[\u0300-\u036f\u0489\u1dc0-\u1dff\u20d0-\u20ff\ufe20-\ufe2f]{3,}",
            message.content,
        ):
            await self._apply_punishment(message, cfg, "Zalgo / distorted Unicode text")
            return True
        return False

    async def _check_bad_words(self, message: discord.Message, cfg: dict) -> bool:
        words = await self._get_bad_words(message.guild.id)
        if not words:
            return False
        content_lower = message.content.lower()
        for word in words:
            if re.search(r"\b" + re.escape(word.lower()) + r"\b", content_lower):
                await self._apply_punishment(message, cfg, "Prohibited language")
                return True
        return False

    async def _is_owner(self, ctx_or_interaction) -> bool:
        if isinstance(ctx_or_interaction, commands.Context):
            return await self.bot.is_owner(ctx_or_interaction.author)
        return await self.bot.is_owner(ctx_or_interaction.user)

    async def _send_overview(self, ctx: commands.Context):
        cfg = await self._get_config(ctx.guild.id)
        status = "✅ Enabled" if cfg.get("enabled") else "❌ Disabled"
        whitelist = await self._get_whitelist(ctx.guild.id)
        punishment = str(cfg.get("punishment", "warn")).capitalize()
        escalate = "✅ On" if cfg.get("auto_escalate", True) else "❌ Off"
        filters_on = sum(1 for k in FILTER_META if cfg.get(k))
        log_ch = ctx.guild.get_channel(int(cfg["log_channel"])) if cfg.get("log_channel") else None
        embed = build_embed(
            "🛡️ AutoMod System",
            "Automated moderation for this server.",
            COLORS["info"],
            fields=[
                ("Status",          status,                              True),
                ("Punishment",      punishment,                          True),
                ("Auto-Escalate",   escalate,                            True),
                ("Active Filters",  f"{filters_on}/{len(FILTER_META)}", True),
                ("Log Channel",     log_ch.mention if log_ch else "Not set", True),
                ("Whitelisted",
                 f"Users: {len(whitelist['user'])} • "
                 f"Roles: {len(whitelist['role'])} • "
                 f"Channels: {len(whitelist['channel'])}", True),
                ("Escalation Thresholds",
                 f"Timeout @ **{cfg.get('warn_threshold_timeout',3)}** warns • "
                 f"Kick @ **{cfg.get('warn_threshold_kick',5)}** warns • "
                 f"Ban @ **{cfg.get('warn_threshold_ban',7)}** warns", False),
            ],
            footer=f"Requested by {ctx.author} • {ctx.guild.name}",
            thumbnail=ctx.guild.icon.url if ctx.guild.icon else None,
        )
        await ctx.send(embed=embed)

    @commands.group(name="automod", aliases=["am"], invoke_without_command=True)
    @commands.has_permissions(manage_guild=True)
    async def automod(self, ctx: commands.Context):
        await self._send_overview(ctx)

    @automod.command(name="enable")
    @commands.has_permissions(manage_guild=True)
    async def automod_enable(self, ctx: commands.Context):
        cfg = await self._get_config(ctx.guild.id)
        if cfg.get("enabled"):
            await ctx.send(embed=build_embed("Already Active", "AutoMod is already enabled.", COLORS["warning"]))
            return
        await self._set_config(ctx.guild.id, enabled=1)
        await ctx.send(embed=build_embed(
            "✅ AutoMod Enabled",
            "All configured filters are now active.",
            COLORS["success"],
            fields=[("Activated By", ctx.author.mention, True)],
            footer=f"{ctx.guild.name} • AutoMod",
        ))

    @automod.command(name="disable")
    @commands.has_permissions(manage_guild=True)
    async def automod_disable(self, ctx: commands.Context):
        cfg = await self._get_config(ctx.guild.id)
        if not cfg.get("enabled"):
            await ctx.send(embed=build_embed("Already Inactive", "AutoMod is already disabled.", COLORS["warning"]))
            return
        await self._set_config(ctx.guild.id, enabled=0)
        await ctx.send(embed=build_embed(
            "❌ AutoMod Disabled",
            "All filters have been deactivated.",
            COLORS["error"],
            fields=[("Deactivated By", ctx.author.mention, True)],
            footer=f"{ctx.guild.name} • AutoMod",
        ))

    @automod.command(name="config")
    @commands.has_permissions(manage_guild=True)
    async def automod_config(self, ctx: commands.Context):
        cfg = await self._get_config(ctx.guild.id)
        view = ConfigView(self, ctx.guild, cfg)
        embed = view._main_embed()
        await ctx.send(embed=embed, view=view)

    @automod.error
    @automod_enable.error
    @automod_disable.error
    @automod_config.error
    async def automod_error(self, ctx: commands.Context, error: commands.CommandError):
        if isinstance(error, commands.MissingPermissions):
            await ctx.send(embed=build_embed(
                "🔒 Access Denied",
                "You require the **Manage Server** permission to use AutoMod commands.",
                COLORS["error"],
                footer=f"Requested by {ctx.author}",
            ))
        elif isinstance(error, commands.BadArgument):
            await ctx.send(embed=build_embed("⚠️ Invalid Argument", str(error), COLORS["warning"]))

    automod_app = app_commands.Group(
        name="automod",
        description="Configure AutoMod for this server.",
        default_permissions=discord.Permissions(manage_guild=True),
    )

    @automod_app.command(name="enable", description="Enable the AutoMod system.")
    async def slash_enable(self, interaction: discord.Interaction):
        cfg = await self._get_config(interaction.guild.id)
        if cfg.get("enabled"):
            await interaction.response.send_message(
                embed=build_embed("Already Active", "AutoMod is already enabled.", COLORS["warning"]),
                ephemeral=True,
            )
            return
        await self._set_config(interaction.guild.id, enabled=1)
        await interaction.response.send_message(
            embed=build_embed(
                "✅ AutoMod Enabled",
                "All configured filters are now active.",
                COLORS["success"],
                fields=[("Activated By", interaction.user.mention, True)],
            ),
        )

    @automod_app.command(name="disable", description="Disable the AutoMod system.")
    async def slash_disable(self, interaction: discord.Interaction):
        cfg = await self._get_config(interaction.guild.id)
        if not cfg.get("enabled"):
            await interaction.response.send_message(
                embed=build_embed("Already Inactive", "AutoMod is already disabled.", COLORS["warning"]),
                ephemeral=True,
            )
            return
        await self._set_config(interaction.guild.id, enabled=0)
        await interaction.response.send_message(
            embed=build_embed(
                "❌ AutoMod Disabled",
                "All filters have been deactivated.",
                COLORS["error"],
                fields=[("Deactivated By", interaction.user.mention, True)],
            ),
        )

    @automod_app.command(name="config", description="Open the interactive AutoMod configuration panel.")
    async def slash_config(self, interaction: discord.Interaction):
        cfg = await self._get_config(interaction.guild.id)
        view = ConfigView(self, interaction.guild, cfg)
        embed = view._main_embed()
        await interaction.response.send_message(embed=embed, view=view)


async def setup(bot: commands.Bot):
    await bot.add_cog(AutoMod(bot))

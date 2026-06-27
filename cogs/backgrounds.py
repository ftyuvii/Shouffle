import discord
from discord.ext import commands, tasks
import aiosqlite
import asyncio
import re
import time
import logging
from datetime import datetime, timezone

log = logging.getLogger("shouffle.backgrounds")

PINK   = 0xFFB6C1
RED    = 0xFF4444
GREEN  = 0x57F287
YELLOW = 0xFFD700

DB = "shouffle.db"

E_RESTRICT = "🚧"
E_TICK     = "✅"
E_CROSS    = "❌"
E_CONFIG   = "🌀"
E_LEAF     = "🍀"
E_STAR     = "✨"

LINK_PATTERN = re.compile(
    r"(?:https?://|www\.)?"
    r"(?:"
    r"(?:youtu\.be|youtube\.com|music\.youtube\.com)"
    r"|(?:instagram\.com|instagr\.am)"
    r"|(?:discord\.gg|discord\.com/invite|discordapp\.com/invite)"
    r"|(?:tiktok\.com|vm\.tiktok\.com)"
    r"|(?:twitter\.com|x\.com|t\.co)"
    r"|(?:twitch\.tv)"
    r"|(?:reddit\.com|redd\.it)"
    r"|(?:facebook\.com|fb\.com|fb\.me)"
    r"|(?:snapchat\.com|snap\.com)"
    r"|(?:t\.me|telegram\.me|telegram\.org)"
    r"|(?:open\.spotify\.com|spoti\.fi)"
    r"|(?:linktr\.ee)"
    r"|(?:bit\.ly|tinyurl\.com|goo\.gl|ow\.ly|buff\.ly|rebrand\.ly|cutt\.ly|short\.io|is\.gd|shorte\.st)"
    r"|(?:[a-zA-Z0-9\-]+\.(?:com|net|org|io|gg|xyz|co|me|tv|live|app|link|site|online|store|shop|info|biz|us|uk|ca|de|fr|jp|au|ru|in|br|gg))"
    r")"
    r"(?:[/\?#][^\s]*)?",
    re.IGNORECASE
)

MUTE_DURATION_LINK = 180

CACHE_FLUSH_INTERVAL  = 300
HEALTH_CHECK_INTERVAL = 600
ORPHAN_CLEAN_INTERVAL = 3600
DB_VACUUM_INTERVAL    = 86400
AUDIT_PRUNE_INTERVAL  = 43200
AUDIT_MAX_AGE_DAYS    = 30


class BackgroundsDB:
    @staticmethod
    async def setup():
        async with aiosqlite.connect(DB) as db:
            await db.execute("""
                CREATE TABLE IF NOT EXISTS bg_link_violations (
                    id         INTEGER PRIMARY KEY AUTOINCREMENT,
                    guild_id   INTEGER,
                    user_id    INTEGER,
                    channel_id INTEGER,
                    url        TEXT,
                    timestamp  INTEGER
                )
            """)
            await db.execute("""
                CREATE TABLE IF NOT EXISTS bg_guild_stats (
                    guild_id           INTEGER PRIMARY KEY,
                    links_blocked      INTEGER DEFAULT 0,
                    spam_blocked       INTEGER DEFAULT 0,
                    raids_blocked      INTEGER DEFAULT 0,
                    last_cache_flush   INTEGER DEFAULT 0,
                    last_health_check  INTEGER DEFAULT 0,
                    last_vacuum        INTEGER DEFAULT 0
                )
            """)
            await db.execute("""
                CREATE TABLE IF NOT EXISTS bg_channel_whitelist (
                    guild_id   INTEGER,
                    channel_id INTEGER,
                    PRIMARY KEY (guild_id, channel_id)
                )
            """)
            await db.commit()

    @staticmethod
    async def log_link_violation(guild_id: int, user_id: int, channel_id: int, url: str):
        async with aiosqlite.connect(DB) as db:
            await db.execute(
                "INSERT INTO bg_link_violations (guild_id, user_id, channel_id, url, timestamp) VALUES (?, ?, ?, ?, ?)",
                (guild_id, user_id, channel_id, url, int(time.time()))
            )
            await db.execute("""
                INSERT INTO bg_guild_stats (guild_id, links_blocked) VALUES (?, 1)
                ON CONFLICT(guild_id) DO UPDATE SET links_blocked = links_blocked + 1
            """, (guild_id,))
            await db.commit()

    @staticmethod
    async def get_stats(guild_id: int) -> dict:
        async with aiosqlite.connect(DB) as db:
            async with db.execute("SELECT * FROM bg_guild_stats WHERE guild_id = ?", (guild_id,)) as cur:
                row = await cur.fetchone()
                if not row:
                    return {}
                cols = [d[0] for d in cur.description]
                return dict(zip(cols, row))

    @staticmethod
    async def is_channel_whitelisted(guild_id: int, channel_id: int) -> bool:
        async with aiosqlite.connect(DB) as db:
            async with db.execute(
                "SELECT 1 FROM bg_channel_whitelist WHERE guild_id = ? AND channel_id = ?",
                (guild_id, channel_id)
            ) as cur:
                return await cur.fetchone() is not None

    @staticmethod
    async def add_channel_whitelist(guild_id: int, channel_id: int):
        async with aiosqlite.connect(DB) as db:
            await db.execute(
                "INSERT OR IGNORE INTO bg_channel_whitelist (guild_id, channel_id) VALUES (?, ?)",
                (guild_id, channel_id)
            )
            await db.commit()

    @staticmethod
    async def remove_channel_whitelist(guild_id: int, channel_id: int):
        async with aiosqlite.connect(DB) as db:
            await db.execute(
                "DELETE FROM bg_channel_whitelist WHERE guild_id = ? AND channel_id = ?",
                (guild_id, channel_id)
            )
            await db.commit()

    @staticmethod
    async def prune_old_violations(max_age_days: int):
        cutoff = int(time.time()) - (max_age_days * 86400)
        async with aiosqlite.connect(DB) as db:
            await db.execute("DELETE FROM bg_link_violations WHERE timestamp < ?", (cutoff,))
            await db.commit()

    @staticmethod
    async def get_all_protected_guilds() -> list[int]:
        async with aiosqlite.connect(DB) as db:
            async with db.execute("SELECT guild_id FROM security_guilds WHERE enabled = 1") as cur:
                rows = await cur.fetchall()
                return [r[0] for r in rows]


class Backgrounds(commands.Cog, name="Backgrounds"):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self._link_cache:    dict[int, dict[int, list[float]]] = {}
        self._muted_cache:   dict[tuple[int, int], float]      = {}
        self._event_cache:   dict[int, set]                    = {}
        self._warn_cache:    dict[tuple[int, int], int]         = {}
        self._protected_ids: set[int]                          = set()
        self._ready = False

    async def cog_load(self):
        await BackgroundsDB.setup()
        self._protected_ids = set(await BackgroundsDB.get_all_protected_guilds())
        self._cache_cleaner.start()
        self._health_check.start()
        self._orphan_cleaner.start()
        self._db_vacuum.start()
        self._audit_pruner.start()
        self._ready = True
        log.info("Backgrounds cog loaded — %d protected guilds", len(self._protected_ids))

    async def cog_unload(self):
        self._cache_cleaner.cancel()
        self._health_check.cancel()
        self._orphan_cleaner.cancel()
        self._db_vacuum.cancel()
        self._audit_pruner.cancel()
        log.info("Backgrounds cog unloaded")

    def _is_protected(self, guild_id: int) -> bool:
        return guild_id in self._protected_ids

    async def _is_security_enabled(self, guild_id: int) -> bool:
        async with aiosqlite.connect(DB) as db:
            async with db.execute(
                "SELECT enabled FROM security_guilds WHERE guild_id = ?", (guild_id,)
            ) as cur:
                row = await cur.fetchone()
                return bool(row and row[0])

    async def _get_security_data(self, guild_id: int) -> dict | None:
        async with aiosqlite.connect(DB) as db:
            async with db.execute("SELECT * FROM security_guilds WHERE guild_id = ?", (guild_id,)) as cur:
                row = await cur.fetchone()
                if not row:
                    return None
                cols = [d[0] for d in cur.description]
                return dict(zip(cols, row))

    async def _is_user_whitelisted(self, guild_id: int, user_id: int) -> bool:
        async with aiosqlite.connect(DB) as db:
            async with db.execute(
                "SELECT 1 FROM security_whitelist WHERE guild_id = ? AND user_id = ?", (guild_id, user_id)
            ) as cur:
                return await cur.fetchone() is not None

    async def _get_or_create_mute_role(self, guild: discord.Guild) -> discord.Role | None:
        role = discord.utils.get(guild.roles, name="Muted")
        if role:
            return role
        try:
            role = await guild.create_role(name="Muted", reason="[Shouffle Backgrounds] Auto-created mute role")
            for channel in guild.channels:
                try:
                    await channel.set_permissions(role, send_messages=False, speak=False, add_reactions=False)
                except (discord.Forbidden, discord.HTTPException):
                    pass
            return role
        except (discord.Forbidden, discord.HTTPException):
            return None

    async def _mute_member(self, guild: discord.Guild, member: discord.Member, duration: int, reason: str):
        key = (guild.id, member.id)
        if key in self._muted_cache and self._muted_cache[key] > time.time():
            return
        self._muted_cache[key] = time.time() + duration

        role = await self._get_or_create_mute_role(guild)
        if not role:
            return
        try:
            await member.add_roles(role, reason=f"[Shouffle Backgrounds] {reason}")
            await asyncio.sleep(duration)
            if role in member.roles:
                await member.remove_roles(role, reason="[Shouffle Backgrounds] Mute expired")
        except (discord.Forbidden, discord.HTTPException):
            pass
        finally:
            self._muted_cache.pop(key, None)

    async def _send_bg_log(self, guild: discord.Guild, embed: discord.Embed):
        data = await self._get_security_data(guild.id)
        if not data:
            return
        webhook_url = data.get("webhook_url")
        logs_channel_id = data.get("logs_channel_id")
        if webhook_url:
            try:
                import aiohttp
                async with aiohttp.ClientSession() as session:
                    wh = discord.Webhook.from_url(webhook_url, session=session)
                    await wh.send(
                        embed=embed,
                        username="Shouffle Backgrounds",
                        avatar_url=self.bot.user.display_avatar.url if self.bot.user else None
                    )
                    return
            except Exception:
                pass
        if logs_channel_id:
            ch = guild.get_channel(logs_channel_id)
            if ch and isinstance(ch, discord.TextChannel):
                try:
                    await ch.send(embed=embed)
                except (discord.Forbidden, discord.HTTPException):
                    pass

    def _extract_links(self, content: str) -> list[str]:
        return LINK_PATTERN.findall(content)

    def _track_link(self, guild_id: int, user_id: int) -> bool:
        now = time.time()
        guild_map = self._link_cache.setdefault(guild_id, {})
        user_hits = guild_map.setdefault(user_id, [])
        user_hits[:] = [t for t in user_hits if now - t < 10]
        user_hits.append(now)
        return len(user_hits) >= 2

    async def on_security_enable(self, guild: discord.Guild):
        self._protected_ids.add(guild.id)
        log.info("Backgrounds activated for guild %d (%s)", guild.id, guild.name)

    async def on_security_disable(self, guild: discord.Guild):
        self._protected_ids.discard(guild.id)
        self._link_cache.pop(guild.id, None)
        self._event_cache.pop(guild.id, None)
        log.info("Backgrounds deactivated for guild %d (%s)", guild.id, guild.name)

    @commands.Cog.listener()
    async def on_ready(self):
        self._protected_ids = set(await BackgroundsDB.get_all_protected_guilds())
        log.info("Backgrounds synced on ready — %d protected guilds", len(self._protected_ids))

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if not message.guild or message.author.bot:
            return
        if not isinstance(message.author, discord.Member):
            return
        if not self._is_protected(message.guild.id):
            return

        if message.author.guild_permissions.administrator:
            return
        if await self._is_user_whitelisted(message.guild.id, message.author.id):
            return
        if await BackgroundsDB.is_channel_whitelisted(message.guild.id, message.channel.id):
            return

        links = self._extract_links(message.content)
        if not links:
            return

        repeated = self._track_link(message.guild.id, message.author.id)

        try:
            await message.delete()
        except (discord.NotFound, discord.Forbidden):
            pass

        url_display = links[0][:60] + ("..." if len(links[0]) > 60 else "")

        embed = discord.Embed(
            title=f"{E_RESTRICT} Link Blocked",
            color=RED
        )
        embed.add_field(name="User",    value=f"<@{message.author.id}> `{message.author.id}`", inline=True)
        embed.add_field(name="Channel", value=message.channel.mention,                          inline=True)
        embed.add_field(name="Link",    value=f"`{url_display}`",                               inline=False)
        if repeated:
            embed.add_field(name="Action", value=f"Muted for {MUTE_DURATION_LINK}s (repeat offender)", inline=False)
        else:
            embed.add_field(name="Action", value="Message deleted", inline=False)
        embed.set_footer(text="Shouffle Backgrounds • Raze Developments")
        embed.timestamp = datetime.now(timezone.utc)

        await BackgroundsDB.log_link_violation(
            message.guild.id, message.author.id, message.channel.id, url_display
        )
        await self._send_bg_log(message.guild, embed)

        if repeated:
            asyncio.create_task(
                self._mute_member(message.guild, message.author, MUTE_DURATION_LINK, "Repeated link spam")
            )

    @commands.Cog.listener()
    async def on_message_edit(self, before: discord.Message, after: discord.Message):
        if not after.guild or after.author.bot:
            return
        if not self._is_protected(after.guild.id):
            return
        if not isinstance(after.author, discord.Member):
            return
        if after.author.guild_permissions.administrator:
            return
        if await self._is_user_whitelisted(after.guild.id, after.author.id):
            return
        if await BackgroundsDB.is_channel_whitelisted(after.guild.id, after.channel.id):
            return

        links = self._extract_links(after.content)
        if not links:
            return

        try:
            await after.delete()
        except (discord.NotFound, discord.Forbidden):
            pass

        url_display = links[0][:60] + ("..." if len(links[0]) > 60 else "")
        embed = discord.Embed(
            title=f"{E_RESTRICT} Link Blocked (Edit)",
            color=RED
        )
        embed.add_field(name="User",    value=f"<@{after.author.id}> `{after.author.id}`", inline=True)
        embed.add_field(name="Channel", value=after.channel.mention,                        inline=True)
        embed.add_field(name="Link",    value=f"`{url_display}`",                           inline=False)
        embed.add_field(name="Action",  value="Edited message deleted",                     inline=False)
        embed.set_footer(text="Shouffle Backgrounds • Raze Developments")
        embed.timestamp = datetime.now(timezone.utc)

        await BackgroundsDB.log_link_violation(
            after.guild.id, after.author.id, after.channel.id, url_display
        )
        await self._send_bg_log(after.guild, embed)

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        if not self._is_protected(member.guild.id):
            return
        if member.bot:
            return

        account_age = (datetime.now(timezone.utc) - member.created_at).days
        if account_age < 3:
            embed = discord.Embed(
                title=f"{E_RESTRICT} Suspicious Account Joined",
                color=YELLOW
            )
            embed.add_field(name="User",         value=f"<@{member.id}> `{member.id}`", inline=True)
            embed.add_field(name="Account Age",  value=f"{account_age} day(s)",         inline=True)
            embed.add_field(name="Note",         value="Account is very new. Monitor closely.", inline=False)
            embed.set_footer(text="Shouffle Backgrounds • Raze Developments")
            embed.timestamp = datetime.now(timezone.utc)
            await self._send_bg_log(member.guild, embed)

    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member):
        if not self._is_protected(member.guild.id):
            return
        self._link_cache.get(member.guild.id, {}).pop(member.id, None)
        self._muted_cache.pop((member.guild.id, member.id), None)
        self._warn_cache.pop((member.guild.id, member.id), None)

    @commands.Cog.listener()
    async def on_guild_remove(self, guild: discord.Guild):
        await self.on_security_disable(guild)

    @commands.Cog.listener()
    async def on_webhooks_update(self, channel: discord.TextChannel):
        if not self._is_protected(channel.guild.id):
            return
        embed = discord.Embed(
            title=f"{E_CONFIG} Webhook Change Detected",
            color=YELLOW
        )
        embed.add_field(name="Channel", value=channel.mention, inline=True)
        embed.add_field(name="Note",    value="Webhooks in this channel were updated.", inline=False)
        embed.set_footer(text="Shouffle Backgrounds • Raze Developments")
        embed.timestamp = datetime.now(timezone.utc)
        await self._send_bg_log(channel.guild, embed)

    @commands.Cog.listener()
    async def on_guild_channel_create(self, channel: discord.abc.GuildChannel):
        if not self._is_protected(channel.guild.id):
            return
        if isinstance(channel, discord.TextChannel):
            try:
                mute_role = discord.utils.get(channel.guild.roles, name="Muted")
                if mute_role:
                    await channel.set_permissions(
                        mute_role,
                        send_messages=False,
                        speak=False,
                        add_reactions=False
                    )
            except (discord.Forbidden, discord.HTTPException):
                pass

    @tasks.loop(seconds=CACHE_FLUSH_INTERVAL)
    async def _cache_cleaner(self):
        now = time.time()
        for guild_id in list(self._link_cache.keys()):
            for uid in list(self._link_cache[guild_id].keys()):
                self._link_cache[guild_id][uid] = [t for t in self._link_cache[guild_id][uid] if now - t < 10]
                if not self._link_cache[guild_id][uid]:
                    del self._link_cache[guild_id][uid]
            if not self._link_cache[guild_id]:
                del self._link_cache[guild_id]

        for key in list(self._muted_cache.keys()):
            if self._muted_cache[key] < now:
                del self._muted_cache[key]

        for guild_id in list(self._event_cache.keys()):
            if not self.bot.get_guild(guild_id):
                del self._event_cache[guild_id]

        log.debug("Cache flush complete — link_cache guilds: %d", len(self._link_cache))

    @tasks.loop(seconds=HEALTH_CHECK_INTERVAL)
    async def _health_check(self):
        bot_guilds = {g.id for g in self.bot.guilds}
        stale = self._protected_ids - bot_guilds
        for gid in stale:
            self._protected_ids.discard(gid)
            self._link_cache.pop(gid, None)
            self._event_cache.pop(gid, None)

        fresh = set(await BackgroundsDB.get_all_protected_guilds())
        added = fresh - self._protected_ids
        self._protected_ids.update(added)

        log.debug(
            "Health check — protected: %d, stale removed: %d, new added: %d",
            len(self._protected_ids), len(stale), len(added)
        )

    @tasks.loop(seconds=ORPHAN_CLEAN_INTERVAL)
    async def _orphan_cleaner(self):
        bot_guilds = {g.id for g in self.bot.guilds}
        async with aiosqlite.connect(DB) as db:
            async with db.execute("SELECT guild_id FROM bg_guild_stats") as cur:
                rows = await cur.fetchall()
            for (gid,) in rows:
                if gid not in bot_guilds:
                    await db.execute("DELETE FROM bg_guild_stats WHERE guild_id = ?", (gid,))
                    await db.execute("DELETE FROM bg_channel_whitelist WHERE guild_id = ?", (gid,))
                    await db.execute("DELETE FROM bg_link_violations WHERE guild_id = ?", (gid,))
            await db.commit()
        log.debug("Orphan cleaner done")

    @tasks.loop(seconds=DB_VACUUM_INTERVAL)
    async def _db_vacuum(self):
        async with aiosqlite.connect(DB) as db:
            await db.execute("VACUUM")
            await db.commit()
        log.debug("Database VACUUM complete")

    @tasks.loop(seconds=AUDIT_PRUNE_INTERVAL)
    async def _audit_pruner(self):
        await BackgroundsDB.prune_old_violations(AUDIT_MAX_AGE_DAYS)
        cutoff = int(time.time()) - (AUDIT_MAX_AGE_DAYS * 86400)
        async with aiosqlite.connect(DB) as db:
            await db.execute("DELETE FROM security_actions WHERE timestamp < ?", (cutoff,))
            await db.commit()
        log.debug("Audit pruner done — max age: %d days", AUDIT_MAX_AGE_DAYS)

    @_cache_cleaner.before_loop
    @_health_check.before_loop
    @_orphan_cleaner.before_loop
    @_db_vacuum.before_loop
    @_audit_pruner.before_loop
    async def _before_loops(self):
        await self.bot.wait_until_ready()


async def setup(bot: commands.Bot):
    await bot.add_cog(Backgrounds(bot))

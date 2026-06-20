import discord
from discord.ext import commands, tasks
from discord import app_commands
import aiosqlite
import time
import asyncio
from datetime import date, datetime, timedelta

DB_PATH = "shouffle.db"
EMBED_COLOR = 0xFFB6C1
SUPPORT_SERVER_URL = "https://discord.gg/yourinvite"
REWARDS_BANNER_URL = ""

E_STAR     = "<:pastelstar:1517787024306733206>"
E_STAR8    = "<:star8:1517787026907336794>"
E_STAR7    = "<:star7:1517787029855932446>"
E_STAR6    = "<:star6:1517787034440433744>"
E_STAR5    = "<:star5:1517787037485498379>"
E_STAR4    = "<:star4:1517787040970834081>"
E_STAR3    = "<:star3:1517787043852189786>"
E_STAR2    = "<:star2:1517787046817828885>"
E_STAR1    = "<:star1:1517787049506246666>"
E_LB       = "<:leaderboardicon:1517783312142172200>"
E_LEAF     = "<:leaf:1515660279944319006>"

AURA_LEVELS = {
    1: (E_LEAF,  "Quiet",      0),
    2: (E_STAR1, "Cozy",    1000),
    3: (E_STAR2, "Soft",    2500),
    4: (E_STAR3, "Dreamy",  5000),
    5: (E_STAR4, "Lively",  9000),
    6: (E_STAR5, "Cosmic",  15000),
    7: (E_STAR6, "Ethereal",25000),
    8: (E_STAR7, "Legendary",40000),
}

AURA_REWARDS = [
    {
        "name": f"{E_STAR} Custom Role Color",
        "description": "Get a unique role color exclusively for your server.",
        "requirement": "Level 3 — Soft",
    },
    {
        "name": f"{E_STAR} Exclusive Badge",
        "description": "A special badge displayed on your server profile.",
        "requirement": "Level 5 — Lively",
    },
    {
        "name": f"{E_STAR} Shouffle Spotlight",
        "description": "Your server gets featured in Shouffle's spotlight channel.",
        "requirement": "Level 6 — Cosmic",
    },
    {
        "name": f"{E_STAR} Priority Support",
        "description": "Jump the queue in the support server ticket system.",
        "requirement": "Level 7 — Ethereal",
    },
    {
        "name": f"{E_STAR8} Legendary Status",
        "description": "Permanent recognition in Shouffle's Hall of Fame.",
        "requirement": "Level 8 — Legendary",
    },
]

MESSAGE_COOLDOWN = 25
VC_CHECK_INTERVAL = 300


def get_level_info(level: int) -> tuple[str, str, int]:
    if level in AURA_LEVELS:
        return AURA_LEVELS[level]
    return (E_STAR8, f"Level {level}", 0)


def get_level_from_points(points: int) -> int:
    current = 1
    for lvl, (_, _, threshold) in AURA_LEVELS.items():
        if points >= threshold:
            current = lvl
    return current


def get_next_level_threshold(level: int) -> int:
    next_level = level + 1
    if next_level in AURA_LEVELS:
        return AURA_LEVELS[next_level][2]
    return AURA_LEVELS[max(AURA_LEVELS.keys())][2]


def progress_bar(current: int, start: int, end: int, length: int = 12) -> str:
    span = end - start
    progress = current - start
    filled = int((progress / span) * length) if span > 0 else 0
    filled = max(0, min(filled, length))
    return "█" * filled + "░" * (length - filled)


def build_leaderboard_embed(rows: list, last_winner: dict | None = None) -> discord.Embed:
    embed = discord.Embed(
        title=f"{E_LB}  Global Aura Leaderboard",
        description="Rankings based on total Aura Points earned this week across all Shouffle servers.",
        color=EMBED_COLOR,
    )

    if last_winner:
        lvl_emoji, lvl_name, _ = get_level_info(last_winner.get("aura_level", 1))
        pts = f"{last_winner.get('aura_points', 0):,}"
        embed.add_field(
            name=f"{E_STAR8}  Last Week's Champion",
            value=f"**{last_winner.get('guild_name', 'Unknown')}** — {lvl_emoji} {lvl_name}  •  **{pts}** pts",
            inline=False,
        )
        embed.add_field(name="\u200b", value="\u200b", inline=False)

    if not rows:
        embed.add_field(name="No Data Yet", value="No servers have earned Aura points this week.", inline=False)
    else:
        medals = {0: "🥇", 1: "🥈", 2: "🥉"}
        for i, row in enumerate(rows[:10]):
            rank_display = medals.get(i, f"`#{i + 1}`")
            level_emoji, level_name, _ = get_level_info(row["aura_level"])
            pts = f"{row['aura_points']:,}"
            embed.add_field(
                name=f"{rank_display}  {row['guild_name']}",
                value=f"{level_emoji} {level_name}  •  **{pts}** pts",
                inline=False,
            )

    embed.set_footer(text="Shouffle • Resets every Monday  •  Made with Love and Safety")
    return embed


def build_status_embed(guild: discord.Guild, data: dict) -> discord.Embed:
    points = data["aura_points"]
    level = data["aura_level"]

    level_emoji, level_name, level_threshold = get_level_info(level)
    next_level = level + 1
    next_threshold = get_next_level_threshold(level)
    next_emoji, next_name, _ = get_level_info(next_level)

    remaining = max(0, next_threshold - points)
    bar = progress_bar(points, level_threshold, next_threshold)
    percent = int(((points - level_threshold) / max(1, next_threshold - level_threshold)) * 100)
    percent = max(0, min(percent, 100))

    embed = discord.Embed(color=EMBED_COLOR)
    embed.set_author(name=f"{guild.name} — Aura Status", icon_url=guild.icon.url if guild.icon else None)
    embed.add_field(
        name="Current Aura",
        value=f"{level_emoji} **{level_name}** (Level {level})\n`{points:,}` pts total",
        inline=True,
    )
    embed.add_field(
        name="Next Level",
        value=f"{next_emoji} **{next_name}**\n`{remaining:,}` pts needed",
        inline=True,
    )
    embed.add_field(
        name=f"Progress — {percent}%",
        value=f"`{bar}`",
        inline=False,
    )
    embed.set_footer(text="Shouffle • Made with Love and Safety")
    return embed


def build_rewards_embed() -> discord.Embed:
    embed = discord.Embed(
        title=f"{E_STAR}  Aura Rewards",
        description=(
            "Unlock exclusive perks as your server's Aura grows.\n"
            "Reach the required level and join the support server to claim."
        ),
        color=EMBED_COLOR,
    )
    for reward in AURA_REWARDS:
        embed.add_field(
            name=reward["name"],
            value=f"{reward['description']}\n**Requires:** {reward['requirement']}",
            inline=False,
        )
    if REWARDS_BANNER_URL:
        embed.set_image(url=REWARDS_BANNER_URL)
    embed.set_footer(text="Shouffle • Made with Love and Safety")
    return embed


class AuraDropdown(discord.ui.Select):
    def __init__(self, cog: "AuraCog"):
        self.cog = cog
        options = [
            discord.SelectOption(
                label="Leaderboard",
                description="View the global weekly Aura leaderboard",
                emoji=discord.PartialEmoji.from_str(E_LB),
                value="leaderboard",
                default=True,
            ),
            discord.SelectOption(
                label="My Guild Status",
                description="View this server's current Aura level and progress",
                emoji=discord.PartialEmoji.from_str(E_STAR4),
                value="status",
            ),
            discord.SelectOption(
                label="Aura Rewards",
                description="See all available Aura rewards and how to claim them",
                emoji=discord.PartialEmoji.from_str(E_STAR8),
                value="rewards",
            ),
        ]
        super().__init__(placeholder="Navigate Aura...", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction):
        selected = self.values[0]

        for opt in self.options:
            opt.default = opt.value == selected

        if selected == "leaderboard":
            async with aiosqlite.connect(DB_PATH) as db:
                db.row_factory = aiosqlite.Row
                async with db.execute(
                    "SELECT * FROM aura_guilds ORDER BY aura_points DESC LIMIT 10"
                ) as cursor:
                    rows = [dict(r) for r in await cursor.fetchall()]
                async with db.execute(
                    "SELECT * FROM aura_last_winner LIMIT 1"
                ) as cursor:
                    winner_row = await cursor.fetchone()
                    last_winner = dict(winner_row) if winner_row else None

            embed = build_leaderboard_embed(rows, last_winner)
            await interaction.response.edit_message(embed=embed, view=self.view)

        elif selected == "status":
            if not interaction.guild:
                await interaction.response.send_message("This can only be used in a server.", ephemeral=True)
                return
            await self.cog.ensure_guild(interaction.guild)
            data = await self.cog.get_guild_data(interaction.guild.id)
            if not data:
                await interaction.response.send_message("Could not retrieve aura data.", ephemeral=True)
                return
            embed = build_status_embed(interaction.guild, data)
            await interaction.response.edit_message(embed=embed, view=self.view)

        elif selected == "rewards":
            embed = build_rewards_embed()
            view = self.view
            claim_present = any(isinstance(item, discord.ui.Button) for item in view.children)
            if not claim_present:
                view.add_item(
                    discord.ui.Button(
                        label="Claim Reward",
                        style=discord.ButtonStyle.link,
                        url=SUPPORT_SERVER_URL,
                        row=1,
                    )
                )
            await interaction.response.edit_message(embed=embed, view=view)


class AuraView(discord.ui.View):
    def __init__(self, cog: "AuraCog"):
        super().__init__(timeout=120)
        self.add_item(AuraDropdown(cog))

    async def on_timeout(self):
        for item in self.children:
            item.disabled = True


class AuraCog(commands.Cog, name="Aura"):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.message_cooldowns: dict[tuple[int, int], float] = {}
        self.vc_join_times: dict[tuple[int, int], float] = {}
        self.vc_aura_loop.start()
        self.weekly_reset_loop.start()

    def cog_unload(self):
        self.vc_aura_loop.cancel()
        self.weekly_reset_loop.cancel()

    async def cog_load(self):
        await self.init_db()

    async def init_db(self):
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("""
                CREATE TABLE IF NOT EXISTS aura_guilds (
                    guild_id INTEGER PRIMARY KEY,
                    guild_name TEXT,
                    aura_points INTEGER DEFAULT 0,
                    aura_level INTEGER DEFAULT 1,
                    daily_messages INTEGER DEFAULT 0,
                    vc_minutes INTEGER DEFAULT 0,
                    joins INTEGER DEFAULT 0,
                    reactions INTEGER DEFAULT 0,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)
            await db.execute("""
                CREATE TABLE IF NOT EXISTS aura_user_activity (
                    guild_id INTEGER,
                    user_id INTEGER,
                    last_message_time REAL DEFAULT 0,
                    daily_streak INTEGER DEFAULT 0,
                    last_active TEXT,
                    PRIMARY KEY (guild_id, user_id)
                )
            """)
            await db.execute("""
                CREATE TABLE IF NOT EXISTS aura_last_winner (
                    id INTEGER PRIMARY KEY DEFAULT 1,
                    guild_id INTEGER,
                    guild_name TEXT,
                    aura_points INTEGER,
                    aura_level INTEGER,
                    week_end TEXT
                )
            """)
            await db.execute("""
                CREATE TABLE IF NOT EXISTS aura_meta (
                    key TEXT PRIMARY KEY,
                    value TEXT
                )
            """)
            await db.commit()

    async def ensure_guild(self, guild: discord.Guild):
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                "INSERT OR IGNORE INTO aura_guilds (guild_id, guild_name) VALUES (?, ?)",
                (guild.id, guild.name),
            )
            await db.execute(
                "UPDATE aura_guilds SET guild_name = ? WHERE guild_id = ?",
                (guild.name, guild.id),
            )
            await db.commit()

    async def get_guild_data(self, guild_id: int) -> dict | None:
        async with aiosqlite.connect(DB_PATH) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT * FROM aura_guilds WHERE guild_id = ?", (guild_id,)
            ) as cursor:
                row = await cursor.fetchone()
                return dict(row) if row else None

    async def add_aura(self, guild: discord.Guild, points: int, source: str = "") -> bool:
        data = await self.get_guild_data(guild.id)
        if not data:
            return False

        old_level = data["aura_level"]
        new_points = max(0, data["aura_points"] + points)
        new_level = get_level_from_points(new_points)

        updates = {"daily_messages": 0, "vc_minutes": 0, "joins": 0, "reactions": 0}
        if source == "message":
            updates["daily_messages"] = data["daily_messages"] + 1
        elif source == "vc":
            updates["vc_minutes"] = data["vc_minutes"] + 5
        elif source == "join":
            updates["joins"] = data["joins"] + 1
        elif source == "reaction":
            updates["reactions"] = data["reactions"] + 1
        else:
            updates = {
                "daily_messages": data["daily_messages"],
                "vc_minutes": data["vc_minutes"],
                "joins": data["joins"],
                "reactions": data["reactions"],
            }

        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                """UPDATE aura_guilds
                   SET aura_points = ?, aura_level = ?,
                       daily_messages = ?, vc_minutes = ?, joins = ?, reactions = ?
                   WHERE guild_id = ?""",
                (
                    new_points, new_level,
                    updates["daily_messages"], updates["vc_minutes"],
                    updates["joins"], updates["reactions"],
                    guild.id,
                ),
            )
            await db.commit()

        if new_level > old_level:
            await self.announce_level_up(guild, old_level, new_level)
            return True
        return False

    async def announce_level_up(self, guild: discord.Guild, old_level: int, new_level: int):
        old_emoji, old_name, _ = get_level_info(old_level)
        new_emoji, new_name, _ = get_level_info(new_level)
        embed = discord.Embed(
            title=f"{E_STAR} Aura Level Up!",
            description=(
                f"**{guild.name}** has grown:\n\n"
                f"{old_emoji} **{old_name}** → {new_emoji} **{new_name}**\n\n"
                f"Community energy is rising."
            ),
            color=EMBED_COLOR,
        )
        embed.set_footer(text="Shouffle • Made with Love and Safety")
        channel = self._get_announce_channel(guild)
        if channel:
            try:
                await channel.send(embed=embed)
            except discord.Forbidden:
                pass

    def _get_announce_channel(self, guild: discord.Guild) -> discord.TextChannel | None:
        for name in ("general", "chat", "lounge", "main", "aura"):
            ch = discord.utils.get(guild.text_channels, name=name)
            if ch and ch.permissions_for(guild.me).send_messages:
                return ch
        for ch in guild.text_channels:
            if ch.permissions_for(guild.me).send_messages:
                return ch
        return None

    async def update_user_activity(self, guild_id: int, user_id: int) -> bool:
        today = date.today().isoformat()
        async with aiosqlite.connect(DB_PATH) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT * FROM aura_user_activity WHERE guild_id = ? AND user_id = ?",
                (guild_id, user_id),
            ) as cursor:
                row = await cursor.fetchone()

            streak_bonus = False
            if row:
                last_active = row["last_active"]
                streak = row["daily_streak"]
                if last_active != today:
                    streak = streak + 1 if last_active else 1
                    streak_bonus = True
                    await db.execute(
                        "UPDATE aura_user_activity SET daily_streak = ?, last_active = ? WHERE guild_id = ? AND user_id = ?",
                        (streak, today, guild_id, user_id),
                    )
            else:
                await db.execute(
                    "INSERT INTO aura_user_activity (guild_id, user_id, daily_streak, last_active) VALUES (?, ?, 1, ?)",
                    (guild_id, user_id, today),
                )
                streak_bonus = True

            await db.commit()
        return streak_bonus

    async def do_weekly_reset(self):
        async with aiosqlite.connect(DB_PATH) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT * FROM aura_guilds ORDER BY aura_points DESC LIMIT 1"
            ) as cursor:
                winner = await cursor.fetchone()

            if winner:
                await db.execute(
                    """INSERT INTO aura_last_winner (id, guild_id, guild_name, aura_points, aura_level, week_end)
                       VALUES (1, ?, ?, ?, ?, ?)
                       ON CONFLICT(id) DO UPDATE SET
                           guild_id=excluded.guild_id,
                           guild_name=excluded.guild_name,
                           aura_points=excluded.aura_points,
                           aura_level=excluded.aura_level,
                           week_end=excluded.week_end""",
                    (winner["guild_id"], winner["guild_name"], winner["aura_points"], winner["aura_level"], date.today().isoformat()),
                )

            await db.execute(
                "UPDATE aura_guilds SET aura_points = 0, aura_level = 1, daily_messages = 0, vc_minutes = 0, joins = 0, reactions = 0"
            )
            await db.execute(
                "INSERT INTO aura_meta (key, value) VALUES ('last_reset', ?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                (date.today().isoformat(),),
            )
            await db.commit()

    @tasks.loop(hours=1)
    async def weekly_reset_loop(self):
        now = datetime.utcnow()
        if now.weekday() != 0 or now.hour != 0:
            return

        async with aiosqlite.connect(DB_PATH) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("SELECT value FROM aura_meta WHERE key = 'last_reset'") as cursor:
                row = await cursor.fetchone()

        if row:
            last_reset = date.fromisoformat(row["value"])
            if (date.today() - last_reset).days < 7:
                return

        await self.do_weekly_reset()

    @weekly_reset_loop.before_loop
    async def before_weekly_loop(self):
        await self.bot.wait_until_ready()

    @commands.Cog.listener()
    async def on_ready(self):
        for guild in self.bot.guilds:
            await self.ensure_guild(guild)

    @commands.Cog.listener()
    async def on_guild_join(self, guild: discord.Guild):
        await self.ensure_guild(guild)

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        if member.bot:
            return
        await self.ensure_guild(member.guild)
        await self.add_aura(member.guild, 5, source="join")

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot or not message.guild:
            return
        if len(message.content) <= 10:
            return

        guild = message.guild
        user = message.author
        key = (guild.id, user.id)
        now = time.time()

        if now - self.message_cooldowns.get(key, 0) < MESSAGE_COOLDOWN:
            return

        self.message_cooldowns[key] = now
        await self.ensure_guild(guild)
        await self.add_aura(guild, 2, source="message")

        if await self.update_user_activity(guild.id, user.id):
            await self.add_aura(guild, 5, source="streak")

    @commands.Cog.listener()
    async def on_reaction_add(self, reaction: discord.Reaction, user: discord.Member | discord.User):
        if user.bot or not reaction.message.guild:
            return
        await self.ensure_guild(reaction.message.guild)
        await self.add_aura(reaction.message.guild, 3, source="reaction")

    @commands.Cog.listener()
    async def on_voice_state_update(
        self,
        member: discord.Member,
        before: discord.VoiceState,
        after: discord.VoiceState,
    ):
        if member.bot:
            return
        key = (member.guild.id, member.id)
        if before.channel is None and after.channel is not None:
            self.vc_join_times[key] = time.time()
        elif before.channel is not None and after.channel is None:
            self.vc_join_times.pop(key, None)

    @tasks.loop(minutes=5)
    async def vc_aura_loop(self):
        now = time.time()
        for key, join_time in list(self.vc_join_times.items()):
            if now - join_time >= VC_CHECK_INTERVAL:
                guild_id, _ = key
                guild = self.bot.get_guild(guild_id)
                if guild:
                    await self.ensure_guild(guild)
                    await self.add_aura(guild, 10, source="vc")
                    self.vc_join_times[key] = now

    @vc_aura_loop.before_loop
    async def before_vc_loop(self):
        await self.bot.wait_until_ready()

    def deduct_aura_external(self, guild_id: int, points: int):
        guild = self.bot.get_guild(guild_id)
        if guild:
            asyncio.create_task(self.add_aura(guild, -points))

    async def _send_aura_panel(self, send_fn, guild: discord.Guild):
        async with aiosqlite.connect(DB_PATH) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT * FROM aura_guilds ORDER BY aura_points DESC LIMIT 10"
            ) as cursor:
                rows = [dict(r) for r in await cursor.fetchall()]
            async with db.execute("SELECT * FROM aura_last_winner LIMIT 1") as cursor:
                winner_row = await cursor.fetchone()
                last_winner = dict(winner_row) if winner_row else None

        embed = build_leaderboard_embed(rows, last_winner)
        view = AuraView(self)
        await send_fn(embed=embed, view=view)

    @commands.command(name="aura")
    @commands.guild_only()
    async def aura_prefix(self, ctx: commands.Context):
        await self.ensure_guild(ctx.guild)
        await self._send_aura_panel(ctx.send, ctx.guild)

    @app_commands.command(name="aura", description="View Aura leaderboard, guild status, and rewards.")
    @app_commands.guild_only()
    async def aura_slash(self, interaction: discord.Interaction):
        await interaction.response.defer()
        await self.ensure_guild(interaction.guild)

        async with aiosqlite.connect(DB_PATH) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT * FROM aura_guilds ORDER BY aura_points DESC LIMIT 10"
            ) as cursor:
                rows = [dict(r) for r in await cursor.fetchall()]
            async with db.execute("SELECT * FROM aura_last_winner LIMIT 1") as cursor:
                winner_row = await cursor.fetchone()
                last_winner = dict(winner_row) if winner_row else None

        embed = build_leaderboard_embed(rows, last_winner)
        view = AuraView(self)
        await interaction.followup.send(embed=embed, view=view)


async def setup(bot: commands.Bot):
    cog = AuraCog(bot)
    await cog.init_db()
    await bot.add_cog(cog)

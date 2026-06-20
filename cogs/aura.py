import discord
from discord.ext import commands, tasks
from discord import app_commands
import aiosqlite
import time
import asyncio
from datetime import date

DB_PATH = "shouffle.db"
EMBED_COLOR = 0xFFB6C1
SUPPORT_SERVER_URL = "https://discord.gg/yourinvite"
REWARDS_BANNER_URL = ""

AURA_LEVELS = {
    1: ("🌱", "Quiet",      0),
    2: ("☁️",  "Cozy",    1000),
    3: ("✨", "Soft",     2500),
    4: ("🌙", "Dreamy",   5000),
    5: ("💫", "Lively",   9000),
    6: ("🔮", "Cosmic",  15000),
    7: ("🌌", "Ethereal",25000),
    8: ("👑", "Legendary",40000),
}

AURA_REWARDS = [
    {
        "name": "✦ Custom Role Color",
        "description": "Get a unique role color exclusively for your server.",
        "requirement": "Level 3 — Soft",
    },
    {
        "name": "✦ Exclusive Badge",
        "description": "A special badge displayed on your server profile.",
        "requirement": "Level 5 — Lively",
    },
    {
        "name": "✦ Shouffle Spotlight",
        "description": "Your server gets featured in Shouffle's spotlight channel.",
        "requirement": "Level 6 — Cosmic",
    },
    {
        "name": "✦ Priority Support",
        "description": "Jump the queue in the support server ticket system.",
        "requirement": "Level 7 — Ethereal",
    },
    {
        "name": "✦ Legendary Status",
        "description": "Permanent recognition in Shouffle's Hall of Fame.",
        "requirement": "Level 8 — Legendary",
    },
]

MESSAGE_COOLDOWN = 25
VC_CHECK_INTERVAL = 300


def get_level_info(level: int) -> tuple[str, str, int]:
    if level in AURA_LEVELS:
        return AURA_LEVELS[level]
    return ("⭐", f"Level {level}", 0)


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


def build_leaderboard_embed(rows: list, banner_url: str = "") -> discord.Embed | None:
    if not rows:
        return None

    medals = {0: "🥇", 1: "🥈", 2: "🥉"}

    embed = discord.Embed(
        title="🏆  Global Aura Leaderboard",
        description="Rankings based on total Aura Points earned across all Shouffle servers.",
        color=EMBED_COLOR,
    )

    for i, row in enumerate(rows[:10]):
        rank_display = medals.get(i, f"`#{i + 1}`")
        level_emoji, level_name, _ = get_level_info(row["aura_level"])
        pts = f"{row['aura_points']:,}"

        embed.add_field(
            name=f"{rank_display}  {row['guild_name']}",
            value=f"{level_emoji} {level_name}  •  **{pts}** pts",
            inline=False,
        )

    if banner_url:
        embed.set_image(url=banner_url)

    embed.set_footer(text="Shouffle • Made with Love and Safety")
    return embed


class ClaimRewardView(discord.ui.View):
    def __init__(self, support_url: str):
        super().__init__(timeout=None)
        self.add_item(
            discord.ui.Button(
                label="Claim Reward",
                emoji="✦",
                style=discord.ButtonStyle.link,
                url=support_url,
            )
        )


def build_rewards_embed(banner_url: str = "") -> discord.Embed:
    embed = discord.Embed(
        title="✦  Aura Rewards",
        description=(
            "Unlock exclusive perks as your server's Aura grows.\n"
            "Reach the required level and claim your reward below."
        ),
        color=EMBED_COLOR,
    )

    for reward in AURA_REWARDS:
        embed.add_field(
            name=reward["name"],
            value=f"{reward['description']}\n**Requires:** {reward['requirement']}",
            inline=False,
        )

    if banner_url:
        embed.set_image(url=banner_url)

    embed.set_footer(text="Shouffle • Made with Love and Safety")
    return embed


class AuraCog(commands.Cog, name="Aura"):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.message_cooldowns: dict[tuple[int, int], float] = {}
        self.vc_join_times: dict[tuple[int, int], float] = {}
        self.vc_aura_loop.start()

    def cog_unload(self):
        self.vc_aura_loop.cancel()

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
            title="✨ Aura Level Up!",
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

    @commands.command(name="aurastatus")
    @commands.guild_only()
    async def aurastatus_prefix(self, ctx: commands.Context):
        await self.ensure_guild(ctx.guild)
        data = await self.get_guild_data(ctx.guild.id)
        if not data:
            await ctx.send("Could not retrieve aura data.")
            return
        await ctx.send(embed=build_status_embed(ctx.guild, data))

    @app_commands.command(name="aurastatus", description="View this server's Aura status.")
    @app_commands.guild_only()
    async def aurastatus_slash(self, interaction: discord.Interaction):
        await interaction.response.defer()
        await self.ensure_guild(interaction.guild)
        data = await self.get_guild_data(interaction.guild.id)
        if not data:
            await interaction.followup.send("Could not retrieve aura data.")
            return
        await interaction.followup.send(embed=build_status_embed(interaction.guild, data))

    @commands.command(name="aurastats")
    @commands.guild_only()
    async def aurastats_prefix(self, ctx: commands.Context):
        async with aiosqlite.connect(DB_PATH) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT * FROM aura_guilds ORDER BY aura_points DESC LIMIT 10"
            ) as cursor:
                rows = [dict(r) for r in await cursor.fetchall()]
        embed = build_leaderboard_embed(rows)
        if not embed:
            await ctx.send("No servers on the leaderboard yet.")
            return
        await ctx.send(embed=embed)

    @app_commands.command(name="aurastats", description="View the global Aura leaderboard.")
    @app_commands.guild_only()
    async def aurastats_slash(self, interaction: discord.Interaction):
        await interaction.response.defer()
        async with aiosqlite.connect(DB_PATH) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT * FROM aura_guilds ORDER BY aura_points DESC LIMIT 10"
            ) as cursor:
                rows = [dict(r) for r in await cursor.fetchall()]
        embed = build_leaderboard_embed(rows)
        if not embed:
            await interaction.followup.send("No servers on the leaderboard yet.")
            return
        await interaction.followup.send(embed=embed)

    @commands.command(name="aurareward")
    @commands.guild_only()
    async def aurareward_prefix(self, ctx: commands.Context):
        view = ClaimRewardView(SUPPORT_SERVER_URL)
        await ctx.send(embed=build_rewards_embed(REWARDS_BANNER_URL), view=view)

    @app_commands.command(name="aurareward", description="View available Aura rewards.")
    @app_commands.guild_only()
    async def aurareward_slash(self, interaction: discord.Interaction):
        view = ClaimRewardView(SUPPORT_SERVER_URL)
        await interaction.response.send_message(embed=build_rewards_embed(REWARDS_BANNER_URL), view=view)


async def setup(bot: commands.Bot):
    cog = AuraCog(bot)
    await cog.init_db()
    await bot.add_cog(cog)

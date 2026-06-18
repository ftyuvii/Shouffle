import discord
from discord.ext import commands
import json
import os
from datetime import datetime

# ── File paths for persistent storage ──────────────────────────────────────────
DATA_DIR       = "data"
NP_FILE        = os.path.join(DATA_DIR, "no_prefix.json")
SAFEHANDS_FILE = os.path.join(DATA_DIR, "safehands.json")
COUNTER_FILE   = os.path.join(DATA_DIR, "command_counter.json")

def ensure_data_dir():
    os.makedirs(DATA_DIR, exist_ok=True)

def load_json(path: str, default):
    try:
        with open(path, "r") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return default

def save_json(path: str, data):
    ensure_data_dir()
    with open(path, "w") as f:
        json.dump(data, f, indent=4)


# ── Permission check ────────────────────────────────────────────────────────────
def is_owner_or_safehands():
    """Allow bot owner + anyone on the safehands list."""
    async def predicate(ctx: commands.Context) -> bool:
        safehands: list = load_json(SAFEHANDS_FILE, [])
        return await ctx.bot.is_owner(ctx.author) or ctx.author.id in safehands
    return commands.check(predicate)


# ══════════════════════════════════════════════════════════════════════════════
class Owner(commands.Cog):
    """Bot-owner / safehands only commands."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        ensure_data_dir()
        # Initialise counter file if missing
        if not os.path.exists(COUNTER_FILE):
            save_json(COUNTER_FILE, {"total": 0})

    # ── Global command counter listener ────────────────────────────────────────
    @commands.Cog.listener()
    async def on_command_completion(self, ctx: commands.Context):
        """Increments the global command-use counter after every successful command."""
        data = load_json(COUNTER_FILE, {"total": 0})
        data["total"] = data.get("total", 0) + 1
        save_json(COUNTER_FILE, data)

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # NO-PREFIX GROUP  (?np)
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    @commands.group(name="np", invoke_without_command=True)
    @is_owner_or_safehands()
    async def np(self, ctx: commands.Context):
        """No-prefix management. Use ?np add / show / remove."""
        embed = discord.Embed(
            title="📋 No-Prefix Help",
            description=(
                "`?np add <@user>` — Grant no-prefix access\n"
                "`?np show` — List all no-prefix users\n"
                "`?np remove <@user>` — Revoke no-prefix access"
            ),
            color=discord.Color.blurple(),
            timestamp=datetime.utcnow()
        )
        await ctx.send(embed=embed)

    # ── ?np add @user ──────────────────────────────────────────────────────────
    @np.command(name="add")
    @is_owner_or_safehands()
    async def np_add(self, ctx: commands.Context, user: discord.User):
        np_list: list = load_json(NP_FILE, [])

        if user.id in np_list:
            embed = discord.Embed(
                description=f"⚠️ {user.mention} already has **no-prefix** access.",
                color=discord.Color.orange()
            )
            return await ctx.send(embed=embed)

        np_list.append(user.id)
        save_json(NP_FILE, np_list)

        embed = discord.Embed(
            description=f"✅ {user.mention} has been granted **no-prefix** access.",
            color=discord.Color.green(),
            timestamp=datetime.utcnow()
        )
        embed.set_footer(text=f"Added by {ctx.author}", icon_url=ctx.author.display_avatar.url)
        await ctx.send(embed=embed)

    # ── ?np show ───────────────────────────────────────────────────────────────
    @np.command(name="show")
    @is_owner_or_safehands()
    async def np_show(self, ctx: commands.Context):
        np_list: list = load_json(NP_FILE, [])

        if not np_list:
            embed = discord.Embed(
                description="📭 No users currently have **no-prefix** access.",
                color=discord.Color.blurple()
            )
            return await ctx.send(embed=embed)

        lines = []
        for uid in np_list:
            user = self.bot.get_user(uid) or await self.bot.fetch_user(uid)
            lines.append(f"• {user.mention} (`{user}` — ID: `{uid}`)")

        embed = discord.Embed(
            title="🔓 No-Prefix Users",
            description="\n".join(lines),
            color=discord.Color.blurple(),
            timestamp=datetime.utcnow()
        )
        embed.set_footer(text=f"Total: {len(np_list)} user(s)")
        await ctx.send(embed=embed)

    # ── ?np remove @user ───────────────────────────────────────────────────────
    @np.command(name="remove")
    @is_owner_or_safehands()
    async def np_remove(self, ctx: commands.Context, user: discord.User):
        np_list: list = load_json(NP_FILE, [])

        if user.id not in np_list:
            embed = discord.Embed(
                description=f"⚠️ {user.mention} doesn't have **no-prefix** access.",
                color=discord.Color.orange()
            )
            return await ctx.send(embed=embed)

        np_list.remove(user.id)
        save_json(NP_FILE, np_list)

        embed = discord.Embed(
            description=f"🗑️ {user.mention}'s **no-prefix** access has been removed.",
            color=discord.Color.red(),
            timestamp=datetime.utcnow()
        )
        embed.set_footer(text=f"Removed by {ctx.author}", icon_url=ctx.author.display_avatar.url)
        await ctx.send(embed=embed)

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # SAFEHANDS  (?safehands / ?remove safehands)
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    @commands.command(name="safehands")
    @commands.is_owner()          # Only the actual bot owner can assign safehands
    async def safehands_add(self, ctx: commands.Context, user: discord.Member):
        """?safehands @user — Trust a user with owner-level commands."""
        sh_list: list = load_json(SAFEHANDS_FILE, [])

        if user.id in sh_list:
            embed = discord.Embed(
                description=f"⚠️ {user.mention} is already in **Safehands**.",
                color=discord.Color.orange()
            )
            return await ctx.send(embed=embed)

        sh_list.append(user.id)
        save_json(SAFEHANDS_FILE, sh_list)

        embed = discord.Embed(
            title="🤝 Safehands Updated",
            description=f"✅ {user.mention} has been added to **Safehands** and can now use owner commands.",
            color=discord.Color.green(),
            timestamp=datetime.utcnow()
        )
        embed.set_footer(text=f"Added by {ctx.author}", icon_url=ctx.author.display_avatar.url)
        await ctx.send(embed=embed)

    @commands.command(name="remove")
    @commands.is_owner()          # Only the actual bot owner can remove safehands
    async def safehands_remove(self, ctx: commands.Context, target: str, user: discord.Member):
        """?remove safehands @user — Remove a user from Safehands."""
        if target.lower() != "safehands":
            return  # Ignore if not "?remove safehands"

        sh_list: list = load_json(SAFEHANDS_FILE, [])

        if user.id not in sh_list:
            embed = discord.Embed(
                description=f"⚠️ {user.mention} is not in **Safehands**.",
                color=discord.Color.orange()
            )
            return await ctx.send(embed=embed)

        sh_list.remove(user.id)
        save_json(SAFEHANDS_FILE, sh_list)

        embed = discord.Embed(
            title="🤝 Safehands Updated",
            description=f"🗑️ {user.mention} has been removed from **Safehands**.",
            color=discord.Color.red(),
            timestamp=datetime.utcnow()
        )
        embed.set_footer(text=f"Removed by {ctx.author}", icon_url=ctx.author.display_avatar.url)
        await ctx.send(embed=embed)

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # COMMAND COUNTER  (?c)
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    @commands.command(name="c")
    @is_owner_or_safehands()
    async def command_count(self, ctx: commands.Context):
        """?c — Show how many commands have been used globally."""
        data = load_json(COUNTER_FILE, {"total": 0})
        total = data.get("total", 0)

        embed = discord.Embed(
            title="📊 Global Command Usage",
            description=f"The bot has processed **{total:,}** command(s) since tracking began.",
            color=discord.Color.blurple(),
            timestamp=datetime.utcnow()
        )
        embed.set_footer(text="Counter updates on every successful command")
        await ctx.send(embed=embed)

    # ── Unified error handler ──────────────────────────────────────────────────
    @np.error
    @safehands_add.error
    @safehands_remove.error
    @command_count.error
    async def owner_error(self, ctx: commands.Context, error):
        if isinstance(error, (commands.CheckFailure, commands.NotOwner)):
            embed = discord.Embed(
                description="🚫 You don't have permission to use this command.",
                color=discord.Color.red()
            )
            await ctx.send(embed=embed)
        elif isinstance(error, commands.MissingRequiredArgument):
            embed = discord.Embed(
                description=f"⚠️ Missing argument: `{error.param.name}`",
                color=discord.Color.orange()
            )
            await ctx.send(embed=embed)
        elif isinstance(error, commands.UserNotFound):
            embed = discord.Embed(
                description="❌ User not found. Please mention a valid user.",
                color=discord.Color.red()
            )
            await ctx.send(embed=embed)
        else:
            raise error


# ── Cog setup ──────────────────────────────────────────────────────────────────
async def setup(bot: commands.Bot):
    await bot.add_cog(Owner(bot))

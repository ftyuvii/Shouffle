from __future__ import annotations

import json
import os
import discord
from discord.ext import commands

from cogs.utils import (
    make_embed,
    success_embed,
    error_embed,
    BRAND_COLOR,
)

NP_FILE = "noprefix.json"


# ─── Storage helpers ──────────────────────────────────────────────────────────

def load_np() -> list:
    if not os.path.exists(NP_FILE):
        with open(NP_FILE, "w") as f:
            json.dump([], f)
    with open(NP_FILE, "r") as f:
        return json.load(f)


def save_np(data: list) -> None:
    with open(NP_FILE, "w") as f:
        json.dump(data, f, indent=4)


# ─── Cog ──────────────────────────────────────────────────────────────────────

class NoPrefix(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        # Cache in memory so on_message is fast
        self._np_users: set[int] = set(load_np())

    def _reload_cache(self):
        self._np_users = set(load_np())

    # ── on_message: only re-invoke commands, never reply to plain chat ────────

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        # Ignore bots & DMs
        if message.author.bot or not message.guild:
            return

        # Only act for users in the no-prefix list
        if message.author.id not in self._np_users:
            return

        # Grab the bot's configured prefix(es)
        prefix = self.bot.command_prefix
        if callable(prefix):
            try:
                prefix = await discord.utils.maybe_coroutine(prefix, self.bot, message)
            except Exception:
                return
        if isinstance(prefix, (list, tuple)):
            prefix = tuple(prefix)
        else:
            prefix = (prefix,)

        # If the message already starts with a prefix, discord.py handles it normally
        content = message.content.strip()
        for p in prefix:
            if content.startswith(p):
                return  # already prefixed — don't interfere

        # Check if the message looks like a command (first word matches a known command)
        first_word = content.split()[0].lower() if content.split() else ""
        if not first_word:
            return

        # Only trigger if it's an actual bot command name or alias — NOT random chat
        all_commands: set[str] = set()
        for cmd in self.bot.walk_commands():
            all_commands.add(cmd.name.lower())
            for alias in cmd.aliases:
                all_commands.add(alias.lower())

        if first_word not in all_commands:
            return  # not a command — ignore (so "hello", "hi", etc. are safe)

        # Re-invoke with the first available prefix prepended
        fake_prefix = prefix[0]
        message.content = fake_prefix + content
        await self.bot.process_commands(message)

    # ── Commands ──────────────────────────────────────────────────────────────

    @commands.group(name="np", invoke_without_command=True)
    @commands.is_owner()
    async def np(self, ctx: commands.Context):
        """No-Prefix Manager — shows help."""
        embed = make_embed(
            title="⚡  No Prefix Manager",
            description=(
                "`?np add @user`    — Grant no-prefix to a user\n"
                "`?np remove @user` — Revoke no-prefix from a user\n"
                "`?np reset`        — Remove **all** no-prefix users\n"
                "`?np show`         — List all no-prefix users"
            ),
            color=BRAND_COLOR,
            footer="Only the bot owner can use these commands",
        )
        await ctx.reply(embed=embed, mention_author=False)

    @np.command(name="add")
    @commands.is_owner()
    async def np_add(self, ctx: commands.Context, member: discord.Member):
        """Add a user to the no-prefix list."""
        if member.bot:
            return await ctx.reply(
                embed=error_embed("Bots cannot be added to the no-prefix list."),
                mention_author=False,
            )

        users = load_np()
        if member.id in users:
            return await ctx.reply(
                embed=error_embed(f"{member.mention} already has no prefix."),
                mention_author=False,
            )

        users.append(member.id)
        save_np(users)
        self._reload_cache()

        await ctx.reply(
            embed=success_embed(
                f"**{member.display_name}** has been granted no-prefix access.\n"
                f"They can now use commands without `?`."
            ),
            mention_author=False,
        )

    @np.command(name="remove")
    @commands.is_owner()
    async def np_remove(self, ctx: commands.Context, member: discord.Member):
        """Remove a user from the no-prefix list."""
        users = load_np()
        if member.id not in users:
            return await ctx.reply(
                embed=error_embed(f"{member.mention} is not in the no-prefix list."),
                mention_author=False,
            )

        users.remove(member.id)
        save_np(users)
        self._reload_cache()

        await ctx.reply(
            embed=success_embed(
                f"**{member.display_name}**'s no-prefix access has been revoked."
            ),
            mention_author=False,
        )

    @np.command(name="reset")
    @commands.is_owner()
    async def np_reset(self, ctx: commands.Context):
        """Remove ALL users from the no-prefix list."""
        users = load_np()
        if not users:
            return await ctx.reply(
                embed=error_embed("The no-prefix list is already empty."),
                mention_author=False,
            )

        count = len(users)
        save_np([])
        self._reload_cache()

        await ctx.reply(
            embed=success_embed(
                f"✅ No-prefix list cleared.\n"
                f"**{count}** user(s) have been removed."
            ),
            mention_author=False,
        )

    @np.command(name="show")
    @commands.is_owner()
    async def np_show(self, ctx: commands.Context):
        """Show all users currently in the no-prefix list."""
        users = load_np()

        if not users:
            return await ctx.reply(
                embed=error_embed("No users currently have no-prefix access."),
                mention_author=False,
            )

        lines = []
        for i, user_id in enumerate(users, 1):
            user = self.bot.get_user(user_id)
            if not user:
                try:
                    user = await self.bot.fetch_user(user_id)
                except Exception:
                    user = None
            if user:
                lines.append(f"`{i}.` {user.mention} — `{user.id}`")
            else:
                lines.append(f"`{i}.` Unknown User — `{user_id}`")

        embed = make_embed(
            title="⚡  No Prefix Users",
            description="\n".join(lines),
            color=BRAND_COLOR,
            footer=f"Total: {len(users)} user(s)",
        )
        await ctx.reply(embed=embed, mention_author=False)

    # ── Error handlers ────────────────────────────────────────────────────────

    @np_add.error
    @np_remove.error
    async def member_error(self, ctx: commands.Context, error: commands.CommandError):
        if isinstance(error, commands.MemberNotFound):
            await ctx.reply(
                embed=error_embed("Member not found. Please mention a valid server member."),
                mention_author=False,
            )
        elif isinstance(error, commands.NotOwner):
            await ctx.reply(
                embed=error_embed("Only the bot owner can manage no-prefix users."),
                mention_author=False,
            )


async def setup(bot: commands.Bot):
    await bot.add_cog(NoPrefix(bot))

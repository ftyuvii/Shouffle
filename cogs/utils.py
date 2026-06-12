"""
utils.py — Shared utility helpers for all cogs.
Place this file inside your cogs/ folder.
"""

import discord
from datetime import datetime


# ─────────────────────────────────────────────
#  Placeholder resolver
# ─────────────────────────────────────────────

PLACEHOLDERS = {
    "{user}":           lambda member, guild: member.mention,
    "{username}":       lambda member, guild: str(member),
    "{displayname}":    lambda member, guild: member.display_name,
    "{server}":         lambda member, guild: guild.name,
    "{membercount}":    lambda member, guild: str(guild.member_count),
    "{userid}":         lambda member, guild: str(member.id),
    "{joined}":         lambda member, guild: discord.utils.format_dt(member.joined_at or datetime.utcnow(), style="D"),
    "{created}":        lambda member, guild: discord.utils.format_dt(member.created_at, style="D"),
}


def resolve_placeholders(text: str, member: discord.Member, guild: discord.Guild) -> str:
    """Replace all {placeholder} tokens in *text* with live values."""
    if not text:
        return text
    for token, resolver in PLACEHOLDERS.items():
        if token in text:
            text = text.replace(token, resolver(member, guild))
    return text


def placeholder_list() -> str:
    """Return a human-readable list of available placeholders."""
    descriptions = {
        "{user}":        "Mentions the user  →  @Yuvraj",
        "{username}":    "Full username       →  Yuvraj#0001",
        "{displayname}": "Server nickname     →  Yuvraj",
        "{server}":      "Server name         →  My Awesome Server",
        "{membercount}": "Total member count  →  1,234",
        "{userid}":      "User's Discord ID   →  123456789",
        "{joined}":      "Join date           →  June 11, 2026",
        "{created}":     "Account created     →  January 1, 2020",
    }
    return "\n".join(f"`{k}` — {v}" for k, v in descriptions.items())


# ─────────────────────────────────────────────
#  Embed builder
# ─────────────────────────────────────────────

BRAND_COLOR  = 0x5865F2   # Discord blurple — change to your liking
SUCCESS_COLOR = 0x57F287
ERROR_COLOR   = 0xED4245
WARNING_COLOR = 0xFEE75C
INFO_COLOR    = 0x5865F2


def make_embed(
    title: str = None,
    description: str = None,
    color: int = BRAND_COLOR,
    footer: str = None,
    thumbnail: str = None,
    image: str = None,
    author_name: str = None,
    author_icon: str = None,
    timestamp: bool = False,
    fields: list[tuple] = None,   # [(name, value, inline), ...]
) -> discord.Embed:
    """Central embed factory used across all cogs."""
    embed = discord.Embed(
        title=title,
        description=description,
        color=color,
    )
    if timestamp:
        embed.timestamp = datetime.utcnow()
    if footer:
        embed.set_footer(text=footer)
    if thumbnail:
        embed.set_thumbnail(url=thumbnail)
    if image:
        embed.set_image(url=image)
    if author_name:
        embed.set_author(name=author_name, icon_url=author_icon or discord.embeds.EmptyEmbed)
    if fields:
        for name, value, inline in fields:
            embed.add_field(name=name, value=value, inline=inline)
    return embed


def success_embed(description: str, title: str = "✅  Success") -> discord.Embed:
    return make_embed(title=title, description=description, color=SUCCESS_COLOR)


def error_embed(description: str, title: str = "❌  Error") -> discord.Embed:
    return make_embed(title=title, description=description, color=ERROR_COLOR)


def info_embed(description: str, title: str = "ℹ️  Info") -> discord.Embed:
    return make_embed(title=title, description=description, color=INFO_COLOR)


# ─────────────────────────────────────────────
#  Permission helper
# ─────────────────────────────────────────────

def is_admin(member: discord.Member) -> bool:
    return member.guild_permissions.administrator


# ─────────────────────────────────────────────
#  Cog setup  (utils is imported, not loaded as an extension,
#  but keeping setup() makes it loadable either way)
# ─────────────────────────────────────────────

async def setup(bot):
    pass   # nothing to register — pure utility module

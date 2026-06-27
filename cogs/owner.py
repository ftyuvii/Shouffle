import discord
from discord.ext import commands
import json
import os
import aiosqlite

OWNER_ID       = 907180055615123456
NOPREFIX_FILE  = "data/noprefix.json"
OWNER_FILE     = "data/owner_data.json"
PINK           = 0xFFB6C1
GREEN          = 0x57F287
RED            = 0xFFBFEA

STAR  = "🌟"
LEAF  = "🍀"
PREMIUM = "💎"

DB = "shouffle.db"


async def _set_guild_premium(guild_id: int, value: bool):
    async with aiosqlite.connect(DB) as db:
        await db.execute(
            "UPDATE security_guilds SET premium = ? WHERE guild_id = ?",
            (int(value), guild_id)
        )
        await db.commit()


async def _get_guild_premium(guild_id: int) -> bool:
    async with aiosqlite.connect(DB) as db:
        async with db.execute(
            "SELECT premium FROM security_guilds WHERE guild_id = ?", (guild_id,)
        ) as cur:
            row = await cur.fetchone()
            return bool(row and row[0])


def _ensure_data():
    os.makedirs("data", exist_ok=True)


def load_noprefix() -> list:
    _ensure_data()
    if not os.path.exists(NOPREFIX_FILE):
        json.dump([], open(NOPREFIX_FILE, "w"), indent=2)
    return json.load(open(NOPREFIX_FILE))


def save_noprefix(data: list):
    _ensure_data()
    json.dump(data, open(NOPREFIX_FILE, "w"), indent=2)


def load_owner() -> dict:
    _ensure_data()
    if not os.path.exists(OWNER_FILE):
        json.dump({"globallogs_channel": None}, open(OWNER_FILE, "w"), indent=2)
    return json.load(open(OWNER_FILE))


def save_owner(data: dict):
    _ensure_data()
    json.dump(data, open(OWNER_FILE, "w"), indent=2)


def is_owner():
    async def predicate(ctx: commands.Context):
        return ctx.author.id == OWNER_ID
    return commands.check(predicate)


def panel_embed(bot: commands.Bot) -> discord.Embed:
    np_users = load_noprefix()
    owner    = load_owner()
    logs     = f"<#{owner['globallogs_channel']}>" if owner.get("globallogs_channel") else "Not set"

    embed = discord.Embed(title=f"{STAR} Owner Panel", color=PINK)
    embed.add_field(
        name="Bot",
        value=(
            f"Servers — **{len(bot.guilds)}**\n"
            f"Users — **{sum(g.member_count for g in bot.guilds):,}**"
        ),
        inline=True,
    )
    embed.add_field(
        name="Config",
        value=(
            f"No-Prefix — **{len(np_users)}**\n"
            f"Global Logs — {logs}"
        ),
        inline=True,
    )
    embed.set_footer(text="Raze Developments • Shouffle")
    return embed


class GrantNPModal(discord.ui.Modal, title="Grant No-Prefix"):
    uid = discord.ui.TextInput(label="User ID", placeholder="Discord user ID", max_length=20)

    def __init__(self, bot: commands.Bot):
        super().__init__()
        self.bot = bot

    async def on_submit(self, interaction: discord.Interaction):
        try:
            uid = int(self.uid.value.strip())
        except ValueError:
            await interaction.response.send_message(
                embed=discord.Embed(description="Invalid ID.", color=RED), ephemeral=True
            )
            return

        data = load_noprefix()
        if uid in data:
            await interaction.response.send_message(
                embed=discord.Embed(description="User already has no-prefix.", color=RED), ephemeral=True
            )
            return

        data.append(uid)
        save_noprefix(data)
        user = self.bot.get_user(uid) or await self.bot.fetch_user(uid)
        name = user.mention if user else f"`{uid}`"
        await interaction.response.send_message(
            embed=discord.Embed(description=f"{STAR} Granted no-prefix to {name}.", color=GREEN),
            ephemeral=True,
        )


class RevokeNPModal(discord.ui.Modal, title="Revoke No-Prefix"):
    uid = discord.ui.TextInput(label="User ID", placeholder="Discord user ID", max_length=20)

    def __init__(self, bot: commands.Bot):
        super().__init__()
        self.bot = bot

    async def on_submit(self, interaction: discord.Interaction):
        try:
            uid = int(self.uid.value.strip())
        except ValueError:
            await interaction.response.send_message(
                embed=discord.Embed(description="Invalid ID.", color=RED), ephemeral=True
            )
            return

        data = load_noprefix()
        if uid not in data:
            await interaction.response.send_message(
                embed=discord.Embed(description=f"`{uid}` doesn't have no-prefix.", color=RED), ephemeral=True
            )
            return

        data.remove(uid)
        save_noprefix(data)
        user = self.bot.get_user(uid) or await self.bot.fetch_user(uid)
        name = user.mention if user else f"`{uid}`"
        await interaction.response.send_message(
            embed=discord.Embed(description=f"{LEAF} Revoked no-prefix from {name}.", color=PINK),
            ephemeral=True,
        )


class GlobalMsgModal(discord.ui.Modal, title="Global Broadcast"):
    message = discord.ui.TextInput(
        label="Message",
        style=discord.TextStyle.paragraph,
        max_length=2000,
    )

    def __init__(self, bot: commands.Bot):
        super().__init__()
        self.bot = bot

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        embed = discord.Embed(
            title=f"{STAR} Shouffle Announcement",
            description=self.message.value,
            color=PINK,
        )
        embed.set_footer(text="Raze Developments • Shouffle")

        sent = failed = 0
        for guild in self.bot.guilds:
            target = None
            for ch in guild.text_channels:
                if any(kw in ch.name.lower() for kw in ["general", "chat", "main", "lobby", "announce"]):
                    if ch.permissions_for(guild.me).send_messages:
                        target = ch
                        break
            if not target:
                for ch in guild.text_channels:
                    if ch.permissions_for(guild.me).send_messages:
                        target = ch
                        break
            if target:
                try:
                    await target.send(embed=embed)
                    sent += 1
                except Exception:
                    failed += 1
            else:
                failed += 1

        await interaction.followup.send(
            embed=discord.Embed(
                description=f"{STAR} Sent to **{sent}** servers. Failed: **{failed}**.",
                color=GREEN,
            ),
            ephemeral=True,
        )


class GrantPremiumModal(discord.ui.Modal, title="Grant Premium"):
    guild_id = discord.ui.TextInput(label="Server ID", placeholder="Discord server ID", max_length=20)

    def __init__(self, bot: commands.Bot):
        super().__init__()
        self.bot = bot

    async def on_submit(self, interaction: discord.Interaction):
        try:
            gid = int(self.guild_id.value.strip())
        except ValueError:
            await interaction.response.send_message(
                embed=discord.Embed(description="Invalid server ID.", color=RED), ephemeral=True
            )
            return

        if await _get_guild_premium(gid):
            await interaction.response.send_message(
                embed=discord.Embed(description="That server already has Premium.", color=RED), ephemeral=True
            )
            return

        await _set_guild_premium(gid, True)
        guild = self.bot.get_guild(gid)
        name = f"**{guild.name}**" if guild else f"`{gid}`"
        await interaction.response.send_message(
            embed=discord.Embed(description=f"{PREMIUM} Granted Premium to {name}.", color=GREEN),
            ephemeral=True,
        )


class RevokePremiumModal(discord.ui.Modal, title="Revoke Premium"):
    guild_id = discord.ui.TextInput(label="Server ID", placeholder="Discord server ID", max_length=20)

    def __init__(self, bot: commands.Bot):
        super().__init__()
        self.bot = bot

    async def on_submit(self, interaction: discord.Interaction):
        try:
            gid = int(self.guild_id.value.strip())
        except ValueError:
            await interaction.response.send_message(
                embed=discord.Embed(description="Invalid server ID.", color=RED), ephemeral=True
            )
            return

        if not await _get_guild_premium(gid):
            await interaction.response.send_message(
                embed=discord.Embed(description=f"`{gid}` does not have Premium.", color=RED), ephemeral=True
            )
            return

        await _set_guild_premium(gid, False)
        guild = self.bot.get_guild(gid)
        name = f"**{guild.name}**" if guild else f"`{gid}`"
        await interaction.response.send_message(
            embed=discord.Embed(description=f"{LEAF} Revoked Premium from {name}.", color=PINK),
            ephemeral=True,
        )


class OwnerView(discord.ui.View):
    def __init__(self, bot: commands.Bot):
        super().__init__(timeout=300)
        self.bot = bot

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != OWNER_ID:
            await interaction.response.send_message(
                embed=discord.Embed(description="Not authorized.", color=RED), ephemeral=True
            )
            return False
        return True

    @discord.ui.button(label="Grant NP", style=discord.ButtonStyle.primary, emoji="➕", row=0)
    async def grant_np(self, interaction: discord.Interaction, _: discord.ui.Button):
        await interaction.response.send_modal(GrantNPModal(self.bot))

    @discord.ui.button(label="Revoke NP", style=discord.ButtonStyle.danger, emoji="➖", row=0)
    async def revoke_np(self, interaction: discord.Interaction, _: discord.ui.Button):
        await interaction.response.send_modal(RevokeNPModal(self.bot))

    @discord.ui.button(label="NP List", style=discord.ButtonStyle.secondary, emoji="📋", row=0)
    async def np_list(self, interaction: discord.Interaction, _: discord.ui.Button):
        data = load_noprefix()
        if not data:
            await interaction.response.send_message(
                embed=discord.Embed(description="No no-prefix users.", color=PINK), ephemeral=True
            )
            return

        lines = []
        for uid in data:
            user = self.bot.get_user(uid) or await self.bot.fetch_user(uid)
            lines.append(f"{LEAF} {user.mention} `{uid}`" if user else f"{LEAF} Unknown `{uid}`")

        embed = discord.Embed(title=f"{STAR} No-Prefix Users", description="\n".join(lines), color=PINK)
        embed.set_footer(text=f"Raze Developments • Shouffle  —  {len(data)} user(s)")
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @discord.ui.button(label="Global Msg", style=discord.ButtonStyle.primary, emoji="📢", row=1)
    async def global_msg(self, interaction: discord.Interaction, _: discord.ui.Button):
        await interaction.response.send_modal(GlobalMsgModal(self.bot))

    @discord.ui.button(label="Set Logs", style=discord.ButtonStyle.secondary, emoji="📡", row=1)
    async def set_logs(self, interaction: discord.Interaction, _: discord.ui.Button):
        owner = load_owner()
        if owner.get("globallogs_channel"):
            ch = self.bot.get_channel(owner["globallogs_channel"])
            label = ch.mention if ch else f"`{owner['globallogs_channel']}`"
            await interaction.response.send_message(
                embed=discord.Embed(description=f"Logs already set to {label}. Reset first.", color=PINK),
                ephemeral=True,
            )
            return

        if not interaction.guild:
            await interaction.response.send_message(
                embed=discord.Embed(description="Run this inside a server.", color=RED), ephemeral=True
            )
            return

        channel = await interaction.guild.create_text_channel(
            name="shouffle-global-logs",
            topic="Shouffle server join/leave logs",
        )
        owner["globallogs_channel"] = channel.id
        save_owner(owner)

        await interaction.response.send_message(
            embed=discord.Embed(
                description=f"{STAR} Log channel created: {channel.mention}",
                color=GREEN,
            ),
            ephemeral=True,
        )

    @discord.ui.button(label="Reset Logs", style=discord.ButtonStyle.danger, emoji="🔄", row=1)
    async def reset_logs(self, interaction: discord.Interaction, _: discord.ui.Button):
        owner = load_owner()
        owner["globallogs_channel"] = None
        save_owner(owner)
        await interaction.response.send_message(
            embed=discord.Embed(description=f"{LEAF} Global logs reset.", color=PINK), ephemeral=True
        )

    @discord.ui.button(label="Grant Premium", style=discord.ButtonStyle.primary, emoji="<:premiumicon:1519965438703046750>", row=2)
    async def grant_premium(self, interaction: discord.Interaction, _: discord.ui.Button):
        await interaction.response.send_modal(GrantPremiumModal(self.bot))

    @discord.ui.button(label="Revoke Premium", style=discord.ButtonStyle.danger, emoji="<:premiumicon:1519965438703046750>", row=2)
    async def revoke_premium(self, interaction: discord.Interaction, _: discord.ui.Button):
        await interaction.response.send_modal(RevokePremiumModal(self.bot))

    @discord.ui.button(label="Refresh", style=discord.ButtonStyle.secondary, emoji="🌸", row=3)
    async def refresh(self, interaction: discord.Interaction, _: discord.ui.Button):
        await interaction.response.edit_message(embed=panel_embed(self.bot), view=self)


class Owner(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def cog_command_error(self, ctx: commands.Context, error):
        if isinstance(error, commands.CheckFailure):
            await ctx.send(
                embed=discord.Embed(description="Not authorized.", color=RED),
                delete_after=4,
            )

    @commands.command(name="owner")
    @is_owner()
    async def owner_panel(self, ctx: commands.Context):
        await ctx.send(embed=panel_embed(self.bot), view=OwnerView(self.bot))

    @commands.Cog.listener()
    async def on_guild_join(self, guild: discord.Guild):
        owner = load_owner()
        ch_id = owner.get("globallogs_channel")
        if not ch_id:
            return
        ch = self.bot.get_channel(ch_id)
        if not ch:
            return
        embed = discord.Embed(title=f"{STAR} Joined a Server", color=GREEN)
        embed.add_field(name="Server",  value=f"{guild.name} `{guild.id}`", inline=False)
        embed.add_field(name="Members", value=str(guild.member_count),      inline=True)
        embed.add_field(name="Owner",   value=f"<@{guild.owner_id}>",       inline=True)
        if guild.icon:
            embed.set_thumbnail(url=guild.icon.url)
        embed.set_footer(text=f"Raze Developments • Shouffle  —  {len(self.bot.guilds)} servers")
        await ch.send(embed=embed)

    @commands.Cog.listener()
    async def on_guild_remove(self, guild: discord.Guild):
        owner = load_owner()
        ch_id = owner.get("globallogs_channel")
        if not ch_id:
            return
        ch = self.bot.get_channel(ch_id)
        if not ch:
            return
        embed = discord.Embed(title=f"{LEAF} Left a Server", color=RED)
        embed.add_field(name="Server",  value=f"{guild.name} `{guild.id}`", inline=False)
        embed.add_field(name="Members", value=str(guild.member_count),      inline=True)
        embed.add_field(name="Owner",   value=f"<@{guild.owner_id}>",       inline=True)
        if guild.icon:
            embed.set_thumbnail(url=guild.icon.url)
        embed.set_footer(text=f"Raze Developments • Shouffle  —  {len(self.bot.guilds)} servers")
        await ch.send(embed=embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(Owner(bot))

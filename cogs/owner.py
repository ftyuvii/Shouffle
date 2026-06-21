import discord
from discord.ext import commands
from discord import app_commands
import json
import os

OWNER_ID = 907180055615123456
NOPREFIX_FILE = "noprefix.json"
OWNER_DATA_FILE = "data/owner_data.json"
EMBED_COLOR = 0xFFB6C1


def load_noprefix() -> list:
    if not os.path.exists(NOPREFIX_FILE):
        with open(NOPREFIX_FILE, "w") as f:
            json.dump([], f)
    with open(NOPREFIX_FILE, "r") as f:
        return json.load(f)


def save_noprefix(data: list):
    with open(NOPREFIX_FILE, "w") as f:
        json.dump(data, f, indent=2)


def load_owner_data() -> dict:
    os.makedirs("data", exist_ok=True)
    if not os.path.exists(OWNER_DATA_FILE):
        with open(OWNER_DATA_FILE, "w") as f:
            json.dump({"globallogs_channel": None}, f)
    with open(OWNER_DATA_FILE, "r") as f:
        return json.load(f)


def save_owner_data(data: dict):
    with open(OWNER_DATA_FILE, "w") as f:
        json.dump(data, f, indent=2)


def is_owner():
    async def predicate(ctx: commands.Context):
        return ctx.author.id == OWNER_ID
    return commands.check(predicate)


class Owner(commands.Cog):

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    def _err(self, desc: str) -> discord.Embed:
        return discord.Embed(description=desc, color=0xFF6B6B)

    def _ok(self, desc: str) -> discord.Embed:
        return discord.Embed(description=desc, color=EMBED_COLOR)

    async def cog_command_error(self, ctx: commands.Context, error):
        if isinstance(error, commands.CheckFailure):
            await ctx.send(embed=self._err("You are not authorized to use this command."), delete_after=5)

    @commands.command(name="owner")
    @is_owner()
    async def owner_panel(self, ctx: commands.Context):
        embed = discord.Embed(
            title="Owner Panel",
            description="Commands available exclusively to the bot owner.",
            color=EMBED_COLOR
        )
        embed.add_field(
            name="No Prefix",
            value=(
                "`?np <user>` — Grant no-prefix access\n"
                "`?np show` — List no-prefix users\n"
                "`?np remove <user>` — Revoke no-prefix access"
            ),
            inline=False
        )
        embed.add_field(
            name="Bot Management",
            value=(
                "`?cc` — View all loaded commands\n"
                "`?globalmsg <message>` — Broadcast message to all servers\n"
                "`?globallogs` — Set up server join/leave log channel"
            ),
            inline=False
        )
        embed.set_footer(text="Shouffle • Owner")
        await ctx.send(embed=embed)

    @commands.group(name="np", invoke_without_command=True)
    @is_owner()
    async def np(self, ctx: commands.Context, user: discord.User = None):
        if user is None:
            await ctx.send(embed=self._err("Usage: `?np <user>` | `?np show` | `?np remove <user>`"))
            return

        data = load_noprefix()
        if user.id in data:
            await ctx.send(embed=self._err(f"{user.mention} already has no-prefix access."))
            return

        data.append(user.id)
        save_noprefix(data)
        await ctx.send(embed=self._ok(f"✅ Granted no-prefix access to {user.mention}."))

    @np.command(name="show")
    @is_owner()
    async def np_show(self, ctx: commands.Context):
        data = load_noprefix()
        if not data:
            await ctx.send(embed=self._ok("No users currently have no-prefix access."))
            return

        lines = []
        for uid in data:
            user = self.bot.get_user(uid) or await self.bot.fetch_user(uid)
            lines.append(f"• {user.mention} (`{uid}`)" if user else f"• Unknown (`{uid}`)")

        embed = discord.Embed(
            title="No-Prefix Users",
            description="\n".join(lines),
            color=EMBED_COLOR
        )
        embed.set_footer(text=f"Shouffle • Owner  |  {len(data)} user(s)")
        await ctx.send(embed=embed)

    @np.command(name="remove")
    @is_owner()
    async def np_remove(self, ctx: commands.Context, user: discord.User = None):
        if user is None:
            await ctx.send(embed=self._err("Usage: `?np remove <user>`"))
            return

        data = load_noprefix()
        if user.id not in data:
            await ctx.send(embed=self._err(f"{user.mention} does not have no-prefix access."))
            return

        data.remove(user.id)
        save_noprefix(data)
        await ctx.send(embed=self._ok(f"✅ Removed no-prefix access from {user.mention}."))

    @commands.command(name="cc")
    @is_owner()
    async def current_commands(self, ctx: commands.Context):
        prefix_cmds = sorted(
            [f"`?{cmd.qualified_name}`" for cmd in self.bot.walk_commands()],
            key=lambda x: x.lower()
        )
        slash_cmds = sorted(
            [f"`/{cmd.name}`" for cmd in self.bot.tree.get_commands()],
            key=lambda x: x.lower()
        )

        embed = discord.Embed(
            title="Loaded Commands",
            color=EMBED_COLOR
        )
        embed.add_field(
            name=f"Prefix Commands ({len(prefix_cmds)})",
            value=", ".join(prefix_cmds) if prefix_cmds else "None",
            inline=False
        )
        embed.add_field(
            name=f"Slash Commands ({len(slash_cmds)})",
            value=", ".join(slash_cmds) if slash_cmds else "None",
            inline=False
        )
        embed.set_footer(text="Shouffle • Owner")
        await ctx.send(embed=embed)

    @commands.command(name="globalmsg")
    @is_owner()
    async def global_message(self, ctx: commands.Context, *, message: str = None):
        if not message:
            await ctx.send(embed=self._err("Usage: `?globalmsg <message>`"))
            return

        embed = discord.Embed(
            title="📢 Announcement from Shouffle",
            description=message,
            color=EMBED_COLOR
        )
        embed.set_footer(text="Shouffle • Global Announcement")

        sent, failed = 0, 0
        status_msg = await ctx.send(embed=self._ok("Broadcasting message to all servers..."))

        for guild in self.bot.guilds:
            target_channel = None

            for ch in guild.text_channels:
                if any(keyword in ch.name.lower() for keyword in ["general", "chat", "main", "lobby", "announcements"]):
                    if ch.permissions_for(guild.me).send_messages:
                        target_channel = ch
                        break

            if not target_channel:
                for ch in guild.text_channels:
                    if ch.permissions_for(guild.me).send_messages:
                        target_channel = ch
                        break

            if target_channel:
                try:
                    await target_channel.send(embed=embed)
                    sent += 1
                except Exception:
                    failed += 1
            else:
                failed += 1

        await status_msg.edit(embed=self._ok(
            f"✅ Broadcast complete.\n\n**Sent:** {sent} servers\n**Failed:** {failed} servers"
        ))

    @commands.command(name="globallogs")
    @is_owner()
    async def global_logs(self, ctx: commands.Context, action: str = None):
        data = load_owner_data()

        if action and action.lower() == "reset":
            data["globallogs_channel"] = None
            save_owner_data(data)
            await ctx.send(embed=self._ok("✅ Global logs channel reset. Use `?globallogs` to set a new one."))
            return

        existing_id = data.get("globallogs_channel")
        if existing_id:
            ch = self.bot.get_channel(existing_id)
            if ch:
                await ctx.send(embed=self._ok(
                    f"Global logs channel is already set to {ch.mention}.\n"
                    f"Use `?globallogs reset` to change it."
                ))
                return

        channel = await ctx.guild.create_text_channel(
            name="shouffle-global-logs",
            topic="Shouffle server join/leave logs"
        )

        data["globallogs_channel"] = channel.id
        save_owner_data(data)

        embed = discord.Embed(
            title="Global Logs Active",
            description=(
                f"✅ Log channel created: {channel.mention}\n\n"
                "This channel will log every server Shouffle joins or leaves."
            ),
            color=EMBED_COLOR
        )
        embed.set_footer(text="Shouffle • Owner")
        await ctx.send(embed=embed)

    @commands.Cog.listener()
    async def on_guild_join(self, guild: discord.Guild):
        data = load_owner_data()
        channel_id = data.get("globallogs_channel")
        if not channel_id:
            return

        channel = self.bot.get_channel(channel_id)
        if not channel:
            return

        embed = discord.Embed(
            title="Joined a Server",
            color=0x77DD77
        )
        embed.add_field(name="Server", value=f"{guild.name} (`{guild.id}`)", inline=False)
        embed.add_field(name="Members", value=str(guild.member_count), inline=True)
        embed.add_field(name="Owner", value=f"<@{guild.owner_id}>", inline=True)
        if guild.icon:
            embed.set_thumbnail(url=guild.icon.url)
        embed.set_footer(text=f"Shouffle • Total Servers: {len(self.bot.guilds)}")
        await channel.send(embed=embed)

    @commands.Cog.listener()
    async def on_guild_remove(self, guild: discord.Guild):
        data = load_owner_data()
        channel_id = data.get("globallogs_channel")
        if not channel_id:
            return

        channel = self.bot.get_channel(channel_id)
        if not channel:
            return

        embed = discord.Embed(
            title="Left a Server",
            color=0xFF6B6B
        )
        embed.add_field(name="Server", value=f"{guild.name} (`{guild.id}`)", inline=False)
        embed.add_field(name="Members", value=str(guild.member_count), inline=True)
        embed.add_field(name="Owner", value=f"<@{guild.owner_id}>", inline=True)
        if guild.icon:
            embed.set_thumbnail(url=guild.icon.url)
        embed.set_footer(text=f"Shouffle • Total Servers: {len(self.bot.guilds)}")
        await channel.send(embed=embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(Owner(bot))

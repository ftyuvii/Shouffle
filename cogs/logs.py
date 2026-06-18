import discord
from discord.ext import commands
import datetime
import asyncio


LOG_CHANNEL_NAME = "bot-logs"
LOG_COLOR = 0xFFBFEA


class Logs(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.log_channels: dict[int, discord.TextChannel] = {}

    async def get_log_channel(self, guild: discord.Guild) -> discord.TextChannel | None:
        channel = discord.utils.get(guild.text_channels, name=LOG_CHANNEL_NAME)
        if channel:
            self.log_channels[guild.id] = channel
        return channel

    async def send_log(self, guild: discord.Guild, embed: discord.Embed):
        channel = self.log_channels.get(guild.id) or await self.get_log_channel(guild)
        if channel:
            try:
                await channel.send(embed=embed)
            except discord.Forbidden:
                pass

    def base_embed(self, title: str, description: str, color: int = LOG_COLOR) -> discord.Embed:
        embed = discord.Embed(
            title=title,
            description=description,
            color=color,
            timestamp=datetime.datetime.utcnow(),
        )
        embed.set_thumbnail(url=self.bot.user.display_avatar.url)
        embed.set_footer(text=f"{self.bot.user.name} Logs", icon_url=self.bot.user.display_avatar.url)
        return embed

    @commands.command(name="botlogs")
    @commands.has_permissions(administrator=True)
    async def botlogs(self, ctx: commands.Context, action: str):
        action = action.lower()

        if action == "enable":
            existing = await self.get_log_channel(ctx.guild)
            if existing:
                embed = self.base_embed(
                    "⚠️ Already Enabled",
                    f"A bot logs channel already exists: {existing.mention}",
                    color=0xF0A500,
                )
                return await ctx.send(embed=embed)

            overwrites = {
                ctx.guild.default_role: discord.PermissionOverwrite(send_messages=False, read_messages=False),
                ctx.guild.me: discord.PermissionOverwrite(send_messages=True, read_messages=True, embed_links=True),
            }

            for role in ctx.guild.roles:
                if role.permissions.administrator:
                    overwrites[role] = discord.PermissionOverwrite(read_messages=True, send_messages=False)

            channel = await ctx.guild.create_text_channel(
                name=LOG_CHANNEL_NAME,
                overwrites=overwrites,
                topic="📋 Automated bot activity logs — Do not post here.",
                reason="Bot logs channel created via ?botlogs enable",
            )

            self.log_channels[ctx.guild.id] = channel

            welcome_embed = self.base_embed(
                "🟢 Bot Logs Activated",
                (
                    "This channel will now receive **real-time automated logs** for all significant "
                    "bot and server events.\n\n"
                    "**Tracked Events Include:**\n"
                    "› Member joins & leaves\n"
                    "› Message edits & deletions\n"
                    "› Role & channel changes\n"
                    "› Voice state updates\n"
                    "› Command executions\n"
                    "› Errors & warnings\n\n"
                    f"**Logging started:** <t:{int(datetime.datetime.utcnow().timestamp())}:F>"
                ),
                color=0x57F287,
            )
            await channel.send(embed=welcome_embed)

            confirm_embed = self.base_embed(
                "✅ Logging Enabled",
                f"Bot logs channel created successfully: {channel.mention}",
                color=0x57F287,
            )
            await ctx.send(embed=confirm_embed)

        elif action == "disable":
            channel = await self.get_log_channel(ctx.guild)
            if not channel:
                embed = self.base_embed(
                    "❌ Not Found",
                    "No active bot logs channel was found on this server.",
                    color=0xED4245,
                )
                return await ctx.send(embed=embed)

            farewell_embed = self.base_embed(
                "🔴 Bot Logs Deactivated",
                (
                    "Logging has been **disabled** by an administrator.\n"
                    "This channel will be deleted in **5 seconds**.\n\n"
                    f"**Logging ended:** <t:{int(datetime.datetime.utcnow().timestamp())}:F>"
                ),
                color=0xED4245,
            )
            await channel.send(embed=farewell_embed)
            await asyncio.sleep(5)
            await channel.delete(reason="Bot logs disabled via ?botlogs disable")

            self.log_channels.pop(ctx.guild.id, None)

            confirm_embed = self.base_embed(
                "🗑️ Logging Disabled",
                "The bot logs channel has been removed successfully.",
                color=0xED4245,
            )
            await ctx.send(embed=confirm_embed)

        else:
            embed = self.base_embed(
                "❓ Invalid Usage",
                "**Usage:**\n`?botlogs enable` — Create and activate the log channel.\n`?botlogs disable` — Delete the existing log channel.",
                color=0xED4245,
            )
            await ctx.send(embed=embed)

    @botlogs.error
    async def botlogs_error(self, ctx: commands.Context, error):
        if isinstance(error, commands.MissingPermissions):
            embed = self.base_embed(
                "🚫 Permission Denied",
                "You need **Administrator** permission to manage bot logs.",
                color=0xED4245,
            )
            await ctx.send(embed=embed)
        elif isinstance(error, commands.MissingRequiredArgument):
            embed = self.base_embed(
                "❓ Missing Argument",
                "**Usage:**\n`?botlogs enable`\n`?botlogs disable`",
                color=0xED4245,
            )
            await ctx.send(embed=embed)

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        embed = self.base_embed(
            "📥 Member Joined",
            f"{member.mention} joined the server.",
            color=0x57F287,
        )
        embed.add_field(name="User", value=f"`{member}` ({member.id})", inline=True)
        embed.add_field(name="Account Created", value=f"<t:{int(member.created_at.timestamp())}:R>", inline=True)
        embed.set_thumbnail(url=member.display_avatar.url)
        await self.send_log(member.guild, embed)

    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member):
        embed = self.base_embed(
            "📤 Member Left",
            f"**{member}** left or was removed from the server.",
            color=0xED4245,
        )
        embed.add_field(name="User ID", value=f"`{member.id}`", inline=True)
        roles = [r.mention for r in member.roles if r != member.guild.default_role]
        embed.add_field(name="Roles", value=", ".join(roles) if roles else "None", inline=False)
        embed.set_thumbnail(url=member.display_avatar.url)
        await self.send_log(member.guild, embed)

    @commands.Cog.listener()
    async def on_message_delete(self, message: discord.Message):
        if message.author.bot or not message.guild:
            return
        embed = self.base_embed(
            "🗑️ Message Deleted",
            f"A message by {message.author.mention} was deleted in {message.channel.mention}.",
            color=0xF0A500,
        )
        embed.add_field(name="Content", value=message.content[:1024] or "*Empty*", inline=False)
        embed.add_field(name="Author", value=f"`{message.author}` ({message.author.id})", inline=True)
        embed.set_thumbnail(url=message.author.display_avatar.url)
        await self.send_log(message.guild, embed)

    @commands.Cog.listener()
    async def on_message_edit(self, before: discord.Message, after: discord.Message):
        if before.author.bot or not before.guild or before.content == after.content:
            return
        embed = self.base_embed(
            "✏️ Message Edited",
            f"A message by {before.author.mention} was edited in {before.channel.mention}. [Jump]({after.jump_url})",
            color=0x5865F2,
        )
        embed.add_field(name="Before", value=before.content[:512] or "*Empty*", inline=False)
        embed.add_field(name="After", value=after.content[:512] or "*Empty*", inline=False)
        embed.set_thumbnail(url=before.author.display_avatar.url)
        await self.send_log(before.guild, embed)

    @commands.Cog.listener()
    async def on_guild_channel_create(self, channel: discord.abc.GuildChannel):
        embed = self.base_embed(
            "➕ Channel Created",
            f"New channel **#{channel.name}** was created.",
            color=0x57F287,
        )
        embed.add_field(name="Type", value=str(channel.type).replace("_", " ").title(), inline=True)
        embed.add_field(name="ID", value=f"`{channel.id}`", inline=True)
        await self.send_log(channel.guild, embed)

    @commands.Cog.listener()
    async def on_guild_channel_delete(self, channel: discord.abc.GuildChannel):
        embed = self.base_embed(
            "➖ Channel Deleted",
            f"Channel **#{channel.name}** was deleted.",
            color=0xED4245,
        )
        embed.add_field(name="Type", value=str(channel.type).replace("_", " ").title(), inline=True)
        embed.add_field(name="ID", value=f"`{channel.id}`", inline=True)
        await self.send_log(channel.guild, embed)

    @commands.Cog.listener()
    async def on_guild_role_create(self, role: discord.Role):
        embed = self.base_embed(
            "🎭 Role Created",
            f"New role **{role.name}** was created.",
            color=0x57F287,
        )
        embed.add_field(name="Color", value=str(role.color), inline=True)
        embed.add_field(name="Mentionable", value=str(role.mentionable), inline=True)
        embed.add_field(name="ID", value=f"`{role.id}`", inline=True)
        await self.send_log(role.guild, embed)

    @commands.Cog.listener()
    async def on_guild_role_delete(self, role: discord.Role):
        embed = self.base_embed(
            "🎭 Role Deleted",
            f"Role **{role.name}** was deleted.",
            color=0xED4245,
        )
        embed.add_field(name="ID", value=f"`{role.id}`", inline=True)
        await self.send_log(role.guild, embed)

    @commands.Cog.listener()
    async def on_member_ban(self, guild: discord.Guild, user: discord.User):
        embed = self.base_embed(
            "🔨 Member Banned",
            f"**{user}** was banned from the server.",
            color=0xED4245,
        )
        embed.add_field(name="User ID", value=f"`{user.id}`", inline=True)
        embed.set_thumbnail(url=user.display_avatar.url)
        await self.send_log(guild, embed)

    @commands.Cog.listener()
    async def on_member_unban(self, guild: discord.Guild, user: discord.User):
        embed = self.base_embed(
            "🔓 Member Unbanned",
            f"**{user}** was unbanned from the server.",
            color=0x57F287,
        )
        embed.add_field(name="User ID", value=f"`{user.id}`", inline=True)
        embed.set_thumbnail(url=user.display_avatar.url)
        await self.send_log(guild, embed)

    @commands.Cog.listener()
    async def on_voice_state_update(self, member: discord.Member, before: discord.VoiceState, after: discord.VoiceState):
        if before.channel == after.channel:
            return
        if after.channel and not before.channel:
            desc = f"{member.mention} joined voice channel **{after.channel.name}**."
            color = 0x57F287
            title = "🔊 Voice Join"
        elif before.channel and not after.channel:
            desc = f"{member.mention} left voice channel **{before.channel.name}**."
            color = 0xED4245
            title = "🔇 Voice Leave"
        else:
            desc = f"{member.mention} moved from **{before.channel.name}** → **{after.channel.name}**."
            color = 0x5865F2
            title = "🔀 Voice Move"
        embed = self.base_embed(title, desc, color=color)
        embed.set_thumbnail(url=member.display_avatar.url)
        await self.send_log(member.guild, embed)

    @commands.Cog.listener()
    async def on_command(self, ctx: commands.Context):
        if not ctx.guild:
            return
        embed = self.base_embed(
            "⚙️ Command Executed",
            f"`{ctx.prefix}{ctx.command}` used by {ctx.author.mention} in {ctx.channel.mention}.",
            color=0x5865F2,
        )
        embed.add_field(name="Full Input", value=f"`{ctx.message.content[:512]}`", inline=False)
        embed.add_field(name="User ID", value=f"`{ctx.author.id}`", inline=True)
        embed.set_thumbnail(url=ctx.author.display_avatar.url)
        await self.send_log(ctx.guild, embed)

    @commands.Cog.listener()
    async def on_command_error(self, ctx: commands.Context, error: commands.CommandError):
        if not ctx.guild:
            return
        ignored = (commands.CommandNotFound,)
        if isinstance(error, ignored):
            return
        embed = self.base_embed(
            "⚠️ Command Error",
            f"An error occurred while running `{ctx.prefix}{ctx.command}` in {ctx.channel.mention}.",
            color=0xF0A500,
        )
        embed.add_field(name="Error", value=f"```{str(error)[:512]}```", inline=False)
        embed.add_field(name="User", value=f"{ctx.author.mention} (`{ctx.author.id}`)", inline=True)
        embed.set_thumbnail(url=ctx.author.display_avatar.url)
        await self.send_log(ctx.guild, embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(Logs(bot))
import discord
from discord.ext import commands, tasks
import asyncio
import json
import os
import feedparser
import urllib.request
import urllib.error
import re
from datetime import datetime, timezone

JSON_FILE = "youtube_channels.json"


class YouTubeNotification(commands.Cog):
    """Professional YouTube Notification System for Discord."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.data = self.load_data()
        self.check_youtube_videos.start()

    # ──────────────────────────────────────────────
    #  Data Helpers
    # ──────────────────────────────────────────────

    def load_data(self) -> dict:
        if not os.path.exists(JSON_FILE):
            with open(JSON_FILE, "w") as f:
                json.dump({}, f, indent=4)
            return {}
        try:
            with open(JSON_FILE, "r") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            return {}

    def save_data(self) -> None:
        with open(JSON_FILE, "w") as f:
            json.dump(self.data, f, indent=4)

    def cog_unload(self):
        self.check_youtube_videos.cancel()

    # ──────────────────────────────────────────────
    #  YouTube Helpers
    # ──────────────────────────────────────────────

    def get_channel_id(self, url: str) -> str | None:
        """
        Resolve a YouTube URL to a channel ID (UCxxxxxxx format).
        Supports:
          - https://www.youtube.com/channel/UCxxxxxxx
          - https://www.youtube.com/@Handle
          - https://www.youtube.com/c/CustomName
          - https://www.youtube.com/user/Username
        """
        url = url.strip().rstrip("/")

        # Direct channel ID in URL
        match = re.search(r"youtube\.com/channel/(UC[a-zA-Z0-9_-]{22})", url)
        if match:
            return match.group(1)

        # Fetch HTML page and extract channel ID
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            "Accept-Language": "en-US,en;q=0.9",
        }
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=15) as resp:
                html = resp.read().decode("utf-8", errors="replace")
        except (urllib.error.URLError, OSError) as exc:
            print(f"[YouTube] Failed to fetch URL {url!r}: {exc}")
            return None

        # Pattern 1 – RSS feed link embedded in <head>
        m = re.search(
            r'https://www\.youtube\.com/feeds/videos\.xml\?channel_id=(UC[a-zA-Z0-9_-]{22})',
            html,
        )
        if m:
            return m.group(1)

        # Pattern 2 – meta itemprop
        m = re.search(r'itemprop="channelId"\s+content="(UC[a-zA-Z0-9_-]{22})"', html)
        if m:
            return m.group(1)

        # Pattern 3 – browse endpoint JSON in page source
        m = re.search(r'"browseId":\s*"(UC[a-zA-Z0-9_-]{22})"', html)
        if m:
            return m.group(1)

        print(f"[YouTube] Could not extract channel ID from {url!r}")
        return None

    def fetch_latest_video(self, channel_id: str) -> dict | None:
        """
        Return a dict with keys: id, title, url, thumbnail, published
        for the most recent public video, or None on failure.
        """
        feed_url = f"https://www.youtube.com/feeds/videos.xml?channel_id={channel_id}"
        try:
            feed = feedparser.parse(feed_url)
        except Exception as exc:
            print(f"[YouTube] feedparser error for {channel_id}: {exc}")
            return None

        if not feed.entries:
            return None

        entry = feed.entries[0]
        video_id = entry.get("yt_videoid") or entry.id.split(":")[-1]

        # Thumbnail via yt:media
        thumbnail = None
        media_group = entry.get("media_group", {})
        if media_group:
            thumb_list = media_group.get("media_thumbnail", [])
            if thumb_list:
                thumbnail = thumb_list[0].get("url")
        if not thumbnail:
            thumbnail = f"https://img.youtube.com/vi/{video_id}/maxresdefault.jpg"

        # Published timestamp
        published = entry.get("published", "")

        return {
            "id": video_id,
            "title": entry.get("title", "Unknown Title"),
            "url": entry.get("link", f"https://www.youtube.com/watch?v={video_id}"),
            "thumbnail": thumbnail,
            "published": published,
            "channel_name": entry.get("author", "YouTube"),
        }

    def build_notification_embed(self, video: dict, channel_name_override: str | None = None) -> discord.Embed:
        """Build a rich embed for a new video notification."""
        channel_name = channel_name_override or video.get("channel_name", "YouTube")

        embed = discord.Embed(
            title=video["title"],
            url=video["url"],
            color=0xFF0000,
        )
        embed.set_author(
            name=channel_name,
            icon_url="https://www.youtube.com/s/desktop/f506bd45/img/favicon_144x144.png",
        )
        embed.set_image(url=video["thumbnail"])
        embed.set_footer(text="YouTube • New Video")

        if video.get("published"):
            try:
                dt = datetime(*[
                    int(x) for x in re.findall(r"\d+", video["published"])[:6]
                ], tzinfo=timezone.utc)
                embed.timestamp = dt
            except Exception:
                embed.timestamp = datetime.now(timezone.utc)
        else:
            embed.timestamp = datetime.now(timezone.utc)

        return embed

    # ──────────────────────────────────────────────
    #  Error Handler
    # ──────────────────────────────────────────────

    async def cog_command_error(self, ctx: commands.Context, error: Exception):
        if isinstance(error, commands.MissingPermissions):
            await ctx.send(
                embed=discord.Embed(
                    description="❌ You need **Administrator** permission to use this command.",
                    color=discord.Color.red(),
                )
            )
        elif isinstance(error, commands.NoPrivateMessage):
            await ctx.send("This command can only be used inside a server.")
        else:
            raise error

    # ──────────────────────────────────────────────
    #  ?youtube  –  Add a new subscription
    # ──────────────────────────────────────────────

    @commands.command(name="youtube")
    @commands.has_permissions(administrator=True)
    @commands.guild_only()
    async def setup_youtube(self, ctx: commands.Context):
        """Interactive wizard to add a YouTube channel notification."""

        def check(m: discord.Message) -> bool:
            return m.author == ctx.author and m.channel == ctx.channel

        async def ask(prompt: str) -> discord.Message | None:
            await ctx.send(embed=discord.Embed(description=prompt, color=0x5865F2))
            try:
                return await self.bot.wait_for("message", check=check, timeout=60.0)
            except asyncio.TimeoutError:
                await ctx.send(
                    embed=discord.Embed(
                        description="⏱️ Timed out. Setup cancelled.",
                        color=discord.Color.red(),
                    )
                )
                return None

        # ── Step 1: YouTube URL ──
        msg = await ask(
            "🎥 **Step 1/3 — YouTube Channel URL**\n"
            "Send the YouTube channel link.\n"
            "Examples: `https://www.youtube.com/@MrBeast` or `https://www.youtube.com/channel/UCxxxxxxx`"
        )
        if msg is None:
            return
        yt_url = msg.content.strip()

        verifying = await ctx.send(
            embed=discord.Embed(description="🔍 Verifying channel…", color=0xFEE75C)
        )

        channel_id = self.get_channel_id(yt_url)
        if not channel_id:
            await verifying.delete()
            return await ctx.send(
                embed=discord.Embed(
                    description=(
                        "❌ Could not find the channel. Make sure the URL is valid.\n"
                        "Try: `https://www.youtube.com/@ChannelHandle`"
                    ),
                    color=discord.Color.red(),
                )
            )

        latest = self.fetch_latest_video(channel_id)
        latest_video_id = latest["id"] if latest else None
        channel_display_name = latest.get("channel_name", channel_id) if latest else channel_id

        await verifying.edit(
            embed=discord.Embed(
                description=f"✅ Found channel: **{channel_display_name}**",
                color=discord.Color.green(),
            )
        )

        # ── Step 2: Ping Role ──
        msg = await ask(
            "🔔 **Step 2/3 — Ping Role**\n"
            "Mention a role to ping on new videos, or type `none` to skip."
        )
        if msg is None:
            return

        ping_role_id = None
        if msg.content.lower().strip() != "none":
            try:
                role = await commands.RoleConverter().convert(ctx, msg.content.strip())
                ping_role_id = role.id
            except commands.BadArgument:
                return await ctx.send(
                    embed=discord.Embed(
                        description="❌ Role not found. Setup cancelled.",
                        color=discord.Color.red(),
                    )
                )

        # ── Step 3: Discord Channel ──
        msg = await ask(
            "📺 **Step 3/3 — Notification Channel**\n"
            "Mention the Discord text channel where notifications should be sent."
        )
        if msg is None:
            return

        try:
            target_channel = await commands.TextChannelConverter().convert(ctx, msg.content.strip())
        except commands.BadArgument:
            return await ctx.send(
                embed=discord.Embed(
                    description="❌ Text channel not found. Setup cancelled.",
                    color=discord.Color.red(),
                )
            )

        # ── Save ──
        guild_id = str(ctx.guild.id)
        self.data.setdefault(guild_id, {})[channel_id] = {
            "channel_url": yt_url,
            "channel_name": channel_display_name,
            "discord_channel_id": target_channel.id,
            "ping_role_id": ping_role_id,
            "last_video_id": latest_video_id,
            "added_by": ctx.author.id,
            "added_at": datetime.now(timezone.utc).isoformat(),
        }
        self.save_data()

        embed = discord.Embed(
            title="✅ YouTube Notifications Enabled",
            color=discord.Color.green(),
            timestamp=datetime.now(timezone.utc),
        )
        embed.add_field(name="📺 YouTube Channel", value=f"[{channel_display_name}]({yt_url})", inline=False)
        embed.add_field(name="💬 Post In", value=target_channel.mention, inline=True)
        embed.add_field(
            name="🔔 Ping Role",
            value=f"<@&{ping_role_id}>" if ping_role_id else "None",
            inline=True,
        )
        embed.set_footer(text=f"Set up by {ctx.author}", icon_url=ctx.author.display_avatar.url)
        await ctx.send(embed=embed)

    # ──────────────────────────────────────────────
    #  ?youtubeconfig  –  Manage subscriptions
    # ──────────────────────────────────────────────

    @commands.command(name="youtubeconfig")
    @commands.has_permissions(administrator=True)
    @commands.guild_only()
    async def youtube_config(self, ctx: commands.Context, action: str = "list", *, target: str = ""):
        """
        Manage YouTube notification subscriptions.

        Actions:
          list              – Show all subscriptions for this server
          remove <channel>  – Remove a subscription (channel ID or partial name)
          test <channel>    – Send a test notification for a subscription
        """
        action = action.lower().strip()
        guild_id = str(ctx.guild.id)
        guild_data: dict = self.data.get(guild_id, {})

        # ── LIST ──
        if action == "list":
            if not guild_data:
                return await ctx.send(
                    embed=discord.Embed(
                        description="📭 No YouTube channels are set up yet. Use `?youtube` to add one.",
                        color=0x5865F2,
                    )
                )

            embed = discord.Embed(
                title="📋 YouTube Subscriptions",
                color=0xFF0000,
                timestamp=datetime.now(timezone.utc),
            )
            for idx, (ch_id, cfg) in enumerate(guild_data.items(), start=1):
                discord_ch = ctx.guild.get_channel(cfg["discord_channel_id"])
                role_text = f"<@&{cfg['ping_role_id']}>" if cfg.get("ping_role_id") else "None"
                embed.add_field(
                    name=f"{idx}. {cfg.get('channel_name', ch_id)}",
                    value=(
                        f"**ID:** `{ch_id}`\n"
                        f"**Posts In:** {discord_ch.mention if discord_ch else '`deleted`'}\n"
                        f"**Ping:** {role_text}"
                    ),
                    inline=False,
                )
            embed.set_footer(text=f"{len(guild_data)} subscription(s)")
            return await ctx.send(embed=embed)

        # ── REMOVE ──
        if action == "remove":
            if not target:
                return await ctx.send(
                    embed=discord.Embed(
                        description="Usage: `?youtubeconfig remove <channel ID or name>`",
                        color=discord.Color.red(),
                    )
                )

            # Match by channel ID or partial name
            matched_id = None
            for ch_id, cfg in guild_data.items():
                if target.lower() in ch_id.lower() or target.lower() in cfg.get("channel_name", "").lower():
                    matched_id = ch_id
                    break

            if not matched_id:
                return await ctx.send(
                    embed=discord.Embed(
                        description=f"❌ No subscription found matching `{target}`.",
                        color=discord.Color.red(),
                    )
                )

            removed_name = guild_data[matched_id].get("channel_name", matched_id)
            del self.data[guild_id][matched_id]
            if not self.data[guild_id]:
                del self.data[guild_id]
            self.save_data()

            return await ctx.send(
                embed=discord.Embed(
                    description=f"🗑️ Removed subscription for **{removed_name}**.",
                    color=discord.Color.orange(),
                )
            )

        # ── TEST ──
        if action == "test":
            if not guild_data:
                return await ctx.send(
                    embed=discord.Embed(
                        description="No subscriptions found. Add one with `?youtube`.",
                        color=discord.Color.red(),
                    )
                )

            # Pick by name/ID or default to first
            cfg_to_test = None
            ch_id_to_test = None
            if target:
                for ch_id, cfg in guild_data.items():
                    if target.lower() in ch_id.lower() or target.lower() in cfg.get("channel_name", "").lower():
                        cfg_to_test = cfg
                        ch_id_to_test = ch_id
                        break
                if cfg_to_test is None:
                    return await ctx.send(
                        embed=discord.Embed(
                            description=f"❌ No subscription matching `{target}`.",
                            color=discord.Color.red(),
                        )
                    )
            else:
                ch_id_to_test, cfg_to_test = next(iter(guild_data.items()))

            discord_ch = ctx.guild.get_channel(cfg_to_test["discord_channel_id"])
            if not discord_ch:
                return await ctx.send(
                    embed=discord.Embed(
                        description="❌ The target Discord channel no longer exists. Please reconfigure.",
                        color=discord.Color.red(),
                    )
                )

            video = self.fetch_latest_video(ch_id_to_test)
            if not video:
                return await ctx.send(
                    embed=discord.Embed(
                        description="❌ Could not fetch a video for this channel.",
                        color=discord.Color.red(),
                    )
                )

            embed = self.build_notification_embed(video, cfg_to_test.get("channel_name"))
            ping_msg = f"<@&{cfg_to_test['ping_role_id']}> " if cfg_to_test.get("ping_role_id") else ""
            await discord_ch.send(
                content=f"🔔 **[TEST]** {ping_msg}",
                embed=embed,
            )
            return await ctx.send(
                embed=discord.Embed(
                    description=f"✅ Test notification sent to {discord_ch.mention}.",
                    color=discord.Color.green(),
                )
            )

        # Unknown action
        await ctx.send(
            embed=discord.Embed(
                description=(
                    "❓ Unknown action. Available actions:\n"
                    "`?youtubeconfig list` — list all subscriptions\n"
                    "`?youtubeconfig remove <name>` — remove a subscription\n"
                    "`?youtubeconfig test [name]` — send a test notification"
                ),
                color=0x5865F2,
            )
        )

    # ──────────────────────────────────────────────
    #  Background Loop — check every 5 minutes
    # ──────────────────────────────────────────────

    @tasks.loop(minutes=5.0)
    async def check_youtube_videos(self):
        for guild_id, channels in list(self.data.items()):
            guild = self.bot.get_guild(int(guild_id))
            if not guild:
                continue

            for channel_id, config in list(channels.items()):
                try:
                    discord_channel = guild.get_channel(config["discord_channel_id"])
                    if not discord_channel:
                        continue

                    video = self.fetch_latest_video(channel_id)
                    if not video:
                        continue

                    if video["id"] == config.get("last_video_id"):
                        continue  # No new video

                    # ── Send notification ──
                    embed = self.build_notification_embed(video, config.get("channel_name"))
                    ping_msg = f"<@&{config['ping_role_id']}> " if config.get("ping_role_id") else ""

                    await discord_channel.send(
                        content=f"🔔 {ping_msg}**New video from {config.get('channel_name', 'YouTube')}!**",
                        embed=embed,
                    )

                    # Update stored video ID
                    self.data[guild_id][channel_id]["last_video_id"] = video["id"]
                    self.save_data()

                except discord.Forbidden:
                    print(f"[YouTube] Missing send permission in guild {guild_id} channel {channel_id}")
                except discord.HTTPException as exc:
                    print(f"[YouTube] Discord HTTP error for {channel_id}: {exc}")
                except Exception as exc:
                    print(f"[YouTube] Unexpected error for {channel_id}: {exc}")

    @check_youtube_videos.before_loop
    async def before_check(self):
        await self.bot.wait_until_ready()


async def setup(bot: commands.Bot):
    await bot.add_cog(YouTubeNotification(bot))

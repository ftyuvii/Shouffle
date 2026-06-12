import discord
from discord.ext import commands
from datetime import datetime, timezone
import json
import os
import re
import random
import aiohttp

COLOUR    = 0xADD8E6
COLOUR_OK = 0x57F287   # green
COLOUR_ERR= 0xED4245   # red


class General(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot       = bot
        self.ar_file   = "autoresponders.json"
        self.media_file= "mediaonly.json"

    # ── JSON helpers ─────────────────────────────────────────────────────────

    def _load_json(self, path: str) -> dict:
        if not os.path.exists(path):
            return {}
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}

    def _save_json(self, path: str, data: dict) -> None:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4)

    # ── Embed builder ────────────────────────────────────────────────────────

    def _embed(self, title: str = None, description: str = None,
               colour: int = COLOUR, *, thumbnail: str = None,
               image: str = None, requester: discord.Member = None) -> discord.Embed:
        e = discord.Embed(title=title, description=description, color=colour)
        if thumbnail:
            e.set_thumbnail(url=thumbnail)
        if image:
            e.set_image(url=image)
        bot_avatar = self.bot.user.display_avatar.url if self.bot.user else None
        if requester and bot_avatar:
            e.set_footer(
                text=f"{self.bot.user.name} • Requested by {requester}",
                icon_url=bot_avatar
            )
        elif bot_avatar:
            e.set_footer(text=self.bot.user.name, icon_url=bot_avatar)
        return e

    def _err(self, description: str) -> discord.Embed:
        return self._embed(description=f"<:cross:1514194117985570888> {description}", colour=COLOUR_ERR)

    def _ok(self, title: str, description: str = None) -> discord.Embed:
        return self._embed(title=f"<:tick:1514194122192191569> {title}", description=description, colour=COLOUR_OK)

    # =========================================================================
    # GENERAL COMMANDS
    # =========================================================================

    @commands.command()
    async def ping(self, ctx: commands.Context):
        """Shows the bot's current latency."""
        latency = round(self.bot.latency * 1000)
        bar = "█" * min(latency // 20, 10) + "░" * (10 - min(latency // 20, 10))
        colour = COLOUR_OK if latency < 100 else (0xFEE75C if latency < 200 else COLOUR_ERR)
        e = self._embed(
            "<:cat:1513885435221508227> Pong!",
            f"**<:right:1513879374741639248> Latency:** `{latency}ms`\n"
            f"**<:right:1513879374741639248> API:** `{round(self.bot.latency * 1000)}ms`\n"
            f"`{bar}`",
            colour=colour,
            requester=ctx.author
        )
        await ctx.send(embed=e)

    @commands.command()
    async def avatar(self, ctx: commands.Context, member: discord.Member = None):
        """Shows a member's avatar."""
        member = member or ctx.author
        e = self._embed(
            f"🖼️ {member.display_name}'s Avatar",
            image=member.display_avatar.url,
            requester=ctx.author
        )
        e.add_field(name="<:right:1513879374741639248> Download", value=f"[PNG]({member.display_avatar.with_format('png').url}) • [WEBP]({member.display_avatar.with_format('webp').url})")
        await ctx.send(embed=e)

    @commands.command()
    async def banner(self, ctx: commands.Context, member: discord.Member = None):
        """Shows a member's profile banner."""
        member = member or ctx.author
        user = await self.bot.fetch_user(member.id)

        if not user.banner:
            return await ctx.send(embed=self._err(f"{member.mention} doesn't have a banner set."))

        e = self._embed(
            f"🎨 {member.display_name}'s Banner",
            image=user.banner.url,
            requester=ctx.author
        )
        await ctx.send(embed=e)

    # =========================================================================
    # FUN / AESTHETIC COMMANDS
    # =========================================================================

    @commands.command()
    async def say(self, ctx: commands.Context, *, message: str):
        """Makes the bot say something (deletes invoking message)."""
        try:
            await ctx.message.delete()
        except discord.Forbidden:
            pass
        await ctx.send(message)

    @commands.command()
    async def embed(self, ctx: commands.Context, colour: str, title: str, *, description: str):
        """Send a custom embed. Usage: !embed #hex "Title" Description"""
        try:
            colour_val = int(colour.strip("#"), 16)
        except ValueError:
            return await ctx.send(embed=self._err("Invalid hex colour. Example: `#ADD8E6`"))
        e = discord.Embed(title=title, description=description, color=colour_val)
        bot_avatar = self.bot.user.display_avatar.url if self.bot.user else None
        if bot_avatar:
            e.set_footer(text=self.bot.user.name, icon_url=bot_avatar)
        await ctx.send(embed=e)

    @commands.command()
    async def roll(self, ctx: commands.Context, dice: str = "1d6"):
        """Roll dice. Usage: !roll 2d6"""
        match = re.fullmatch(r"(\d+)d(\d+)", dice.lower())
        if not match:
            return await ctx.send(embed=self._err("Use format like `2d6` or `1d20`."))
        count, sides = int(match.group(1)), int(match.group(2))
        if count < 1 or count > 25 or sides < 2:
            return await ctx.send(embed=self._err("Dice: 1–25 dice, 2+ sides."))
        rolls  = [random.randint(1, sides) for _ in range(count)]
        total  = sum(rolls)
        detail = " + ".join(f"`{r}`" for r in rolls)
        e = self._embed(
            "🎲 Dice Roll",
            f"**<:right:1513879374741639248> Dice:** `{dice}`\n"
            f"**<:right:1513879374741639248> Rolls:** {detail}\n"
            f"**<:right:1513879374741639248> Total:** **{total}**",
            requester=ctx.author
        )
        await ctx.send(embed=e)

    @commands.command()
    async def coinflip(self, ctx: commands.Context):
        """Flips a coin."""
        result = random.choice(["Heads 🪙", "Tails 🔁"])
        await ctx.send(embed=self._embed(
            "🪙 Coin Flip",
            f"**<:right:1513879374741639248> Result:** {result}",
            requester=ctx.author
        ))

    @commands.command()
    async def choose(self, ctx: commands.Context, *, options: str):
        """Pick one option from a comma-separated list. !choose red, blue, green"""
        choices = [o.strip() for o in options.split(",") if o.strip()]
        if len(choices) < 2:
            return await ctx.send(embed=self._err("Provide at least 2 comma-separated options."))
        picked = random.choice(choices)
        await ctx.send(embed=self._embed(
            "🤔 Decision Made",
            f"**<:right:1513879374741639248> Options:** {', '.join(f'`{c}`' for c in choices)}\n"
            f"**<:right:1513879374741639248> I choose:** **{picked}**",
            requester=ctx.author
        ))

    @commands.command()
    async def poll(self, ctx: commands.Context, *, question: str):
        """Creates a quick yes/no poll."""
        e = self._embed(
            "📊 Poll",
            f"**{question}**\n\n✅ Yes   |   ❌ No",
            requester=ctx.author
        )
        e.set_footer(text=f"Poll by {ctx.author} • {self.bot.user.name}",
                     icon_url=self.bot.user.display_avatar.url if self.bot.user else None)
        msg = await ctx.send(embed=e)
        await msg.add_reaction("✅")
        await msg.add_reaction("❌")

    @commands.command(name="8ball")
    async def eightball(self, ctx: commands.Context, *, question: str):
        """Ask the magic 8ball a question."""
        responses = [
            "It is certain.", "Without a doubt.", "Yes, definitely.",
            "You may rely on it.", "As I see it, yes.", "Most likely.",
            "Outlook good.", "Signs point to yes.",
            "Reply hazy, try again.", "Ask again later.",
            "Better not tell you now.", "Cannot predict now.",
            "Don't count on it.", "My reply is no.",
            "My sources say no.", "Outlook not so good.", "Very doubtful."
        ]
        answer = random.choice(responses)
        positive = any(w in answer.lower() for w in ["yes", "certain", "good", "likely", "definitely"])
        negative = any(w in answer.lower() for w in ["no", "doubtful", "don't", "not"])
        colour = COLOUR_OK if positive else (COLOUR_ERR if negative else 0xFEE75C)

        await ctx.send(embed=self._embed(
            "🎱 Magic 8-Ball",
            f"**<:right:1513879374741639248> Question:** {question}\n"
            f"**<:right:1513879374741639248> Answer:** *{answer}*",
            colour=colour,
            requester=ctx.author
        ))

    @commands.command()
    async def calculate(self, ctx: commands.Context, *, expression: str):
        """Basic calculator. !calculate 2 + 2 * 10"""
        allowed = re.fullmatch(r"[\d\s\+\-\*\/\.\(\)%]+", expression)
        if not allowed:
            return await ctx.send(embed=self._err("Only basic math operators allowed (`+ - * / ( ) %`)."))
        try:
            result = eval(expression, {"__builtins__": {}})  # safe: only digits/ops allowed
            await ctx.send(embed=self._embed(
                "🧮 Calculator",
                f"**<:right:1513879374741639248> Expression:** `{expression}`\n"
                f"**<:right:1513879374741639248> Result:** `{result}`",
                requester=ctx.author
            ))
        except Exception:
            await ctx.send(embed=self._err("Could not evaluate that expression."))

    # =========================================================================
    # EMOJI / MEDIA TOOLS
    # =========================================================================

    @commands.command()
    @commands.has_permissions(manage_emojis_and_stickers=True)
    async def steal(self, ctx: commands.Context, *, name: str = None):
        """Steal a custom emoji from a replied message and add it to the server."""
        if not ctx.message.reference:
            return await ctx.send(embed=self._err("Reply to a message containing a custom emoji."))

        ref = await ctx.channel.fetch_message(ctx.message.reference.message_id)
        match = re.search(r"<(a?):(\w+):(\d+)>", ref.content)
        if not match:
            return await ctx.send(embed=self._err("No custom emoji found in that message."))

        animated   = bool(match.group(1))
        emoji_name = name or match.group(2)
        emoji_id   = match.group(3)
        ext        = "gif" if animated else "png"
        url        = f"https://cdn.discordapp.com/emojis/{emoji_id}.{ext}"

        async with aiohttp.ClientSession() as session:
            async with session.get(url) as resp:
                if resp.status != 200:
                    return await ctx.send(embed=self._err("Failed to download the emoji."))
                image = await resp.read()

        try:
            emoji = await ctx.guild.create_custom_emoji(name=emoji_name, image=image)
        except discord.HTTPException as exc:
            return await ctx.send(embed=self._err(f"Failed to add emoji: {exc}"))

        await ctx.send(embed=self._ok(
            "Emoji Stolen!",
            f"Added {emoji} as `:{emoji.name}:`",
        ))

    @commands.command()
    async def emojiinfo(self, ctx: commands.Context, emoji: discord.Emoji):
        """Shows info about a server emoji."""
        ts = int(emoji.created_at.timestamp())
        e = self._embed(
            "😀 Emoji Info",
            f"**<:right:1513879374741639248> Name:** `:{emoji.name}:`\n"
            f"**<:right:1513879374741639248> ID:** `{emoji.id}`\n"
            f"**<:right:1513879374741639248> Animated:** {'Yes' if emoji.animated else 'No'}\n"
            f"**<:right:1513879374741639248> Created:** <t:{ts}:R>\n"
            f"**<:right:1513879374741639248> URL:** [Click here]({emoji.url})",
            thumbnail=emoji.url,
            requester=ctx.author
        )
        await ctx.send(embed=e)

    # =========================================================================
    # AUTORESPONDERS
    # =========================================================================

    @commands.command()
    @commands.has_permissions(administrator=True)
    async def autoresponder(self, ctx: commands.Context, trigger: str, *, response: str):
        """Add an autoresponder. !autoresponder "hello" Hello there!"""
        data = self._load_json(self.ar_file)
        data.setdefault(str(ctx.guild.id), {})[trigger.lower()] = response
        self._save_json(self.ar_file, data)
        await ctx.send(embed=self._ok(
            "Autoresponder Added",
            f"**<:right:1513879374741639248> Trigger:** `{trigger}`\n"
            f"**<:right:1513879374741639248> Response:** {response}"
        ))

    @commands.command()
    @commands.has_permissions(administrator=True)
    async def removeresponder(self, ctx: commands.Context, *, trigger: str):
        """Remove an autoresponder trigger."""
        data    = self._load_json(self.ar_file)
        guild_id= str(ctx.guild.id)

        if guild_id not in data or trigger.lower() not in data[guild_id]:
            return await ctx.send(embed=self._err(f"No autoresponder found for `{trigger}`."))

        del data[guild_id][trigger.lower()]
        self._save_json(self.ar_file, data)
        await ctx.send(embed=self._ok("Autoresponder Removed", f"Removed trigger: `{trigger}`"))

    @commands.command()
    @commands.has_permissions(administrator=True)
    async def listresponders(self, ctx: commands.Context):
        """List all autoresponders for this server."""
        data      = self._load_json(self.ar_file)
        responders= data.get(str(ctx.guild.id), {})

        if not responders:
            return await ctx.send(embed=self._err("No autoresponders set up yet."))

        lines = [f"`{i+1}.` **{trig}** → {resp}" for i, (trig, resp) in enumerate(responders.items())]
        await ctx.send(embed=self._embed(
            "📋 Autoresponders",
            "\n".join(lines),
            requester=ctx.author
        ))

    # =========================================================================
    # MEDIA-ONLY CHANNELS
    # =========================================================================

    @commands.command()
    @commands.has_permissions(manage_channels=True)
    async def mediaonly(self, ctx: commands.Context, channel: discord.TextChannel):
        """Mark a channel as media-only."""
        data     = self._load_json(self.media_file)
        guild_id = str(ctx.guild.id)
        data.setdefault(guild_id, [])

        if channel.id in data[guild_id]:
            return await ctx.send(embed=self._err(f"{channel.mention} is already media-only."))

        data[guild_id].append(channel.id)
        self._save_json(self.media_file, data)
        await ctx.send(embed=self._ok(
            "Media-Only Enabled",
            f"<:right:1513879374741639248> {channel.mention} is now **media-only**."
        ))

    @commands.command()
    @commands.has_permissions(manage_channels=True)
    async def unmediaonly(self, ctx: commands.Context, channel: discord.TextChannel):
        """Remove media-only restriction from a channel."""
        data     = self._load_json(self.media_file)
        guild_id = str(ctx.guild.id)

        if guild_id not in data or channel.id not in data[guild_id]:
            return await ctx.send(embed=self._err(f"{channel.mention} is not a media-only channel."))

        data[guild_id].remove(channel.id)
        self._save_json(self.media_file, data)
        await ctx.send(embed=self._ok(
            "Media-Only Disabled",
            f"<:right:1513879374741639248> {channel.mention} is no longer media-only."
        ))

    # =========================================================================
    # LISTENERS
    # =========================================================================

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot or not message.guild:
            return

        guild_id = str(message.guild.id)

        # Media-only enforcement
        media_data = self._load_json(self.media_file)
        if (
            guild_id in media_data
            and message.channel.id in media_data[guild_id]
            and not message.attachments
            and not message.embeds
        ):
            try:
                await message.delete()
                await message.channel.send(
                    f"{message.author.mention} Only media is allowed in this channel.",
                    delete_after=5
                )
            except discord.Forbidden:
                pass
            return

        # Autoresponder
        ar_data = self._load_json(self.ar_file)
        if guild_id in ar_data:
            response = ar_data[guild_id].get(message.content.lower())
            if response:
                await message.channel.send(response)


async def setup(bot: commands.Bot):
    await bot.add_cog(General(bot))

import discord
from discord.ext import commands
from discord import app_commands
import time

# ── Constants ──────────────────────────────────────────────────────────────────
BLUE   = 0xFFBFEA
PREFIX = "?"

# ── Custom Emojis ──────────────────────────────────────────────────────────────
LEAF      = "<:leaf:1515660279944319006>"
CLOUD     = "<:cloud:1515660282771542016>"
INFO      = "<:infoicon:1515660285850157137>"
SHIELD    = "<:shield:1515660276270239804>"
WARN      = "<:warnicon:1515660263129350155>"
HOME      = "<:Home:1514196660228718713>"
BOT       = "<:Bot:1514196657644765205>"
COMMUNITY = "<:Communie:1514196655233040455>"
CROSS     = "<:cross:1514194117985570888>"
TICK      = "<:tick:1514194122192191569>"
PYTHON    = "<:Python:1513879400544731236>"


class HelpDropdown(discord.ui.Select):

    def __init__(self, view_id: str):
        options = [
            discord.SelectOption(
                label="Home",
                description="Shouffle Index & Dashboard",
                emoji="<:Home:1514196660228718713>",
                value="0",
            ),
            discord.SelectOption(
                label="General & Utility",
                description="Commands for everyday use.",
                emoji="<:leaf:1515660279944319006>",
                value="1",
            ),
            discord.SelectOption(
                label="Moderation & Automod",
                description="Tools for server management.",
                emoji="<:cloud:1515660282771542016>",
                value="2",
            ),
            discord.SelectOption(
                label="Admin & Security",
                description="Advanced security controls.",
                emoji="<:shield:1515660276270239804>",
                value="3",
            ),
        ]
        super().__init__(
            placeholder="Select a category...",
            min_values=1,
            max_values=1,
            options=options,
            custom_id=f"help_dropdown_{view_id}",
        )

    async def callback(self, interaction: discord.Interaction):
        view: HelpView = self.view
        view.current_page = int(self.values[0])
        await view.update_message(interaction)


class HelpButtons(discord.ui.Button):

    def __init__(self, label: str, style: discord.ButtonStyle, custom_id: str):
        super().__init__(label=label, style=style, custom_id=custom_id)

    async def callback(self, interaction: discord.Interaction):
        view: HelpView = self.view

        if self.custom_id.startswith("prev"):
            view.current_page = (view.current_page - 1) % len(view.embeds)
        elif self.custom_id.startswith("next"):
            view.current_page = (view.current_page + 1) % len(view.embeds)

        await view.update_message(interaction)


class HelpView(discord.ui.View):

    def __init__(self, embeds: list, author: discord.User | discord.Member):
        super().__init__(timeout=180)
        self.embeds = embeds
        self.author = author
        self.current_page = 0
        self.message: discord.Message | None = None

        # Unique ID per view instance so custom_ids never collide
        uid = str(int(time.time() * 1000))[-8:]

        # Plain Unicode arrows — always render correctly as text buttons
        self.add_item(HelpButtons("◀", discord.ButtonStyle.blurple, f"prev_{uid}"))
        self.add_item(HelpButtons("▶", discord.ButtonStyle.blurple, f"next_{uid}"))
        self.add_item(HelpDropdown(uid))

    def _sync_dropdown(self):
        """Mark the currently active page as default in the dropdown."""
        for item in self.children:
            if isinstance(item, discord.ui.Select):
                for option in item.options:
                    option.default = int(option.value) == self.current_page

    async def update_message(self, interaction: discord.Interaction):
        self._sync_dropdown()
        embed = self.embeds[self.current_page]

        try:
            if not interaction.response.is_done():
                await interaction.response.edit_message(embed=embed, view=self)
            else:
                await interaction.edit_original_response(embed=embed, view=self)
        except discord.NotFound:
            pass
        except discord.HTTPException:
            pass

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.author.id:
            await interaction.response.send_message(
                f"{CROSS} This menu belongs to someone else.", ephemeral=True
            )
            return False
        return True

    async def on_timeout(self):
        for item in self.children:
            item.disabled = True
        if self.message is not None:
            try:
                await self.message.edit(view=self)
            except (discord.NotFound, discord.HTTPException):
                pass


class Help(commands.Cog):

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    def create_help_embeds(self) -> list[discord.Embed]:
        avatar_url = self.bot.user.display_avatar.url

        # ── Page 1 · Home ─────────────────────────────────────────────────────
        embed1 = discord.Embed(
            title=f"{BOT}  Welcome to Shouffle",
            description=(
                f"{INFO}  Use the dropdown or arrows below to browse all command modules.\n"
                f"Select a category to get started."
            ),
            color=BLUE,
        )
        embed1.add_field(
            name=f"{HOME}  Navigation",
            value=(
                f"{HOME}  **Page 1** — Home\n"
                f"{LEAF}  **Page 2** — General & Utility\n"
                f"{CLOUD}  **Page 3** — Moderation & Automod\n"
                f"{SHIELD}  **Page 4** — Admin & Security"
            ),
            inline=False,
        )
        embed1.add_field(
            name=f"{INFO}  Bot Info",
            value=(
                f"Prefix: **{PREFIX}**\n"
                f"{PYTHON}  Library: **discord.py 2.x**\n"
                f"{COMMUNITY}  [Join Shouffle](https://discord.gg/nrUJrhxeg8)"
            ),
            inline=False,
        )

        # ── Page 2 · General & Utility ────────────────────────────────────────
        embed2 = discord.Embed(
            title=f"{LEAF}  General & Utility",
            description=f"{INFO}  Everyday commands available to all members.",
            color=BLUE,
        )
        embed2.add_field(
            name=f"{BOT}  Information",
            value="ping, uptime, botinfo, serverinfo, roleinfo, membercount, inviteinfo, emojiinfo",
            inline=False,
        )
        embed2.add_field(
            name=f"{LEAF}  User & Profile",
            value="avatar, banner, afk, afkremove",
            inline=False,
        )
        embed2.add_field(
            name=f"{COMMUNITY}  Fun & Misc",
            value="say, embed, roll, coinflip, choose, poll, 8ball, calculate, snipe, steal",
            inline=False,
        )
        embed2.add_field(
            name=f"{LEAF}  Sticky & Auto-Responders",
            value="stick, stickremove, autoresponder, removeresponder, listresponders",
            inline=False,
        )
        embed2.add_field(
            name=f"{COMMUNITY}  Giveaways",
            value="gcreate, gend, greroll",
            inline=False,
        )

        # ── Page 3 · Moderation & Automod ─────────────────────────────────────
        embed3 = discord.Embed(
            title=f"{CLOUD}  Moderation & Automod",
            description=f"{INFO}  Tools for staff members to maintain server order.",
            color=BLUE,
        )
        embed3.add_field(
            name=f"{WARN}  Member Actions",
            value="mute, unmute, kick, softban, ban, unban",
            inline=False,
        )
        embed3.add_field(
            name=f"{SHIELD}  Warnings",
            value="warn, clearwarns",
            inline=False,
        )
        embed3.add_field(
            name=f"{CLOUD}  Channel & Role Management",
            value="purge, mediaonly, unmediaonly, roleadd, roleremove, say",
            inline=False,
        )
        embed3.add_field(
            name=f"{CLOUD}  Voice",
            value="deafen, undeafen, vcban",
            inline=False,
        )

        # ── Page 4 · Admin & Security ──────────────────────────────────────────
        embed4 = discord.Embed(
            title=f"{SHIELD}  Admin & Security",
            description=f"{INFO}  High-level configurations restricted to administrators.",
            color=BLUE,
        )
        embed4.add_field(
            name=f"{HOME}  Welcome System",
            value="welcomesetup, welcomechannel, welcometest, welcomeconfig",
            inline=False,
        )
        embed4.add_field(
            name=f"{COMMUNITY}  Ticket System",
            value="ticketsetup, ticketconfig",
            inline=False,
        )
        embed4.add_field(
            name=f"{SHIELD}  Server Settings",
            value="autorole, botlogs enable, botlogs disable",
            inline=False,
        )

        # ── Shared footer & thumbnail ──────────────────────────────────────────
        embeds = [embed1, embed2, embed3, embed4]

        for index, embed in enumerate(embeds):
            embed.set_thumbnail(url=avatar_url)
            embed.set_author(name=self.bot.user.name, icon_url=avatar_url)
            embed.set_footer(
                text=f"Page {index + 1}/{len(embeds)} • Developed by yuvrzz",
                icon_url="https://i.ibb.co/fVc25WLZ/487-4871694-p-python-logo-hd-png-download-removebg-preview.png",
            )

        return embeds

    # ── Prefix command: ?help ──────────────────────────────────────────────────
    @commands.command(name="help")
    async def help_prefix(self, ctx: commands.Context):
        try:
            embeds = self.create_help_embeds()
        except Exception as e:
            await ctx.send(f"{CROSS} Failed to build help menu: {e}")
            return

        view = HelpView(embeds, ctx.author)
        view.message = await ctx.send(embed=embeds[0], view=view)

    # ── Slash command: /help ───────────────────────────────────────────────────
    @app_commands.command(name="help", description="View all available commands")
    async def help_slash(self, interaction: discord.Interaction):
        try:
            embeds = self.create_help_embeds()
        except Exception as e:
            await interaction.response.send_message(
                f"{CROSS} Failed to build help menu: {e}", ephemeral=True
            )
            return

        view = HelpView(embeds, interaction.user)
        await interaction.response.send_message(embed=embeds[0], view=view)
        view.message = await interaction.original_response()


async def setup(bot: commands.Bot):
    await bot.add_cog(Help(bot))
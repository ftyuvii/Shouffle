import discord
from discord.ext import commands
from discord import app_commands
import time

RED = 0xADD8E6
PREFIX = "?"


class HelpDropdown(discord.ui.Select):

    def __init__(self, view_id: str):
        options = [
            discord.SelectOption(
                label="Home Index",
                description="Shouffle Index & Dashboard",
                emoji="<:python:1513795344800940084>",
                value="0",
            ),
            discord.SelectOption(
                label="General & Utility",
                description="Commands for everyday use.",
                emoji="🔧",
                value="1",
            ),
            discord.SelectOption(
                label="Moderation & Automod",
                description="Tools for Server Management.",
                emoji="🛡️",
                value="2",
            ),
            discord.SelectOption(
                label="Admins & Security",
                description="Advanced security controls.",
                emoji="🔐",
                value="3",
            ),
        ]
        # Unique custom_id per view instance — prevents conflicts across users
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
                # Interaction already responded (e.g. slow click) — use followup edit
                await interaction.edit_original_response(embed=embed, view=self)
        except discord.NotFound:
            # Interaction token expired (>3s or unknown interaction) — silently ignore
            pass
        except discord.HTTPException:
            pass

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.author.id:
            await interaction.response.send_message(
                "❌ You cannot control this menu.", ephemeral=True
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

        embed1 = discord.Embed(
            title="<:python:1513795344800940084> Start with Shouffle",
            description=(
                "Welcome to **Shouffle** ✈️\n"
                "<:right:1513795469371900135> Use the navigation panel below to browse modules."
            ),
            color=RED,
        )
        embed1.add_field(
            name="<:right:1513879374741639248> Navigation Guide",
            value=(
                "▫️ **Page 1:** Home Index\n"
                "▫️ **Page 2:** General & Utility\n"
                "▫️ **Page 3:** Moderation & Automod\n"
                "▫️ **Page 4:** Admin & Security"
            ),
            inline=False,
        )
        embed1.add_field(
            name="",
            value=(
                f"<:Dot:1514580222673027232> Prefix: `{PREFIX}`\n"
                f"<:Info:1514580225558577245> Library: `discord.py 2.x`\n"
                f"<:Home:1514196660228718713> [Shouffle Home](https://discord.gg/nrUJrhxeg8)"
            ),
            inline=False,
        )

        embed2 = discord.Embed(
            title="🔧 General & Utility Commands",
            description="Everyday basic commands available for all members.",
            color=RED,
        )
        embed2.add_field(
            name="Available Commands",
            value=(
                "`help` `ping` `avatar` `banner` `userinfo` `serverinfo`\n"
                "`autoresponder` `removeresponder` `userinfo` `listresponders`\n"
                "`coinflip` `emojiinfo` `8ball`"
            ),
            inline=False,
        )

        embed3 = discord.Embed(
            title="🛡️ Moderation & Automod Panel",
            description="Tools for staff members to maintain server decorum.",
            color=RED,
        )
        embed3.add_field(
            name="Available Commands",
            value=(
                "`mute` `unmute` `kick` `softban` `ban` `unban`\n"
                "`warn` `uwarn` `clearwarns` `purge`\n"
                "`mediaonly` `unmediaonly` `roleadd` `roleremove`\n"
                "`deafen` `undeafen` `vcban` `say`"
            ),
            inline=False,
        )

        embed4 = discord.Embed(
            title="🔐 Admin & Securities Panel",
            description="High-tier restrictions and system security configurations.",
            color=RED,
        )
        embed4.add_field(
            name="Setup & Core Settings",
            value=(
                "`welcomesetup` `welcomechannel` `testwelcome`\n"
                "`welcomeconfig` `roleall` *(more coming soon)*"
            ),
            inline=False,
        )

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
            await ctx.send(f"❌ Failed to build help menu: `{e}`")
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
                f"❌ Failed to build help menu: `{e}`", ephemeral=True
            )
            return

        view = HelpView(embeds, interaction.user)
        await interaction.response.send_message(embed=embeds[0], view=view)
        view.message = await interaction.original_response()


async def setup(bot: commands.Bot):
    await bot.add_cog(Help(bot))

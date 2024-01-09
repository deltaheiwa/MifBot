"""
The main file of the bot. Launches the bot and sets up the environment.

Requirements:
- TOKEN environment variable must be set in .env file
- Check the requirements.txt file for the list of required packages
- You need to have a MySQL server running on your machine. Credentials are stored in .env file

Other requirements can be found in other .py files

? TODO: Maybe move the bot to it's own file? As well as the commands in here
"""

import calendar
import os
from typing import Union
import time
import random
import asyncio
from datetime import datetime as dt, timedelta
import logging
import langcodes
import nest_asyncio
import psutil
import discord
from discord.ext import commands
from discord import app_commands
from dotenv import load_dotenv
from bot_util import exceptions
from bot_util.converters import MembersOrRoles
from bot_util.functions.bot import determine_prefix
from bot_util.functions.config import init_bot
from bot_util.functions.discord import channel_perms_change
from bot_util.functions.universal import chance, pretty_date
import bot_util.bot_config as b_cfg
from bot_util.bot_config import IS_DEV_BUILD
from bot_util.misc import AsyncTranslator, BotStringsReader, WebSocketClient, Logger
from telegram_helper.main import MifTelegramReporter
from db_data.database_main import PrefixDatabase
from db_data import psql_main
# from vg_ext.database.connector import PUDBConnector

toc = time.perf_counter()

initial_extensions = []

for filename in os.listdir("./cogs"):
    if filename.endswith(".py"):
        initial_extensions.append("cogs." + filename[:-3])

logger = Logger(__name__, logging.DEBUG, b_cfg.LogFiles.main_log)

nest_asyncio.apply()
activity = discord.Game("with Dan")
intents = discord.Intents.default()
intents.members = True
intents.dm_reactions = True
intents.message_content = True


class Mif(commands.Bot):
    telegram_bot: MifTelegramReporter

    def __init__(self, *args, **kwargs):
        super().__init__(
            command_prefix=determine_prefix,
            activity=activity,
            intents=intents,
            case_insensitive=True,
            strip_after_prefix=True,
            status=discord.Status.idle,
        )
        self.remove_command("help")
        self.interaction_server_overload = {}
        self.telegram_bot: MifTelegramReporter
        self.process = psutil.Process(os.getpid())
        self.ws_client = WebSocketClient()

    async def setup_hook(self):
        for extension in initial_extensions:
            await self.load_extension(extension)
        asyncio.create_task(init_bot(self))

    async def on_ready(self):
        logger.info("We have logged in as %s", bot.user.name)
        logger.info("I'm in %s guilds!", len(bot.guilds))
        tic = time.perf_counter()
        logger.info(f"Bot loaded in {tic - toc:0.4f} seconds")
        await self.wait_until_ready()
        logger.info("Connecting to the databases")

        psql_main.PostgresConnector.connect_to_dev_db() if IS_DEV_BUILD else psql_main.PostgresConnector.connect_to_prod_db()
        psql_main.DatabaseFunctions.create_tables()
        # PUDBConnector.engine_creation()
        logger.info("Bot is ready")
        await self.change_presence(
            status=discord.Status.online, activity=discord.Game(name="with Dan")
        )

    async def stop(self):
        await self.telegram_bot.close() if self.telegram_bot is not None else logger.warning(
            "No telegram bot instance detected"
        )
        await self.close()

    async def on_command_error(self, ctx: commands.Context, error: Exception) -> None:
        if hasattr(ctx.command, "on_error"):
            return
        cog = ctx.cog
        if cog:
            if cog._get_overridden_method(cog.cog_command_error) is not None:
                return
        ignored = commands.CommandNotFound
        if isinstance(error, ignored):
            return
        logger.error(error, exc_info=(type(error), error, error.__traceback__))
        if isinstance(error, commands.MemberNotFound):
            embed = discord.Embed(
                title="Error",
                description="Couldn't find such user on discord",
                color=b_cfg.CustomColors.red,
            )
            await ctx.reply(embed=embed)
            return
        if isinstance(error, commands.MissingPermissions):
            embed_missing_perms = discord.Embed(
                title="Missing Permissions",
                description=error,
                color=b_cfg.CustomColors.dark_red,
            )
            await ctx.reply(embed=embed_missing_perms)
            return
        if isinstance(error, commands.CommandOnCooldown):
            now = dt.utcnow()
            retry_after = timedelta(seconds=error.retry_after)
            retry_time = now + retry_after
            embed = discord.Embed(
                title="Slow down",
                description="You can retry **{error}**.".format(
                    error=f"<t:{int(calendar.timegm(retry_time.timetuple()))}:R>"
                ),
                color=discord.Color.red(),
            )
            await ctx.reply(embed=embed, delete_after=error.retry_after)
            return

        if isinstance(error, exceptions.NotAuthorizedError):
            embed = discord.Embed(
                title="Error", description=error, color=b_cfg.CustomColors.red
            )
            await ctx.reply(embed=embed, ephemeral=True)
            return

        if isinstance(error, exceptions.BattleMissingArgumentsError):
            embed = discord.Embed(
                title="No active characters",
                description="You haven't selected any characters.",
                color=discord.Color.red(),
            )
            await ctx.reply(embed=embed)
            return
        await self.telegram_bot.send_automatic_exception(error, ctx=ctx)

        if isinstance(error, commands.CommandError):
            return await super().on_command_error(ctx, error)

    @staticmethod
    async def on_guild_join(guild: discord.Guild):
        await PrefixDatabase.new_prefix(guild_id=guild.id, prefix=".")

    @staticmethod
    async def on_guild_remove(guild: discord.Guild):
        await PrefixDatabase.remove_prefix(guild_id=guild.id)


bot = Mif()

load_dotenv("creds/.env")
token = os.getenv("TOKEN" if IS_DEV_BUILD else "TOKEN_MIF")


@bot.event
async def on_message(message: discord.Message):
    await bot.process_commands(message)
    if (
        message.author != bot.user
        and message.content in ["...", "..", "...."]
        and message.guild
    ):
        if chance(10.0):
            if message.guild.id in bot.interaction_server_overload and (
                dt.now() - bot.interaction_server_overload[message.guild.id]
            ) < timedelta(days=1, hours=12):
                return
            bot.interaction_server_overload.pop(message.guild.id, None)
            query_info = {"times_called": 1, "amount": 0}
            fill = 0
            people = []
            channel_history = message.channel.history(limit=25)
            async for msg in channel_history:
                if msg.author.id == bot.user.id:
                    fill += 0.5
                    continue
                if msg.content in ["...", "..", "...."]:
                    people.append(
                        msg.author.id
                    ) if msg.author.id not in people else None
                    query_info["times_called"] += 1 if fill > 0 else 0
                fill = 0
            query_info["amount"] += len(people)
            if query_info["times_called"] > 3:
                bot.interaction_server_overload[message.guild.id] = dt.now()
            message_to_send = BotStringsReader(
                bot, "triggering", message.author
            ).return_string(query_info)
            await message.channel.send(embed=message_to_send) if isinstance(
                message_to_send, discord.Embed
            ) else await message.channel.send(message_to_send)


@bot.hybrid_command(
    name="change-prefix",
    description="Changes the prefix of the bot",
    aliases=["prefix"],
    with_app_command=True,
)
@commands.has_guild_permissions(manage_guild=True)
@commands.guild_only()
async def change_prefix(ctx: commands.Context, prefix):
    await ctx.defer(ephemeral=True)
    async_trans = AsyncTranslator(
        language_code=psql_main.DatabaseFunctions.get_lang_code(ctx.author.id)
    )
    async with async_trans as lang:
        lang.install()
        _ = lang.gettext
        if (
            ctx.message.author.guild_permissions.administrator
            or ctx.message.author.guild_permissions.manage_guild
        ):
            if ctx.guild is not None:
                await PrefixDatabase.new_prefix(ctx.guild.id, prefix)

            embed = discord.Embed(
                title="",
                description=_("Server prefix changed to: {prefix}").format(
                    prefix=prefix
                ),
                color=discord.Color.from_rgb(0, 255, 255),
            )
            await ctx.send(embed=embed)
            psql_main.DatabaseFunctions.add_to_command_stat(ctx.author.id)
        else:
            embed = discord.Embed(
                title=_("Error, user missing permissions"),
                description=_(
                    ":x: Only `Administrator` or user with `Manage Server` permissions can change the prefix"
                ),
                color=discord.Color.red(),
            )
            await ctx.reply(embed=embed)


class UserInfoButtonsView(discord.ui.View):
    message: discord.Message

    def __init__(self, ui_embed, user, gettext_lang, *, timeout=180):
        super().__init__(timeout=timeout)
        self.message: discord.Message
        self.user_info_embed = ui_embed
        self.user = user
        self._ = gettext_lang

    @discord.ui.button(label="Avatar", style=discord.ButtonStyle.blurple)
    async def avatar_button(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        if button.label == "Avatar":
            embed = discord.Embed(
                title=self._("User's avatar"),
                description=f"{self.user}",
                color=self.user.color,
            )
            embed.set_image(url=self.user.display_avatar.url)
            button.label = "User Info"
            await interaction.response.edit_message(embed=embed, view=self)
        elif button.label == "User Info":
            button.label = "Avatar"
            await interaction.response.edit_message(
                embed=self.user_info_embed, view=self
            )

    async def on_timeout(self) -> None:
        for item in self.children:
            item.disabled = True
        await self.message.edit(view=self)


@bot.hybrid_command(
    name="user-info",
    with_app_command=True,
    description="Shows basic data about specified user. Works for avatar as well",
)
async def user_info(
    ctx: commands.Context, user: Union[discord.Member, discord.User, None] = None
) -> None:
    async_trans = AsyncTranslator(
        language_code=psql_main.DatabaseFunctions.get_lang_code(ctx.author.id)
    )
    async with async_trans as lang:
        lang.install()
        _ = lang.gettext
        if user is None:
            user = ctx.message.author
        embed = discord.Embed(
            title=_("Info about user"),
            description=_("Here is the info I retrieved about {user}").format(
                user=user
            ),
            color=user.color,
        )

        embed.set_thumbnail(url=user.display_avatar.url)
        embed.add_field(name=_("Username"), value=user.name, inline=True)
        embed.add_field(name=_("Nickname"), value=user.display_name, inline=True)
        embed.add_field(name="ID", value=user.id, inline=True)
        embed.add_field(
            name=_("Status"),
            value=user.status
            if isinstance(user, discord.Member)
            else _("*Couldn't retrieve status*"),
            inline=True,
        )
        embed.add_field(
            name=_("Top role"),
            value=user.top_role.name
            if isinstance(user, discord.Member)
            else _("*Couldn't retrieve highest role*"),
            inline=True,
        )
        embed.add_field(
            name=b_cfg.CustomEmojis.empty, value=b_cfg.CustomEmojis.empty, inline=False
        )
        embed.add_field(
            name=_("Created"), value=pretty_date(user.created_at), inline=False
        )
        embed.add_field(
            name=_("Joined"),
            value=pretty_date(user.joined_at)
            if isinstance(user, discord.Member)
            else _("*Is not in the server*"),
            inline=False,
        )
        view = UserInfoButtonsView(ui_embed=embed, user=user, gettext_lang=_)
        view.message = await ctx.send(embed=embed, view=view)
        psql_main.DatabaseFunctions.add_to_command_stat(ctx.message.author.id)


class PreferencesModal(discord.ui.Modal):
    def __init__(self, user_id: int, preferences, func, view):
        super().__init__(title="Preferences", timeout=300.0)
        self.user_id = user_id
        self.preferences = preferences
        self.func = func
        self.view = view

    custom_prefix = discord.ui.TextInput(
        label="Custom prefix",
        placeholder="Type your custom prefix here (leave empty if default)",
        min_length=0,
        max_length=5,
        required=False,
    )

    async def on_submit(self, interaction: discord.Interaction):
        self.preferences["prefix"] = (
            self.custom_prefix.value if self.custom_prefix.value != "" else None
        )
        psql_main.DatabaseFunctions.store_custom_prefix(
            self.user_id, self.preferences["prefix"]
        )
        await PrefixDatabase.new_prefix(self.user_id, self.preferences["prefix"])
        async with AsyncTranslator(
            language_code=psql_main.DatabaseFunctions.get_lang_code(self.user_id)
        ) as lang:
            lang.install()
            _ = lang.gettext
            embed = self.func(self.preferences, _)
            await interaction.response.edit_message(view=self.view, embed=embed)


class PreferencesView(discord.ui.View):
    message: discord.Message

    def __init__(self, preferences, user_id, func, *, timeout: float | None = 300):
        super().__init__(timeout=timeout)
        self.message: discord.Message
        self.preferences = preferences
        self.user_id = user_id
        self.func = func
        self.modal: PreferencesModal

    @discord.ui.button(label="Change preferences", style=discord.ButtonStyle.blurple)
    async def change_preferences_button(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        self.modal = PreferencesModal(self.user_id, self.preferences, self.func, self)
        await interaction.response.send_modal(self.modal)

    @discord.ui.select(
        placeholder="Select language",
        min_values=1,
        max_values=1,
        options=[
            discord.SelectOption(
                label="English", description="English", emoji="🇬🇧", value="en"
            ),
            discord.SelectOption(
                label="Ukrainian", description="Українська", emoji="🇺🇦", value="uk"
            ),
        ],
    )
    async def language(
        self, interaction: discord.Interaction, select: discord.ui.Select
    ):
        language = select.values[0]
        self.preferences["language"] = language
        psql_main.DatabaseFunctions.store_lang_code(self.user_id, language)

        async with AsyncTranslator(language_code=language) as lang:
            lang.install()
            _ = lang.gettext
            embed = self.func(self.preferences, _)
            await interaction.response.edit_message(embed=embed, view=self)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id == self.user_id:
            return True

        await interaction.response.send_message(
            "You can't change someone's else settings", ephemeral=True
        )
        return False

    async def on_timeout(self):
        await self.message.edit(view=None)


@bot.hybrid_command(
    aliases=["settings"],
    name="preferences",
    description="Shows your preferences",
    with_app_command=True,
)
async def preferences(ctx: commands.Context):
    user = ctx.author

    async_trans = AsyncTranslator(
        language_code=psql_main.DatabaseFunctions.get_lang_code(ctx.author.id)
    )
    async with async_trans as lang:
        lang.install()
        _ = lang.gettext

        if psql_main.DatabaseFunctions.check_if_member_exists(user.id):
            preferences_stored = psql_main.DatabaseFunctions.get_user_preferences(
                user.id
            )

            def build_embed(preferences, _):
                embed = discord.Embed(
                    title=_("Preferences"),
                    description=_("{}' preferences").format(user.name),
                    color=b_cfg.CustomColors.cyan,
                )
                embed.add_field(
                    name=_("Custom prefix"),
                    value=f"**{preferences['prefix']}**"
                    if preferences["prefix"] is not None
                    else _(
                        "*There is no custom prefix set. The default is either `.` or server-specific.*"
                    ),
                    inline=False,
                )
                lang_text = (
                    langcodes.Language.make(language=preferences["language"])
                    .display_name(preferences["language"])
                    .capitalize()
                )
                embed.add_field(
                    name=_("Language"),
                    value=f"{b_cfg.language_emojis[preferences['language']]} **{lang_text}**",
                    inline=False,
                )
                return embed

            view = PreferencesView(preferences_stored, user.id, build_embed)
            view.message = await ctx.send(
                embed=build_embed(preferences_stored, _), view=view
            )
            psql_main.DatabaseFunctions.add_to_command_stat(user.id)
        else:
            await ctx.defer(ephemeral=True)
            error_embed = discord.Embed(
                title="Error",
                description="You are not registered on this bot. Use `/register` command to register.",
                color=b_cfg.CustomColors.red,
            )
            await ctx.send(embed=error_embed, ephemeral=True)


@bot.hybrid_command(name="ping", description="Shows bot's ping", with_app_command=True)
async def ping(ctx: commands.Context):
    async_trans = AsyncTranslator(
        language_code=psql_main.DatabaseFunctions.get_lang_code(ctx.author.id)
    )
    async with async_trans as lang:
        lang.install()
        _ = lang.gettext
        logger.info(f"My ping is {round(bot.latency * 1000)} ms")
        await ctx.reply(_("Pong {}ms").format(round(bot.latency * 1000)))


@bot.command()
async def nsfw(ctx: commands.Context):
    user = ctx.message.author
    async_trans = AsyncTranslator(
        language_code=psql_main.DatabaseFunctions.get_lang_code(ctx.author.id)
    )
    async with async_trans as lang:
        lang.install()
        _ = lang.gettext
        if isinstance(user, discord.User):
            return await ctx.reply(_("You are in my DMS. I can't call you!"))
        voice_state = user.voice
        guild = ctx.guild

        def play_song(voice_channel_to_play_on: discord.VoiceProtocol):
            songs = []
            for song in os.listdir("./vcPlay"):
                songs.append(song)
            song_n = random.randint(1, 100)
            if song_n > (len(songs) - 1):
                song_n = 0
            main_dir = os.path.dirname(__file__)
            song_dir = "vcPlay/" + f"{songs[song_n]}"
            abs_file_path = os.path.join(main_dir, song_dir)
            voice_channel_to_play_on.play(discord.FFmpegPCMAudio(f"{abs_file_path}"))
            members = channel.members
            member_ids = []
            for person in members:
                member_ids.append(person.id)
            psql_main.DatabaseFunctions.add_rickroll_stats(user.id, member_ids)
            psql_main.DatabaseFunctions.add_to_command_stat(user.id)

        if voice_state is None:
            # Exiting if the user is not in a voice channel
            return await ctx.send(
                _("Join a voice chat and I will stream for you, senpaii-")
            )
        voice_clients = guild.voice_client
        channel = voice_state.channel
        if channel is not None and voice_clients is None:
            await channel.connect()
            voice_channel = discord.utils.get(bot.voice_clients, guild=guild)
            if voice_channel is None:
                embed = discord.Embed(
                    title=_("Ugh, where are you?"),
                    description=_(
                        "I couldn't detect a voice channel to connect. Meow."
                    ),
                    color=b_cfg.CustomColors.red,
                )
                await ctx.send(embed=embed)
                logger.error("VoiceProtocol not detected in %", guild)
                return
            play_song(voice_channel)
            while voice_channel.is_playing():
                await asyncio.sleep(1)
            await voice_channel.disconnect()
        elif channel is not None and voice_clients is not None:
            await ctx.send(_("Redirecting..."), delete_after=10.0)
            await voice_clients.disconnect(force=True)
            await channel.connect()
            voice_channel = discord.utils.get(bot.voice_clients, guild=guild)
            play_song(voice_channel)
            while voice_channel.is_playing():
                await asyncio.sleep(1)
            await voice_channel.disconnect()


@bot.hybrid_command(
    name="channel-access",
    with_app_command=True,
    description="Changes channel permissions for specified user",
    aliases=["channelAccess", "ch-access"],
)
@commands.has_guild_permissions(manage_permissions=True)
@app_commands.choices(
    add_remove=[
        app_commands.Choice(name="Add", value="add"),
        app_commands.Choice(name="Remove", value="remove"),
        app_commands.Choice(name="Default", value="default"),
    ]
)
@commands.guild_only()
async def channel_access(
    ctx: commands.Context, add_remove, channel: discord.TextChannel, *, members: str
):
    await ctx.defer(ephemeral=True)
    perms_change = {"add": True, "remove": False, "default": None}
    members = members.split(" ")

    async_trans = AsyncTranslator(
        language_code=psql_main.DatabaseFunctions.get_lang_code(ctx.author.id)
    )
    async with async_trans as lang:
        lang.install()
        _ = lang.gettext

        if add_remove.lower() not in perms_change:
            await ctx.send(
                _("Please specify if you want to add/remove or set default permissions")
            )
            return

        if len(members) < 1:
            await ctx.send(_("User not specified"))
            return

        processed_members = []
        for member in members:
            try:
                member_dc = await MembersOrRoles().convert(ctx, member)
                processed_members.append(member_dc[0])
            except commands.RoleNotFound:
                member_dc = discord.utils.find(
                    lambda m: m.name.lower().startswith(member), ctx.guild.members
                )
                if member_dc is None:
                    await ctx.send(_("User or role {} not found").format(member))
                else:
                    processed_members.append(member_dc)

        if not processed_members:
            return

        if not isinstance(channel, discord.TextChannel):
            embed_err = discord.Embed(
                title=_("Channel error"),
                description=_(
                    "Channel is unidentified, or channel type is not supported"
                ),
                color=b_cfg.CustomColors.red,
            )
            await ctx.reply(embed=embed_err)
            return

        try:
            mentions = []
            for member in processed_members:
                if isinstance(member, str):
                    continue
                await channel_perms_change(
                    member, channel, perms_change[add_remove.lower()]
                )
                mentions.append(member.mention)
            await ctx.reply(_("Updated permissions for {}").format(" ".join(mentions)))
            if psql_main.DatabaseFunctions.check_if_member_is_logged(ctx.author.id):
                psql_main.DatabaseFunctions.add_to_command_stat(ctx.author.id)
        except discord.Forbidden:
            embed_err = discord.Embed(
                title=_("Access error"),
                description=_("I have no access to {}").format(channel.name),
                color=b_cfg.CustomColors.red,
            )
            await ctx.reply(embed=embed_err)


@bot.command(aliases=["patch", "patchNotes"])
async def patch_notes(ctx: commands.Context):
    async_trans = AsyncTranslator(
        language_code=psql_main.DatabaseFunctions.get_lang_code(ctx.author.id)
    )
    async with async_trans as lang:
        lang.install()

        _ = lang.gettext
        embed = discord.Embed(
            title=_("Patch notes"),
            description=_("for **{}**").format(b_cfg.version),
            color=b_cfg.CustomColors.cyan,
        )
    embed.add_field(
        name="New!",
        value="""** · Lichess flairs:** Added display for lichess' new flairs.
    ** · Random chess opening:** Use `.random-opening` to get a random opening if you lack inspiration.
        """,
        inline=False,
    )
    embed.add_field(
        name="Changes",
        value="""** · Slash-commands support:** Added missing wov-player and wov-clan slash commands.
    ** · Wov-player:** Added explanations on how the graph works. Also made the cache more efficient to store and retrieve.
    ** · Database API update:** Migrated to another database engine, which also reduced the number of transactions per command.
        """,
        inline=False,
    )
    embed.add_field(
        name="Fixes",
        value="""** · Many minor fixes:** With database migration, I've encountered a lot of bugs. Took a while to get them fixed
        ** · Blackjack:** Rewrote the game from scratch, to make it more bug-free.
        ** · Wov-player:** Username conflict safety mechanism. It will now throw a message where you can choose the username you searched for, if it found similar usernames (finding two similar usernames used to crash the command instead).
        ** · lichess-player:** Fixed flag display.
        """,
    )
    await ctx.send(embed=embed)
    psql_main.DatabaseFunctions.add_to_command_stat(ctx.author.id)


class HelpSelect(discord.ui.Select):
    def __init__(self, options, embeds: dict, gettext_lang):
        self._ = gettext_lang
        super().__init__(
            options=options,
            placeholder=self._("Select a section..."),
            min_values=1,
            max_values=1,
        )
        self.embed_infos = embeds
        self.embeds = {}

    async def callback(self, interaction: discord.Interaction):
        if self.values[0] not in self.embeds:
            self.embeds[self.values[0]] = discord.Embed(
                title=self.values[0], description="", color=b_cfg.CustomColors.cyan
            )
            for command in self.embed_infos[self.values[0]]:
                self.embeds[self.values[0]].add_field(
                    name=command,
                    value=self.embed_infos[self.values[0]][command],
                    inline=False,
                )
            self.embeds[self.values[0]].set_footer(
                text=self._("version {}").format(b_cfg.version)
            )

        await interaction.response.edit_message(embed=self.embeds[self.values[0]])


class HelpView(discord.ui.View):
    message: discord.Message

    def __init__(
        self, embeds: dict, options, gettext_lang, *, timeout=3600
    ):  # timeout = 1 hour
        self.message: discord.Message
        super().__init__(timeout=timeout)
        self.add_item(
            HelpSelect(options=options, embeds=embeds, gettext_lang=gettext_lang)
        )

    async def on_timeout(self) -> None:
        for item in self.children:
            item.disabled = True  # type: ignore
        await self.message.edit(view=self)


@bot.hybrid_command(
    name="help",
    aliases=["h"],
    description="Check what commands are available",
    with_app_command=True,
)
async def help(ctx):
    async_trans = AsyncTranslator(
        language_code=psql_main.DatabaseFunctions.get_lang_code(ctx.author.id)
    )
    async with async_trans as lang:
        lang.install()
        _ = lang.gettext
        help_dict = {
            _("Administrative commands"): {
                "change-prefix": _(
                    "Changes server-specific prefix to a desirable one. You would need at least 'Manage server' permission to change it. \nExample: `.change-prefix -`"
                ),
                "channel-access": _(
                    "Add/remove or set default access to the channel for specified users. You would need at least 'Manage permissions' permission to use it. Supports string searching.\nExample: `.channel-access Add #my-channel someonecute/@someonecute`"
                ),
            },
            _("Informative commands"): {
                "userinfo": _(
                    "Retrieves info about mentioned user (If user is not specified, then about you). Button can be used to toggle between 'User info' and 'Avatar'. \nExample: `.user-info @someonecute`"
                ),
                "ping": _(
                    "Pongs you back. Meow.\nYou may want to test if the bot is alive with it."
                ),
                "patchnotes": _("Check out what's changed with the latest update!"),
                "botstats": _(
                    "Shows statistics on bot usage (wins/losses, amount of commands used, etc). Requires an account. \nAliases: bstats"
                ),
            },
            _("Fun and games"): {
                "nsfw": _(
                    "You have to be 18+ to use this command. Will stream a random 18+ video for you from ||`xvideos`||"
                ),
                "numberguessing": _(
                    "(Maybe) fun number guessing game. It has three difficulties: easy, medium, hard. Hard mode changes number every 20 guesses. \nAliases: ng, ngstart"
                ),
                "hangman": _(
                    "Word guessing game. You have 6 tries until you hang a man. Over than 1500 words stored. Contact `{}` if you want to suggest new words. Has two modes - `short words` and `long words`. For example `.hangman short`. If you want it to be fully random, simply don't specify the length of the word.\nAliases: hgm, hangm"
                ).format(bot.get_user(b_cfg.admin_account_ids[0])),
                "blackjack": _(
                    "A classic blackjack game. Requires an account, as you can bet on bot's currency. \nExample: `.blackjack 100` \nAliases: bj"
                ),
                "bullsandcows": _(
                    "Both single-player and multiplayer games, 'bagels' and 'classic'. 'Bagels' has four types of difficulty - classic, fast, hard, and long. You can find more information by starting the game itself. All of the won, lost, and abandoned games are counted toward your stats if you have an account. \nExample: `.bulls bagels classic` \nAliases: [`bulls`] [`pfb`->bagels] [`blitz`->fast | `nerd`->long]\n\nYou can also check your records of the games you played with `.bulls records` command. Or a detailed information and replay of a certain game with `.bulls replay {game id}` command."
                ),
            },
            _("Chess commands"): {
                "lichess-top10": _(
                    "Shows a list of top 10 players in every variant of chess. Use select menu to switch between variants. \nAliases: li-top10, litop"
                ),
                "lichess-player": _(
                    "Shows stats of a certain lichess player. This command accepts variants of chess as second argument to receive detailed stats of certain player for that variant. \nExample: `.lichessplayer {username} rapid`. \nAliases: liplayer, li-player, li-p"
                ),
                "lichess-game": _(
                    "Shows stats of a certain lichess game. \nExample: `.lichess-game {game id}`. \nAliases: li-game, li-g, lichessgame"
                ),
                "random-opening": _(
                    "Shows a random opening for inspirational purposes. \nExample: `.random-opening` \nAliases: roc"
                ),
            },
            _("Wolvesville commands"): {
                "wovplayer": _(
                    "Shows all the stats gathered from a Wolvesville account. Use an additional argument - `avatars`, to render all the avatars of a specific user. It can also be used to render a 'skill points' graph. Don't get your hopes up, it won't show the stats hidden by the player.\nExample: `.wovplayer {username}` \nAliases: wov-player, w-player, wov-p, wovp, w-p"
                ),
                "wovclan": _(
                    "Shows all the stats gathered about Wolvesville clan: description, creation date, members, etc. \nExample: `.wovclan {clan name}` \nAliases: wov-clan, w-clan, wov-c, wovc, w-c"
                ),
            },
            _("Account commands"): {
                "register": _(
                    "Use this command to start a registration process. You need an account to access locked bot's features\nAliases: reg, signup"
                ),
                "login": _(
                    "Use this command to log into your account or someone else's existing account (You will probably need their confirmation to transfer ownership)."
                ),
                "logout": _(
                    "Use this command to log out of your account, if you are logged in. Might be helpful."
                ),
                "nickname": _(
                    "Use this command to change your nickname (don't confuse it with username!). Example: `.nickname My New Nickname`"
                ),
                "wallet": _("Shows the amount of coins you have."),
                "daily": _("Collect coins daily!"),
                "preferences": _(
                    "Use this command to change your preferences. You can change your language, or set your custom prefix\nAliases: settings"
                ),
            },
        }
        select_options = []
        embed = discord.Embed(
            title=_("Help Command"),
            description=_("All available commands. Meow"),
            color=b_cfg.CustomColors.cyan,
        )
        embed.set_thumbnail(url=bot.user.display_avatar.url)
        embed.add_field(name=_("Sections"), value=_("*Use select menu*"))
        for section in help_dict:
            select_options.append(discord.SelectOption(label=f"{section}"))
        embed.set_footer(text=_("version {}").format(b_cfg.version))
        view = HelpView(embeds=help_dict, options=select_options, gettext_lang=_)

        view.message = await ctx.send(embed=embed, view=view)


bot.run(token)

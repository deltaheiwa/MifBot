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
import subprocess
import langcodes
import coloredlogs
import nest_asyncio
import psutil
import discord
from discord.ext import commands
from discord import app_commands
from dotenv import load_dotenv
from bot_util.bot_functions import AsyncTranslator
from bot_util import (
    bot_functions as b_func,
    bot_exceptions
)
import bot_util.bot_config as b_cfg
from bot_util.bot_ws import WebSocketClient
from bot_util.bot_strings_reader import BotStringsReader
from telegram_helper.main import MifTelegramReporter
from db_data.database_main import PrefixDatabase
from db_data import mysql_main
# from vg_ext.database.connector import PUDBConnector



toc = time.perf_counter()

initial_extensions = []

for filename in os.listdir("./cogs"):
    if filename.endswith(".py"):
        initial_extensions.append("cogs." + filename[:-3])

logger = logging.getLogger(__name__)
coloredlogs.install(level='INFO', logger=logger)
logger.setLevel(logging.INFO)
formatter = logging.Formatter('%(asctime)s:%(levelname)s --- %(message)s')
file_handler = logging.FileHandler(b_cfg.LogFiles.main_log)
file_handler.setFormatter(formatter)
logger.addHandler(file_handler)

error_logger = logging.getLogger(f"{__name__}_error")
error_logger.setLevel(logging.ERROR)
error_formatter = logging.Formatter('%(asctime)s:%(levelname)s:%(module)s --- %(message)s')
error_file_handler = logging.FileHandler(b_cfg.LogFiles.main_log)
error_file_handler.setFormatter(error_formatter)
error_logger.addHandler(error_file_handler)

nest_asyncio.apply()
activity = discord.Game("with Dan")
intents = discord.Intents.default()
intents.members = True
intents.dm_reactions = True
intents.message_content = True

class Mif(commands.Bot):
    def __init__(self, *args, **kwargs):
        super().__init__(
            command_prefix=b_func.determine_prefix,
            activity=activity,
            intents=intents,
            case_insensitive=True,
            status=discord.Status.idle
        )
        self.remove_command("help")
        self.interaction_server_overload = {}
        self.telegram_bot: MifTelegramReporter = None
        self.process = psutil.Process(os.getpid())
        self.ws_client = WebSocketClient()
        self.sub_js = None # Used for subprocess which runs js-twin

    async def setup_hook(self):
        for extension in initial_extensions:
            await self.load_extension(extension)
        '''
        if os.path.exists('./pu_ext'):
            from pu_ext.python_tree.loader import VillageGameLoader
            VillageGameLoader._load()
        '''
    
    async def on_ready(self):
        logger.info("We have logged in as %s", bot.user.name)
        logger.info("I'm in %s guilds!", len(bot.guilds))
        tic = time.perf_counter()
        logger.info(f"Bot loaded in {tic-toc:0.4f} seconds")
        await self.wait_until_ready()
        logger.info("Connecting to the databases")
        
        
        mysql_main.MySQLConnector.engine_creation()
        # PUDBConnector.engine_creation()
        asyncio.create_task(b_func.init_bot(self))
        logger.info("Bot is ready")
        await self.change_presence(
            status=discord.Status.online,
            activity=discord.Game(name="with Dan")
        )
        if os.path.exists("./js-twin/index.ts"):
            asyncio.create_task(self.launch_js_twin())
        else:
            logger.warning("File not found")
    
    async def launch_js_twin(self):
        self.sub_js = subprocess.Popen(["npx", "ts-node", "./js-twin/index.ts"], shell=True)
        logger.info("Launched js-twin")
        await asyncio.create_task(self.run_ws_client())
    
    async def run_ws_client(self):
        self.ws_client.run()
        await self.ws_client.send("Reaching js-twin")
    
    async def on_command_error(self, ctx: commands.Context, error: Exception) -> None:
        if hasattr(ctx.command, 'on_error'):
            return
        cog = ctx.cog
        if cog:
            if cog._get_overridden_method(cog.cog_command_error) is not None:
                return
        ignored = commands.CommandNotFound
        if isinstance(error, ignored):
            return
        error_logger.error(error, exc_info=(type(error), error, error.__traceback__))
        if isinstance(error, commands.MemberNotFound):
            embed=discord.Embed(
                title="Error",
                description="Couldn't find such user on discord",
                color=b_cfg.CustomColors.red
            )
            await ctx.reply(embed=embed)
            return
        if isinstance(error, commands.MissingPermissions):
            await ctx.reply(error, ephemeral=True)
            return
        if isinstance(error, commands.CommandOnCooldown):
            now = dt.utcnow()
            retry_after = timedelta(seconds=error.retry_after)
            retry_time = now + retry_after
            embed = discord.Embed(
                title="Slow down",
                description="You can retry in **{error}**."
                .format(error=f"<t:{int(calendar.timegm(retry_time.timetuple()))}:R>"),
                color=discord.Color.red()
            )
            await ctx.reply(embed=embed, delete_after=error.retry_after)
            return
        
        if isinstance(error, bot_exceptions.NotAuthorizedError):
            embed = discord.Embed(
                title="Error",
                description=error,
                color=b_cfg.CustomColors.red
            )
            await ctx.reply(embed=embed)
            return
        
        if isinstance(error , bot_exceptions.BattleMissingArgumentsError):
            embed = discord.Embed(
                title="No active characters",
                description="You haven't selected any characters.",
                color=discord.Color.red()
            )
            await ctx.reply(embed=embed)
        await self.telegram_bot._send_automatic_exception(error, ctx=ctx)
        return await super().on_command_error(ctx, error)
    
    async def on_guild_join(self, guild: discord.Guild):
        await PrefixDatabase.new_prefix(guild_id=guild.id, prefix='.')

    async def on_guild_remove(self, guild: discord.Guild):
        await PrefixDatabase.remove_prefix(guild_id=guild.id)

bot = Mif()
load_dotenv('creds/.env')
token = os.getenv("TOKEN")


@bot.event
async def on_message(message: discord.Message):
    await bot.process_commands(message)
    if (
        message.author != bot.user
        and message.content in ["...","..","...."]
        and message.guild
    ):
        if b_func.chance(10.0):
            if message.guild.id in bot.interaction_server_overload and \
            (dt.now()-bot.interaction_server_overload[message.guild.id])<timedelta(days=1,hours=12):
                return
            bot.interaction_server_overload.pop(message.guild.id, None)
            query_info = {'times_called': 1, 'amount': 0}
            fill = 0
            people = []
            channel_history = message.channel.history(limit=25)
            async for msg in channel_history:
                if msg.author.id == bot.user.id:
                    fill += 0.5
                    continue
                if msg.content in ["...","..","...."]:
                    people.append(msg.author.id) if msg.author.id not in people else None
                    query_info['times_called'] += 1 if fill > 0 else 0
                fill = 0
            query_info['amount'] += len(people)
            if query_info['times_called'] > 3:
                bot.interaction_server_overload[message.guild.id] = dt.now()
            message_to_send = BotStringsReader(bot,'triggering',message.author) \
                .return_string(query_info)
            await message.channel.send(embed=message_to_send) \
                if isinstance(message_to_send, discord.Embed) \
                else await message.channel.send(message_to_send)


@bot.hybrid_command(
    name="change-prefix",
    description="Changes the prefix of the bot",
    aliases = ["prefix"],
    with_app_command=True
)
@commands.has_guild_permissions(manage_guild=True)
async def changePrefix(ctx: commands.Context, prefix):
    await ctx.defer(ephemeral=True)
    async_trans = AsyncTranslator(
        language_code=mysql_main.JsonOperating.get_lang_code(ctx.author.id)
    )
    async with async_trans as lang:
        lang.install()
        _ = lang.gettext
        if ctx.message.author.guild_permissions.administrator \
            or ctx.message.author.guild_permissions.manage_guild:
            if ctx.guild is not None:
                await PrefixDatabase.new_prefix(ctx.guild.id, prefix)

            embed = discord.Embed(
                title="",
                description=_("Server prefix changed to: {prefix}").format(prefix=prefix),
                color=discord.Color.from_rgb(0, 255, 255),
            )
            await ctx.send(embed=embed)
            mysql_main.DatabaseFunctions.add_command_stats(ctx.author.id)
        else:
            embed = discord.Embed(
                title=_("Error, user missing permissions"),
                description=_(":x: Only `Administrator` or user with `Manage Server` permissions can change the prefix"),
                color=discord.Color.red(),
            )
            await ctx.reply(embed=embed)


class UserInfoButtonsView(discord.ui.View):
    def __init__(self, ui_embed, user, gettext_lang, *, timeout = 180):
        super().__init__(timeout=timeout)
        self.message: discord.Message
        self.user_info_embed = ui_embed
        self.user = user
        self._ = gettext_lang
    
    @discord.ui.button(label="Avatar", style=discord.ButtonStyle.blurple)
    async def avatar_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if button.label == "Avatar":
            embed=discord.Embed(
                title=self._("User's avatar"),
                description=f"{self.user}",
                color=self.user.color
            )
            embed.set_image(url=self.user.avatar.url)
            button.label = "User Info"
            await interaction.response.edit_message(embed=embed,view=self)
        elif button.label == "User Info":
            button.label = "Avatar"
            await interaction.response.edit_message(embed=self.user_info_embed, view=self)

    async def on_timeout(self) -> None:
        for item in self.children:
            item.disabled = True
        await self.message.edit(view=self)

@bot.hybrid_command(
    name="user-info",
    with_app_command=True,
    description="Shows basic data about specified user. Works for avatar as well")
async def userInfo(
    ctx: commands.Context,
    user:Union[
        discord.Member,
        discord.User,
        None
    ] = None) -> None:
    async_trans = AsyncTranslator(
        language_code=mysql_main.JsonOperating.get_lang_code(ctx.author.id)
    )
    async with async_trans as lang:
        lang.install()
        _ = lang.gettext
        if user is None:
            user = ctx.message.author
        empty = discord.utils.get(bot.emojis, name="empty")
        embed = discord.Embed(
            title=_("Info about user"),
            description=_("Here is the info I retrieved about {user}").format(user=user),
            color=user.color,
        )
        if isinstance(user, discord.Member) and user.nick is not None:
            nickname = user.nick
        else:
            nickname = user.global_name
        if user.avatar is not None: 
            embed.set_thumbnail(url=user.avatar.url)
        embed.add_field(name=_("Username"), value=user.name, inline=True)
        embed.add_field(name=_("Nickname"), value=nickname, inline=True)
        embed.add_field(name="ID", value=user.id, inline=True)
        embed.add_field(
            name=_("Status"),
            value=user.status if isinstance(user, discord.Member) else _("*Couldn't retrieve status*"),
            inline=True
        )
        embed.add_field(
            name=_("Top role"),
            value=user.top_role.name if isinstance(user, discord.Member) else _("*Couldn't retrieve highest role*"),
            inline=True
        )
        embed.add_field(name=empty,value=empty,inline=False)
        embed.add_field(name=_("Created"), value=b_func.pretty_date(user.created_at), inline=False)
        embed.add_field(
            name=_("Joined"),
            value=b_func.pretty_date(user.joined_at) if isinstance(user, discord.Member) else _("*Is not in the server*"),
            inline=False
        )
        view = UserInfoButtonsView(ui_embed = embed, user=user, gettext_lang=_)
        view.message = await ctx.send(embed=embed, view=view)
        mysql_main.DatabaseFunctions.add_command_stats(ctx.message.author.id)

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
        required=False
    )
    
    async def on_submit(self, interaction: discord.Interaction):
        self.preferences["prefix"] = self.custom_prefix.value if self.custom_prefix.value != "" else None
        mysql_main.JsonOperating.store_custom_prefix(self.user_id, self.preferences["prefix"])
        await PrefixDatabase.new_prefix(self.user_id, self.preferences["prefix"])
        async with AsyncTranslator(language_code=mysql_main.JsonOperating.get_lang_code(self.user_id)) as lang:
            lang.install()
            _ = lang.gettext
            embed = self.func(self.preferences, _)
            await interaction.response.edit_message(view=self.view, embed=embed)
        
class PreferencesView(discord.ui.View):
    def __init__(self, preferences, user_id, func, *, timeout: float | None = 300):
        super().__init__(timeout=timeout)
        self.message: discord.Message
        self.preferences = preferences
        self.user_id = user_id
        self.func = func
        self.modal: PreferencesModal
    
    @discord.ui.button(label="Change preferences", style=discord.ButtonStyle.blurple)
    async def change_preferences_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.modal = PreferencesModal(self.user_id, self.preferences, self.func, self)
        await interaction.response.send_modal(self.modal)
    
    @discord.ui.select(placeholder="Select language", min_values=1, max_values=1, options=[
        discord.SelectOption(label="English", description="English", emoji="🇬🇧", value='en'),
        discord.SelectOption(label="Ukrainian", description="Українська", emoji="🇺🇦", value='uk'),
        ]
    )
    async def language(self, interaction: discord.Interaction, select: discord.ui.Select):
        language = select.values[0]
        self.preferences["language"] = language
        mysql_main.JsonOperating.store_lang_code(self.user_id, language)
        
        async with AsyncTranslator(language_code=language) as lang:
            lang.install()
            _ = lang.gettext
            embed = self.func(self.preferences, _)
            await interaction.response.edit_message(embed=embed, view=self)
    
    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id == self.user_id:
            return True

        await interaction.response.send_message("You can't change someone's else settings", ephemeral=True)
        return False
    
    async def on_timeout(self):
        await self.message.edit(view=None)

@bot.hybrid_command(aliases=["settings"], name="preferences", description="Shows your preferences", with_app_command=True)
async def preferences(ctx: commands.Context):
    user = ctx.author
    
    async_trans = AsyncTranslator(language_code=mysql_main.JsonOperating.get_lang_code(ctx.author.id))
    async with async_trans as lang:
        lang.install()
        _ = lang.gettext
        
        if mysql_main.DatabaseFunctions.check_exists(user.id):
            preferences_stored = mysql_main.DatabaseFunctions.get_user_preferences(user.id)
            def build_embed(preferences, _):
                embed = discord.Embed(
                    title=_("Preferences"),
                    description=_("{}' preferences").format(user.name),
                    color=b_cfg.CustomColors.cyan
                )
                embed.add_field(
                    name=_("Custom prefix"),
                    value=f"**{preferences['prefix']}**" if preferences['prefix'] is not None \
                        else _("*There is no custom prefix set. The default is either `.` or server-specific.*"),
                    inline=False
                )
                embed.add_field(
                    name=_("Language"),
                    value=f"{b_cfg.language_emojis[preferences['language']]} **{langcodes.Language.make(language=preferences['language']).display_name(preferences['language']).capitalize()}**",
                    inline=False
                )
                return embed
            view = PreferencesView(preferences_stored, user.id, build_embed)
            view.message = await ctx.send(embed=build_embed(preferences_stored, _), view=view)
            mysql_main.DatabaseFunctions.add_command_stats(user.id)
        else:
            error_embed = discord.Embed(title="Error", description="You need to register first before setting your preferences.", color=b_cfg.CustomColors.red)
            await ctx.send(embed=error_embed)

@bot.hybrid_command(name="ping", description="Shows bot's ping", with_app_command=True)
async def ping(ctx: commands.Context):
    async_trans = AsyncTranslator(language_code=mysql_main.JsonOperating.get_lang_code(ctx.author.id))
    async with async_trans as lang:
        lang.install()
        _ = lang.gettext
        logger.info("My ping is %ms", round(bot.latency * 1000))
        await ctx.reply(_("Pong {}ms").format(round(bot.latency * 1000)))

@bot.command()
async def nsfw(ctx: commands.Context):
    user = ctx.message.author
    async_trans = AsyncTranslator(language_code=mysql_main.JsonOperating.get_lang_code(ctx.author.id))
    async with async_trans as lang:
        lang.install()
        _ = lang.gettext
        if isinstance(user, discord.User):
            return await ctx.reply(_("You are in my DMS. I can't call you!'"))
        assert isinstance(user, discord.Member)
        voice_state = user.voice   
        guild=ctx.guild
        def play_song(voice_channel):
            songs = []
            for song in os.listdir("./vcPlay"):
                songs.append(song)
            songs.insert(0,"a_normal.mp3")
            song_n = random.randint(1, 100)
            if song_n > (len(songs)-1):
                song_n = 0
            # create StreamPlayer
            main_dir = os.path.dirname(__file__)
            song_dir = "vcPlay/"+f"{songs[song_n]}"
            abs_file_path = os.path.join(main_dir, song_dir)
            voice_channel.play(discord.FFmpegPCMAudio(f"{abs_file_path}"))
            members = channel.members
            member_ids = []
            for person in members:
                member_ids.append(person.id)
            mysql_main.DatabaseFunctions.add_rickroll_stats(user.id, member_ids)
            mysql_main.DatabaseFunctions.add_command_stats(user.id)

        if voice_state is None:
            # Exiting if the user is not in a voice channel
            return await ctx.send(_("Join a voice chat and I will stream for you, senpaii-"))
        voice_clients = guild.voice_client # type: ignore
        channel = voice_state.channel
        if channel is not None and voice_clients is None:
            await channel.connect()
            voice_channel = discord.utils.get(bot.voice_clients, guild=guild)
            if voice_channel is None:
                embed = embed=discord.Embed(
                    title=_("Ugh, where are you?"),
                    description=_("I couldn't detect a voice channel to connect. Meow."),
                    color=b_cfg.CustomColors.red
                )
                await ctx.send(embed=embed)
                logger.error("VoiceProtocol not detected in %", guild)
                return
            play_song(voice_channel)
            while voice_channel.is_playing(): # type: ignore               
                await asyncio.sleep(1)
            await voice_channel.disconnect() # type: ignore
        elif channel is not None and voice_clients is not None:
            await ctx.send(_("Redirecting..."), delete_after = 10.0)
            await voice_clients.disconnect(force=True)
            await channel.connect()
            voice_channel = discord.utils.get(bot.voice_clients, guild=guild)
            play_song(voice_channel)
            while voice_channel.is_playing(): # type: ignore
                await asyncio.sleep(1)
            await voice_channel.disconnect() # type: ignore

@bot.hybrid_command(
    name="channel-access",
    with_app_command=True,
    description="Changes channel permissions for specified user",
    aliases=["channelAccess", "ch-access"]
)
@commands.has_guild_permissions(manage_permissions=True)
@app_commands.choices(
    add_remove=[
        app_commands.Choice(name="Add", value="add"),
        app_commands.Choice(name="Remove", value="remove"),
        app_commands.Choice(name="Default", value="default")
    ]
)
async def channelAccess(ctx: commands.Context, add_remove, channel: discord.TextChannel, *, members: str):
    await ctx.defer(ephemeral=True)
    perms_change = {"add": True, "remove": False, "default": None}
    members = members.split(" ")

    async_trans = AsyncTranslator(language_code=mysql_main.JsonOperating.get_lang_code(ctx.author.id))
    async with async_trans as lang:
        lang.install()
        _ = lang.gettext

        if add_remove.lower() not in perms_change:
            await ctx.send(_("Please specify if you want to add/remove or set default permissions"))
            return

        if len(members) < 1:
            await ctx.send(_("User not specified"))
            return

        processed_members = []
        for member in members:
            try:
                member_dc = await b_func.MembersOrRoles().convert(ctx, member)
                processed_members.append(member_dc[0])
            except commands.RoleNotFound:
                member_dc = discord.utils.find(
                    lambda m: m.name.lower().startswith(member),
                    ctx.guild.members
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
                description=_("Channel is unidentified, or channel type is not supported"),
                color=b_cfg.CustomColors.red)
            await ctx.reply(embed=embed_err)
            return

        try:
            mentions = []
            for member in processed_members:
                if isinstance(member, str):
                    continue
                await b_func.channel_perms_change(member, channel, perms_change[add_remove.lower()])
                mentions.append(member.mention)
            await ctx.reply(_("Updated permissions for {}").format(' '.join(mentions)))
            mysql_main.DatabaseFunctions.add_command_stats(ctx.author.id)
        except discord.Forbidden:
            embed_err = discord.Embed(
                title=_("Access error"),
                description=_("I have no access to {}").format(channel.name),
                color=b_cfg.CustomColors.red)
            await ctx.reply(embed=embed_err)


@bot.command(aliases=['patch'])
async def patchNotes(ctx: commands.Context):
    async_trans = AsyncTranslator(language_code=mysql_main.JsonOperating.get_lang_code(ctx.author.id))
    async with async_trans as lang:
        lang.install()
    
        _ = lang.gettext
        embed = discord.Embed(
            title=_("Patch notes"),
            description=_("for **{}**").format(b_cfg.version),
            color=b_cfg.CustomColors.cyan
        )
    embed.add_field(
        name="New!",
        value='''** · random-opening:** Added `.random-opening` command. ''',
        inline=False
    )
    embed.add_field(
        name="Changes",
        value='''** · Gradually improved bot's framework:** Updates should come out more often.
        ''',
        inline=False
    )
    embed.add_field(
        name="Fixes",
        value='''** · Critical Blackjack bug fix:** Losing and winning the game would incorrectly calculate your profit/loss.
        ** · Minor fixes:** Many other minor fixes which are not worth mentioned specifically.
        '''
    )
    await ctx.send(embed=embed)
    mysql_main.DatabaseFunctions.add_command_stats(ctx.author.id)


class HelpSelect(discord.ui.Select):
    def __init__(self, options, embeds: dict, gettext_lang):
        self._ = gettext_lang
        super().__init__(options=options, placeholder=self._("Select a section..."),min_values=1,max_values=1)
        self.embed_infos = embeds
        self.embeds = {}
    
    async def callback(self, interaction: discord.Interaction):
        if self.values[0] not in self.embeds:
            self.embeds[self.values[0]] = discord.Embed(title=self.values[0], description="", color=b_cfg.CustomColors.cyan)
            for command in self.embed_infos[self.values[0]]:
                self.embeds[self.values[0]].add_field(name=command, value=self.embed_infos[self.values[0]][command], inline=False)
            self.embeds[self.values[0]].set_footer(text=self._("version {}").format(b_cfg.version))
        
        await interaction.response.edit_message(embed=self.embeds[self.values[0]])

class HelpView(discord.ui.View):
    def __init__(self, embeds:dict, options, gettext_lang, *, timeout=3600): # timeout = 1 hour
        self.message: discord.Message
        super().__init__(timeout=timeout)
        self.add_item(HelpSelect(options=options, embeds=embeds, gettext_lang=gettext_lang))
    
    async def on_timeout(self) -> None:
        for item in self.children:
            item.disabled = True # type: ignore        
        await self.message.edit(view=self)

@bot.hybrid_command(name="help", aliases=['h'], description="Check what commands are available", with_app_command=True)
async def help(ctx):
    async_trans = AsyncTranslator(language_code=mysql_main.JsonOperating.get_lang_code(ctx.author.id))
    async with async_trans as lang:
        lang.install()
        _ = lang.gettext
        help_dict = {
            _("Administrative commands"):{
                "change-prefix": _("Changes server-specific prefix to a desirable one. You would need at least 'Manage server' permission to change it. \nExample: `.change-prefix -`"),
                "channel-access": _("Add/remove or set default access to the channel for specified users. You would need at least 'Manage permissions' permission to use it. Supports string searching.\nExample: `.channel-access Add #my-channel someonecute/@someonecute`"),
            },
            _("Informative commands"):{
                "userinfo": _("Retrieves info about mentioned user (If user is not specified, then about you). Button can be used to toggle between 'User info' and 'Avatar'. \nExample: `.user-info @someonecute`"),
                "ping": _("Pongs you back. Meow.\nYou may want to test if the bot is alive with it."), 
                "patchnotes": _("Check out what's changed with the latest update!"), 
                "botstats": _("Shows statistics on bot usage (wins/losses, amount of commands used, etc). Requires an account. \nAliases: bstats")
            },
            _("Fun and games"): {
                "nsfw": _("You have to be 18+ to use this command. Will stream a random 18+ video for you from ||`xvideos`||"), 
                "numberguessing": _("(Maybe) fun number guessing game. It has three difficulties: easy, medium, hard. Hard mode changes number every 20 guesses. \nAliases: ng, ngstart"),
                "hangman": _("Word guessing game. You have 6 tries until you hang a man. Over than 1500 words stored. Contact `{}` if you want to suggest new words. Has two modes - `short words` and `long words`. For example `.hangman short`. If you want it to be fully random, simply don't specify the length of the word.\nAliases: hgm, hangm").format(bot.get_user(835883093662761000)),
                "blackjack": _("A classic blackjack game. Requires an account, as you can bet on bot's currency. \nExample: `.blackjack 100` \nAliases: bj"),
                "bullsandcows": _("Both single-player and multiplayer games, 'bagels' and 'classic'. 'Bagels' has four types of difficulty - classic, fast, hard, and long. You can find more information by starting the game itself. All of the won, lost, and abandoned games are counted toward your stats if you have an account. \nExample: `.bulls bagels classic` \nAliases: [`bulls`] [`pfb`->bagels] [`blitz`->fast | `nerd`->long]\n\nYou can also check your records of the games you played with `.bulls records` command. Or a detailed information and replay of a certain game with `.bulls replay {game id}` command."),
            },
            _("Chess commands"): {
                "lichess-top10": _("Shows a list of top 10 players in every variant of chess. Use select menu to switch between variants. \nAliases: li-top10, litop"),
                "lichess-player": _("Shows stats of a certain lichess player. This command accepts variants of chess as second argument to receive detailed stats of certain player for that variant. \nExample: `.lichessplayer {username} rapid`. \nAliases: liplayer, li-player, li-p"),
                "lichess-game": _("Shows stats of a certain lichess game. \nExample: `.lichess-game {game id}`. \nAliases: li-game, li-g, lichessgame"),
                "random-opening": _("Shows a random chess opening for inspiration. \nAliases: roc, randomopening")
            },
            _("Wolvesville commands"): {
                "wovplayer": _("Shows all the stats gathered from a Wolvesville account. Use an additional argument - `avatars`, to render all the avatars of a specific user. It can also be used to render a 'skill points' graph. Don't get your hopes up, it won't show the stats hidden by the player.\nExample: `.wovplayer {username}` \nAliases: wov-player, w-player, wov-p, wovp, w-p"),
                "wovclan": _("Shows all the stats gathered about Wolvesville clan: description, creation date, members, etc. \nExample: `.wovclan {clan name}` \nAliases: wov-clan, w-clan, wov-c, wovc, w-c")
            },
            _("Account commands"): {
                "register": _("Use this command to start a registration process. You need an account to access locked bot's features\nAliases: reg, signup"),
                "login": _("Use this command to log into your account or someone else's existing account (You will probably need their confirmation to transfer ownership)."),
                "logout": _("Use this command to log out of your account, if you are logged in. Might be helpful."),
                "nickname": _("Use this command to change your nickname (don't confuse it with username!). Example: `.nickname My New Nickname`"), 
                "wallet": _("Shows the amount of coins you have."),
                "daily": _("Collect coins daily!"),
                "preferences": _("Use this command to change your preferences. You can change your language, or set your custom prefix\nAliases: settings"),
            }
        }
        select_options = []
        embed = discord.Embed(
            title=_("Help Command"),
            description=_("All available commands. Meow"),
            color=b_cfg.CustomColors.cyan
        )
        embed.set_thumbnail(url=bot.user.display_avatar.url)
        embed.add_field(name=_("Sections"), value=_("*Use select menu*"))
        for section in help_dict:
            select_options.append(discord.SelectOption(label=f"{section}"))
        embed.set_footer(text=_("version {}").format(b_cfg.version))
        view = HelpView(embeds=help_dict, options=select_options, gettext_lang=_)
        
        view.message = await ctx.send(embed=embed, view=view)


bot.run(token)

from cmath import log
import discord
import os
import re
import typing
import json
import time
import random
import asyncio
from discord.ext import commands
from discord import app_commands
from pymysql.connections import Connection
from pymysql.cursors import DictCursor
from discord.ui import Button
from hangman_words import *
import ffmpeg
import config
import creds
from functions import *
import pymysql
import get_sheets
import logging
import coloredlogs
import traceback
from sqlite_data import database_main

toc = time.perf_counter()

try:
    get_sheets.run()
except Exception as e:
    print(e)
try:
    connection = pymysql.connect(
        host=creds.host,
        port=3306,
        user=creds.user,
        password=creds.password,
        database=creds.db_name,
        cursorclass=pymysql.cursors.DictCursor
    )
    print("Connection succeded")
    print("#"*20)

    try:
        cursor = connection.cursor()

        # with connection.cursor() as cursor:
        #     drop_table_query = "DROP TABLE user_data;"
        #     cursor.execute(drop_table_query)
        # Create table
        with connection.cursor() as cursor:
            create_table_query = "CREATE TABLE IF NOT EXISTS users (id BIGINT," \
                "login VARCHAR(50) NOT NULL," \
                "password VARCHAR(128) NOT NULL," \
                "nickname VARCHAR(50) NOT NULL," \
                "is_logged BOOL NOT NULL," \
                "atc BOOL NOT NULL," \
                "PRIMARY KEY (id));"
            cursor.execute(create_table_query)
            print("Table users created successfully")

        with connection.cursor() as cursor:
            create_table_query = "CREATE TABLE IF NOT EXISTS user_data (user_id BIGINT," \
                "cash INT NOT NULL," \
                "level INT NOT NULL," \
                "xp INT NOT NULL," \
                "max_xp INT NOT NULL," \
                "bg INT NOT NULL," \
                "FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE ON UPDATE CASCADE);"
            cursor.execute(create_table_query)
            print("Table user_data created successfully")
            # insert_column = "ALTER TABLE user_data ADD COLUMN json_stats JSON AFTER bg;"
            # cursor.execute(insert_column)
            # connection.commit()
            # print("Added column to the user_data successfully")

        with connection.cursor() as cursor:
            create_table_query = "CREATE TABLE IF NOT EXISTS inventories (id INT AUTO_INCREMENT," \
                "user_id BIGINT," \
                "PRIMARY KEY (id)," \
                "FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE ON UPDATE CASCADE);"
            cursor.execute(create_table_query)
            print("Table inventories created successfully")

        with connection.cursor() as cursor:
            create_table_query = "CREATE TABLE IF NOT EXISTS item_type (id INT AUTO_INCREMENT," \
                "name VARCHAR(50) NOT NULL," \
                "PRIMARY KEY (id));"
            cursor.execute(create_table_query)
            print("Table item_type created successfully")

        with connection.cursor() as cursor:
            create_table_query = "CREATE TABLE IF NOT EXISTS inventory_slots (id INT AUTO_INCREMENT," \
                "inventory_id INT NOT NULL," \
                "slot_id INT NOT NULL," \
                "item_id INT NOT NULL," \
                "quantity INT NOT NULL," \
                "item_type_id INT NOT NULL," \
                "PRIMARY KEY (id)," \
                "FOREIGN KEY (item_type_id) REFERENCES item_type(id) ON DELETE CASCADE ON UPDATE CASCADE," \
                "FOREIGN KEY (inventory_id) REFERENCES inventories(id) ON DELETE CASCADE ON UPDATE CASCADE);"
            cursor.execute(create_table_query)
            print("Table inventory_slots created successfully")

        with connection.cursor() as cursor:
            create_table_query = "CREATE TABLE IF NOT EXISTS chests (id INT AUTO_INCREMENT," \
                "inventory_id INT," \
                "PRIMARY KEY (id)," \
                "FOREIGN KEY (inventory_id) REFERENCES inventories(id) ON DELETE CASCADE ON UPDATE CASCADE);"
            cursor.execute(create_table_query)
            print("Table chests created successfully")

        with connection.cursor() as cursor:
            create_table_query = "CREATE TABLE IF NOT EXISTS character_storage (id INT AUTO_INCREMENT," \
                "user_id BIGINT," \
                "PRIMARY KEY (id)," \
                "FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE ON UPDATE CASCADE);"
            cursor.execute(create_table_query)
            print("Table character_storage created successfully")

        with connection.cursor() as cursor:
            create_table_query = "CREATE TABLE IF NOT EXISTS characters (id INT AUTO_INCREMENT," \
                "user_storage_id INT NOT NULL," \
                "char_id INT NOT NULL," \
                "name TEXT NOT NULL," \
                "damage INT," \
                "hp INT," \
                "weapon INT," \
                "armor_ids VARCHAR(30)," \
                "active BOOL NOT NULL," \
                "PRIMARY KEY (id)," \
                "FOREIGN KEY (user_storage_id) REFERENCES character_storage(id) ON DELETE CASCADE ON UPDATE CASCADE);"
            cursor.execute(create_table_query)
            print("Table characters created successfully")
        
        with connection.cursor() as cursor:
            create_table_query = "CREATE TABLE IF NOT EXISTS bulls_records (id INT AUTO_INCREMENT," \
                "user_1 BIGINT," \
                "user_2 BIGINT," \
                "user_3 BIGINT," \
                "user_4 BIGINT," \
                "t1 TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP," \
                "player_won INT NOT NULL," \
                "json_game JSON," \
                "PRIMARY KEY (id));"
            cursor.execute(create_table_query)
            print("Table bulls_records created successfully")
        
        with connection.cursor() as cursor:
            create_table_query = "CREATE TABLE IF NOT EXISTS wov_players (id VARCHAR(50) NOT NULL," \
                "username VARCHAR(30) NOT NULL," \
                "personal_message VARCHAR(256)," \
                "json_data JSON," \
                "PRIMARY KEY (id));"
            cursor.execute(create_table_query)
            print("Table wov_players created successfully")
        
        with connection.cursor() as cursor:
            create_table_query = "CREATE TABLE IF NOT EXISTS wov_clans (id VARCHAR(50) NOT NULL," \
                "name VARCHAR(50) NOT NULL," \
                "connected BOOL," \
                "json_data JSON," \
                "description VARCHAR(512)," \
                "members JSON," \
                "PRIMARY KEY (id));"
            cursor.execute(create_table_query)
            print("Table wov_clans created successfully")
        
        # with connection.cursor() as cursor:
        #     altertable_query = "ALTER TABLE inventories ADD CONSTRAINT FK_USER_INV_ID FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE;" \
        #         "ALTER TABLE inventory_slots ADD CONSTRAINT FK_INVENTORY_ID FOREIGN KEY (inventory_id) REFERENCES inventories(id) ON DELETE CASCADE;" \
        #         "ALTER TABLE user_data ADD CONSTRAINT FK_USER_ID FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE;" \
        #         "ALTER TABLE characters ADD CONSTRAINT FK_CHARACTERS_ID FOREIGN KEY(user_storage_id) REFERENCES character_storage(id) ON DELETE CASCADE;" \
        #         "ALTER TABLE character_storage ADD CONSTRAINT FK_CSTORAGE_ID FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE;" \
        #         "ALTER TABLE chests ADD CONSTRAINT FK_CHESTS_ID FOREIGN KEY(inventory_id) REFERENCES inventories(id) ON DELETE CASCADE;"
        #     cursor.execute(altertable_query)
        #     connection.commit()
        #     print("Alter Table done successfully")

        # with connection.cursor() as cursor:
        #     insert_query = "INSERT INTO item_type (name) VALUES ('Weapon');"
        #     cursor.execute(insert_query)
        #     insert_query1 = "INSERT INTO item_type (name) VALUES ('Armor');"
        #     cursor.execute(insert_query1)
        #     insert_query2 = "INSERT INTO item_type (name) VALUES ('Items');"
        #     cursor.execute(insert_query2)
        #     connection.commit()

        # Insert data
        # with connection.cursor() as cursor:
        #     insert_query = "INSERT INTO users (name, password) VALUES ('Olga', '1q2w3e4r5t');"
        #     cursor.execute(insert_query)
        #     connection.commit()

        # Select all data from table
        # with connection.cursor() as cursor:
        #     select_all_rows = "SELECT * FROM users"
        #     cursor.execute(select_all_rows)
        #     rows = cursor.fetchall()
        #     for row in rows:
        #         print(row)

        # Update data
        # with connection.cursor() as cursor:
        #     update_query = "UPDATE users SET password = 'qwerty' WHERE id = 1"
        #     cursor.execute(update_query)
        #     connection.commit()

        # Delete data
        # with connection.cursor() as cursor:
        #     delete_query = "DELETE FROM users WHERE id = 2;"
        #     cursor.execute(delete_query)
        #     connection.commit()

        # Drop table
        # with connection.cursor() as cursor:
        #     drop_table_query = "DROP TABLE users;"
        #     cursor.execute(drop_table_query)
    finally:
        connection.close()
except Exception as e:
    print("Connection refused...")
    print(e)
try:
    database_main.main()
except Exception as e:
    print(e)


intitial_extensions = []

for filename in os.listdir("./cogs"):
    if filename.endswith(".py"):
        intitial_extensions.append("cogs." + filename[:-3])

logger = logging.getLogger(__name__)
coloredlogs.install(level='INFO', logger=logger)
logger.setLevel(logging.INFO)
formatter = logging.Formatter('%(asctime)s:%(levelname)s --- %(message)s')
file_handler = logging.FileHandler(config.main_log)
file_handler.setFormatter(formatter)
logger.addHandler(file_handler)

error_logger = logging.getLogger(f"{__name__}_error")
error_logger.setLevel(logging.ERROR)
error_formatter = logging.Formatter('%(asctime)s:%(levelname)s:%(module)s --- %(message)s')
error_file_handler = logging.FileHandler(config.main_log)
error_file_handler.setFormatter(error_formatter)
error_logger.addHandler(error_file_handler)

activity = discord.Game("with Dan")
intents = discord.Intents.default()
intents.members = True
intents.dm_reactions = True
intents.message_content = True



class Mif(commands.Bot):
    def __init__(self, *args, **kwargs):
        super().__init__(command_prefix=determine_prefix,activity=activity, intents=intents)
    
    async def setup_hook(self):
        # // self.synced = False
        for extension in intitial_extensions:
            await self.load_extension(extension)
        
        
    async def on_ready(self):
        # // await self.wait_until_ready()
        # // if not self.synced:
        # //    await app_commands.CommandTree.sync(self, guild = discord.Object(id=testing_guild_id))
        # //    self.synced = True
        print("We have logged in as {0.user}".format(bot))
        print(f"I'm in {len(bot.guilds)} guilds!")
        tic = time.perf_counter()
        print(f"Bot loaded in {tic-toc:0.4f} seconds")
    
    async def on_command_error(self, ctx, error) -> None:
        if hasattr(ctx.command, 'on_error'):
            return
        cog = ctx.cog
        if cog:
            if cog._get_overridden_method(cog.cog_command_error) is not None:
                return
        ignored = (commands.CommandNotFound)
        if isinstance(error, ignored):
            return
        error_logger.error(error, exc_info=(type(error), error, error.__traceback__))
        if isinstance(error, commands.MissingPermissions):
            await ctx.reply(error, ephemeral=True)
        if isinstance(error, commands.CommandOnCooldown):
            embed = discord.Embed(title="Slow down", description=f"You can retry in {error.retry_after:.2f}s.", color=discord.Color.red())
            await ctx.reply(embed=embed)
        return await super().on_command_error(ctx, error)
    
    async def on_guild_join(self, guild):
        await database_main.new_prefix(guild.id, '.')

    async def on_guild_remove(self, guild):
        await database_main.remove_prefix(guild.id)

#client = discord.Client(command_prefix=determine_prefix, activity=activity, intents=intents)
bot = Mif()
bot.remove_command("help")
token = creds.TOKEN_MIF


@bot.event
async def on_message(message):
    await bot.process_commands(message)
    id = message.author.id
    if (
        message.author != bot.user
        and message.content in ["...","..","...."]
    ):
        num = random.randint(1, 100)
        if num < 15:
            await message.channel.send("Stop triggering me!")
        else:
            pass
    # if message.author != bot.user message.guild.id

@commands.cooldown(1, 60, commands.BucketType.user)
@bot.command()
async def update(ctx):
    if ctx.message.author.id in config.admin_account_ids:
        try:
            get_sheets.run()
            await ctx.send("Updated successfully")
        except Exception as e:
            logger.exception("Error updating sheets")
            await ctx.send("ERROR!")
            await ctx.send(e)

@commands.cooldown(1, 60, commands.BucketType.user)
@commands.has_guild_permissions(administrator=True)
@bot.command()
async def sync(ctx):
    if ctx.message.author.id in config.admin_account_ids:
        message = await ctx.send("Syncing...")
        fmt = await bot.tree.sync()
        logger.info(f"Synced slash commands in {ctx.guild}")
        await message.edit(content=f"Successfully synced {len(fmt)} slash commands")



@bot.command(aliases = ["prefix"])
# @app_commands.guilds(discord.Object(id=testing_guild_id))
@commands.has_guild_permissions(manage_guild=True)
async def changeprefix(ctx: commands.Context, prefix):
    await ctx.defer(ephemeral=True)
    if ctx.message.author.guild_permissions.administrator or ctx.message.author.guild_permissions.manage_guild:
        await database_main.new_prefix(ctx.guild.id, prefix)

        embed = discord.Embed(
            title="",
            description=f"Prefix changed to: {prefix}",
            color=discord.Color.from_rgb(0, 255, 255),
        )
        await ctx.send(embed=embed)
    else:
        embed = discord.Embed(
            title="Error, user missing permissions",
            description=":x: Only `Administrator` or user with `Manage Server` permissions can change the prefix",
            color=discord.Color.red(),
        )
        await ctx.reply(embed=embed)

class UserinfoButtonsView(discord.ui.View):
    def __init__(self, ui_embed, user, *, timeout = 180):
        super().__init__(timeout=timeout)
        self.user_info_embed = ui_embed
        self.user = user
    
    @discord.ui.button(label="Avatar", style=discord.ButtonStyle.blurple)
    async def avatar_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if button.label == "Avatar":
            embed=discord.Embed(title="User's avatar", description=f"{self.user}", color=self.user.color)
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

@bot.command()
async def userinfo(ctx, member: discord.Member = None):
    if member is None:
        member = ctx.message.author
    user = member
    empty = discord.utils.get(bot.emojis, name="empty")
    embed = discord.Embed(
        title="Info about user",
        description=f"Here is the info I retrieved about {user}",
        color=user.color,
    )
    if user.nick == None:
        nickname = user.name
    else:
        nickname = user.nick
    embed.set_thumbnail(url=user.avatar.url)
    embed.add_field(name="Username", value=user.name, inline=True)
    embed.add_field(name="Nickname", value=nickname, inline=True)
    embed.add_field(name="ID", value=user.id, inline=True)
    embed.add_field(name="Status", value=user.status, inline=True)
    embed.add_field(name="Top role", value=user.top_role.name, inline=True)
    embed.add_field(name=empty,value=empty,inline=False)
    embed.add_field(name="Created", value=pretty_date(user.created_at), inline=False)
    embed.add_field(name="Joined", value=pretty_date(user.joined_at), inline=False)
    view = UserinfoButtonsView(ui_embed = embed, user=user)
    view.message = await ctx.send(embed=embed, view=view)
    add_command_stats(ctx.message.author)


@bot.command()
async def ping(ctx, arg=None):
    if arg == "pong":
        await ctx.reply("You already ponged yourself. Meow")
    else:
        logger.info(f"My ping is {round(bot.latency * 1000)}")
        await ctx.reply(f"Pong {round(bot.latency * 1000)}ms")


@bot.command()
async def nsfw(ctx):
    voice_state = ctx.author.voice
    guild=ctx.guild
    
    def play_song(vc):
        songs = []
        for song in os.listdir("./vcPlay"):
            songs.append(song)
        n = random.randint(1, 100)
        if n > (len(songs)-1):
            n = 0
        # create StreamPlayer
        main_dir = os.path.dirname(__file__)
        song_dir = "vcPlay/"+f"{songs[n]}"
        abs_file_path = os.path.join(main_dir, song_dir)
        vc.play(discord.FFmpegPCMAudio(f"{abs_file_path}"))
        members = channel.members
        memids = []
        for person in members:
            memids.append(person.id)
        add_rickroll_stats(ctx.author, memids)
        add_command_stats(ctx.message.author)

    if voice_state is None:
        # Exiting if the user is not in a voice channel
        return await ctx.send("Join a voice chat and I will stream for you, senpaii-")
    else:
        voice_clients = guild.voice_client
        channel = ctx.author.voice.channel
        if channel is not None and voice_clients is None:
            await channel.connect()
            vc = discord.utils.get(bot.voice_clients, guild=guild)
            play_song(vc)
            while vc.is_playing():
                await asyncio.sleep(1)
            await vc.disconnect()
        elif channel is not None and voice_clients is not None:
            await ctx.send("Redirecting...")
            await voice_clients.disconnect()
            await channel.connect()
            vc = discord.utils.get(bot.voice_clients, guild=guild)
            play_song(vc)
            while vc.is_playing():
                await asyncio.sleep(1)
            await vc.disconnect()

@bot.hybrid_command(name="channel-access",with_app_command=True, description="Changes channel permissions for specified user")
@commands.has_guild_permissions(manage_permissions=True)
@app_commands.choices(add_remove=[app_commands.Choice(name="Add", value="Adds permissions to the channel"), app_commands.Choice(name="Remove", value="Removes permissions from the channel")])
async def channelaccess(ctx: commands.Context, add_remove, channel: discord.TextChannel, *, member: typing.Union[discord.Member, discord.Role] = None, member2: typing.Union[discord.Member, discord.Role] = None, member3: typing.Union[discord.Member, discord.Role] = None):
    await ctx.defer(ephemeral=True)
    perms_change = True
    if member is None:
        await ctx.send("No user specified")
        return
    if add_remove == "Removes permissions from the channel" or add_remove.lower() == "remove":
        perms_change = False
    
    if type(channel) == discord.TextChannel:
        try:
            await channel.set_permissions(member, send_messages=perms_change, read_messages=perms_change, read_message_history=perms_change, view_channel=perms_change)
            if member2 is not None and type(member2) in [discord.Member, discord.Role]:
                await channel.set_permissions(member2, send_messages=perms_change, read_messages=perms_change, read_message_history=perms_change, view_channel=perms_change)
            if member3 is not None and type(member3) in [discord.Member, discord.Role]:
                await channel.set_permissions(member3, send_messages=perms_change, read_messages=perms_change, read_message_history=perms_change, view_channel=perms_change)
            await ctx.reply("Changed successfully")
        except discord.Forbidden:
            embed_err = discord.Embed(title="Access error", description=f"I have no access to {channel.name}", color=config.CustomColors.red)
            await ctx.reply(embed=embed_err)
    else:
        embed_err = discord.Embed(title="Channel error", description=f"Channel is unidentified, or channel type is not supported", color=config.CustomColors.red)
        await ctx.reply(embed=embed_err)


@bot.command(aliases=['patch'])
async def patchnotes(ctx):
    embed = discord.Embed(
        title="Patch notes",
        description=f"for **{config.version}**",
        colour=config.CustomColors.cyan
    )
    embed.add_field(
        name="New!",
        value='''  · Stats on bot's usage. Amount of wins in different games, etc.
             · Secret stat...
             · A classic "Bulls and Cows" trial-and-error game, you can play alone or with your friends!
             · Over 1000 new words for hangman (why did I do that :sob:)
             · Bot's currency - coins! 
             · Blackjack game, where you can win (or lose) bot's currency
             · Dailies! Another way to waste 5 seconds of your life, and collect some coins
             · Wolvesville commands. You may request information about players and clans, with some extra features
             · Channel managing with `.channel-access`. Adds or removes users from the channel
        ''',
        inline=False
    )
    embed.add_field(
        name="Minor fixes",
        value=''' · Slight improvement of number guessing game
             · Fixed two critical bugs in `.lichessplayer`, which broke the command
             · Improved help command. Now sorted, and has more information about commands
             · Account registration and login is now way cleaner
             · Fixed `.wovplayer` not working correctly. It now has case-sensitive search
             · Fixed `.wallet` showing '*Approximate value*' incorrectly in some cases
             · Fixed critical bug in `.nsfw` command. It's working again
        '''
    )
    embed.add_field(
        name="Coming soon...",
        value=''' · A chess game streaming in real time, and pgn viewer command
             · Wolvesville clan management commands
             · Replays of "Bulls and Cows" games you played 
        '''
    )
    await ctx.send(embed=embed)
    add_command_stats(ctx.message.author)


class HelpSelect(discord.ui.Select):
    def __init__(self, options, embeds: dict):
        super().__init__(options=options, placeholder="Select a section...",min_values=1,max_values=1)
        self.embed_infos = embeds
        self.embeds = {}
    
    async def callback(self, interaction: discord.Interaction):
        if self.values[0] not in self.embeds:
            self.embeds[self.values[0]] = discord.Embed(title=self.values[0], description="", color=config.CustomColors.cyan)
            for command in self.embed_infos[self.values[0]]:
                self.embeds[self.values[0]].add_field(name=command, value=self.embed_infos[self.values[0]][command], inline=False)
            self.embeds[self.values[0]].set_footer(text=f"version {config.version}")
        
        await interaction.response.edit_message(embed=self.embeds[self.values[0]])

class HelpView(discord.ui.View):
    def __init__(self, embeds:dict, options, *, timeout=3600): # timeout = 1 hour
        super().__init__(timeout=timeout)
        self.add_item(HelpSelect(options=options, embeds=embeds))
    
    async def on_timeout(self) -> None:
        for item in self.children:
            item.disabled = True
        
        await self.message.edit(view=self)

@bot.command()
async def help(ctx):
    help_dict = {
        "Administrative commands":{
            "changeprefix": "Changes prefix to desirable one. You would need at least 'Manage server' permission to change it. \nExample: `.changeprefix -`",
            "channel-access": "Add or remove access to the channel for specified users. You would need at least 'Manage permissions' permission to use it. \nExample: `.channel-access Add #my-channel @someonecute`"
        },
        "Informative commands":{
            "userinfo": "Retrieves info about mentioned user (If user is not specified, then about the author). Button can be used to toggle between 'User info' and 'Avatar'. \nExample: `.userinfo @someonecute`",
            "ping": "Pongs you back. Meow.\nYou may want to test if the bot is alive or not with it.", 
            "patchnotes": "Check what's changed with latest update!", 
            "botstats": "Shows statistics on bot usage (wins/losses, amount of commands used, etc). Requires an account. \nAliases: bstats"
        },
        "Fun and games": {
            "nsfw": "You have to be 18+ to use this command. Will stream a random 18+ video for you from ||`xvideos`||", 
            "numberguessing": "(Maybe) fun number guessing game. It has three difficulties: easy, medium, hard. Hardmode changes number every 20 guesses. \nAliases: ng, Numberguessing, ngstart",
            "hangman": f"Word guessing game. You have 6 tries until you hang a man. Over than 1000 words stored. Contact `{bot.get_user(835883093662761000)}` if you want to suggest new words. \nAliases: hgm, hangm",
            "blackjack": "A classic blackjack game. Requires an account, as you can bet on bot's currency. \nExample: `.blackjack 100` \nAliases: bj",
            "bullsandcows": "Both single-player and multiplayer games, 'bagels' and 'classic'. 'Bagels' has four types of difficulty - classic, fast, hard, and long. You can find more information by starting the game itself. All of the won, lost, and abandoned games are counted toward your stats if you have an account. \nExample: `.bulls bagels classic` \nAliases: [`bulls`] [`pfb`->bagels] [`blitz`->fast | `nerd`->long]",
        },
        "Chess commands": {
            "lichesstop10": "Shows a list of top 10 players in specified variant of chess. For example: `.lichesstop10 rapid`. \nAliases: li-top10, litop",
            "lichessplayer": "Shows stats of a certain lichess player. This command also accepts variants of chess as second argument to receive detailed stats of certain player for that variant. \nExample: `.lichessplayer {username} rapid`. \nAliases: liplayer, li-player, li-p"
        },
        "Wolvesville commands": {
            "wovplayer": "Shows all the stats gathered from a Wolvesville account. Use an additional argument, `avatars`, to render all the avatars of a specific user. It can also be used to render a 'skill points' graph. \nExample: `.wovplayer {username}` \n Aliases: wov-player, w-player, wov-p, wovp, w-p",
            "wovclan": "Shows all the stats gathered from a Wolvesville clan: description, date created, members, etc. \nExample: `.wovclan {clan name}` \nAliases: wov-clan, w-clan, wov-c, wovc, w-c"
        },
        "Account commands": {
            "register": "Use this command to start a registration process. You need an account to access locked bot's features",
            "login": "Use this command to log into your account or someone else's existing account (You will probably need their confirmation to transfer ownership).",
            "logout": "Use this command to log out of your account, if you are logged in. Might be helpful.",
            "nickname": "Use this command to change your nickname (don't confuse it with username!). Example: `.nickname My New Nickname`", 
            "wallet": "Shows the amount of coins you have.",
            "daily": "Collect coins daily!"
        }
    }
    select_options = []
    embed = discord.Embed(
        title="Help Command",
        description=f"All available commands. Meow",
        colour=config.CustomColors.cyan
    )
    embed.set_thumbnail(url="https://cdn.discordapp.com/attachments/874304187834454106/886616960044003328/0da4d00cb173cf7cb8ffbd9ee53f0010.png")
    embed.add_field(name="Sections", value="*Use select menu*")
    for section in help_dict:
        select_options.append(discord.SelectOption(label=f"{section}"))
    embed.set_footer(text=f"version {config.version}")
    view = HelpView(embeds=help_dict, options=select_options)
    
    view.message = await ctx.send(embed=embed, view=view)


bot.run(token)

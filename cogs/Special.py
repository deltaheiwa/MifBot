import shutil
import subprocess
import sys
import aiohttp
import discord
from discord.ext import commands
import bot_util.bot_config as b_cfg
import logging
from bot_util.bot_functions import CustomFormatter, dev_command, get_directory_structure
from bot_util.bot_exceptions import NotAuthorizedError
import coloredlogs
from db_data.database_main import Databases, PrefixDatabase, GameDb
from telegram_helper.main import MifTelegramReporter
import get_sheets
from db_data import mysql_main
import sqlite3
import os

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
formatter = logging.Formatter("%(asctime)s:%(levelname)s --- %(message)s")
console_formatter = CustomFormatter()
stream_handler = logging.StreamHandler()
coloredlogs.install(level="DEBUG", logger=logger)
file_handler_debug = logging.FileHandler(b_cfg.LogFiles.special_log)
file_handler_debug.setFormatter(formatter)
stream_handler.setFormatter(console_formatter)
logger.addHandler(file_handler_debug)

if os.path.exists("vg_ext"):
    from vg_ext.database.connector import PUDBConnector
else:
    logger.warning("vg_ext not found")


class ConfirmView(discord.ui.View):
    def __init__(self, ctx):
        super().__init__()
        self.ctx = ctx
        self.value = None
        self.message: discord.Message

    async def disable_all_buttons(self):
        for child in self.children:
            child.disabled = True

    @discord.ui.button(label="Confirm", style=discord.ButtonStyle.green)
    async def confirm(self, interaction: discord.Interaction, button: discord.Button):
        self.value = True
        self.stop()

        self.disable_all_buttons()
        await interaction.response.edit_message(view=self)

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.red)
    async def cancel(self, interaction: discord.Interaction, button: discord.Button):
        self.value = False
        self.stop()

        self.disable_all_buttons()
        await interaction.response.edit_message(view=self)

    async def interaction_check(self, interaction: discord.Interaction):
        if interaction.user.id in b_cfg.admin_account_ids:
            return True
        else:
            raise NotAuthorizedError("You are not authorized to use this command")

    async def on_timeout(self):
        self.disable_all_buttons()
        await self.message.edit(view=self)

        self.value = False
        self.stop()


class Special(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.admins = b_cfg.admin_account_ids

    async def cog_load(self):
        print("Special cog loaded successfully!")

    @commands.command(aliases=["resources"])
    @dev_command()
    async def resourceUsage(self, ctx: commands.Context):
        await ctx.send(
            f"```{self.bot.process.cpu_percent()}% CPU\n{round(self.bot.process.memory_full_info().rss/1024/1024, 1)} MB RAM```"
        )

    @commands.cooldown(1, 60, commands.BucketType.user)
    @commands.command()
    @dev_command()
    async def sync(self, ctx):
        message = await ctx.send("Syncing...")
        fmt = await self.bot.tree.sync()
        logger.info(f"Synced slash commands in {ctx.guild}")
        await message.edit(content=f"Successfully synced {len(fmt)} slash commands")

    @commands.command(aliases=["telegram-launch", "tl"])
    @dev_command()
    async def launchBot(self, ctx):
        if self.bot.telegram_bot is not None:
            await ctx.send("Bot already launched")
            return
        message = await ctx.send("Launching bot...")
        try:
            self.bot.telegram_bot = MifTelegramReporter(self.bot.application_id)
            await self.bot.telegram_bot.run()
        except Exception as e:
            await message.edit(content=f"Error launching bot\n{e}")

    @commands.hybrid_command(
        name="reload-cog",
        description="Reloads specified cog",
        with_app_command=True,
        guild=discord.Object(id=b_cfg.main_guild_id),
        aliases=["rc", "r-c", "reload-c", "reloadc"],
    )
    @dev_command()
    async def reloadCog(self, ctx: commands.Context, cog):
        try:
            await self.bot.reload_extension(f"cogs.{cog.capitalize()}")
            await ctx.send(f"Reloaded cog {cog}")
        except Exception as e:
            await ctx.send(f"Couldn't reload cog {cog}")
            logger.error(e)

    @commands.command()
    @dev_command()
    async def restart(self, ctx):
        script_path = os.path.join(
            os.getcwd(), "run_bot.bat" if os.name == "nt" else "run_bot.bash"
        )

        try:
            # subprocess.run(
            #    [script_path], check=True, shell=True if os.name == "nt" else False
            # )
            await ctx.send("Bot restarted")
            await self.bot.stop()
        except Exception as e:
            logger.exception(e)
            await ctx.send("Error restarting bot")

    @commands.hybrid_command(
        name="update-file",
        description="Updates specified file",
        with_app_command=True,
        guild=discord.Object(id=b_cfg.main_guild_id),
        aliases=["uf", "u-f", "update-f", "updatef"],
    )
    @dev_command()
    async def updateFile(self, ctx: commands.Context, path: str = "./", *, args=None):
        if len(ctx.message.attachments) == 0:
            await ctx.send("No file provided!")
            return
        attachment = ctx.message.attachments[0]
        BACKUP_PATH = "./backup_files/"
        args = args.split() if isinstance(args, str) else []

        # Confirmation before overwriting
        if os.path.exists(f"{path}{attachment.filename}"):
            view = ConfirmView(ctx)
            embed = discord.Embed(
                title="File already exists",
                description=f"File {attachment.filename} already exists. Overwrite?",
                color=b_cfg.CustomColors.dark_red,
            )
            view.message = await ctx.send(embed=embed, view=view)
            await view.wait()
            if not view.value:
                await ctx.send("Operation cancelled.")
                return

        # Check if directory does not exist, to create one
        if not os.path.isdir(path):
            view = ConfirmView(ctx)
            embed = discord.Embed(
                title="Directory does not exist",
                description="The specified directory does not exist. Create it?",
                color=b_cfg.CustomColors.dark_red,
            )
            view.message = await ctx.send(embed=embed, view=view)
            await view.wait()
            if not view.value:
                await ctx.send("Operation cancelled.")
                return
            os.makedirs(path)

        # Backup existing file
        backup_filename = f"{attachment.filename}.bak"
        if os.path.exists(f"{BACKUP_PATH}{attachment.filename}"):
            shutil.copyfile(
                f"{path}{attachment.filename}", f"{BACKUP_PATH}{backup_filename}"
            )

        # Download and save the file
        async with aiohttp.ClientSession() as session:
            async with session.get(str(attachment.url)) as response:
                # Read the file content
                file_content = await response.read()
                # Save the file
                with open(f"{path}{attachment.filename}", "wb") as file:
                    file.write(file_content)

        if set(args).intersection({"d", "delete"}):
            await ctx.message.delete()

        embed = discord.Embed(
            title="File updated",
            description=f"File {attachment.filename} has been updated!",
            color=b_cfg.CustomColors.cyan,
        )
        if not set(args).intersection({"nodir", "nd"}):
            get_dir = get_directory_structure()
            for content in get_dir:
                await ctx.author.send(content=content)

        await ctx.send(embed=embed)

    @commands.command()
    async def revert_file(self, ctx, filename: str, filepath: str = "./"):
        backup_filename = f"{filename}.bak"
        BACKUP_PATH = "./backup_files/"
        try:
            if os.path.exists(f"{BACKUP_PATH}{backup_filename}"):
                shutil.copyfile(
                    f"{BACKUP_PATH}{backup_filename}", f"{filepath}{filename}"
                )  # Find a path to the file in the directory
                await ctx.send(f"Reverted changes to {filename}.")
            else:
                await ctx.send(f"No backup found for {filename}.")
        except Exception as e:
            await ctx.send(f"Error reverting changes to {filename}.\n```{e}```")
            logger.exception(f"Error reverting changes to {filename}.\n{e}")

    @commands.command()
    @dev_command()
    async def database(self, ctx, arg, arg2=None, arg3=None):
        match arg:
            case "mysql":
                match arg2:
                    case "mif":
                        match arg3:
                            case "create":
                                mysql_main.DatabaseFunctions.create_tables()
                                await ctx.reply("Created tables")
                    case "mif_vg":
                        match arg3:
                            case "create":
                                try:
                                    PUDBConnector.create_tables()
                                    await ctx.reply("Created tables")
                                except Exception as e:
                                    await ctx.reply(f"Error: {e}")
            case "local":
                match arg2:
                    case "game":
                        match arg3:
                            case "drop":
                                Databases.game.unlink()
                                await ctx.reply("Dropped database")
                            case "init":
                                GameDb.initiate_db()
                                await ctx.reply("Initialized database")

            case "help":
                await ctx.reply(
                    "```database <mysql/local> <mif/mif_vg|game> <create|drop/init>```"
                )

    @commands.cooldown(1, 60, commands.BucketType.user)
    @commands.command()
    @dev_command()
    async def update(self, ctx, tabledb=None, obj_id=None):
        """Update the the database with the latest data from sheets.

        Args:
            tabledb (str, optional): table to update. If None, inserts new objects to all tables. Defaults to None.
            obj_id (str/int, optional): item id to update. If None, updates all items in the table. Defaults to None.
        """
        try:
            get_sheets.run()

            def table_update(type_of_update, table, start_id, end_id=-1):
                sheets_data = get_sheets.SheetsData().return_section(table)
                new_records = []
                id_list = []
                if end_id == -1:
                    end_id = len(sheets_data)
                for ids in range(start_id, end_id):
                    data = []
                    for cell in sheets_data[ids]:
                        data.append(cell)
                    if type_of_update == "update":
                        data.append(sheets_data[ids][0])
                    new_records.append(tuple(data))
                    id_list.append(str(ids))

                question_marks = "?" * len(sheets_data[0])
                question_marks = ",".join(question_marks)

                if type_of_update == "insert":
                    executemany_query = (
                        f"INSERT INTO {table} VALUES ({question_marks});"
                    )
                else:
                    set_dict = {
                        "weapons": "id = ?, name = ?, description = ?, damage = ?, second_attack = ?, special_ability = ?, element = ?, rarity = ?, weapon_type = ?, value = ?, craft = ?, drops = ?, image = ?, crit_chance = ?",
                        "armors": "id = ?, name = ?, description = ?, armor_points = ?, armor_resistance = ?, armor_type = ?, special_ability = ?, element = ?, rarity = ?, set_bonus = ?, value = ?, craft = ?, drops = ?, image = ?",
                        "enemies": "id = ?, name = ?, description = ?, damage = ?, hp = ?, element = ?, weapon = ?, armor = ?, second_action = ?, third_action = ?, passive_ability = ?, special_ability = ?, drops = ?, image = ?",
                        "characters": "id = ?, name = ?, description = ?, damage = ?, hp = ?, element = ?, weapon = ?, armor = ?, second_action = ?, third_action = ?, passive_ability = ?, special_ability = ?, craft = ?, drops = ?, image = ?",
                        "general_items": "id = ?, name = ?, description = ?, item_type = ?, value = ?, rarity = ?, crafted_by = ?, craft = ?, crafted_on = ?, drops = ?, image = ?, max_stock = ?",
                        "artefacts": "id = ?, name = ?, description = ?, passive_effect = ?, active_effect = ?, synergy = ?, element = ?, rarity = ?, value = ?, craft = ?, drops = ?, image = ?",
                    }
                    executemany_query = (
                        f"UPDATE {table} SET {set_dict[table]} WHERE id = ?;"
                    )
                if len(new_records) == 1:
                    new_records = new_records[0]
                    c.executemany(executemany_query, (new_records,))
                else:
                    c.executemany(executemany_query, new_records)

            with sqlite3.connect(Databases.game) as conn:
                c = conn.cursor()
                tables = [
                    "armors",
                    "weapons",
                    "enemies",
                    "characters",
                    "general_items",
                    "artefacts",
                ]
                if tabledb is not None and (tabledb) in tables:
                    if obj_id is None:
                        table_update("update", tabledb, 0, -1)
                    else:
                        table_update("update", tabledb, int(obj_id), int(obj_id) + 1)
                else:
                    for table_name in tables:
                        c.execute(
                            f"SELECT id FROM {table_name} ORDER BY id DESC LIMIT 1;"
                        )

                        last_record = c.fetchone()
                        sheets_data = get_sheets.SheetsData().return_section(table_name)

                        if last_record is not None and last_record[0] == int(
                            sheets_data[-1][0]
                        ):
                            continue
                        next_id = 0
                        if last_record is not None:
                            next_id = int(last_record[0]) + 1
                        table_update("insert", table_name, next_id, -1)

            await ctx.send("Updated successfully")
        except Exception as e:
            logger.exception("Error updating sheets")
            await ctx.send(f"ERROR!\n{e}")

        get_sheets.delete_cache()

    @commands.hybrid_command(
        aliases=[],
        with_app_command=True,
        name="information",
        description="Get information about the bot",
        guilds=[b_cfg.main_guild_id],
    )
    @dev_command()
    async def information(self, ctx: commands.Context):
        await ctx.defer(ephemeral=True)
        embed = discord.Embed(
            title="Information",
            description="Information about the bot",
            colour=b_cfg.CustomColors.cyan,
        )
        embed.set_thumbnail(url=self.bot.user.avatar.url)
        embed.add_field(name="Version", value=b_cfg.version)
        embed.add_field(name="Guilds in", value=len(self.bot.guilds))
        embed.add_field(name="Ping", value=f"{round(self.bot.latency*1000)}ms")

        await ctx.send(embed=embed)

    @commands.hybrid_command(
        aliases=["dir"],
        with_app_command=True,
        name="directory",
        description="Get the directory structure of the bot",
        guilds=[b_cfg.main_guild_id],
    )
    @dev_command()
    async def directory(self, ctx):
        # Generate the directory listing
        directory_structure = get_directory_structure()

        # Write to a text file
        file_path = "./junk/directory_list.txt"
        with open(file_path, "w") as file:
            file.write(directory_structure)

        # Send the file
        with open(file_path, "rb") as file:
            await ctx.send(file=discord.File(file, "directory_list.txt"))

    @commands.hybrid_command(
        name="help-dev",
        description="Provides help information for developer commands",
        with_app_command=True,
        guilds=[b_cfg.main_guild_id],
        aliases=["helpDev", "helpD"],
    )
    @dev_command()
    async def helpDev(self, ctx):
        embed = discord.Embed(
            title="Developer Commands Help",
            description="List of available commands for developers",
            color=b_cfg.CustomColors.cyan,
        )

        embed.add_field(
            name="resourceUsage",
            value="Shows the bot's current resource usage. No arguments needed. Aliases: ['resources']",
            inline=False,
        )
        embed.add_field(
            name="sync",
            value="Syncs the bot's slash commands. No arguments needed.",
            inline=False,
        )
        embed.add_field(
            name="launchBot",
            value="Launches the Telegram bot if not already running. No arguments needed. Aliases: ['telegram-launch', 'tl']",
            inline=False,
        )
        embed.add_field(
            name="reloadCog <cog>",
            value="Reloads the specified cog. Argument: `<cog>` - the name of the cog to reload. Aliases: ['rc', 'r-c', 'reload-c', 'reloadc']",
            inline=False,
        )
        embed.add_field(
            name="updateFile <path> <*args>",
            value="Updates a specified file with an uploaded attachment. Arguments: `<path>` - the path to save the file, `*args` - additional arguments like 'd' for delete, 'nd' for no directory. Aliases: ['uf', 'u-f', 'update-f', 'updatef']",
            inline=False,
        )
        embed.add_field(
            name="revert_file <filename> [filepath]",
            value="Reverts changes to a specified file. Arguments: `<filename>` - the name of the file to revert, `[filepath]` - optional path where the file is located.",
            inline=False,
        )
        embed.add_field(
            name="database <type> <subcommand> [action]",
            value="Interacts with the bot's database. Arguments: `<type>` - type of database ('mysql' or 'local'), `<subcommand>` - specific command for the database, `[action]` - optional action like 'create', 'drop', 'init'. Usage: `.database mysql mif create`",
            inline=False,
        )
        embed.add_field(
            name="update [tabledb] [obj_id]",
            value="Updates the database with the latest data from sheets. Arguments: `[tabledb]` - optional, specifies the table to update, `[obj_id]` - optional, specifies the object ID to update.",
            inline=False,
        )
        embed.add_field(
            name="information",
            value="Gets information about the bot. No arguments needed.",
            inline=False,
        )

        await ctx.send(embed=embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(Special(bot))

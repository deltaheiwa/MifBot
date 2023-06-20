import discord
from discord.ext import commands
import util.bot_config as b_cfg
import logging
from util.bot_functions import CustomFormatter
import coloredlogs
from db_data.database_main import Databases, PrefixDatabase, GameDb
import get_sheets
from db_data import mysql_main
import sqlite3


logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
formatter = logging.Formatter('%(asctime)s:%(levelname)s --- %(message)s')
console_formatter = CustomFormatter()
stream_handler = logging.StreamHandler()
coloredlogs.install(level='DEBUG', logger=logger)
file_handler_debug = logging.FileHandler(b_cfg.LogFiles.special_log)
file_handler_debug.setFormatter(formatter)
stream_handler.setFormatter(console_formatter)
logger.addHandler(file_handler_debug)


class Special(commands.Cog):
    def __init__(self, bot:commands.Bot):
        self.bot = bot
        self.admins = b_cfg.admin_account_ids
    
    async def cog_load(self):
        print("Special cog loaded successfully!")

    @commands.cooldown(1, 60, commands.BucketType.user)
    @commands.has_guild_permissions(administrator=True)
    @commands.command()
    async def sync(self, ctx):
        if ctx.message.author.id in self.admins:
            message = await ctx.send("Syncing...")
            fmt = await self.bot.tree.sync()
            logger.info(f"Synced slash commands in {ctx.guild}")
            await message.edit(content=f"Successfully synced {len(fmt)} slash commands")
    
    @commands.command()
    async def database(self, ctx, arg, arg2):
        if ctx.message.author.id in self.admins:
            match arg:
                case "drop":
                    Databases.game.unlink()
                    await ctx.reply("Dropped database")
                case "init":
                    GameDb.initiate_db()
                    await ctx.reply("Initialized database")
                case "mysql":
                    match arg2:
                        case 'create':
                            mysql_main.DatabaseFunctions.create_tables()
                            await ctx.reply("Created tables")

    @commands.cooldown(1, 60, commands.BucketType.user)
    @commands.command()
    async def update(ctx, tabledb=None, obj_id=None):
        '''Update the the database with the latest data from sheets.
        
        Args:
            tabledb (str, optional): table to update. If None, inserts new objects to all tables. Defaults to None.
            obj_id (str/int, optional): item id to update. If None, updates all items in the table. Defaults to None.
        '''
        if ctx.message.author.id in b_cfg.admin_account_ids:
            try:
                get_sheets.run()
                def table_update(type_of_update, table, start_id, end_id=-1):
                    sheets_data = get_sheets.SheetsData().return_section(table)
                    new_records = []
                    id_list = []
                    if end_id == -1: end_id = len(sheets_data)
                    for ids in range(start_id, end_id):
                        data = []
                        for cell in sheets_data[ids]:
                            data.append(cell)
                        if type_of_update == "update":
                            data.append(sheets_data[ids][0])
                        new_records.append(tuple(data))
                        id_list.append(str(ids))
                    
                    
                    question_marks = "?"*len(sheets_data[0])
                    question_marks = ','.join(question_marks)
                    
                    if type_of_update == "insert":
                        executemany_query = f"INSERT INTO {table} VALUES ({question_marks});"
                    else:
                        set_dict = {"weapons": "id = ?, name = ?, description = ?, damage = ?, second_attack = ?, special_ability = ?, element = ?, rarity = ?, weapon_type = ?, value = ?, craft = ?, drops = ?, image = ?, crit_chance = ?", 
                                    "armors": "id = ?, name = ?, description = ?, armor_points = ?, armor_resistance = ?, armor_type = ?, special_ability = ?, element = ?, rarity = ?, set_bonus = ?, value = ?, craft = ?, drops = ?, image = ?", 
                                    "enemies": "id = ?, name = ?, description = ?, damage = ?, hp = ?, element = ?, weapon = ?, armor = ?, second_action = ?, third_action = ?, passive_ability = ?, special_ability = ?, drops = ?, image = ?", 
                                    "characters": "id = ?, name = ?, description = ?, damage = ?, hp = ?, element = ?, weapon = ?, armor = ?, second_action = ?, third_action = ?, passive_ability = ?, special_ability = ?, craft = ?, drops = ?, image = ?",
                                    "general_items": "id = ?, name = ?, description = ?, item_type = ?, value = ?, rarity = ?, crafted_by = ?, craft = ?, crafted_on = ?, drops = ?, image = ?, max_stock = ?",
                                    "artefacts": "id = ?, name = ?, description = ?, passive_effect = ?, active_effect = ?, synergy = ?, element = ?, rarity = ?, value = ?, craft = ?, drops = ?, image = ?"}
                        executemany_query = f"UPDATE {table} SET {set_dict[table]} WHERE id = ?;"
                    if len(new_records) == 1:
                        new_records = new_records[0]
                        c.executemany(executemany_query, (new_records,))
                    else: c.executemany(executemany_query, new_records)
                with sqlite3.connect(Databases.game) as conn:
                    c = conn.cursor()
                    tables = ['armors', 'weapons', 'enemies', 'characters', 'general_items', "artefacts"]
                    if tabledb is not None and (tabledb) in tables:
                        if obj_id is None:
                            table_update("update", tabledb, 0, -1)
                        else: table_update("update", tabledb, int(obj_id), int(obj_id)+1)
                    else: 
                        for table_name in tables:
                            c.execute(f"SELECT id FROM {table_name} ORDER BY id DESC LIMIT 1;")
                            
                            last_record = c.fetchone()
                            sheets_data = get_sheets.SheetsData().return_section(table_name)
                            
                            if last_record is not None and last_record[0] == int(sheets_data[-1][0]): continue
                            next_id = 0
                            if last_record is not None: next_id = int(last_record[0]) + 1
                            table_update("insert", table_name, next_id, -1)
                        
                await ctx.send("Updated successfully")
            except Exception as e:
                logger.exception("Error updating sheets")
                await ctx.send(f"ERROR!\n{e}")
                
            get_sheets.delete_cache()

async def setup(bot:commands.Bot):
    await bot.add_cog(Special(bot))
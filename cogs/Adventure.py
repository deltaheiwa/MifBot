import discord
import random
import asyncio
import json
from tqdm import tqdm
import names
from discord.ext import commands
from discord.ui import Button
from discord import app_commands
from bot_util.bot_functions import *
import bot_util.bot_exceptions as bot_exceptions
import creds
import bot_util.bot_config as bot_config
from get_sheets import SheetsData
import GameFunctions as GF

from db_data.database_main import GameDb
from db_data.mysql_main import DatabaseFunctions as DF
from db_data.mysql_main import JsonOperating as JO
import traceback

logger = logging.getLogger(__name__)
coloredlogs.install(level='DEBUG', logger=logger)
logger.setLevel(logging.DEBUG)
formatter = logging.Formatter('%(asctime)s:%(levelname)s --- %(message)s')
file_handler = logging.FileHandler(bot_config.LogFiles.adventure_log)
file_handler.setFormatter(formatter)
logger.addHandler(file_handler)

class Adventure(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
    
    async def cog_load(self):
        print("Adventure cog loaded successfully!")

    @commands.command()
    async def addxp(self, ctx, amount):
        if ctx.message.author.id in bot_config.admin_account_ids:
            DF.add_xp(ctx.author.id, int(amount))
            await ctx.send("Added successfully")
    

    @commands.command()
    async def adventurestart(self, ctx:commands.Context):
        user = ctx.message.author
        user_id = ctx.message.author.id
        if DF.local_checks(user.id):
            try:
                connection = pymysql.connect(
                    host=creds.host,
                    port=3306,
                    user=creds.user,
                    password=creds.password,
                    database=creds.db_name,
                    cursorclass=pymysql.cursors.DictCursor
                )
                try:
                    with connection.cursor() as cursor:
                        check_if_inv_exists = f"SELECT user_id FROM character_storage WHERE user_id = '{user_id}'"
                        cursor.execute(check_if_inv_exists)
                        check_if_inv_exists_ret = cursor.fetchone()
                        print(check_if_inv_exists_ret)
                    if check_if_inv_exists_ret != None:
                        await ctx.send("You have already started your adventure!")
                    else:
                        # print("Doesnt exist inv")
                        with connection.cursor() as cursor:
                            insert_query = f"INSERT IGNORE INTO character_storage (user_id) VALUES ('{user_id}');"
                            cursor.execute(insert_query)
                            connection.commit()
                            print("Inserted CHARACTER_STORAGE successfully")
                        with connection.cursor() as cursor:
                            insert_query = f"INSERT IGNORE INTO inventories (user_id) VALUES ('{user_id}');"
                            cursor.execute(insert_query)
                            connection.commit()
                            print("Inserted INVENTORY successfully")
                        with connection.cursor() as cursor:
                            select_inventory = f"SELECT id FROM inventories WHERE user_id = '{user_id}'"
                            cursor.execute(select_inventory)
                            inv_id = cursor.fetchone()
                        with connection.cursor() as cursor:
                            select_char_storage = f"SELECT id FROM character_storage WHERE user_id = '{user_id}'"
                            cursor.execute(select_char_storage)
                            stor_id = cursor.fetchone()
                        with connection.cursor() as cursor:
                            insert_weapon1 = f"INSERT IGNORE INTO inventory_slots (inventory_id, slot_id, item_id, quantity, item_type_id) " \
                                f"VALUES ('{inv_id['id']}', 1, 0, 1, 1)"
                            cursor.execute(insert_weapon1)
                            connection.commit()
                        print("Inserted WEAPON successfully")
                        with connection.cursor() as cursor:
                            main_character = GF.Character(0)
                            insert_query = f"INSERT IGNORE INTO characters (user_storage_id, char_id, name, level, damage, hp, weapon, armor_ids, artefact_id, active) " \
                                f"VALUES ('{stor_id['id']}', 0, '{names.get_first_name()}', 1, '{main_character.damage}', '{main_character.hp}', NULL, NULL, NULL, TRUE);"
                            cursor.execute(insert_query)
                            connection.commit()
                            print("Inserted MAIN_CHARACTER successfully")
                            await user.send("well")
                except Exception as e:
                    print(e)
                finally:
                    connection.close()
            except Exception as e:
                print("Connection refused...")
                print(e)

    @commands.command(aliases=['b'])
    async def battle(self, ctx):
        user = ctx.message.author

        active_characters = get_player_characters(user)
        print(active_characters)
        try:
            # error_instance = GF.GameManager() # ! Should raise a BattleMissingArgumentsError exception because no active characters specified
            gm_instance = GF.GameManager(enemy_ids=[0,0,0], active_characters=active_characters)
        except Exception as e:
            if isinstance(e, bot_exceptions.BattleMissingArgumentsError):
                embed = discord.Embed(title="No active characters", description="Select your characters via `.somecommand` first!", color=bot_config.CustomColors.red)
                await ctx.reply(embed=embed, delete_after=60)
            else:
                logger.exception(f"Error when creating a game instance: {e}")
        # gm_instance.enemies[0].base_armor_set[1] = GF.Armor(6)
        
        # ? Should I port this to GameFunctions.py? 
        for enemy in gm_instance.enemies:
            ### Moved everything into constructor
            # Get average level of armor rarity (3, 4, 1 => 3)
            print(enemy.armor_rarity)
            # Calculate damage resistance rate based on element type
            # ...
            # // maybe in GF.ItemType.ElementTypeEnum.something()
            # or GF.Entity.something()  <---- This makes sense I guess
            # // or GF.Armor.something()
            print(enemy.armor_element_resistance)
            ###
        gm_instance.enemies[0].status_effects.append(GF.LethalStatusEffects.Burn(gm_instance.enemies[0], 1.25, 0))
        print(vars(gm_instance.enemies[0]))
        
        gm_instance.start_battle()
        health_bar = ProgressBar(gm_instance.enemies[0].hp, gm_instance.enemies[0].total_hp, length=10, suffix=f'| {math.ceil(gm_instance.enemies[0].hp)}/{gm_instance.enemies[0].total_hp}')
        pb_message = await ctx.reply(f"{health_bar.bar_string}")
        await asyncio.sleep(3)
        gm_instance.enemies[0].deal_damage(gm_instance.enemies[2])
        await pb_message.edit(content=f"{health_bar.update_bar(new_iteration=gm_instance.enemies[0].hp, new_suffix=f'| {math.ceil(gm_instance.enemies[0].hp)}/{gm_instance.enemies[0].total_hp}')}")

    @commands.command(aliases=['inv'])
    async def inventory(self, ctx, detailed=None):
        user = ctx.message.author

        if DF.local_checks(user) == False:
            await ctx.send(content = "You are not registered or not logged in", delete_after = 10.0)
            return
        
        if check_if_inv_exists(user) == False:
            await ctx.send("You haven't started your adventure yet. Use `adventurestart` to start")
            return
        
        nickname = get_user_by_id(user.id, ["nickname"])
        user_inventory = get_inventory(user.id)
        print(user_inventory)
        if detailed == "d" or detailed == "detailed" or detailed == "details":
            print("detailed")
            embed = discord.Embed(
                title=f"{nickname[0]['nickname']}'s Inventory", color=user.color)
            for i in user_inventory:
                item = GF.fetch_item(
                    i['item_type_id'], i["item_id"])
                item_emoji = GF.get_emoji(item[0])
        else:
            inv_string = f""
            for i in user_inventory:
                item = GF.GameItem.fetch_item(i["item_id"], i["item_type_id"])
                item_emoji = GF.GameItem.get_emoji(item.image)
                inv_string += f"**{sub_sup_text('sup', str(i['slot_id']))}**`{GF.ItemType.get_id_type_from_inventory_slot(i['item_type_id'])}_{item.id}`{item_emoji}**{sub_sup_text('sub', str(i['quantity']))}** "
            embed = discord.Embed(
                title=f"{nickname[0]['nickname']}'s Inventory", description=inv_string, color=user.color)
            await ctx.send(embed=embed)

    @commands.command()
    async def info(self, ctx, id=None):
        if id is None:
            embed = discord.Embed(
                title="Error!", description="Please, include id of an item or a character. *For example:* `info w_0`", color=discord.Color.red())
            await ctx.send(embed=embed)
        else:
            try:
                id = id.split('_')
                item_info = GF.fetch_item(
                    GF.convert_type(id[0].lower()), int(id[1]))
                print(item_info)
                item = item_info[0]
                colour = GF.get_rarity_color(item[7].lower(), mode="embed")
                if id[0] == "w":
                    emoji = GF.get_emoji(item[12])
                    emoji_split = emoji.split(':')
                    try:
                        print(emoji_split)
                        discord_emoji = discord.utils.get(
                            self.bot.emojis, name=emoji_split[1])
                        emoji_url = discord_emoji.url
                        print(emoji_url)
                    except Exception as e:
                        emoji_url = emoji_split[1]
                    embed = discord.Embed(
                        title=item[0], description=item[2], color=colour)
                    embed.set_thumbnail(url=emoji_url)
                    general_value = f'''**Rarity:** {item[7]} {GF.get_rarity_color(item[7].lower(), mode='message')}\n**Element:** {item[6]} {GF.get_element(item[6].lower())}\n**Type:** {item[8]}'''
                    embed.add_field(
                        name="General info of the weapon", value=general_value)
                    crit_info = item[13].split("|")
                    stats_value = f'''**Damage:** {item[3]}\n**Crit chance:** {crit_info[0]}%\n**Crit multiplier:** {crit_info[1]}x\n**Value = {GF.get_coins(int(item[9]))}**'''
                    embed.add_field(
                        name="Stats of the weapon", value=stats_value)
                    special_info = item[5].split('|')
                    special_value = ""
                    for i in range(0, len(special_info)):
                        special_ability_info = GF.weapon_special_ability(
                            special_info[i], item[3])
                        special_value += f'''**{special_ability_info['name']}**\n{special_ability_info['description']}\n'''
                    second_attack_info = GF.weapon_second_attack(item[4])
                    special_value += f'''\n**Second attack: {second_attack_info['name']}** \n{second_attack_info['description']}'''
                    embed.add_field(name="Special ability",
                                    value=special_value, inline=False)
                    obtain_value = GF.get_obtanation(item[10], item[11])
                    embed.add_field(name="Obtanable from", value=f'''**Crafting:** {obtain_value['craft']}\n\n**Drop:** {obtain_value['drop']}''')
                    await ctx.send(embed=embed)
                elif id[0] == "a":
                    emoji = GF.get_emoji(item[12])
                    emoji_split = emoji.split(':')
                    try:
                        discord_emoji = discord.utils.get(
                            self.bot.emojis, name=emoji_split[1])
                        emoji_url = discord_emoji.url
                    except Exception as e:
                        emoji_url = emoji_split[1]
                    embed = discord.Embed(
                        title=item[0], description=item[2], color=colour)
                    embed.set_thumbnail(url=emoji_url)
                    general_value = f'''**Rarity:** {item[7]} {GF.get_rarity_color(item[7].lower(), mode='message')}\n**Element:** {item[6]} {GF.get_element(item[6].lower())}\n**Type:** {item[4]}'''
                    embed.add_field(
                        name="General info of the armor", value=general_value)
                    ap_info = item[3].split('>')
                    stats_value = f'''**Armor Points:** {ap_info[0]}\n**Defense Percentage:** {ap_info[1]}%\n**Value = {GF.get_coins(int(item[9]))}**'''
                    embed.add_field(
                        name="Stats of the armor", value=stats_value)
                    special_info = item[5].split('|')
                    special_value = ""
                    for i in range(0, len(special_info)):
                        if i == len(special_info):
                            break
                        special_ability_info = GF.armor_special_ability(
                            special_info[i], ap_info[0])
                        special_value += f'''**{special_ability_info['name']}**\n{special_ability_info['description']}\n'''
                    set_bonus_container = item[8].split(' ')
                    set_bonus_container[0] = (
                        set_bonus_container[0].split(','))
                    set_bonus_value = ""
                    print(set_bonus_container)
                    set_bonus_info = GF.armor_set_bonus(
                        set_bonus_container[1], set_bonus_container[0], "display")
                    set_bonus_value += f'''\n**Set bonus: {set_bonus_info['name']}** \n{set_bonus_info['description']} \n\n**Armor ids in the set:** {set_bonus_info['armors']}'''
                    embed.add_field(name="Special ability",
                                    value=special_value+set_bonus_value, inline=False)
                    obtain_value = GF.get_obtanation(item[10], item[11])
                    embed.add_field(
                        name="Obtanable from", value=f'''**Crafting:** {obtain_value['craft']} \n\n**Drop:** {obtain_value['drop']}''')
                    await ctx.send(embed=embed)
            except Exception as e:
                print(traceback.format_exc())
                embed = discord.Embed(
                    title="Error!", description="This id does not exist", color=discord.Color.red())
                await ctx.send(embed=embed)

    @commands.command()
    async def give(self, ctx, item_id, quantity):
        user = ctx.message.author

        if check_exists(user) == False:
            await ctx.send("You don't have an account yet. You can register by using command `register`")
        else:
            if check_logged(user) == False:
                await ctx.send("You are logged out")
            else:
                if user.id in bot_config.admin_account_ids:
                    insert_item(user, item_id, quantity)


async def setup(bot):
    await bot.add_cog(Adventure(bot))

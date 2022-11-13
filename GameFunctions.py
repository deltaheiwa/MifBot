from dis import disco
import discord
import random
import asyncio
import json
import enum
import math
from discord.ext import commands
from discord.ui import Button
from functions import *
import creds
from get_sheets import enemies, items, weapons, armor, characters

class Rarity(enum.Enum):
    grey = 1
    white = 2
    green = 3
    blue = 4
    yellow = 5
    orange = 6
    red = 7


class Type(enum.Enum):
    fire = 1
    water = 2
    life = 3
    void = 4
    neutral = 5


def fetch_item(type_id, id):
    return_value = []
    if type_id == 1:
        return_value.append(weapons[id])
        return_value.append("w")
    elif type_id == 2:
        return_value.append(armor[id])
        return_value.append("a")
    elif type_id == 3:
        return_value.append(items[id])
        return_value.append("i")
    return return_value

def fetch_char(char_type, id):
    if char_type == 'e':
        return enemies[id]
    elif char_type == 'c':
        return characters[id]

def get_emoji(item_emoji):
    if item_emoji == "-" or item_emoji == "":
        emoji = "<:Question_Mark_fixed:944588141405282335>"
    else:
        emoji = item_emoji
    return emoji

def convert_type(type_id):
    if type(type_id) == type('a'):
        if type_id == 'w': return 1
        elif type_id == 'a': return 2
        elif type_id == 'i': return 3
        else: return False
    elif type(type_id) == type(1):
        if type_id == 1: return 'w'
        elif type_id == 2:return 'a'
        elif type_id == 3: return 'i'
        else: return False
    else: return False

def enemy_spawner(enemy_ids):
    enemies_id = enemy_ids.split(',')
    enemy = []
    for id in enemies_id:
        enemy.append(enemies[int(id)])
    return enemy

def armor_check(enemy):
    return_armor = []
    if enemy[6] == "-":
        return None
    else:
        armor_ids = enemy[6].split(', ')
        for id in armor_ids:
            return_armor.append(armor[int(id)])
        return return_armor
    

def armor_points(armors):
    points = 0
    for obj in armors:
        points += obj[3]
    return points


def weapon_check(enemy):
    if enemy[6] == "-":
        return None
    else:
        return weapons[int(enemy[6])]

def define_rarity_armor(armors):
    num = 0
    container = []
    for obj in armors:
        rarity = obj[6].lower()
        if rarity == "grey": container.append(Rarity.grey.value)
        elif rarity == "white": container.append(Rarity.white.value)
        elif rarity == "yellow": container.append(Rarity.yellow.value)
        elif rarity == "blue": container.append(Rarity.blue.value)
        elif rarity == "green": container.append(Rarity.green.value)
        elif rarity == "orange": container.append(Rarity.orange.value)
        elif rarity == "red": container.append(Rarity.red.value)
    for i in container:
        num += i
    num = num / len(container)
    return num

def get_rarity_color(rarity, mode):
    if mode == "embed":
        if rarity == "grey":
            return discord.Color.from_rgb(220, 220, 220)
        elif rarity == "white":
            return discord.Color.from_rgb(255, 255, 255)
        elif rarity == "yellow":
            return discord.Color.yellow()
        elif rarity == "blue":
            return discord.Color.blue()
        elif rarity == "green":
            return discord.Color.green()
        elif rarity == "orange":
            return discord.Color.orange()
        elif rarity == "red":
            return discord.Color.red()
    elif mode == "message": 
        if rarity == "grey":
            return "<:gray_rarity:945418409410166784>"
        elif rarity == "white":
            return ":white_circle:"
        elif rarity == "yellow":
            return ":yellow_circle:"
        elif rarity == "blue":
            return ":blue_circle:"
        elif rarity == "green":
            return ":green_circle:"
        elif rarity == "orange":
            return ":orange_circle:"
        elif rarity == "red":
            return ":red_circle:"

def get_element(element):
    if element == "fire":
        return "<:fireEmblem:927711447537049611>"
    elif element == "life":
        return "<:lifeEmblem:927721601464692776>"
    elif element == "water":
        return "<:waterEmblem:927711447956463676>"
    elif element == "void":
        return "<:voidEmblem:927726580275503164>"
    elif element == "neutral":
        return "<:neutralEmblem:927728956680048660>"

def get_coins(value):
    if value/10000 >= 1:
        mcoins = f"{math.floor(value/10000)}**M** "
        if value/10000 - math.floor(value/10000) != 0:
            wcoins_value = math.floor((value/10000 - math.floor(value/10000))*100)
            wcoins = f"{wcoins_value}**W** "
            if wcoins_value/100 - math.floor(wcoins_value/100) != 0:
                fcoins = f"{round((value/100 - math.floor(value/100))*100)}**F** "
            else:
                fcoins = ""
        else:
            fcoins = ""
            wcoins = ""
    else:
        if value/100 >= 1:
            mcoins=""
            wcoins = f"{math.floor(value/100)}**W** "
            if value/100 - math.floor(value/100) != 0:
                fcoins = f"{round((value/100 - math.floor(value/100))*100)}**F** "
            else:
                fcoins = ""
        else:
            if value/100 < 1:
                mcoins=""
                wcoins=""
                fcoins = f"{value}**F** "
            else:
                mcoins = ""
                fcoins = ""
                wcoins = ""
    if mcoins+wcoins+fcoins == "": return "No value"
    else: return mcoins+wcoins+fcoins

def weapon_special_ability(ability_code, damage):
    ability_info = {}
    if ability_code == "fire_effect":
        ability_info['name'] = "Sets on fire"
        ability_info['description'] = (f"Sets an enemy on fire with a 65% chance with each attack. Lasts 2 turns. Deals **{round(int(damage)/100*20)}** damage each turn")
    elif ability_code == "-" or ability_code == "":
        ability_info['name'] = "No special ability"
        ability_info['description'] = "This weapon has no special ability"
    
    return ability_info

def armor_special_ability(ability_code, armor_points):
    ability_info = {}
    if ability_code == "-" or ability_code == "":
        ability_info['name'] = "No special ability"
        ability_info['description'] = "This armor has no special ability"
    elif ability_code == "ranged_lowered_50":
        ability_info['name'] = "Received ranged damage lowered"
        ability_info['description'] = "Reduces damage taken from ranged weapons by 50%"
    
    return ability_info

def weapon_second_attack(attack):
    attack_info = {}
    if attack == "-" or attack == "":
        attack_info['name'] = "No second attack"
        attack_info['description'] = "This weapon has no second attack"
    
    return attack_info

def armor_set_bonus(set_code, armor_ids, mode):
    set_bonus_info = {}
    armors = ""
    for each_id in armor_ids:
        armors += f"`a_{each_id}` "
    if mode == "display":
        if set_code == "-" or set_code == "":
            set_bonus_info['name'] = "No set bonus"
            set_bonus_info['description'] = "This piece of armor has no set bonus, all you get for wearing full set - extra `Armor Points`"
            set_bonus_info['armors'] = armors
        else:
            if set_code == "open_space_air":
                set_bonus_info["name"] = "Ability to breathe in outer space"
                set_bonus_info["description"] = "Your character won't receive damage in outer space"
                set_bonus_info['armors'] = armors
    
    return set_bonus_info



def get_obtanation(craft, drop):
    obtanation = {}
    if craft == "-" or craft == "":
        obtanation['craft'] = "Not craftable"
    else:
        craft_string = ""
        craft = craft.split(', ')
        for i in range(0, len(craft)):
            if i == len(craft): break
            quantity = craft[i].split("*")
            item = quantity[0].split("_")
            item_info = fetch_item(convert_type(item[0]), int(item[1]))
            item_emoji = get_emoji(item_info[0])
            try:
                quantity = quantity[1]
            except Exception:
                quantity.append(1)
            craft_string += f"`{quantity[0]}`{item_emoji}** x{quantity[1]}**  "
        obtanation['craft'] = craft_string
    
    if drop == "-" or drop == "":
        obtanation['drop'] = "Cannot be obtained from enemies nor found"
    else:
        drop_string = ""
        drop = drop.split(', ')
        for i in range(0, len(drop)):
            if i == len(drop):
                break
            source = drop[i].split("_")
            if source[0] == 'e':
                source_info = fetch_char(source[0], int(source[1]))
            drop_string += f"`{drop[i]}` - {source_info[0]}\n"
        obtanation['drop'] = drop_string
    
    return obtanation

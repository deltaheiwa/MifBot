# from flask import Flask
# from flask import render_template
# from flask_sqlalchemy import SQLAlchemy
import asyncio
import datetime
import json
import math
import random
import re as re
import traceback
import urllib.request
import coloredlogs
from datetime import datetime as datetimefix
from io import BytesIO
from locale import normalize
from pathlib import Path
import calendar
import colorama as cl
import discord
import orm
import pymysql
import requests
import sqlalchemy as sa
from discord.ext import commands
from PIL import Image, ImageChops, ImageDraw, ImageFont
import time
import creds
import logging
from functools import wraps
from sqlite_data import database_main
import config
from functools import lru_cache
import gc


logger_deb = logging.getLogger(__name__+"debug")
logger_deb.setLevel(logging.DEBUG)
formatter = logging.Formatter('%(asctime)s:%(levelname)s --- %(message)s')
file_handler_debug = logging.FileHandler(config.functions_log_debug)
file_handler_debug.setFormatter(formatter)
logger_deb.addHandler(file_handler_debug)

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
file_handler = logging.FileHandler(config.functions_log)
file_handler.setFormatter(formatter)
logger.addHandler(file_handler)



class bcolors:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKCYAN = '\033[96m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'

class CustomFormatter(logging.Formatter):

    grey = "\x1b[38;20m"
    yellow = "\x1b[33;20m"
    red = "\x1b[31;20m"
    bold_red = "\x1b[31;1m"
    reset = "\x1b[0m"
    format = "%(asctime)s - %(name)s - %(levelname)s - %(message)s (%(filename)s:%(lineno)d)"

    FORMATS = {
        logging.DEBUG: grey + format + reset,
        logging.INFO: grey + format + reset,
        logging.WARNING: yellow + format + reset,
        logging.ERROR: red + format + reset,
        logging.CRITICAL: bold_red + format + reset
    }

    def format(self, record):
        log_fmt = self.FORMATS.get(record.levelno)
        formatter = logging.Formatter(log_fmt)
        return formatter.format(record)

console_formatter = CustomFormatter()
stream_handler = logging.StreamHandler()
stream_handler.setFormatter(console_formatter)
coloredlogs.install(level='INFO', logger=logger)

async def determine_prefix(client, message):
    if not message.guild:
        return "."
    else:
        prefix = await database_main.return_prefix(message.guild.id)
        return prefix

baseboard_map = {'p': '♟', 'P': '♙', 'k': '♚', 'K': '♔', 'q': '♛',
                 'Q': '♕', 'r': '♜', 'R': '♖', 'b': '♝', 'B': '♗', 'n': '♞', 'N': '♘'}

board_trans = str.maketrans(''.join(baseboard_map.keys()),
                            ''.join(baseboard_map.values()))

# engine_db = None
# def run_db():
#     try:
#         global engine_db
#         engine_db = sa.create_engine(f"mysql+pymysql://{creds.user}:{creds.password}@{creds.host}:3306/{creds.db_name}")
#         print("success")
#     except Exception as e:
#         print(traceback.format_exc())


def chess_pieces_visualizator(symbol):
    '''
    Takes a piece letter from 'python chess' board, and transposes it into an emoji
    '''
    translated = symbol.translate(board_trans)
    rows = translated.split('\n')
    symbol_matrix = []
    for each_row in rows:
        symbols = each_row.split(' ')
        for each in symbols:
            symbol_matrix.append(each)
    color_toggle = True
    insertpoint = 8
    for i in range(8):
        symbol_matrix.insert(insertpoint*i+i, '\n')
    del symbol_matrix[0]
    for uni in symbol_matrix:
        if uni == '.':
            if color_toggle == True:
                symbol_matrix[symbol_matrix.index(uni)] = '\u25fb'
            else:
                symbol_matrix[symbol_matrix.index(uni)] = '\u25fc'
        color_toggle = not color_toggle
    return "".join(symbol_matrix)


superscript_map = {
    "0": "⁰", "1": "¹", "2": "²", "3": "³", "4": "⁴", "5": "⁵", "6": "⁶",
    "7": "⁷", "8": "⁸", "9": "⁹", "a": "ᵃ", "b": "ᵇ", "c": "ᶜ", "d": "ᵈ",
    "e": "ᵉ", "f": "ᶠ", "g": "ᵍ", "h": "ʰ", "i": "ᶦ", "j": "ʲ", "k": "ᵏ",
    "l": "ˡ", "m": "ᵐ", "n": "ⁿ", "o": "ᵒ", "p": "ᵖ", "q": "۹", "r": "ʳ",
    "s": "ˢ", "t": "ᵗ", "u": "ᵘ", "v": "ᵛ", "w": "ʷ", "x": "ˣ", "y": "ʸ",
    "z": "ᶻ", "A": "ᴬ", "B": "ᴮ", "C": "ᶜ", "D": "ᴰ", "E": "ᴱ", "F": "ᶠ",
    "G": "ᴳ", "H": "ᴴ", "I": "ᴵ", "J": "ᴶ", "K": "ᴷ", "L": "ᴸ", "M": "ᴹ",
    "N": "ᴺ", "O": "ᴼ", "P": "ᴾ", "Q": "Q", "R": "ᴿ", "S": "ˢ", "T": "ᵀ",
    "U": "ᵁ", "V": "ⱽ", "W": "ᵂ", "X": "ˣ", "Y": "ʸ", "Z": "ᶻ", "+": "⁺",
    "-": "⁻", "=": "⁼", "(": "⁽", ")": "⁾"}

trans = str.maketrans(
    ''.join(superscript_map.keys()),
    ''.join(superscript_map.values()))

subscript_map = {
    "0": "₀", "1": "₁", "2": "₂", "3": "₃", "4": "₄", "5": "₅", "6": "₆",
    "7": "₇", "8": "₈", "9": "₉", "a": "ₐ", "b": "♭", "c": "꜀", "d": "ᑯ",
    "e": "ₑ", "f": "բ", "g": "₉", "h": "ₕ", "i": "ᵢ", "j": "ⱼ", "k": "ₖ",
    "l": "ₗ", "m": "ₘ", "n": "ₙ", "o": "ₒ", "p": "ₚ", "q": "૧", "r": "ᵣ",
    "s": "ₛ", "t": "ₜ", "u": "ᵤ", "v": "ᵥ", "w": "w", "x": "ₓ", "y": "ᵧ",
    "z": "₂", "A": "ₐ", "B": "₈", "C": "C", "D": "D", "E": "ₑ", "F": "բ",
    "G": "G", "H": "ₕ", "I": "ᵢ", "J": "ⱼ", "K": "ₖ", "L": "ₗ", "M": "ₘ",
    "N": "ₙ", "O": "ₒ", "P": "ₚ", "Q": "Q", "R": "ᵣ", "S": "ₛ", "T": "ₜ",
    "U": "ᵤ", "V": "ᵥ", "W": "w", "X": "ₓ", "Y": "ᵧ", "Z": "Z", "+": "₊",
    "-": "₋", "=": "₌", "(": "₍", ")": "₎"}


sub_trans = str.maketrans(
    ''.join(subscript_map.keys()),
    ''.join(subscript_map.values()))


def sub_sup_text(type, text):
    '''
    Converts a text into subscript or superscript. Use "sub" for subscript and "sup" for superscript
    '''
    if type == "sub":
        return text.translate(sub_trans)
    elif type == "sup":
        return text.translate(trans)

@lru_cache(maxsize=None)
def coins_formula(day):
    # * y=x^(((1)/(2))) (((7)/(3)))^(((x)/(10 x))+2)
    coins_bonus = day**(1/2) * (7/3)**(day/(10*day)+2)
    coins_bonus = (day+random.randint(9,11)) * coins_bonus
    # // logger.debug(f"{round(coins_bonus)} day:{day}. GF: {GF.get_coins(round(coins_bonus))}" )
    return coins_bonus

def percentage_calc(full_value: int, percentage: int):
    '''Calculates percentage of the given value

    Args:
        full_value (int): Ful value to calculate the percentage of
        percentage (int): Percentage itself

    Returns:
        float: Part of the full value by percentage
    
    Extras:
        Returns '0.00' if full value is 0
    '''
    if full_value == 0:
        return 0.00
    return percentage * 100 / full_value

def repeating_symbols(text) -> bool:
    '''
    Checks if some symbols were repeated in the text. Returns True or False
    '''
    for i in range(len(text)):
        if i != text.rfind(text[i]):
            return True
    return False

def timestamp_calculate(objT, type_of_format: str):
    '''
    Types of format:
        Creation Date - 06/12/2018, 09:55:22
        Recent Date - Monday, Mar 21 2022, 13:31:09
        Light Date - Mar 21 2022, 13:31:09

    '''
    if type(objT) == str:
        try:
            date_obj = datetimefix.strptime(
                objT, "%Y-%m-%dT%H:%M:%S.%fZ")
        except:
            date_obj = datetimefix.strptime(objT, "%Y-%m-%d %H:%M:%S")
    else: date_obj = objT
    try:
        date_str = date_obj.strftime(
            "%Y-%m-%dT%H:%M:%SZ")
    except:
        date_str = date_obj.strftime(
            "%Y-%m-%d %H:%M:%S")
    try:
        epoch = calendar.timegm(time.strptime(
            date_str, '%Y-%m-%dT%H:%M:%SZ'))
    except:
        epoch = calendar.timegm(time.strptime(
            date_str, '%Y-%m-%d %H:%M:%S'))
    if type_of_format == "Creation Date":
        complete = str(time.strftime(
            '%m/%d/%Y, %H:%M:%S', time.gmtime(epoch)))
    elif type_of_format == "Recent Date":
        complete = str(time.strftime(
            '%A, %b %d %Y, %H:%M:%S', time.gmtime(epoch)))
    elif type_of_format == "Light Date":
        complete = str(time.strftime(
            '%b %d %Y, %H:%M:%S', time.gmtime(epoch)))
    elif type_of_format == "Only Date":
        complete = str(time.strftime(
            '%b %d, %H:00', time.gmtime(epoch)))
    return complete

async def wov_api_call(name_id: str, req_info = "user", by_id = False):
    '''Sends an API call to the Wolvesville API

    Args:
        name_id (str): Username/Clan name/id
        req_info (str, optional): Request for "user", "clan", "clan_members", "shop"). Anything else will raise an exception. Defaults to "user".
        by_id (bool, optional): True to search by id. Defaults to False.

    Returns:
        JSON or None: Returns a response object containing JSON. Returns None if user or clan is not found.
    
    Extras:
        "clan_members" requires "by_id" to be True
    '''
    headers = {"Authorization": f"Bot {creds.WOV_API_TOKEN}"}
    api_url = "https://api.wolvesville.com/"
    if by_id is False:
        match req_info:
            case "user":
                response = requests.get(url = api_url+f"/players/search?username={name_id}", headers=headers)
            case "clan":
                response = requests.get(url = api_url+f"/clans/search?name={name_id}", headers=headers)
            case "shop":
                response = requests.get(url = api_url+f"/shop/activeOffers", headers=headers)
            case _: raise AttributeError(f"Invalid request type: {req_info}")
    else:
        match req_info:
            case "user":
                response = requests.get(url = api_url+f"/players/{name_id}", headers=headers)
            case "clan":
                response = requests.get(url = api_url+f"/clans/{name_id}/info", headers=headers)
            case "clan_members":
                response = requests.get(url = api_url+f"/clans/{name_id}/members", headers=headers)
            case _: raise AttributeError(f"Invalid request type: {req_info}")
    if response.status_code == 404:
        return None
    return response.json()


def cache_check(what_to_search: str, type_of_search: str, name: str):
    '''
    Returns T or F based on if data exists in cache or no
    \nwhat_to_search: user, clan, clan_members
    \ntype_of_search - by the name of the column
    '''
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
                # SELECT 'email' COLLATE utf8_bin = 'Email'
                if what_to_search == "user":
                    select_query = f"SELECT id FROM wov_players WHERE {type_of_search} COLLATE utf8mb4_bin LIKE '{name}%';"
                elif what_to_search == "clan": select_query = f"SELECT id FROM wov_clans WHERE {type_of_search} = '{name}';"
                elif what_to_search == "clan_members": select_query = f"SELECT members FROM wov_clans WHERE id = '{name}';"
                cursor.execute(select_query)
                check = cursor.fetchone()
                if type(check) == dict:
                    for key in check:
                        if check[key] is not None:
                            return True
                        else:
                            return False
                else:
                    if check is not None:
                        return True
                    else:
                        return False
        finally:
            connection.close()
    except Exception as e:
        print(traceback.print_exception(e))
        print("Connection refused...")
        print(e)

def json_caching(cache_type, json_data, extra_data=None):
    '''
    Accepts json data from Wolvesville API, to update the cache
    \ncache_type: user, clan, clan_members
    '''
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
            cache_file = {}
            if cache_type == "user":
                cache_file[f"{json_data['username']}"] = json_data
                time_cached = datetimefix.utcnow()
                iso = time_cached.isoformat() + "Z"
                cache_file[f"{json_data['username']}"]['caching_data'] = {}
                cache_file[f"{json_data['username']}"]['caching_data']['time_cached'] = str(iso)
                with connection.cursor() as cursor:
                    select_query = f"SELECT id, username FROM wov_players WHERE id = '{json_data['id']}'"
                    cursor.execute(select_query)
                    check = cursor.fetchone()
                bio = ""
                try:
                    if json_data['personalMessage'] == bio:
                        bio = "*No personal message found*"
                    else: bio = json_data['personalMessage']
                except KeyError:
                    bio = "*No personal message found*"
                bio = re.sub('"', '\\"', bio)
                
                del cache_file[f"{json_data['username']}"]['personalMessage']
                json_cache_file = str(json.dumps(cache_file))
                
                if check is not None:
                    if check['username'] != json_data['username']:
                        cache_file[json_data['username']]['caching_data']['previous_username'] = check['username']
                        json_cache_file = str(json.dumps(cache_file))
                    with connection.cursor() as cursor:
                        update_query = f'''UPDATE wov_players SET username = '{json_data['username']}', json_data = '{json_cache_file}', personal_message = "{bio}" WHERE id = '{json_data['id']}';'''
                        cursor.execute(update_query)
                        connection.commit()
                        print("Updated successfully")
                else:
                    with connection.cursor() as cursor:
                        update_query = f'''INSERT INTO wov_players (id, username, personal_message, json_data) VALUES ('{json_data['id']}', '{json_data['username']}', "{bio}", '{json_cache_file}');'''
                        print(update_query)
                        cursor.execute(update_query)
                        connection.commit()
                        print("Inserted successfully")
            elif cache_type == "clan":
                cache_file[json_data['id']] = json_data
                clan_description = json_data['description']
                clan_description = re.sub('"', '\\"', clan_description)
                cache_file[json_data['id']].pop('description')
                time_cached = datetimefix.utcnow()
                iso = time_cached.isoformat() + "Z"
                cache_file[json_data['id']]['caching_data'] = {}
                cache_file[json_data['id']]['caching_data']['time_cached'] = str(iso)
                json_cache_file = str(json.dumps(cache_file))
                with connection.cursor() as cursor:
                    select_query = f"SELECT id, name FROM wov_clans WHERE id = '{json_data['id']}'"
                    cursor.execute(select_query)
                    check = cursor.fetchone()
                
                if check is not None:
                    with connection.cursor() as cursor:
                        update_query = f'''UPDATE wov_clans SET name = '{json_data['name']}', json_data = '{json_cache_file}' WHERE id = '{json_data['id']}';'''
                        cursor.execute(update_query)
                        connection.commit()
                        print("Updated successfully")
                else:
                    with connection.cursor() as cursor:
                        update_query = f'''INSERT INTO wov_clans (id, name, json_data, description) VALUES ('{json_data['id']}', '{json_data['name']}', '{json_cache_file}', "{clan_description}");'''
                        print(update_query)
                        cursor.execute(update_query)
                        connection.commit()
                        print("Inserted successfully")
            elif cache_type == "clan_members":
                json_cache_file = str(json.dumps(json_data))
                
                with connection.cursor() as cursor:
                    update_query = f'''UPDATE wov_clans SET members = '{json_cache_file}' WHERE id = '{extra_data}';'''
                    cursor.execute(update_query)
                    connection.commit()
                    print("Updated successfully")
        finally:
            connection.close()
    except Exception as e:
        print("Connection refused...")
        print(traceback.format_exc())

def history_caching(json_data):
    with open(Path('Wov Cache', 'old_player_cache.json'), "r") as js_f:
        cache_file = json.load(js_f)
    
    if json_data['id'] not in cache_file:
        cache_file[json_data['id']] = {}
    cache_file[json_data['id']][json_data['caching_data']['time_cached']] = json_data

    with open(Path('Wov Cache', 'old_player_cache.json'), "w") as js_f:
        json.dump(cache_file, js_f, indent=4)

def level_rank(level):
    if level < 420:
        rank = math.floor(level/10+1)
        if rank < 10:
            return f"0{rank}"
        else:
            return math.floor(level/10+1)
    elif 420 <= level < 1000:
        if level < 500: return 43
        elif level < 600: return 44
        elif level < 700: return 45
        elif level < 800: return 46
        elif level < 900: return 47
        elif level < 1000: return 48
    else: return "last"

def round_edges(im, radius):
    mask = Image.new("L", (radius * 2, radius * 2), 0)
    draw = ImageDraw.Draw(mask)
    draw.ellipse((0, 0, radius * 2, radius * 2), fill = 255)
    alpha = Image.new("L", im.size, 255)
    w, h, = im.size
    alpha.paste(mask.crop((0, 0, radius, radius)), box=(0,0))
    alpha.paste(mask.crop((0, radius, radius, radius*2)), box=(0, h - radius))
    alpha.paste(mask.crop((radius, 0, radius*2, radius)), box=(w-radius, 0))
    alpha.paste(mask.crop((radius, radius, radius*2, radius*2)), box=(w-radius, h - radius))

    im.putalpha(alpha)
    return im


async def avatar_rendering(image_URL, level=None, rank=True):
    '''
    This one is fked up
    '''
    av_bg = Image.open(Path('Images', 'wolvesville_small_night_AVATAR.png')).convert("RGBA")
    # urllib.request.urlretrieve(image_URL)
    url_response = requests.get(image_URL)
    avatar = Image.open(BytesIO(url_response.content)).convert("RGBA")
    lvlfont = ImageFont.truetype('Fonts/OpenSans-Bold.ttf', 12)
    one_ts_lvl_font = ImageFont.truetype('Fonts/OpenSans-Bold.ttf', 10)
    width_bg, height_bg = av_bg.size
    width_av, height_av = avatar.size
    # left, upper, right, lower
    box = []
    color_bg = Image.new(mode="RGBA", size=(width_bg, height_bg), color=(78, 96, 120))
    if width_av > width_bg:
        diff = width_av - width_bg
        box.append(diff/2)
        box.append(width_av-diff/2)
    else:
        box.append(0)
        box.append(width_av)
    if height_av > height_bg:
        diff = height_av - height_bg
        box.append(height_av-diff)
        box.insert(1, 0)
    else:
        box.append(height_av)
        box.insert(1, 0)
    cropped_avatar = avatar.crop(tuple(box))
    ca_width, ca_height = cropped_avatar.size
    insert_box = [math.floor((width_bg - ca_width)/2), height_bg-ca_height, width_bg - math.floor((width_bg - ca_width)/2), height_bg]
    if insert_box[2]-insert_box[0] < ca_width or insert_box[2]>ca_width and insert_box[0] == 0: insert_box[0] += 1
    elif insert_box[2]-insert_box[0] > ca_width: insert_box[2] -= 1
    av_bg.paste(cropped_avatar, tuple(insert_box), cropped_avatar)
    color_bg.paste(av_bg, (0,0), av_bg)
    if rank is True:
        rank_icon = Image.open(Path('Images/ranks', f'rank_{level_rank(level)}.png')).convert('RGBA')
        rank_width, rank_height = rank_icon.size
        resized_dimensions = (int(rank_width * 0.25), int(rank_height * 0.25))
        resized_rank = rank_icon.resize(resized_dimensions)
        draw = ImageDraw.Draw(resized_rank)
        if int(level) < 10:
            draw.text((15, 10), text=str(level), font=lvlfont, fill='white', stroke_width=1, stroke_fill=(214, 214, 214))
        elif int(level) >= 10 and int(level) < 100:
            draw.text((11, 10), text=str(level), font=lvlfont, fill='white', stroke_width=1, stroke_fill=(214, 214, 214))
        elif int(level) >= 100 and int(level) < 1000:
            draw.text((9, 10), text=str(level), font=lvlfont, fill='white', stroke_width=1, stroke_fill=(214, 214, 214))
        elif int(level) >= 1000 and int(level) < 10000:
            draw.text((7, 11), text=str(level), font=one_ts_lvl_font, fill='white', stroke_width=1, stroke_fill=(214, 214, 214))
        else:
            draw.text((5, 11), text=str(level), font=one_ts_lvl_font, fill='white')
        color_bg.paste(resized_rank, (100, 10), resized_rank)
        rank_icon.close()
    color_bg = round_edges(color_bg, 15)
    av_bg.close(), avatar.close()
    
    return color_bg

async def all_avatars_rendering(avatars: list, urls: list):
    main_avatars = avatars
    avatars_copy = avatars.copy()
    avatar_dict = {'queue': urls}
    for av in urls:
        if av not in avatar_dict:
            avatar_dict[f'{av}'] = avatars_copy[0]
            avatars_copy.pop(0)
    amount_of_avatars = len(urls)
    last_row_avatars = amount_of_avatars % 3
    amount_of_rows = math.ceil(amount_of_avatars / 3)
    av_w, av_h = main_avatars[0].size
    main_height = (av_h+10)*amount_of_rows+50
    main_width = av_w*3+60
    logger_deb.debug(f"Avatars last row: {last_row_avatars}. Amount of rows: {amount_of_rows}. Main width/height: {main_width}/{main_height}")
    image_font = ImageFont.truetype('Fonts/OpenSans-Bold.ttf', 20)
    color_bg = Image.new(mode="RGBA", size=(main_width, main_height), color=(66, 66, 66))
    draw = ImageDraw.Draw(color_bg)
    draw.text((15, 15), text="Avatars", font=image_font, fill='white')
    if last_row_avatars == 0: v = 0
    else: v = 1
    for row in range(amount_of_rows-1*v):
        for i in range(0, 3):
            color_bg.paste(avatar_dict[urls[i+3*row]], (20+(av_w+10)*i, 50+(10+av_h)*row), avatar_dict[urls[i]])
    upper_1 = 50+(10+av_h)*(amount_of_rows-1)
    match last_row_avatars:
        case 2: # if two avatars on the last row
            for i in range(2):
                left_1 = 20+round(av_w/3)*(1*(i+1))+(av_w)*i
                color_bg.paste(avatar_dict[urls[-1*(i+1)]], (left_1, upper_1), avatar_dict[urls[i]])
                logger_deb.debug(f"left: {left_1}, upper: {upper_1}")
        case 1: # if one avatars on the last row
            left_2 = 20+(av_w+10)
            color_bg.paste(avatar_dict[urls[-1]], (left_2, upper_1), avatar_dict[urls[i]])
            logger_deb.debug(f"left: {left_2}, upper: {upper_1}")
        case _: # if three avatars on the last row
            pass
    
    return color_bg



def on_new_player(member, info: list):
    '''
    Inserts user and user_data objects into the SQL database
    '''
    statDict = {
        "botUsage": {
            "commandsUsed": 0,
            "ngWins": {
                "easy": 0,
                "medium": 0,
                "hard": 0
            },
            "hangman": {
                "Wins": 0,
                "Losses": 0
            },
            "bulls": {
                "word": {
                    "wins": 0,
                    "losses": 0
                },
                "number": {
                    "wins": 0,
                    "losses": 0
                },
                "pfb": {
                    "fast": {
                        "wins": 0,
                        "losses": 0,
                        "abandoned": 0
                    },
                    "classic": {
                        "wins": 0,
                        "losses": 0,
                        "abandoned": 0
                    },
                    "hard": {
                        "wins": 0,
                        "losses": 0,
                        "abandoned": 0
                    },
                    "long": {
                        "wins": 0,
                        "losses": 0,
                        "abandoned": 0
                    }
                }
            },
            "dailyInfo": {
                "dailyCount": 0,
                "lastDailyTime": None
            }
        }
    }
    try:
        connection = pymysql.connect(
            host=creds.host,
            port=3306,
            user=creds.user,
            password=creds.password,
            database=creds.db_name,
            cursorclass=pymysql.cursors.DictCursor
        )
        logger.info("Connection succeeded in \"on_new_player()\".")
        try:
            with connection.cursor() as cursor:
                insert_query = f"INSERT INTO users (id, login, password, nickname, is_logged, atc) VALUES ('{member.id}', '{info[0]}', '{info[1]}', '{info[2]}', TRUE, TRUE);"
                cursor.execute(insert_query)
                connection.commit()
                logger.info("Inserted user into 'users' table")
            
            json_stats = str(json.dumps(statDict))

            with connection.cursor() as cursor:
                insert_query = f'''INSERT INTO user_data (user_id, cash, level, xp, max_xp, bg, json_stats) VALUES ('{member.id}', 50, 1, 0, 100, 0, '{json_stats}');'''
                cursor.execute(insert_query)
                connection.commit()
                logger.info("Inserted user into 'user_data' table")
        finally:
            connection.close()
    except Exception as e:
        logger.exception("Connection refused...")


def on_login(id):
    '''
    Updates is_logged parameter to True
    '''
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
            with connection.cursor() as cursor:
                update_query = f"UPDATE users SET is_logged = TRUE WHERE id = '{id}'"
                cursor.execute(update_query)
                connection.commit()
                print("Updated successfully")
        finally:
            connection.close()
    except Exception as e:
        print("Connection refused...")
        print(e)

# def temp_personal(id, personal_message):
#     '''
#     Updates is_logged parameter to True
#     '''
#     try:
#         connection = pymysql.connect(
#             host=creds.host,
#             port=3306,
#             user=creds.user,
#             password=creds.password,
#             database=creds.db_name,
#             cursorclass=pymysql.cursors.DictCursor
#         )
#         print("Connection succeded")
#         print("#"*20)
#         try:
#             personal_message = re.sub('"', '\\"', personal_message)
#             with connection.cursor() as cursor:
#                 update_query = f'''UPDATE wov_players SET personal_message = "{personal_message}" WHERE id = "{id}";'''
#                 cursor.execute(update_query)
#                 connection.commit()
#                 print("Updated successfully")
#         finally:
#             connection.close()
#     except Exception as e:
#         print("Connection refused...")
#         print(e)

def insert_json(json_to_insrt, table):
    '''
    json_game = {
        "meta": {
            "players": {
                "player1": {
                    "user_id": 1231434545321345, 
                    "number": 3750
                    },
                "player2": {
                    "user_id": 423456998921122, 
                    "number": 8721
                    }
            },
            "datetime_started": f"{utcnow}",
            "state": "Finished/Abandoned. {player}",
            "duration": f"{datetime_started - utcnow}",
        },
        "game": {
            "turn1": {}
        }
    }
    '''
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
            if table == "bulls_records":
                players = {"player1": None, "player2": None, "player3": None, "player4": None}
                for player_num in json_to_insrt["meta"]["players"]:
                    u_id = json_to_insrt["meta"]["players"][player_num]["user_id"]
                    players[player_num] = int(u_id)
                for player in players:
                    if players[player] == None:
                        players[player] = "NULL"
                state = json_to_insrt["meta"]["state"].split(" ")
                player_won = int(state[1])
                json_to_insrt['meta']['datetime_started'] = json_to_insrt['meta']['datetime_started'].isoformat()
                json_to_insrt['meta']['duration'] = json_to_insrt['meta']['duration'].total_seconds()
                json_g = str(json_to_insrt)
                json_g = json_g.replace("'", '"')
                with connection.cursor() as cursor:
                    insert_query = f"INSERT INTO {table} (user_1, user_2, user_3, user_4, player_won, json_game) VALUES ({players['player1']}, {players['player2']}, {players['player3']}, {players['player4']}, {player_won}, '{json_g}');"
                    print(insert_query)
                    cursor.execute(insert_query)
                    connection.commit()
                    print("JSON inserted successfully")
        finally:
            connection.close()
    except Exception as e:
        print("Connection refused...")
        print(e)

def on_logout(id):
    '''
    Updates is_logged parameter to False
    '''
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
            with connection.cursor() as cursor:
                update_query = f"UPDATE users SET is_logged = FALSE WHERE id = {id};"
                cursor.execute(update_query)
                connection.commit()
                print("Updated successfully")
        finally:
            connection.close()
    except Exception as e:
        print("Connection refused...")
        print(e)


def pretty_date(time, time_utc = True):
    '''
    Get a datetime object or a int() Epoch timestamp and return a
    pretty string like 'an hour ago', 'Yesterday', '3 months ago',
    'just now', etc
    '''
    try:
        time = time.replace(tzinfo=None)
    except:
        pass
    if time_utc:
        now = datetimefix.utcnow()
    else: now = datetimefix.now()
    if type(time) is int:
        diff = now - datetime.date.fromtimestamp(time)
    elif isinstance(time, datetimefix):
        diff = now - time
    elif not time:
        diff = now - now
    else:
        time = time[:-1]
        dt = datetimefix.fromisoformat(time)
        diff = now - dt
    second_diff = diff.seconds
    day_diff = diff.days

    if day_diff < 0:
        return ''

    if day_diff == 0:
        if second_diff < 10:
            return "just now"
        if second_diff < 60:
            return str(round(second_diff)) + " seconds ago"
        if second_diff < 120:
            return "a minute ago"
        if second_diff < 3600:
            return str(round(second_diff / 60)) + " minutes ago"
        if second_diff < 7200:
            return "an hour ago"
        if second_diff < 86400:
            return str(round(second_diff / 3600)) + " hours ago"
    if day_diff == 1:
        return "Yesterday"
    if day_diff < 7:
        return str(round(day_diff)) + " days ago"
    if day_diff < 14:
        return "a week ago"
    if day_diff < 31:
        return str(round(day_diff / 7)) + " weeks ago"
    if day_diff < 60:
        return "a month ago"
    if day_diff < 365:
        return str(round(day_diff / 30)) + " months ago"
    if day_diff < 730:
        return "a year ago"
    return str(round(day_diff / 365)) + " years ago"

def pretty_time_delta(seconds):
    sign_string = '-' if seconds < 0 else ''
    seconds = abs(int(seconds))
    days, seconds = divmod(seconds, 86400)
    hours, seconds = divmod(seconds, 3600)
    minutes, seconds = divmod(seconds, 60)
    if days > 0:
        return '%s%dd %dh %dm %ds' % (sign_string, days, hours, minutes, seconds)
    elif hours > 0:
        return '%s%dh %dm %ds' % (sign_string, hours, minutes, seconds)
    elif minutes > 0:
        return '%s%dm %ds' % (sign_string, minutes, seconds)
    else:
        return '%s%ds' % (sign_string, seconds)


def on_nickname_change(id: int, nickname: str):
    '''
    Updates nickname of a user. Takes discord.Member.id as an id. For example 'ctx.author.id'
    '''
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
            with connection.cursor() as cursor:
                update_query = f'UPDATE users SET nickname = "{nickname}" WHERE id = {id};'
                cursor.execute(update_query)
                connection.commit()
                print("Updated successfully")
        finally:
            connection.close()
    except Exception as e:
        print("Connection refused...")
        print(e)


def check_exists(member) -> bool:
    '''
    Checks if member exists by it's id. Takes discord.Member or number instance to search. For example 'ctx.author' or 'ctx.author.id'
    '''
    try:
        connection = pymysql.connect(
            host=creds.host,
            port=3306,
            user=creds.user,
            password=creds.password,
            database=creds.db_name,
            cursorclass=pymysql.cursors.DictCursor
        )
        print("check_exists succeded")
        print("#"*20)
        try:
            if type(member) == int:
                member_id = member
            else: 
                member_id = member.id
            with connection.cursor() as cursor:
                select_query = f"SELECT id FROM users WHERE id = {member_id}"
                cursor.execute(select_query)
                check = cursor.fetchone()
                if check is None:
                    return False
                else:
                    return True
        finally:
            connection.close()
    except Exception as e:
        print("Connection refused...")
        print(e)


def check_logged(member) -> bool:
    '''
    Checks if member is logged by it's id. Takes discord.Member for search. For example 'ctx.author'
    '''
    try:
        connection = pymysql.connect(
            host=creds.host,
            port=3306,
            user=creds.user,
            password=creds.password,
            database=creds.db_name,
            cursorclass=pymysql.cursors.DictCursor
        )
        print("check_logged succeded")
        print("#"*20)
        try:
            if type(member) == int:
                member_id = member
            else: member_id = member.id
            with connection.cursor() as cursor:
                select_query = f"SELECT is_logged FROM users WHERE id = {member_id}"
                cursor.execute(select_query)
                check = cursor.fetchone()
                if check is not None and check['is_logged'] == 1:
                    return True
                else:
                    return False
        finally:
            connection.close()
    except Exception as e:
        print(traceback.format_exc())
        print("Connection refused...")
        print(e)


def check_login(login) -> bool:
    '''
    Checks if certain login is already exists in a database'
    '''
    try:
        connection = pymysql.connect(
            host=creds.host,
            port=3306,
            user=creds.user,
            password=creds.password,
            database=creds.db_name,
            cursorclass=pymysql.cursors.DictCursor
        )
        logger.info("Connection succeeded in \"check_login()\".")
        try:
            with connection.cursor() as cursor:
                select_query = f"SELECT login FROM users WHERE login = '{login}'"
                cursor.execute(select_query)
                check = cursor.fetchone()
                if check is None:
                    logger.info(f"Login {login} doesn't exist in the database. Returns False")
                    return False
                else:
                    logger.debug(f"Login {login} exists in the database. Returns True")
                    return True
        finally:
            connection.close()
    except Exception as e:
        logger.exception("Connection refused...")


'''
def check_password(password):
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
            with connection.cursor() as cursor:
                select_query = f"SELECT id, login, password, is_logged, atc FROM users WHERE login = {login}"
                cursor.execute(select_query)
                check = cursor.fetchone()
                if check is None:
                    return False
                else:
                    return True
        finally:
            connection.close()
    except Exception as e:
        print("Connection refused...")
        print(e)
'''


def get_user_by_login(login):
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
        try:
            with connection.cursor() as cursor:
                get_query = f"SELECT id, login, password, is_logged, atc FROM users WHERE login = '{login}'"
                cursor.execute(get_query)
                information = cursor.fetchall()
                if information is None:
                    return False
                else:
                    return information
        finally:
            connection.close()
    except Exception as e:
        print("#"*20)
        print("Connection refused...")
        print(e)


def get_user_by_id(member_id, INFO_NEEDED):
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
        try:
            with connection.cursor() as cursor:
                if type(member_id) == type([]):
                    get_query = f"SELECT {INFO_NEEDED} FROM users WHERE id = '{int(member_id[0])}'"
                    for id in member_id:
                        if member_id.index(id) == 0:
                            continue
                        get_query += f" OR '{int(id)}'"
                else: 
                    get_query = f"SELECT {INFO_NEEDED} FROM users WHERE id = '{int(member_id)}'"
                cursor.execute(get_query)
                information = cursor.fetchall()
                return information
        finally:
            connection.close()
    except Exception as e:
        print("#"*20)
        print("Connection refused...")
        print(e)


def get_userdata_by_id(member_id, INFO_NEEDED):
    try:
        connection = pymysql.connect(
            host=creds.host,
            port=3306,
            user=creds.user,
            password=creds.password,
            database=creds.db_name,
            cursorclass=pymysql.cursors.DictCursor
        )
        logger.info("Connection succeeded in \"get_userdata_by_id()\".")
        try:
            with connection.cursor() as cursor:
                get_query = f"SELECT {INFO_NEEDED} FROM user_data WHERE user_id = '{member_id}'"
                cursor.execute(get_query)
                information = cursor.fetchone()
                logger_deb.debug(information)
                logger.info(f"Retrieved information from userdata table about {member_id}. Func \"get_userdata_by_id()\"")
                return information
        finally:
            connection.close()
    except Exception as e:
        logger.exception("Connection refused...")


def get_player_characters(member):
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
                get_characters = f"SELECT * FROM characters WHERE user_storage_id IN (SELECT id FROM character_storage WHERE user_id = '{member.id}') AND active = TRUE"
                cursor.execute(get_characters)
                get_characters_ret = cursor.fetchmany()
                print(get_characters_ret)
            if get_characters_ret != None:
                return get_characters_ret
            else:
                return False
        finally:
            connection.close()
    except Exception as e:
        print("Connection refused...")
        print(e)


def check_if_inv_exists(member):
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
                check_if_inv_exists = f"SELECT id FROM inventories WHERE user_id = '{member.id}'"
                cursor.execute(check_if_inv_exists)
                check_if_inv_exists_ret = cursor.fetchone()
                print(check_if_inv_exists_ret)
            if check_if_inv_exists_ret != None:
                return True
            else:
                return False
        finally:
            connection.close()
    except Exception as e:
        print("Connection refused...")
        print(e)


def get_inventory(member):
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
            with connection.cursor() as cursor:
                select_query = f"SELECT * FROM inventory_slots WHERE inventory_id IN (SELECT id FROM inventories WHERE user_id = {member.id}); "
                cursor.execute(select_query)
                information = cursor.fetchall()
                return information
        finally:
            connection.close()
    except Exception as e:
        print("Connection refused...")
        print(e)


def insert_item(member, item_id, quantity):
    item_id = item_id.split('_')
    if item_id[0] == "w":
        item_id[0] = 1
    elif item_id[0] == "a":
        item_id[0] = 2
    elif item_id[0] == "i":
        item_id[0] = 3
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
            with connection.cursor() as cursor:
                select_query = f"SELECT inventory_id, slot_id FROM inventory_slots WHERE inventory_id IN (SELECT id FROM inventories WHERE user_id = {member.id});"
                cursor.execute(select_query)
                inv_id = cursor.fetchall()
                if inv_id[0]['slot_id'] == 50:
                    pass
                else:
                    select_query = f"SELECT id FROM inventory_slots WHERE inventory_id = {inv_id[0]['inventory_id']}, item_id = {item_id[1]}, item_type_id = {item_id[0]};"
                    try:
                        cursor.execute(select_query)
                        check_item = cursor.fetchone()
                    except:
                        check_item = None
                    if check_item is None:
                        insert_query = f"INSERT INTO inventory_slots (inventory_id, slot_id, item_id, quantity, item_type_id) " \
                            f"VALUES ('{inv_id[0]['inventory_id']}', {inv_id[0]['slot_id'] + 1}, {int(item_id[1])}, {quantity}, {int(item_id[0])});"
                        cursor.execute(insert_query)
                        connection.commit()
                    else:
                        update_query = f"UPDATE inventory_slots SET quantity = quantity + {quantity} WHERE id = {check_item[0]}"
                        cursor.execute(update_query)
                        connection.commit()
        finally:
            connection.close()
    except Exception as e:
        print("Connection refused...")
        print(e)


def delete_user(member):
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
        with connection.cursor() as cursor:
            try:
                delete_query = f"DELETE FROM users WHERE id = '{member.id}'"
                cursor.execute(delete_query)
                connection.commit()
                print("Deleted successfully")
            finally:
                connection.close()
    except Exception as e:
        print("Connection refused...")
        print(e)


def account_switch(user1, user2):
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
                try:
                    delete_query1 = f"DELETE FROM user_data WHERE user_id = '{user1.id}'"
                    cursor.execute(delete_query1)
                    connection.commit()
                    print("Deleted data successfully")
                    delete_query = f"DELETE FROM users WHERE id = '{user1.id}'"
                    cursor.execute(delete_query)
                    connection.commit()
                    print("Deleted successfully")
                except Exception:
                    pass
                # fk_set = "SET foreign_key_checks = 0"
                # cursor.execute(fk_set)
                update_query = f"UPDATE users SET id = '{user1.id}' WHERE id = '{user2.id}'"
                cursor.execute(update_query)
                connection.commit()
                print("Updated successfully")
                update_query = f"UPDATE user_data SET user_id = '{user1.id}' WHERE user_id = '{user2.id}'"
                cursor.execute(update_query)
                connection.commit()
                print("Updated data successfully")
                # fk_set = "SET foreign_key_checks = 1"
                # cursor.execute(fk_set)
        finally:
            print("account_switch succeded")
            print("#"*20)
            connection.close()
    except Exception as e:
        print("Connection refused...")
        print(e)


def get_json(member=None, raw=True, table="user_data"):
    '''_summary_

    Args:
        member (_type_, optional): _description_. Defaults to None.
        raw (bool, optional): _description_. Defaults to True.
        table (str, optional): _description_. Defaults to "user_data".

    Raises:
        ValueError: _description_

    Returns:
        _type_: _description_
    '''
    '''
    Tables: 'user_data', 'wov_players', 'wov_clans'
    Search type: 'id:', 'un:', 'me:'
    '''
    try:
        connection = pymysql.connect(
            host=creds.host,
            port=3306,
            user=creds.user,
            password=creds.password,
            database=creds.db_name,
            cursorclass=pymysql.cursors.DictCursor
        )
        logger.info("Connection succeeded in \"get_json()\".")
        with connection.cursor() as cursor:
            try:
                if table == "user_data":
                    if member is None:
                        select_query = f"SELECT user_id, json_stats->'$.botUsage' AS 'bot_stats' FROM user_data"
                        cursor.execute(select_query)
                        information = cursor.fetchall()
                        logger.info(f"Retrieved information from json about everyone. Func \"get_json()\"")
                        return information
                    else:
                        select_query = f"SELECT user_id, json_extract(json_stats, '$.botUsage') AS bot_stats FROM user_data WHERE user_id = '{member.id}'"
                        cursor.execute(select_query)
                        information = cursor.fetchone()
                        if information is None: return False
                        logger.info(f"Retrieved information from json about {member.id}. Func \"get_json()\"")
                        if raw == True:
                            return information
                        else:
                            dict_to_ret = json.loads(information['bot_stats'])
                            dict_to_ret['user_id'] = information['user_id']
                            print(dict_to_ret)
                            return dict_to_ret
                elif table in ["wov_players", "wov_clans"]:
                    if member is None: return None
                    search_type = member[0:3]
                    where_clause = "username"
                    desc = "personal_message"
                    if table == "wov_clans": where_clause, desc = where_clause[4:], "description"
                    if search_type == "id:": select_query = f'''SELECT {desc}, json_data->'$.*' AS wov_data FROM {table} WHERE id = '{member[3:]}';'''
                    elif search_type == "un:": select_query = f'''SELECT {desc}, json_data->'$.*' AS wov_data FROM {table} WHERE {where_clause} COLLATE utf8mb4_bin LIKE '{member[3:]}%';'''
                    elif search_type == "me:" and table == "wov_clans": select_query = f'''SELECT members AS wov_data FROM {table} WHERE id = '{member[3:]}';'''
                    else: raise ValueError(f"Couldn't recognize object. Supports 'id:', 'un:', 'me:'. received {search_type}")
                    cursor.execute(select_query)
                    information = cursor.fetchone()
                    if information is None: return False
                    logger.info(f"Retrieved information from json about {member[3:]}. Context: {[table, member[0:3]]}. Func \"get_json()\"")
                    if raw == True:
                        return information
                    else:
                        dict_to_ret = json.loads(information['wov_data'])
                        if search_type != "me:":
                            dict_to_ret.append(information[desc])
                        return dict_to_ret
            finally:
                connection.close()
    except Exception as e:
        logger.exception("Connection refused from \"get_json()\".")

def daily_info_json(member_id, raw=False):
    try:
        connection = pymysql.connect(
            host=creds.host,
            port=3306,
            user=creds.user,
            password=creds.password,
            database=creds.db_name,
            cursorclass=pymysql.cursors.DictCursor
        )
        logger.info("Connection succeeded in \"daily_info_json()\".")
        with connection.cursor() as cursor:
            try:
                select_query = f"SELECT user_id, json_stats->'$.botUsage.dailyInfo' AS bot_stats FROM user_data WHERE user_id = '{member_id}'"
                cursor.execute(select_query)
                information = cursor.fetchone()
                if information is None: return False
                logger.info(f"Retrieved information from json about {member_id}. Func \"daily_info_json()\"")
                if raw is True:
                    return information
                else:
                    dict_to_ret = json.loads(information['bot_stats'])
                    dict_to_ret['user_id'] = information['user_id']
                    return dict_to_ret
            finally:
                connection.close()
    except Exception as e:
        logger.exception(f"Connection refused from \"daily_info_json()\".")


def add_command_stats(member):
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
                select_query = f"SELECT json_stats->'$[0].botUsage.commandsUsed' AS commands_used FROM user_data WHERE user_id = '{member.id}'"
                cursor.execute(select_query)
                commands = cursor.fetchone()
                commands['commands_used'] = re.sub('"', "", commands['commands_used'])
                cu = int(commands['commands_used'])
                cu += 1 
                print(commands)
                update_query = f"UPDATE user_data SET json_stats = JSON_REPLACE(json_stats, '$[0].botUsage.commandsUsed', {cu}) WHERE user_id = '{member.id}'"
                cursor.execute(update_query)
                connection.commit()
                print("Updated data successfully")
                # fk_set = "SET foreign_key_checks = 1"
                # cursor.execute(fk_set)
        finally:
            connection.close()
    except Exception as e:
        pass


async def add_stats(member, stat=None, diff=None, sap=None, wwl=None, replacement = None):
    """
    Adds statistics to the user. Needs to be awaited. Takes "discord.Member" as user object
    """
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
            if type(member) == int:
                member_id = member
            else: 
                member_id = member.id
            with connection.cursor() as cursor:
                async def slct_query(st, dif=None, sp=None, wl=None):
                    if sp is not None and wl is None:
                        select_query = f"SELECT json_stats->'$[0].botUsage.{st}.{dif}.{sp}' AS bot_stats FROM user_data WHERE user_id = '{member_id}'"
                    elif sp is not None and wl is not None:
                        select_query = f"SELECT json_stats->'$[0].botUsage.{st}.{dif}.{sp}.{wl}' AS bot_stats FROM user_data WHERE user_id = '{member_id}'"
                    elif dif is not None:
                        select_query = f"SELECT json_stats->'$[0].botUsage.{st}.{dif}' AS bot_stats FROM user_data WHERE user_id = '{member_id}'"
                    else:
                        select_query = f"SELECT json_stats->'$[0].botUsage.{st}' AS bot_stats FROM user_data WHERE user_id = '{member_id}'"
                    cursor.execute(select_query)
                    stat = cursor.fetchone()
                    logger_deb.debug(stat)
                    return stat
                
                async def updt_query(st, dif=None, sp=None, wl=None, update_data=None):
                    if sp != None and wl is None:
                        update_query = f"UPDATE user_data SET json_stats = JSON_REPLACE(json_stats, '$[0].botUsage.{st}.{dif}.{sp}', {update_data}) WHERE user_id = {member_id};"
                    elif sp != None and wl != None:
                        update_query = f"UPDATE user_data SET json_stats = JSON_REPLACE(json_stats, '$[0].botUsage.{st}.{dif}.{sp}.{wl}', {update_data}) WHERE user_id = {member_id};"
                    elif dif != None:
                        update_query = f"UPDATE user_data SET json_stats = JSON_REPLACE(json_stats, '$[0].botUsage.{st}.{dif}', {update_data}) WHERE user_id = {member_id};"
                    else:
                        update_query = f"UPDATE user_data SET json_stats = JSON_REPLACE(json_stats, '$[0].botUsage.{st}', {update_data}) WHERE user_id = {member_id};"
                    
                    cursor.execute(update_query)
                    connection.commit()

                if stat != None:
                    if stat == "dailyInfo":
                        ck_if_exists = await slct_query(stat)
                        if ck_if_exists['bot_stats'] is None:
                            insert_query = f'''UPDATE user_data SET json_stats = JSON_INSERT(json_stats, '$.botUsage.dailyInfo', JSON_OBJECT('dailyCount', 0, 'lastDailyTime', null)) WHERE user_id = '{member_id}';'''
                            cursor.execute(insert_query)
                            connection.commit()
                            return
                        time_obj = datetimefix.utcnow()
                        iso = time_obj.isoformat() + "Z"
                        await updt_query(stat, update_data=f"JSON_OBJECT('dailyCount', {replacement}, 'lastDailyTime', '{str(iso)}')")
                        return
                    i_stat = await slct_query(stat, diff, sap, wwl)
                    i_stat = re.sub('"', "", i_stat['bot_stats'])
                    num_stat = int(i_stat)
                    num_stat += 1
                    await updt_query(stat, diff, sap, wwl, update_data=num_stat)
        finally:
            connection.close()
    except Exception as e:
        print(traceback.format_exc())
        pass


def add_rickroll_stats(member: discord.Member, list_of_users: list):
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
                def slct_query(member_id):
                    select_query = f"SELECT json_stats->'$[0].botUsage.rickroll' AS bot_stats FROM user_data WHERE user_id = '{member_id}'"
                    cursor.execute(select_query)
                    stat = cursor.fetchone()
                    print(stat)
                    if stat['bot_stats'] != None:
                        json_stat = json.loads(stat['bot_stats'])
                        full_json = { "rickroll" : json_stat}
                    else: full_json = None
                    print(full_json)
                    return full_json
                
                def updt_query(member_id, update_data=None):
                    print(update_data)
                    json_g = json.dumps(update_data)
                    update_query = f'''UPDATE user_data SET json_stats = JSON_SET(json_stats, '$[0].botUsage', JSON_MERGE_PATCH(JSON_EXTRACT(json_stats, '$[0].botUsage'), '{json_g}')) WHERE user_id = '{member_id}';'''
                    cursor.execute(update_query)
                    connection.commit()
                    print('Updated r stats')
                print(list_of_users)
                if len(list_of_users) > 2:
                    if check_exists(member.id) == True:
                        rickroll_stat = slct_query(member.id)
                        try:
                            if rickroll_stat != None:
                                pass
                            else: rickroll_stat = { "rickroll": { "themselves": 0, "others": 0 } }
                        except KeyError:
                            rickroll_stat = { "rickroll": { "themselves": 0, "others": 0 } }
                        rickroll_stat["rickroll"]["others"] += len(list_of_users) - 2
                        updt_query(member.id, update_data=rickroll_stat)
                    for person in list_of_users:
                        if check_exists(person) == True and person != member.id:
                            stats2 = slct_query(person)
                            print(stats2)
                            if stats2 != None:
                                stats2["rickroll"]["themselves"] += 1
                            else: stats2 = { "rickroll": { "themselves": 1, "others": 0 } }
                            updt_query(person, update_data=stats2)
                else:
                    if check_exists(member.id) == True:
                        rickroll_stat = slct_query(member.id)
                        try:
                            if rickroll_stat != None: rickroll_stat['rickroll']['themselves'] += 1
                            else: rickroll_stat = { "rickroll": { "themselves": 1, "others": 0 } }
                        except KeyError or TypeError:
                            rickroll_stat = { "rickroll": { "themselves": 1, "others": 0 } }
                        updt_query(member.id, update_data=rickroll_stat)
        finally:
            connection.close()
    except Exception as e:
        print(traceback.format_exc())
        pass

def add_xp(member, amount):
    amount = int(amount)
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
            with connection.cursor() as cursor:
                select_query = f"SELECT level, xp, max_xp FROM user_data WHERE user_id = {member.id};"
                cursor.execute(select_query)
                lvl_info = cursor.fetchmany()
                print(lvl_info)
                lvl_info[0]['xp'] += amount
                while lvl_info[0]['xp'] >= lvl_info[0]['max_xp']:
                    lvl_info[0]['xp'] = lvl_info[0]['xp'] - \
                        lvl_info[0]['max_xp']
                    if lvl_info[0]['level'] <= 6:
                        lvl_info[0]['max_xp'] = round(
                            lvl_info[0]['max_xp'] + lvl_info[0]['max_xp']/2)
                    elif 6 < lvl_info[0]['level'] <= 10:
                        lvl_info[0]['max_xp'] = 2000
                    else:
                        lvl_info[0]['max_xp'] = 2500
                    lvl_info[0]['level'] += 1
                update_query = f"UPDATE user_data SET level = {lvl_info[0]['level']}, xp = {lvl_info[0]['xp']}, max_xp = {lvl_info[0]['max_xp']} WHERE user_id = {member.id};"
                cursor.execute(update_query)
                connection.commit()
        finally:
            connection.close()
    except Exception as e:
        print("Connection refused...")
        print(e)
    # with open("players.json", "r") as f:
    #     players = json.load(f)
    #     stats = players[str(member.id)]["profile"]
    #     stats["xp"] += amount
    #     while stats["xp"] >= stats["maxXp"]:
    #         stats["xp"] = stats["xp"] - stats["maxXp"]
    #         if stats["level"] <= 6: stats["maxXp"] = round(stats["maxXp"] + stats["maxXp"]/2)
    #         elif 6 < stats["level"] <= 10: stats["maxXp"] = 2000
    #         else: stats["maxXp"] = 2500
    #         stats["level"] += 1

    # with open("players.json", "w") as f:
    #     json.dump(players, f, indent=4)

def update_userdata(member_id, column, replacement):
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
            if column == "user_id" or column == "json_stats":
                print(f"{bcolors.FAIL}Can't change '{column}' column. Please consider using safest functions for that")
                return None
            
            with connection.cursor() as cursor:
                update_query = f"UPDATE user_data SET {column} = {replacement} WHERE user_id = '{member_id}'"
                cursor.execute(update_query)
                connection.commit()
                print("Updated data successfully")
        finally:
            connection.close()
    except Exception as e:
        pass

def local_checks(user):
    if check_exists(user) == True:
        if check_logged(user) == True:
            return True
        else:
            return False
    else:
        return False


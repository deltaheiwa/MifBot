import logging
import subprocess
from typing import Any, Literal, Union, Callable
import gettext
import chess
import chess.svg
from cairosvg import svg2png
import asyncio
import aiohttp
import datetime
import json
import math
import random
import re
import os
import coloredlogs
from datetime import datetime as datetimefix, timedelta
from io import BytesIO
from pathlib import Path
import calendar
import discord
import requests
from discord.ext import commands
from PIL import Image, ImageDraw, ImageFont
import time
import os
from dotenv import load_dotenv


class CustomFormatter(logging.Formatter):
    grey = "\x1b[38;20m"
    yellow = "\x1b[33;20m"
    red = "\x1b[31;20m"
    bold_red = "\x1b[31;1m"
    reset = "\x1b[0m"
    format_str = (
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s (%(filename)s:%(lineno)d)"
    )

    FORMATS = {
        logging.DEBUG: grey + format_str + reset,
        logging.INFO: grey + format_str + reset,
        logging.WARNING: yellow + format_str + reset,
        logging.ERROR: red + format_str + reset,
        logging.CRITICAL: bold_red + format_str + reset,
    }

    def format(self, record):
        log_fmt = self.FORMATS.get(record.levelno)
        formatter = logging.Formatter(log_fmt)
        return formatter.format(record)

class AsyncTranslator():
    def __init__(self, language_code):
        if language_code is None:
            language_code = "en"
        self.language_code = language_code

    async def __aenter__(self):
        lang = gettext.translation(
            "mifbot2", localedir=os.path.abspath('./locales'), languages=[self.language_code], fallback=True
        )
        return lang

    async def __aexit__(self, exc_type, exc, tb):
        del self

class ProgressBar:
    """
    Call in a loop to create terminal progress bar
    @params:
        iteration   - Required  : current iteration (Int)
        total       - Required  : total iterations (Int)
        prefix      - Optional  : prefix string (Str)
        suffix      - Optional  : suffix string (Str)
        decimals    - Optional  : positive number of decimals in percent complete (Int)
        length      - Optional  : character length of bar (Int)
        fill        - Optional  : bar fill character (Str)
        printEnd    - Optional  : end character (e.g. "\r", "\r\n") (Str)
    """

    def __init__(
        self,
        iteration,
        total,
        prefix="",
        suffix="",
        decimals=1,
        length=100,
        fill="█",
        print_end="\r",
    ):
        self.iteration = iteration
        self.total = total
        self.prefix = prefix
        self.suffix = suffix
        self.decimals = decimals
        self.length = length
        self.fill = fill
        self.print_end = print_end
        self.percent = ("{0:." + str(decimals) + "f}").format(
            100 * (iteration / float(total))
        )
        self.bar_string = None
        self.update_bar()

    def update_bar(
        self,
        new_iteration=None,
        new_prefix=None,
        new_suffix=None,
        percentage: bool = True,
    ):
        if new_iteration is None:
            new_iteration = self.iteration
        if new_prefix is not None:
            self.prefix = new_prefix
        if new_suffix is not None:
            self.suffix = new_suffix
        filledLength = int(self.length * new_iteration // self.total)
        if percentage is False:
            self.percent = ""
        else:
            self.percent = ("{0:." + str(self.decimals) + "f}").format(
                100 * (new_iteration / float(self.total))
            )
        bar = self.fill * filledLength + "-" * (self.length - filledLength)
        self.bar_string = f"\r{self.prefix} |{bar}| {self.percent}% {self.suffix}"
        return self.bar_string


from db_data import database_main, mysql_main
import bot_util.bot_config as bot_config
from bot_util.bot_exceptions import NotAuthorizedError
from functools import lru_cache


formatter = logging.Formatter("%(asctime)s:%(levelname)s --- %(message)s")
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
file_handler = logging.FileHandler(bot_config.LogFiles.functions_log)
file_handler.setFormatter(formatter)
logger.addHandler(file_handler)

load_dotenv('creds/.env')

class bcolors:
    HEADER = "\033[95m"
    OKBLUE = "\033[94m"
    OKCYAN = "\033[96m"
    OKGREEN = "\033[92m"
    WARNING = "\033[93m"
    FAIL = "\033[91m"
    ENDC = "\033[0m"
    BOLD = "\033[1m"
    UNDERLINE = "\033[4m"


console_formatter = CustomFormatter()
stream_handler = logging.StreamHandler()
stream_handler.setFormatter(console_formatter)
coloredlogs.install(level="INFO", logger=logger)


async def determine_prefix(client, message):
    try:
        user_pref = await database_main.PrefixDatabase.return_prefix(_id=message.author.id, user=True)
        guild_pref = await database_main.PrefixDatabase.return_prefix(_id=message.guild.id) if message.guild else None
        if user_pref is None or user_pref != message.content[0: len(user_pref)]:
            prefix = guild_pref or "."
        else:
            prefix = user_pref
        return prefix
    except Exception as e:
        logger.error(f"Error in determine_prefix: {e}")
        await client.telegram_bot._send_automatic_exception(e, func=determine_prefix, line=e.__traceback__.tb_lineno, extra=f"Message: {message.content}")
        return "."

class ConfigFunctions:
    @classmethod
    def add_telegram_chat(cls, chat_id: int):
        try:
            if chat_id not in bot_config.telegram_chat_id:
                bot_config.telegram_chat_id.append(chat_id)
                with open("bot_config_perma.json", "r") as f:
                    json_file = json.load(f)
                json_file["telegram_chat_id"] = bot_config.telegram_chat_id
                with open("bot_config_perma.json", "w") as f:
                    json.dump(json_file, f)
                logger.info(f"Chat id {chat_id} added")
                return True
            else:
                return False
        except Exception as e:
            logger.exception(f"Error in add_telegram_chat")
            return False
    
    @classmethod
    def remove_telegram_chat(cls, chat_id: int):
        try:
            if chat_id in bot_config.telegram_chat_id:
                bot_config.telegram_chat_id.remove(chat_id)
                with open("bot_config_perma.json", "r") as f:
                    json_file = json.load(f)
                json_file["telegram_chat_id"] = bot_config.telegram_chat_id
                with open("bot_config_perma.json", "w") as f:
                    json.dump(json_file, f)
                logger.info(f"Chat id {chat_id} removed")
                return True
            else:
                return False
        except Exception as e:
            logger.exception(f"Error in remove_telegram_chat")
            return False

def dev_command():
    def predicate(ctx):
        if ctx.message.author.id not in bot_config.admin_account_ids:
            raise NotAuthorizedError()
        return True
    return commands.check(predicate)

def get_directory_structure(startpath='.'):
    excluded_dirs = {'.git', 'node_modules', '.mypy_cache', '.idea', '__pycache__', '.ruff_cache'}
    structure = ''
    for root, dirs, files in os.walk(startpath):
        dirs[:] = [d for d in dirs if d not in excluded_dirs]  # Exclude specified directories
        level = root.replace(startpath, '').count(os.sep)
        indent = ' ' * 4 * level
        structure += f'{indent}{os.path.basename(root)}/\n'
        subindent = ' ' * 4 * (level + 1)
        for f in files:
            structure += f'{subindent}{f}\n'
    return structure


baseboard_map = {
    "p": "♟",
    "P": "♙",
    "k": "♚",
    "K": "♔",
    "q": "♛",
    "Q": "♕",
    "r": "♜",
    "R": "♖",
    "b": "♝",
    "B": "♗",
    "n": "♞",
    "N": "♘",
}

chess_emojis = {
    "B_0": "<:B_0:1042158166114320394>",
    "B_1": "<:B_1:1042158167456501880>",  # White Bishop
    "N_0": "<:N_0:1042158182874763274>",
    "N_1": "<:N_1:1042158184242086082>",  # White Knight
    "K_0": "<:K_0:1042158176562323577>",
    "K_1": "<:K_1:1042158178479116398>",  # White King
    "P_0": "<:P_0:1042158188956495972>",
    "P_1": "<:P_1:1042158190852317204>",  # White Pawn
    "Q_0": "<:Q_0:1042158195172450354>",
    "Q_1": "<:Q_1:1042158196841779370>",  # White Queen
    "R_0": "<:R_0:1042158201300320296>",
    "R_1": "<:R_1:1042158203053547540>",  # White Rook
    "b_0": "<:b_0:1042158163337695284>",
    "b_1": "<:b_1:1042158164671467530>",  # Black Bishop
    "._0": "<:blank_0:1042158168790282270>",
    "._1": "<:blank_1:1042158172670021673>",  # Blanks
    "k_0": "<:k_0:1042158173987012668>",
    "k_1": "<:k_1:1042158175283056741>",  # Black King
    "n_0": "<:n_0:1042158180081336381>",
    "n_1": "<:n_1:1042158181431906304>",  # Black Knight
    "p_0": "<:p_0:1042158185831743619>",
    "p_1": "<:p_1:1042158187329110037>",  # Black Pawn
    "q_0": "<:q_0:1042158192467124264>",
    "q_1": "<:q_1:1042158193800908840>",  # Black Queen
    "r_0": "<:r_0:1042158198100082709>",
    "r_1": "<:r_1:1042158199823937547>",  # Black Rook
}

board_trans = str.maketrans(
    "".join(baseboard_map.keys()), "".join(baseboard_map.values())
)

def board_to_image(board: chess.Board, lastmove: chess.Move = None, check_square: chess.Square = None):
    with BytesIO() as image_binary:
        board_svg = chess.svg.board(
            board=board,
            size=600,
            lastmove=lastmove,
            check=check_square,
            orientation=chess.WHITE
        )
        bytes_image = svg2png(bytestring=board_svg, write_to=image_binary)
        image_binary.seek(0)
        board_png_image = Image.open(fp=image_binary)
        image_binary.seek(0)
        attachment_board = discord.File(fp=image_binary, filename="board.png")
        return attachment_board, board_png_image


def chess_pieces_visualizator(symbol):
    """
    Takes a piece letter from 'python chess' board, and transposes it into an emoji
    """
    translated = symbol.translate(board_trans)
    rows = translated.split("\n")
    symbol_matrix = []
    for each_row in rows:
        symbols = each_row.split(" ")
        for each in symbols:
            symbol_matrix.append(each)
    color_toggle = True
    insertpoint = 8
    for i in range(8):
        symbol_matrix.insert(insertpoint * i + i, "\n")
    del symbol_matrix[0]
    for uni in symbol_matrix:
        if uni == ".":
            if color_toggle == True:
                symbol_matrix[symbol_matrix.index(uni)] = "\u25fb"
            else:
                symbol_matrix[symbol_matrix.index(uni)] = "\u25fc"
        color_toggle = not color_toggle
    return "".join(symbol_matrix)


superscript_map = {
    "0": "⁰",
    "1": "¹",
    "2": "²",
    "3": "³",
    "4": "⁴",
    "5": "⁵",
    "6": "⁶",
    "7": "⁷",
    "8": "⁸",
    "9": "⁹",
    "a": "ᵃ",
    "b": "ᵇ",
    "c": "ᶜ",
    "d": "ᵈ",
    "e": "ᵉ",
    "f": "ᶠ",
    "g": "ᵍ",
    "h": "ʰ",
    "i": "ᶦ",
    "j": "ʲ",
    "k": "ᵏ",
    "l": "ˡ",
    "m": "ᵐ",
    "n": "ⁿ",
    "o": "ᵒ",
    "p": "ᵖ",
    "q": "۹",
    "r": "ʳ",
    "s": "ˢ",
    "t": "ᵗ",
    "u": "ᵘ",
    "v": "ᵛ",
    "w": "ʷ",
    "x": "ˣ",
    "y": "ʸ",
    "z": "ᶻ",
    "A": "ᴬ",
    "B": "ᴮ",
    "C": "ᶜ",
    "D": "ᴰ",
    "E": "ᴱ",
    "F": "ᶠ",
    "G": "ᴳ",
    "H": "ᴴ",
    "I": "ᴵ",
    "J": "ᴶ",
    "K": "ᴷ",
    "L": "ᴸ",
    "M": "ᴹ",
    "N": "ᴺ",
    "O": "ᴼ",
    "P": "ᴾ",
    "Q": "Q",
    "R": "ᴿ",
    "S": "ˢ",
    "T": "ᵀ",
    "U": "ᵁ",
    "V": "ⱽ",
    "W": "ᵂ",
    "X": "ˣ",
    "Y": "ʸ",
    "Z": "ᶻ",
    "+": "⁺",
    "-": "⁻",
    "=": "⁼",
    "(": "⁽",
    ")": "⁾",
}

trans = str.maketrans(
    "".join(superscript_map.keys()), "".join(superscript_map.values())
)

subscript_map = {
    "0": "₀",
    "1": "₁",
    "2": "₂",
    "3": "₃",
    "4": "₄",
    "5": "₅",
    "6": "₆",
    "7": "₇",
    "8": "₈",
    "9": "₉",
    "a": "ₐ",
    "b": "♭",
    "c": "꜀",
    "d": "ᑯ",
    "e": "ₑ",
    "f": "բ",
    "g": "₉",
    "h": "ₕ",
    "i": "ᵢ",
    "j": "ⱼ",
    "k": "ₖ",
    "l": "ₗ",
    "m": "ₘ",
    "n": "ₙ",
    "o": "ₒ",
    "p": "ₚ",
    "q": "૧",
    "r": "ᵣ",
    "s": "ₛ",
    "t": "ₜ",
    "u": "ᵤ",
    "v": "ᵥ",
    "w": "w",
    "x": "ₓ",
    "y": "ᵧ",
    "z": "₂",
    "A": "ₐ",
    "B": "₈",
    "C": "C",
    "D": "D",
    "E": "ₑ",
    "F": "բ",
    "G": "G",
    "H": "ₕ",
    "I": "ᵢ",
    "J": "ⱼ",
    "K": "ₖ",
    "L": "ₗ",
    "M": "ₘ",
    "N": "ₙ",
    "O": "ₒ",
    "P": "ₚ",
    "Q": "Q",
    "R": "ᵣ",
    "S": "ₛ",
    "T": "ₜ",
    "U": "ᵤ",
    "V": "ᵥ",
    "W": "w",
    "X": "ₓ",
    "Y": "ᵧ",
    "Z": "Z",
    "+": "₊",
    "-": "₋",
    "=": "₌",
    "(": "₍",
    ")": "₎",
}


sub_trans = str.maketrans(
    "".join(subscript_map.keys()), "".join(subscript_map.values())
)


def sub_sup_text(type, text):
    """
    Converts a text into subscript or superscript. Use "sub" for subscript and "sup" for superscript
    """
    if type == "sub":
        return text.translate(sub_trans)
    elif type == "sup":
        return text.translate(trans)

@lru_cache(maxsize=None)
def coins_formula(day, multiplier):
    max_coins = 10000  # The asymptotic limit
    growth_rate = 0.1  # The rate of growth
    mid_point = 30  # The midpoint of the curve (the point of maximum growth, aka day)
    min_coins = 10  # The minimum number of coins that can be earned
    
    # logistic growth formula
    coins_bonus = max_coins / (1 + math.exp(-growth_rate * (day - mid_point)))
    
    # shift the curve down so that it starts at min_coins
    coins_bonus -= max_coins / (1 + math.exp(growth_rate * mid_point))
    
    # adjust based on multiplier and add min_coins
    coins_bonus = coins_bonus * multiplier + min_coins

    logger.debug(f"{round(coins_bonus)} day: {day}, m: {multiplier}")
    return coins_bonus


def percentage_calc(
    full_value: int, percentage: int, if_round: bool = False, round_to: int = 2
):
    """Calculates percentage of the given value

    Args:
        full_value (int): Full value to calculate the percentage of
        percentage (int): Percentage itself

    Returns:
        float: Part of the full value by percentage+-+-

    Extras:
        Returns '0.00' if full value is 0
    """
    if full_value == 0:
        return 0.00
    percent = percentage * 100 / full_value
    if if_round:
        percent = round(percent, round_to)
    return percent


def repeating_symbols(text: str) -> bool:
    """
    Checks if some symbols were repeated in the text. Returns True or False
    """
    for i in range(len(text)):
        if i != text.rfind(text[i]):
            return True
    return False


def regulated_request(
    url: str, sleep_time: float = 0.5, backoff_time: float = 10.0, **kwargs: Any
) -> requests.Response:
    resp: requests.Response = requests.get(url, **kwargs)
    if resp.status_code == 429:
        logger.warning("429 error, waiting 10 seconds")
        time.sleep(backoff_time)
        kwargs["backoff_time"] = backoff_time
        kwargs["sleep_time"] = sleep_time
        return regulated_request(url, **kwargs)
    else:
        if resp.status_code != 200:
            logger.error(
                f"Warning: {url} received non 200 exit code: {resp.status_code}"
            )
        time.sleep(sleep_time)
        return resp

def chance(percent: float) -> bool:
    """
    Returns True or False based on the given percentage
    """
    return random.random() < percent / 100

def timestamp_calculate(objT: Union[str, datetimefix], type_of_format: str) -> str:
    """
    Types of format:
        - Creation Date: 06/12/2018, 09:55:22
        - Recent Date: Monday, Mar 21 2022, 13:31:09
        - Light Datetime: Mar 21 2022, 13:31:09
        - Light Date: Mar 21 2022

    """
    if isinstance(objT, str):
        try:
            date_obj = datetimefix.strptime(objT, "%Y-%m-%dT%H:%M:%S.%fZ")
        except Exception as e:
            try:
                date_obj = datetimefix.fromisoformat(objT)
            except:
                date_obj = datetimefix.strptime(objT, "%Y-%m-%d %H:%M:%S")
    else:
        date_obj = objT
    try:
        date_str = date_obj.strftime("%Y-%m-%dT%H:%M:%SZ")
    except:
        date_str = date_obj.strftime("%Y-%m-%d %H:%M:%S")
    try:
        epoch = calendar.timegm(time.strptime(date_str, "%Y-%m-%dT%H:%M:%SZ"))
    except:
        epoch = calendar.timegm(time.strptime(date_str, "%Y-%m-%d %H:%M:%S"))
    if type_of_format == "Creation Date":
        complete = str(time.strftime("%m/%d/%Y, %H:%M:%S", time.gmtime(epoch)))
    elif type_of_format == "Recent Date":
        complete = str(time.strftime("%A, %b %d %Y, %H:%M:%S", time.gmtime(epoch)))
    elif type_of_format == "Light Datetime":
        complete = str(time.strftime("%b %d %Y, %H:%M:%S", time.gmtime(epoch)))
    elif type_of_format == "Light Date":
        complete = str(time.strftime("%b %d %Y", time.gmtime(epoch)))
    elif type_of_format == "Only Date":
        complete = str(time.strftime("%b %d, %H:00", time.gmtime(epoch)))
    else:
        raise AttributeError("Unknown format. Received {}".format(type_of_format))
    return complete

class APICaller:
    def __init__(self):
        self.queue = asyncio.Queue()
        self.worker = asyncio.create_task(self.process_queue())

    async def add_to_queue(self, func: Callable, *args: Any):
        future = asyncio.Future()
        await self.queue.put((func, args, future))
        return future

    async def process_queue(self):
        while True:
            func, args, future = await self.queue.get()
            try:
                result = await func(*args)  # Ensure the await is here.
                future.set_result(result)
            except Exception as e:
                future.set_exception(e)
            self.queue.task_done()
            await asyncio.sleep(1)  # Respect the rate limit.

class MembersOrRoles(commands.Converter):
    async def convert(self, ctx, argument):
        members = []
        for arg in argument.split():
            try:
                member = await commands.MemberConverter().convert(ctx, arg)
            except commands.BadArgument:
                member = await commands.RoleConverter().convert(ctx, arg)
            members.append(member)
        return members


class WovApiCall:
    headers = {"Authorization": f"Bot {os.getenv('WOV_API_TOKEN')}"}
    api_url = "https://api.wolvesville.com/"

    @classmethod
    async def get_user_by_id(cls, user_id: int):
        async with aiohttp.ClientSession() as session:
            async with session.get(
                url=cls.api_url + f"players/{user_id}", headers=cls.headers
            ) as response:
                if response.status == 200:
                    return await response.json()
                else:
                    logger.error(
                        f"Wov User API call failed with status code {response.status}. User ID: {user_id}"
                    )
                    return None

    @classmethod
    async def get_user_by_name(cls, username: str):
        async with aiohttp.ClientSession() as session:
            async with session.get(
                url=cls.api_url + f"players/search?username={username}", headers=cls.headers
            ) as response:
                if response.status == 200:
                    return await response.json()
                else:
                    logger.error(
                        f"Wov User API call failed with status code {response.status}. Username: {username}"
                    )
                    return None

    @classmethod
    async def get_clan_by_id(cls, clan_id: int):
        async with aiohttp.ClientSession() as session:
            async with session.get(
                url=cls.api_url + f"clans/{clan_id}/info", headers=cls.headers
            ) as response:
                if response.status == 200:
                    return await response.json()
                else:
                    logger.error(
                        f"Wov Clan API call failed with status code {response.status}. Clan ID: {clan_id}"
                    )
                    return None

    @classmethod
    async def get_clan_by_name(cls, clan_name: str):
        async with aiohttp.ClientSession() as session:
            async with session.get(
                url=cls.api_url + f"clans/search?name={clan_name}", headers=cls.headers
            ) as response:
                if response.status == 200:
                    return await response.json()
                else:
                    logger.error(
                        f"Wov Clan API call failed with status code {response.status}. Clan name: {clan_name}"
                    )
                    return None

    @classmethod
    async def get_clan_members(cls, clan_id: int):
        async with aiohttp.ClientSession() as session:
            async with session.get(
                url=cls.api_url + f"clans/{clan_id}/members", headers=cls.headers
            ) as response:
                if response.status == 200:
                    return await response.json()
                else:
                    logger.error(
                        f"Wov Clan Members API call failed with status code {response.status}. Clan ID: {clan_id}"
                    )
                    return None

    @classmethod
    async def get_shop(cls):
        async with aiohttp.ClientSession() as session:
            async with session.get(
                url=cls.api_url + f"shop/activeOffers", headers=cls.headers
            ) as response:
                if response.status == 200:
                    return await response.json()
                else:
                    logger.error(
                        "Wov Shop API call failed with status code %s.".format(response.status)
                    )
                    return None


class LichessApiCall:
    lichess_url = "https://lichess.org/api/"
    headers = {"Authorization": f"Bearer {os.getenv('LI_API_TOKEN')}"}

    @classmethod
    def get_user_performance(cls, username: str, perf_type: str):
        response = requests.get(
            url=cls.lichess_url + f"user/{username}/perf/{perf_type}",
            headers=cls.headers,
        )
        if response.status_code == 200:
            return response.json()
        else:
            logger.error(
                f"Lichess User Performance API call failed with status code {response.status_code}. Username: {username}"
            )
            return None

    @classmethod
    def export_by_player(
        cls,
        username: str,
        since: int | datetimefix = None,
        until: int | datetimefix = None,
        limit: int = None,
        vs: str = None,
        rated: bool = None,
        perf_type: list = None,  # "ultraBullet","bullet","blitz","rapid","classical","correspondence","chess960","crazyhouse","antichess","atomic","horde","kingOfTheHill","racingKings","threeCheck"
        color: Literal["white", "black"] = None,
        analysed: bool = None,
        moves: bool = True,
        tags: bool = True,
        evals: bool = True,
        pgn_in_json: bool = False,
        opening: bool = False,
        clocks: bool = False,
        accuracy: bool = False,
        ongoing: bool = False,
        finished: bool = True,
        literate: bool = False,
        lastFen: bool = False,
        sort: str = "dateDesc",
    ):
        """Export games by player.

        Args:
            username (str): Lichess username.

        Kwargs:
            since (int | datetimefix, optional): Download games played since this timestamp. Defaults to account creation date.
            until (int | datetimefix, optional): Download games played until this timestamp. Defaults to now.
            max (int, optional): How many games to download. Leave empty to download all games. Defaults to None.
            vs (str, optional): [Filter] Only games played against this opponent. Defaults to None.
            rated (bool, optional): [Filter] Only rated (True) or casual (False) games. Defaults to None.
            perf_type (list(Literal[ultraBullet,bullet,blitz,rapid,classical,correspondence,chess960,crazyhouse,antichess,atomic,horde,kingOfTheHill,racingKings,threeCheck]), optional): [Filter] Only games in these speeds or variants. Multiple perf types can be specified, separated by a comma. Defaults to None.
            color (Literal[white,black], optional): [Filter] Only games played as this color. Defaults to None.
            analysed (bool, optional): [Filter] Only games with or without a computer analysis available. Defaults to None.
            moves (bool, optional): Include PGN moves. Defaults to True.
            tags (bool, optional): Include PGN tags. Defaults to True.
            evals (bool, optional): Include analysis evaluations and comments when available. Defaults to True.
            pgn_in_json (bool, optional): Include the full PGN within the JSON response, in a pgn field. Defaults to True.
            opening (bool, optional): Include the opening name. Defaults to False.
            clocks (bool, optional): Include clock status when available. Defaults to False.
            accuracy (bool, optional): Include accuracy percent of each player, when available. Defaults to False.
            ongoing (bool, optional): Include ongoing games. The last 3 moves will be omitted. Defaults to False.
            finished (bool, optional): Include finished games. Set to false to only get ongoing games. Defaults to True.
            literate (bool, optional): Insert textual annotations in the PGN about the opening, analysis variations, mistakes, and game termination. Defaults to False.
            lastFen (bool, optional): Include the FEN notation of the last position of the game. Defaults to False.
            sort (str["dateDesc", "dateAsc"], optional): Sort order of the games. Defaults to "dateDesc".

        Yields:
            _type_: _description_
        """

        params = {
            "since": since,
            "until": until,
            "max": limit,
            "vs": vs,
            "rated": rated,
            "perfType": perf_type,
            "color": color,
            "analysed": analysed,
            "moves": moves,
            "tags": tags,
            "evals": evals,
            "pgnInJson": pgn_in_json,
            "opening": opening,
            "clocks": clocks,
            "accuracy": accuracy,
            "ongoing": ongoing,
            "finished": finished,
            "literate": literate,
            "lastFen": lastFen,
            "sort": sort,
        }
        headers = cls.headers
        headers["Accept"] = "application/x-ndjson"
        try:
            resp = regulated_request(
                url=cls.lichess_url + f"games/user/{username}",
                headers=headers,
                params=params,
            )
            for line in resp.text.splitlines():
                if line.strip():
                    yield json.loads(line)
        except Exception as e:
            logger.error(
                f"Lichess Export By Player API call failed. Username: {username}. Error: {e}"
            )
            return None


async def channel_perms_change(
    user: Union[discord.Member, discord.Role],
    channel: Union[discord.TextChannel, discord.VoiceChannel],
    perms_change: bool,
):
    await channel.set_permissions(
        user,
        send_messages=perms_change,
        read_messages=perms_change,
        view_channel=perms_change,
    )

'''
def vg_check(user: discord.Member, server_id: int):
    try:
        connection = pymysql.connect(
            host=creds.host,
            port=3306,
            user=creds.user,
            password=creds.password,
            database=creds.db_vg_name,
            cursorclass=pymysql.cursors.DictCursor,
        )
        try:
            with connection.cursor() as cursor:
                select_query = f"SELECT ongoing_games.id, ongoing_games.status, ongoing_games.phase, players.state FROM ongoing_games INNER JOIN players ON ongoing_games.id = players.game_id WHERE players.id = {user.id} AND ongoing_games.server_id = '{server_id}';"
                cursor.execute(select_query)
                check = cursor.fetchone()
                print(check)
                if check is not None:
                    return check
                return None
        finally:
            connection.close()
    except Exception as e:
        print(traceback.print_exception(e))
        print("Connection refused...")
        print(e)


def append_village_game(user: discord.Member, server_id: int):
    if vg_check(user, server_id) is not None:
        return None

    try:
        connection = pymysql.connect(
            host=creds.host,
            port=3306,
            user=creds.user,
            password=creds.password,
            database=creds.db_vg_name,
            cursorclass=pymysql.cursors.DictCursor,
        )
        try:
            with connection.cursor() as cursor:
                insert_query = f"INSERT INTO ongoing_games (server_id, status, main_os, player_cap, phase) VALUES ({server_id}, 'Creating', {user.id}, -1, -1);"
                cursor.execute(insert_query)
                connection.commit()
        finally:
            connection.close()
    except Exception as e:
        print(traceback.print_exception(e))
        print("Connection refused...")
        print(e)
'''
def level_rank(level: int) -> int | str:
    if level < 0: return 'no'
    if level < 420:
        rank = math.floor(level / 10 + 1)
        if rank < 10:
            return f"0{rank}"
        else:
            return math.floor(level / 10 + 1)
    elif 420 <= level < 1000:
        if level < 500:
            return 43
        elif level < 600:
            return 44
        elif level < 700:
            return 45
        elif level < 800:
            return 46
        elif level < 900:
            return 47
        elif level < 1000:
            return 48
    else:
        return "last"

def round_edges(im, radius):
    mask = Image.new("L", (radius * 2, radius * 2), 0)
    draw = ImageDraw.Draw(mask)
    draw.ellipse((0, 0, radius * 2, radius * 2), fill=255)
    alpha = Image.new("L", im.size, 255)
    (
        w,
        h,
    ) = im.size
    alpha.paste(mask.crop((0, 0, radius, radius)), box=(0, 0))
    alpha.paste(mask.crop((0, radius, radius, radius * 2)), box=(0, h - radius))
    alpha.paste(mask.crop((radius, 0, radius * 2, radius)), box=(w - radius, 0))
    alpha.paste(
        mask.crop((radius, radius, radius * 2, radius * 2)),
        box=(w - radius, h - radius),
    )

    im.putalpha(alpha)
    return im

class WolvesvilleFunctions:
    @staticmethod
    def history_caching(json_data):
        with open(Path("Wov Cache", "old_player_cache.json"), "r") as js_f:
            cache_file = json.load(js_f)

        if json_data["id"] not in cache_file:
            cache_file[json_data["id"]] = {}
        cache_file[json_data["id"]][json_data["caching_data"]["time_cached"]] = json_data['rankedSeasonSkill'] if 'rankedSeasonSkill' in json_data else None

        with open(Path("Wov Cache", "old_player_cache.json"), "w") as js_f:
            json.dump(cache_file, js_f, indent=4)

    @staticmethod
    async def avatar_rendering(image_URL: str, level: int = 0, rank: bool = True):
        """
        This one is fked up
        """
        av_bg = Image.open(Path("Images", "wolvesville_small_night_AVATAR.png")).convert(
            "RGBA"
        )
        # urllib.request.urlretrieve(image_URL)
        url_response = requests.get(image_URL)
        avatar = Image.open(BytesIO(url_response.content)).convert("RGBA")
        lvlfont = ImageFont.truetype("Fonts/OpenSans-Bold.ttf", 12)
        one_ts_lvl_font = ImageFont.truetype("Fonts/OpenSans-Bold.ttf", 10)
        width_bg, height_bg = av_bg.size
        width_av, height_av = avatar.size
        # left, upper, right, lower
        box = []
        color_bg = Image.new(mode="RGBA", size=(width_bg, height_bg), color=(78, 96, 120))
        if width_av > width_bg:
            diff = width_av - width_bg
            box.append(diff / 2)
            box.append(width_av - diff / 2)
        else:
            box.append(0)
            box.append(width_av)
        if height_av > height_bg:
            diff = height_av - height_bg
            box.append(height_av - diff)
            box.insert(1, 0)
        else:
            box.append(height_av)
            box.insert(1, 0)
        cropped_avatar = avatar.crop(tuple(box))
        ca_width, ca_height = cropped_avatar.size
        insert_box = [
            math.floor((width_bg - ca_width) / 2),
            height_bg - ca_height,
            width_bg - math.floor((width_bg - ca_width) / 2),
            height_bg,
        ]
        if (
            insert_box[2] - insert_box[0] < ca_width
            or insert_box[2] > ca_width
            and insert_box[0] == 0
        ):
            insert_box[0] += 1
        elif insert_box[2] - insert_box[0] > ca_width:
            insert_box[2] -= 1
        av_bg.paste(cropped_avatar, tuple(insert_box), cropped_avatar)
        color_bg.paste(av_bg, (0, 0), av_bg)
        if rank is True:
            rank_icon = Image.open(
                Path("Images/ranks", f"rank_{level_rank(level)}.png")
            ).convert("RGBA")
            rank_width, rank_height = rank_icon.size
            resized_dimensions = (int(rank_width * 0.25), int(rank_height * 0.25))
            resized_rank = rank_icon.resize(resized_dimensions)
            draw = ImageDraw.Draw(resized_rank)
            if int(level) < 0:
                pass
            elif int(level) < 10:
                draw.text(
                    (15, 10),
                    text=str(level),
                    font=lvlfont,
                    fill="white",
                    stroke_width=1,
                    stroke_fill=(214, 214, 214),
                )
            elif int(level) >= 10 and int(level) < 100:
                draw.text(
                    (11, 10),
                    text=str(level),
                    font=lvlfont,
                    fill="white",
                    stroke_width=1,
                    stroke_fill=(214, 214, 214),
                )
            elif int(level) >= 100 and int(level) < 1000:
                draw.text(
                    (9, 10),
                    text=str(level),
                    font=lvlfont,
                    fill="white",
                    stroke_width=1,
                    stroke_fill=(214, 214, 214),
                )
            elif int(level) >= 1000 and int(level) < 10000:
                draw.text(
                    (7, 11),
                    text=str(level),
                    font=one_ts_lvl_font,
                    fill="white",
                    stroke_width=1,
                    stroke_fill=(214, 214, 214),
                )
            else:
                draw.text((5, 11), text=str(level), font=one_ts_lvl_font, fill="white")
            color_bg.paste(resized_rank, (100, 10), resized_rank)
            rank_icon.close()
        color_bg = round_edges(color_bg, 15)
        av_bg.close(), avatar.close()  # type: ignore

        return color_bg

    @staticmethod
    async def all_avatars_rendering(avatars: list, urls: list):
        main_avatars = avatars
        avatars_copy = avatars.copy()
        avatar_dict: dict[str, Image.Image] = {}
        for av in urls:
            if av not in avatar_dict:
                avatar_dict[f"{av}"] = avatars_copy[0]
                avatars_copy.pop(0)
        amount_of_avatars = len(urls)
        last_row_avatars = amount_of_avatars % 3
        amount_of_rows = math.ceil(amount_of_avatars / 3)
        av_w, av_h = main_avatars[0].size
        main_height = (av_h + 10) * amount_of_rows + 50
        main_width = av_w * 3 + 60
        logger.debug(
            f"Avatars last row: {last_row_avatars}. Amount of rows: {amount_of_rows}. Main width/height: {main_width}/{main_height}"
        )
        image_font = ImageFont.truetype("Fonts/OpenSans-Bold.ttf", 20)
        color_bg = Image.new(
            mode="RGBA", size=(main_width, main_height), color=(66, 66, 66)
        )
        draw = ImageDraw.Draw(color_bg)
        draw.text((15, 15), text="Avatars", font=image_font, fill="white")
        if last_row_avatars == 0:
            v = 0
        else:
            v = 1
        for row in range(amount_of_rows - 1 * v):
            for i in range(0, 3):
                color_bg.paste(
                    avatar_dict[urls[i + 3 * row]],
                    (20 + (av_w + 10) * i, 50 + (10 + av_h) * row),
                    avatar_dict[urls[i]],
                )
        upper_1 = 50 + (10 + av_h) * (amount_of_rows - 1)
        match last_row_avatars:
            case 2:  # if two avatars on the last row
                for i in range(2):
                    left_1 = 20 + round(av_w / 3) * (1 * (i + 1)) + (av_w) * i
                    color_bg.paste(
                        avatar_dict[urls[-1 * (i + 1)]],
                        (left_1, upper_1),
                        avatar_dict[urls[i]],
                    )
                    logger.debug(f"left: {left_1}, upper: {upper_1}")
            case 1:  # if one avatars on the last row
                left_2 = 20 + (av_w + 10)
                color_bg.paste(
                    avatar_dict[urls[-1]], (left_2, upper_1), avatar_dict[urls[0]]
                )
                logger.debug(f"left: {left_2}, upper: {upper_1}")
            case _:  # if three avatars on the last row
                pass

        return color_bg

def pretty_date(time, time_utc=True):
    """
    Get a datetime object or a int() Epoch timestamp and return a
    pretty string like 'an hour ago', 'Yesterday', '3 months ago',
    'just now', etc
    """

    try:
        tzinf = time.tzinfo
        time = time.replace(tzinfo=None)
    except:
        tzinf = None
    if time_utc:
        now = datetimefix.utcnow()
    else:
        now = datetimefix.now(tz=tzinf)
    if type(time) is int:
        now = datetime.date.today()
        diff = now - datetime.date.fromtimestamp(time)
    elif isinstance(time, datetimefix):
        diff = now - time
    elif not time:
        diff = now - now
    else:
        if time[-1] == "Z":
            time = time[:-1]
        dt = datetimefix.fromisoformat(time)
        diff = now - dt.replace(tzinfo=None)
    second_diff = diff.seconds
    day_diff = diff.days

    if day_diff < 0:
        return ""

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

def pretty_time_delta(seconds: int, timedelta:datetime.timedelta = None):
    if timedelta:
        seconds = timedelta.total_seconds()
    sign_string = "-" if seconds < 0 else ""
    seconds = abs(int(seconds))
    months, seconds = divmod(seconds, 2629800)
    days, seconds = divmod(seconds, 86400)
    hours, seconds = divmod(seconds, 3600)
    minutes, seconds = divmod(seconds, 60)
    if months > 0:
        return "%s%dmo %dd %dh %dm %ds" % (
            sign_string,
            months,
            days,
            hours,
            minutes,
            seconds,
        )
    elif days > 0:
        return "%s%dd %dh %dm %ds" % (sign_string, days, hours, minutes, seconds)
    elif hours > 0:
        return "%s%dh %dm %ds" % (sign_string, hours, minutes, seconds)
    elif minutes > 0:
        return "%s%dm %ds" % (sign_string, minutes, seconds)
    else:
        return "%s%ds" % (sign_string, seconds)


async def init_bot(bot):
    if bot_config.launch_variables['rewrite_userdata']:
        await mysql_main.DatabaseFunctions.iterate_userdata("json_stats")
        bot_config.launch_variables['rewrite_userdata'] = False
    if bot_config.launch_variables['telegram_bot']:
        from telegram_helper.main import MifTelegramReporter
        bot.telegram_bot = MifTelegramReporter(bot.application_id)
        await bot.telegram_bot._run()
    
    bot_config.bot = bot

def countdown_timer(total_milliseconds):
    if total_milliseconds < 0:
        return "∞"
    total_seconds = total_milliseconds / 100
    minutes, seconds = divmod(total_seconds, 60)

    if total_seconds < 20:
        # If less than 20 seconds, show seconds and the decimal part
        return f"{int(total_seconds):02}:{int((total_seconds % 1) * 100):02}ms"
    else:
        # If more than or equal to 20 seconds, show minutes and seconds
        return f"{int(minutes):02}:{int(seconds):02}"

def chess_eval(eval: int, mate=False):
    if eval == None:
        return "None"
    if mate:
        if eval > 0:
            return f"#{eval}"
        else:
            return f"#-{abs(eval)}"
    else:
        if eval > 0:
            return f"+{eval/100:.2f}"
        else:
            return f"{eval/100:.2f}"

def chess_eval_comment(eval: int, mate=False):
    if eval == None:
        return "..."
    if mate:
        return "White mates" if eval > 0 else "Black mates"
    if eval > 0:
        if 40 < eval <= 110:
            return "White is slightly better"
        elif 110 < eval < 500:
            return "White is better"
        elif 500 <= eval < 1000:
            return "White is much better"
        elif 1000 <= eval < 2000:
            return "White is winning"
        elif 2000 <= eval:
            return "White is winning decisively"
        else:
            return "Position is equal"
    else:
        if -110 < eval <= -40:
            return "Black is slightly better"
        elif -500 < eval <= -110:
            return "Black is better"
        elif -1000 < eval <= -500:
            return "Black is much better"
        elif -2000 < eval <= -1000:
            return "Black is winning"
        elif eval <= -2000:
            return "Black is winning decisively"
        else:
            return "Position is equal"

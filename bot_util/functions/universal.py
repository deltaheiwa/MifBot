import calendar
import os
import pytz
import requests
import time
import math
import random
from datetime import (
    datetime as dt,
    timedelta
)
from typing import Literal, Any, Union

from PIL import Image, ImageDraw

from bot_util.misc import Logger
from bot_util import bot_config


logger = Logger(__name__, log_file_path=bot_config.LogFiles.functions_log)

def get_directory_structure(startpath="."):
    excluded_dirs = {
        ".git",
        "node_modules",
        ".mypy_cache",
        ".idea",
        "__pycache__",
        ".ruff_cache",
        ".venv",
        ".run",
        ".vscode"
    }
    structure = ""
    for root, dirs, files in os.walk(startpath):
        dirs[:] = [
            d for d in dirs if d not in excluded_dirs
        ]  # Exclude specified directories
        level = root.replace(startpath, "").count(os.sep)
        indent = " " * 4 * level
        structure += f"{indent}{os.path.basename(root)}/\n"
        subindent = " " * 4 * (level + 1)
        for f in files:
            structure += f"{subindent}{f}\n"
    return structure


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


def sub_sup_text(type: Literal["sub", "sup"], text: str) -> str:
    """
    Converts a text into subscript or superscript. Use "sub" for subscript and "sup" for superscript
    """
    if type == "sub":
        return text.translate(sub_trans)
    elif type == "sup":
        return text.translate(trans)

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


def timestamp_calculate(objT: Union[str, dt], type_of_format: str) -> str:
    """
    Calculates a timestamp based on the given object and type of format.

    Parameters:
    - objT (Union[str, dt]): The object representing the timestamp. It can be either a string or a datetime object.
    - type_of_format (str): The type of format for the timestamp calculation. Possible values are:
        - "Creation Date": Returns the timestamp in the format "mm/dd/yyyy, hh:mm:ss".
        - "Recent Date": Returns the timestamp in the format "Day, Month dd yyyy, hh:mm:ss".
        - "Light Datetime": Returns the timestamp in the format "Month dd yyyy, hh:mm:ss".
        - "Light Date": Returns the timestamp in the format "Month dd yyyy".
        - "Only Date": Returns the timestamp in the format "Month dd, hh:00".

    Returns:
    - str: The calculated timestamp.

    """
    if isinstance(objT, str):
        try:
            date_obj = dt.strptime(objT, "%Y-%m-%dT%H:%M:%S.%fZ")
        except Exception:
            try:
                date_obj = dt.fromisoformat(objT)
            except Exception:
                date_obj = dt.strptime(objT, "%Y-%m-%d %H:%M:%S")
    else:
        date_obj = objT
    try:
        date_str = date_obj.strftime("%Y-%m-%dT%H:%M:%SZ")
    except Exception:
        date_str = date_obj.strftime("%Y-%m-%d %H:%M:%S")
    try:
        epoch = calendar.timegm(time.strptime(date_str, "%Y-%m-%dT%H:%M:%SZ"))
    except Exception:
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

def level_rank(level: int) -> int | str:
    if level < 0:
        return "no"
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

def pretty_date(time: Union[int, str, dt], time_utc=True):
    """
    Returns a human-readable string representing the time difference between the current time and the provided time.
    
    Parameters:
        time (int or str or datetime): The time to calculate the difference from. It can be an integer representing a timestamp, a string in ISO format, or a datetime object.
        time_utc (bool, optional): Whether the provided time is in UTC. Defaults to True.
    
    Returns:
        str: A string representing the time difference. Examples include: "just now", "5 seconds ago", "2 minutes ago", "an hour ago", "Yesterday", "3 days ago", "a week ago", "2 weeks ago", "a month ago", "3 months ago", "a year ago", "2 years ago", or an empty string if the provided time is in the future.
    """
    
    now = dt.utcnow() if time_utc else dt.now()

    if isinstance(time, int):
        time = dt.fromtimestamp(time)
    elif isinstance(time, str):
        if time[-1] == "Z":
            time = time[:-1]
        time = dt.fromisoformat(time)
    else:
        tz_info = time.tzinfo
        now = now.astimezone(tz_info)
    now = now.replace(tzinfo=pytz.utc) if time_utc else now.astimezone(pytz.utc)

    # Convert 'time' to a timezone-aware datetime
    if isinstance(time, int):
        time = dt.fromtimestamp(time, tz=pytz.utc)
    elif isinstance(time, str):
        if time[-1] == "Z":
            time = time[:-1]
        time = dt.fromisoformat(time)
        time = time.replace(tzinfo=pytz.utc)
    elif time.tzinfo is None:
        time = time.replace(tzinfo=pytz.utc)
    
    diff = now - time
    seconds_diff = diff.total_seconds()
    days_diff = diff.days

    if days_diff < 0:
        return ""

    if days_diff == 0:
        if seconds_diff < 10:
            return "just now"
        if seconds_diff < 60:
            return str(round(seconds_diff)) + " seconds ago"
        if seconds_diff < 120:
            return "a minute ago"
        if seconds_diff < 3600:
            return str(round(seconds_diff / 60)) + " minutes ago"
        if seconds_diff < 7200:
            return "an hour ago"
        if seconds_diff < 86400:
            return str(round(seconds_diff / 3600)) + " hours ago"
    if days_diff == 1:
        return "Yesterday"
    if days_diff < 7:
        return str(round(days_diff)) + " days ago"
    if days_diff < 14:
        return "a week ago"
    if days_diff < 31:
        return str(round(days_diff / 7)) + " weeks ago"
    if days_diff < 60:
        return "a month ago"
    if days_diff < 365:
        return str(round(days_diff / 30)) + " months ago"
    if days_diff < 730:
        return "a year ago"
    return str(round(days_diff / 365)) + " years ago"

def pretty_time_delta(seconds: int, time_delta: timedelta = None):
    if time_delta:
        seconds = time_delta.total_seconds()
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
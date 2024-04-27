import asyncio
from typing import Callable

import aiohttp
import json
import math

from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
from io import BytesIO

import discord

from db_data.psql_main import DatabaseFunctions as DF
# from bot_util.debug.timer import Timer
from bot_util.functions.universal import round_edges, level_rank
from bot_util.misc import Logger, api_callers
from bot_util import bot_config

logger = Logger(__name__, log_file_path=bot_config.LogFiles.wolvesville_log)


def history_caching(json_data):
    with open(Path("WovCache", "old_player_cache.json"), "r") as js_f:
        cache_file = json.load(js_f)

    if json_data["id"] not in cache_file:
        cache_file[json_data["id"]] = {}
    cache_file[json_data["id"]][json_data["caching_data"]["time_cached"]] = (
        json_data["rankedSeasonSkill"] if "rankedSeasonSkill" in json_data else None
    )

    with open(Path("WovCache", "old_player_cache.json"), "w") as js_f:
        json.dump(cache_file, js_f, indent=4)


async def download_image(url, session=None):
    if session is None:
        async with aiohttp.ClientSession() as session:
            return await download_image(url, session)
    async with session.get(url) as response:
        if response.status == 200:
            return await response.read()
        # Handle errors as needed


async def download_images(urls):
    async with aiohttp.ClientSession() as session:
        tasks = [download_image(url, session) for url in urls]
        return await asyncio.gather(*tasks)


async def open_image_from_url(url: str) -> Image.Image:
    response = await download_image(url=url)
    return Image.open(BytesIO(response)).convert('RGBA')


async def open_images_from_urls(urls: list[str]) -> dict[str, Image.Image]:
    responses = await download_images(urls)
    images = [Image.open(BytesIO(response)).convert('RGBA') for response in responses]
    return dict(zip(urls, images))


def resize_and_crop_avatar(avatar: Image.Image, bg_width: int, bg_height: int) -> Image.Image:
    width, height = avatar.size

    # Resizing logic
    if width > bg_width:
        diff = width - bg_width
        left = diff / 2
        right = width - diff / 2
    else:
        left, right = 0, width

    if height > bg_height:
        diff = height - bg_height
        upper = height - diff
        lower = 0
    else:
        upper, lower = 0, height

    return avatar.crop((left, upper, right, lower))


def insert_avatar_into_bg(cropped_avatar: Image.Image, bg: Image.Image) -> Image.Image:
    ca_width, ca_height = cropped_avatar.size
    bg_width, bg_height = bg.size

    insert_box = [
        math.floor((bg_width - ca_width) / 2),
        bg_height - ca_height,
        bg_width - math.floor((bg_width - ca_width) / 2),
        bg_height
    ]

    if (insert_box[2] - insert_box[0] < ca_width or
            insert_box[2] > ca_width and insert_box[0] == 0):
        insert_box[0] += 1
    elif insert_box[2] - insert_box[0] > ca_width:
        insert_box[2] -= 1

    bg.paste(cropped_avatar, tuple(insert_box), cropped_avatar)
    return bg


def add_rank_to_avatar(bg: Image.Image, level: int) -> Image.Image:
    rank_icon = Image.open(Path("Images/ranks", f"rank_{level_rank(level)}.png")).convert("RGBA")
    rank_width, rank_height = rank_icon.size
    resized_dimensions = (int(rank_width * 0.25), int(rank_height * 0.25))
    resized_rank = rank_icon.resize(resized_dimensions)

    draw = ImageDraw.Draw(resized_rank)
    lvlfont = ImageFont.truetype("Fonts/OpenSans-Bold.ttf", 12)
    one_ts_lvl_font = ImageFont.truetype("Fonts/OpenSans-Bold.ttf", 10)

    if level < 0:
        pass
    elif level < 10:
        draw.text((15, 10), str(level), font=lvlfont, fill="white", stroke_width=1, stroke_fill=(214, 214, 214))
    elif level < 100:
        draw.text((11, 10), str(level), font=lvlfont, fill="white", stroke_width=1, stroke_fill=(214, 214, 214))
    elif level < 1000:
        draw.text((9, 10), str(level), font=lvlfont, fill="white", stroke_width=1, stroke_fill=(214, 214, 214))
    elif level < 10000:
        draw.text((7, 11), str(level), font=one_ts_lvl_font, fill="white", stroke_width=1, stroke_fill=(214, 214, 214))
    else:
        draw.text((5, 11), str(level), font=one_ts_lvl_font, fill="white")

    # Paste rank icon onto the background
    bg.paste(resized_rank, (100, 10), resized_rank)
    rank_icon.close()

    return bg


async def avatar_rendering(avatar: Image.Image, level: int = 0, rank: bool = True) -> Image.Image:
    av_bg = Image.open(Path("Images", "wolvesville_small_night_AVATAR.png")).convert("RGBA")

    cropped_avatar = resize_and_crop_avatar(avatar, *av_bg.size)

    color_bg = Image.new("RGBA", av_bg.size, (78, 96, 120))
    combined_img = insert_avatar_into_bg(cropped_avatar, av_bg)
    color_bg.paste(combined_img, (0, 0), combined_img)

    if rank:
        color_bg = add_rank_to_avatar(color_bg, level)

    av_bg.close()
    avatar.close()

    color_bg = round_edges(color_bg, 15)
    return color_bg


async def bulk_avatar_rendering(avatars: dict, level: int = 0, rank: bool = True) -> dict[str, Image.Image]:
    tasks = [avatar_rendering(avatar, level, rank) for avatar in avatars.values()]
    results = await asyncio.gather(*tasks)
    return dict(zip(avatars.keys(), results))


def all_avatars_rendering(avatars: dict[str, Image.Image], urls: list):
    amount_of_avatars = len(urls)
    last_row_avatars = amount_of_avatars % 3
    amount_of_rows = math.ceil(amount_of_avatars / 3)
    av_w, av_h = avatars[urls[0]].size
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
                avatars[urls[i + 3 * row]],
                (20 + (av_w + 10) * i, 50 + (10 + av_h) * row),
                avatars[urls[i]],
            )
    upper_1 = 50 + (10 + av_h) * (amount_of_rows - 1)
    match last_row_avatars:
        case 2:  # if two avatars on the last row
            for i in range(2):
                left_1 = 20 + round(av_w / 3) * (1 * (i + 1)) + av_w * i
                color_bg.paste(
                    avatars[urls[-1 * (i + 1)]],
                    (left_1, upper_1),
                    avatars[urls[i]],
                )
                logger.debug(f"left: {left_1}, upper: {upper_1}")
        case 1:  # if one avatar on the last row
            left_2 = 20 + (av_w + 10)
            color_bg.paste(
                avatars[urls[-1]], (left_2, upper_1), avatars[urls[0]]
            )
            logger.debug(f"left: {left_2}, upper: {upper_1}")
        case _:  # if three avatars on the last row
            pass
    return color_bg


def check_clan_command_invocation_validity(server_id: str, gettext: Callable, user_info: tuple) -> tuple[discord.Embed | None, bool]:
    """
    Check if the clan command invocation is valid
    :param server_id: id of the server
    :param gettext: gettext function
    :param user_info: Tuple of user id and user roles
    :return: Tuple of Embed and boolean. Always has an Embed if the boolean is False, and None if the boolean is True
    """
    _ = gettext
    user_id, user_roles = user_info
    server_check = DF.get_wov_clan_by_server_id(server_id)
    if server_check is None:  # If server is not connected to any clan
        embed_err = discord.Embed(
            title=_("Error"),
            description=_("This server is not connected to any Wolvesville clan"),
            color=bot_config.CustomColors.red,
        )
        return embed_err, False

    leader_info = DF.get_wov_clan_discord_leaders(server_id)
    if (
            user_id not in leader_info["leaders"]
            and leader_info["roles"] not in user_roles
    ):  # If user is not the leader of the clan
        embed_err = discord.Embed(
            title=_("Error"),
            description=_(
                "You're not the leader of the clan connected to this server"
            ),
            color=bot_config.CustomColors.red,
        )
        return embed_err, False
    return None, True


async def dump_quests():
    caller = api_callers.WovAPICaller()
    quests_data = await caller.add_to_queue(
        api_callers.WovApiCall.get_all_quests
    )
    if quests_data:
        DF.store_all_quests(quests_data)
        logger.debug("Quests data dumped to database.")

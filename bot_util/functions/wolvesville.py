import json
import requests
import math

from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
from io import BytesIO

from bot_util.functions.universal import round_edges, level_rank
from bot_util.misc import Logger
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


async def avatar_rendering(image_URL: str, level: int = 0, rank: bool = True):
    """
    This one is fucked up
    """
    av_bg = Image.open(
        Path("Images", "wolvesville_small_night_AVATAR.png")
    ).convert("RGBA")
    url_response = requests.get(image_URL)
    avatar = Image.open(BytesIO(url_response.content)).convert("RGBA")
    lvlfont = ImageFont.truetype("Fonts/OpenSans-Bold.ttf", 12)
    one_ts_lvl_font = ImageFont.truetype("Fonts/OpenSans-Bold.ttf", 10)
    width_bg, height_bg = av_bg.size
    width_av, height_av = avatar.size
    # left, upper, right, lower
    box = []
    color_bg = Image.new(
        mode="RGBA", size=(width_bg, height_bg), color=(78, 96, 120)
    )
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
    av_bg.close(), avatar.close()

    return color_bg


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
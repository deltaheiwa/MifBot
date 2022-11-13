from fileinput import filename
import discord
import berserk
import chess
import chess.svg
from cairosvg import svg2png
import lichess.api
import base64
import requests
import aiohttp
import aiodns
import os
from datetime import datetime as class_dt
import time
import calendar
import array as arr
from humanfriendly import format_timespan
import creds
import config
from functions import *
from io import BytesIO
from PIL import Image
from pathlib import Path
import traceback
import nest_asyncio
from discord.ext import commands


token = creds.LI_API_TOKEN
session = berserk.TokenSession(token)
client = berserk.Client(session=session)

logger = logging.getLogger(__name__)
coloredlogs.install(level='INFO', logger=logger)
logger.setLevel(logging.INFO)
formatter = logging.Formatter('%(asctime)s:%(levelname)s --- %(message)s')
file_handler = logging.FileHandler(config.chess_log)
console_formatter = CustomFormatter()
stream_handler = logging.StreamHandler()
stream_handler.setFormatter(console_formatter)
file_handler.setFormatter(formatter)
logger.addHandler(file_handler)

'''
async def delete_file(num):
    try:
        if num >= len(game_channels_active):
            file_to_rem = Path(f"/Images/chessOutput/output{num}.png")
            await file_to_rem.unlink()
    except PermissionError:
        os.remove(f'/Images/chessOutput/output{num}.png')
'''


'''
async def stopstr(request, channel_id):
    try:
        await request.close()
        await asyncio.sleep(0.5)
    except:
        await asyncio.sleep(0)
    finally:
        print("Its closed")
        if channel_id in game_channels_active:
            game_channels_active.remove(channel_id)
            print("channel_id removed successfully")
        await asyncio.sleep(0)
'''
'''
class ButtonsTV(discord.ui.View):
    def __init__(self, object, channel_id, *, timeout=180):
        super().__init__(timeout=timeout)
        self.object = object
        self.channel_id = channel_id
    
    

    @discord.ui.button(label="Stop streaming", style=discord.ButtonStyle.red)
    async def func_button(self, button: discord.ui.Button, interaction: discord.Interaction):
        button.style = discord.ButtonStyle.gray
        # And i cant pass requests object here
        await stopstr(self.object, self.channel_id)
        button.disabled = True
        await interaction.response.edit_message(view=self)
'''

class Chess(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def cog_load(self):
        print("Chess cog loaded successfully!")

    @commands.command(aliases=["litop10", "li-top10", "litop", "li-top"])
    async def lichesstop10(self, ctx, mode=None):
        if mode == None:
            mode = "rapid"
        try:
            top10 = client.users.get_leaderboard(mode, count=11)
            embed = discord.Embed(
                title=f"Top 10 in {mode}",
                color=discord.Color.from_rgb(0, 255, 255),
            )
            x = 0
            for x in range(10):
                print(top10[x])
                embed.add_field(
                    name=f"Top {x+1}",
                    value=f"[{top10[x]['username']}](https://lichess.org/@/{top10[x]['username']}) with rating {top10[x]['perfs'][mode]['rating']}",
                    inline=False,
                )
            embed.set_footer(text=f"Requested by {ctx.message.author}")
            await ctx.send(embed=embed)
            add_command_stats(ctx.message.author)
        except Exception as e:
            await ctx.send("Wrong mode")
            print(e)
    global game_id_link

    def game_id_link(id):
        game_link = f"(https://lichess.org/{id})"
        return game_link

    @commands.command(aliases=["liplayer", "li-player", "li-p"])
    async def lichessplayer(self, ctx, nickname=None, mode=None):
        empty = discord.utils.get(self.bot.emojis, name="empty")
        patron = discord.utils.get(self.bot.emojis, name="patron")
        if nickname == None:
            embed = discord.Embed(title="Please input a lichess username")
            await ctx.send(embed=embed)
        else:
            if mode == None:
                try:
                    player = client.users.get_public_data(nickname)
                    print(player)
                    nickname = player['username']
                    # ! online = player["online"]
                    online = False
                    thumbnail = "https://cdn.discordapp.com/attachments/874304187834454106/906300327270174741/Lichess.png"
                    try:
                        title = player["title"]
                        username = nickname + "    **" + \
                            str(title) + " TITLE**"
                    except:
                        username = nickname
                    try:
                        if player["patron"] == True:
                            username = username + " " + str(patron)
                            thumbnail = "https://cdn.discordapp.com/attachments/874304187834454106/906898579115892736/2021-11-07_152824.png"
                    except:
                        username = username
                    try:
                        if player["disabled"] == True:
                            username = username + "      ***DISABLED***"
                    except:
                        username = username
                    embed = discord.Embed(
                        title=username,
                        description="Everything I could find about "
                        + nickname
                        + " on lichess",
                        color=discord.Color.from_rgb(0, 255, 255),
                    )
                    embed.set_thumbnail(url=thumbnail)
                    embed.add_field(name="Username",
                                    value=str(player["username"]))
                    try:
                        if player["profile"]["country"].lower() == "_rainbow":
                            country_flag = ":rainbow_flag:"
                        else:
                            country_flag = (
                                ":flag_" +
                                str(player["profile"]["country"]).lower() + ":"
                            )
                    except:
                        country_flag = ":united_nations:"
                    embed.add_field(name="Country", value=country_flag)
                    if online == True:
                        isOnline = ":green_circle:"
                    else:
                        isOnline = ":black_circle:"
                    embed.add_field(name="Online", value=isOnline)
                    try:
                        embed.add_field(
                            name="Bio", value=player["profile"]["bio"], inline=False
                        )
                    except:
                        embed.add_field(
                            name="Bio", value="*No info provided*", inline=False
                        )
                    seenAt = player["seenAt"]
                    seenTime = pretty_date(seenAt)
                    if online == True:
                        seen_value = "Player is online"
                    else:
                        seen_value = str(seenTime)
                    embed.add_field(name="Last active", value=seen_value)
                    createdAt = player["createdAt"]
                    createdTime = timestamp_calculate(createdAt, "Creation Date")
                    embed.add_field(name="Created at",
                                    value=createdTime + " UTC")
                    # playtime_total = str(datetime.timedelta(seconds=player['playTime']['total']))
                    playtime_total = format_timespan(
                        player["playTime"]["total"])
                    try:
                        tv_total = format_timespan(player["playTime"]["tv"])
                    except:
                        tv_total = "0 seconds"
                    embed.add_field(name="Total playtime",
                                    value=f"{playtime_total}\n**Time on TV: **{tv_total}")
                    embed.add_field(name=empty, value=empty, inline=False)
                    rated_games = player["count"]["rated"]
                    all_games = player["count"]["all"]
                    ai_games = player["count"]["ai"]
                    wins = player["count"]["win"]
                    losses = player["count"]["loss"]
                    draws = player["count"]["draw"]
                    rated_percentage = rated_games * 100 / all_games
                    ai_percentage = ai_games * 100 / all_games
                    winrate = wins * 100 / all_games
                    lossrate = losses * 100 / all_games
                    drawrate = draws * 100 / all_games
                    embed.add_field(
                        name="General stats",
                        value=  # "Completion Rate: **"
                        # + str(player["completionRate"])
                        # + "%**"
                        "All games: **"
                        + str(all_games)
                        + "**"
                        + "\n Rated games: **"
                        + str(rated_games)
                        + " ("
                        + str(round(rated_percentage, 1))
                        + "%)**"
                        + "\n Against AI: **"
                        + str(ai_games)
                        + " ("
                        + str(round(ai_percentage, 2))
                        + "%)**"
                        + "\n Wins: **"
                        + str(wins)
                        + " ("
                        + str(round(winrate, 1))
                        + "%)**"
                        + "\n Losses: **"
                        + str(losses)
                        + " ("
                        + str(round(lossrate, 1))
                        + "%)**"
                        + "\n Draws: **"
                        + str(draws)
                        + " ("
                        + str(round(drawrate, 1))
                        + "%)**",
                    )

                    global lrating
                    lrating = ""
                    print(len(player["perfs"]))
                    a = []
                    for key in player["perfs"]:
                        print(key)
                        a.append(key)
                    for i in a:
                        try:
                            if i == "storm" or i == "streak" or i == "racer":
                                points = str(player["perfs"][i]["score"])
                                try:
                                    if i == "storm":
                                        tempVar = (
                                            "\n Puzzle Storm: **" + points + " points**"
                                        )
                                    elif i == "streak":
                                        tempVar = (
                                            "\n Puzzle Streak: **"
                                            + points
                                            + " points**"
                                        )
                                except:
                                    tempVar = None
                                    pass
                            else:
                                srating = str(player["perfs"][i]["rating"])
                                try:
                                    if i == "ultraBullet":
                                        tempVar = "\n Ultrabullet: **" + srating + "**"
                                    elif i == "bullet":
                                        tempVar = "\n Bullet: **" + srating + "**"
                                    elif i == "blitz":
                                        tempVar = "\n Blitz: **" + srating + "**"
                                    elif i == "rapid":
                                        tempVar = "\n Rapid: **" + srating + "**"
                                    elif i == "classical":
                                        tempVar = "\n Classical: **" + srating + "**"
                                    elif i == "correspondence":
                                        tempVar = (
                                            "\n Correspondence: **" + srating + "**"
                                        )
                                    elif i == "crazyhouse":
                                        tempVar = "\n Crazyhouse: **" + srating + "**"
                                    elif i == "chess960":
                                        tempVar = "\n Chess960: **" + srating + "**"
                                    elif i == "kingOfTheHill":
                                        tempVar = (
                                            "\n King of the Hill: **" + srating + "**"
                                        )
                                    elif i == "threeCheck":
                                        tempVar = "\n Three-check: **" + srating + "**"
                                    elif i == "antichess":
                                        tempVar = "\n Antichess: **" + srating + "**"
                                    elif i == "atomic":
                                        tempVar = "\n Atomic: **" + srating + "**"
                                    elif i == "horde":
                                        tempVar = "\n Horde: **" + srating + "**"
                                    elif i == "racingKings":
                                        tempVar = "\n Racing Kings: **" + srating + "**"
                                    elif i == "puzzle":
                                        tempVar = "\n Puzzles: **" + srating + "**"
                                except:
                                    tempVar = None
                                    pass
                                lrating = lrating + tempVar
                        except:
                            print("failed")
                            pass
                    embed.add_field(name="Rating", value=lrating)
                    embed.add_field(name="Link", value=str(
                        player["url"]), inline=False)
                    embed.set_footer(text="Requested by " + str(ctx.author))
                    await ctx.send(embed=embed)
                    add_command_stats(ctx.message.author)
                except Exception as e:
                    logger.exception("Couldn't find a player or unknown problem")
                    embed = discord.Embed(
                        title="Couldn't find any user with that username",
                        color=discord.Color.from_rgb(255, 0, 0),
                    )
                    await ctx.send(embed=embed)
                    add_command_stats(ctx.message.author)
            elif mode != None:
                exist = False
                gamesNotZero = False
                try:
                    player = client.users.get_public_data(nickname)
                    print(player)
                    print()
                    exist = True
                    nickname = player['username']
                except:
                    embed = discord.Embed(
                        title="Couldn't find any user with that username",
                        color=discord.Color.from_rgb(255, 0, 0),
                    )
                    await ctx.send(embed=embed)
                if exist == True:
                    try:
                        mode = mode.lower()
                        if mode == "kingofthehill":
                            mode = "kingOfTheHill"
                        elif mode == "threecheck":
                            mode == "threeCheck"
                        elif mode == "racingkings":
                            mode == "racingKings"
                        elif mode == "ultrabullet":
                            mode = "ultraBullet"
                        print(mode)
                        try:
                            playerPerfinfo = client.users.get_user_performance(
                                nickname, mode)
                            playerPerf = playerPerfinfo['stat']
                            print(playerPerf)
                            streak_sc = playerPerf["resultStreak"]
                            playst = playerPerf["playStreak"]
                        except Exception as e:
                            print(e)
                            pass
                        modeInfo = player["perfs"][mode]
                        embed = discord.Embed(
                            title=nickname,
                            description="Everything I could find about **"
                            + mode
                            + "** details",
                            color=discord.Color.from_rgb(0, 255, 255),
                        )
                        try:
                            if player['perfs'][mode]['games'] != 0:
                                gamesNotZero = True
                            else:
                                gamesNotZero = False
                        except:
                            gamesNotZero = False
                        if gamesNotZero == True:
                            try:
                                arrow = None
                                rd_warning = None
                                bestrw_op = None
                                try:
                                    date_obj_high = class_dt.strptime(
                                        playerPerf['highest']['at'], "%Y-%m-%dT%H:%M:%S.%fZ")
                                    date_str_high = date_obj_high.strftime(
                                        "%Y-%m-%dT%H:%M:%SZ")
                                    epoch_high = calendar.timegm(time.strptime(
                                        date_str_high, '%Y-%m-%dT%H:%M:%SZ'))
                                    high_link = "(https://lichess.org/" + \
                                        str(playerPerf['highest']
                                            ['gameId'])+")"
                                    highest_rating = str(playerPerf['highest']['int']) + " at " + str(time.strftime(
                                        '%A, %m/%d/%Y, %H:%M:%S', time.localtime(epoch_high)))+"  [Link]"+high_link
                                except:
                                    highest_rating = "Not enough games played"
                                try:
                                    date_obj_low = class_dt.strptime(
                                        playerPerf['lowest']['at'], "%Y-%m-%dT%H:%M:%S.%fZ")
                                    date_str_low = date_obj_low.strftime(
                                        "%Y-%m-%dT%H:%M:%SZ")
                                    epoch_low = calendar.timegm(time.strptime(
                                        date_str_low, '%Y-%m-%dT%H:%M:%SZ'))
                                    low_link = "(https://lichess.org/" + \
                                        str(playerPerf['lowest']['gameId'])+")"
                                    lowest_rating = str(playerPerf['lowest']['int']) + " at " + str(
                                        time.strftime('%A, %m/%d/%Y, %H:%M:%S', time.localtime(epoch_low)))+"  [Link]"+low_link
                                except:
                                    lowest_rating = "Not enough games played"
                                try:
                                    cwinst_from_obj = class_dt.strptime(
                                        streak_sc['win']['cur']['from']['at'], "%Y-%m-%dT%H:%M:%S.%fZ")
                                    cwinst_from_str = cwinst_from_obj.strftime(
                                        "%Y-%m-%dT%H:%M:%SZ")
                                    cwinst_from_epoch = calendar.timegm(
                                        time.strptime(cwinst_from_str, '%Y-%m-%dT%H:%M:%SZ'))
                                    cwinst_from_comp = str(
                                        time.strftime('%A, %m/%d/%Y, %H:%M:%S', time.localtime(cwinst_from_epoch)))
                                    cwinst_to_obj = class_dt.strptime(
                                        streak_sc['win']['cur']['to']['at'], "%Y-%m-%dT%H:%M:%S.%fZ")
                                    cwinst_to_str = cwinst_to_obj.strftime(
                                        "%Y-%m-%dT%H:%M:%SZ")
                                    cwinst_to_epoch = calendar.timegm(
                                        time.strptime(cwinst_to_str, "%Y-%m-%dT%H:%M:%SZ"))
                                    cwinst_to_comp = str(
                                        time.strftime('%A, %m/%d/%Y, %H:%M:%S', time.localtime(cwinst_to_epoch)))
                                    cwinst_from_link = "(https://lichess.org/" + \
                                        str(streak_sc['win']['cur']
                                            ['from']['gameId'])+")"
                                    cwinst_to_link = "(https://lichess.org/" + \
                                        str(streak_sc['win']['cur']
                                            ['to']['gameId'])+")"
                                    cwinst = "\n Current Winning streak: **" + \
                                        str(streak_sc['win']['cur']['v']) + " [from]" + cwinst_from_link + " " + \
                                        cwinst_from_comp + \
                                        " [to]" + cwinst_to_link + \
                                        " " + cwinst_to_comp + "** "
                                except Exception as e:
                                    print(e)
                                    cwinst = "No current winning streak"
                                try:
                                    lwinst_from_obj = class_dt.strptime(
                                        streak_sc['win']['max']['from']['at'], "%Y-%m-%dT%H:%M:%S.%fZ")
                                    lwinst_from_str = lwinst_from_obj.strftime(
                                        "%Y-%m-%dT%H:%M:%SZ")
                                    lwinst_from_epoch = calendar.timegm(
                                        time.strptime(lwinst_from_str, '%Y-%m-%dT%H:%M:%SZ'))
                                    lwinst_from_comp = str(
                                        time.strftime('%A, %m/%d/%Y, %H:%M:%S', time.localtime(lwinst_from_epoch)))
                                    lwinst_to_obj = class_dt.strptime(
                                        streak_sc['win']['max']['to']['at'], "%Y-%m-%dT%H:%M:%S.%fZ")
                                    lwinst_to_str = lwinst_to_obj.strftime(
                                        "%Y-%m-%dT%H:%M:%SZ")
                                    lwinst_to_epoch = calendar.timegm(
                                        time.strptime(lwinst_to_str, "%Y-%m-%dT%H:%M:%SZ"))
                                    lwinst_to_comp = str(
                                        time.strftime('%A, %m/%d/%Y, %H:%M:%S', time.localtime(lwinst_to_epoch)))
                                    lwinst_from_link = "(https://lichess.org/" + \
                                        str(streak_sc['win']['max']
                                            ['from']['gameId'])+")"
                                    lwinst_to_link = "(https://lichess.org/" + \
                                        str(streak_sc['win']['max']
                                            ['to']['gameId'])+")"
                                    lwinst = "\n Longest Winning streak: **" + \
                                        str(streak_sc['win']['max']['v']) + " [from]" + lwinst_from_link + " " + \
                                        lwinst_from_comp + \
                                        " [to]" + lwinst_to_link + \
                                        " " + lwinst_to_comp + "** "
                                except Exception as e:
                                    print(e)
                                    lwinst = "No longest winning streak"
                                try:
                                    cwinst_from_obj = class_dt.strptime(
                                        streak_sc['win']['cur']['from']['at'], "%Y-%m-%dT%H:%M:%S.%fZ")
                                    cwinst_from_str = cwinst_from_obj.strftime(
                                        "%Y-%m-%dT%H:%M:%SZ")
                                    cwinst_from_epoch = calendar.timegm(
                                        time.strptime(cwinst_from_str, '%Y-%m-%dT%H:%M:%SZ'))
                                    cwinst_from_comp = str(
                                        time.strftime('%A, %m/%d/%Y, %H:%M:%S', time.localtime(cwinst_from_epoch)))
                                    cwinst_to_obj = class_dt.strptime(
                                        streak_sc['win']['cur']['to']['at'], "%Y-%m-%dT%H:%M:%S.%fZ")
                                    cwinst_to_str = cwinst_to_obj.strftime(
                                        "%Y-%m-%dT%H:%M:%SZ")
                                    cwinst_to_epoch = calendar.timegm(
                                        time.strptime(cwinst_to_str, "%Y-%m-%dT%H:%M:%SZ"))
                                    cwinst_to_comp = str(
                                        time.strftime('%A, %m/%d/%Y, %H:%M:%S', time.localtime(cwinst_to_epoch)))
                                    cwinst_from_link = "(https://lichess.org/" + \
                                        str(streak_sc['win']['cur']
                                            ['from']['gameId'])+")"
                                    cwinst_to_link = "(https://lichess.org/" + \
                                        str(streak_sc['win']['cur']
                                            ['to']['gameId'])+")"
                                    cwinst = "\n Current Winning streak: **" + \
                                        str(streak_sc['win']['cur']['v']) + " [from]" + cwinst_from_link + " " + \
                                        cwinst_from_comp + \
                                        " [to]" + cwinst_to_link + \
                                        " " + cwinst_to_comp + "** "
                                except Exception as e:
                                    print(e)
                                    cwinst = "No current winning streak"
                                try:
                                    lwinst_from_obj = class_dt.strptime(
                                        streak_sc['win']['max']['from']['at'], "%Y-%m-%dT%H:%M:%S.%fZ")
                                    lwinst_from_str = lwinst_from_obj.strftime(
                                        "%Y-%m-%dT%H:%M:%SZ")
                                    lwinst_from_epoch = calendar.timegm(
                                        time.strptime(lwinst_from_str, '%Y-%m-%dT%H:%M:%SZ'))
                                    lwinst_from_comp = str(
                                        time.strftime('%A, %m/%d/%Y, %H:%M:%S', time.localtime(lwinst_from_epoch)))
                                    lwinst_to_obj = class_dt.strptime(
                                        streak_sc['win']['max']['to']['at'], "%Y-%m-%dT%H:%M:%S.%fZ")
                                    lwinst_to_str = lwinst_to_obj.strftime(
                                        "%Y-%m-%dT%H:%M:%SZ")
                                    lwinst_to_epoch = calendar.timegm(
                                        time.strptime(lwinst_to_str, "%Y-%m-%dT%H:%M:%SZ"))
                                    lwinst_to_comp = str(
                                        time.strftime('%A, %m/%d/%Y, %H:%M:%S', time.localtime(lwinst_to_epoch)))
                                    lwinst_from_link = "(https://lichess.org/" + \
                                        str(streak_sc['win']['max']
                                            ['from']['gameId'])+")"
                                    lwinst_to_link = "(https://lichess.org/" + \
                                        str(streak_sc['win']['max']
                                            ['to']['gameId'])+")"
                                    lwinst = "\n Longest Winning streak: **" + \
                                        str(streak_sc['win']['max']['v']) + " [from]" + lwinst_from_link + " " + \
                                        lwinst_from_comp + \
                                        " [to]" + lwinst_to_link + \
                                        " " + lwinst_to_comp + "** "
                                except Exception as e:
                                    print(e)
                                    lwinst = "No longest winning streak"
                                try:
                                    clossst_from_obj = class_dt.strptime(
                                        streak_sc['loss']['cur']['from']['at'], "%Y-%m-%dT%H:%M:%S.%fZ")
                                    clossst_from_str = clossst_from_obj.strftime(
                                        "%Y-%m-%dT%H:%M:%SZ")
                                    clossst_from_epoch = calendar.timegm(
                                        time.strptime(clossst_from_str, '%Y-%m-%dT%H:%M:%SZ'))
                                    clossst_from_comp = str(
                                        time.strftime('%A, %m/%d/%Y, %H:%M:%S', time.localtime(clossst_from_epoch)))
                                    clossst_to_obj = class_dt.strptime(
                                        streak_sc['loss']['cur']['to']['at'], "%Y-%m-%dT%H:%M:%S.%fZ")
                                    clossst_to_str = clossst_to_obj.strftime(
                                        "%Y-%m-%dT%H:%M:%SZ")
                                    clossst_to_epoch = calendar.timegm(
                                        time.strptime(clossst_to_str, "%Y-%m-%dT%H:%M:%SZ"))
                                    clossst_to_comp = str(
                                        time.strftime('%A, %m/%d/%Y, %H:%M:%S', time.localtime(clossst_to_epoch)))
                                    clossst_from_link = "(https://lichess.org/" + \
                                        str(streak_sc['loss']['cur']
                                            ['from']['gameId'])+")"
                                    clossst_to_link = "(https://lichess.org/" + \
                                        str(streak_sc['loss']['cur']
                                            ['to']['gameId'])+")"
                                    clossst = "\n Current Winning streak: **" + \
                                        str(streak_sc['loss']['cur']['v']) + " [from]" + clossst_from_link + " " + \
                                        clossst_from_comp + \
                                        " [to]" + clossst_to_link + \
                                        " " + clossst_to_comp + "** "
                                except Exception as e:
                                    print(e)
                                    clossst = "No current losing streak"
                                try:
                                    llossst_from_obj = class_dt.strptime(
                                        streak_sc['loss']['max']['from']['at'], "%Y-%m-%dT%H:%M:%S.%fZ")
                                    llossst_from_str = llossst_from_obj.strftime(
                                        "%Y-%m-%dT%H:%M:%SZ")
                                    llossst_from_epoch = calendar.timegm(
                                        time.strptime(llossst_from_str, '%Y-%m-%dT%H:%M:%SZ'))
                                    llossst_from_comp = str(
                                        time.strftime('%A, %m/%d/%Y, %H:%M:%S', time.localtime(llossst_from_epoch)))
                                    llossst_to_obj = class_dt.strptime(
                                        streak_sc['loss']['max']['to']['at'], "%Y-%m-%dT%H:%M:%S.%fZ")
                                    llossst_to_str = llossst_to_obj.strftime(
                                        "%Y-%m-%dT%H:%M:%SZ")
                                    llossst_to_epoch = calendar.timegm(
                                        time.strptime(llossst_to_str, "%Y-%m-%dT%H:%M:%SZ"))
                                    llossst_to_comp = str(
                                        time.strftime('%A, %m/%d/%Y, %H:%M:%S', time.localtime(llossst_to_epoch)))
                                    llossst_from_link = "(https://lichess.org/" + \
                                        str(streak_sc['loss']['max']
                                            ['from']['gameId'])+")"
                                    llossst_to_link = "(https://lichess.org/" + \
                                        str(streak_sc['loss']['max']
                                            ['to']['gameId'])+")"
                                    llossst = "\n Longest Losing streak: **" + \
                                        str(streak_sc['loss']['max']['v']) + " [from]" + llossst_from_link + " " + \
                                        llossst_from_comp + \
                                        " [to]" + llossst_to_link + \
                                        " " + llossst_to_comp + "** "
                                except Exception as e:
                                    print(e)
                                    llossst = "No longest losing streak"
                                try:
                                    bestr = playerPerf['bestWins']['results']
                                    bestr_prime = enumerate(bestr)
                                    # print(list(bestr_prime))
                                    bestrw_op = ""
                                    for i, item in bestr_prime:
                                        opData = item['opId']
                                        date_obj_br = class_dt.strptime(
                                            item['at'], "%Y-%m-%dT%H:%M:%S.%fZ")
                                        date_str_br = date_obj_br.strftime(
                                            "%Y-%m-%dT%H:%M:%SZ")
                                        epoch_br = calendar.timegm(time.strptime(
                                            date_str_br, '%Y-%m-%dT%H:%M:%SZ'))
                                        op_br_comp = "["+str(time.strftime(
                                            '%A, %m/%d/%Y, %H:%M:%S', time.localtime(epoch_br)))+"]"
                                        game_link = "(https://lichess.org/" + \
                                            str(item['gameId'])+")"
                                        opName = str(opData['name'])
                                        if opData['title'] is None:
                                            opTitle = " "
                                        else:
                                            opTitle = "**" + \
                                                str(opData['title'])+"** "
                                        opNameLink = "["+opName+"]" + \
                                            "(https://lichess.org/@/"+opName+")"
                                        rating = " with rating **" + \
                                            str(item['opInt'])+"**"
                                        finish = f"\n Against {opTitle}{opNameLink}{rating} on {op_br_comp}{game_link}"
                                        print(finish)
                                        bestrw_op += finish
                                except Exception as e:
                                    print(traceback.format_exc())
                                    bestrw_op = "**No information found**"
                                    print(e)
                                try:
                                    worstr = playerPerf['worstLosses']['results']
                                    worstr_prime = enumerate(worstr)
                                    # print(list(worstr_prime))
                                    worstrw_op = ""
                                    for i, item in worstr_prime:
                                        opData = item['opId']
                                        # date_obj_br = datetime.datetime.strptime(
                                        #     item['at'], "%Y-%m-%dT%H:%M:%S.%fZ")
                                        # date_str_br = date_obj_br.strftime(
                                        #     "%Y-%m-%dT%H:%M:%SZ")
                                        # epoch_br = calendar.timegm(time.strptime(
                                        #     date_str_br, '%Y-%m-%dT%H:%M:%SZ'))
                                        # op_br_comp = "["+str(time.strftime(
                                        #     '%A, %m/%d/%Y, %H:%M:%S', time.localtime(epoch_br)))+"]"
                                        op_br_comp = f"[{timestamp_calculate(objT=item['at'], type_of_format='Recent Date')}]"
                                        game_link = "(https://lichess.org/" + \
                                            str(item['gameId'])+")"
                                        opName = str(opData['name'])
                                        if opData['title'] is None:
                                            opTitle = " "
                                        else:
                                            opTitle = "**" + \
                                                str(opData['title'])+"** "
                                        opNameLink = "["+opName+"]" + \
                                            "(https://lichess.org/@/"+opName+")"
                                        rating = " with rating **" + \
                                            str(item['opInt'])+"**"
                                        finish = f"\n Against {opTitle}{opNameLink}{rating} on {op_br_comp}{game_link}"
                                        print(finish)
                                        worstrw_op += finish
                                except Exception as e:
                                    print(e)
                                    bestrw_op = "**No information found**"
                                try:
                                    playstGL = playst["nb"]["max"]
                                    Lstreak_fromTime = timestamp_calculate(
                                        playstGL['from']['at'])
                                    Lstreak_fromGame = game_id_link(
                                        playstGL['from']['gameId'])
                                    Lstreak_toTime = timestamp_calculate(
                                        playstGL['to']['at'])
                                    Lstreak_toGame = game_id_link(
                                        playstGL['to']['gameId'])
                                    gamesPlayedL = f"Longest streak: **{playstGL['v']} \n [from]{Lstreak_fromGame} {Lstreak_fromTime} \n [to]{Lstreak_toGame} {Lstreak_toTime}**"
                                except Exception as e:
                                    gamesPlayedL = "\n Longest streak - **No information found**"
                                try:
                                    playstGC = playst["nb"]["cur"]
                                    Cstreak_fromTime = timestamp_calculate(
                                        playstGC['from']['at'])
                                    Cstreak_fromGame = game_id_link(
                                        playstGC['from']['gameId'])
                                    Cstreak_toTime = timestamp_calculate(
                                        playstGC['to']['at'])
                                    Cstreak_toGame = game_id_link(
                                        playstGC['to']['gameId'])
                                    gamesPlayedC = f"\n Current streak: **{playstGC['v']} \n [from]{Cstreak_fromGame} {Cstreak_fromTime} \n [to]{Cstreak_toGame} {Cstreak_toTime}**"
                                except Exception as e:
                                    gamesPlayedC = "\n Current streak - **No information found**"
                                try:
                                    timestL = playst["time"]["max"]
                                    Ltime_fromTime = timestamp_calculate(
                                        timestL['from']['at'])
                                    Ltime_fromGame = game_id_link(
                                        timestL['from']['gameId'])
                                    Ltime_toTime = timestamp_calculate(
                                        timestL['to']['at'])
                                    Ltime_toGame = game_id_link(
                                        timestL['to']['gameId'])
                                    timeSpentL = f"Longest streak: **{format_timespan(timestL['v'])} \n[from]{Ltime_fromGame} {Ltime_fromTime} \n[to]{Ltime_toGame} {Ltime_toTime}**"
                                except Exception as e:
                                    timeSpentL = "Longest streak - **No information found**"
                                try:
                                    timestC = playst["time"]["cur"]
                                    Ctime_fromTime = timestamp_calculate(
                                        timestC['from']['at'])
                                    Ctime_fromGame = game_id_link(
                                        timestC['from']['gameId'])
                                    Ctime_toTime = timestamp_calculate(
                                        timestC['to']['at'])
                                    Ctime_toGame = game_id_link(
                                        timestC['to']['gameId'])
                                    timeSpentC = f"\n Current streak: **{format_timespan(timestC['v'])} \n[from]{Ctime_fromGame} {Ctime_fromTime} \n[to]{Ctime_toGame} {Ctime_toTime}**"
                                except Exception as e:
                                    timeSpentC = "\n Current streak - **No information found**"
                                if modeInfo["rd"] > 75:
                                    rd_warning = " (TOO HIGH)"
                                else:
                                    rd_warning = " (It's okay)"
                                if modeInfo["prog"] > 0:
                                    arrow = discord.utils.get(
                                        self.bot.emojis, name="arrowUp"
                                    )
                                elif modeInfo["prog"] < 0:
                                    arrow = discord.utils.get(
                                        self.bot.emojis, name="arrowDown"
                                    )
                                elif modeInfo["prog"] == 0:
                                    arrow = ""
                                all_games = playerPerf["count"]["all"]
                                embed.add_field(
                                    name="Games played",
                                    value="All: **"
                                    + str(all_games) + "** "
                                    + "\n Rated games: **"
                                    + str(playerPerf["count"]["rated"]) + " ("+str(
                                        round(playerPerf['count']['rated']*100/all_games, 1))+"%)** "
                                    + "\n Wins: **"
                                    + str(playerPerf["count"]["win"]) + " ("+str(
                                        round(playerPerf['count']['win']*100/all_games, 1))+"%)** "
                                    + "\n Losses: **"
                                    + str(playerPerf["count"]["loss"]) + " ("+str(
                                        round(playerPerf['count']['loss']*100/all_games, 1))+"%)** "
                                    + "\n Draws: **"
                                    + str(playerPerf["count"]["draw"]) + " ("+str(
                                        round(playerPerf['count']['draw']*100/all_games, 1))+"%)** "
                                    + "\n Tournament games: **"
                                    + str(playerPerf["count"]["tour"]) + " ("+str(
                                        round(playerPerf['count']['tour']*100/all_games, 1))+"%)** "
                                    + "\n Berserked games: **"
                                    + str(playerPerf["count"]["berserk"]) + " ("+str(
                                        round(playerPerf['count']['berserk']*100/all_games, 1))+"%)** "
                                    + "\n Time spent playing - **"
                                    + str(format_timespan(playerPerf["count"]["seconds"]))+"**",
                                    inline=False,
                                )
                                embed.add_field(
                                    name="Rating",
                                    value="Current rating: **"
                                    + str(modeInfo["rating"])+"** "
                                    + "\n Highest rating: **"
                                    + highest_rating+"** "
                                    # str(datetime.datetime.utcfromtimestamp(epoch_high).replace(tzinfo=class_dt.timezone.utc))
                                    + "\n Lowest rating: **"
                                    + lowest_rating + "** "
                                    + "\n Rating deviation: **"
                                    + str(modeInfo["rd"]) + \
                                    str(rd_warning)+"** "
                                    + "\n Progress: **"
                                    + str(arrow) + str(modeInfo["prog"])+"** ",
                                    inline=False,
                                )
                                cst = ""
                                if clossst == "No current losing streak":
                                    cst = cwinst
                                else:
                                    cst = clossst
                                embed.add_field(
                                    name="Current streak",
                                    value=cst,
                                )
                                embed.add_field(
                                    name="Winning streak",
                                    value=lwinst,
                                    inline=False,
                                )
                                embed.add_field(
                                    name="Losing streak",
                                    value=llossst,
                                    inline=False,
                                )
                                embed.add_field(
                                    name="Best rated wins",
                                    value=bestrw_op,
                                    inline=False,
                                )
                                embed.add_field(
                                    name="Worst rated losses",
                                    value=worstrw_op,
                                    inline=False,
                                )
                                embed.add_field(
                                    name="Games played in a row",
                                    value=gamesPlayedL+gamesPlayedC,
                                    inline=False
                                )
                                embed.add_field(
                                    name="Max time spent playing",
                                    value=timeSpentL+timeSpentC,
                                    inline=False
                                )
                            except Exception as e:
                                print(e)
                                embed.add_field(
                                    name="Runs", value=str(modeInfo["runs"]), inline=False
                                )
                                embed.add_field(
                                    name="Highest score",
                                    value=str(modeInfo["score"]),
                                    inline=False,
                                )
                            await ctx.send(embed=embed)
                            add_command_stats(ctx.message.author)
                        else:
                            embedNoGames = discord.Embed(title=nickname,
                                                         description=f"No games in **{mode}** detected",
                                                         color=discord.Color.from_rgb(0, 255, 255))
                            embedNoGames.add_field(
                                name="Total games", value="**0**")
                            await ctx.send(embed=embedNoGames)
                            add_command_stats(ctx.message.author)
                    except Exception as e:
                        print(traceback.format_exc())
                        embed = discord.Embed(
                            title="Incorrect mode",
                            color=discord.Color.from_rgb(255, 0, 0),
                        )
                        await ctx.send(embed=embed)
                        print(e)

'''
    global game_channels_active
    game_channels_active = []


    @commands.command(aliases=['li-game'])
    async def game(self, ctx, get_from=None, typeOfBoard=None):
        if get_from is None:
            get_from = "tv"
        if typeOfBoard is None:
            typeOfBoard = "svg"
        

        if get_from == 'tv':
            if ctx.message.channel.id in game_channels_active:
                embedActiveGame = discord.Embed(
                    title="Error, active stream detected", description="Sorry, stop streaming any active games in this channel", color=discord.Color.from_rgb(255, 0, 0))
                await ctx.send(embed=embedActiveGame)
            else:
                headers = {'Method': 'POST', 'Authorization': 'Bearer ' +
                           creds.LI_API_TOKEN, 'scope': 'https://lichess.org/api/'}
                game_channels_active.append(ctx.message.channel.id)
                async with aiohttp.ClientSession(headers=headers) as session:
                    tv_url = "https://lichess.org/api/tv/feed"
                    async with session.get(tv_url) as r:
                        num = len(game_channels_active)
                        view = ButtonsTV(r, ctx.message.channel.id)
                        embed_loading = discord.Embed(
                            title="Retrieving game data...", description='Game loading. Meow')
                        board = await ctx.send(embed=embed_loading, view=view)
                        title = ""
                        file = None
                        id = ""
                        try:
                            async for line in r.content:
                                if line:
                                    decoded_line = line.decode('utf-8')
                                    json_line = json.loads(decoded_line)
                                    print(json_line)
                                    try:
                                        try:
                                            id = json_line['d']['id']
                                        except:
                                            id = id
                                        try:
                                            title = f"**{json_line['d']['players'][0]['user']['name']} {json_line['d']['players'][0]['rating']}** vs **{json_line['d']['players'][1]['user']['name']} {json_line['d']['players'][1]['rating']}**"
                                        except:
                                            pass
                                        game = requests.get(
                                            f"https://lichess.org/game/export/{id}", stream=False,
                                            params={
                                                'clocks': 'true'
                                            },
                                            headers={
                                                'Method': 'GET',
                                                'Authorization': 'Bearer ' + creds.LI_API_TOKEN,
                                                'scope': 'https://lichess.org/',
                                                'accept': 'application/json'}
                                        )
                                        game_decoded = game.content.decode(
                                            'utf-8')
                                        game_json = json.loads(game_decoded)
                                        print(game_json)
                                        if game_json['rated'] == True:
                                            rated = "Rated"
                                        else:
                                            rated = "Unrated"
                                        all_moves = game_json['moves'].split(
                                            " ")
                                        opening = "No opening"
                                        try:
                                            opening = f"**{game_json['opening']['eco']}** {game_json['opening']['name']}"
                                        except:
                                            pass
                                        amount_time = game_json['clock']['initial']
                                        timedesc = "mins"
                                        if amount_time/60 >= 1:
                                            amount_time = amount_time/60
                                        else:
                                            timedesc = "seconds"
                                        game_started_at = game_json['createdAt']
                                        epoch2 = time.localtime(
                                            float(game_started_at/1000.0))
                                        description = f"{rated} {game_json['speed']} {game_json['variant']} {amount_time}+{game_json['clock']['increment']} {timedesc}"
                                        field_value1 = f"Game id - [{id}](https://lichess.org/{id})\n" \
                                            f"Opening - {opening}\n"
                                        gamestart = f"Game started {pretty_date(datetime(year=epoch2.tm_year, month=epoch2.tm_mon, day=epoch2.tm_mday, hour=epoch2.tm_hour, minute=epoch2.tm_min, second=epoch2.tm_sec))}\n"
                                    except Exception as e:
                                        print(e)
                                        id = id
                                        title = title
                                        game = game
                                    try:
                                        orientationGet = json_line.get(
                                            'orientation')
                                        if orientationGet == 'white':
                                            orientation = chess.WHITE
                                        else:
                                            orientation = chess.BLACK
                                    except Exception:
                                        orientation = orientation
                                    fen_code = json_line['d']['fen'].split(" ")

                                    baseboard = chess.BaseBoard(fen_code[0])
                                    try:
                                        last_move = chess.Move.from_uci(
                                            json_line['d']['lm'])
                                    except:
                                        try:
                                            actual_board = chess.Board()
                                            last_move_in_all_moves = all_moves[-1]
                                            for move in all_moves:
                                                try:
                                                    if all_moves.index(move, len(all_moves)-2) == len(all_moves)-1:
                                                        break
                                                except:
                                                    pass
                                                actual_board.push_san(move)
                                            last_move = chess.Move.from_uci(
                                                actual_board.parse_san(last_move_in_all_moves).uci())
                                        except Exception as e:
                                            last_move = None
                                    embedGame = discord.Embed(
                                        title=title, description=description, color=discord.Color.from_rgb(0, 255, 255))
                                    embedGame.add_field(name=f"Game information",
                                                        value=field_value1, inline=False)
                                    embedGame.add_field(
                                        name=f"Game started", value=gamestart)
                                    embedGame.set_footer(
                                        text=f"Requested by {ctx.message.author}")
                                    if typeOfBoard == 'svg':
                                        with BytesIO() as im_bin:
                                            
                                            svg_board = chess.svg.board(
                                                board=baseboard, orientation=orientation, lastmove=last_move)
                                            bytes_im = svg2png(
                                                bytestring=svg_board, write_to=im_bin)
                                            im_bin.seek(0)
                                            image = Image.open(BytesIO(im_bin.getvalue()))
                                            image.save(im_bin, format='PNG')
                                            # with BytesIO() as a:
                                            #     a.write(encoded_string)
                                            #     print(a.getbuffer().nbytes)
                                            #     a.seek(0)
                                            #     file = discord.File(a, filename=f'output{num}.png')
                                            #     await board.edit(content=f"{title} \n{description}", attachments=[file])

                                            # file = discord.File(im, filename=f'output{num}.png')
                                            embedGame.set_image(
                                                url=f"attachment://output.png")
                                            try:
                                                await board.edit(attachments=[image], embed=embedGame)
                                            except Exception as e:
                                                embedError = discord.Embed(
                                                    title="Error", description=f"{e}", color=discord.Color.red())
                                                await ctx.send(embed=embedError)
                                                if session.closed == True:
                                                    print(e, "\ngoint to quit..")
                                                    await asyncio.sleep(0)
                                                else:
                                                    print(e)
                                                    await stopstr(session, ctx.message.channel.id)
                                                    await asyncio.sleep(0)
                                    elif typeOfBoard == 'base':
                                        embedGame.add_field(name=f"{config.CustomEmojis.empty}",
                                                            value=f"`{chess_pieces_visualizator(str(baseboard))}`")    
                                    if session.closed == True:
                                        print("goint to quit..")
                                        try:
                                            await r.close()
                                        except:
                                            pass
                                        await asyncio.sleep(0)
                            await asyncio.sleep(1)
                            if session.closed == True:
                                print("goint to quit..")
                                try:
                                    await r.close()
                                except:
                                    pass
                                await asyncio.sleep(0)
                        except (aiohttp.ClientConnectionError, asyncio.TimeoutError):
                            if session.closed == True:
                                print("goint to quit..")
                                await asyncio.sleep(0)
                            else:
                                await stopstr(session, ctx.message.channel.id)
                                await asyncio.sleep(0)
                        if session.closed == True:
                            await asyncio.sleep(0)
                    if session.closed == True:
                        await asyncio.sleep(0)
                print("quit")
                embedFinished = embedGame.copy()
                embedFinished.remove_field(1)
                date_started = datetime(
                    year=epoch2.tm_year, month=epoch2.tm_mon, day=epoch2.tm_mday, hour=epoch2.tm_hour, minute=epoch2.tm_min, second=epoch2.tm_sec)
                print(date_started)
                gameend = f"Game started at **{timestamp_calculate(date_started)}**\n"
                embedFinished.add_field(name=f"Game ended", value=gameend)
                file = discord.File(
                    f'output{num}.png', filename=f'output{num}.png')
                if file is not None:
                    await board.edit(attachments=[file], embed=embedFinished)
                elif file is None:
                    await board.edit(attachments=[], embed=embedFinished)
                try:
                    await asyncio.sleep(10)
                    await delete_file(num)
                except:
                    await asyncio.sleep(0.5)
                    await delete_file(num)
        elif get_from == 'id':
            await ctx.send("Waiting for game id...")
            while True:
                try:
                    game_id = await self.bot.wait_for(
                        "message",
                        timeout=60,
                        check=lambda m: m.author.id == ctx.author.id and m.channel.id == ctx.channel.id,
                    )
                    print(game_id.content)
                except ValueError:
                    continue
                except asyncio.TimeoutError:
                    await ctx.send("Timeout error. Couldn't detect game id")
                    break
                try:
                    game_id_c = game_id.content
                    game = requests.get(
                        f"https://lichess.org/game/export/{game_id_c}", stream=False,
                        params={
                            'clocks': 'true'
                        },
                        headers={
                            'Method': 'GET',
                            'Authorization': 'Bearer ' + creds.LI_API_TOKEN,
                            'scope': 'https://lichess.org/',
                            'accept': 'application/json'}
                    )
                    game_decoded = game.content.decode('utf-8')
                    game_json = json.loads(game_decoded)
                    await ctx.send("Game detected")
                    print(game_json)
                    moves = game_json['moves'].split(' ')
                    board = chess.Board()
                    for move in moves:
                        push = board.parse_san(move)
                        board.push(push)
                    fen_info = board.fen()
                    fen = fen_info.split(' ')
                    baseboard = chess.BaseBoard(fen[0])
                    await ctx.send(f"`{chess_pieces_visualizator(str(baseboard))}`")
                    break
                except Exception as e:
                    print(traceback.format_exc())
                    await ctx.send("Game ID error. Couldn't detect game by that id")
'''

async def setup(bot):
    await bot.add_cog(Chess(bot))

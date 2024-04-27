import asyncio
import calendar
import json
import math
import os
from datetime import datetime as dt, timedelta
from io import BytesIO
from urllib.parse import urlparse

import aiohttp
import berserk
import chess
import chess.svg
import chess.variant
import discord
import pycountry
import requests
from PIL import Image
from cairosvg import svg2png
from discord.enums import ButtonStyle
from discord.ext import commands
from dotenv import load_dotenv
from humanfriendly import format_timespan

import bot_util.bot_config as bot_config
from bot_util.enums import TimestampFormats
from bot_util.functions.chess_supp import (board_to_image, chess_emojis, chess_eval, chess_eval_comment, fetch_flair)
from bot_util.functions.universal import (
    countdown_timer, percentage_calc, pretty_date, pretty_time_delta, send_report, send_report_exc, timestamp_maker
)
from bot_util.misc import AsyncTranslator, Logger, Scheduler
from bot_util.misc.api_callers import ChessDotComApiCall as CDCApiCall, ChessDotComApiCaller as CDCApiCaller, \
    LichessApiCall
from db_data.database_main import LocalCache
from db_data.psql_main import DatabaseFunctions as DF, ChessFunctions as LT
from random_chess_opening import core as rco

logger = Logger(__name__)

load_dotenv("creds/.env")
token = os.getenv("LI_API_TOKEN")


class NextGameButton(discord.ui.Button):
    def __init__(self, channel_id, _):
        super().__init__(
            label=_("Next Game"), style=discord.ButtonStyle.gray, disabled=True
        )
        self.channel_id = channel_id
        self._ = _

    async def func_button(
            self, button: discord.ui.Button, interaction: discord.Interaction
    ):
        button.style = discord.ButtonStyle.gray
        '''
        if ACTIVE_LICHESS_GAMES["tv"] is None:
            ACTIVE_LICHESS_GAMES["tv"] = LichessGame(
                channel_id=self.channel_id,
                message=GAME_CHANNELS_ACTIVE_TV[self.channel_id]["message"],
                tv=True,
            )
            await ACTIVE_LICHESS_GAMES["tv"].get_game_stream()
        else:
            GAME_CHANNELS_ACTIVE_TV[self.channel_id]["streaming"] = True
        '''
        button.disabled = True
        await interaction.response.edit_message(view=button.view)


class ViewTV(discord.ui.View):
    def __init__(self, object_inst, channel_id, *, timeout=None):
        super().__init__(timeout=timeout)
        self.object = object_inst
        self.channel_id = channel_id
        self.next_button = NextGameButton(channel_id=self.channel_id)
        self.add_item(self.next_button)


GAME_CHANNELS_ACTIVE_TV = {}

ACTIVE_LICHESS_GAMES = {"tv": {}}


class LichessGame:
    def __init__(
            self,
            client,
            user_id,
            channel_id,
            gettext_,
            message: discord.Message,
            game_id=None,
            game_json=None,
            tv: bool = False,
            live: bool = False,
            tv_type=None,
    ):
        self.client = client
        self.game_id = game_id
        self.user_id = user_id
        self.embed = discord.Embed()
        self.embed_game: discord.Embed | None = None
        self._ = gettext_
        self.channel_id = channel_id
        self.message = message
        self.board = None
        self.board_message = None
        self.white_message = None
        self.black_message = None
        self.white_clock: int
        self.black_clock: int
        self.white_name: str
        self.black_name: str
        self.author = None
        self.game_info = game_json
        self.orientation = chess.WHITE
        self.move_count = 0
        self.current_move_number = -1
        self.moves = []
        self.clocks: list = []
        self.analysis = None

        self.opening = {"name": "No opening", "eco": "No ECO", "ply": 0}
        self.description = ""

        # Live game variables
        self.live = live
        self.tv = tv
        self.games_limit = {"bullet": 10, "blitz": 3, "rapid": 2, "classical": 1}
        self.stopped = False if self.live is True else True
        # Checks if game is from tv feed
        global ACTIVE_LICHESS_GAMES
        if self.tv is True:
            if tv_type is None:
                tv_type = "feed"
            self.tv_type = tv_type
            global GAME_CHANNELS_ACTIVE_TV
            GAME_CHANNELS_ACTIVE_TV[self.channel_id] = {
                "message": message,
                "no_update": True,
                "streaming": True,
                "tv_type": self.tv_type,
                "embed": None,
                "view": None,
            }  # Adds channel to active tv channels
            # Checks if game is already being streamed
            if self.tv_type not in ACTIVE_LICHESS_GAMES["tv"]:
                ACTIVE_LICHESS_GAMES["tv"][
                    tv_type
                ] = self  # If not, adds it to the dict
        else:
            if self.live is True:
                ACTIVE_LICHESS_GAMES[self.game_id] = {
                    "game": self,
                    "channels": [self.channel_id],
                }
                self.get_game_info()
                self.set_board()
            else:
                if self.game_info is None:
                    self.get_game_info()
                self.moves = self.get_move_list()
                self.opening = self.get_opening()
                self.set_board()
                self.post_init()
                asyncio.get_running_loop().create_task(
                    self.edit_message(attachments=[self.attachment])
                )

    def __del__(self):
        logger.info(f"Lichess game stream of {self.game_id} deleted")

    def set_board(self):
        game_variant = self.game_info["variant"]
        match game_variant:
            case "standard":
                self.board = chess.Board()
            case "chess960":
                self.board = chess.Board(self.game_info["initialFen"], chess960=True)
            case "crazyhouse":
                self.board = chess.variant.CrazyhouseBoard()
            case "antichess":
                self.board = chess.variant.AntichessBoard()
            case "atomic":
                self.board = chess.variant.AtomicBoard()
            case "horde":
                self.board = chess.variant.HordeBoard()
            case "kingOfTheHill":
                self.board = chess.variant.KingOfTheHillBoard()
            case "racingKings":
                self.board = chess.variant.RacingKingsBoard()
            case "threeCheck":
                self.board = chess.variant.ThreeCheckBoard()

    def post_init(self):
        whiteDiff = (
            self.game_info["players"]["white"]["ratingDiff"]
            if "ratingDiff" in self.game_info["players"]["white"]
            else 0
        )
        blackDiff = (
            self.game_info["players"]["black"]["ratingDiff"]
            if "ratingDiff" in self.game_info["players"]["black"]
            else 0
        )
        self.white_name = (
            self.game_info["players"]["white"]["user"]["name"]
            if "user" in self.game_info["players"]["white"]
            else self.game_info["players"]["white"]["name"]
        )
        self.black_name = (
            self.game_info["players"]["black"]["user"]["name"]
            if "user" in self.game_info["players"]["black"]
            else self.game_info["players"]["black"]["name"]
        )
        if "clock" in self.game_info:
            gameClock = f"{'{} mins'.format(int(self.game_info['clock']['initial'] // 60)) if self.game_info['clock']['initial'] >= 60 else '{} seconds'.format(self.game_info['clock']['initial'])}  + {int(self.game_info['clock']['increment'])} inc"
            self.clocks = self.game_info["clocks"]
        else:
            if (
                    self.game_info["speed"] == "correspondence"
                    and "daysPerTurn" in self.game_info
            ):
                gameClock = f"{self.game_info['daysPerTurn']} days"
            else:
                gameClock = self._("Unlimited")
        results_hash = {
            "outoftime": " by timeout",
            "resign": " by resignation",
            "mate": " by checkmate",
            "abandoned": " by abandonment",
            "cheat": " by opponent cheating",
            "variantend": " by variant end",
        }
        self.embed = discord.Embed(color=bot_config.CustomColors.cyan)
        self.embed.title = (
                f"{self.white_name} "
                + (
                    fetch_flair(self.game_info["players"]["white"]["user"]["flair"])
                    if "user" in self.game_info["players"]["white"]
                       and "flair" in self.game_info["players"]["white"]["user"]
                    else ""
                )
                + f"({self.game_info['players']['white']['rating'] if 'rating' in self.game_info['players']['white'] else ''}) {whiteDiff}{bot_config.CustomEmojis.progress_down if whiteDiff < 0 else bot_config.CustomEmojis.progress_up}"
                  f"\nvs \n{self.black_name} "
                + (
                    fetch_flair(self.game_info["players"]["black"]["user"]["flair"])
                    if "user" in self.game_info["players"]["black"]
                       and "flair" in self.game_info["players"]["black"]["user"]
                    else ""
                )
                + f"({self.game_info['players']['black']['rating'] if 'rating' in self.game_info['players']['black'] else ''}) {blackDiff}{bot_config.CustomEmojis.progress_down if blackDiff < 0 else bot_config.CustomEmojis.progress_up}"
        )
        self.embed.description = f"[{'Rated' if self.game_info['rated'] is True else 'Unrated'} {self.game_info['perf'].capitalize()} {self.game_info['variant'].capitalize()}]{self.game_id_link(self.game_info['id'])} | **{gameClock}**"
        last_move_at = (
            dt.strptime(self.game_info["lastMoveAt"], "%Y-%m-%d %H:%M:%S")
            if isinstance(self.game_info["lastMoveAt"], str)
            else self.game_info["lastMoveAt"]
        )
        created_at = (
            dt.strptime(self.game_info["createdAt"], "%Y-%m-%d %H:%M:%S")
            if isinstance(self.game_info["createdAt"], str)
            else self.game_info["createdAt"]
        )
        game_info = self._(
            "Result: **{win_cond} {etc}**\nOpening: {opening}\nMoves: **{moves}**\nPlayed on: {date} \nGame took {time}"
        ).format(
            win_cond="Draw"
            if self.game_info["status"] == "draw" or "winner" not in self.game_info
            else f'{self.game_info["winner"].capitalize()} won ',
            etc=f"· {results_hash[self.game_info['status']]}"
            if self.game_info["status"] in results_hash
            else "",
            opening=f"***{self.opening['eco']}*** **{self.opening['name']}**",
            moves=str(self.move_count) + self._(" moves")
            if self.move_count > 1
            else self._(" move"),
            date=f"*<t:{calendar.timegm(created_at.timetuple())}>*",
            time=f"`{pretty_time_delta((last_move_at - created_at).total_seconds())}`",
        )

        self.embed.add_field(
            name=self._("Game information"),
            value=game_info,
            inline=False,
        )
        if "analysis" in self.game_info:
            for player in self.game_info["players"]:
                self.embed.add_field(
                    name="{player}".format(
                        player=self.white_name if player == "white" else self.black_name
                    ),
                    value="{in_emoji} **{inaccuracies}** {ina}\n{mi_emoji} **{mistakes}** {mista}\n{bl_emoji} **{blunders}** {blundr}\n**{acl}** Average centipawn loss".format(
                        in_emoji=bot_config.CustomEmojis.inaccuracy,
                        inaccuracies=self.game_info["players"][player]["analysis"][
                            "inaccuracy"
                        ],
                        ina=self._("inaccuracy")
                        if str(
                            self.game_info["players"][player]["analysis"]["inaccuracy"]
                        )[0]
                           == "1"
                        else self._("inaccuracies"),
                        mi_emoji=bot_config.CustomEmojis.mistake,
                        mistakes=self.game_info["players"][player]["analysis"][
                            "mistake"
                        ],
                        mista=self._("mistake")
                        if str(
                            self.game_info["players"][player]["analysis"]["mistake"]
                        )[0]
                           == "1"
                        else self._("mistakes"),
                        bl_emoji=bot_config.CustomEmojis.blunder,
                        blunders=self.game_info["players"][player]["analysis"][
                            "blunder"
                        ],
                        blundr=self._("blunder")
                        if str(
                            self.game_info["players"][player]["analysis"]["blunder"]
                        )[0]
                           == "1"
                        else self._("blunders"),
                        acl=self.game_info["players"][player]["analysis"]["acpl"],
                    ),
                    inline=True,
                )
                self.analysis = self.game_info["analysis"]
        else:
            self.embed.add_field(
                name=self._("Game analysis"),
                value=self._(
                    "No analysis available\n||*Please visit game on lichess and request analysis by yourself*||"
                ),
                inline=False,
            )
        self.thumbnail_set()

        self.view = LiGameMainView(self, self.user_id)

    async def edit_message(self, content=None, attachments=[None]):
        await self.message.edit(
            embed=self.embed, content=content, attachments=attachments, view=self.view
        )

    def lichess_req(self):
        game = self.client.games.export(
            self.game_id, clocks=True, literate=True, opening=True
        )
        LT.store_lichess_game(game)
        return game

    def draw_svg(self, last_move=None, eval=None):
        lastmove = (
            chess.Move.from_uci(self.board.peek().uci())
            if last_move is not None
            else None
        )
        check_square = (
            self.board.king(self.board.turn) if self.board.is_check() else None
        )
        arrows = []
        if eval is not None or eval == "Game over":
            if "judgment" in eval:
                bestmove = chess.Move.from_uci(eval["best"])
                match eval["judgment"]["name"]:
                    case "Inaccuracy":
                        arrows = [
                            chess.svg.Arrow(
                                lastmove.from_square,
                                lastmove.to_square,
                                color="#00d0ff",
                            ),
                            chess.svg.Arrow(
                                bestmove.from_square,
                                bestmove.to_square,
                                color="#315cea",
                            ),
                        ]
                    case "Mistake":
                        arrows = [
                            chess.svg.Arrow(
                                lastmove.from_square,
                                lastmove.to_square,
                                color="#ffc300",
                            ),
                            chess.svg.Arrow(
                                bestmove.from_square,
                                bestmove.to_square,
                                color="#315cea",
                            ),
                        ]
                    case "Blunder":
                        arrows = [
                            chess.svg.Arrow(
                                lastmove.from_square,
                                lastmove.to_square,
                                color="#ff1d00",
                            ),
                            chess.svg.Arrow(
                                bestmove.from_square,
                                bestmove.to_square,
                                color="#315cea",
                            ),
                        ]
                    case _:
                        logger.error(f"Unknown judgment: {eval['judgment']['name']}")
                        send_report("Unknown judgment", eval)

        with BytesIO() as image_binary:
            # print(dict.fromkeys(self.board.attacks(chess.B1))) <--- Example given in docs
            self.board_svg = chess.svg.board(
                board=self.board,
                size=600,
                lastmove=lastmove,
                check=check_square,
                arrows=arrows,
                orientation=self.orientation,
            )
            bytes_image = svg2png(
                bytestring=self.board_svg, write_to=image_binary
            )  # idk why it's here, but the code breaks if I remove. Fuck this too
            image_binary.seek(0)
            self.board_png_image = Image.open(fp=image_binary)
            image_binary.seek(0)
            self.attachment_board = discord.File(fp=image_binary, filename="board.png")
            self.embed_game.set_image(url="attachment://board.png")

    def build_game_embed(self):
        self.embed_game = discord.Embed(
            title=self.embed.title,
            description=self.embed.description,
            color=bot_config.CustomColors.cyan,
        )
        self.white_clock = self.clocks[0] if len(self.clocks) > 0 else -1
        self.black_clock = self.clocks[0] if len(self.clocks) > 0 else -1
        self.embed_game.add_field(
            name=self._("Clocks"),
            value="{white} - **{white_clock}**\n{black} - **{black_clock}**".format(
                white=self.white_name,
                white_clock=countdown_timer(self.white_clock),
                black=self.black_name,
                black_clock=countdown_timer(self.black_clock),
            ),
            inline=False,
        )
        self.embed_game.add_field(
            name=self._("Move Comment"), value=self._("*No comment*"), inline=False
        )
        self.embed_game.add_field(
            name=self._("Evaluation"),
            value=self._("**+0.2** - *Starting position*")
            if self.analysis is not None
            else self._("*No evaluation*"),
            inline=False,
        )

    def update_game_embed(self, revert=False):
        if len(self.clocks) > 0:
            if self.board.turn == chess.WHITE:
                if revert:
                    self.white_clock = self.clocks[self.current_move_number - 1]
                else:
                    self.black_clock = self.clocks[self.current_move_number]
            else:
                if revert:
                    self.black_clock = self.clocks[self.current_move_number - 1]
                else:
                    self.white_clock = self.clocks[self.current_move_number]

        self.embed_game.set_field_at(
            index=0,
            name=self._("Clocks"),
            value="{white} - **{white_clock}**\n{black} - **{black_clock}**".format(
                white=self.white_name,
                white_clock=countdown_timer(self.white_clock),
                black=self.black_name,
                black_clock=countdown_timer(self.black_clock),
            ),
            inline=False,
        )
        if self.analysis is not None:
            if len(self.game_info["analysis"]) == self.current_move_number:
                self.embed_game.set_field_at(
                    index=1,
                    name=self._("Move Comment"),
                    value="{comment}".format(comment=self._("Game over.")),
                    inline=False,
                )
                self.embed_game.set_field_at(
                    index=2,
                    name=self._("Evaluation"),
                    value="**{eval}** - *{comment}*".format(
                        eval="#", comment=self._("Game over.")
                    ),
                    inline=False,
                )
            else:
                if "judgment" in self.game_info["analysis"][self.current_move_number]:
                    self.embed_game.set_field_at(
                        index=1,
                        name=self._("Move Comment"),
                        value="{comment}".format(
                            comment=self.game_info["analysis"][
                                self.current_move_number
                            ]["judgment"]["comment"]
                        ),
                        inline=False,
                    )
                else:
                    self.embed_game.set_field_at(
                        index=1,
                        name=self._("Move Comment"),
                        value=self._("*No comment*"),
                        inline=False,
                    )

                self.embed_game.set_field_at(
                    index=2,
                    name=self._("Evaluation"),
                    value="**{eval}** - *{comment}*".format(
                        eval=chess_eval(
                            self.game_info["analysis"][self.current_move_number]["eval"]
                            if "eval"
                               in self.game_info["analysis"][self.current_move_number]
                            else self.game_info["analysis"][self.current_move_number][
                                "mate"
                            ],
                            mate=True
                            if "mate"
                               in self.game_info["analysis"][self.current_move_number]
                            else False,
                        ),
                        comment=chess_eval_comment(
                            self.game_info["analysis"][self.current_move_number]["eval"]
                            if "eval"
                               in self.game_info["analysis"][self.current_move_number]
                            else self.game_info["analysis"][self.current_move_number][
                                "mate"
                            ],
                            mate=True
                            if "mate"
                               in self.game_info["analysis"][self.current_move_number]
                            else False,
                        ),
                    ),
                    inline=False,
                )

    def flip_board(self):
        self.orientation = (
            chess.WHITE if self.orientation == chess.BLACK else chess.BLACK
        )

    def thumbnail_set(self):
        fp = (
            self.game_info["perf"].lower()
            if self.game_info["variant"] == "standard"
            else self.game_info["variant"]
        )
        self.attachment = discord.File(
            fp=f"Images/Lichess/{fp}.png", filename=f"{fp}.png"
        )
        self.embed.set_thumbnail(url=f"attachment://{fp}.png")

    def get_game_info(self):
        game = LT.get_lichess_game(self.game_id)
        if game is None:
            game = self.lichess_req()
        logger.debug(f"Game info: {game}")
        self.game_info = game
        return self.game_info

    def update_game_info(self):
        if self.game_info is None or "analysis" not in self.game_info:
            return self.lichess_req()

    def get_move_list(self):
        move_list = self.game_info["moves"].split()
        self.move_count = math.ceil(len(move_list) / 2)
        return move_list

    def get_opening(self):
        opening = (
            self.game_info["opening"] if "opening" in self.game_info else self.opening
        )
        return opening

    def play_moves(self, move_list):
        # // print(move_list)
        for move in move_list:
            self.board.push_san(move)

    def update_board(self, fen):
        self.board.set_fen(fen)

    def play_uci_move(self, move):
        self.board.push_uci(move)

    def play_san_move(self, move):  # (Nc3, b5, dxe5)
        self.board.push_san(move)

    def undo_move(self):
        self.board.pop()

    def emoji_chess_pieces(self):
        i = 0
        emote_representation = ""
        print(str(self.board))
        for piece in str(self.board).replace(" ", ""):
            if piece != "\n":
                emote_representation += chess_emojis[f"{piece}_{i % 2}"]
            else:
                emote_representation += "\n"
            i += 1
        return emote_representation

    def game_id_link(self, id):
        game_link = f"(https://lichess.org/{id})"
        return game_link

    def limit_exceeded(self, channel):
        embed_limit = discord.Embed(
            title="Limit exceeded",
            description="This channel has reached the limit of games played for this time control. If you wish to watch more games, just restart the command.",
            color=bot_config.CustomColors.cyan,
        )
        global GAME_CHANNELS_ACTIVE_TV
        GAME_CHANNELS_ACTIVE_TV[channel]["message"].edit(embed=embed_limit)
        GAME_CHANNELS_ACTIVE_TV.pop(channel)

    async def get_game_stream(self):
        headers = {
            "Method": "POST",
            "Authorization": "Bearer " + token,
            "scope": "https://lichess.org/api/",
        }
        if self.tv is True:
            async with aiohttp.ClientSession(headers=headers) as session:
                tv_url = f"https://lichess.org/api/tv/{self.tv_type}"
                self.session = session
                async with session.get(tv_url) as r:
                    try:
                        async for line in r.content:
                            if line and self.live is True:
                                decoded_line = line.decode("utf-8")
                                json_line = json.loads(decoded_line)
                                print(json_line)
                                if "orientation" in json_line["d"]:
                                    global GAME_CHANNELS_ACTIVE_TV
                                    for dc_channel in GAME_CHANNELS_ACTIVE_TV:
                                        if (
                                                GAME_CHANNELS_ACTIVE_TV[dc_channel]["no_update"]
                                                is False
                                        ):
                                            GAME_CHANNELS_ACTIVE_TV[dc_channel]["view"].next_button.disabled = False
                                            GAME_CHANNELS_ACTIVE_TV[dc_channel][
                                                "view"].next_button.style = discord.ButtonStyle.green
                                            n_embed = discord.Embed.from_dict(
                                                GAME_CHANNELS_ACTIVE_TV[dc_channel][
                                                    "embed"
                                                ]
                                            )
                                            n_embed = self.enchance_embed(n_embed)
                                            await GAME_CHANNELS_ACTIVE_TV[dc_channel]["message"].edit(
                                                embed=n_embed,
                                                view=GAME_CHANNELS_ACTIVE_TV[dc_channel]["view"],
                                            )
                                            GAME_CHANNELS_ACTIVE_TV[dc_channel]["streaming"] = False
                                    self.game_id = json_line["d"]["id"]
                                    self.get_game_info()
                                    print(self.game_info)
                                    if (
                                            len(GAME_CHANNELS_ACTIVE_TV) == 0
                                            or (
                                            GAME_CHANNELS_ACTIVE_TV[channel][
                                                "streaming"
                                            ]
                                            for channel in GAME_CHANNELS_ACTIVE_TV
                                    )
                                            is False
                                    ):
                                        await self.close_stream()
                                    self.set_board()
                                    self.play_moves(self.get_move_list())

                                    title = f"**{json_line['d']['players'][0]['user']['name']} [{json_line['d']['players'][0]['rating']}]** vs **{json_line['d']['players'][1]['user']['name']} [{json_line['d']['players'][1]['rating']}]**"
                                    if self.game_info["rated"] is True:
                                        rated = "Rated"
                                    else:
                                        rated = "Unrated"
                                    self.get_opening()
                                    amount_time = self.game_info["clock"]["initial"]
                                    timedesc = "mins"
                                    if amount_time / 60 >= 1:
                                        amount_time = amount_time / 60
                                    else:
                                        timedesc = "seconds"
                                    self.description = f"{rated} {self.game_info['speed']} {self.game_info['variant']} {amount_time}+{self.game_info['clock']['increment']} {timedesc}"
                                    embed_game = discord.Embed(
                                        title=title,
                                        description=f"{self.description} \n\n {self.emoji_chess_pieces()}",
                                        color=bot_config.CustomColors.cyan,
                                    )
                                    for channel_stream in list(
                                            GAME_CHANNELS_ACTIVE_TV
                                    ):  # Loops through all active tv channels. Converting to list is crucial, because dict is changing size during iteration
                                        if (
                                                GAME_CHANNELS_ACTIVE_TV[channel_stream][
                                                    "tv_type"
                                                ]
                                                != self.tv_type
                                        ):
                                            continue
                                        if (
                                                GAME_CHANNELS_ACTIVE_TV[channel_stream][
                                                    "streaming"
                                                ]
                                                is False
                                        ):
                                            continue
                                        if (
                                                GAME_CHANNELS_ACTIVE_TV[channel_stream][
                                                    "no_update"
                                                ]
                                                is True
                                        ):
                                            GAME_CHANNELS_ACTIVE_TV[channel_stream][
                                                "embed"
                                            ] = embed_game.to_dict()
                                            embed_game = self.enchance_embed(embed_game)
                                            GAME_CHANNELS_ACTIVE_TV[channel_stream][
                                                "view"
                                            ] = ViewTV(self, channel_stream)
                                            await GAME_CHANNELS_ACTIVE_TV[
                                                channel_stream
                                            ]["message"].edit(
                                                embed=embed_game,
                                                view=GAME_CHANNELS_ACTIVE_TV[
                                                    channel_stream
                                                ]["view"],
                                            )
                                            GAME_CHANNELS_ACTIVE_TV[channel_stream][
                                                "no_update"
                                            ] = False
                                else:
                                    try:
                                        self.play_uci_move(json_line["d"]["lm"])
                                    except Exception:
                                        self.update_board(json_line["d"]["fen"])
                                    self.move_count += 1
                                    if (
                                            self.game_info["variant"] == "standart"
                                            and self.move_count < 25
                                            and self.move_count % 5 == 0
                                    ):
                                        self.get_game_info()
                                        self.get_opening()
                                    for channel_stream in list(GAME_CHANNELS_ACTIVE_TV):
                                        if (
                                                GAME_CHANNELS_ACTIVE_TV[channel_stream][
                                                    "tv_type"
                                                ]
                                                != self.tv_type
                                        ):
                                            continue
                                        if (
                                                GAME_CHANNELS_ACTIVE_TV[channel_stream][
                                                    "streaming"
                                                ]
                                                is False
                                        ):
                                            continue
                                        if (
                                                GAME_CHANNELS_ACTIVE_TV[channel_stream][
                                                    "no_update"
                                                ]
                                                is False
                                        ):
                                            n_embed = GAME_CHANNELS_ACTIVE_TV[
                                                self.channel_id
                                            ]["embed"]
                                            n_embed[
                                                "description"
                                            ] = f"{self.description} \n\n {self.emoji_chess_pieces()}"
                                            n_embed = discord.Embed.from_dict(n_embed)
                                            n_embed = self.enchance_embed(n_embed)
                                            await GAME_CHANNELS_ACTIVE_TV[
                                                channel_stream
                                            ]["message"].edit(
                                                embed=n_embed,
                                                view=GAME_CHANNELS_ACTIVE_TV[
                                                    channel_stream
                                                ]["view"],
                                            )
                                        else:
                                            embed_game = discord.Embed(
                                                title="Game",
                                                description=f"{self.description} \n\n {self.emoji_chess_pieces()}",
                                                color=bot_config.CustomColors.cyan,
                                            )
                                            GAME_CHANNELS_ACTIVE_TV[channel_stream][
                                                "embed"
                                            ] = embed_game
                                            embed_game = self.enchance_embed(embed_game)
                                            await GAME_CHANNELS_ACTIVE_TV[
                                                channel_stream
                                            ]["message"].edit(embed=embed_game)
                                            GAME_CHANNELS_ACTIVE_TV[channel_stream][
                                                "no_update"
                                            ] = False
                    except Exception:
                        logger.exception("Closing TV stream")
                        await self.close_stream()

    async def close_stream(self):
        if self.session is None:
            return
        try:
            await self.session.close()
            global ACTIVE_LICHESS_GAMES
            ACTIVE_LICHESS_GAMES["tv"] = None
        except Exception:
            logger.exception("Stream close error")


class PrevMoveButton(discord.ui.Button):
    def __init__(self, *, style: ButtonStyle = ButtonStyle.primary):
        super().__init__(style=style, label="<", disabled=True)
        self.view: GameViewNotLive

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.view.game_obj.user_id:
            await interaction.response.send_message("Don't interrupt!", ephemeral=True)
            return

        self.view.game_obj.undo_move()
        self.view.game_obj.current_move_number -= 1
        if self.view.game_obj.current_move_number == -1:
            self.disabled = True
        if self.view.next_move.disabled is True:
            self.view.next_move.disabled = False
        self.view.game_obj.draw_svg(
            last_move=self.view.game_obj.moves[self.view.game_obj.current_move_number],
            eval=self.view.game_obj.analysis[self.view.game_obj.current_move_number]
            if self.view.game_obj.analysis is not None
            else None,
        )
        self.view.game_obj.update_game_embed(revert=True)
        await interaction.response.edit_message(
            embed=self.view.game_obj.embed_game,
            view=self.view,
            attachments=[
                self.view.game_obj.attachment_board,
            ],
        )

        # await interaction.message.edit(embed=embed_game, view=interaction.view)


class NextMoveButton(discord.ui.Button):
    def __init__(self, *, style: discord.ButtonStyle = discord.ButtonStyle.primary):
        super().__init__(style=style, label=">")
        self.view: GameViewNotLive

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.view.game_obj.user_id:
            await interaction.response.send_message("Don't interrupt!", ephemeral=True)
            return

        self.view.game_obj.current_move_number += 1
        self.view.game_obj.play_san_move(
            self.view.game_obj.moves[self.view.game_obj.current_move_number]
        )
        if self.view.game_obj.current_move_number == len(self.view.game_obj.moves) - 1:
            self.disabled = True
        if self.view.prev_move.disabled is True:
            self.view.prev_move.disabled = False

        try:
            eval = (
                self.view.game_obj.analysis[self.view.game_obj.current_move_number]
                if self.view.game_obj.analysis is not None
                else None
            )
        except Exception:
            eval = "Game over"

        self.view.game_obj.draw_svg(
            last_move=self.view.game_obj.moves[self.view.game_obj.current_move_number],
            eval=eval,
        )
        self.view.game_obj.update_game_embed()

        await interaction.response.edit_message(
            embed=self.view.game_obj.embed_game,
            view=self.view,
            attachments=[self.view.game_obj.attachment_board],
        )


class FlipBoard(discord.ui.Button):
    def __init__(self, *, style: ButtonStyle = ButtonStyle.primary):
        super().__init__(style=style, label="⮔")

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.view.game_obj.user_id:
            await interaction.response.send_message("Don't interrupt!", ephemeral=True)
            return
        self.view.game_obj.flip_board()
        self.view.game_obj.draw_svg(
            last_move=self.view.game_obj.moves[self.view.game_obj.current_move_number]
            if self.view.game_obj.current_move_number != -1
            else None,
            eval=self.view.game_obj.analysis[self.view.game_obj.current_move_number]
            if self.view.game_obj.analysis is not None and self.view.game_obj.current_move_number > 0
            else None,
        )

        await interaction.response.edit_message(
            embed=self.view.game_obj.embed_game,
            view=self.view,
            attachments=[self.view.game_obj.attachment_board],
        )


class ViewGameButton(discord.ui.Button):
    def __init__(self, *, style: discord.ButtonStyle = discord.ButtonStyle.secondary):
        super().__init__(style=style, label="", emoji="🔍")
        self.view: LiGameMainView
        self.view_to_post: GameViewNotLive = None

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.view.user_id:
            await interaction.response.send_message("Don't interrupt!", ephemeral=True)
            return
        self.view_to_post = (
            GameViewNotLive(self.view.game_obj, self.view.user_id, self.view)
            if self.view_to_post is None
            else self.view_to_post
        )
        self.view_to_post.game_obj.build_game_embed()
        self.view_to_post.game_obj.draw_svg()

        await interaction.response.edit_message(
            embed=self.view_to_post.game_obj.embed_game,
            view=self.view_to_post,
            attachments=[self.view_to_post.game_obj.attachment_board],
        )


class ReturnButton(discord.ui.Button):
    def __init__(
            self,
            view_return_to,
            *,
            style: discord.ButtonStyle = discord.ButtonStyle.secondary,
    ):
        super().__init__(style=style, label="↵")
        self.view_to_return_to = view_return_to

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.view_to_return_to.user_id:
            await interaction.response.send_message("Don't interrupt!", ephemeral=True)
            return
        self.view_to_return_to.game_obj.thumbnail_set()
        await interaction.response.edit_message(
            embed=self.view_to_return_to.game_obj.embed,
            view=self.view_to_return_to,
            attachments=[self.view_to_return_to.game_obj.attachment],
        )


class RefreshGameButton(discord.ui.Button):
    def __init__(self, *, style: discord.ButtonStyle = discord.ButtonStyle.secondary):
        super().__init__(style=style, label="🔄")
        self.view: LiGameMainView

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.view.game_obj.user_id:
            await interaction.response.send_message("Don't interrupt!", ephemeral=True)
            return

        self.view.game_obj.game_info = self.view.game_obj.lichess_req()
        self.view.game_obj.post_init()

        await interaction.response.edit_message(
            embed=self.view.game_obj.embed,
            view=self.view,
            attachments=[self.view.game_obj.attachment],
        )


class LiGameMainView(discord.ui.View):
    def __init__(
            self, game_obj: LichessGame, user_id: int, *, timeout: float | None = 180
    ):
        super().__init__(timeout=timeout)
        self.game_obj: LichessGame = game_obj
        self.user_id = user_id
        self.embed = game_obj.embed
        self.view_game_butt = ViewGameButton()
        self.refresh_butt = RefreshGameButton()
        # Check if database already contains the game and if it's already analyzed. If yes, disable the button. If no, add the enabled button.
        if game_obj.analysis is not None:
            self.refresh_butt.disabled = True
        self.add_item(self.view_game_butt)
        self.add_item(self.refresh_butt)

    async def on_timeout(self):
        for item in self.children:
            item.disabled = True
        await self.game_obj.message.edit(view=self)
        del self.game_obj


class GameViewNotLive(discord.ui.View):
    def __init__(
            self,
            game_obj: LichessGame,
            user_id: int,
            view_to_return: LiGameMainView,
            *,
            timeout: float | None = 600,
    ):
        super().__init__(timeout=timeout)
        self.game_obj = game_obj
        self.user_id = user_id
        self.prev_move = PrevMoveButton()
        self.next_move = NextMoveButton()
        self.flip_board = FlipBoard()
        self.return_button = ReturnButton(view_return_to=view_to_return)
        self.add_item(self.prev_move)
        self.add_item(self.next_move)
        self.add_item(self.flip_board)
        self.add_item(self.return_button)

    async def on_timeout(self):
        for item in self.children:
            item.disabled = True
        await self.game_obj.message.edit(view=self)
        del self.game_obj


class LiTopSelect(discord.ui.Select):
    def __init__(self, *, options: list[discord.SelectOption] = ...):
        super().__init__(
            placeholder="Select time control or variant",
            min_values=1,
            max_values=1,
            options=options,
            disabled=False,
        )

    async def callback(self, interaction: discord.Interaction):
        mode = self.values[0]
        if mode in self.view.embeds.keys():
            await self.view.message.edit(embed=self.view.embeds[mode])
            return
        embed = discord.Embed(
            title=f"Lichess leaderboard - {mode.capitalize()}",
            description="*as for {}*".format(
                timestamp_maker(self.view.time_cached, TimestampFormats.SHORT_DATE)
            ),
            color=bot_config.CustomColors.cyan,
        )
        embed.set_footer(
            text=f"Requested by {interaction.user.name}#{interaction.user.discriminator}"
        )
        for player in self.view.json_data[mode]:
            embed.add_field(
                name=f"Top {self.view.json_data[mode].index(player) + 1}",
                value=f"{'**' + player['title'] + '**' if 'title' in player else ''} [{player['username']}](https://lichess.org/@/{player['username']}) "
                      f"with rating **{player['perfs'][mode]['rating']}** ||{'+' if player['perfs'][mode]['progress'] > 0 else ''}{player['perfs'][mode]['progress']} {bot_config.CustomEmojis.progress_up if player['perfs'][mode]['progress'] >= 0 else bot_config.CustomEmojis.progress_down}||",
                inline=False,
            )
        self.view.embeds[mode] = embed
        await interaction.response.edit_message(embed=embed, view=self.view)


class LiTopView(discord.ui.View):
    def __init__(self, json_data: list[dict, dt], embed: discord.Embed, *, timeout=180):
        super().__init__(timeout=timeout)
        self.json_data: dict = json_data[0]
        self.time_cached = json_data[1]
        self.embeds = {"rapid": embed}
        self.add_item(
            LiTopSelect(
                options=[
                    discord.SelectOption(label=mode.capitalize(), value=mode)
                    for mode in self.json_data.keys()
                ]
            )
        )


class Chess(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.session = berserk.TokenSession(token)
        self.client = berserk.Client(session=self.session)
        self.chess_scheduler = Scheduler()
        self.cdc_caller = CDCApiCaller()

    async def cog_load(self):
        print("Chess cog loaded successfully!")
        self.chess_scheduler.scheduler.add_job(
            self.update_lichess_top, "cron", hour=2, minute=0
        )

    async def update_lichess_top(self):
        logger.debug("Updating lichess top")
        json_top = self.client.users.get_all_top_10()
        LT.store_lichess_top(json_top)
        logger.info(f"Lichess top updated for {dt.now()}")

    @commands.hybrid_command(
        aliases=["litop", "li-top", "li-lb", "lichess-lb", "li-leaderboard"],
        name="lichess-leaderboard",
        description="Shows current lichess leaderboard for all time formats and modes",
        with_app_command=True,
    )
    async def lichessleaderboard(self, ctx: commands.Context):
        async with AsyncTranslator(DF.get_lang_code(ctx.author.id)) as t:
            t.install()
            _ = t.gettext
            try:
                vital_info = LT.get_lichess_top(dt.utcnow())
                if not vital_info:
                    json_top = self.client.users.get_all_top_10()
                    vital_info = [json_top, dt.utcnow()]
                    LT.store_lichess_top(json_top)
                json_top = vital_info[0]
                embed = discord.Embed(
                    title=_("Lichess leaderboard - Rapid"),
                    description=_("*as for {}*").format(
                        timestamp_maker(vital_info[1], TimestampFormats.SHORT_DATE)
                    ),
                    color=bot_config.CustomColors.cyan,
                )
                for player in json_top["rapid"]:
                    embed.add_field(
                        name=f"Top {json_top['rapid'].index(player) + 1}",
                        value=f"{'**' + player['title'] + '**' if 'title' in player else ''} [{player['username']}](https://lichess.org/@/{player['username']}) "
                              + _("with rating")
                              + f" **{player['perfs']['rapid']['rating']}** ||{'+' if player['perfs']['rapid']['progress'] > 0 else ''}{player['perfs']['rapid']['progress']} {bot_config.CustomEmojis.progress_up if player['perfs']['rapid']['progress'] >= 0 else bot_config.CustomEmojis.progress_down}||",
                        inline=False,
                    )
                embed.set_footer(
                    text=_("Requested by {}").format(ctx.message.author.name),
                )
                view = LiTopView(vital_info, embed)
                view.message = await ctx.send(embed=embed, view=view)
                DF.add_to_command_stat(ctx.message.author.id)
            except Exception:
                embed_error = discord.Embed(
                    title=_("Error"),
                    description=_("Something went wrong"),
                    color=bot_config.CustomColors.dark_red,
                )
                await ctx.send(embed=embed_error)
                logger.exception("Error in lichesstop10")
                # self.bot.get_user(bot_config.admin_account_ids[0]).send(f"Error in lichesstop10: {e}")

    def game_id_link(self, id):
        game_link = f"(https://lichess.org/{id})"
        return game_link

    @commands.hybrid_command(
        aliases=["liplayer", "li-player", "li-p"],
        name="lichess-player",
        description="Shows lichess player's stats",
        with_app_command=True,
    )
    async def lichessplayer(
            self, ctx: commands.Context, nickname: str = None, mode: str = None
    ):
        async with AsyncTranslator(DF.get_lang_code(ctx.author.id)) as t:
            t.install()
            _ = t.gettext
            if not nickname:
                embed = discord.Embed(title=_("Please input a lichess username"))
                await ctx.send(embed=embed)
            modes = [
                "rapid",
                "blitz",
                "bullet",
                "classical",
                "puzzle",
                "chess960",
                "crazyhouse",
                "antichess",
                "atomic",
                "horde",
                "kingofthehill",
                "racingkings",
                "threecheck",
                "ultrabullet",
                "correspondence",
            ]
            if mode is None:
                try:
                    player = LT.get_lichess_player(nickname)
                    if player is None or player[
                        "time_cached"
                    ] < dt.utcnow() - timedelta(hours=3):
                        player = self.client.users.get_public_data(nickname)
                        LT.store_lichess_player(player)
                        time_cached = dt.utcnow()
                    else:
                        time_cached = player["time_cached"]

                    # realtime_status = self.client.users.get_realtime_statuses(*players) # This is not needed anymore
                    # print(player)
                    thumbnail = discord.File(
                        "Images/Lichess/Lichess.png", filename="Lichess.png"
                    )
                    unusual_flags = {
                        "_adygea": "flag_white",
                        "_rainbow": "rainbow_flag",
                        "_belarus-wrw": bot_config.CustomEmojis.belarus_wrw,
                        "_russian-wbw": bot_config.CustomEmojis.ru_wbw,
                        "ru": ":pirate_flag:",
                        "_east-turkestan": bot_config.CustomEmojis.east_turk,
                        "_pirate": ":pirate_flag:",
                        "_united-nations": ":united_nations:",
                        "_transgender": ":transgender_flag:",
                        "_earth": ":earth_africa:",
                        "_lichess": bot_config.CustomEmojis.lichess,
                    }
                    special_modes = {
                        "kingOfTheHill": "King of the Hill",
                        "threeCheck": "Three-check",
                        "racingKings": "Racing Kings",
                        "puzzle": "Puzzles",
                    }
                    username = player["username"]
                    if "title" in player:
                        username = f"**{player['title']}** {username}"
                    if "patron" in player:
                        username = f"{username} {bot_config.CustomEmojis.patron}"
                        thumbnail = discord.File(
                            "Images/Lichess/LichessPatronWings.png",
                            filename="LichessPatron.png",
                        )
                    if "flair" in player:
                        username += f" {fetch_flair(player['flair'])}"
                    if "disabled" in player:
                        username = f"{username}     ***DISABLED***"

                    embed = discord.Embed(
                        title=username,
                        description=_(
                            "Everything I could find about {} on lichess"
                        ).format(player["username"]),
                        color=bot_config.CustomColors.cyan,
                        timestamp=time_cached,
                    )
                    embed.set_thumbnail(url=f"attachment://{thumbnail.filename}")

                    embed.add_field(name=_("Username"), value=str(player["username"]))
                    if "profile" in player:
                        bio = (
                            player["profile"]["bio"]
                            if "bio" in player["profile"]
                            else _("*No bio*")
                        )
                        full_name = f"{player['profile']['firstName'] if 'firstName' in player['profile'] else '*~*'} {player['profile']['lastName'] if 'lastName' in player['profile'] else '*~*'}"
                    else:
                        full_name = "*~*"
                        bio = _("*No bio*")
                    embed.add_field(
                        name=_("Full name"),
                        value=full_name,
                    )
                    try:  # Used try-statement because some users don't have a country, or more countries might be added in the future
                        if player["profile"]["flag"].lower() in unusual_flags:
                            country_flag = unusual_flags[
                                player["profile"]["flag"].lower()
                            ]
                        else:
                            country_flag = f":flag_{player['profile']['flag'].lower()}:"
                    except Exception:
                        country_flag = ":united_nations:"
                    embed.add_field(name=_("Flag"), value=country_flag)
                    if "fideRating" in player:
                        embed.add_field(
                            name=_("FIDE rating"), value=player["fideRating"]
                        )
                    embed.add_field(
                        name=_("Bio"),
                        value=bio,
                        inline=False,
                    )
                    embed.add_field(
                        name=_("Last active"),
                        value=pretty_date(player["seenAt"])
                        if "seenAt" in player and player["seenAt"]
                        else _("Unknown"),
                    )
                    embed.add_field(
                        name=_("Created on"),
                        value=timestamp_maker(
                            player["createdAt"], TimestampFormats.SHORT_DATE_TIME
                        )
                        if "createdAt" in player and player["createdAt"]
                        else _("Unknown"),
                    )
                    if "playTime" in player:
                        embed.add_field(
                            name=_("Total playtime"),
                            value=f"{format_timespan(player['playTime']['total'])}\nTime on TV: {format_timespan(player['playTime']['tv'])}",
                        )
                    else:
                        embed.add_field(
                            name=_("Total playtime"),
                            value=_("Unknown"),
                        )
                    embed.add_field(
                        name=bot_config.CustomEmojis.empty,
                        value=bot_config.CustomEmojis.empty,
                        inline=False,
                    )
                    if "count" not in player:
                        player["count"] = {
                            "all": 0,
                            "rated": 0,
                            "ai": 0,
                            "win": 0,
                            "loss": 0,
                            "draw": 0,
                        }
                    stats_string = f"{_('All games')}: **{player['count']['all']}**\n"
                    stats_string += f"{_('Rated games')}: **{player['count']['rated']} ({percentage_calc(player['count']['all'], player['count']['rated'], round_to=1, if_round=True)}%)**\n"
                    stats_string += f"{_('Against AI')}: **{player['count']['ai']} ({percentage_calc(player['count']['all'], player['count']['ai'], round_to=1, if_round=True)}%)**\n"
                    stats_string += f"{_('Wins')}: **{player['count']['win']} ({percentage_calc(player['count']['all'], player['count']['win'], round_to=1, if_round=True)}%)**\n"
                    stats_string += f"{_('Losses')}: **{player['count']['loss']} ({percentage_calc(player['count']['all'], player['count']['loss'], round_to=1, if_round=True)}%)**\n"
                    stats_string += f"{_('Draws')}: **{player['count']['draw']} ({percentage_calc(player['count']['all'], player['count']['draw'], round_to=1, if_round=True)}%)**"

                    embed.add_field(
                        name=_("General stats"), value=stats_string, inline=True
                    )
                    modes_string = ""
                    if "perfs" not in player:
                        player["perfs"] = {}
                    for mode in player["perfs"]:
                        if mode in ["storm", "streak", "racer"]:
                            match mode:
                                case "storm":
                                    modes_string += f"{_('Puzzle storm')}: **{player['perfs'][mode]['score']}** points\n"
                                case "streak":
                                    modes_string += f"{_('Puzzle streak')}: **{player['perfs'][mode]['score']}** points\n"
                                case "racer":
                                    modes_string += f"{_('Puzzle racer')}: **{player['perfs'][mode]['score']}** points\n"
                        else:
                            modes_string += (
                                f"{mode.capitalize() if mode not in special_modes else special_modes[mode]}: **{player['perfs'][mode]['rating']}** "
                                f"""{f"||{'+' if player['perfs'][mode]['prog'] > 0 else ''}{player['perfs'][mode]['prog']} {bot_config.CustomEmojis.progress_down if player['perfs'][mode]['prog'] < 0 else bot_config.CustomEmojis.progress_up}||" if 'prog' in player['perfs'][mode] else ''}\n"""
                            )
                    embed.add_field(name=_("Rating"), value=modes_string, inline=True)
                    if "url" not in player:
                        player["url"] = f"https://lichess.org/@/{player['username']}"
                    links_value = f"[{_('Lichess profile')}]({player['url']})\n"
                    if (
                            "profile" not in player
                            or "links" not in player["profile"]
                            or player["profile"]["links"] == ""
                    ):
                        links = None
                    else:
                        links = [
                            link for link in player["profile"]["links"].split("\r\n")
                        ]
                    if links:
                        for link in links:
                            try:
                                link = urlparse(link)
                                links_value += f"[{link.netloc}]({link.geturl()})\n"
                            except Exception:
                                logger.exception(
                                    f"Couldn't parse link while processing {player['username']} lichess profile. Link: {link}"
                                )
                                continue
                    embed.add_field(name=_("Links"), value=links_value, inline=False)

                    await ctx.send(embed=embed, file=thumbnail)
                except Exception:
                    logger.exception("Couldn't find a player or unknown problem")
                    embed = discord.Embed(
                        title=_("Couldn't find any user with that username"),
                        color=bot_config.CustomColors.dark_red,
                    )
                    await ctx.send(embed=embed)
            elif mode.lower() in modes:
                double_word_modes = {
                    "kingofthehill": "King of the Hill",
                    "racingkings": "Racing Kings",
                    "threecheck": "Three-Check",
                }
                special_modes = {
                    "kingofthehill": "kingOfTheHill",
                    "threecheck": "threeCheck",
                    "racingkings": "racingKings",
                    "ultrabullet": "ultraBullet",
                }
                mode = mode.lower()
                if mode not in modes:
                    embed = discord.Embed(
                        title=_("Variant/Time control not recognized"),
                        description=_("Valid modes are: `{}`").format(", ".join(modes)),
                        color=bot_config.CustomColors.dark_red,
                    )
                    await ctx.send(embed=embed)
                    return
                if mode in special_modes:
                    mode = special_modes[mode]
                playerPerfinfo = LT.get_lichess_performance(nickname, mode)
                if not playerPerfinfo:
                    playerPerfinfo = LichessApiCall.get_user_performance(nickname, mode)
                    if not playerPerfinfo:
                        embed = discord.Embed(
                            title=_("Couldn't find any user with that username"),
                            color=bot_config.CustomColors.dark_red,
                        )
                        await ctx.send(embed=embed)
                        return
                    else:
                        LT.store_lichess_performance(nickname, playerPerfinfo)
                else:
                    if dt.strptime(
                            playerPerfinfo["time_cached"], "%Y-%m-%d %H:%M:%S"
                    ) < dt.utcnow() - timedelta(days=7):
                        playerPerfinfo = LichessApiCall.get_user_performance(
                            nickname, mode
                        )
                        if not playerPerfinfo:
                            embed = discord.Embed(
                                title=_("Couldn't find any user with that username"),
                                color=bot_config.CustomColors.dark_red,
                            )
                            await ctx.send(embed=embed)
                            return
                        else:
                            LT.store_lichess_performance(nickname, playerPerfinfo)
                    else:
                        pass
                print(playerPerfinfo)
                try:
                    if playerPerfinfo["stat"]["userId"]["title"] is not None:
                        nickname = f"{playerPerfinfo['stat']['userId']['title']} {playerPerfinfo['stat']['userId']['name']}"
                    else:
                        nickname = playerPerfinfo["stat"]["userId"]["name"]
                    embed = discord.Embed(
                        title=nickname,
                        description="Detailed stats on {mode}".format(
                            mode=mode.capitalize()
                            if mode not in double_word_modes
                            else double_word_modes[mode]
                        ),
                        color=bot_config.CustomColors.cyan,
                        timestamp=dt.strptime(
                            playerPerfinfo["time_cached"], "%Y-%m-%d %H:%M:%S"
                        ),
                    )

                    if playerPerfinfo["stat"]["count"]["all"] == 0:
                        embed.add_field(
                            name=_("Games"), value=_("*No games played*"), inline=False
                        )
                        embed.add_field(
                            name=_("Rating"),
                            value=_(
                                "Current rating: **{current_rating}?**\nDeviation: **{deviation}** ||(Zero games played)||"
                            ).format(
                                current_rating=math.floor(
                                    playerPerfinfo["perf"]["glicko"]["rating"]
                                ),
                                deviation=round(
                                    playerPerfinfo["perf"]["glicko"]["deviation"]
                                ),
                            ),
                            inline=False,
                        )
                    else:
                        embed.add_field(
                            name=_("Games"),
                            value=_(
                                "Total: **{total}**\nRated: **{rated} ({rated_percent}%)**\nWins: **{win} ({win_percent}%)**\nLosses: **{loss} ({loss_percent}%)**\nDraws: **{draw} ({draw_percent}%)**\nTournament: **{tournament} ({tournament_percent}%)**\nBerserk: **{berserk} ({berserk_tournament_percent}%)**\nDisconnects: **{disconnect} ({disconnect_percent}%)**\nAverage opponent's ELO: **~{average_elo}**\nTotal playtime: **{total_playtime}**\nRank: **{rank}**\n**Better than {better_than_percent} of players**"
                            ).format(
                                total=playerPerfinfo["stat"]["count"]["all"],
                                rated=playerPerfinfo["stat"]["count"]["rated"],
                                rated_percent=percentage_calc(
                                    playerPerfinfo["stat"]["count"]["all"],
                                    playerPerfinfo["stat"]["count"]["rated"],
                                    if_round=True,
                                    round_to=2,
                                ),
                                win=playerPerfinfo["stat"]["count"]["win"],
                                win_percent=percentage_calc(
                                    playerPerfinfo["stat"]["count"]["all"],
                                    playerPerfinfo["stat"]["count"]["win"],
                                    if_round=True,
                                    round_to=2,
                                ),
                                loss=playerPerfinfo["stat"]["count"]["loss"],
                                loss_percent=percentage_calc(
                                    playerPerfinfo["stat"]["count"]["all"],
                                    playerPerfinfo["stat"]["count"]["loss"],
                                    if_round=True,
                                    round_to=2,
                                ),
                                draw=playerPerfinfo["stat"]["count"]["draw"],
                                draw_percent=percentage_calc(
                                    playerPerfinfo["stat"]["count"]["all"],
                                    playerPerfinfo["stat"]["count"]["draw"],
                                    if_round=True,
                                    round_to=2,
                                ),
                                tournament=playerPerfinfo["stat"]["count"]["tour"],
                                tournament_percent=percentage_calc(
                                    playerPerfinfo["stat"]["count"]["all"],
                                    playerPerfinfo["stat"]["count"]["tour"],
                                    if_round=True,
                                    round_to=2,
                                ),
                                berserk=playerPerfinfo["stat"]["count"]["berserk"],
                                berserk_tournament_percent=percentage_calc(
                                    playerPerfinfo["stat"]["count"]["tour"],
                                    playerPerfinfo["stat"]["count"]["berserk"],
                                    if_round=True,
                                    round_to=2,
                                ),
                                disconnect=playerPerfinfo["stat"]["count"][
                                    "disconnects"
                                ],
                                disconnect_percent=percentage_calc(
                                    playerPerfinfo["stat"]["count"]["all"],
                                    playerPerfinfo["stat"]["count"]["disconnects"],
                                    if_round=True,
                                    round_to=2,
                                ),
                                average_elo=round(
                                    playerPerfinfo["stat"]["count"]["opAvg"]
                                ),
                                total_playtime=format_timespan(
                                    playerPerfinfo["stat"]["count"]["seconds"]
                                ),
                                rank=playerPerfinfo["rank"]
                                if playerPerfinfo["rank"] is not None
                                else _("*No rank this week yet*"),
                                better_than_percent=str(playerPerfinfo["percentile"])
                                                    + "%"
                                if playerPerfinfo["percentile"] is not None
                                else "0%",
                            ),
                            inline=False,
                        )
                        embed.add_field(
                            name=_("Rating"),
                            value=_(
                                "Current rating: **{current_rating}**\n[Deviation](https://lichess.org/forum/general-chess-discussion/rating-deviation#2): **{deviation}**\nHighest rating: **{best_rating}** on **{best_date} {best_link}**\nLowest rating: **{worst_rating}** on **{worst_date} {worst_link}**\nProgress: **{progress}**{arrow}"
                            ).format(
                                current_rating=math.floor(
                                    playerPerfinfo["perf"]["glicko"]["rating"]
                                ),
                                deviation=round(
                                    playerPerfinfo["perf"]["glicko"]["deviation"]
                                ),
                                best_rating=playerPerfinfo["stat"]["highest"]["int"]
                                if "highest" in playerPerfinfo["stat"]
                                else "*No highest rating yet*",
                                best_date=timestamp_maker(
                                    playerPerfinfo["stat"]["highest"]["at"],
                                    TimestampFormats.LONG_DATE_TIME,
                                )
                                if "highest" in playerPerfinfo["stat"]
                                else "*never*",
                                best_link=f" [Link]{self.game_id_link(playerPerfinfo['stat']['highest']['gameId'])}"
                                if "highest" in playerPerfinfo["stat"]
                                else "",
                                worst_rating=playerPerfinfo["stat"]["lowest"]["int"]
                                if "lowest" in playerPerfinfo["stat"]
                                else "*No lowest rating yet*",
                                worst_date=timestamp_maker(
                                    playerPerfinfo["stat"]["lowest"]["at"],
                                    TimestampFormats.LONG_DATE_TIME,
                                )
                                if "lowest" in playerPerfinfo["stat"]
                                else "*never*",
                                worst_link=f"[Link]{self.game_id_link(playerPerfinfo['stat']['lowest']['gameId'])}"
                                if "lowest" in playerPerfinfo["stat"]
                                else "",
                                progress=playerPerfinfo["perf"]["progress"],
                                arrow=bot_config.CustomEmojis.progress_down
                                if playerPerfinfo["perf"]["progress"] < 0
                                else bot_config.CustomEmojis.progress_up,
                            ),
                            inline=True,
                        )
                        if "resultStreak" in playerPerfinfo["stat"]:
                            if (
                                    "from"
                                    in playerPerfinfo["stat"]["resultStreak"]["win"]["cur"]
                                    or "from"
                                    in playerPerfinfo["stat"]["resultStreak"]["loss"]["cur"]
                            ):
                                current_streak = _(
                                    "Current streak: ({win_or_loss}) **{streak} [from]{from_link} {from_date} [to]{to_link} {to_date}**"
                                ).format(
                                    win_or_loss="Winning"
                                    if "from"
                                       in playerPerfinfo["stat"]["resultStreak"]["win"][
                                           "cur"
                                       ]
                                    else "Losing",
                                    streak=playerPerfinfo["stat"]["resultStreak"][
                                        "win"
                                    ]["cur"]["v"]
                                    if "from"
                                       in playerPerfinfo["stat"]["resultStreak"]["win"][
                                           "cur"
                                       ]
                                    else playerPerfinfo["stat"]["resultStreak"]["loss"][
                                        "cur"
                                    ]["v"],
                                    from_link=self.game_id_link(
                                        playerPerfinfo["stat"]["resultStreak"]["win"][
                                            "cur"
                                        ]["from"]["gameId"]
                                        if "from"
                                           in playerPerfinfo["stat"]["resultStreak"][
                                               "win"
                                           ]["cur"]
                                        else playerPerfinfo["stat"]["resultStreak"][
                                            "loss"
                                        ]["cur"]["from"]["gameId"]
                                    ),
                                    from_date=timestamp_maker(
                                        playerPerfinfo["stat"]["resultStreak"]["win"][
                                            "cur"
                                        ]["from"]["at"]
                                        if "from"
                                           in playerPerfinfo["stat"]["resultStreak"][
                                               "win"
                                           ]["cur"]
                                        else playerPerfinfo["stat"]["resultStreak"][
                                            "loss"
                                        ]["cur"]["from"]["at"],
                                        TimestampFormats.LONG_DATE_TIME,
                                    ),
                                    to_link=self.game_id_link(
                                        playerPerfinfo["stat"]["resultStreak"]["win"][
                                            "cur"
                                        ]["to"]["gameId"]
                                        if "to"
                                           in playerPerfinfo["stat"]["resultStreak"][
                                               "win"
                                           ]["cur"]
                                        else playerPerfinfo["stat"]["resultStreak"][
                                            "loss"
                                        ]["cur"]["to"]["gameId"]
                                    ),
                                    to_date=timestamp_maker(
                                        playerPerfinfo["stat"]["resultStreak"]["win"][
                                            "cur"
                                        ]["to"]["at"]
                                        if "to"
                                           in playerPerfinfo["stat"]["resultStreak"][
                                               "win"
                                           ]["cur"]
                                        else playerPerfinfo["stat"]["resultStreak"][
                                            "loss"
                                        ]["cur"]["to"]["at"],
                                        TimestampFormats.LONG_DATE_TIME,
                                    ),
                                )
                            else:
                                current_streak = _("*No current streak*")
                            embed.add_field(
                                name=_("Current streak"),
                                value=current_streak,
                                inline=False,
                            )
                            winning_streak = _(
                                "Longest winning streak: **{streak} [from]{from_link} {from_date} [to]{to_link} {to_date}**"
                            ).format(
                                streak=playerPerfinfo["stat"]["resultStreak"]["win"][
                                    "max"
                                ]["v"],
                                from_link=self.game_id_link(
                                    playerPerfinfo["stat"]["resultStreak"]["win"][
                                        "max"
                                    ]["from"]["gameId"]
                                )
                                if "from"
                                   in playerPerfinfo["stat"]["resultStreak"]["win"]["max"]
                                else "",
                                from_date=timestamp_maker(
                                    playerPerfinfo["stat"]["resultStreak"]["win"][
                                        "max"
                                    ]["from"]["at"],
                                    TimestampFormats.LONG_DATE_TIME,
                                )
                                if "from"
                                   in playerPerfinfo["stat"]["resultStreak"]["win"]["max"]
                                else "*never*",
                                to_link=self.game_id_link(
                                    playerPerfinfo["stat"]["resultStreak"]["win"][
                                        "max"
                                    ]["to"]["gameId"]
                                )
                                if "to"
                                   in playerPerfinfo["stat"]["resultStreak"]["win"]["max"]
                                else "",
                                to_date=timestamp_maker(
                                    playerPerfinfo["stat"]["resultStreak"]["win"][
                                        "max"
                                    ]["to"]["at"],
                                    TimestampFormats.LONG_DATE_TIME,
                                )
                                if "to"
                                   in playerPerfinfo["stat"]["resultStreak"]["win"]["max"]
                                else "*never*",
                            )
                            embed.add_field(
                                name=_("Winning streak"),
                                value=winning_streak,
                                inline=False,
                            )
                            losing_streak = _(
                                "Longest losing streak: **{streak} [from]{from_link} {from_date} [to]{to_link} {to_date}**"
                            ).format(
                                streak=playerPerfinfo["stat"]["resultStreak"]["loss"][
                                    "max"
                                ]["v"],
                                from_link=self.game_id_link(
                                    playerPerfinfo["stat"]["resultStreak"]["loss"][
                                        "max"
                                    ]["from"]["gameId"]
                                )
                                if "from"
                                   in playerPerfinfo["stat"]["resultStreak"]["loss"]["max"]
                                else "",
                                from_date=timestamp_maker(
                                    playerPerfinfo["stat"]["resultStreak"]["loss"][
                                        "max"
                                    ]["from"]["at"],
                                    TimestampFormats.LONG_DATE_TIME,
                                )
                                if "from"
                                   in playerPerfinfo["stat"]["resultStreak"]["loss"]["max"]
                                else "*never*",
                                to_link=self.game_id_link(
                                    playerPerfinfo["stat"]["resultStreak"]["loss"][
                                        "max"
                                    ]["to"]["gameId"]
                                )
                                if "to"
                                   in playerPerfinfo["stat"]["resultStreak"]["loss"]["max"]
                                else "",
                                to_date=timestamp_maker(
                                    playerPerfinfo["stat"]["resultStreak"]["loss"][
                                        "max"
                                    ]["to"]["at"],
                                    TimestampFormats.LONG_DATE_TIME,
                                )
                                if "to"
                                   in playerPerfinfo["stat"]["resultStreak"]["loss"]["max"]
                                else "*never*",
                            )
                            embed.add_field(
                                name=_("Losing streak"),
                                value=losing_streak,
                                inline=False,
                            )

                        if playerPerfinfo["stat"]["bestWins"]["results"] == []:
                            best_rated_wins = _("*No best rated wins*")
                        else:
                            best_rated_wins = ""
                            for win in playerPerfinfo["stat"]["bestWins"]["results"]:
                                best_rated_wins += _(
                                    "Against {title} [{opponent}]{op_link} with rating **{op_rating}** [on]{game_link} {date_played}\n"
                                ).format(
                                    title=f'***{win["opId"]["title"]}***'
                                    if win["opId"]["title"] is not None
                                    else "",
                                    opponent=win["opId"]["name"],
                                    op_link=self.game_id_link(win["opId"]["id"]),
                                    op_rating=win["opRating"],
                                    date_played=timestamp_maker(
                                        win["at"], TimestampFormats.SHORT_DATE_TIME
                                    ),
                                    game_link=self.game_id_link(win["gameId"]),
                                )
                        embed.add_field(
                            name=_("Best rated wins"),
                            value=best_rated_wins,
                            inline=False,
                        )

                        if playerPerfinfo["stat"]["worstLosses"]["results"] == []:
                            worst_rated_losses = _("*No worst rated losses*")
                        else:
                            worst_rated_losses = ""
                            for loss in playerPerfinfo["stat"]["worstLosses"][
                                "results"
                            ]:
                                worst_rated_losses += _(
                                    "Against {title} [{opponent}]{op_link} with rating **{op_rating}** [on]{game_link} {date_played}\n"
                                ).format(
                                    title=f'***{loss["opId"]["title"]}***'
                                    if loss["opId"]["title"] is not None
                                    else "",
                                    opponent=loss["opId"]["name"],
                                    op_link=self.game_id_link(loss["opId"]["id"]),
                                    op_rating=loss["opRating"],
                                    date_played=timestamp_maker(
                                        loss["at"], TimestampFormats.SHORT_DATE_TIME
                                    ),
                                    game_link=self.game_id_link(loss["gameId"]),
                                )
                        embed.add_field(
                            name=_("Worst rated losses"),
                            value=worst_rated_losses,
                            inline=False,
                        )

                        if playerPerfinfo["stat"]["playStreak"]["nb"]["max"]["v"] == 0:
                            longest_playstreak = _("*No longest play streak*")
                        else:
                            longest_playstreak = _(
                                "Longest play streak: **{streak} \n[from]{from_link} {from_date} \n[to]{to_link} {to_date}**\n"
                            ).format(
                                streak=playerPerfinfo["stat"]["playStreak"]["nb"][
                                    "max"
                                ]["v"],
                                from_link=self.game_id_link(
                                    playerPerfinfo["stat"]["playStreak"]["nb"]["max"][
                                        "from"
                                    ]["gameId"]
                                ),
                                from_date=timestamp_maker(
                                    playerPerfinfo["stat"]["playStreak"]["nb"]["max"][
                                        "from"
                                    ]["at"],
                                    TimestampFormats.SHORT_DATE_TIME,
                                ),
                                to_link=self.game_id_link(
                                    playerPerfinfo["stat"]["playStreak"]["nb"]["max"][
                                        "to"
                                    ]["gameId"]
                                ),
                                to_date=timestamp_maker(
                                    playerPerfinfo["stat"]["playStreak"]["nb"]["max"][
                                        "to"
                                    ]["at"],
                                    TimestampFormats.SHORT_DATE_TIME,
                                ),
                            )

                        if playerPerfinfo["stat"]["playStreak"]["nb"]["cur"]["v"] == 0:
                            current_playstreak = _("*No current play streak*")
                        else:
                            current_playstreak = _(
                                "Current play streak: **{streak} \n[from]{from_link} {from_date} \n[to]{to_link} {to_date}**"
                            ).format(
                                streak=playerPerfinfo["stat"]["playStreak"]["nb"][
                                    "cur"
                                ]["v"],
                                from_link=self.game_id_link(
                                    playerPerfinfo["stat"]["playStreak"]["nb"]["cur"][
                                        "from"
                                    ]["gameId"]
                                ),
                                from_date=timestamp_maker(
                                    playerPerfinfo["stat"]["playStreak"]["nb"]["cur"][
                                        "from"
                                    ]["at"],
                                    TimestampFormats.SHORT_DATE_TIME,
                                ),
                                to_link=self.game_id_link(
                                    playerPerfinfo["stat"]["playStreak"]["nb"]["cur"][
                                        "to"
                                    ]["gameId"]
                                ),
                                to_date=timestamp_maker(
                                    playerPerfinfo["stat"]["playStreak"]["nb"]["cur"][
                                        "to"
                                    ]["at"],
                                    TimestampFormats.SHORT_DATE_TIME,
                                ),
                            )
                        embed.add_field(
                            name=_("Play streak"),
                            value=longest_playstreak + current_playstreak,
                            inline=False,
                        )

                        if (
                                playerPerfinfo["stat"]["playStreak"]["time"]["max"]["v"]
                                == 0
                        ):
                            longest_playstreak_time = _(
                                "Longest streak: **0 seconds**\n"
                            )
                        else:
                            longest_playstreak_time = _(
                                "Longest streak: **{streak} \n[from]{from_link} {from_date} \n[to]{to_link} {to_date}**\n"
                            ).format(
                                streak=format_timespan(
                                    playerPerfinfo["stat"]["playStreak"]["time"]["max"][
                                        "v"
                                    ]
                                ),
                                from_link=self.game_id_link(
                                    playerPerfinfo["stat"]["playStreak"]["time"]["max"][
                                        "from"
                                    ]["gameId"]
                                ),
                                from_date=timestamp_maker(
                                    playerPerfinfo["stat"]["playStreak"]["time"]["max"][
                                        "from"
                                    ]["at"],
                                    TimestampFormats.SHORT_DATE_TIME,
                                ),
                                to_link=self.game_id_link(
                                    playerPerfinfo["stat"]["playStreak"]["time"]["max"][
                                        "to"
                                    ]["gameId"]
                                ),
                                to_date=timestamp_maker(
                                    playerPerfinfo["stat"]["playStreak"]["time"]["max"][
                                        "to"
                                    ]["at"],
                                    TimestampFormats.SHORT_DATE_TIME,
                                ),
                            )

                        if (
                                playerPerfinfo["stat"]["playStreak"]["time"]["cur"]["v"]
                                == 0
                        ):
                            current_playstreak_time = _("Current streak: **0 seconds**")
                        else:
                            current_playstreak_time = _(
                                "Current streak: **{streak} \n[from]{from_link} {from_date} \n[to]{to_link} {to_date}**"
                            ).format(
                                streak=format_timespan(
                                    playerPerfinfo["stat"]["playStreak"]["time"]["cur"][
                                        "v"
                                    ]
                                ),
                                from_link=self.game_id_link(
                                    playerPerfinfo["stat"]["playStreak"]["time"]["cur"][
                                        "from"
                                    ]["gameId"]
                                ),
                                from_date=timestamp_maker(
                                    playerPerfinfo["stat"]["playStreak"]["time"]["cur"][
                                        "from"
                                    ]["at"],
                                    TimestampFormats.SHORT_DATE_TIME,
                                ),
                                to_link=self.game_id_link(
                                    playerPerfinfo["stat"]["playStreak"]["time"]["cur"][
                                        "to"
                                    ]["gameId"]
                                ),
                                to_date=timestamp_maker(
                                    playerPerfinfo["stat"]["playStreak"]["time"]["cur"][
                                        "to"
                                    ]["at"],
                                    TimestampFormats.SHORT_DATE_TIME,
                                ),
                            )
                        embed.add_field(
                            name=_("Time spent playing"),
                            value=longest_playstreak_time + current_playstreak_time,
                            inline=False,
                        )

                    thumbnail = discord.File(
                        "Images/Lichess/Lichess.png", filename="Lichess.png"
                    )
                    embed.set_thumbnail(url=f"attachment://{thumbnail.filename}")
                    await ctx.send(embed=embed, file=thumbnail)
                except Exception as e:
                    logger.exception("Unknown error occurred in lichess player command")
                    embed = discord.Embed(
                        title=_("Unknown error occurred"),
                        description=_(
                            "Please try again later, details were sent to the developer"
                        ),
                        color=bot_config.CustomColors.dark_red,
                    )
                    embed_error = discord.Embed(
                        title="Unknown error occurred in lichess player command",
                        description=f"```{e}```",
                        color=bot_config.CustomColors.dark_red,
                    )
                    embed_error.add_field(
                        name="Metadata",
                        value=f"```{ctx.message.content}```\n\n\n```{playerPerfinfo if playerPerfinfo is not None else ''}```",
                        inline=False,
                    )
                    try:
                        await self.bot.get_user(bot_config.admin_account_ids[0]).send(
                            embed=embed_error
                        )
                    except Exception:
                        await self.bot.fetch_user(bot_config.admin_account_ids[0]).send(
                            embed=embed_error
                        )
                    await ctx.send(embed=embed)
            elif mode.lower() in ["game", "g", "games"]:
                try:
                    fetching_message = await ctx.send(
                        _("Please wait, fetching game data...")
                    )
                    game_id_list = LT.get_ten_lichess_games_from_user(nickname)
                    if not game_id_list:
                        game_list_exp = LichessApiCall.export_by_player(
                            nickname, clocks=True, literate=True, opening=True, limit=10
                        )
                        game_ids, game_list = [], []
                        for game in game_list_exp:
                            LT.store_lichess_game(game)
                            game_ids.append(game["id"])
                            game_list.append(game)
                        LT.store_ten_lichess_games_from_user(nickname, game_ids)
                    else:
                        game_list, unprocessed_ids = LT.get_lichess_games_bulk(
                            game_id_list
                        )

                        if len(unprocessed_ids) != 0:
                            exported_games = self.client.games.export_multi(
                                *game_id_list, clocks=True, opening=True
                            )
                            for game in exported_games:
                                LT.store_lichess_game(game)
                                game_list.append(game)

                    # Create embed containing all games. Ids as names of fields, player names as values
                    embed = discord.Embed(
                        title=_("Games of {nickname}").format(nickname=nickname),
                        description=_("Click on the game id to view the game"),
                        color=bot_config.CustomColors.cyan,
                    )

                    for game in game_list:
                        embed.add_field(
                            name=game["perf"].capitalize()
                                 + " "
                                 + game["variant"].capitalize(),
                            value=f"**{game['players']['white']['user']['name']} ({game['players']['white']['rating']})** {game['players']['white']['ratingDiff'] if 'ratingDiff' in game['players']['white'] else 0}{bot_config.CustomEmojis.progress_down if 'ratingDiff' in game['players']['white'] and game['players']['white']['ratingDiff'] < 0 else bot_config.CustomEmojis.progress_up}"
                                  f"\n[vs]{self.game_id_link(game['id'])} \n**{game['players']['black']['user']['name']} ({game['players']['black']['rating']})** {game['players']['black']['ratingDiff'] if 'ratingDiff' in game['players']['black'] else 0}{bot_config.CustomEmojis.progress_down if 'ratingDiff' in game['players']['black'] and game['players']['black']['ratingDiff'] < 0 else bot_config.CustomEmojis.progress_up}\n"
                                  f"ID: **{game['id']}**",
                            inline=False,
                        )

                    await fetching_message.edit(content="", embed=embed)
                except Exception as e:
                    logger.exception("Unknown error occurred in lichess game command")
                    embed = discord.Embed(
                        title=_("Unknown error occurred"),
                        description="Please try again later, details were sent to the developer",
                        color=bot_config.CustomColors.dark_red,
                    )
                    embed_error = discord.Embed(
                        title="Unknown error occurred in lichess game command",
                        description=f"```{e}```",
                        color=bot_config.CustomColors.dark_red,
                    )
                    embed_error.add_field(
                        name="Metadata",
                        value=f"```{ctx.message.content}```",
                        inline=False,
                    )
                    try:
                        await self.bot.get_user(bot_config.admin_account_ids[0]).send(
                            embed=embed_error
                        )
                    except Exception:
                        await self.bot.fetch_user(bot_config.admin_account_ids[0]).send(
                            embed=embed_error
                        )
                    await ctx.send(embed=embed)
                    return
        DF.add_to_command_stat(ctx.author.id)

    @commands.hybrid_command(
        name="lichess-game",
        description="A PGN viewer for games played on lichess",
        aliases=["li-game", "li-g", "lichessgame"],
        with_app_command=True,
    )
    async def lichessgame(self, ctx: commands.Context, _id: str):
        # PGN viewer for discord taking games from lichess, by game id
        # search_method: game
        # _id: game id
        # example: .lichessgame 42yhFd8k
        async with AsyncTranslator(
                language_code=DF.get_lang_code(ctx.author.id)
        ) as lang:
            lang.install()
            _ = lang.gettext

            try:
                fetching_message = await ctx.send(
                    _("Please wait, fetching game data...")
                )

                game = LichessGame(
                    client=self.client,
                    message=fetching_message,
                    channel_id=ctx.channel.id,
                    game_id=_id,
                    gettext_=_,
                    user_id=ctx.author.id,
                )
                DF.add_to_command_stat(ctx.author.id)
            except Exception as e:
                if e.__class__ in [
                    requests.exceptions.HTTPError,
                    berserk.exceptions.ResponseError,
                ]:
                    logger.info(f"Game with ID of {_id} not found")
                    embed = discord.Embed(
                        title=_("Game not found"),
                        description=_("Please check the game id and try again"),
                        color=bot_config.CustomColors.dark_red,
                    )
                    await fetching_message.edit(content="", embed=embed)
                    if "game" in locals():
                        del game
                    DF.add_to_command_stat(ctx.author.id)
                    return
                logger.exception("Unknown error occurred in lichess game command")
                embed = discord.Embed(
                    title=_("Unknown error occurred"),
                    description=_(
                        "Please try again later, details were sent to the developer"
                    ),
                    color=bot_config.CustomColors.dark_red,
                )
                await fetching_message.edit(content="", embed=embed)
                await send_report_exc(
                    e,
                    "Unknown error occurred in lichess game command",
                    func=ctx.command.name,
                    line=e.__traceback__.tb_lineno,
                    ctx=ctx,
                )

    @commands.hybrid_command(
        name="random-opening",
        description="A random inspirational opening, to try something new",
        aliases=[
            "roc",
            "randomopeningchallenge",
            "randomopening",
            "randomopeningchall",
            "randomopeningch",
            "randomopeningc",
        ],
        with_app_command=True,
    )
    async def randomopening(self, ctx: commands.Context):
        async with AsyncTranslator(
                language_code=DF.get_lang_code(ctx.author.id)
        ) as lang:
            lang.install()
            _ = lang.gettext

            opening_cache = rco.get_user_from_cache(ctx.author.id)

            if opening_cache is None:
                opening_basic_info = rco.generate_opening().split("\t")
                opening_cache = {
                    "code": opening_basic_info[0],
                    "name": opening_basic_info[1],
                    "moves": opening_basic_info[2],
                }
                rco.load_user_to_cache(ctx.author.id, opening_cache)

            embed = discord.Embed(
                title=_("Random Opening"),
                description=_("Try this opening out!"),
                color=bot_config.CustomColors.cyan,
            )
            embed.add_field(
                name=_("Name"),
                value=f"**{opening_cache['code']} | {opening_cache['name']}**",
                inline=False,
            )
            embed.add_field(
                name=_("Moves"),
                value=f"{opening_cache['moves']}",
                inline=False,
            )
            board = chess.Board()
            for move in opening_cache["moves"].split(" "):
                if move[-1] != ".":
                    board.push_san(move.replace("\n", ""))

            check_sq = board.king(board.turn) if board.is_check() else None
            discord_file, attachment = board_to_image(
                board, chess.Move.from_uci(board.peek().uci()), check_sq
            )
            embed.set_image(url=f"attachment://{discord_file.filename}")
            embed.set_footer(
                text=_("Refreshes in {in_time}").format(
                    in_time=pretty_time_delta(
                        0,
                        time_delta=(dt.utcnow() + timedelta(days=1)).replace(
                            hour=0, minute=0, second=0, microsecond=0
                        )
                                   - dt.utcnow(),
                    )
                )
            )
            await ctx.send(embed=embed, file=discord_file)
            DF.add_to_command_stat(ctx.author.id)

    # TODO: Chess.com commands

    @commands.hybrid_command(
        name="chesscom-player",
        description="Get information about a player on chess.com",
        aliases=["chesscom-p", "cc-p", "ccplayer"],
        with_app_command=True,
    )
    async def chess_com_player(self, ctx: commands.Context, username: str):
        async with AsyncTranslator(
                language_code=DF.get_lang_code(ctx.author.id)
        ) as lang:
            lang.install()
            _ = lang.gettext

            try:
                fetching_message = await ctx.send(_("Please wait, fetching player data..."))

                # Try to get player data from the cache
                player_data_db = LT.get_cc_player_by_username(username)

                if player_data_db is None:  # If the player is not in the cache, fetch profile from the API
                    player_profile = await self.cdc_caller.add_to_queue(CDCApiCall.get_player_profile, username)
                elif (player_data_db.get(
                        "json_profile_data") is None  # If the player is in the cache, but the data is not fetched...
                      or dt.strptime(player_data_db.get("json_profile_data").get("time_cached"), "%Y-%m-%d %H:%M:%S")
                      < dt.now() - timedelta(days=1)):  # ...or expired
                    player_profile = await self.cdc_caller.add_to_queue(CDCApiCall.get_player_profile, username)
                else:  # If the player is in the cache and the data is fresh
                    player_profile = player_data_db.get("json_profile_data")

                if isinstance(player_profile, dict):  # If the profile data is fetched successfully
                    if 'time_cached' not in player_profile:  # If the data is not cached
                        LT.store_cc_player_profile(player_profile)
                elif isinstance(player_profile,
                                int):  # If the profile data is not fetched successfully case 1 (other http code error)
                    embed = discord.Embed(
                        title=_("Unknown error occurred"),
                        description=_("Please try again later. Details were sent to the developer"),
                        color=bot_config.CustomColors.dark_red,
                    )
                    await fetching_message.edit(content="", embed=embed)
                    logger.error(f"Error occurred while fetching player data. Response code: {player_data_db}")
                    await send_report(
                        f"Error occurred while fetching player data. Response code: {player_data_db}. Username: {username}")
                    DF.add_to_command_stat(ctx.author.id)
                    return
                else:  # If the profile data is not fetched successfully case 2 (404 error not found)
                    embed = discord.Embed(
                        title=_("Player not found"),
                        description=_("Please check the username and try again"),
                        color=bot_config.CustomColors.dark_red,
                    )
                    await fetching_message.edit(content="", embed=embed)
                    DF.add_to_command_stat(ctx.author.id)
                    return

                # Same thing with stats data (expiration time is shorter)
                # So the trick is to save an extra API call if user doesn't exist
                if player_data_db is not None and (player_data_db.get("json_player_stats") is None or dt.strptime(
                        player_data_db.get("json_player_stats").get("time_cached"),
                        "%Y-%m-%d %H:%M:%S") < dt.now() - timedelta(minutes=30)):
                    player_stats = player_data_db.get("json_player_stats")
                else:
                    player_stats = await self.cdc_caller.add_to_queue(CDCApiCall.get_player_stats, username)
                    LT.store_cc_player_stats(player_stats, player_profile["player_id"])

                country_code = player_profile["country"][
                               -2:] if "country" in player_profile else None  # Get country code from the api link bruh
                country_info = pycountry.countries.get(alpha_2=country_code)  # Get country name from country code

                username = [
                    (player_profile["title"] if "title" in player_profile else ""),
                    player_profile["username"],
                    (country_info.flag if country_info is not None else ''),
                ]

                # Unused, but let it be here for now
                async def get_online_status(player_id, username_to_check):
                    is_online = LocalCache.get_player_online(player_id)

                    if is_online in (
                    -1, None):  # -1 is returned if the player is in the cache, but the data has expired
                        initial_value = is_online
                        is_online = await self.cdc_caller.add_to_queue(CDCApiCall.get_player_online_status,
                                                                       username_to_check)
                        if is_online is None: raise Exception("Error occurred while fetching online status")
                        is_online = is_online["online"]
                        if initial_value is None:
                            LocalCache.add_player_online(player_id, is_online, dt.now().strftime("%Y-%m-%d %H:%M:%S"))
                        else:
                            LocalCache.update_player_online(player_id, is_online,
                                                            dt.now().strftime("%Y-%m-%d %H:%M:%S"))
                    else:
                        is_online = bool(is_online)

                    return is_online

                def process_status(status: str) -> str:
                    """
                    Process the status of the player
                    :param status: str - status of the player
                        - closed, closed:fair_play_violations, basic, premium, mod, staff
                    :return: str - emoji string
                    """
                    # I planned to add more functionality to this function, but I'll pos
                    status_emojis: dict[str, str] = {
                        "closed": bot_config.CustomEmojis.gray_no_entry_sign,
                        "closed:fair_play_violations": ":no_entry_sign:",
                        "basic": "",
                        "premium": ":gem:",
                        "mod": bot_config.CustomEmojis.chess_mod,
                        "staff": bot_config.CustomEmojis.chess_staff,
                    }
                    return status_emojis.get(status, "")

                status_emoji = process_status(player_profile["status"])
                username.append(status_emoji)
                username.append(bot_config.CustomEmojis.twitch_logo if player_profile["is_streamer"] else "")

                embed = discord.Embed(
                    title=" ".join(username),
                    description=_("{username}'s profile on [chess.com]({link})").format(username=username[1],
                                                                                        link=player_profile['url']),
                    # username[1] is the raw username
                    color=bot_config.CustomColors.cyan if player_profile[
                                                              "status"] != "closed:fair_play_violations" else bot_config.CustomColors.dark_red,
                    timestamp=dt.strptime(player_profile['time_cached'],
                                          "%Y-%m-%d %H:%M:%S") if 'time_cached' in player_profile else dt.now(),
                )
                logger.debug(player_profile)
                logger.debug(player_stats)

                embed.set_thumbnail(
                    url=player_profile["avatar"] if "avatar" in player_profile else bot_config.Chess.default_avatar_url)

                embed.add_field(
                    name=_("Full name"),
                    value=player_profile["name"] if "name" in player_profile else _("*No full name provided*"),
                    inline=True,
                )

                location_string = (country_info.name if country_info else '*Unknown*') + ', ' + (
                    player_profile["location"] if "location" in player_profile else _("*No city provided*"))
                embed.add_field(
                    name=_("Location"),
                    value=location_string,
                    inline=True,
                )
                embed.add_field(
                    name=_("Followers"),
                    value=player_profile["followers"],
                    inline=True,
                )

                embed.add_field(
                    name=_("Created on"),
                    value=timestamp_maker(player_profile["joined"], TimestampFormats.SHORT_DATE_TIME),
                    inline=True,
                )
                # // player_is_online = await get_online_status(player_profile["player_id"], username)
                # getting online status is currently broken smh
                embed.add_field(
                    name=_("Last online"),
                    value=timestamp_maker(player_profile["last_online"], TimestampFormats.RELATIVE_TIME),
                    # // + f" ({_('Online {}').format(':green_circle:') if bool(player_is_online) else _('Offline {}').format(':gray_circle:')})",
                    inline=True,
                )

                embed.add_field(
                    name=_("Twitch Stream Link"),
                    value="[{name}]({link})".format(
                        name=player_profile["twitch_url"].split('/')[-1].capitalize(),
                        # Get the last part of the link (username of the streamer)
                        link=player_profile["twitch_url"]
                    ),
                    inline=False,
                ) if "twitch_url" in player_profile else \
                    embed.add_field(name="\u200B", value="\u200B",
                                    inline=False)  # If the user is not a streamer, don't show the field, but still make a "line-break" with inline=False

                def process_stats(stats: dict) -> tuple[dict, dict]:
                    return_stats = {
                        "win": 0,
                        "loss": 0,
                        "draw": 0,
                    }
                    return_ratings = {
                        "rapid": stats["chess_rapid"]["last"]["rating"] if "chess_rapid" in stats else "*?*",
                        "bullet": stats["chess_bullet"]["last"]["rating"] if "chess_bullet" in stats else "*?*",
                        "blitz": stats["chess_blitz"]["last"]["rating"] if "chess_blitz" in stats else "*?*",
                        "daily": stats["chess_daily"]["last"]["rating"] if "chess_daily" in stats else "*?*",
                        "960": stats["chess960_daily"]["last"]["rating"] if "chess960_daily" in stats else "*?*",
                        "tactics": stats["tactics"]["highest"]["rating"] if "tactics" in stats else "*?*",
                        # Highest tactics rating
                        "puzzle_rush": stats["puzzle_rush"]["best"]["score"] if "puzzle_rush" in stats else "*?*",
                        # Best puzzle rush score
                    }

                    for time_control in stats:
                        if time_control in ["tactics", "puzzle_rush", "fide", "time_cached"]:
                            continue
                        return_stats["win"] += stats[time_control]["record"]["win"]
                        return_stats["loss"] += stats[time_control]["record"]["loss"]
                        return_stats["draw"] += stats[time_control]["record"]["draw"]
                    return return_stats, return_ratings

                general_stats, ratings = process_stats(player_stats)
                all_games = general_stats["win"] + general_stats["loss"] + general_stats["draw"]

                embed.add_field(
                    name=_("General stats"),
                    value=_(
                        "All games: **{all}**\nWins: **{win} ({wr}%)**\nLosses: **{loss} ({lr}%)**\nDraws: **{draw} ({dr}%)**"
                        # wr - Winrate, lr - Loss rate, dr - Draw rate
                    ).format(
                        all=all_games,
                        win=general_stats["win"],
                        wr=percentage_calc(all_games, general_stats["win"], True),
                        loss=general_stats["loss"],
                        lr=percentage_calc(all_games, general_stats["loss"], True),
                        draw=general_stats["draw"],
                        dr=percentage_calc(all_games, general_stats["draw"], True),
                    ),
                    inline=True
                )

                embed.add_field(
                    name=_("Rating"),
                    value=_(
                        "Rapid: **{rapid}**\nBullet: **{bullet}**\nBlitz: **{blitz}**\nDaily: **{daily}**\nChess960: **{chess960}**\nHighest puzzles rating: **{tactics}**\nPuzzle Rush: **{puzzle_rush}**"
                    ).format(
                        rapid=ratings["rapid"],
                        bullet=ratings["bullet"],
                        blitz=ratings["blitz"],
                        daily=ratings["daily"],
                        chess960=ratings["960"],
                        tactics=ratings["tactics"],
                        puzzle_rush=ratings["puzzle_rush"],
                    ) + "\nFIDE: **{fide}**".format(fide=player_stats["fide"]) if "fide" in player_stats else "",
                    inline=True
                )
                # 'verified': False, 'league': 'Champion'
                embed.add_field(name="\u200B", value="\u200B", inline=False)
                stats_index = 0
                for time_control in player_stats:

                    if time_control in ["tactics", "puzzle_rush", "fide", "time_cached"]:
                        continue
                    stats_index += 1
                    if stats_index % 3 == 0:
                        embed.add_field(name="\u200B", value="\u200B", inline=False)
                        stats_index += 1
                    total_amount_of_games_in_control = player_stats[time_control]["record"]["win"] + \
                                                       player_stats[time_control]["record"]["loss"] + \
                                                       player_stats[time_control]["record"]["draw"]
                    embed.add_field(
                        name=_("{} stats").format(time_control.split('_')[
                                                      1].capitalize() if time_control != "chess960_daily" else "Daily960"),
                        value=_(
                            "Current rating: **{rating}**\nHighest rating: **{best}**\n**Games:**\n{empty}Total: **{total}**\n{empty}Wins: **{win} ({wr}%)**\n{empty}Losses: **{loss} ({lr}%)**\n{empty}Draws: **{draw} ({dr}%)**"
                        ).format(
                            rating=str(player_stats[time_control]["last"]["rating"]) + (
                                '?' if player_stats[time_control]["last"]["rd"] > 75 else ''),
                            best=player_stats[time_control]["best"]["rating"] if "best" in player_stats[
                                time_control] else player_stats[time_control]["last"]["rating"],
                            total=total_amount_of_games_in_control,
                            win=player_stats[time_control]["record"]["win"],
                            wr=percentage_calc(total_amount_of_games_in_control,
                                               player_stats[time_control]["record"]["win"], True),
                            loss=player_stats[time_control]["record"]["loss"],
                            lr=percentage_calc(total_amount_of_games_in_control,
                                               player_stats[time_control]["record"]["loss"], True),
                            draw=player_stats[time_control]["record"]["draw"],
                            dr=percentage_calc(total_amount_of_games_in_control,
                                               player_stats[time_control]["record"]["draw"], True),
                            empty=bot_config.CustomEmojis.empty,
                        ) + ("\nTime per move: **{time}**\nTimeout percent: **{timeout}%**".format(
                            time=player_stats[time_control]["record"]["time_per_move"],
                            timeout=player_stats[time_control]["record"][
                                "timeout_percent"]) if "daily" in time_control else ""),
                        inline=True,
                    )

                await fetching_message.edit(content="", embed=embed)

            except Exception as e:
                logger.exception("Unknown error occurred in chess.com player command")
                embed = discord.Embed(
                    title=_("Unknown error occurred"),
                    description=_(
                        "Please try again later, details were sent to the developer"
                    ),
                    color=bot_config.CustomColors.dark_red,
                )

                await fetching_message.edit(content="", embed=embed)
                await send_report_exc(
                    e,
                    "Unknown error occurred in chess.com player command",
                    func=ctx.command.name,
                    line=e.__traceback__.tb_lineno,
                    ctx=ctx,
                )

                return

    # TODO: Chess puzzles


async def setup(bot):
    await bot.add_cog(Chess(bot))

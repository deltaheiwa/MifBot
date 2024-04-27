import asyncio
import aiohttp
import os
import json
import requests
from datetime import datetime as dt
from typing import Any, Callable, Literal

from dotenv import load_dotenv

from bot_util.misc import Logger
from bot_util.functions.universal import regulated_request
from bot_util import bot_config

load_dotenv("creds/.env")

logger = Logger(__name__, log_file_path=bot_config.LogFiles.functions_log)


class WovAPICaller:
    """
    This class is used to make API calls to the Wolvesville API.
    Respects queue
    """
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(WovAPICaller, cls).__new__(cls)
        return cls._instance

    def __init__(self):
        if not hasattr(self, 'initialized'):
            self.queue = asyncio.Queue()
            self.worker = asyncio.create_task(self.process_queue())
            self.initialized = True

    async def add_to_queue(self, func: Callable, *args: Any):
        future = asyncio.Future()
        await self.queue.put((func, args, future))
        return await future

    async def process_queue(self):
        while True:
            func, args, future = await self.queue.get()
            try:
                result = await func(*args)
                future.set_result(result)
            except Exception as e:
                future.set_exception(e)
            self.queue.task_done()
            await asyncio.sleep(1)  # Respect the rate limit.


class WovClanApiCall:
    headers = {"Authorization": f"Bot {os.getenv('WOV_CLAN_CHAT_API_TOKEN')}"}
    api_url = "https://api.wolvesville.com/"

    @classmethod
    async def get_clan_chat(cls, clan_id: str, time=None):
        """
        Retrieves the clan chat for a given clan ID.

        Args:
            clan_id (str): The ID of the clan.
            time (str, optional): The oldest timestamp for the chat messages. Defaults to None.
                Format: YYYY-MM-DDTHH:MM:SS.000Z

        Returns:
            dict: The clan chat data in JSON format if the API call is successful, None otherwise.
        """

        async with aiohttp.ClientSession() as session:
            async with session.get(
                    url=cls.api_url + f"clans/{clan_id}/chat" + ("?oldest=" + time if time else ""),
                    headers=cls.headers,
            ) as response:
                if response.status == 200:
                    return await response.json()
                else:
                    logger.error(
                        f"Wov Clan Chat API call failed with status code {response.status}. Clan ID: {clan_id}"
                    )
                    return None

    @classmethod
    async def send_message_to_clan(cls, clan_id: str, message: str):
        """
        Sends a message to the clan chat.

        Args:
            clan_id (str): The ID of the clan.
            message (str): The message to send.

        Returns:
            dict: The clan chat data in JSON format if the API call is successful, response code otherwise.
        """

        async with aiohttp.ClientSession() as session:
            async with session.post(
                    url=cls.api_url + f"clans/{clan_id}/chat",
                    headers=cls.headers,
                    json={"message": message}
            ) as response:
                if response.status == 204:
                    return True
                else:
                    logger.error(
                        f"Wov Clan Chat API call failed with status code {response.status}. Clan ID: {clan_id}"
                    )
                    return response.status

    @classmethod
    async def get_authorized_clans(cls):
        async with aiohttp.ClientSession() as session:
            async with session.get(
                    url=cls.api_url + "clans/authorized", headers=cls.headers
            ) as response:
                if response.status == 200:
                    return await response.json()
                else:
                    logger.error(
                        f"Wov Authorized Clans API call failed with status code {response.status}."
                    )
                    return None

    @classmethod
    async def get_available_quests(cls, clan_id: str):
        async with aiohttp.ClientSession() as session:
            async with session.get(
                    url=cls.api_url + f"clans/{clan_id}/quests/available", headers=cls.headers
            ) as response:
                if response.status == 200:
                    return await response.json()
                else:
                    logger.error(
                        f"Wov Available Quests API call failed with status code {response.status}. Clan ID: {clan_id}"
                    )
                    return None


class WovApiCall:
    headers = {"Authorization": f"Bot {os.getenv('WOV_API_TOKEN')}"}
    api_url = "https://api.wolvesville.com/"

    @classmethod
    async def get_user_by_id(cls, user_id: str):
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
                    url=cls.api_url + f"players/search?username={username}",
                    headers=cls.headers,
            ) as response:
                if response.status == 200:
                    return await response.json()
                else:
                    logger.error(
                        f"Wov User API call failed with status code {response.status}. Username: {username}"
                    )
                    return None

    @classmethod
    async def get_clan_by_id(cls, clan_id: str):
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
    async def get_clan_members(cls, clan_id: str):
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
                    url=cls.api_url + "shop/activeOffers", headers=cls.headers
            ) as response:
                if response.status == 200:
                    return await response.json()
                else:
                    logger.error(
                        "Wov Shop API call failed with status code %s.", response.status
                    )
                    return None

    @classmethod
    async def get_all_quests(cls):
        async with aiohttp.ClientSession() as session:
            async with session.get(
                    url=cls.api_url + "clans/quests/all", headers=cls.headers
            ) as response:
                if response.status == 200:
                    return await response.json()
                else:
                    logger.error(
                        "Wov Quests API call failed with status code %s.", response.status
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
            since: int | dt = None,
            until: int | dt = None,
            limit: int = None,
            vs: str = None,
            rated: bool = None,
            perf_type: list = None,
            # "ultraBullet","bullet","blitz","rapid","classical","correspondence","chess960","crazyhouse","antichess","atomic","horde","kingOfTheHill","racingKings","threeCheck"
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
            since (int | dt, optional): Download games played since this timestamp. Defaults to account creation date.
            until (int | dt, optional): Download games played until this timestamp. Defaults to now.
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
            finished (bool, optional): Include finished games. Set false to only get ongoing games. Defaults to True.
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


class ChessDotComApiCaller:
    # Singleton caller for chess.com API
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(ChessDotComApiCaller, cls).__new__(cls)
        return cls._instance

    def __init__(self):
        if not hasattr(self, 'initialized'):
            self.queue = asyncio.Queue()
            self.worker = asyncio.create_task(self.process_queue())
            self.initialized = True

    async def add_to_queue(self, func: Callable, *args: Any):
        future = asyncio.Future()
        await self.queue.put((func, args, future))
        return await future

    async def process_queue(self):
        while True:
            func, args, future = await self.queue.get()
            try:
                result = await func(*args)
                future.set_result(result)
            except Exception as e:
                future.set_exception(e)
            self.queue.task_done()
            await asyncio.sleep(1)  # Respect the rate limit.


class ChessDotComApiCall:
    chess_dot_com_url = "https://api.chess.com/pub/"
    headers = {"User-Agent": "application: Mif, username: {}, email: {}".format(os.getenv("CHESSDOTCOM_USERNAME"),
                                                                                os.getenv("CONTACT_EMAIL"))}

    @classmethod
    async def get_player_profile(cls, username: str):
        async with aiohttp.ClientSession() as session:
            async with session.get(
                    url=cls.chess_dot_com_url + f"player/{username}",
                    headers=cls.headers
            ) as response:
                if response.status == 200:
                    return await response.json()
                elif response.status == 404:
                    logger.info("Chess.com Player Profile not found. Username: %s", username)
                    return None
                else:
                    logger.error(
                        f"Chess.com Player Profile API call failed with status code {response.status}. Username: {username}"
                    )
                    return response.status

    @classmethod
    async def get_player_stats(cls, username: str):
        async with aiohttp.ClientSession() as session:
            async with session.get(
                    url=cls.chess_dot_com_url + f"player/{username}/stats",
                    headers=cls.headers
            ) as response:
                if response.status == 200:
                    return await response.json()
                else:
                    logger.error(
                        f"Chess.com Player Stats API call failed with status code {response.status}. Username: {username}"
                    )
                    return None

    @classmethod
    async def get_player_online_status(cls, username: str):
        # ? It doesn't seem to work
        async with aiohttp.ClientSession() as session:
            async with session.get(
                    url=cls.chess_dot_com_url + f"player/{username}/is-online",
                    headers=cls.headers
            ) as response:
                if response.status == 200:
                    return await response.json()
                else:
                    logger.error(
                        f"Chess.com Player Online Status API call failed with status code {response.status}. Username: {username}"
                    )
                    return None

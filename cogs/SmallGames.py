import asyncio
import calendar
from datetime import datetime as dt
import random
import re
from typing import Optional, Union
import math

import discord
from discord import app_commands
from discord.ext import commands

from bot_util.misc import AsyncTranslator, Logger
from bot_util.functions import games, security
from bot_util.functions.universal import (
    repeating_symbols,
    pretty_date,
    pretty_time_delta,
)
from hangman_words import words_long, words_short, pics
from bot_util import bot_config
from db_data.psql_main import DatabaseFunctions as DF

# Constants ------------------------------

NG_GUILD_CHECK = set()
BAC_GAMES_DICT = dict()
BJ_GAMES_DICT = dict()

# ---------------------------------------

logger = Logger(__name__, log_file_path=bot_config.LogFiles.s_games_log)


def check_numbers(channel_id):
    for user in BAC_GAMES_DICT[f"{channel_id}"]:
        if BAC_GAMES_DICT[f"{channel_id}"][f"{user}"] == {}:
            return False
        else:
            continue
    return True


class JoinButton(discord.ui.Button):
    def __init__(self, channel_id, passed_embed=None):
        super().__init__(label="Join (1/4)", style=discord.ButtonStyle.green)
        self.channel_id = channel_id
        self.passed_embed = passed_embed

    async def callback(self, interaction):
        async with AsyncTranslator(DF.get_lang_code(interaction.user.id)) as at:
            at.install()
            self._ = at.gettext
        if str(interaction.user.id) in BAC_GAMES_DICT[f"{self.channel_id}"]:
            await interaction.response.send_message(
                self._("You already joined"), ephemeral=True
            )
        else:
            BAC_GAMES_DICT[f"{self.channel_id}"][f"{interaction.user.id}"] = {}

            self.label = f"Join ({len(BAC_GAMES_DICT[f'{self.channel_id}']) - 1}/4)"
            if len(BAC_GAMES_DICT[f"{self.channel_id}"]) == 5:
                self.style = discord.ButtonStyle.gray
                self.disabled = True
            elif len(BAC_GAMES_DICT[f"{self.channel_id}"]) >= 3:
                self.view.s_butt.disabled = False
                pass

            embed_dict = self.passed_embed.to_dict()
            if embed_dict["fields"][0]["value"] == "No players in lobby":
                embed_dict["fields"][0]["value"] = ""
            embed_dict["fields"][0]["value"] += f"{interaction.user.mention}\n"
            new_embed = discord.Embed.from_dict(embed_dict)

            await interaction.response.edit_message(embed=new_embed, view=self.view)
            await interaction.followup.send(content=self._("Joined!"), ephemeral=True)
            # if interaction.user.nick == None:
            #     nickname = interaction.user.name
            # else:
            #     nickname = interaction.user.nick
            await interaction.followup.send(
                content="{} joined the game!".format(interaction.user.mention)
            )


class LeaveButton(discord.ui.Button):
    def __init__(self, channel_id, join_button, passed_embed=None):
        super().__init__(
            label="Leave", style=discord.ButtonStyle.red, custom_id="leave"
        )
        self.join_button = join_button
        self.channel_id = channel_id
        self.passed_embed = passed_embed

    async def callback(self, interaction):
        async with AsyncTranslator(DF.get_lang_code(interaction.user.id)) as at:
            at.install()
            self._ = at.gettext
        if BAC_GAMES_DICT[f"{self.channel_id}"][f"{interaction.user.id}"] is None:
            await interaction.response.send_message(
                self._("You didn't join the game to leave it"), ephemeral=True
            )
        else:
            del BAC_GAMES_DICT[f"{self.channel_id}"][f"{interaction.user.id}"]
            self.join_button.label = (
                f"Join ({len(BAC_GAMES_DICT[f'{self.channel_id}'])-1}/4)"
            )
            if self.join_button.style == discord.ButtonStyle.gray:
                self.join_button.style = discord.ButtonStyle.green
            if len(BAC_GAMES_DICT[f"{self.channel_id}"]) < 3:
                self.view.s_butt.disabled = True

            embed_dict = self.passed_embed.to_dict()
            if len(BAC_GAMES_DICT[f"{self.channel_id}"]) != 1:
                embed_dict["fields"][0]["value"] = re.sub(
                    f"{interaction.user.mention}\n",
                    "",
                    embed_dict["fields"][0]["value"],
                )
            else:
                embed_dict["fields"][0]["value"] = "No players in lobby"
            new_embed = discord.Embed.from_dict(embed_dict)
            await interaction.response.edit_message(embed=new_embed, view=self.view)
            await interaction.followup.send(
                content=self._("You left the lobby!"), ephemeral=True
            )
            await interaction.followup.send(
                content=f"{interaction.user.mention} left the game!"
            )


class StartButton(discord.ui.Button):
    def __init__(self, channel_id, host_id):
        super().__init__(
            label="Start", style=discord.ButtonStyle.blurple, custom_id="start"
        )
        self.channel_id = channel_id
        self.host_id = host_id

    async def callback(self, interaction: discord.Interaction):
        async with AsyncTranslator(DF.get_lang_code(interaction.user.id)) as at:
            at.install()
            self._ = at.gettext
        if interaction.user.id != self.host_id:
            await interaction.response.send_message(
                content=self._("You are not the host!"), ephemeral=True
            )
            return
        Join_Button, Leave_Button = self.view.j_butt, self.view.l_butt
        Join_Button.disabled = True
        Leave_Button.disabled = True
        BAC_GAMES_DICT[f"{self.channel_id}"]["gameStarted"] = True
        await interaction.response.edit_message(view=self.view)
        self.view.stop()


class HelpButton(discord.ui.Button):
    def __init__(self):
        super().__init__(
            label="Help", style=discord.ButtonStyle.blurple, custom_id="help"
        )

    async def callback(self, interaction: discord.Interaction):
        async_trans = AsyncTranslator(
            language_code=DF.get_lang_code(interaction.user.id)
        )
        async with async_trans as lang:
            lang.install()

            _ = lang.gettext
            embed_help = discord.Embed(
                title=_("Bulls and Cows Rules"),
                description=_("Rulebook for the game **Bulls and Cows**"),
                color=discord.Color.from_rgb(0, 255, 255),
            )
            embed_help.add_field(
                name=_("General rules"),
                value=_(
                    "The game is played in turns by two (or more) opponents who aim to decipher the other's secret code by trial and error"
                ),
                inline=False,
            )
            embed_help.add_field(
                name=_("Hints"),
                value=_(
                    """After each guess, the bot will give you the amount of "bulls" and "cows" your guess has, comparing it to the secret number of each opponent:\n
 ·  **Cow** - One of the digits is in the secret number, but in the wrong place\n
 ·  **Bull** - The guess has a correct digit in the correct place\n\n
For example, your secret number is 7914 and the opponent's guess is 1234, the clues would be: '1 cow, 1 bull'. The 'cow' is 1 and 'bull' is 4\n\n
The goal of the game is to be the first to get 4 bulls on every of opponent's secret numbers"""
                ),
                inline=False,
            )
            embed_help.add_field(
                name=_("Statistics"),
                value=_(
                    "If you are registered on the bot network, bot will record your victories and losses. To access your stats, use command `botstats`"
                ),
            )
            self.view.h_butt = True
            await interaction.response.send_message(embed=embed_help, ephemeral=True)


class HelpButtonBagels(discord.ui.Button):
    def __init__(self):
        super().__init__(
            label="Help", style=discord.ButtonStyle.blurple, custom_id="help"
        )

    async def callback(self, interaction: discord.Interaction):
        async with AsyncTranslator(DF.get_lang_code(interaction.user.id)) as at:
            at.install()
            _ = at.gettext
            embedHint = discord.Embed(
                title=_("Bagels Rules"),
                description=_("Rulebook for the game **Pico, Fermi, Bagels**"),
                color=discord.Color.from_rgb(0, 255, 255),
            )
            embedHint.add_field(
                name=_("General rules"),
                value=_(
                    "The main goal is to guess the secret number of the amount of digits (with no repeating digits) depending on the mode, in certain amount of tries"
                ),
                inline=False,
            )
            embedHint.add_field(
                name=_("Hints"),
                value=_(
                    "After each try, bot will give three types of clues:\n"
                    " ·  **Pico** - One of the digits is in the secret number, but in the wrong place\n"
                    " ·  **Fermi** - The guess has a correct digit in the correct place\n"
                    " ·  **Bagels** - None of the digits is in the secret numbers\n\n"
                    "For example secret number is 273 and the player's guess is 123, the clues would be: 'Pico Fermi'. The 'Pico' is from the 2 and 'Fermi' is from the 3"
                ),
                inline=False,
            )
            embedHint.add_field(
                name=_("Modes"),
                value=_(
                    "There are currently 4 gamemodes for **Bagels**:\n"
                    " ·   **Fast mode** - Blitz mode. No major gameplay changes. *You have 7 tries to guess a 2-digit number*\n"
                    " ·   **Classic mode** - No gameplay changes. *You have 10 tries to guess a 3-digit number*\n"
                    " ·   **Hard mode** - In this mode bot will give only one clue for the guess, for example secret number is 273 and the player's guess is 123, the clue would be only: 'Pico'. *You have 13 tries to guess a 3-digit number*\n"
                    " ·   **Prolonged mode** - Nerd mode. No major gameplay changes. *You have 20 tries to guess a 6-digit number*"
                ),
                inline=False,
            )
            embedHint.add_field(
                name=_("Statistics"),
                value=_(
                    "If you are registered on the bot network, bot will record your victories, losses and abandoned games in each game mode. To access your stats, use command `botstats`"
                ),
            )

            await interaction.response.send_message(embed=embedHint, ephemeral=True)


class BagelsView(discord.ui.View):
    def __init__(self, *, timeout=1200):
        super().__init__(timeout=timeout)
        self.h_butt = HelpButtonBagels()
        self.add_item(self.h_butt)

    async def on_timeout(self):
        self.h_butt.disabled = True
        await self.message.edit(view=self)
        self.stop()


class ButtonsBACJoin(discord.ui.View):
    def __init__(
        self, channel_id, pass_embed=None, ctx: commands.Context = None, *, timeout=1200
    ):
        super().__init__(timeout=timeout)
        self.channel_id = channel_id
        self.ctx = ctx
        self.j_butt = JoinButton(self.channel_id, pass_embed)
        self.l_butt = LeaveButton(
            channel_id=self.channel_id, join_button=self.j_butt, passed_embed=pass_embed
        )
        self.s_butt = StartButton(self.channel_id, ctx.author.id)
        self.s_butt.disabled = True
        self.h_butt = HelpButton()
        self.add_item(self.j_butt)
        self.add_item(self.l_butt)
        self.add_item(self.s_butt)
        self.add_item(self.h_butt)

    async def on_timeout(self) -> None:
        await self.ctx.send(
            "The game hasn't started for over 20 minutes.\nRestart the game if this message has ruined all your hopes and dreams."
        )
        await self.message.edit(view=None)
        BAC_GAMES_DICT.pop(f"{self.ctx.channel.id}")


class InputButtonView(discord.ui.View):
    def __init__(self, channel_id, bot, player_ids):
        super().__init__(timeout=180)
        self.channel_id = channel_id
        self.bot = bot
        self.p_ids = player_ids

    @discord.ui.button(label="Input", style=discord.ButtonStyle.green)
    async def callback(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        modal = NumberForBAC(channel_id=self.channel_id, bot=self.bot)
        await interaction.response.send_modal(modal)

    async def interaction_check(self, interaction) -> bool:
        if str(interaction.user.id) in self.p_ids:
            return True
        else:
            async_trans = AsyncTranslator(
                language_code=DF.get_lang_code(interaction.user.id)
            )
            async with async_trans as lang:
                lang.install()

                _ = lang.gettext
                await interaction.response.send_message(
                    _("Somehow you are not in game..."), ephemeral=True
                )
                return False


class NumberForBAC(discord.ui.Modal):
    def __init__(self, channel_id, bot):
        super().__init__(
            title="Number for BAC", custom_id=f"{channel_id}{random.random()}"
        )
        self.channel_id = channel_id
        self.bot = bot

    answer = discord.ui.TextInput(
        label="Number",
        style=discord.TextStyle.short,
        required=True,
        min_length=4,
        max_length=4,
    )

    async def on_submit(self, interaction: discord.Interaction):
        if self.children[0].value.isdecimal() and len(
            set(self.children[0].value)
        ) == len(self.children[0].value):
            embed = discord.Embed(
                title="Your number",
                description=f"{self.children[0].value}",
                color=discord.Color.from_rgb(0, 255, 255),
            )
            BAC_GAMES_DICT[f"{self.channel_id}"][f"{interaction.user.id}"][
                "number"
            ] = self.children[0].value
            await interaction.response.send_message(embeds=[embed])
            await interaction.followup.edit_message(
                message_id=interaction.message.id, view=None
            )
            channel = self.bot.get_channel(int(self.channel_id))
            await channel.send(content=f"{interaction.user.mention} is ready!")
            if check_numbers(self.channel_id) is True:
                await asyncio.sleep(3.0)
                await channel.send(content="Game starting...", delete_after=3.0)
        else:
            async with AsyncTranslator(
                language_code=DF.get_lang_code(interaction.user.id)
            ) as lang:
                lang.install()
                _ = lang.gettext
                embed = discord.Embed(
                    title=_("Error"),
                    description=_(
                        "{number} is either not a number, or contains repeated digits"
                    ).format(number=self.children[0].value),
                    color=discord.Color.dark_red(),
                )
                await interaction.response.send_message(embed=embed)


class OngoingGameGuessingBAC(discord.ui.View):
    def __init__(self, order, channel_id, p_ids, bot):
        super().__init__(timeout=1800)
        self.order = order
        self.channel_id = channel_id
        self.p_ids = p_ids
        self.bot = bot

    @discord.ui.button(label="Guess", style=discord.ButtonStyle.blurple)
    async def callback(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        async with AsyncTranslator(
            language_code=DF.get_lang_code(interaction.user.id)
        ) as lang:
            lang.install()
            _ = lang.gettext
            await interaction.response.send_modal(
                GuessModalBAC(
                    player_ids=self.p_ids,
                    channel_id=self.channel_id,
                    bot=self.bot,
                    message_view=self,
                    button=button,
                    gettext_lang=_,
                )
            )

    async def interaction_check(self, interaction) -> bool:
        if interaction.user.id == int(self.order[0]):
            return True
        else:
            async with AsyncTranslator(
                language_code=DF.get_lang_code(interaction.user.id)
            ) as lang:
                lang.install()
                _ = lang.gettext
                await interaction.response.send_message(
                    _("It's not your turn!"), ephemeral=True
                )
            return False


class GuessModalBAC(discord.ui.Modal):
    def __init__(self, player_ids, channel_id, bot, message_view, button, gettext_lang):
        self._ = gettext_lang
        super().__init__(title=self._("Your guess...?"))
        self.player_ids = player_ids
        self.channel_id = channel_id
        self.bot = bot
        self.message_view = message_view
        self.button = button

    answer = discord.ui.TextInput(
        label="Number",
        style=discord.TextStyle.short,
        required=True,
        min_length=4,
        max_length=4,
    )

    async def on_submit(self, interaction: discord.Interaction):
        if self.children[0].value.isdecimal() and len(
            set(self.children[0].value)
        ) == len(self.children[0].value):

            def check_the_guess(guess, number):
                result = {"bulls": 0, "cows": 0}
                guess, number = list(guess), list(number)
                for num1 in guess:
                    for num2 in number:
                        if num1 == num2:
                            if guess.index(num1) == number.index(num2):
                                result["bulls"] += 1
                            else:
                                result["cows"] += 1
                return result

            results = {}
            for player_id in self.player_ids:
                if player_id == self.player_ids[0]:
                    continue
                else:
                    results[f"{player_id}"] = check_the_guess(
                        self.children[0].value,
                        BAC_GAMES_DICT[f"{self.channel_id}"][f"{player_id}"]["number"],
                    )
            results_value = self._("**Your guess:** {number}\n").format(
                number=self.children[0].value
            )
            for player in results:
                results_value += f"**{BAC_GAMES_DICT[f'{self.channel_id}'][f'{player}']['username']}**: {results[f'{player}']['bulls']} bulls, {results[f'{player}']['cows']} cows\n"
            results["initial_guess"] = self.children[0].value
            BAC_GAMES_DICT[f"{self.channel_id}"]["temp_results"] = results
            await interaction.response.send_message(
                content=results_value, ephemeral=True
            )
            channel = self.bot.get_channel(int(self.channel_id))
            await channel.send(content="They made a guess..", delete_after=0.5)
            self.button.disabled = True
            await interaction.followup.edit_message(
                message_id=BAC_GAMES_DICT[f"{self.channel_id}"]["extra_info"][
                    "message_id"
                ],
                view=self.message_view,
            )
        else:
            embed = discord.Embed(
                title=self._("Error"),
                description=self._(
                    "{number} is either not a number, or contains repeated digits. Try again!"
                ).format(number=self.children[0].value),
                color=discord.Color.dark_red(),
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)


class BlackjackHitStop(discord.ui.View):
    def __init__(self, user_b, gettext_lang):
        super().__init__(timeout=None)
        self.user_b = user_b
        self._ = gettext_lang

    @discord.ui.button(label="Hit", style=discord.ButtonStyle.green)
    async def callback(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        user_id = self.user_b.id
        game: dict = BJ_GAMES_DICT[user_id]["game"]

        # Drawing a card for the player
        games.BlackJack.draw_card("player", 3, game)

        # Update game state
        player_busted, dealer_busted = games.BlackJack.update_game_state(game)

        # Game status if dealer or player busted
        game_ended = player_busted or dealer_busted

        if game_ended:
            view = None
            BJ_GAMES_DICT[user_id]["metadata"]["game_ended"] = True
            end_message, code = games.BlackJack.get_game_end_message_and_code(
                game, self._
            )
            new_embed = games.BlackJack.create_blackjack_embed(
                game, end_message, self._, code
            )
            games.BlackJack.process_results(code, user_id, game["player"]["bet"])
        else:
            view = self
            new_embed = games.BlackJack.create_blackjack_embed(
                game, None, self._, games.BlackJackEndCodes.ONGOING
            )

        await interaction.response.edit_message(embed=new_embed, view=view)

        # Clean up if game ended
        if game_ended:
            del BJ_GAMES_DICT[user_id]

    @discord.ui.button(label="Stand", style=discord.ButtonStyle.red)
    async def callback2(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        user_id = self.user_b.id
        game: dict = BJ_GAMES_DICT[user_id]["game"]

        # Update game state
        games.BlackJack.update_game_state(game)
        BJ_GAMES_DICT[user_id]["metadata"]["game_ended"] = game_ended = True

        end_message, code = games.BlackJack.get_game_end_message_and_code(game, self._)
        new_embed = games.BlackJack.create_blackjack_embed(
            game, end_message, self._, code
        )
        games.BlackJack.process_results(code, user_id, game["player"]["bet"])

        await interaction.response.edit_message(embed=new_embed, view=None)

        if game_ended:
            del BJ_GAMES_DICT[user_id]

    async def interaction_check(self, interaction) -> bool:
        if interaction.user.id == self.user_b.id:
            return True
        else:
            async with AsyncTranslator(DF.get_lang_code(interaction.user.id)) as at:
                at.install()
                _ = at.gettext
                await interaction.response.send_message(
                    _("It's not your game!"), ephemeral=True
                )
            return False


class BacReplayRecordsPageDown(discord.ui.Button):
    def __init__(self):
        super().__init__(
            label="<",
            style=discord.ButtonStyle.blurple,
            custom_id="page_down",
            disabled=True,
        )

    async def callback(self, interaction: discord.Interaction):
        self.view._current_page -= 1
        if self.view._current_page == 1:
            self.disabled = True
        else:
            self.disabled = False
        self.view.children[1].disabled = False
        embed_page = discord.Embed.from_dict(
            self.view.pages[f"page_{(self.view._current_page - 1)}"]
        )
        await interaction.response.edit_message(embed=embed_page, view=self.view)


class BacReplayRecordsPageUp(discord.ui.Button):
    def __init__(self, disabled: bool = False):
        super().__init__(
            label=">",
            style=discord.ButtonStyle.blurple,
            custom_id="page_up",
            disabled=disabled,
        )

    async def callback(self, interaction: discord.Interaction):
        self.view._current_page += 1
        self.disabled = (
            False if self.view._max_pages != self.view._current_page else True
        )
        self.view.children[0].disabled = False
        if f"page_{self.view._current_page}" in self.view.pages:
            embed_page = discord.Embed.from_dict(
                self.view.pages[
                    f"page_{(self.view._current_page) - (0 if isinstance(self.view, BacReplayRecordsView) else 1)}"
                ]
            )
        else:
            if isinstance(self.view, BacReplayRecordsView):
                embed_page = discord.Embed(
                    title=self.view.pages["page_1"]["title"],
                    description=self.view.pages["page_1"]["description"],
                    color=bot_config.CustomColors.cyan,
                )
                embed_page.set_footer(
                    text=f"Page: {self.view._current_page}/{self.view._max_pages}"
                )
                embed_page, self.view.recorded_games = self.view.function(
                    embed_page,
                    self.view.recorded_games[
                        12 * (self.view._current_page - 1) : 12
                        * self.view._current_page
                    ],
                )
                self.view.pages[
                    f"page_{self.view._current_page}"
                ] = embed_page.to_dict()
            else:
                turn = (self.view._current_page) - 1
                embed_page = discord.Embed(
                    title=self.view.pages["page_0"]["title"],
                    description=f"Turn {turn}/{self.view._max_pages-1}",
                    color=bot_config.CustomColors.cyan,
                )
                embed_page.set_footer(
                    text=f"Page: {self.view._current_page}/{self.view._max_pages}"
                )
                for player in self.view.game_dict[f"turn{turn}"]:
                    value = f"**Initial guess — {self.view.game_dict[f'turn{turn}'][player]['initial_guess']}**"
                    for p in self.view.game_dict[f"turn{turn}"][player]:
                        if p != "initial_guess":
                            value += (
                                f"\n{self.view.player_list[int(p)]}: "
                                f"{self.view.game_dict[f'turn{turn}'][player][p]['cows']} cows, "
                                f"{self.view.game_dict[f'turn{turn}'][player][p]['bulls']} bulls"
                            )
                    embed_page.add_field(
                        name=f"{self.view.player_list[int(player)]}", value=value, inline=False
                    )
                self.view.pages[f"page_{turn}"] = embed_page.to_dict()
        await interaction.response.edit_message(embed=embed_page, view=self.view)


class BacReplayRecordsView(discord.ui.View):
    def __init__(self, pages: dict, recorded_games: dict, function):
        super().__init__(timeout=600)
        self.pages = pages
        self.recorded_games = recorded_games
        self.function = function
        self._current_page = 1
        self._max_pages = (
            math.ceil(len(recorded_games) / 12) if len(recorded_games) != 0 else 1
        )
        self.add_item(BacReplayRecordsPageDown())
        self.add_item(
            BacReplayRecordsPageUp(
                disabled=False if self._max_pages != self._current_page else True
            )
        )

    async def on_timeout(self) -> None:
        for button in self.children:
            button.disabled = True
        await self.message.edit(view=self)


class BacReplayGameView(discord.ui.View):
    def __init__(self, main_embed: discord.Embed, game_dict: dict, player_list: dict):
        super().__init__(timeout=600)
        self.pages = {"page_0": main_embed.to_dict()}
        self.game_dict = game_dict
        self.player_list = player_list
        self._current_page = 1
        self._max_pages = len(game_dict) + 1
        self.add_item(BacReplayRecordsPageDown())
        self.add_item(BacReplayRecordsPageUp())


class SmallGames(commands.Cog):
    def __init__(self, bot):
        self.bot: commands.Bot = bot

    async def cog_load(self):
        print("Small Games cog loaded successfully!")

    @commands.hybrid_command(
        name="number-guessing",
        description="Play a quick guessing game where you try to find the correct number based on two types of clues",
        aliases=["ng", "ngstart"],
        with_app_command=True,
    )
    @app_commands.choices(
        difficulty=[
            app_commands.Choice(name="Easy", value="easy"),
            app_commands.Choice(name="Medium", value="medium"),
            app_commands.Choice(name="Hard", value="hard"),
        ]
    )
    async def numberguessing(self, ctx: commands.Context, difficulty=None):
        channel = ctx.channel
        hard = False
        async with AsyncTranslator(DF.get_lang_code(ctx.author.id)) as at:
            at.install()
            _ = at.gettext
            if difficulty is None:
                difficulty = "easy"
            match difficulty.lower():
                case "easy":
                    maxnum = 1000
                case "medium":
                    maxnum = 10000
                case "hard":
                    maxnum = 100000
                    hard = True
                    count = 20
                case _:
                    difficulty = "easy"
                    maxnum = 1000
                    await ctx.send(_("Difficulty was changed to `easy`"))
            n = random.randint(1, maxnum)
            guess = 100
            if channel.id not in NG_GUILD_CHECK:
                embed = discord.Embed(
                    title=_("Game started"),
                    description=_("Start guessing :3"),
                    color=bot_config.CustomColors.cyan,
                )
                embed.add_field(name=_("Range"), value=_("Pick a number between **1** and **{maxnum}**").format(
                            maxnum=maxnum
                        ))
                await ctx.send(embed=embed)
                DF.add_to_command_stat(ctx.author.id)
                NG_GUILD_CHECK.add(channel.id)
                while guess != -1 and channel.id in NG_GUILD_CHECK:
                    if guess <= 10 and guess != 0:
                        await ctx.send(
                            _("You have only {guess} guesses left").format(guess=guess)
                        )
                    elif guess == 0:
                        await ctx.send(_("You ran out of guesses, gg"))
                        break
                    if hard is True:
                        if count > 0:
                            count -= 1
                        elif count == 0:
                            n = random.randint(1, maxnum)
                            count += 20
                        else:
                            pass
                    else:
                        pass
                    while True:
                        try:
                            msg = await self.bot.wait_for(
                                "message",
                                timeout=60,
                                check=lambda m: m.channel.id == ctx.channel.id
                                and m.content.isnumeric()
                                and m.author.id != self.bot.user.id,
                            )
                            attempt = int(msg.content)
                        except ValueError:
                            continue
                        except asyncio.TimeoutError:
                            await ctx.send(_("Game canceled due to timeout."))
                            NG_GUILD_CHECK.remove(channel.id)
                            return
                        else:
                            break
                    if attempt > n:
                        await ctx.send(
                            _(
                                "The secret number is **smaller** than **{attempt}**"
                            ).format(attempt=attempt)
                        )
                        guess -= 1
                    elif attempt < n:
                        await ctx.send(
                            _(
                                "The secret number is **bigger** than **{attempt}**"
                            ).format(attempt=attempt)
                        )
                        guess -= 1
                    elif attempt == n:
                        await ctx.send(
                            _("{} **won the game**").format(msg.author.mention)
                        )
                        if DF.check_if_member_is_logged(msg.author.id) is True:
                            DF.add_stats(msg.author.id, f"ngWins.{difficulty}")
                        break
                    elif attempt is None:
                        break
                NG_GUILD_CHECK.remove(channel.id)
            else:
                await ctx.send(_("There is already a game running in this channel"))

    @commands.hybrid_command(
        name="hangman",
        description="Play an old school favorite, a word game where the goal is simply to find the missing word",
        aliases=["hgm", "hangm"],
        with_app_command=True,
    )
    @app_commands.choices(
        diff=[
            app_commands.Choice(name="Short word", value="short"),
            app_commands.Choice(name="Long word", value="long"),
        ]
    )
    async def hangman(self, ctx: commands.Context, diff: str = None):
        try:
            if diff is None or diff.lower() not in ["short", "long"]:
                diff = random.choice(["short", "long"])
        except Exception:
            diff = random.choice(["short", "long"])
        match diff.lower():
            case "short":
                word_to_guess = random.choice(words_short)
            case "long":
                word_to_guess = random.choice(words_long)
        missed = 0
        # logger.debug(f"I chose word: {word_to_guess}. Seed: {}")
        word_completion = "-" * len(word_to_guess)
        guessed = False
        guessed_letters = []
        async with AsyncTranslator(DF.get_lang_code(ctx.author.id)) as at:
            at.install()
            _ = at.gettext
            start_embed = discord.Embed(
                title=_("Game started!"),
                description=_("Guess the word (You have only 6 tries)"),
                colour=discord.Color.from_rgb(0, 255, 255),
            )
            start_embed.add_field(name=pics[missed].strip(), value="", inline=False)
            start_embed.add_field(
                name=_("Word"), value=f"**{word_completion}**", inline=False
            )
            start_embed.add_field(
                name=_("Used letters"), value=_("*No letters*"), inline=False
            )
            main_message = await ctx.send(embed=start_embed)
            DF.add_to_command_stat(ctx.author.id)
            while guessed is False and missed < 6:
                try:
                    guess = await self.bot.wait_for(
                        "message",
                        timeout=300,
                        check=lambda m: m.channel.id == ctx.channel.id,
                    )
                except asyncio.TimeoutError:
                    await ctx.send(_("Game canceled due to timeout."))
                    if DF.check_if_member_is_logged(ctx.author.id) is True:
                        DF.add_stats(ctx.author.id, f"hangman.{diff}.losses")
                    return
                p_guess = (guess.content).lower()
                if len(p_guess) == 1 and p_guess.isalpha():
                    if p_guess in guessed_letters:
                        await guess.reply("You already guessed this letter")
                    elif p_guess not in word_to_guess:
                        await guess.reply(
                            "{guess} is not in the word".format(guess=p_guess)
                        )
                        missed += 1
                        guessed_letters.append(p_guess)
                    else:
                        await guess.reply(
                            "Good job, {guess} is in the word".format(guess=p_guess),
                            delete_after=5,
                        )
                        guessed_letters.append(p_guess)
                        word_as_list = list(word_completion)
                        indices = [
                            i
                            for i, letter in enumerate(word_to_guess)
                            if letter == p_guess
                        ]
                        for index in indices:
                            word_as_list[index] = p_guess
                        word_completion = "".join(word_as_list)
                        if "-" not in word_completion:
                            guessed = True
                second_embed = start_embed.to_dict()
                second_embed["fields"][0]["name"] = pics[missed].strip()
                second_embed["fields"][1]["value"] = f"**{word_completion}**"
                second_embed["fields"][2]["value"] = f"*{', '.join(guessed_letters)}*"
                await main_message.edit(embed=discord.Embed.from_dict(second_embed))
            if missed == 6:
                await ctx.send(
                    _(
                        "The man is hanged. You ran out of tries. The word was: {word}"
                    ).format(word=word_to_guess)
                )
                if DF.check_if_member_is_logged(guess.author.id):
                    DF.add_stats(guess.author.id, f"hangman.{diff}.losses")
            elif missed <= 5:
                await ctx.send(_("Congrats, you guessed the word!"))
                if DF.check_if_member_is_logged(guess.author.id):
                    DF.add_stats(guess.author.id, f"hangman.{diff}.wins")

    @commands.cooldown(1, 15, commands.BucketType.user)
    @commands.hybrid_command(
        name="blackjack",
        description="Play a round of blackjack using in-bot currency for bets and payouts",
        aliases=["bj"],
        with_app_command=True,
    )
    async def blackjack(self, ctx: commands.Context, cash: str | None = None):
        user = ctx.author
        user_cash = None

        async with AsyncTranslator(DF.get_lang_code(user.id)) as lang:
            lang.install()
            _ = lang.gettext

            if user.id in BJ_GAMES_DICT:
                BJ_GAMES_DICT[user.id]["metadata"]["gettext"] = _
                old_one = self.bot.get_channel(
                    BJ_GAMES_DICT[user.id]["metadata"]["channel_id"]
                )
                old_one = old_one.get_partial_message(
                    BJ_GAMES_DICT[user.id]["metadata"]["message_id"]
                )
                await old_one.delete()
                game = BJ_GAMES_DICT[user.id]["game"]
                embed_game = games.BlackJack.create_blackjack_embed(
                    game,
                    _("Resuming a game of Blackjack..."),
                    _,
                    games.BlackJackEndCodes.ONGOING,
                )

                view = BlackjackHitStop(user_b=user, gettext_lang=_)
                original_message = await ctx.send(embed=embed_game, view=view)
                DF.add_to_command_stat(user.id)
                BJ_GAMES_DICT[user.id]["metadata"]["message_id"] = original_message.id
                BJ_GAMES_DICT[user.id]["metadata"][
                    "channel_id"
                ] = original_message.channel.id
            else:
                if cash is None:
                    await ctx.send(
                        content=_("You didn't wager any coins!"), delete_after=10.0
                    )
                    return

                if DF.check_if_member_is_logged(user.id) is False:
                    await ctx.send(
                        content=_("You are not registered or not logged in"),
                        delete_after=10.0,
                    )
                    return

                if cash.isdigit() is True:
                    cash = int(cash)
                else:
                    if cash.lower() == "all":
                        user_cash = int(DF.get_coins(user.id))
                        cash = user_cash
                    else:
                        await ctx.send(
                            content=_("Using **10** as a wager..."), delete_after=10.0
                        )
                        cash = 10
                if cash < 10:  # Min possible bet
                    await ctx.send(
                        content=_("Using **10** as a wager..."), delete_after=10.0
                    )
                    cash = 10
                elif cash > 200000:  # Max possible bet
                    await ctx.send(
                        content=_("Using **200000** as a wager..."), delete_after=10.0
                    )
                    cash = 200000
                if user_cash is None:
                    user_cash = DF.get_coins(user.id)
                if user_cash < 10:
                    await ctx.send(
                        _("You don't have enough coins. *Minimal value is* **10**")
                    )
                    return
                elif user_cash < cash:
                    await ctx.send(
                        _(
                            "You don't have enough coins. *You have only **{user_cash}** coins*"
                        ).format(user_cash=user_cash)
                    )
                    return

                nickname = DF.get_user_by_id(user.id, ["nickname"])["nickname"]
                BJ_GAMES_DICT[user.id] = {
                    "game": {
                        "dealer": {
                            "cards": [],
                            "first_card_points": 0,
                            "points_total": 0,
                            "busted": False,
                        },
                        "player": {
                            "cards": [],
                            "nickname": nickname,
                            "bet": cash,
                            "points_total": 0,
                            "busted": False,
                        },
                    },
                    "metadata": {
                        "gettext": _,
                        "user_id": user.id,
                        "channel_id": ctx.channel.id,
                        "message_id": None,
                        "game_ended": False,
                    },
                }
                DF.remove_coins(user.id, int(cash))
                game = BJ_GAMES_DICT[user.id]["game"]

                for player in game:
                    games.BlackJack.draw_card(
                        player, len(game[player]["cards"]), game, 2
                    )

                while (
                    game["dealer"]["points_total"] < 18
                ):  # Really need to adjust this, because it's pretty dumb at anything above 18
                    games.BlackJack.draw_card(
                        "dealer", len(game["dealer"]["cards"]), game
                    )

                embed_game = games.BlackJack.create_blackjack_embed(
                    game,
                    _("Starting a new game of Blackjack..."),
                    _,
                    games.BlackJackEndCodes.ONGOING,
                )

                view = BlackjackHitStop(user_b=user, gettext_lang=_)
                original_message = await ctx.send(embed=embed_game, view=view)
                DF.add_to_command_stat(user.id)
                BJ_GAMES_DICT[user.id]["metadata"]["message_id"] = original_message.id

    @commands.command(aliases=["bulls"])
    async def bullsandcows(
        self,
        ctx: commands.Context,
        mode: str = None,
        arg: Union[Optional[discord.Member], str] = None,
    ):
        user = ctx.author
        modes = ["classic", "bagels", "replay"]
        args = ["normal", "fast", "hard", "long"]
        try:
            mode = mode.lower()
        except Exception:
            pass
        try:
            arg = arg.lower()
        except Exception:
            pass
        match mode:
            case None:
                mode = "classic"
            case "pfb":
                mode = "bagels"
            case "rep":
                mode = "replay"
            case "records":
                mode = "replay"
            case _:
                if mode in modes:
                    mode = mode
                else:
                    mode = "classic"
        match arg:
            case None:
                arg = "classic"
            case "blitz":
                arg = "fast"
            case "nerd":
                arg = "long"
            case _:
                if arg in args or mode == "replay":
                    pass
                else:
                    arg = "classic"

        async with AsyncTranslator(DF.get_lang_code(ctx.author.id)) as at:
            at.install()
            _ = at.gettext

            async def bagels_game_loop(digits, guesses, arg):
                guess_count = guesses
                num_list = list("0123456789")
                random.shuffle(num_list)
                secret_number = num_list[0:digits]
                embed = discord.Embed(
                    title=_("Bagels - {mode}").format(mode=arg.capitalize()),
                    description=_(
                        "I have thought of {digits}-digit number. Try to guess it, you have {guesses} tries"
                    ).format(digits=digits, guesses=guesses),
                    color=discord.Color.from_rgb(0, 255, 255),
                )
                embed.set_footer(
                    text=_(
                        "Need help with figuring it out? Use button 𝐡𝐞𝐥𝐩 to get more information on the mode"
                    )
                )
                view = BagelsView()
                view.message = await ctx.send(embed=embed, view=view)
                while guess_count != -1:
                    try:
                        guess = await self.bot.wait_for(
                            "message",
                            timeout=300,
                            check=lambda m: m.author.id == user.id
                            and m.channel.id == ctx.channel.id
                            and m.content.isdecimal()
                            and len(m.content) == digits,
                        )
                    except asyncio.TimeoutError:
                        await ctx.send(_("Game abandoned."))
                        if DF.check_if_member_is_logged(user.id):
                            DF.add_stats(user.id, f"bulls.pfb.{arg}.abandoned")
                            DF.add_to_command_stat(user.id)
                        break
                    guess_m = guess.content
                    if repeating_symbols(guess_m) is True:
                        await guess.reply(
                            _(
                                "This number has repeated digits. Please think of another number"
                            )
                        )
                        continue
                    else:
                        guess_count -= 1
                        answer = []
                        guess_listed = list(guess_m)
                        for num1 in guess_listed:
                            for num2 in secret_number:
                                if num1 == num2:
                                    if arg == "hard" and len(answer) != 0:
                                        break
                                    if guess_listed.index(num1) == secret_number.index(
                                        num2
                                    ):
                                        answer.append("Fermi")
                                    else:
                                        answer.append("Pico")

                        if len(answer) == 0:
                            answer.append("Bagels")
                        answer.sort()
                        answer_string = " ".join(answer)
                        await ctx.send(answer_string)
                        if secret_number == guess_listed:
                            embedWin = discord.Embed(
                                title=_("Congrats, you are victorious"),
                                description=_(
                                    "{mention} won in the {arg} mode. It took {amount} guesses"
                                ).format(
                                    mention=ctx.author.mention,
                                    arg=arg,
                                    amount=guesses - guess_count,
                                ),
                                color=discord.Color.from_rgb(0, 255, 255),
                            )
                            await ctx.send(embed=embedWin)
                            if DF.check_if_member_is_logged(user.id):
                                DF.add_stats(user.id, f"bulls.pfb.{arg}.wins")
                                DF.add_to_command_stat(user.id)
                            break
                        elif guess_count == 0:
                            embedLoss = discord.Embed(
                                title=_("Sorry to inform you, but you lost"),
                                description=_(
                                    "You are out of tries. The number was **{number}**"
                                ).format(number="".join(secret_number)),
                                color=discord.Color.from_rgb(0, 255, 255),
                            )
                            await ctx.send(embed=embedLoss)
                            if DF.check_if_member_is_logged(user.id):
                                DF.add_stats(user.id, f"bulls.pfb.{arg}.losses")
                                DF.add_to_command_stat(user.id)
                            break

            match mode:
                case "bagels":
                    match arg:
                        case "classic":
                            max_digits = 3
                            guesses = 10
                            await bagels_game_loop(max_digits, guesses, arg)
                        case "fast":
                            max_digits = 2
                            guesses = 7
                            await bagels_game_loop(max_digits, guesses, arg)
                        case "hard":
                            max_digits = 3
                            guesses = 13
                            await bagels_game_loop(max_digits, guesses, arg)
                        case "long":
                            max_digits = 6
                            guesses = 20
                            await bagels_game_loop(max_digits, guesses, arg)
                case "classic":
                    embedClassicStart = discord.Embed(
                        title="Bulls and Cows Classic Mode",
                        description="Press the green button to join the game",
                        color=discord.Color.from_rgb(0, 255, 255),
                    )
                    embedClassicStart.set_footer(
                        text="Need help with figuring it out? Use button 𝐡𝐞𝐥𝐩 to get more information on the mode. Host must use 𝘀𝘁𝗮𝗿𝘁 button in order to start the game"
                    )
                    BAC_GAMES_DICT[f"{ctx.channel.id}"] = {}
                    BAC_GAMES_DICT[f"{ctx.channel.id}"]["gameStarted"] = False
                    BAC_GAMES_DICT[f"{ctx.channel.id}"][f"{user.id}"] = {}
                    embedClassicStart.add_field(
                        name="Players in game", value=f"{user.mention}\n"
                    )
                    view = ButtonsBACJoin(
                        ctx.message.channel.id, pass_embed=embedClassicStart, ctx=ctx
                    )
                    view.message = await ctx.send(embed=embedClassicStart, view=view)
                    DF.add_to_command_stat(user.id)

                    if await view.wait() is True:
                        logger.info(f"BAC game timeout in {ctx.channel.id}")
                        return
                    if (
                        BAC_GAMES_DICT[f"{ctx.channel.id}"] is not None
                        and BAC_GAMES_DICT[f"{ctx.channel.id}"]["gameStarted"] is True
                    ):
                        p_ids = []
                        for p in BAC_GAMES_DICT[f"{ctx.channel.id}"]:
                            p_ids.append(p)
                        p_ids.remove("gameStarted")

                        input_view = InputButtonView(ctx.channel.id, self.bot, p_ids)
                        for player in p_ids:
                            u_player = self.bot.get_user(int(player))
                            async with AsyncTranslator(
                                DF.get_lang_code(u_player.id)
                            ) as at:
                                at.install()
                                _ = at.gettext
                                await u_player.send(
                                    _("Please input a 4-digit number"), view=input_view
                                )
                        await self.bot.wait_for(
                            "message",
                            check=lambda m: m.channel.id == ctx.channel.id
                            and m.author.id in bot_config.bot_ids
                            and check_numbers(ctx.channel.id) is True
                            and m.content == "Game starting...",
                        )
                        stat_gathering = ""
                        queue = []
                        for player in p_ids:
                            d_user = self.bot.get_user(int(player))
                            BAC_GAMES_DICT[f"{ctx.channel.id}"][f"{player}"][
                                "username"
                            ] = d_user.name
                            BAC_GAMES_DICT[f"{ctx.channel.id}"][f"{player}"][
                                "win_condt"
                            ] = 0
                            queue.append(
                                BAC_GAMES_DICT[f"{ctx.channel.id}"][f"{player}"][
                                    "username"
                                ]
                            )
                            if DF.check_if_member_exists(d_user.id):
                                stat = DF.get_user_stats(d_user.id)
                                stat_gathering += f"**{BAC_GAMES_DICT[f'{ctx.channel.id}'][f'{player}']['username']}**: {stat['bulls']['number']['wins']} Wins/{stat['bulls']['number']['losses']} Losses\n"
                            else:
                                stat_gathering += f"**{BAC_GAMES_DICT[f'{ctx.channel.id}'][f'{player}']['username']}**: No info available\n"
                        embed_gamestarted = discord.Embed(
                            title="Game started!",
                            description=f"**Queue:** \n*--->* {' - '.join(queue)}",
                            color=discord.Color.from_rgb(0, 255, 255),
                        )
                        embed_gamestarted.add_field(
                            name="Stats", value=f"{stat_gathering}"
                        )
                        main_message = await ctx.send(embed=embed_gamestarted)
                        main_embed_dict = embed_gamestarted.to_dict()

                        utcnow = dt.utcnow()

                        json_game = {
                            "meta": {
                                "id": security.generate_short_hash_8bit(utcnow.strftime("%Y%m%d%H%M%S")),  # Generate a unique ID for the game
                                "players": {},
                                "datetime_started": str(utcnow.isoformat()) + "Z",
                                "state": "",
                                "duration": utcnow,
                            },
                            "game": {},
                        }
                        for player in p_ids:
                            json_game["meta"]["players"][
                                f"player{p_ids.index(player)+1}"
                            ] = {
                                "user_id": int(player),
                                "number": str(
                                    BAC_GAMES_DICT[f"{ctx.channel.id}"][f"{player}"][
                                        "number"
                                    ]
                                ),
                            }

                        turn = 0
                        BAC_GAMES_DICT[f"{ctx.channel.id}"]["extra_info"] = {
                            "first_player": int(p_ids[0])
                        }

                        def update_queue(array):
                            temp_var = array[0]
                            del array[0]
                            array.append(temp_var)
                            return array

                        while True:
                            # await ctx.send(f"{json_game}")
                            player_guessing = self.bot.get_user(int(p_ids[0]))
                            view = OngoingGameGuessingBAC(
                                order=p_ids,
                                channel_id=ctx.channel.id,
                                p_ids=p_ids,
                                bot=self.bot,
                            )
                            turn_message = await ctx.send(
                                f"It's {player_guessing.mention}'s turn. Please enter your next guess",
                                view=view,
                            )
                            BAC_GAMES_DICT[f"{ctx.channel.id}"]["extra_info"][
                                "message_id"
                            ] = turn_message.id
                            try:
                                await self.bot.wait_for(
                                    "message",
                                    check=lambda m: m.channel.id == ctx.channel.id
                                    and m.author.id in bot_config.bot_ids
                                    and m.content == "They made a guess..",
                                )
                                # guess = await self.bot.wait_for("message", check=lambda m: m.channel.id == ctx.channel.id and m.author.id == int(p_ids[0]) and m.content.isdecimal() and len(set(m.content)) == len(m.content), timeout=1800)
                            except asyncio.TimeoutError:
                                embed_error = discord.Embed(
                                    title="Timeout Error",
                                    description=f"{player_guessing} took more than 30 minutes to guess. Game abandoned.",
                                    color=discord.Color.from_rgb(255, 0, 0),
                                )
                                if (
                                    DF.check_if_member_is_logged(player_guessing.id)
                                    is True
                                ):
                                    DF.add_stats(
                                        player_guessing.id, "bulls.number.losses"
                                    )
                                del p_ids[0]
                                for player in p_ids:
                                    player_d = self.bot.get_user(int(player))
                                    if DF.check_if_member_is_logged(player_d) is True:
                                        DF.add_stats(player_d.id, "bulls.number.wins")
                                await ctx.send(embed=embed_error)
                                time_finished = dt.utcnow()
                                json_game["meta"]["duration"] = (
                                    time_finished - json_game["duration"]
                                )
                                json_game["meta"][
                                    "state"
                                ] = f"Abandoned. {player_guessing.id}"
                                break
                            results = BAC_GAMES_DICT[f"{ctx.channel.id}"][
                                "temp_results"
                            ]
                            if BAC_GAMES_DICT[f"{ctx.channel.id}"]["extra_info"][
                                "first_player"
                            ] == int(p_ids[0]):
                                turn += 1
                                json_game["game"][f"turn{turn}"] = {}
                            json_game["game"][f"turn{turn}"][f"{p_ids[0]}"] = results
                            for player in results:
                                if player == "initial_guess":
                                    continue
                                if results[f"{player}"]["bulls"] == 4:
                                    BAC_GAMES_DICT[f"{ctx.channel.id}"][f"{p_ids[0]}"][
                                        "win_condt"
                                    ] += 1
                            if (
                                BAC_GAMES_DICT[f"{ctx.channel.id}"][f"{p_ids[0]}"][
                                    "win_condt"
                                ]
                                == len(results) - 1
                            ):
                                tries = len(json_game["game"])
                                embed_win = discord.Embed(
                                    title="Game ended",
                                    description=f"{player_guessing.mention} is the winner. It took them {tries} guesses",
                                    color=bot_config.CustomColors.cyan,
                                )
                                await ctx.send(embed=embed_win)
                                if DF.check_if_member_is_logged(player_guessing.id):
                                    DF.add_stats(
                                        player_guessing.id, "bulls.number.wins"
                                    )
                                del p_ids[0]
                                for player in p_ids:
                                    if DF.check_if_member_is_logged(int(player)):
                                        DF.add_stats(int(player), "bulls.number.losses")
                                time_finished = dt.utcnow()
                                json_game["meta"]["duration"] = (
                                    time_finished - json_game["meta"]["duration"]
                                )
                                json_game["meta"][
                                    "state"
                                ] = f"Finished. {player_guessing.id}"
                                break
                            queue = update_queue(queue)
                            p_ids = update_queue(p_ids)
                            new_embed_game_started = discord.Embed(
                                title=f"{main_embed_dict['title']}",
                                description=f"**Queue:** \n*--->* {' - '.join(queue)}",
                                color=bot_config.CustomColors.cyan,
                            )
                            new_embed_game_started.add_field(
                                name=main_embed_dict["fields"][0]["name"],
                                value=main_embed_dict["fields"][0]["value"],
                            )
                            await main_message.edit(embed=new_embed_game_started)
                        DF.insert_bulls_record(json_game)
                    BAC_GAMES_DICT.pop(f"{ctx.channel.id}")
                case "replay":
                    user = ctx.author
                    if DF.check_if_member_is_logged(user.id):
                        nickname = DF.get_user_by_id(user.id, ["nickname"])['nickname']
                        DF.add_to_command_stat(user.id)
                    else:
                        await ctx.send(
                            _("You are not registered or not logged in!"), ephemeral=True
                        )
                        return

                    def create_player_list(player_list, temp_cache) -> tuple:
                        return_dict = {}
                        for player in player_list:
                            if player == user.id:
                                return_dict[player] = nickname
                            else:
                                if str(player) not in temp_cache:
                                    if DF.check_if_member_is_logged(player):
                                        p_nickname = DF.get_user_by_id(
                                            player, ["nickname"]
                                        )
                                        p_nickname = p_nickname["nickname"]
                                    else:
                                        try:
                                            p_user = self.bot.get_user(player)
                                            p_nickname = p_user.name
                                        except Exception:
                                            p_nickname = _("Anonymous")
                                    temp_cache[str(player)] = p_nickname
                                else:
                                    p_nickname = temp_cache[str(player)]
                                return_dict[player] = p_nickname
                        return return_dict, temp_cache

                    def build_game_replay(game: dict):
                        if not game:
                            embed = discord.Embed(
                                title=_("Game not found"),
                                description=_("The requested game was not found."),
                                color=bot_config.CustomColors.dark_red,
                            )
                            return embed, None

                        # Check if the received dictionary contains "Private" flag
                        if "private" in game:
                            embed = discord.Embed(
                                title=_("Game not played by user who requested it"),
                                description=_(
                                    "This game is private."
                                ),
                                color=bot_config.CustomColors.dark_red,
                            )
                            return embed, None

                        player_list = [
                            game["meta"]["players"][x]["user_id"]
                            for x in game["meta"]["players"]
                        ]
                        player_list_id = player_list.copy()
                        player_list_dict, temp = create_player_list(player_list, {})
                        del temp
                        player_list = [player_list_dict[x] for x in player_list_dict]
                        queue = " -> ".join(player_list)
                        finish_state = game["meta"]["state"].split()
                        embed = discord.Embed(
                            title=_(
                                ("Win" if int(finish_state[1]) == user.id else "Loss")
                                + " by guessing"
                                if finish_state[0] == "Finished."
                                else " by timeout"
                            ),
                            description=queue,
                            color=bot_config.CustomColors.cyan,
                        )
                        value = ""
                        for i in range(0, len(player_list)):
                            value += (
                                f"\n{bot_config.CustomEmojis.empty * 2}{player_list[i]}: {game['meta']['players'][f'player{i+1}']['number']}"
                                + (
                                    _(" - ***Winner***")
                                    if player_list_id[i] == int(finish_state[1])
                                    else ""
                                )
                            )
                        embed.add_field(name=_("Players"), value=value)
                        embed.add_field(
                            name=_("Date played"),
                            value=f"<t:{calendar.timegm(game['meta']['datetime_started'].timetuple())}> (<t:{calendar.timegm(game['meta']['datetime_started'].timetuple())}:R>)",
                            inline=False,
                        )
                        embed.add_field(
                            name=_("Duration"),
                            value=f"`{pretty_time_delta(game['meta']['duration'])}`",
                            inline=False,
                        )
                        embed.add_field(
                            name=_("Amount of turns"),
                            value=f"{len(game['game'])} {_('turns') if len(game['game']) != 1 else _('turn')}",
                        )
                        embed.set_footer(
                            text=_("Page: 1/{total_pages}").format(
                                total_pages=len(game["game"]) + 1
                            )
                        )
                        view = BacReplayGameView(
                            embed, game["game"], player_list=player_list_dict
                        )
                        return embed, view

                    if isinstance(arg, discord.Member):
                        recorded_games = DF.get_bac_records(user.id, member_2=arg.id)
                    elif arg.isdigit():
                        recorded_game = DF.get_single_bac_record(
                            user.id, game_id=int(arg)
                        )
                        embed, view = build_game_replay(recorded_game)
                        await ctx.send(embed=embed, view=view)
                        return
                    else:
                        recorded_games = DF.get_bac_records(user.id)
                    print(recorded_games)
                    recorded_games.reverse()
                    pages_dict = {}

                    embed_pg1 = discord.Embed(
                        title=_("Games archive"),
                        description=_(
                            "{}' archive of played **Bulls and Cows** games {}"
                        ).format(
                            nickname,
                            _("against {mention}").format(mention=arg.mention)
                            if isinstance(arg, discord.Member)
                            else "",
                        ),
                        color=bot_config.CustomColors.cyan,
                    )
                    embed_pg1.set_footer(
                        text=_("Page: 1/{total_pages}").format(
                            total_pages=math.ceil(len(recorded_games) / 12)
                            if len(recorded_games) != 0
                            else 1
                        )
                    )

                    def finish_page(embed: discord.Embed, games: list):
                        if len(games) == 0:
                            embed.add_field(
                                name=_("No games"),
                                value=_("I couldn't find any games "),
                            )
                        temp_cache = {}
                        for game in games:
                            if games.index(game) % 12 == 0 and games.index(game) != 0:
                                break

                            player_list = [
                                game[x]
                                for x in game
                                if x in ["user_1", "user_2", "user_3", "user_4"]
                                and game[x] is not None
                            ]
                            player_list, temp_cache = create_player_list(
                                player_list, temp_cache
                            )
                            player_queue = " -> ".join(player_list.values())
                            if len(player_queue) > 20:
                                player_queue = player_queue[0:20] + "..."
                            timestamp = game["t1"]
                            embed.add_field(
                                name=_("Win")
                                if game["player_won"] == user.id
                                else _("Loss"),
                                value=f"{player_queue} \n`{pretty_date(timestamp)}`\n*id: **{game['id']}***",
                            )
                        return embed, games

                    embed_pg1, recorded_games = finish_page(embed_pg1, recorded_games)
                    pages_dict["page_1"] = embed_pg1.to_dict()
                    bac_replay_view = BacReplayRecordsView(
                        pages_dict, recorded_games, function=finish_page
                    )
                    bac_replay_view.message = await ctx.send(
                        embed=embed_pg1, view=bac_replay_view
                    )


async def setup(bot):
    await bot.add_cog(SmallGames(bot))

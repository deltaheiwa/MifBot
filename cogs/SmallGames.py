from socket import timeout
import sys
import discord
from discord import app_commands
import random
import asyncio
import json
import pytz
from discord.ext import commands
from util.bot_functions import *
from hangman_words import *
import util.bot_config as b_cfg
from datetime import datetime as datetimefix
import GameFunctions as GF
from db_data.mysql_main import DatabaseFunctions as DF
from db_data.mysql_main import JsonOperating as JO
from typing import Optional

global NG_GUILD_CHECK
NG_GUILD_CHECK = set()

global BAC_GAMES_DICT
BAC_GAMES_DICT = dict()

global BJ_GAMES_DICT
BJ_GAMES_DICT = dict()

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
formatter = logging.Formatter('%(asctime)s:%(levelname)s --- %(message)s')
console_formatter = CustomFormatter()
stream_handler = logging.StreamHandler()
coloredlogs.install(level='DEBUG', logger=logger)
file_handler_debug = logging.FileHandler(bot_config.LogFiles.s_games_log)
file_handler_debug.setFormatter(formatter)
stream_handler.setFormatter(console_formatter)
logger.addHandler(file_handler_debug)


def check_numbers(channel_id):
    for user in BAC_GAMES_DICT[f'{channel_id}']:
        if BAC_GAMES_DICT[f'{channel_id}'][f'{user}'] == {}:
            return False
        else:
            continue
    return True


class JoinButton(discord.ui.Button):
    def __init__(self, channel_id, passed_embed=None): 
        super().__init__(label=f"Join (1/4)", style=discord.ButtonStyle.green)
        self.channel_id = channel_id
        self.passed_embed = passed_embed

    async def callback(self, interaction):
        async with AsyncTranslator(JO.get_lang_code(interaction.user.id)) as at:
            at.install()
            self._ = at.gettext
        if str(interaction.user.id) in BAC_GAMES_DICT[f'{self.channel_id}']:
            await interaction.response.send_message(self._("You already joined"), ephemeral=True)
        else:
            BAC_GAMES_DICT[f'{self.channel_id}'][f'{interaction.user.id}'] = {}

            self.label = f"Join ({len(BAC_GAMES_DICT[f'{self.channel_id}']) - 1}/4)"
            if len(BAC_GAMES_DICT[f'{self.channel_id}']) == 5:
                self.style = discord.ButtonStyle.gray
                self.disabled = True
            elif len(BAC_GAMES_DICT[f'{self.channel_id}']) >= 3:
                self.view.s_butt.disabled = False
                pass

            embed_dict = self.passed_embed.to_dict()
            if embed_dict['fields'][0]['value'] == "No players in lobby":
                    embed_dict['fields'][0]['value'] = ""
            embed_dict['fields'][0]['value'] += f"{interaction.user.mention}\n"
            new_embed = discord.Embed.from_dict(embed_dict)

            await interaction.response.edit_message(embed=new_embed, view=self.view)
            await interaction.followup.send(content=self._("Joined!"), ephemeral=True)
            # if interaction.user.nick == None:
            #     nickname = interaction.user.name
            # else:
            #     nickname = interaction.user.nick
            await interaction.followup.send(content="{} joined the game!".format(interaction.user.mention))


class LeaveButton(discord.ui.Button):
    def __init__(self, channel_id, join_button, passed_embed=None):
        super().__init__(label=f"Leave", style=discord.ButtonStyle.red, custom_id="leave")
        self.join_button = join_button
        self.channel_id = channel_id
        self.passed_embed = passed_embed

    async def callback(self, interaction):
        async with AsyncTranslator(JO.get_lang_code(interaction.user.id)) as at:
            at.install()
            self._ = at.gettext
        if BAC_GAMES_DICT[f'{self.channel_id}'][f'{interaction.user.id}'] is None:
            await interaction.response.send_message(self._("You didn't join the game to leave it"), ephemeral=True)
        else:
            del BAC_GAMES_DICT[f'{self.channel_id}'][f'{interaction.user.id}']
            self.join_button.label = f"Join ({len(BAC_GAMES_DICT[f'{self.channel_id}'])-1}/4)"
            if self.join_button.style == discord.ButtonStyle.gray:
                self.join_button.style = discord.ButtonStyle.green
            if len(BAC_GAMES_DICT[f'{self.channel_id}']) < 3:
                self.view.s_butt.disabled = True

            embed_dict = self.passed_embed.to_dict()
            if len(BAC_GAMES_DICT[f'{self.channel_id}']) != 1:
                embed_dict['fields'][0]['value'] = re.sub(
                    f'{interaction.user.mention}\n', "", embed_dict['fields'][0]['value'])
            else:
                embed_dict['fields'][0]['value'] = "No players in lobby"
            new_embed = discord.Embed.from_dict(embed_dict)
            await interaction.response.edit_message(embed=new_embed, view=self.view)
            await interaction.followup.send(content=self._("You left the lobby!"), ephemeral=True)
            await interaction.followup.send(content=f"{interaction.user.mention} left the game!")

class StartButton(discord.ui.Button):
    def __init__(self, channel_id, host_id):
        super().__init__(label=f"Start", style=discord.ButtonStyle.blurple, custom_id="start")
        self.channel_id = channel_id
        self.host_id = host_id
    
    async def callback(self, interaction: discord.Interaction):
        async with AsyncTranslator(JO.get_lang_code(interaction.user.id)) as at:
            at.install()
            self._ = at.gettext
        if interaction.user.id != self.host_id:
            await interaction.response.send_message(content=self._("You are not the host!"), ephemeral=True)
            return
        Join_Button, Leave_Button = self.view.j_butt, self.view.l_butt
        Join_Button.disabled = True
        Leave_Button.disabled = True
        BAC_GAMES_DICT[f'{self.channel_id}']['gameStarted'] = True
        await interaction.response.edit_message(view=self.view)
        self.view.stop()
    

class HelpButton(discord.ui.Button):
    def __init__(self):
        super().__init__(label="Help", style=discord.ButtonStyle.blurple, custom_id="help")
    
    async def callback(self, interaction: discord.Interaction):
        async_trans = AsyncTranslator(language_code=JO.get_lang_code(interaction.user.id))
        async with async_trans as lang:
            lang.install()
        
            _ = lang.gettext
            embed_help = discord.Embed(title=_("Bulls and Cows Rules"), description=_('Rulebook for the game **Bulls and Cows**'), color=discord.Color.from_rgb(0, 255, 255))
            embed_help.add_field(
                name=_("General rules"),
                value=_("The game is played in turns by two (or more) opponents who aim to decipher the other's secret code by trial and error"),
                inline=False)
            embed_help.add_field(
                name=_("Hints"),
            value=_('''After each guess, the bot will give you the amount of "bulls" and "cows" your guess has, comparing it to the secret number of each opponent:\n
 ·  **Cow** - One of the digits is in the secret number, but in the wrong place\n
 ·  **Bull** - The guess has a correct digit in the correct place\n\n
For example, your secret number is 7914 and the opponent's guess is 1234, the clues would be: '1 cow, 1 bull'. The 'cow' is 1 and 'bull' is 4\n\n
The goal of the game is to be the first to get 4 bulls on every of opponent's secret numbers'''),
            inline=False
                )
            embed_help.add_field(
                name=_("Statistics"),
                value=_("If you are registered on the bot network, bot will record your victories and losses. To access your stats, use command `botstats`"))
            self.view.h_butt = True
            await interaction.response.send_message(embed=embed_help, ephemeral=True)

class HelpButtonBagels(discord.ui.Button):
    def __init__(self):
        super().__init__(label="Help", style=discord.ButtonStyle.blurple, custom_id="help")
    
    async def callback(self, interaction: discord.Interaction):
        async with AsyncTranslator(JO.get_lang_code(interaction.user.id)) as at:
            at.install()
            _ = at.gettext
            embedHint = discord.Embed(
                title=_("Bagels Rules"), description=_('Rulebook for the game **Pico, Fermi, Bagels**'), color=discord.Color.from_rgb(0, 255, 255))
            embedHint.add_field(
                name=_("General rules"),
                value=_("The main goal is to guess the secret number of the amount of digits (with no repeating digits) depending on the mode, in certain amount of tries"),
                inline=False)
            embedHint.add_field(
                name=_("Hints"),
                value=_("After each try, bot will give three types of clues:\n"
                        " ·  **Pico** - One of the digits is in the secret number, but in the wrong place\n"
                        " ·  **Fermi** - The guess has a correct digit in the correct place\n"
                        " ·  **Bagels** - None of the digits is in the secret numbers\n\n"
                        "For example secret number is 273 and the player's guess is 123, the clues would be: 'Pico Fermi'. The 'Pico' is from the 2 and 'Fermi' is from the 3"),
                inline=False)
            embedHint.add_field(
                name=_("Modes"),
                value=_("There are currently 4 gamemodes for **Bagels**:\n"
                        " ·   **Fast mode** - Blitz mode. No major gameplay changes. *You have 7 tries to guess a 2-digit number*\n"
                        " ·   **Classic mode** - No gameplay changes. *You have 10 tries to guess a 3-digit number*\n"
                        " ·   **Hard mode** - In this mode bot will give only one clue for the guess, for example secret number is 273 and the player's guess is 123, the clue would be only: 'Pico'. *You have 13 tries to guess a 3-digit number*\n"
                        " ·   **Prolonged mode** - Nerd mode. No major gameplay changes. *You have 20 tries to guess a 6-digit number*"),
                inline=False)
            embedHint.add_field(
                name=_("Statistics"),
                value=_("If you are registered on the bot network, bot will record your victories, losses and abandoned games in each game mode. To access your stats, use command `botstats`"))
            
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
    

class ButtonsBACjoin(discord.ui.View):
    def __init__(self, channel_id, pass_embed=None, ctx:commands.Context=None, *, timeout=1200):
        super().__init__(timeout=timeout)
        self.channel_id = channel_id
        self.ctx = ctx
        self.j_butt = JoinButton(self.channel_id, pass_embed)
        self.l_butt = LeaveButton(
            channel_id=self.channel_id, join_button=self.j_butt, passed_embed=pass_embed)
        self.s_butt = StartButton(self.channel_id, ctx.author.id)
        self.s_butt.disabled = True
        self.h_butt = HelpButton()
        self.add_item(self.j_butt)
        self.add_item(self.l_butt)
        self.add_item(self.s_butt)
        self.add_item(self.h_butt)
    
    async def on_timeout(self) -> None:
        await self.ctx.send("The game hasn't started for over 20 minutes.\nRestart the game if this message has ruined all your hopes and dreams.")
        await self.message.edit(view=None)
        BAC_GAMES_DICT.pop(f'{self.ctx.channel.id}')


class InputButtonView(discord.ui.View):
    def __init__(self, channel_id, bot, player_ids):
        super().__init__(timeout=180)
        self.channel_id = channel_id
        self.bot = bot
        self.p_ids = player_ids

    @discord.ui.button(label="Input", style=discord.ButtonStyle.green)
    async def callback(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = NumberForBAC(channel_id=self.channel_id, bot=self.bot)
        await interaction.response.send_modal(modal)

    async def interaction_check(self, interaction) -> bool:
        if str(interaction.user.id) in self.p_ids:
            return True
        else:
            async_trans = AsyncTranslator(language_code=JO.get_lang_code(interaction.user.id))
            async with async_trans as lang:
                lang.install()

                _ = lang.gettext
                await interaction.response.send_message(_("Somehow you are not in game..."), ephemeral=True)
                return False


class NumberForBAC(discord.ui.Modal):
    def __init__(self, channel_id, bot):
        super().__init__(title="Number for BAC", custom_id=f"{channel_id}{random.random()}")
        self.channel_id = channel_id
        self.bot = bot

    answer = discord.ui.TextInput(
        label="Number", style=discord.TextStyle.short, required=True, min_length=4, max_length=4)

    async def on_submit(self, interaction: discord.Interaction):
        if self.children[0].value.isdecimal() and len(set(self.children[0].value)) == len(self.children[0].value):
            embed = discord.Embed(
                title="Your number", description=f"{self.children[0].value}", color=discord.Color.from_rgb(0, 255, 255))
            BAC_GAMES_DICT[f'{self.channel_id}'][f'{interaction.user.id}']['number'] = self.children[0].value
            await interaction.response.send_message(embeds=[embed])
            await interaction.followup.edit_message(message_id=interaction.message.id, view=None)
            channel = self.bot.get_channel(int(self.channel_id))
            await channel.send(content=f"{interaction.user.mention} is ready!")
            if check_numbers(self.channel_id) is True:
                await asyncio.sleep(3.0)
                await channel.send(content=f"Game starting...", delete_after = 3.0)
        else:
            async with AsyncTranslator(language_code=JO.get_lang_code(interaction.user.id)) as lang:
                lang.install()
                _ = lang.gettext
                embed = discord.Embed(
                    title=self._("Error"), description=self._("{number} is either not a number, or contains repeated digits").format(number=self.children[0].value), color=discord.Color.dark_red())
                await interaction.response.send_message(embed=embed)
class OngoingGameGuessingBAC(discord.ui.View):
    def __init__(self, order, channel_id, p_ids, bot):
        super().__init__(timeout=1800)
        self.order = order
        self.channel_id = channel_id
        self.p_ids = p_ids
        self.bot = bot
    
    @discord.ui.button(label="Guess", style=discord.ButtonStyle.blurple)
    async def callback(self, interaction: discord.Interaction, button: discord.ui.Button):
        async with AsyncTranslator(language_code=JO.get_lang_code(interaction.user.id)) as lang:
            lang.install()
            _ = lang.gettext
            await interaction.response.send_modal(GuessModalBAC(player_ids=self.p_ids, channel_id=self.channel_id, bot=self.bot, message_view=self, button=button, gettext_lang=_))
    
    async def interaction_check(self, interaction) -> bool:
        if interaction.user.id == int(self.order[0]):
            return True
        else:
            async with AsyncTranslator(language_code=JO.get_lang_code(interaction.user.id)) as lang:
                lang.install()
                _ = lang.gettext
                await interaction.response.send_message(_("It's not your turn!"), ephemeral=True)
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
        label="Number", style=discord.TextStyle.short, required=True, min_length=4, max_length=4)
    
    async def on_submit(self, interaction: discord.Interaction):
        if self.children[0].value.isdecimal() and len(set(self.children[0].value)) == len(self.children[0].value):
            def check_the_guess(guess, number):
                result = {"bulls": 0, "cows": 0}
                guess, number = list(guess), list(number)
                for num1 in guess:
                    for num2 in number:
                        if num1 == num2:
                            if guess.index(num1) == number.index(num2):
                                result['bulls'] += 1
                            else:
                                result['cows'] += 1
                return result
            results = {}
            for player_id in self.player_ids:
                if player_id == self.player_ids[0]:
                    continue
                else:
                    results[f'{player_id}'] = check_the_guess(self.children[0].value, BAC_GAMES_DICT[f'{self.channel_id}'][f'{player_id}']['number'])
            results_value = self._("**Your guess:** {number}\n").format(number=self.children[0].value)
            for player in results:
                results_value += f"**{BAC_GAMES_DICT[f'{self.channel_id}'][f'{player}']['username']}**: {results[f'{player}']['bulls']} bulls, {results[f'{player}']['cows']} cows\n"
            results['initial_guess'] = self.children[0].value
            BAC_GAMES_DICT[f'{self.channel_id}']['temp_results'] = results
            await interaction.response.send_message(content=results_value, ephemeral=True)
            channel = self.bot.get_channel(int(self.channel_id))
            await channel.send(content="They made a guess..", delete_after = 0.5)
            self.button.disabled = True
            await interaction.followup.edit_message(message_id=BAC_GAMES_DICT[f'{self.channel_id}']['extra_info']['message_id'], view=self.message_view)
        else:
            embed = discord.Embed(
                title=self._("Error"), description=self._("{number} is either not a number, or contains repeated digits. Try again!").format(number=self.children[0].value), color=discord.Color.dark_red())
            await interaction.response.send_message(embed=embed, ephemeral=True)


class BlackjackHitStop(discord.ui.View):
    def __init__(self, user_b, embed, gettext_lang):
        self._ = gettext_lang
        super().__init__(timeout=None)
        self.embed_game = embed
        self.user_b = user_b
    
    @discord.ui.button(label="Hit", style=discord.ButtonStyle.green)
    async def callback(self, interaction: discord.Interaction, button: discord.ui.Button):
        DRAW_CARD('player', 3, BJ_GAMES_DICT[f'{self.user_b.id}'])
        d_embed = self.embed_game.copy()
        d_embed.clear_fields()
        d_embed = d_embed.to_dict()
        new_embed = discord.Embed()
        view = self
        game_ended = False
        
        if BJ_GAMES_DICT[f'{self.user_b.id}']['player']['points_total'] > 21: BJ_GAMES_DICT[f'{self.user_b.id}']['player']['busted'] = True
        else: BJ_GAMES_DICT[f'{self.user_b.id}']['player']['busted'] = False
        if BJ_GAMES_DICT[f'{self.user_b.id}']['dealer']['points_total'] > 21: BJ_GAMES_DICT[f'{self.user_b.id}']['dealer']['busted'] = True
        else: BJ_GAMES_DICT[f'{self.user_b.id}']['dealer']['busted'] = False
        
        if BJ_GAMES_DICT[f'{self.user_b.id}']['dealer']['busted'] == True and BJ_GAMES_DICT[f'{self.user_b.id}']['player']['busted'] == True:
            container_embed = discord.Embed(title=d_embed['title'], description=d_embed['description'], color=discord.Color.from_rgb(108, 128, 128))
            container_embed.set_footer(text=self._("Both you and Dealer bust. You both received your coins back"))
            new_embed = container_embed
            game_ended = True
        elif BJ_GAMES_DICT[f'{self.user_b.id}']['dealer']['busted'] == True:
            container_embed = discord.Embed(title=d_embed['title'], description=d_embed['description'], color=discord.Color.from_rgb(90, 255, 255))
            container_embed.set_footer(text=self._("Dealer busts. You received {amount} coins").format(amount=BJ_GAMES_DICT[f'{self.user_b.id}']['user_data']['coins_bet'] * 2))
            new_embed = container_embed
            game_ended = True
            DF.update_userdata(BJ_GAMES_DICT[f'{self.user_b.id}']['user_data']['user_id'], "cash", int(BJ_GAMES_DICT[f'{self.user_b.id}']['user_data']['user_coins'] + BJ_GAMES_DICT[f'{self.user_b.id}']['user_data']['coins_bet'] * 2))
        elif BJ_GAMES_DICT[f'{self.user_b.id}']['player']['busted'] == True:
            container_embed = discord.Embed(title=d_embed['title'], description=d_embed['description'], color=discord.Color.from_rgb(0, 165, 165))
            container_embed.set_footer(text=self._("You bust and lost {amount} coins").format(amount=BJ_GAMES_DICT[f'{self.user_b.id}']['user_data']['coins_bet'])) 
            new_embed = container_embed
            game_ended = True
        else:
            container_embed = discord.Embed(title=d_embed['title'], description=d_embed['description'], color=discord.Color.from_rgb(0, 255, 255))
            new_embed = container_embed
        
        player_value, dealer_value = "", ""
        for i in range(1,int((len(BJ_GAMES_DICT[f'{self.user_b.id}']['player'])-3)/2)+1):
            player_value += f"**{BJ_GAMES_DICT[f'{self.user_b.id}']['player'][f'card{i}']}**{BJ_GAMES_DICT[f'{self.user_b.id}']['player'][f'suit{i}']} "
        if game_ended:
            view = None
            dealer_pretotal = f"{BJ_GAMES_DICT[f'{self.user_b.id}']['dealer']['points_total']}"
            for i in range(1,int((len(BJ_GAMES_DICT[f'{self.user_b.id}']['dealer'])-3)/2)+1):
                dealer_value += f"**{BJ_GAMES_DICT[f'{self.user_b.id}']['dealer'][f'card{i}']}**{BJ_GAMES_DICT[f'{self.user_b.id}']['dealer'][f'suit{i}']} "
        else:
            dealer_pretotal = f"{BJ_GAMES_DICT[f'{self.user_b.id}']['dealer']['first_card_points']}+?"
            for i in range(1,2):
                dealer_value += f"**{BJ_GAMES_DICT[f'{self.user_b.id}']['dealer'][f'card{i}']}**{BJ_GAMES_DICT[f'{self.user_b.id}']['dealer'][f'suit{i}']} " + bot_config.CustomEmojis.question_mark
        new_embed.add_field(name=f"{BJ_GAMES_DICT[f'{self.user_b.id}']['player']['nickname']} [{BJ_GAMES_DICT[f'{self.user_b.id}']['player']['points_total']}]", value=f"{player_value}", inline=True)
        new_embed.add_field(name=f"Dealer [{dealer_pretotal}]", value=f"{dealer_value}", inline=True)
        
        await interaction.response.edit_message(embed=new_embed, view=view)
        if game_ended:
            del BJ_GAMES_DICT[f"{BJ_GAMES_DICT[f'{self.user_b.id}']['user_data']['user_id']}"]
    

    @discord.ui.button(label="Stand", style=discord.ButtonStyle.red)
    async def callback2(self, interaction: discord.Interaction, button: discord.ui.Button):
        d_embed = self.embed_game.copy()
        d_embed.clear_fields()
        d_embed = d_embed.to_dict()
        new_embed = discord.Embed()
        view = None

        if BJ_GAMES_DICT[f'{self.user_b.id}']['dealer']['points_total'] > 21: BJ_GAMES_DICT[f'{self.user_b.id}']['dealer']['busted'] = True
        else: BJ_GAMES_DICT[f'{self.user_b.id}']['dealer']['busted'] = False

        if BJ_GAMES_DICT[f'{self.user_b.id}']['dealer']['busted'] == True:
            container_embed = discord.Embed(title=d_embed['title'], description=d_embed['description'], color=discord.Color.from_rgb(90, 255, 255))
            container_embed.set_footer(text=self._("Dealer busts. You received {amount} coins").format(amount=BJ_GAMES_DICT[f'{self.user_b.id}']['user_data']['coins_bet'] * 2))
            new_embed = container_embed
            DF.update_userdata(BJ_GAMES_DICT[f'{self.user_b.id}']['user_data']['user_id'], "cash", int(BJ_GAMES_DICT[f'{self.user_b.id}']['user_data']['user_coins'] + BJ_GAMES_DICT[f'{self.user_b.id}']['user_data']['coins_bet']))
        else:
            if BJ_GAMES_DICT[f'{self.user_b.id}']['dealer']['points_total'] < BJ_GAMES_DICT[f'{self.user_b.id}']['player']['points_total']:
                container_embed = discord.Embed(title=d_embed['title'], description=d_embed['description'], color=discord.Color.from_rgb(90, 255, 255))
                container_embed.set_footer(text=self._("Dealer has less value than you. You received {amount} coins").format(amount=BJ_GAMES_DICT[f'{self.user_b.id}']['user_data']['coins_bet'] * 2))
                new_embed = container_embed
                DF.update_userdata(BJ_GAMES_DICT[f'{self.user_b.id}']['user_data']['user_id'], "cash", int(BJ_GAMES_DICT[f'{self.user_b.id}']['user_data']['user_coins'] + BJ_GAMES_DICT[f'{self.user_b.id}']['user_data']['coins_bet'] * 2))
            elif BJ_GAMES_DICT[f'{self.user_b.id}']['dealer']['points_total'] > BJ_GAMES_DICT[f'{self.user_b.id}']['player']['points_total']:
                container_embed = discord.Embed(title=d_embed['title'], description=d_embed['description'], color=discord.Color.from_rgb(0, 165, 165))
                container_embed.set_footer(text=self._("You have less value than dealer, and lost {amount} coins").format(amount=BJ_GAMES_DICT[f'{self.user_b.id}']['user_data']['coins_bet']))
                new_embed = container_embed
            else:
                container_embed = discord.Embed(title=d_embed['title'], description=d_embed['description'], color=discord.Color.from_rgb(108, 128, 128))
                container_embed.set_footer(text=self._("It's a tie. You received your coins back"))
                new_embed = container_embed
        
        player_value, dealer_value = "", ""
        dealer_pretotal = f"{BJ_GAMES_DICT[f'{self.user_b.id}']['dealer']['points_total']}"
        for i in range(1,int((len(BJ_GAMES_DICT[f'{self.user_b.id}']['player'])-2)/2)+1):
            player_value += f"**{BJ_GAMES_DICT[f'{self.user_b.id}']['player'][f'card{i}']}**{BJ_GAMES_DICT[f'{self.user_b.id}']['player'][f'suit{i}']} "
        for i in range(1,int((len(BJ_GAMES_DICT[f'{self.user_b.id}']['dealer'])-3)/2)+1):
            dealer_value += f"**{BJ_GAMES_DICT[f'{self.user_b.id}']['dealer'][f'card{i}']}**{BJ_GAMES_DICT[f'{self.user_b.id}']['dealer'][f'suit{i}']} "
        new_embed.add_field(name=f"{BJ_GAMES_DICT[f'{self.user_b.id}']['player']['nickname']} [{BJ_GAMES_DICT[f'{self.user_b.id}']['player']['points_total']}]", value=f"{player_value}", inline=True)
        new_embed.add_field(name=f"Dealer [{dealer_pretotal}]", value=f"{dealer_value}", inline=True)

        await interaction.response.edit_message(embed=new_embed, view=view)
        del BJ_GAMES_DICT[f"{BJ_GAMES_DICT[f'{self.user_b.id}']['user_data']['user_id']}"]
    
    async def interaction_check(self, interaction) -> bool:
        if interaction.user.id == self.user_b.id:
            return True
        else:
            async with AsyncTranslator(JO.get_lang_code(interaction.user.id)) as at:
                at.install()
                _ = at.gettext
                await interaction.response.send_message(_("It's not your game!"), ephemeral=True)
            return False 

class BacReplayRecordsPageDown(discord.ui.Button):
    def __init__(self):
        super().__init__(label="<", style=discord.ButtonStyle.blurple, custom_id="page_down", disabled=True)
    
    async def callback(self, interaction: discord.Interaction):
        self.view._current_page -= 1
        if self.view._current_page == 1: self.disabled = True
        else: self.disabled = False
        self.view.children[1].disabled = False
        embed_page = discord.Embed.from_dict(self.view.pages[f"page_{(self.view._current_page - 1)}"])
        await interaction.response.edit_message(embed=embed_page, view=self.view)

class BacReplayRecordsPageUp(discord.ui.Button):
    def __init__(self, disabled:bool=False):
        super().__init__(label=">", style=discord.ButtonStyle.blurple, custom_id="page_up", disabled=disabled)
    
    async def callback(self, interaction: discord.Interaction):
        self.view._current_page += 1
        self.disabled = False if self.view._max_pages != self.view._current_page else True
        self.view.children[0].disabled = False
        if f"page_{self.view._current_page}" in self.view.pages:
            embed_page = discord.Embed.from_dict(self.view.pages[f"page_{(self.view._current_page) - (0 if isinstance(self.view, BacReplayRecordsView) else 1)}"])
        else:
            if isinstance(self.view, BacReplayRecordsView):
                embed_page = discord.Embed(title=self.view.pages['page_1']['title'], description=self.view.pages['page_1']['description'], color=b_cfg.CustomColors.cyan)
                embed_page.set_footer(text=f"Page: {self.view._current_page}/{self.view._max_pages}")
                embed_page, self.view.recorded_games = self.view.function(embed_page, self.view.recorded_games[12*(self.view._current_page-1):12*self.view._current_page])
                self.view.pages[f"page_{self.view._current_page}"] = embed_page.to_dict()
            else:
                turn = (self.view._current_page)-1
                embed_page = discord.Embed(title=self.view.pages['page_0']['title'], description=f"Turn {turn}/{self.view._max_pages-1}", color=b_cfg.CustomColors.cyan)
                embed_page.set_footer(text=f"Page: {self.view._current_page}/{self.view._max_pages}")
                for player in self.view.game_dict[f'turn{turn}']:
                    value = f"**Initial guess — {self.view.game_dict[f'turn{turn}'][player]['initial_guess']}**"
                    for p in self.view.game_dict[f'turn{turn}'][player]:
                        if p != "initial_guess": value += f"\n{self.view.player_list[int(p)]}: " \
                        f"{self.view.game_dict[f'turn{turn}'][player][p]['cows']} cows, " \
                        f"{self.view.game_dict[f'turn{turn}'][player][p]['bulls']} bulls"
                    embed_page.add_field(name=f"{self.view.player_list[int(player)]}", value=value)
                self.view.pages[f"page_{turn}"] = embed_page.to_dict()
        await interaction.response.edit_message(embed=embed_page, view=self.view)

class BacReplayRecordsView(discord.ui.View):
    def __init__(self, pages: dict, recorded_games: dict, function):
        super().__init__(timeout=600)
        self.pages = pages
        self.recorded_games = recorded_games
        self.function = function
        self._current_page = 1
        self._max_pages = math.ceil(len(recorded_games)/12) if len(recorded_games) != 0 else 1
        self.add_item(BacReplayRecordsPageDown())
        self.add_item(BacReplayRecordsPageUp(disabled=False if self._max_pages != self._current_page else True))
    
    async def on_timeout(self) -> None:
        for button in self.children: button.disabled = True
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

    @commands.hybrid_command(name="number-guessing", description="Play a quick guessing game where you try to find the correct number based on two types of clues", aliases=["ng", "ngstart"], with_app_command=True)
    @app_commands.choices(difficulty=[app_commands.Choice(name="Easy", value="easy"), app_commands.Choice(name="Medium", value="medium"), app_commands.Choice(name="Hard", value="hard")])
    async def numberguessing(self, ctx: commands.Context, difficulty=None):
        channel = ctx.channel
        hard = False
        async with AsyncTranslator(JO.get_lang_code(ctx.author.id)) as at:
            at.install()
            _ = at.gettext
            if difficulty == None:
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
                embed=discord.Embed(title=_("Game started"), description=_("Start guessing :3"), color=b_cfg.CustomColors.cyan)
                await ctx.send(embed=embed)
                DF.add_command_stats(ctx.author.id)
                NG_GUILD_CHECK.add(channel.id)
                while guess != -1 and channel.id in NG_GUILD_CHECK:
                    if guess <= 10 and guess != 0:
                        await ctx.send(_("You have only {guess} guesses left").format(guess=guess))
                    elif guess == 0:
                        await ctx.send(_("You ran out of guesses, gg"))
                        break
                    if hard == True:
                        if count > 0:
                            count -= 1
                        elif count == 0:
                            n = random.randint(1, maxnum)
                            count += 20
                        else:
                            pass
                    else:
                        pass
                    await ctx.send(_("Pick a number between **1** and **{maxnum}**").format(maxnum=maxnum))
                    while True:
                        try:
                            msg = await self.bot.wait_for(
                                "message",
                                timeout=60,
                                check=lambda m: m.channel.id == ctx.channel.id and m.content.isnumeric() and m.author.id != self.bot.user.id,
                            )
                            attempt = int(msg.content)
                        except ValueError:
                            continue
                        except asyncio.TimeoutError:
                            await ctx.send(_("Game canceled due to timeout."))
                            check += 1
                            break
                        else:
                            break
                    if attempt > n:
                        await ctx.send(_("The secret number is **smaller** than **{attempt}**").format(attempt=attempt))
                        guess -= 1
                    elif attempt < n:
                        await ctx.send(_("The secret number is **bigger** than **{attempt}**").format(attempt=attempt))
                        guess -= 1
                    elif attempt == n:
                        await ctx.send(_("{} **won the game**").format(msg.author.mention))
                        if DF.local_checks(msg.author.id) is True:
                            DF.add_stats(msg.author.id, f"ngWins.{difficulty}")
                        break
                    elif attempt == None:
                        break
                NG_GUILD_CHECK.remove(channel.id)
            else:
                await ctx.send(_("There is already a game running in this channel"))

    @commands.hybrid_command(name="hangman", description="Play an old school favorite, a word game where the goal is simply to find the missing word", aliases=["hgm", "hangm"], with_app_command=True)
    @app_commands.choices(diff=[app_commands.Choice(name="Short word", value="short"), app_commands.Choice(name="Long word", value="long")])
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
        async with AsyncTranslator(JO.get_lang_code(ctx.author.id)) as at:
            at.install()
            _ = at.gettext
            start_embed = discord.Embed(
                title=_("Game started!"),
                description=_("Guess the word (You have only 6 tries)"),
                colour=discord.Color.from_rgb(0, 255, 255),
            )
            start_embed.add_field(name=pics[missed].strip(), value="", inline=False)
            start_embed.add_field(name=_("Word"), value=f"**{word_completion}**", inline=False)
            start_embed.add_field(name=_("Used letters"), value=_("*No letters*"), inline=False)
            main_message = await ctx.send(embed=start_embed)
            DF.add_command_stats(ctx.author.id)
            while guessed == False and missed < 6:
                try:
                    guess = await self.bot.wait_for(
                        "message", timeout=300, check=lambda m: m.channel.id == ctx.channel.id
                    )
                except asyncio.TimeoutError:
                    await ctx.send(_("Game canceled due to timeout."))
                    if DF.local_checks(ctx.author.id) == True:
                        DF.add_stats(ctx.author.id, f"hangman.{diff}.losses")
                    return
                p_guess = (guess.content).lower()
                if len(p_guess) == 1 and p_guess.isalpha():
                    if p_guess in guessed_letters:
                        await guess.reply("You already guessed this letter")
                    elif p_guess not in word_to_guess:
                        await guess.reply("{guess} is not in the word".format(guess=p_guess))
                        missed += 1
                        guessed_letters.append(p_guess)
                    else:
                        await guess.reply("Good job, {guess} is in the word".format(guess=p_guess), delete_after=5)
                        guessed_letters.append(p_guess)
                        word_as_list = list(word_completion)
                        indices = [
                            i for i, letter in enumerate(word_to_guess) if letter == p_guess
                        ]
                        for index in indices:
                            word_as_list[index] = p_guess
                        word_completion = "".join(word_as_list)
                        if "-" not in word_completion:
                            guessed = True
                second_embed = start_embed.to_dict()
                second_embed['fields'][0]['name'] = pics[missed].strip()
                second_embed['fields'][1]['value'] = f"**{word_completion}**"
                second_embed['fields'][2]['value'] = f"*{', '.join(guessed_letters)}*"
                await main_message.edit(embed=discord.Embed.from_dict(second_embed))
            if missed == 6:
                await ctx.send(_("The man is hanged. You ran out of tries. The word was: {word}").format(word=word_to_guess))
                if DF.local_checks(guess.author.id) == True:
                    DF.add_stats(guess.author.id, f"hangman.{diff}.losses")
            elif missed <= 5:
                await ctx.send(_("Congrats, you guessed the word!"))
                if DF.local_checks(guess.author.id) == True:
                    DF.add_stats(guess.author.id, f"hangman.{diff}.wins")

    @commands.cooldown(1, 15, commands.BucketType.user)
    @commands.hybrid_command(name="blackjack", description="Play a round of blackjack using in-bot currency for bets and payouts", aliases=['bj'], with_app_command=True)
    async def blackjack(self, ctx: commands.Context, cash=None):
        user = ctx.author
        user_cash = None
        pack = [2, 3, 4, 5, 6, 7, 8, 9, 10, "J", "Q", "K", "A"]
        suits = ["<:clubs_out:997942006808588379>", "<:spades_out:997942007987183717>", ":hearts:", ":diamonds:"]
        
        async with AsyncTranslator(JO.get_lang_code(user.id)) as lang:
            lang.install()
            _ = lang.gettext
        
            if str(user.id) in BJ_GAMES_DICT:
                old_one = self.bot.get_channel(BJ_GAMES_DICT[f'{user.id}']['user_data']['channel_id'])
                old_one = old_one.get_partial_message(BJ_GAMES_DICT[f'{user.id}']['user_data']['message_id'])
                await old_one.delete()
                nickname = BJ_GAMES_DICT[f'{user.id}']['player']['nickname']
                embed_game = discord.Embed(title=_("Resuming a game of Blackjack..."), description=_("{nickname} bet **{bet}** coins to play blackjack").format(nickname=nickname, bet=BJ_GAMES_DICT[f'{user.id}']['user_data']['coins_bet']), color=bot_config.CustomColors.cyan) 
                player_value, dealer_value = "", ""
                dealer_pretotal = f"{BJ_GAMES_DICT[f'{user.id}']['dealer']['first_card_points']}+?"
                for i in range(1,3):
                    player_value += f"**{BJ_GAMES_DICT[f'{user.id}']['player'][f'card{i}']}**{BJ_GAMES_DICT[f'{user.id}']['player'][f'suit{i}']} "
                for i in range(1,2):
                    dealer_value += f"**{BJ_GAMES_DICT[f'{user.id}']['dealer'][f'card{i}']}**{BJ_GAMES_DICT[f'{user.id}']['dealer'][f'suit{i}']} " + bot_config.CustomEmojis.question_mark
                embed_game.add_field(name=f"{nickname} [{BJ_GAMES_DICT[f'{user.id}']['player']['points_total']}]", value=f"{player_value}", inline=True)
                embed_game.add_field(name=f"Dealer [{dealer_pretotal}]", value=f"{dealer_value}", inline=True)
                view = BlackjackHitStop(user_b=user, embed=embed_game, gettext_lang=_)
                original_message = await ctx.send(embed=embed_game, view=view)
                BJ_GAMES_DICT[f'{user.id}']['user_data']['message_id'] = original_message.id
                BJ_GAMES_DICT[f'{user.id}']['user_data']['channel_id'] = original_message.channel.id
            else:
                if cash is None:
                    await ctx.send(content=_("You didn't wager any coins!"), delete_after = 10.0)
                else: 
                    if DF.local_checks(user.id) == False:
                        await ctx.send(content=_("You are not registered or not logged in"), delete_after = 10.0)
                    else:
                        if cash.isdigit() == True:
                            cash = int(cash)
                        else:
                            if cash.lower() == "all":
                                user_cash = DF.get_userdata_by_id(user.id, ["cash"])
                                cash = user_cash["cash"]
                                user_cash = cash
                            else:
                                await ctx.send(content=_("Using **10** as a wager..."), delete_after = 10.0)
                                cash = 10
                        if int(cash) < 10:
                            await ctx.send(content=_("Using **10** as a wager..."), delete_after = 10.0)
                            cash = 10
                        elif int(cash) > 200000:
                            await ctx.send(content=_("Using **200000** as a wager..."), delete_after = 10.0)
                            cash = 200000
                        if user_cash is None:
                            user_cash = DF.get_userdata_by_id(user.id, ["cash"])
                            user_cash = user_cash["cash"]
                        if user_cash < 10:
                            await ctx.send(_("You don't have enough coins. *Minimal value is* **10**"))
                        elif user_cash < int(cash):
                            await ctx.send(_("You don't have enough coins. *You have only **{user_cash}** coins*").format(user_cash=user_cash))
                        else:
                            nickname = DF.get_user_by_id(user.id, ["nickname"])
                            nickname = nickname['nickname']
                            BJ_GAMES_DICT[f'{user.id}'] = {"dealer": {}, "player": {}, "user_data": { "coins_bet": cash, "user_coins": user_cash, "user_id": user.id} }
                            DF.update_userdata(user.id, "cash", int(user_cash - int(cash)))
                            global DRAW_CARD
                            def DRAW_CARD(p, i, dict_g):
                                dict_g[f'{p}'][f'card{i}'] = random.choice(pack)
                                dict_g[f'{p}'][f'suit{i}'] = random.choice(suits)
                                if type(dict_g[f'{p}'][f'card{i}']) == str and dict_g[f'{p}'][f"card{i}"] != "A":
                                    points = 10
                                elif dict_g[f'{p}'][f"card{i}"] == "A":
                                    if dict_g[f'{p}'][f'points_total'] + 11 > 21: points = 1
                                    else: points = 11
                                else:
                                    points = dict_g[f'{p}'][f"card{i}"]
                                if p == "dealer" and i == 1:
                                    dict_g[f'{p}']['first_card_points'] = points
                                dict_g[f'{p}']['points_total'] += points
                            for i in range(1,3):
                                for p in BJ_GAMES_DICT[f'{user.id}']:
                                    print(p)
                                    if p == "user_data": continue
                                    if len(BJ_GAMES_DICT[f'{user.id}'][f'{p}']) == 0:
                                        BJ_GAMES_DICT[f'{user.id}'][f'{p}']['points_total'] = 0
                                    DRAW_CARD(p, i, BJ_GAMES_DICT[f'{user.id}'])
                            card_num = 3
                            while BJ_GAMES_DICT[f'{user.id}']['dealer']['points_total'] < 17:
                                DRAW_CARD('dealer', card_num, BJ_GAMES_DICT[f'{user.id}'])
                                card_num += 1
                            embed_game = discord.Embed(title=_("Blackjack"), description=_("{nickname} bet **{cash}** coins to play blackjack").format(nickname=nickname, cash=cash), color=bot_config.CustomColors.cyan) 
                            player_value, dealer_value = "", ""
                            dealer_pretotal = f"{BJ_GAMES_DICT[f'{user.id}']['dealer']['first_card_points']}+?"
                            for i in range(1,3):
                                player_value += f"**{BJ_GAMES_DICT[f'{user.id}']['player'][f'card{i}']}**{BJ_GAMES_DICT[f'{user.id}']['player'][f'suit{i}']} "
                            for i in range(1,2):
                                dealer_value += f"**{BJ_GAMES_DICT[f'{user.id}']['dealer'][f'card{i}']}**{BJ_GAMES_DICT[f'{user.id}']['dealer'][f'suit{i}']} "
                            dealer_value += bot_config.CustomEmojis.question_mark
                            BJ_GAMES_DICT[f'{user.id}']['player']['nickname'] = nickname
                            embed_game.add_field(name=f"{nickname} [{BJ_GAMES_DICT[f'{user.id}']['player']['points_total']}]", value=f"{player_value}", inline=True)
                            embed_game.add_field(name=f"Dealer [{dealer_pretotal}]", value=f"{dealer_value}", inline=True)
                            view = BlackjackHitStop(user_b=user, embed=embed_game, gettext_lang=_)
                            original_message = await ctx.send(embed=embed_game, view=view)
                            if DF.local_checks(user.id):
                                DF.add_command_stats(user.id)
                            BJ_GAMES_DICT[f'{user.id}']['user_data']['message_id'] = original_message.id
                            BJ_GAMES_DICT[f'{user.id}']['user_data']['channel_id'] = original_message.channel.id

    @commands.command(aliases=['bulls'])
    async def bullsandcows(self, ctx: commands.Context, mode:str=None, arg: Union[Optional[discord.Member], str]=None):
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
                if mode in modes: mode = mode
                else: mode = "classic"
        match arg:
            case None:
                arg = "classic"
            case "blitz":
                arg = "fast"
            case "nerd":
                arg = "long"
            case _:
                if arg in args or mode == "replay": pass
                else: arg = "classic"
        
        async with AsyncTranslator(JO.get_lang_code(ctx.author.id)) as at:
            at.install()
            _ = at.gettext

            async def bagels_game_loop(digits, guesses, arg):
                guess_count = guesses
                num_list = list('0123456789')
                random.shuffle(num_list)
                secret_number = num_list[0:digits]
                embed = discord.Embed(title=_("Bagels - {mode}").format(mode=arg.capitalize()),
                                    description=_("I have thought of {digits}-digit number. Try to guess it, you have {guesses} tries").format(digits=digits, guesses=guesses),
                                    color=discord.Color.from_rgb(0, 255, 255))
                embed.set_footer(
                    text=_("Need help with figuring it out? Use button 𝐡𝐞𝐥𝐩 to get more information on the mode"))
                view = BagelsView()
                view.message = await ctx.send(embed=embed, view=view)
                while guess_count != -1:
                    try:
                        guess = await self.bot.wait_for(
                            "message", timeout=300, check=lambda m: m.author.id == user.id and m.channel.id == ctx.channel.id and m.content.isdecimal() and len(m.content) == digits
                        )
                    except asyncio.TimeoutError:
                        await ctx.send(_("Game abandoned."))
                        if DF.local_checks(user.id):
                            DF.add_stats(user.id, f"bulls.pfb.{arg}.abandoned")
                            DF.add_command_stats(user.id)
                        break
                    guess_m = guess.content
                    if repeating_symbols(guess_m) == True:
                        await guess.reply(_("This guess has repeating digits. Please pick a different guess"))
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
                                    if guess_listed.index(num1) == secret_number.index(num2):
                                        answer.append("Fermi")
                                    else:
                                        answer.append("Pico")

                        if len(answer) == 0:
                            answer.append("Bagels")
                        answer.sort()
                        answer_string = " ".join(answer)
                        await ctx.send(answer_string)
                        if secret_number == guess_listed:
                            embedWin = discord.Embed(title=_("Congrats, you are victorious"),
                                                    description=_("{mention} won in the {arg} mode. It took {amount} guesses").format(mention=ctx.author.mention, arg=arg, amount=guesses-guess_count),
                                                    color=discord.Color.from_rgb(0, 255, 255))
                            await ctx.send(embed=embedWin)
                            if DF.local_checks(user.id):
                                DF.add_stats(user.id, f"bulls.pfb.{arg}.wins")
                                DF.add_command_stats(user.id)
                            break
                        elif guess_count == 0:
                            embedLoss = discord.Embed(title=_("Sorry to inform you, but you lost"),
                                                    description=_("You are out of tries. The number was **{number}**").format(number=''.join(secret_number)), color=discord.Color.from_rgb(0, 255, 255))
                            await ctx.send(embed=embedLoss)
                            if DF.local_checks(user.id):
                                DF.add_stats(user.id, f"bulls.pfb.{arg}.losses")
                                DF.add_command_stats(user.id)
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
                    embedClassicStart = discord.Embed(title="Bulls and Cows Classic Mode",
                                                    description="Press the green button to join the game",
                                                    color=discord.Color.from_rgb(0, 255, 255))
                    embedClassicStart.set_footer(
                    text=f"Need help with figuring it out? Use button 𝐡𝐞𝐥𝐩 to get more information on the mode. Host must use 𝘀𝘁𝗮𝗿𝘁 button in order to start the game")
                    BAC_GAMES_DICT[f'{ctx.channel.id}'] = {}
                    BAC_GAMES_DICT[f'{ctx.channel.id}']['gameStarted'] = False
                    BAC_GAMES_DICT[f'{ctx.channel.id}'][f'{user.id}'] = {}
                    embedClassicStart.add_field(
                        name="Players in game", value=f"{user.mention}\n")
                    view = ButtonsBACjoin(
                        ctx.message.channel.id, pass_embed=embedClassicStart, ctx=ctx)
                    view.message = await ctx.send(embed=embedClassicStart, view=view)
                    if DF.local_checks(user.id):
                        DF.add_command_stats(user.id)

                    if await view.wait() is True:
                        logger.info(f"BAC game timeout in {ctx.channel.id}")
                        return
                    if BAC_GAMES_DICT[f'{ctx.channel.id}'] is not None and BAC_GAMES_DICT[f'{ctx.channel.id}']['gameStarted'] == True:
                        p_ids = []
                        for p in BAC_GAMES_DICT[f'{ctx.channel.id}']:
                            p_ids.append(p)
                        p_ids.remove('gameStarted')
                        
                        input_view = InputButtonView(ctx.channel.id, self.bot, p_ids)
                        for player in p_ids:
                            u_player = self.bot.get_user(int(player))
                            async with AsyncTranslator(JO.get_lang_code(u_player.id)) as at:
                                at.install()
                                _ = at.gettext
                                await u_player.send(_("Please input a 4-digit number"), view=input_view)
                        await self.bot.wait_for("message", check=lambda m: m.channel.id == ctx.channel.id and m.author.id in bot_config.bot_ids and check_numbers(ctx.channel.id) is True and m.content == "Game starting...")
                        stat_gathering = ""
                        queue = []
                        for player in p_ids:
                            d_user = self.bot.get_user(int(player))
                            BAC_GAMES_DICT[f'{ctx.channel.id}'][f'{player}']['username'] = d_user.name
                            BAC_GAMES_DICT[f'{ctx.channel.id}'][f'{player}']['win_condt'] = 0
                            queue.append(BAC_GAMES_DICT[f'{ctx.channel.id}'][f'{player}']['username'])
                            if DF.check_exists(d_user.id) == True:
                                stat = JO.get_userdata_stats(d_user.id)[1]
                                stat_gathering += f"**{BAC_GAMES_DICT[f'{ctx.channel.id}'][f'{player}']['username']}**: {stat['bulls']['number']['wins']} Wins/{stat['bulls']['number']['losses']} Losses\n"
                            else:
                                stat_gathering += f"**{BAC_GAMES_DICT[f'{ctx.channel.id}'][f'{player}']['username']}**: No info available\n"
                        embed_gamestarted = discord.Embed(
                            title="Game started!", description=f"**Queue:** \n*--->* {' - '.join(queue)}", color=discord.Color.from_rgb(0, 255, 255))
                        embed_gamestarted.add_field(name="Stats",
                                                    value=f"{stat_gathering}")
                        main_message = await ctx.send(embed=embed_gamestarted)
                        main_embed_dict = embed_gamestarted.to_dict()
                        
                        utcnow = datetimefix.utcnow()
                        
                        json_game = {
                            "meta": {
                                "players": {},
                                "datetime_started": str(utcnow.isoformat()) + "Z",
                                "state": "",
                                "duration": utcnow,
                            },
                            "game": {}
                        }
                        for player in p_ids:
                            json_game["meta"]["players"][f"player{p_ids.index(player)+1}"] = {
                                "user_id": int(player), 
                                "number": str(BAC_GAMES_DICT[f'{ctx.channel.id}'][f'{player}']['number'])
                                }
                        
                        turn = 0
                        BAC_GAMES_DICT[f'{ctx.channel.id}']['extra_info'] = {"first_player": int(p_ids[0])}

                        def update_queue(array):
                            temp_var = array[0]
                            del array[0]
                            array.append(temp_var)
                            return array

                        while True:
                            # await ctx.send(f"{json_game}")
                            player_guessing = self.bot.get_user(int(p_ids[0]))
                            view = OngoingGameGuessingBAC(order=p_ids, channel_id=ctx.channel.id, p_ids=p_ids, bot=self.bot)
                            turn_message = await ctx.send(f"It's {player_guessing.mention}'s turn. Please enter your next guess", view=view)
                            BAC_GAMES_DICT[f'{ctx.channel.id}']['extra_info']['message_id'] = turn_message.id
                            try:
                                await self.bot.wait_for("message", check=lambda m: m.channel.id == ctx.channel.id and m.author.id in bot_config.bot_ids and m.content == "They made a guess..")
                                #guess = await self.bot.wait_for("message", check=lambda m: m.channel.id == ctx.channel.id and m.author.id == int(p_ids[0]) and m.content.isdecimal() and len(set(m.content)) == len(m.content), timeout=1800)
                            except asyncio.TimeoutError:
                                embedError = discord.Embed(
                                    title="Timeout Error",
                                    description=f"{player_guessing} took more than 30 minutes to guess. Game abandoned.",
                                    color=discord.Color.from_rgb(255, 0, 0))
                                if DF.local_checks(player_guessing.id) == True:
                                    await DF.add_stats(player_guessing.id, "bulls.number.losses")
                                del p_ids[0]
                                for player in p_ids:
                                    player_d = self.bot.get_user(int(player))
                                    if DF.local_checks(player_d) == True:
                                        DF.add_stats(player_d.id, "bulls.number.wins")
                                await ctx.send(embed=embedError)
                                time_finished = datetimefix.utcnow()
                                json_game['meta']['duration'] = time_finished - json_game["duration"]
                                json_game['meta']['state'] = f"Abandoned. {player_guessing.id}"
                                break
                            results = BAC_GAMES_DICT[f'{ctx.channel.id}']['temp_results']
                            if BAC_GAMES_DICT[f'{ctx.channel.id}']["extra_info"]['first_player'] == int(p_ids[0]): 
                                turn += 1
                                json_game["game"][f"turn{turn}"] = {}
                            json_game["game"][f"turn{turn}"][f'{p_ids[0]}'] = results
                            for player in results:
                                if player == "initial_guess": continue
                                if results[f'{player}']['bulls'] == 4: BAC_GAMES_DICT[f'{ctx.channel.id}'][f'{p_ids[0]}']['win_condt'] += 1
                            if BAC_GAMES_DICT[f'{ctx.channel.id}'][f'{p_ids[0]}']['win_condt'] == len(results)-1:
                                tries = len(json_game["game"])
                                embed_win = discord.Embed(title=f"Game ended", description=f"{player_guessing.mention} is the winner. It took them {tries} guesses", color=bot_config.CustomColors.cyan)
                                await ctx.send(embed=embed_win)
                                if DF.local_checks(player_guessing.id) == True:
                                    DF.add_stats(player_guessing.id, "bulls.number.wins")
                                del p_ids[0]
                                for player in p_ids:
                                    if DF.local_checks(int(player)) == True:
                                        DF.add_stats(int(player), "bulls.number.losses")
                                time_finished = datetimefix.utcnow()
                                json_game['meta']['duration'] = time_finished - json_game["meta"]["duration"]
                                json_game['meta']['state'] = f"Finished. {player_guessing.id}"
                                break
                            queue = update_queue(queue)
                            p_ids = update_queue(p_ids)
                            new_embed_game_started = discord.Embed(title=f"{main_embed_dict['title']}", description=f"**Queue:** \n*--->* {' - '.join(queue)}", color=bot_config.CustomColors.cyan)
                            new_embed_game_started.add_field(name=main_embed_dict['fields'][0]['name'], value=main_embed_dict['fields'][0]['value'])
                            await main_message.edit(embed=new_embed_game_started)
                        DF.insert_json(json_game, "bulls_records")
                    BAC_GAMES_DICT.pop(f'{ctx.channel.id}')
                case "replay":
                    user = ctx.author
                    if DF.local_checks(user.id):
                        nickname = DF.get_user_by_id(user.id, ["nickname"])
                        nickname = nickname['nickname']
                    else: nickname = user.name
                    
                    def create_player_list(player_list, temp_cache):
                        return_dict = {}
                        for player in player_list: 
                            if player == user.id: return_dict[player] = nickname
                            else:
                                if str(player) not in temp_cache:
                                    if DF.local_checks(player):
                                        p_nickname = DF.get_user_by_id(player, ["nickname"])
                                        p_nickname = p_nickname['nickname']
                                    else:
                                        try:
                                            p_user = self.bot.get_user(player)
                                            p_nickname = p_user.name
                                        except Exception:
                                            p_nickname = _("Anonymous")
                                    temp_cache[str(player)] = p_nickname
                                else: p_nickname = temp_cache[str(player)]
                                return_dict[player] = p_nickname
                        return return_dict, temp_cache
                    
                    def build_game_replay(game:dict):
                        if not game:
                            embed = discord.Embed(title=_("Game not found"), description=_("The requested game was not found."), color=b_cfg.CustomColors.dark_red)
                            return embed, None

                        # Check if the received dictionary contains "Private" flag
                        if 'private' in game:
                            embed = discord.Embed(title=_("Game not played by requested user"), description=_("The requested user did not play this game."), color=b_cfg.CustomColors.dark_red)
                            return embed, None
                        
                        player_list = [game['meta']['players'][x]['user_id'] for x in game['meta']['players']]
                        player_list_id = player_list.copy()
                        player_list_dict, temp = create_player_list(player_list, {})
                        del temp
                        player_list = [player_list_dict[x] for x in player_list_dict]
                        queue = " -> ".join(player_list)
                        finish_state = game['meta']['state'].split()
                        embed = discord.Embed(title=_(("Win" if int(finish_state[1]) == user.id else "Loss") + " by guessing" if finish_state[0] == "Finished." else " by timeout"), description=queue, color=b_cfg.CustomColors.cyan)
                        value = ""
                        for i in range(0, len(player_list)): value += f"\n{b_cfg.CustomEmojis.empty * 2}{player_list[i]}: {game['meta']['players'][f'player{i+1}']['number']}" + (_(" - ***Winner***") if player_list_id[i] == int(finish_state[1]) else "")
                        embed.add_field(name=_("Players"), value=value)
                        embed.add_field(name=_("Date played"), value=f"<t:{calendar.timegm(game['meta']['datetime_started'].timetuple())}> (<t:{calendar.timegm(game['meta']['datetime_started'].timetuple())}:R>)", inline=False)
                        embed.add_field(name=_("Duration"),value=f"`{pretty_time_delta(game['meta']['duration'])}`", inline=False)
                        embed.add_field(name=_("Amount of turns"), value=f"{len(game['game'])} {_('turns') if len(game['game']) != 1 else _('turn')}")
                        embed.set_footer(text=_("Page: 1/{total_pages}").format(total_pages=len(game['game']) + 1))
                        view = BacReplayGameView(embed, game['game'], player_list=player_list_dict)
                        return embed, view
                    if isinstance(arg, discord.Member):
                        recorded_games = DF.get_bac_records(user.id, member_2=arg.id)
                    elif arg.isdigit():
                        recorded_game = DF.get_bac_records(user.id, game_id=int(arg))
                        embed, view = build_game_replay(recorded_game)
                        await ctx.send(embed=embed, view=view)
                        return
                    else:
                        recorded_games = DF.get_bac_records(user.id)
                    print(recorded_games)
                    recorded_games.reverse()
                    pages_dict = {}
                    
                    embed_pg1=discord.Embed(title=_("Games archive"), description=_("{}' archive of played **Bulls and Cows** games {}").format(nickname, _('against {mention}').format(mention=arg.mention) if isinstance(arg, discord.Member) else ''), color=b_cfg.CustomColors.cyan)
                    embed_pg1.set_footer(text=_("Page: 1/{total_pages}").format(total_pages=math.ceil(len(recorded_games) / 12) if len(recorded_games) != 0 else 1))
                    def finish_page(embed:discord.Embed, games:list):
                        if len(games) == 0: embed.add_field(name=_("No games"), value=_("I couldn't find any games "))
                        temp_cache = {}
                        for game in games:
                            if games.index(game) % 12 == 0 and games.index(game) != 0:
                                break
                            
                            player_list = [game[x] for x in game if x in ["user_1", "user_2", "user_3", "user_4"] and game[x] is not None]
                            player_list, temp_cache = create_player_list(player_list, temp_cache)
                            player_queue = " -> ".join(player_list.values())
                            if len(player_queue) > 20: player_queue = player_queue[0:20]+"..."
                            timestamp = game['t1'].replace(tzinfo=pytz.UTC)
                            embed.add_field(name=_("Win") if game['player_won'] == user.id else _("Loss"), value=f"{player_queue} \n`{pretty_date(timestamp)}`\n*id: **{game['id']}***")
                        return embed, games
                    embed_pg1, recorded_games = finish_page(embed_pg1, recorded_games)
                    pages_dict[f'page_1'] = embed_pg1.to_dict()
                    bac_replay_view = BacReplayRecordsView(pages_dict, recorded_games, function=finish_page)
                    bac_replay_view.message = await ctx.send(embed=embed_pg1, view=bac_replay_view)


async def setup(bot):
    await bot.add_cog(SmallGames(bot))

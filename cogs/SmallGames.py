from socket import timeout
import sys
import discord
import random
import asyncio
import json
from discord.ext import commands
from functions import *
from hangman_words import *
import config
from datetime import *
import GameFunctions as GF

global NG_GUILD_CHECK
NG_GUILD_CHECK = []

global BAC_GAMES_DICT
BAC_GAMES_DICT = {}

global BJ_GAMES_DICT
BJ_GAMES_DICT = {}

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
formatter = logging.Formatter('%(asctime)s:%(levelname)s --- %(message)s')
console_formatter = CustomFormatter()
stream_handler = logging.StreamHandler()
coloredlogs.install(level='DEBUG', logger=logger)
file_handler_debug = logging.FileHandler(config.s_games_log_debug)
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
        print("checking join button")
        print(interaction.user.id, BAC_GAMES_DICT[f'{self.channel_id}'])
        if str(interaction.user.id) in BAC_GAMES_DICT[f'{self.channel_id}']:
            await interaction.response.send_message("You already joined", ephemeral=True)
        else:
            BAC_GAMES_DICT[f'{self.channel_id}'][f'{interaction.user.id}'] = {}

            self.label = f"Join ({len(BAC_GAMES_DICT[f'{self.channel_id}']) - 1}/4)"
            if len(BAC_GAMES_DICT[f'{self.channel_id}']) == 4:
                self.style = discord.ButtonStyle.gray
                self.disabled = True
            else:
                pass

            embed_dict = self.passed_embed.to_dict()
            print(embed_dict)
            if embed_dict['fields'][0]['value'] == "No players in lobby":
                    embed_dict['fields'][0]['value'] = ""
            embed_dict['fields'][0]['value'] += f"{interaction.user.mention}\n"
            new_embed = discord.Embed.from_dict(embed_dict)

            await interaction.response.edit_message(embed=new_embed, view=self.view)
            await interaction.followup.send(content="Joined!", ephemeral=True)
            # if interaction.user.nick == None:
            #     nickname = interaction.user.name
            # else:
            #     nickname = interaction.user.nick
            await interaction.followup.send(content=f"{interaction.user.mention} joined the game!")


class LeaveButton(discord.ui.Button):
    def __init__(self, channel_id, join_button, passed_embed=None):
        super().__init__(label=f"Leave", style=discord.ButtonStyle.red, custom_id="leave")
        self.join_button = join_button
        self.channel_id = channel_id
        self.passed_embed = passed_embed

    async def callback(self, interaction):
        print("checking leave button")
        if BAC_GAMES_DICT[f'{self.channel_id}'][f'{interaction.user.id}'] is None:
            await interaction.response.send_message("You didn't join the game to leave", ephemeral=True)
        else:
            del BAC_GAMES_DICT[f'{self.channel_id}'][f'{interaction.user.id}']
            self.join_button.label = f"Join ({len(BAC_GAMES_DICT[f'{self.channel_id}'])-1}/4)"
            if self.join_button.style == discord.ButtonStyle.gray:
                self.join_button.style = discord.ButtonStyle.green

            embed_dict = self.passed_embed.to_dict()
            print(embed_dict)
            if len(BAC_GAMES_DICT[f'{self.channel_id}']) != 1:
                embed_dict['fields'][0]['value'] = re.sub(
                    f'{interaction.user.mention}\n', "", embed_dict['fields'][0]['value'])
            else:
                embed_dict['fields'][0]['value'] = "No players in lobby"
            new_embed = discord.Embed.from_dict(embed_dict)
            await interaction.response.edit_message(embed=new_embed, view=self.view)
            await interaction.followup.send(content="You left!", ephemeral=True)
            # if interaction.user.nick == None:
            #     nickname = interaction.user.name
            # else:
            #     nickname = interaction.user.nick
            await interaction.followup.send(content=f"{interaction.user.mention} left the game!")


class ButtonsBACjoin(discord.ui.View):
    def __init__(self, channel_id, pass_embed=None, *, timeout=1200):
        super().__init__(timeout=timeout)
        self.channel_id = channel_id
        self.j_butt = JoinButton(self.channel_id, pass_embed)
        self.l_butt = LeaveButton(
            channel_id=self.channel_id, join_button=self.j_butt, passed_embed=pass_embed)
        self.add_item(self.j_butt)
        self.add_item(self.l_butt)

    # async def interaction_check(self, interaction) -> bool:
    #     print(interaction.user.id, BAC_GAMES_DICT)
    #     print(interaction.application_id, interaction.id, self.j_butt.custom_id)
    #     if interaction.application_id != "leave":
    #         if interaction.user.id in BAC_GAMES_DICT[f'{self.channel_id}']:
    #             await interaction.response.send_message("You already joined", ephemeral=True)
    #             return False
    #         else:
    #             BAC_GAMES_DICT[f'{self.channel_id}'].append(interaction.user.id)
    #             return True
    #     else:
    #         if interaction.user.id not in BAC_GAMES_DICT[f'{self.channel_id}']:
    #             await interaction.response.send_message("You didn't join the game to leave", ephemeral=True)
    #             return False
    #         else:
    #             BAC_GAMES_DICT[f'{self.channel_id}'].remove(
    #                 interaction.user.id)
    #             return True


class InputButtonView(discord.ui.View):
    def __init__(self, channel_id, modal, player_ids):
        super().__init__()
        self.channel_id = channel_id
        self.modal = modal
        self.p_ids = player_ids

    @discord.ui.button(label="Input", style=discord.ButtonStyle.green)
    async def callback(self, interaction: discord.Interaction, button: discord.ui.Button):
        print("checking input")
        await interaction.response.send_modal(self.modal)

    async def interaction_check(self, interaction) -> bool:
        if str(interaction.user.id) in self.p_ids:
            return True
        else:
            await interaction.response.send_message("Somehow you are not in game...", ephemeral=True)
            return False


class NumberForBAC(discord.ui.Modal):
    def __init__(self, channel_id, bot):
        super().__init__(title="Number for BAC")
        self.channel_id = channel_id
        self.bot = bot

    answer = discord.ui.TextInput(
        label="Number", style=discord.TextStyle.short, required=True, min_length=4, max_length=4)

    async def on_submit(self, interaction: discord.Interaction):
        if self.children[0].value.isdecimal() and len(set(self.children[0].value)) == len(self.children[0].value):
            embed = discord.Embed(
                title="Your number", description=f"{self.children[0].value}", color=discord.Color.from_rgb(0, 255, 255))
            print(self.answer)
            BAC_GAMES_DICT[f'{self.channel_id}'][f'{interaction.user.id}']['number'] = self.children[0].value
            await interaction.response.send_message(embeds=[embed])
            await interaction.followup.edit_message(message_id=interaction.message.id, view=None)
            channel = self.bot.get_channel(int(self.channel_id))
            await channel.send(content=f"{interaction.user.mention} is ready!")
            if check_numbers(self.channel_id) is True:
                await asyncio.sleep(3.0)
                await channel.send(content=f"Game starting...", delete_after = 3.0)
        else:
            embed = discord.Embed(
                title="Error", description=f"{self.children[0].value} is either not a number, or contains repeated digits", color=discord.Color.dark_red())
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
        await interaction.response.send_modal(GuessModalBAC(player_ids=self.p_ids, channel_id=self.channel_id, bot=self.bot, message_view=self, button=button))
    
    async def interaction_check(self, interaction) -> bool:
        if interaction.user.id == int(self.order[0]):
            return True
        else:
            await interaction.response.send_message("It's not your turn!", ephemeral=True)
            return False 

class GuessModalBAC(discord.ui.Modal):
    def __init__(self, player_ids, channel_id, bot, message_view, button):
        super().__init__(title="Your guess...?")
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
            results_value = f"**Your guess:** {self.children[0].value}\n"
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
                title="Error", description=f"{self.children[0].value} is either not a number, or contains repeated digits. Try again!", color=discord.Color.dark_red())
            await interaction.response.send_message(embed=embed, ephemeral=True)


class BlackjackHitStop(discord.ui.View):
    def __init__(self, user_b, embed):
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
            container_embed.set_footer(text="Both you and Dealer busted. You both received your coins back")
            new_embed = container_embed
            game_ended = True
        elif BJ_GAMES_DICT[f'{self.user_b.id}']['dealer']['busted'] == True:
            container_embed = discord.Embed(title=d_embed['title'], description=d_embed['description'], color=discord.Color.from_rgb(90, 255, 255))
            container_embed.set_footer(text=f"Dealer busts. You received {BJ_GAMES_DICT[f'{self.user_b.id}']['user_data']['coins_bet'] * 2} coins")
            new_embed = container_embed
            game_ended = True
            update_userdata(BJ_GAMES_DICT[f'{self.user_b.id}']['user_data']['user_id'], "cash", int(BJ_GAMES_DICT[f'{self.user_b.id}']['user_data']['user_coins'] + BJ_GAMES_DICT[f'{self.user_b.id}']['user_data']['coins_bet'] * 2))
        elif BJ_GAMES_DICT[f'{self.user_b.id}']['player']['busted'] == True:
            container_embed = discord.Embed(title=d_embed['title'], description=d_embed['description'], color=discord.Color.from_rgb(0, 165, 165))
            container_embed.set_footer(text=f"You bust and lost {BJ_GAMES_DICT[f'{self.user_b.id}']['user_data']['coins_bet']} coins")
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
                dealer_value += f"**{BJ_GAMES_DICT[f'{self.user_b.id}']['dealer'][f'card{i}']}**{BJ_GAMES_DICT[f'{self.user_b.id}']['dealer'][f'suit{i}']} " + config.CustomEmojis.question_mark
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
            container_embed.set_footer(text=f"Dealer busts. You received {BJ_GAMES_DICT[f'{self.user_b.id}']['user_data']['coins_bet'] * 2} coins")
            new_embed = container_embed
            update_userdata(BJ_GAMES_DICT[f'{self.user_b.id}']['user_data']['user_id'], "cash", int(BJ_GAMES_DICT[f'{self.user_b.id}']['user_data']['user_coins'] + BJ_GAMES_DICT[f'{self.user_b.id}']['user_data']['coins_bet']))
        else:
            if BJ_GAMES_DICT[f'{self.user_b.id}']['dealer']['points_total'] < BJ_GAMES_DICT[f'{self.user_b.id}']['player']['points_total']:
                container_embed = discord.Embed(title=d_embed['title'], description=d_embed['description'], color=discord.Color.from_rgb(90, 255, 255))
                container_embed.set_footer(text=f"Dealer has less value than you. You received {BJ_GAMES_DICT[f'{self.user_b.id}']['user_data']['coins_bet'] * 2} coins")
                new_embed = container_embed
                update_userdata(BJ_GAMES_DICT[f'{self.user_b.id}']['user_data']['user_id'], "cash", int(BJ_GAMES_DICT[f'{self.user_b.id}']['user_data']['user_coins'] + BJ_GAMES_DICT[f'{self.user_b.id}']['user_data']['coins_bet'] * 2))
            elif BJ_GAMES_DICT[f'{self.user_b.id}']['dealer']['points_total'] > BJ_GAMES_DICT[f'{self.user_b.id}']['player']['points_total']:
                container_embed = discord.Embed(title=d_embed['title'], description=d_embed['description'], color=discord.Color.from_rgb(0, 165, 165))
                container_embed.set_footer(text=f"You have less value than dealer, and lost {BJ_GAMES_DICT[f'{self.user_b.id}']['user_data']['coins_bet']} coins")
                new_embed = container_embed
            else:
                container_embed = discord.Embed(title=d_embed['title'], description=d_embed['description'], color=discord.Color.from_rgb(108, 128, 128))
                container_embed.set_footer(text="It's a tie. You received your coins back")
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
            await interaction.response.send_message("It's not your game!", ephemeral=True)
            return False 


class SmallGames(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def cog_load(self):
        print("Small Games cog loaded successfully!")

    @commands.command(
        aliases=["ng", "Numberguessing", "ngstart"],
        help="A small number guessing game",
        pass_context=True,
    )
    async def numberguessing(self, ctx, difficulty=None, guesses=None):
        channel = ctx.channel
        count = 20
        hard = False
        if difficulty == None:
            difficulty = "easy"
        else:
            difficulty = difficulty.lower()
        if difficulty == "easy":
            maxnum = 1000
        elif difficulty == "medium":
            maxnum = 10000
        elif difficulty == "hard":
            maxnum = 100000
            hard = True
        else:
            difficulty = "easy"
            maxnum = 1000
            await ctx.send("Difficulty was changed to `easy`")
        n = random.randint(1, maxnum)
        if guesses == None:
            guess = 100
        else:
            guess = int(guesses)
        if channel.id not in NG_GUILD_CHECK:
            await ctx.send("Game started, guess a number")
            add_command_stats(ctx.message.author)
            NG_GUILD_CHECK.append(channel.id)
            check_end = False
            await asyncio.sleep(1)
            print(n)
            while guess != -1 and check_end == False:
                if guess <= 10 and guess != 0:
                    await ctx.send("You have only " + str(guess) + " guesses left")
                elif guess == 0:
                    check_end = True
                    await ctx.send("You ran out of guesses, gg")
                    break
                if hard == True:
                    if count > 0:
                        count -= 1
                    elif count == 0:
                        n = random.randint(1, maxnum)
                        print(n)
                        count += 20
                    else:
                        pass
                else:
                    pass
                await ctx.send("Pick a number between 1 and " + str(maxnum))
                while True:
                    try:
                        msg = await self.bot.wait_for(
                            "message",
                            timeout=60,
                            check=lambda m: m.channel.id == ctx.channel.id,
                        )
                        attempt = int(msg.content)
                    except ValueError:
                        continue
                    except asyncio.TimeoutError:
                        await ctx.send("Game canceled due to timeout.")
                        check += 1
                        break
                    else:
                        break
                if attempt > n and check_end == False:
                    await ctx.send("The number is smaller")
                    guess -= 1
                elif attempt < n and check_end == False:
                    await ctx.send("The number is bigger")
                    guess -= 1
                if attempt == n and check_end == False:
                    await ctx.send("Here is a winner: " + format(msg.author.mention))
                    if local_checks(msg.author) == True:
                        await add_stats(msg.author, "ngWins", difficulty)
                    check_end == True
                    break
                elif attempt == None:
                    break
            NG_GUILD_CHECK.remove(channel.id)
        else:
            await ctx.send("Game has already started")

    @commands.command(aliases=["hgm", "hangm"])
    async def hangman(self, ctx):
        seed = random.randrange(sys.maxsize)
        word_to_guess = random.choice(words)
        word_to_guess = re.sub("\\n", "", word_to_guess)
        missed = 0
        logger.debug(f"I chose word: {word_to_guess}. Seed: {seed}")
        word_completion = "-" * len(word_to_guess)
        guessed = False
        guessed_letters = []
        start_embed = discord.Embed(
            title="Game started!",
            description="Guess the word (You have only 6 tries)",
            colour=discord.Color.from_rgb(0, 255, 255),
        )
        first_embed = discord.Embed(title=pics[missed])
        # for num in pics:
        # await ctx.send(num)
        await ctx.send(embed=start_embed)
        add_command_stats(ctx.message.author)
        msg = await ctx.send(embed=first_embed)
        comp = await ctx.send(word_completion)
        while guessed == False and missed < 6:
            try:
                guess = await self.bot.wait_for(
                    "message", timeout=300, check=lambda m: m.channel.id == ctx.channel.id
                )
            except asyncio.TimeoutError:
                await ctx.send("Game canceled due to timeout.")
                return
            p_guess = (guess.content).lower()
            if len(p_guess) == 1 and p_guess.isalpha():
                if p_guess in guessed_letters:
                    await ctx.send(
                        format(guess.author.mention) +
                        " You already guessed this letter"
                    )
                elif p_guess not in word_to_guess:
                    await ctx.send(
                        format(guess.author.mention) + " " +
                        p_guess + " is not in the word"
                    )
                    missed += 1
                    guessed_letters.append(p_guess)
                else:
                    await ctx.send(
                        format(guess.author.mention)
                        + " Good job, "
                        + p_guess
                        + " is in the word",
                        delete_after=5,
                    )
                    guessed_letters.append(p_guess)
                    word_as_list = list(word_completion)
                    indices = [
                        i for i, letter in enumerate(word_to_guess) if letter == p_guess
                    ]
                    for index in indices:
                        word_as_list[index] = p_guess
                    word_completion = "".join(word_as_list)
                    # re.sub('\\', '', word_completion)
                    if "-" not in word_completion:
                        guessed = True
            elif len(p_guess) == len(word_to_guess) and p_guess.isalpha():
                if p_guess != word_to_guess:
                    await ctx.send(p_guess + " is not the word")
                    missed += 1
                else:
                    guessed = True
                    await ctx.send(
                        format(guess.author.mention) +
                        " guessed the word and won the game"
                    )
                    word_completion = word_to_guess
            else:
                pass
            second_embed = discord.Embed(title=pics[missed])
            await msg.edit(embed=second_embed)
            await comp.edit(content=word_completion)
        if missed == 6:
            await ctx.send("The man is hanged. You ran out of tries. The word was: " + word_to_guess)
            if local_checks(guess.author) == True:
                await add_stats(guess.author, "hangman", "Losses")
        elif missed <= 5:
            await ctx.send("Congrats, you guessed the word!")
            if local_checks(guess.author) == True:
                await add_stats(guess.author, "hangman", "Wins")

    @commands.command(aliases=['bj'])
    async def blackjack(self, ctx, cash=None):
        user = ctx.author
        pack = [2, 3, 4, 5, 6, 7, 8, 9, 10, "J", "Q", "K", "A"]
        suits = ["<:clubs_out:997942006808588379>", "<:spades_out:997942007987183717>", "♥", "♦"]
        
        if str(user.id) in BJ_GAMES_DICT:
            old_one = self.bot.get_channel(BJ_GAMES_DICT[f'{user.id}']['user_data']['channel_id'])
            old_one = old_one.get_partial_message(BJ_GAMES_DICT[f'{user.id}']['user_data']['message_id'])
            await old_one.delete()
            nickname = BJ_GAMES_DICT[f'{user.id}']['player']['nickname']
            embed_game = discord.Embed(title="Resuming a game of Blackjack...", description=f"{nickname} bet **{BJ_GAMES_DICT[f'{user.id}']['user_data']['coins_bet']}** coins to play blackjack", color=config.CustomColors.cyan) 
            player_value, dealer_value = "", ""
            dealer_pretotal = f"{BJ_GAMES_DICT[f'{user.id}']['dealer']['first_card_points']}+?"
            for i in range(1,3):
                player_value += f"**{BJ_GAMES_DICT[f'{user.id}']['player'][f'card{i}']}**{BJ_GAMES_DICT[f'{user.id}']['player'][f'suit{i}']} "
            for i in range(1,2):
                dealer_value += f"**{BJ_GAMES_DICT[f'{user.id}']['dealer'][f'card{i}']}**{BJ_GAMES_DICT[f'{user.id}']['dealer'][f'suit{i}']} " + config.CustomEmojis.question_mark
            embed_game.add_field(name=f"{nickname} [{BJ_GAMES_DICT[f'{user.id}']['player']['points_total']}]", value=f"{player_value}", inline=True)
            embed_game.add_field(name=f"Dealer [{dealer_pretotal}]", value=f"{dealer_value}", inline=True)
            view = BlackjackHitStop(user_b=user, embed=embed_game)
            original_message = await ctx.send(embed=embed_game, view=view)
            BJ_GAMES_DICT[f'{user.id}']['user_data']['message_id'] = original_message.id
            BJ_GAMES_DICT[f'{user.id}']['user_data']['channel_id'] = original_message.channel.id
        else:
            if cash is None:
                await ctx.send(content = "You didn't wager any coins!", delete_after = 10.0)
            else: 
                if local_checks(user) == False:
                        await ctx.send(content = "You are not registered or not logged in", delete_after = 10.0)
                else:
                    if cash.isdigit() == True:
                        cash = int(cash)
                    else:
                        await ctx.send(content = "Using **10** as a wager...", delete_after = 10.0)
                        cash = 10
                    if int(cash) < 10:
                        await ctx.send(content = "Using **10** as a wager...", delete_after = 10.0)
                        cash = 10
                    user_cash = get_userdata_by_id(user.id, "cash")
                    user_cash = user_cash["cash"]
                    if user_cash < 10:
                        await ctx.send("You don't have enough coins. *Minimal value is* **10**")
                    elif user_cash < int(cash):
                        await ctx.send(f"You don't have enough coins. *You have only **{user_cash}** coins*")
                    else:
                        nickname = get_user_by_id(user.id, "nickname")
                        nickname = nickname[0]["nickname"]
                        BJ_GAMES_DICT[f'{user.id}'] = {"dealer": {}, "player": {}, "user_data": { "coins_bet": cash, "user_coins": user_cash, "user_id": user.id} }
                        update_userdata(user.id, "cash", int(user_cash - int(cash)))
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
                        embed_game = discord.Embed(title="Blackjack", description=f"{nickname} bet **{cash}** coins to play blackjack", color=config.CustomColors.cyan) 
                        player_value, dealer_value = "", ""
                        dealer_pretotal = f"{BJ_GAMES_DICT[f'{user.id}']['dealer']['first_card_points']}+?"
                        for i in range(1,3):
                            player_value += f"**{BJ_GAMES_DICT[f'{user.id}']['player'][f'card{i}']}**{BJ_GAMES_DICT[f'{user.id}']['player'][f'suit{i}']} "
                        for i in range(1,2):
                            dealer_value += f"**{BJ_GAMES_DICT[f'{user.id}']['dealer'][f'card{i}']}**{BJ_GAMES_DICT[f'{user.id}']['dealer'][f'suit{i}']} "
                        dealer_value += config.CustomEmojis.question_mark
                        BJ_GAMES_DICT[f'{user.id}']['player']['nickname'] = nickname
                        embed_game.add_field(name=f"{nickname} [{BJ_GAMES_DICT[f'{user.id}']['player']['points_total']}]", value=f"{player_value}", inline=True)
                        embed_game.add_field(name=f"Dealer [{dealer_pretotal}]", value=f"{dealer_value}", inline=True)
                        view = BlackjackHitStop(user_b=user, embed=embed_game)
                        original_message = await ctx.send(embed=embed_game, view=view)
                        if local_checks(user=user):
                            add_command_stats(user)
                        BJ_GAMES_DICT[f'{user.id}']['user_data']['message_id'] = original_message.id
                        BJ_GAMES_DICT[f'{user.id}']['user_data']['channel_id'] = original_message.channel.id



    @commands.command(aliases=['bulls'])
    async def bullsandcows(self, ctx, mode=None, arg=None):
        user = ctx.author
        bot_prefix = await determine_prefix(client=self.bot, message=ctx.message)
        bot_prefix = bot_prefix[0]
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
            case _:
                if mode in modes: mode = mode
                else: mode = "classic"
        match arg:
            case None:
                arg = "normal"
            case "blitz":
                arg = "fast"
            case "nerd":
                arg = "long"
            case _:
                if arg.isnumeric():
                    arg = arg
                elif arg in args: arg = arg
                else: arg = "normal"

        async def bagels_game_loop(digits, guesses, arg):
            guess_count = guesses
            num_list = list('0123456789')
            random.shuffle(num_list)
            secret_number = num_list[0:digits]
            print(secret_number)
            embed = discord.Embed(title=f"Bagels {arg} mode",
                                  description=f"I have thought of {digits}-digit number. Try to guess it, you have {guesses} tries",
                                  color=discord.Color.from_rgb(0, 255, 255))
            embed.set_footer(
                text="Need help with figuring it out? Use command ^.𝐡𝐞𝐥𝐩 to get more information on the mode")
            await ctx.send(embed=embed)
            while guess_count != -1:
                try:
                    guess = await self.bot.wait_for(
                        "message", timeout=300, check=lambda m: m.author.id == user.id and m.channel.id == ctx.channel.id and m.content.isdecimal() and len(m.content) == digits or m.content == f"^{bot_prefix}help"
                    )
                except asyncio.TimeoutError:
                    await ctx.send("Game abandoned.")
                    if local_checks(user):
                        await add_stats(user, "bulls", "pfb", arg, "abandoned")
                        add_command_stats(user)
                    break
                guess_m = guess.content
                if guess_m == f"^{bot_prefix}help":
                    embedHint = discord.Embed(
                        title="Bagels Rules", description='Rulebook for the game **Pico, Fermi, Bagels**', color=discord.Color.from_rgb(0, 255, 255))
                    embedHint.add_field(
                        name="General rules",
                        value="The main goal is to guess the secret number of the amount of digits (with no repeating digits) depending on the mode, in certain amount of tries",
                        inline=False)
                    embedHint.add_field(
                        name="Hints",
                        value="After each try, bot will give three types of clues:\n"
                        " ·  **Pico** - One of the digits is in the secret number, but in the wrong place\n"
                        " ·  **Fermi** - The guess has a correct digit in the correct place\n"
                        " ·  **Bagels** - None of the digits is in the secret numbers\n\n"
                        "For example secret number is 273 and the player's guess is 123, the clues would be: 'Pico Fermi'. The 'Pico' is from the 2 and 'Fermi' is from the 3",
                        inline=False)
                    embedHint.add_field(
                        name="Modes",
                        value="There are currently 4 gamemodes for **Bagels**:\n"
                        " ·   **Fast mode** - Blitz mode. No major gameplay changes. *You have 7 tries to guess a 2-digit number*\n"
                        " ·   **Classic mode** - No gameplay changes. *You have 10 tries to guess a 3-digit number*\n"
                        " ·   **Hard mode** - In this mode bot will give only one clue for the guess, for example secret number is 273 and the player's guess is 123, the clue would be only: 'Pico'. *You have 13 tries to guess a 3-digit number*\n"
                        " ·   **Prolonged mode** - Nerd mode. No major gameplay changes. *You have 20 tries to guess a 6-digit number*",
                        inline=False)
                    embedHint.add_field(
                        name="Statistics",
                        value="If you are registered on the bot network, bot will record your victories, losses and abandoned games in each game mode. To access your stats, use command `botstats`")
                    await ctx.send(embed=embedHint)
                else:
                    if repeating_symbols(guess_m) == True:
                        await ctx.send("This guess has repeating digits. Please pick a different guess")
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
                            embedWin = discord.Embed(title="Congrats, you are victorious",
                                                     description=f"{ctx.author.mention} won in the {arg} mode. It took {guesses-guess_count} guesses",
                                                     color=discord.Color.from_rgb(0, 255, 255))
                            await ctx.send(embed=embedWin)
                            if local_checks(user):
                                await add_stats(user, "bulls", "pfb", arg, "wins")
                                add_command_stats(user)
                            break
                        elif guess_count == 0:
                            embedLoss = discord.Embed(title="Sorry to inform you, but you lost",
                                                      description=f"You are out of tries. The number was **{''.join(secret_number)}**", color=discord.Color.from_rgb(0, 255, 255))
                            await ctx.send(embed=embedLoss)
                            if local_checks(user):
                                await add_stats(user, "bulls", "pfb", arg, "losses")
                                add_command_stats(user)
                            break

                print(guess_m)

        match mode:
            case "bagels":
                match arg:
                    case "normal":
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
                                                description=f"Press the green button to join the game",
                                                color=discord.Color.from_rgb(0, 255, 255))
                embedClassicStart.set_footer(
                text=f"Need help with figuring it out? Use command ^{bot_prefix}𝐡𝐞𝐥𝐩 to get more information on the mode. Host must use ^{bot_prefix}𝘀𝘁𝗮𝗿𝘁 in order to start the game")
                BAC_GAMES_DICT[f'{ctx.channel.id}'] = {}
                BAC_GAMES_DICT[f'{ctx.channel.id}']['gameStarted'] = False
                BAC_GAMES_DICT[f'{ctx.channel.id}'][f'{user.id}'] = {}
                embedClassicStart.add_field(
                    name="Players in game", value=f"{user.mention}\n")
                view = ButtonsBACjoin(
                    ctx.message.channel.id, pass_embed=embedClassicStart)
                start_massage = await ctx.send(embed=embedClassicStart, view=view)
                if local_checks(user):
                    add_command_stats(user)
                while True:
                    try:
                        message_a = await self.bot.wait_for(
                            "message", timeout=1200, check=lambda m: m.author.id == user.id and m.channel.id == ctx.channel.id
                            and len(BAC_GAMES_DICT[f'{ctx.channel.id}']) > 2 and BAC_GAMES_DICT[f'{ctx.channel.id}']['gameStarted'] != True
                            and m.content == f"^{bot_prefix}start" or m.content == f"^{bot_prefix}help"
                        )
                    except asyncio.TimeoutError:
                        await ctx.send("The game hasn't started for over 20 minutes.\nRestart the game if this message has ruined all your hopes and dreams.")
                        await start_massage.edit(view=None)
                        break

                    if message_a.content == f"^{bot_prefix}start":
                        Join_Button, Leave_Button = view.j_butt, view.l_butt
                        Join_Button.disabled = True
                        Leave_Button.disabled = True
                        await start_massage.edit(view=view)
                        BAC_GAMES_DICT[f'{ctx.channel.id}']['gameStarted'] = True
                        print(BAC_GAMES_DICT[f'{ctx.channel.id}'])
                        break
                    elif message_a.content == f"^{bot_prefix}help":
                        embed_help = discord.Embed(title="Bulls and Cows Rules", description='Rulebook for the game **Bulls and Cows**', color=discord.Color.from_rgb(0, 255, 255))
                        embed_help.add_field(
                            name="General rules",
                            value="The game is played in turns by two (or more) opponents who aim to decipher the other's secret code by trial and error",
                            inline=False)
                        embed_help.add_field(
                            name="Hints",
                        value="After each guess, the bot will give you the amount of \"bulls\" and \"cows\" your guess has, comparing it to the secret number of each opponent:\n" \
                        " ·  **Cow** - One of the digits is in the secret number, but in the wrong place\n" \
                        " ·  **Bull** - The guess has a correct digit in the correct place\n\n" \
                        "For example, your secret number is 7914 and the opponent's guess is 1234, the clues would be: '1 cow, 1 bull'. The 'cow' is 1 and 'bull' is 4\n\n" \
                        "The goal of the game is to be the first to get 4 bulls on every of opponent's secret numbers",
                        inline=False
                            )
                        embed_help.add_field(
                            name="Statistics",
                            value="If you are registered on the bot network, bot will record your victories and losses. To access your stats, use command `botstats`")

                if BAC_GAMES_DICT[f'{ctx.channel.id}']['gameStarted'] == True:
                    p_ids = []
                    for p in BAC_GAMES_DICT[f'{ctx.channel.id}']:
                        p_ids.append(p)
                    p_ids.remove('gameStarted')
                    modal = NumberForBAC(
                        channel_id=ctx.channel.id, bot=self.bot)
                    input_view = InputButtonView(ctx.channel.id, modal, p_ids)
                    for player in p_ids:
                        u_player = self.bot.get_user(int(player))
                        await u_player.send("Please input a 4-digit number", view=input_view)
                    await self.bot.wait_for("message", check=lambda m: m.channel.id == ctx.channel.id and m.author.id in config.bot_ids and check_numbers(ctx.channel.id) is True and m.content == "Game starting...")
                    stat_gathering = ""
                    queue = []
                    for player in p_ids:
                        d_user = self.bot.get_user(int(player))
                        BAC_GAMES_DICT[f'{ctx.channel.id}'][f'{player}']['username'] = d_user.name
                        BAC_GAMES_DICT[f'{ctx.channel.id}'][f'{player}']['win_condt'] = 0
                        queue.append(BAC_GAMES_DICT[f'{ctx.channel.id}'][f'{player}']['username'])
                        if check_exists(d_user) == True:
                            stat = get_json(member=d_user, raw=False)
                            stat_gathering += f"**{BAC_GAMES_DICT[f'{ctx.channel.id}'][f'{player}']['username']}**: {stat['bulls']['number']['wins']} Wins/{stat['bulls']['number']['losses']} Losses\n"
                        else:
                            stat_gathering += f"**{BAC_GAMES_DICT[f'{ctx.channel.id}'][f'{player}']['username']}**: No info available\n"
                    embed_gamestarted = discord.Embed(
                        title="Game started!", description=f"**Queue:** \n*--->* {' - '.join(queue)}", color=discord.Color.from_rgb(0, 255, 255))
                    embed_gamestarted.add_field(name="Stats",
                                                value=f"{stat_gathering}")
                    main_message = await ctx.send(embed=embed_gamestarted)
                    main_embed_dict = embed_gamestarted.to_dict()
                    
                    utcnow = datetime.now(timezone.utc)
                    
                    json_game = {
                        "meta": {
                            "players": {},
                            "datetime_started": utcnow,
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
                            await self.bot.wait_for("message", check=lambda m: m.channel.id == ctx.channel.id and m.author.id in config.bot_ids and m.content == "They made a guess..")
                            #guess = await self.bot.wait_for("message", check=lambda m: m.channel.id == ctx.channel.id and m.author.id == int(p_ids[0]) and m.content.isdecimal() and len(set(m.content)) == len(m.content), timeout=1800)
                        except asyncio.TimeoutError:
                            embedError = discord.Embed(
                                title="Timeout Error",
                                description=f"{player_guessing} took more than 30 minutes to guess. Game abandoned.",
                                color=discord.Color.from_rgb(255, 0, 0))
                            if local_checks(player_guessing) == True:
                                await add_stats(player_guessing, "bulls", "number", "losses")
                            del p_ids[0]
                            for player in p_ids:
                                player_d = self.bot.get_user(int(player))
                                if local_checks(player_d) == True:
                                    await add_stats(player_d, "bulls", "number", "wins")
                            await ctx.send(embed=embedError)
                            time_finished = datetime.now(timezone.utc)
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
                            embed_win = discord.Embed(title=f"Game ended", description=f"{player_guessing.mention} is the winner. It took them {tries} guesses", color=config.CustomColors.cyan)
                            await ctx.send(embed=embed_win)
                            if local_checks(player_guessing) == True:
                                await add_stats(player_guessing, "bulls", "number", "wins")
                            del p_ids[0]
                            for player in p_ids:
                                if local_checks(int(player)) == True:
                                    await add_stats(int(player), "bulls", "number", "losses")
                            time_finished = datetime.now(timezone.utc)
                            json_game['meta']['duration'] = time_finished - json_game["meta"]["duration"]
                            json_game['meta']['state'] = f"Finished. {player_guessing.id}"
                            break
                        queue = update_queue(queue)
                        p_ids = update_queue(p_ids)
                        new_embed_game_started = discord.Embed(title=f"{main_embed_dict['title']}", description=f"**Queue:** \n*--->* {' - '.join(queue)}", color=config.CustomColors.cyan)
                        new_embed_game_started.add_field(name=main_embed_dict['fields'][0]['name'], value=main_embed_dict['fields'][0]['value'])
                        await main_message.edit(embed=new_embed_game_started)
                    insert_json(json_game, "bulls_records")
                BAC_GAMES_DICT.pop(f'{ctx.channel.id}')
            case "replay":
                print("p")


async def setup(bot):
    await bot.add_cog(SmallGames(bot))

from enum import Enum
import random
from typing import Callable
from bot_util import bot_config
from db_data.psql_main import DatabaseFunctions as DF
import discord

# Constants
SUITS = ("<:clubs_out:997942006808588379>", "<:spades_out:997942007987183717>", ":hearts:", ":diamonds:")
PACK = (2, 3, 4, 5, 6, 7, 8, 9, 10, "J", "Q", "K", "A")


class BlackJackEndCodes(Enum):
    ONGOING = -1
    PLAYER_WON = 0
    DEALER_WON = 1
    TIE = 2


class BlackJack:
    @staticmethod
    def draw_card(player: str, card_num: int, game: dict, amount: int = 1):
        """ Draw a card for a player and update their total points """
        card = random.choice(PACK)
        suit = random.choice(SUITS)
        game[player]['cards'].append({'pack': card, 'suit': suit})

        # Calculate points
        points = card if isinstance(card, int) else (
            10 if card != "A" else (1 if game[player]['points_total'] + 11 > 21 else 11))
        if player == "dealer" and card_num == 0:
            game[player]['first_card_points'] = points
        game[player]['points_total'] += points

        if amount > 1:
            for _ in range(amount - 1):
                BlackJack.draw_card(player, 1, game, 1)

    @staticmethod
    def update_game_state(game_dict: dict):
        """ Update game state based on current points """
        player_busted = game_dict['player']['points_total'] > 21
        dealer_busted = game_dict['dealer']['points_total'] > 21

        game_dict['player']['busted'] = player_busted
        game_dict['dealer']['busted'] = dealer_busted
        return player_busted, dealer_busted

    @staticmethod
    def get_game_end_message_and_code(game_dict: dict, gettext: Callable):
        """ Handle game end message
        Returns:
            tuple: (message_end: str, code: BlackJackEndCodes)
        """
        _ = gettext
        player_points: int = game_dict['player']['points_total']
        dealer_points: int = game_dict['dealer']['points_total']
        player_busted: bool = game_dict['player']['busted']
        dealer_busted: bool = game_dict['dealer']['busted']

        message_end = _("Unexpected game outcome")
        code = BlackJackEndCodes.TIE  # Default to TIE in unexpected scenarios

        if player_busted or dealer_busted:
            if player_busted and dealer_busted:
                message_end = _("Both you and Dealer bust. You both received your coins back")
                code = BlackJackEndCodes.TIE
            elif player_busted:
                message_end = _("You bust and lost {amount} coins").format(amount=game_dict['player']['bet'])
                code = BlackJackEndCodes.DEALER_WON
            elif dealer_busted:
                message_end = _("Dealer busts. You received {amount} coins").format(
                    amount=game_dict['player']['bet'] * 2)
                code = BlackJackEndCodes.PLAYER_WON
        else:
            if player_points > dealer_points:
                message_end = _("Dealer has less value than you. You received {amount} coins").format(
                    amount=game_dict['player']['bet'] * 2)
                code = BlackJackEndCodes.PLAYER_WON
            elif player_points == dealer_points:
                message_end = _("It's a tie. You received your coins back")
                code = BlackJackEndCodes.TIE
            else:
                message_end = _("You have less value than dealer, and lost {amount} coins").format(
                    amount=game_dict['player']['bet'])
                code = BlackJackEndCodes.DEALER_WON
        return message_end, code

    @staticmethod
    def process_results(code: BlackJackEndCodes, user_id: int, coins_bet: int):
        match code:
            case BlackJackEndCodes.PLAYER_WON:
                DF.add_coins(user_id, coins_bet * 2)
            case BlackJackEndCodes.TIE:
                DF.add_coins(user_id, coins_bet)

    @staticmethod
    def create_blackjack_embed(game_dict: dict, outcome_message: str | None, gettext: Callable,
                               status_code: BlackJackEndCodes) -> discord.Embed:
        _ = gettext
        color_status_codes = {
            BlackJackEndCodes.PLAYER_WON: discord.Color.from_rgb(90, 255, 255),
            BlackJackEndCodes.DEALER_WON: discord.Color.from_rgb(0, 165, 165),
            BlackJackEndCodes.TIE: discord.Color.from_rgb(108, 128, 128),
            BlackJackEndCodes.ONGOING: bot_config.CustomColors.cyan
        }
        embed = discord.Embed(title=_("Blackjack"), color=color_status_codes[status_code])
        embed.description = _("{nickname} bet **{bet}** coins to play blackjack").format(
            nickname=game_dict['player']['nickname'], bet=game_dict['player']['bet'])

        dealer_first = status_code == BlackJackEndCodes.ONGOING

        # Formatting card display
        player_hand = ' '.join([BlackJack.format_card(card) for card in game_dict['player']['cards']])
        dealer_hand = ' '.join([BlackJack.format_card(card) for card in
                                game_dict['dealer']['cards']]) if not dealer_first else BlackJack.format_card(
            game_dict['dealer']['cards'][0]) + bot_config.CustomEmojis.question_mark

        embed.add_field(name=f"{game_dict['player']['nickname']} [{game_dict['player']['points_total']}]",
                        value=player_hand, inline=True)
        dealer_translation = _('Dealer')
        embed.add_field(
            name=f"{dealer_translation} [{game_dict['dealer']['points_total'] if not dealer_first else str(game_dict['dealer']['first_card_points']) + '+?'}]",
            value=dealer_hand, inline=True)
        embed.set_footer(text=outcome_message)

        return embed

    @staticmethod
    def format_card(card):
        return f"**{card['pack']}**{card['suit']}"

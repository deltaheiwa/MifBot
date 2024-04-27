import chess
import chess.svg
from cairosvg import svg2png
from discord import File
from io import BytesIO
from PIL import Image
import emoji


baseboard_map = {
    "p": "♟",
    "P": "♙",
    "k": "♚",
    "K": "♔",
    "q": "♛",
    "Q": "♕",
    "r": "♜",
    "R": "♖",
    "b": "♝",
    "B": "♗",
    "n": "♞",
    "N": "♘",
}

chess_emojis = {
    "B_0": "<:B_0:1042158166114320394>",
    "B_1": "<:B_1:1042158167456501880>",  # White Bishop
    "N_0": "<:N_0:1042158182874763274>",
    "N_1": "<:N_1:1042158184242086082>",  # White Knight
    "K_0": "<:K_0:1042158176562323577>",
    "K_1": "<:K_1:1042158178479116398>",  # White King
    "P_0": "<:P_0:1042158188956495972>",
    "P_1": "<:P_1:1042158190852317204>",  # White Pawn
    "Q_0": "<:Q_0:1042158195172450354>",
    "Q_1": "<:Q_1:1042158196841779370>",  # White Queen
    "R_0": "<:R_0:1042158201300320296>",
    "R_1": "<:R_1:1042158203053547540>",  # White Rook
    "b_0": "<:b_0:1042158163337695284>",
    "b_1": "<:b_1:1042158164671467530>",  # Black Bishop
    "._0": "<:blank_0:1042158168790282270>",
    "._1": "<:blank_1:1042158172670021673>",  # Blanks
    "k_0": "<:k_0:1042158173987012668>",
    "k_1": "<:k_1:1042158175283056741>",  # Black King
    "n_0": "<:n_0:1042158180081336381>",
    "n_1": "<:n_1:1042158181431906304>",  # Black Knight
    "p_0": "<:p_0:1042158185831743619>",
    "p_1": "<:p_1:1042158187329110037>",  # Black Pawn
    "q_0": "<:q_0:1042158192467124264>",
    "q_1": "<:q_1:1042158193800908840>",  # Black Queen
    "r_0": "<:r_0:1042158198100082709>",
    "r_1": "<:r_1:1042158199823937547>",  # Black Rook
}

board_trans = str.maketrans(
    "".join(baseboard_map.keys()), "".join(baseboard_map.values())
)


def board_to_image(
    board: chess.Board, lastmove: chess.Move = None, check_square: chess.Square = None
):
    with BytesIO() as image_binary:
        board_svg = chess.svg.board(
            board=board,
            size=600,
            lastmove=lastmove,
            check=check_square,
            orientation=chess.WHITE,
        )
        bytes_image = svg2png(bytestring=board_svg, write_to=image_binary)  # IDK why it's here, but the code breaks if I remove. Fuck this
        image_binary.seek(0)
        board_png_image = Image.open(fp=image_binary)
        image_binary.seek(0)
        attachment_board = File(fp=image_binary, filename="board.png")
        return attachment_board, board_png_image


def chess_pieces_visualizer(symbol):
    """
    Takes a piece letter from 'python chess' board, and transposes it into an emoji
    """
    translated = symbol.translate(board_trans)
    rows = translated.split("\n")
    symbol_matrix = []
    for each_row in rows:
        symbols = each_row.split(" ")
        for each in symbols:
            symbol_matrix.append(each)
    color_toggle = True
    insert_point = 8
    for i in range(8):
        symbol_matrix.insert(insert_point * i + i, "\n")
    del symbol_matrix[0]
    for uni in symbol_matrix:
        if uni == ".":
            if color_toggle is True:
                symbol_matrix[symbol_matrix.index(uni)] = "\u25fb"
            else:
                symbol_matrix[symbol_matrix.index(uni)] = "\u25fc"
        color_toggle = not color_toggle
    return "".join(symbol_matrix)


def chess_eval(eval: int, mate=False):
    if eval is None:
        return "None"
    if mate:
        if eval > 0:
            return f"#{eval}"
        else:
            return f"#-{abs(eval)}"
    else:
        if eval > 0:
            return f"+{eval/100:.2f}"
        else:
            return f"{eval/100:.2f}"


def chess_eval_comment(eval: int, mate=False):
    if eval is None:
        return "..."
    
    if mate:
        return "White mates" if eval > 0 else "Black mates"
    
    if eval > 0:
        if 40 < eval <= 110:
            return "White is slightly better"
        if 110 < eval < 500:
            return "White is better"
        if 500 <= eval < 1000:
            return "White is much better"
        if 1000 <= eval < 2000:
            return "White is winning"
        if 2000 <= eval:
            return "White is winning decisively"
        
        return "Position is equal"
    
    if -110 < eval <= -40:
        return "Black is slightly better"
    if -500 < eval <= -110:
        return "Black is better"
    if -1000 < eval <= -500:
        return "Black is much better"
    if -2000 < eval <= -1000:
        return "Black is winning"
    if eval <= -2000:
        return "Black is winning decisively"
    
    return "Position is equal"


def fetch_flair(flair: str):
    flair_tokens = flair.split('.')
    emoji_string = f":{flair_tokens[1].replace('-', '_')}: "
    actual_emoji = emoji.emojize(emoji_string)
    is_valid_emoji = actual_emoji != emoji_string
    if not is_valid_emoji: 
        return ""
    return actual_emoji

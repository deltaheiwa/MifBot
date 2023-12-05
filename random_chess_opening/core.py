import random
from pathlib import Path
import json
from datetime import datetime as dt


current_dir = Path(__file__).resolve().parent

def generate_opening():
    letter_list = ['a', 'b', 'c', 'd', 'e']
    letter = random.choice(letter_list)
    line = random.choice(open(current_dir / "openings" / f"{letter}.tsv").readlines())
    return line

def load_user_to_cache(user_id: int, opening_information: dict):
    with open(current_dir / "cache" / "_.json", "r") as f:
        user_cache = json.load(f)
    
    opening_information["time"] = dt.utcnow().strftime("%d/%m/%Y %H:%M:%S")
    user_cache[str(user_id)] = opening_information

    with open(current_dir / "cache" / "_.json", "w") as f:
        json.dump(user_cache, f, indent=4)

def get_user_from_cache(user_id: int):
    with open(current_dir / "cache" / "_.json", "r") as f:
        user_cache = json.load(f)
    
    return user_cache[str(user_id)] if str(user_id) in user_cache and not (dt.utcnow() - dt.strptime(user_cache[str(user_id)]["time"], "%d/%m/%Y %H:%M:%S")).total_seconds() > 86400 else None

def get_time_left(user_id: int):
    with open(current_dir / "cache" / "_.json", "r") as f:
        user_cache = json.load(f)
    
    return (dt.utcnow() - dt.strptime(user_cache[str(user_id)]["time"], "%d/%m/%Y %H:%M:%S")).total_seconds() if str(user_id) in user_cache else None

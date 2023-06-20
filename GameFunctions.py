from dataclasses import dataclass
from dis import disco
import discord
import random
import asyncio
import json
import enum
from tqdm import tqdm
import math
from discord.ext import commands
from discord.ui import Button
from util.bot_functions import ProgressBar as PB
from util.bot_exceptions import *
import util.bot_config as bot_config
import creds
from typing import Union
from get_sheets import SheetsData
import numpy as np
from db_data import database_main
import logging
import coloredlogs

logger = logging.getLogger(__name__)
coloredlogs.install(level='DEBUG', logger=logger)
logger.setLevel(logging.DEBUG)
formatter = logging.Formatter('%(asctime)s:%(levelname)s --- %(message)s')
file_handler = logging.FileHandler(bot_config.LogFiles.gf_log)
file_handler.setFormatter(formatter)
logger.addHandler(file_handler)

class Rarity(enum.Enum):
    NULL = None
    grey = 1
    white = 2
    green = 3
    blue = 4
    yellow = 5
    orange = 6
    red = 7

    def get_color(self, mode):
        if mode == "embed":
            if self.value == "grey":
                return discord.Color.from_rgb(220, 220, 220)
            elif self.value == "white":
                return discord.Color.from_rgb(255, 255, 255)
            elif self.value == "yellow":
                return discord.Color.yellow()
            elif self.value == "blue":
                return discord.Color.blue()
            elif self.value == "green":
                return discord.Color.green()
            elif self.value == "orange":
                return discord.Color.orange()
            elif self.value == "red":
                return discord.Color.red()
        elif mode == "message": 
            if self.value == "grey":
                return "<:gray_rarity:945418409410166784>"
            elif self.value == "white":
                return ":white_circle:"
            elif self.value == "yellow":
                return ":yellow_circle:"
            elif self.value == "blue":
                return ":blue_circle:"
            elif self.value == "green":
                return ":green_circle:"
            elif self.value == "orange":
                return ":orange_circle:"
            elif self.value == "red":
                return ":red_circle:"
    
# @unique
class ItemType:
    @staticmethod
    def get_id_type_from_inventory_slot(item_type_id: int):
        match item_type_id:
            case 3:
                return "i"
            case 2:
                return "a"
            case 1:
                return "w"
    
    class ElementType:
        class FireElement:
            _name = "FireElement"
            element_id = 1
            emoji = "<:fireEmblem:927711447537049611>"
            extra_damage_rate = {"FireElement": 0, "WaterElement": -0.1, "LifeElement": 0.1, "VoidElement": 0.05, "NeutralElement": 0.2} 
        
        class WaterElement:
            _name = "WaterElement"
            element_id = 2
            emoji = "<:waterEmblem:927711447956463676>"
            extra_damage_rate = {"FireElement": 0.1, "WaterElement": 0, "LifeElement": -0.05, "VoidElement": -0.1, "NeutralElement": 0.1} 
        
        class LifeElement:
            _name = "LifeElement"
            element_id = 3
            emoji = "<:lifeEmblem:927721601464692776>"
            extra_damage_rate = {"FireElement": -0.1, "WaterElement": 0.05, "LifeElement": 0, "VoidElement": 0.1, "NeutralElement": 0.05} 
        
        class VoidElement:
            _name = "VoidElement"
            element_id = 4
            emoji = "<:voidEmblem:927726580275503164>"
            extra_damage_rate = {"FireElement": -0.1, "WaterElement": 0.1, "LifeElement": 0.1, "VoidElement": 0, "NeutralElement": 0.15} 
        
        class NeutralElement:
            _name = "NeutralElement"
            element_id = 5
            emoji = "<:neutralEmblem:927728956680048660>"
            extra_damage_rate = {"FireElement": -0.05, "WaterElement": 0, "LifeElement": 0.05, "VoidElement": -0.05, "NeutralElement": 0} 

    class ElementTypeEnum:
        def __init__(self, ex_num):
            if ex_num in [1, "FireElement"]:
                self._element_class = ItemType.ElementType.FireElement
            elif ex_num in [2, "WaterElement"]:
                self._element_class = ItemType.ElementType.WaterElement
            elif ex_num in [3, "LifeElement"]:
                self._element_class = ItemType.ElementType.LifeElement
            elif ex_num in [4, "VoidElement"]:
                self._element_class = ItemType.ElementType.VoidElement
            elif ex_num in [5, "NeutralElement"]:
                self._element_class = ItemType.ElementType.NeutralElement
            else: raise ValueError("Invalid element type")
        
        def get_emoji(self) -> str:
            return self._element_class.emoji
        


    class WeaponType(enum.Enum):
        NULL = None
        melee = 1
        ranged = 2
        magic = 3

    class GeneralItemType(enum.Enum):
        NULL = None
        rubbish = 1
        raw_material = 2

    class ArmorType(enum.Enum):
        NULL = None
        physical = 1
        holographic = 2
        magic = 3
    
    class EffectType(enum.Enum):
        NULL = None
        lethal = 1
        protective = 2


class StatusEffect:
    def __init__(self, entity, duration=-1, effect_type: ItemType.EffectType=ItemType.EffectType(None), effect_element: ItemType.ElementTypeEnum=None): # if duration is -1, it is permanent
        self.entity = entity
        self.duration = duration
        self.effect_type = effect_type
        self.effect_element = effect_element

class LethalStatusEffects:
    class Burn(StatusEffect):
        def __init__(self, multiplier: float, duration: float, entity, effect_type: ItemType.EffectType=ItemType.EffectType(1), effect_element: ItemType.ElementTypeEnum=ItemType.ElementTypeEnum("FireElement")):
            self._name = "Burn"
            self.multiplier = multiplier
            self.base_damage = 20
            super().__init__(entity, duration=duration, effect_type=effect_type, effect_element=effect_element)
        
        def activate(self):
            self.entity.deal_damage(self)
            self.duration -= 1
            if self.duration == 0:
                self.entity.remove_object(object_to_remove=self)

class Entity:
    '''This class is used to create an entity object. It is used to store all the information about an entity.
    
    Arguments:
        id: The id of the character
        from_database: If the character is being created from the database, this should be set to True. If the character is being created from a dictionary or fully via keywords, this should be set to False.
    
    Keyword arguments:
        name: The name of the character
        description: The description of the character
        damage: The damage of the character
        hp: The health points of the character
        level: The level of the character (default 1, since a character has no proper 'level' until they are created)
        element: The element of the character (look up for ItemType.ElementTypeEnum)
        base_weapon_id: The id of the weapon the character is using
        base_armor_set: The list of ids of the armor the character is using. If no armor is being used, this should be set to [None]
        artefact: The id of the artefact the character is using. If no artefact is being used, this should be set to None
        speed: The speed of the character
        second_action: The second action of the character
        third_action: The third action of the character (Shouldn't be set if the character doesn't have a second action)
        passive_ability: The passive ability of the character (can be infuenced by the artefact)
        special: The special of the character (can be infuenced by the artefact)
        drops: The drops of the character (in the form of a dictionary)
        image: The image of the character (in the form of a blob or emoji string)
    '''
    
    def __init__(self, id: int, info=None, **params):
        self.id: int = id
        self.name: str = params.get("name", info[1])
        self.description: str = params.get("description", info[2])
        self.damage: int = params.get("damage", info[3])
        self.hp: int = params.get("hp", info[4])
        self.total_hp: int = self.hp
        self.level: int = params.get("level", 1)
        self.element: ItemType.ElementTypeEnum = ItemType.ElementTypeEnum(params.get("element", info[5]))
        if params.get("weapon", info[6]) in [None, "NULL"]: self.base_weapon_id = None
        else: self.base_weapon_id: Weapon = Weapon(int(params.get("weapon", info[6])))
        armor_set = params.get("armors", info[7]).split(",")
        if armor_set in [None, "NULL"] or armor_set[0] in [None, "NULL"]: self.base_armor_set: list = [None]
        else: self.base_armor_set: list[Armor] = list(Armor(id=int(armor)) for armor in armor_set)
        if params.get("artefact", info[8]) in [None, "NULL"]: self.artefact = None
        else: self.artefact: Artefact = Artefact(int(params.get("artefact", info[8])))
        self.speed: int = params.get("speed", info[9])
        self.second_action: str = params.get("second_action", info[10])
        self.third_action: str = params.get("third_action", info[11])
        self.passive_ability: str = params.get("passive_ability", info[12])
        self.special_ability: str = params.get("special_ability", info[13])
        self.drops: dict = params.get("drops", info[14])
        self.image = params.get("image", info[15])
        self.status_effects: list[StatusEffect] = []
        self.passive_effects = self.fetch_passives()
        self.armor_element_resistance: dict = self.calculate_armor_element_resistance()
        self.armor_rarity: int = self.define_rarity_armor()
        self.health_bar: PB = PB(self.hp, self.total_hp, length=10, suffix=f'| {math.ceil(self.hp)}/{self.total_hp}')
    
    def armor_points(self):
        points = 0
        if self.base_armor_set[0] is not None:
            for armor in self.base_armor_set:
                points += armor.armor_points
        return points
    
    def define_rarity_armor(self) -> int:
        if self.base_armor_set[0] is None: return 0
        container = [r.rarity.value for r in self.base_armor_set]
        
        return round(np.mean(container))
    
    def calculate_armor_element_resistance (self):
        # One piece of armor would give only 50% of armor_resistance
        # Two pieces of armor would give only 80% of armor_resistance
        # Every piece of armor would give whole 120% of armor_resistance
        
        armor_element_resistance = {"FireElement": [], "WaterElement": [], "LifeElement": [], "VoidElement": [], "NeutralElement": []}
        armor_element_count = {}
        if self.base_armor_set[0] is None: return None
        for armor in self.base_armor_set: 
            if armor.element._element_class._name not in armor_element_count:
                armor_element_count[f"{armor.element._element_class._name}"] = 0
            armor_element_count[f"{armor.element._element_class._name}"] += 1
        for elem_count in armor_element_count:
            match armor_element_count[elem_count]:
                case 1:
                    result = list(map(lambda x: x * 0.5, ItemType.ElementTypeEnum(elem_count)._element_class.extra_damage_rate.values()))
                case 2:
                    result = list(map(lambda x: x * 0.8, ItemType.ElementTypeEnum(elem_count)._element_class.extra_damage_rate.values()))
                case 3:
                    result = list(map(lambda x: x * 1.2, ItemType.ElementTypeEnum(elem_count)._element_class.extra_damage_rate.values()))
            
            for elem in armor_element_resistance:
                armor_element_resistance[elem].append(result[list(armor_element_resistance).index(elem)])
        for elem in armor_element_resistance:
            armor_element_resistance[elem] = round(np.mean(armor_element_resistance[elem]))
            if armor_element_resistance[elem] < 0:
                armor_element_resistance[elem] = 0
        return armor_element_resistance
    
    def fetch_passives(self):
        passives =[]
        if self.base_armor_set[0] is not None:
            for armor in self.base_armor_set:
                if armor.special_ability not in [None, 'NULL']:
                    passives.append(armor.special_ability)
        return passives

    def remove_object(self, object_to_remove=None):
        if object_to_remove is not None:
            if isinstance(object_to_remove, StatusEffect):
                self.status_effects.remove(object_to_remove)

    def deal_damage(self, attacker):
        if self.armor_element_resistance is not None:
            if isinstance(attacker, Union[Enemy, Character]):
                weapon_extra_element_damage = attacker.base_weapon_id.element._element_class.extra_damage_rate
                # self.armor_element_resistance
                if attacker.element._element_class != attacker.base_weapon_id.element._element_class:
                    for element in weapon_extra_element_damage:
                        weapon_extra_element_damage[element] /= 2
                damage_to_deal = (attacker.damage+attacker.base_weapon_id.damage) + \
                    (attacker.base_weapon_id.damage * weapon_extra_element_damage[attacker.base_weapon_id.element._element_class._name]) - \
                    (attacker.base_weapon_id.damage * self.armor_element_resistance[attacker.base_weapon_id.element._element_class._name])
                
                # Do the rarity check
                damage_to_deal = damage_to_deal + (damage_to_deal * ((attacker.base_weapon_id.rarity.value - self.armor_rarity) * 0.02))
                
                for passive in self.passive_effects:
                    if "ranged_lowered_" in passive:
                        if attacker.base_weapon_id.weapon_type == ItemType.WeaponType(2):
                            damage_to_deal /= (100 / int(passive[-2:]))
                
                self.hp -= damage_to_deal
                logger.debug(f"{attacker.name} dealt {damage_to_deal} to {self.name}. HP left: {self.hp}")
            elif isinstance(attacker, StatusEffect):
                if attacker.effect_type == ItemType.EffectType.lethal:
                    status_extra_effects_damage = attacker.effect_element._element_class.extra_damage_rate
                    if type(attacker.base_damage) != type(int):
                        damage_to_deal = (attacker.base_damage*((attacker.multiplier - self.armor_element_resistance[attacker.effect_element._element_class._name])- attacker.multiplier * status_extra_effects_damage[attacker.effect_element._element_class._name]))
                        self.hp -= damage_to_deal
                        logger.debug(f"{attacker._name} ability dealt {damage_to_deal} to {self.name}. HP left: {self.hp}")
            elif isinstance(attacker, int):
                self.hp -= attacker
                logger.debug(f"Custom damage dealt {attacker} to {self.name}. HP left: {self.hp}")


class GameItem:
    @staticmethod
    def fetch_item(item_id: int, item_type: int):
        match item_type:
            case 1:
                return Weapon(item_id)
            case 2:
                return Armor(item_id)
            case 3:
                return database_main.GameDb.get_gen_item("id", item_id)
            case 4:
                return Artefact(item_id)
    
    @staticmethod
    def get_emoji(item_emoji):
        if item_emoji == "-" or item_emoji == "":
            emoji = "<:Question_Mark_fixed:944588141405282335>"
        else:
            emoji = item_emoji
        return emoji
    

@dataclass
class Enemy(Entity):
    '''This class is used to create an enemy object. It is used to store all the information about an enemy. It inherits from the Entity class.'''
    def __init__(self, id, from_database: bool=True, **params):
        if from_database is True:
            info = database_main.GameDb.get_enemy("id", id)
        else: info = [None for _ in range(16)]
        super().__init__(id, info=info, **params)
    
    def __str__(self):
        return self.name
    

@dataclass
class Character(Entity):
    '''This class is used to create a character object. It is used to store all the information about a character. It inherits from the Entity class.'''
    def __init__(self, id, from_database: bool=True, **params):
        if from_database is True:
            info = database_main.GameDb.get_character("id", id)
        else: info = [None for _ in range(16)]
        super().__init__(id, info=info, **params)
    
    def __str__(self):
        return self.name

@dataclass
class Weapon:
    def __init__(self, id, from_database: bool=True, **params):
        self.id: int = id
        if from_database is True:
            info = database_main.GameDb.get_weapon("id", self.id)
        else: info = [None for _ in range(15)]
        self.name: str = params.get("name", info[1])
        self.description: str = params.get("description", info[2])
        self.damage: int = params.get("damage", info[3])
        self.second_attack: str = params.get("second_attack", info[4])
        self.special_ability: str = params.get("special_ability", info[5])
        self.element: ItemType.ElementTypeEnum = ItemType.ElementTypeEnum(params.get("element", info[6]))
        self.rarity: Rarity = Rarity(params.get("rarity", info[7]))
        self.weapon_type: ItemType.WeaponType = ItemType.WeaponType(params.get("weapon_type", info[8]))
        self.value: int = params.get("value", info[9])
        self.craft: str = params.get("craft", info[10])
        self.drops: str = params.get("drops", info[11])
        self.image = params.get("image", info[12])
        self.crit_chance: int = params.get("crit_chance", info[13])
    

@dataclass
class Armor:
    def __init__(self, id: int, from_database: bool = True, **params):
        self.id: int = id
        if from_database is True:
            info = database_main.GameDb.get_armor("id", self.id)
        else: info = [None for _ in range(15)]
        self.name: str = params.get("name", info[1])
        self.description: str = params.get("description", info[2])
        self.armor_points: int = params.get("armor_points", info[3])
        self.armor_resistance: int = params.get("armor_resistance", info[4])
        self.armor_type: ItemType.ArmorType = ItemType.ArmorType(params.get("armor_type", info[5]))
        self.special_ability: str = params.get("special_ability", info[6])
        self.element: ItemType.ElementTypeEnum = ItemType.ElementTypeEnum(params.get("element", info[7]))
        self.rarity: Rarity = Rarity(params.get("rarity", info[8]))
        set_bonus_info = params.get("set_bonus", info[9])
        if set_bonus_info is None: set_bonus_info = "- -"
        set_bonus_info.split(" ")
        self.set: list = set_bonus_info[0].split(",")
        self.set_bonus: str = set_bonus_info[-1]
        self.value = params.get("value", info[10])
        self.craft: str = params.get("craft", info[11])
        self.drops:str = params.get("drops", info[12])
        self.image:str = params.get("image", info[13])

@dataclass
class Artefact:
    def __init__(self, id: int, from_database: bool=True, **params):
        self.id: int = id
        if from_database is True:
            info = database_main.GameDb.get_artefact("id", self.id)
        else: info = [None for _ in range(13)]
        self.name: str = params.get("name", info[1])
        self.description: str = params.get("description", info[2])
        self.passive_effect: str = params.get("passive_effect", info[3])
        self.active_effect: str = params.get("active_effect", info[4])
        self.synergy: str = params.get("synergy", info[5])
        self.element: ItemType.ElementTypeEnum = ItemType.ElementTypeEnum(params.get("element", info[6]))
        self.rarity: Rarity = Rarity(params.get("rarity", info[7]))
        self.value: int = params.get("value", info[8])
        self.craft: str = params.get("craft", info[9])
        self.drops: str = params.get("drops", info[10])
        self.image: str = params.get("image", info[11])

class GameManager:
    def __init__(self, active_characters=None, **kwargs):
        self.enemy_ids: list = kwargs.get("enemy_ids", [])
        self.enemies: list[Enemy] = self.entity_spawner(self.enemy_ids)
        self.active_characters: list = active_characters
        if self.active_characters is None or type(self.active_characters) != list: raise BattleMissingArgumentsError(self.active_characters, "active_characters")
        self.characters: list[Character] = self.entity_spawner(self.active_characters, entity_enemy=False)

    def entity_spawner(self, ids_of_entities: list, entity_enemy: bool=True):
        entity_list = []
        for entity in ids_of_entities:
            if entity_enemy is True:
                entity_list.append(Enemy(int(entity)))
            else:
                entity_list.append(Character(int(entity['char_id']), name=entity["name"], level=entity['level'], base_weapon_id=entity['weapon'], base_armor_set=entity['armor_ids'], artefact=entity['artefact_id']))
        return entity_list
    
    def start_battle(self):
        PreTurn(self)

class PreTurn:
    def __init__(self, battle_object: GameManager):
        self.battle_object = battle_object
        self.status_effects()
    
    # status effects
    def status_effects(self):
        for entity in self.battle_object.enemies:
            if entity.status_effects is not []:
                for effect in entity.status_effects:
                    effect.activate()
    

def get_coins(value):
    if value/10000 >= 1:
        mcoins = f"{math.floor(value/10000)}**M**"
        if value/10000 - math.floor(value/10000) != 0:
            wcoins_value = math.floor((value/10000 - math.floor(value/10000))*100)
            wcoins = f" {wcoins_value}**W**"
            if wcoins_value/100 - math.floor(wcoins_value/100) != 0:
                fcoins = f" {round((value/100 - math.floor(value/100))*100)}**F**"
            else:
                fcoins = ""
        else:
            fcoins = ""
            wcoins = ""
    else:
        if value/100 >= 1:
            mcoins=""
            wcoins = f"{math.floor(value/100)}**W**"
            if value/100 - math.floor(value/100) != 0:
                fcoins = f" {round((value/100 - math.floor(value/100))*100)}**F**"
            else:
                fcoins = ""
        else:
            if value/100 < 1:
                mcoins=""
                wcoins=""
                fcoins = f"{value}**F**"
            else:
                mcoins = ""
                fcoins = ""
                wcoins = ""
    if mcoins+wcoins+fcoins == "": return "No value"
    else: return mcoins+wcoins+fcoins

def weapon_special_ability(ability_code, damage):
    ability_info = {}
    if ability_code == "fire_effect":
        ability_info['name'] = "Sets on fire"
        ability_info['description'] = (f"Sets an enemy on fire with a 65% chance with each attack. Lasts 2 turns. Deals **{round(int(damage)/100*20)}** damage each turn")
    elif ability_code == "-" or ability_code == "":
        ability_info['name'] = "No special ability"
        ability_info['description'] = "This weapon has no special ability"
    
    return ability_info

def armor_special_ability(ability_code, armor_points):
    ability_info = {}
    if ability_code == "-" or ability_code == "":
        ability_info['name'] = "No special ability"
        ability_info['description'] = "This armor has no special ability"
    elif ability_code == "ranged_lowered_50":
        ability_info['name'] = "Received ranged damage lowered"
        ability_info['description'] = "Reduces damage taken from ranged weapons by 50%"
    
    return ability_info

def weapon_second_attack(attack):
    attack_info = {}
    if attack == "-" or attack == "":
        attack_info['name'] = "No second attack"
        attack_info['description'] = "This weapon has no second attack"
    
    return attack_info

def armor_set_bonus(set_code, armor_ids, mode):
    set_bonus_info = {}
    armors = ""
    for each_id in armor_ids:
        armors += f"`a_{each_id}` "
    if mode == "display":
        if set_code == "-" or set_code == "":
            set_bonus_info['name'] = "No set bonus"
            set_bonus_info['description'] = "This piece of armor has no set bonus, all you get for wearing full set - extra `Armor Points`"
            set_bonus_info['armors'] = armors
        else:
            if set_code == "open_space_air":
                set_bonus_info["name"] = "Ability to breathe in outer space"
                set_bonus_info["description"] = "Your character won't receive damage in outer space"
                set_bonus_info['armors'] = armors
    
    return set_bonus_info



# def get_obtanation(craft, drop):
#     obtanation = {}
#     if craft == "-" or craft == "":
#         obtanation['craft'] = "Not craftable"
#     else:
#         craft_string = ""
#         craft = craft.split(', ')
#         for i in range(0, len(craft)):
#             if i == len(craft): break
#             quantity = craft[i].split("*")
#             item = quantity[0].split("_")
#             item_info = fetch_item(convert_type(item[0]), int(item[1]))
#             item_emoji = get_emoji(item_info[0])
#             try:
#                 quantity = quantity[1]
#             except Exception:
#                 quantity.append(1)
#             craft_string += f"`{quantity[0]}`{item_emoji}** x{quantity[1]}**  "
#         obtanation['craft'] = craft_string
    
#     if drop == "-" or drop == "":
#         obtanation['drop'] = "Cannot be obtained from enemies nor found"
#     else:
#         drop_string = ""
#         drop = drop.split(', ')
#         for i in range(0, len(drop)):
#             if i == len(drop):
#                 break
#             source = drop[i].split("_")
#             if source[0] == 'e':
#                 source_info = fetch_char(source[0], int(source[1]))
#             drop_string += f"`{drop[i]}` - {source_info[0]}\n"
#         obtanation['drop'] = drop_string
    
#     return obtanation

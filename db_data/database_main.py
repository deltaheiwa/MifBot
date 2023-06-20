import logging
from pathlib import Path
import sqlite3
from util.bot_functions import CustomFormatter
import coloredlogs
import util.bot_config as bot_config
import GameFunctions as GF

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
formatter = logging.Formatter('%(asctime)s:%(levelname)s --- %(message)s')
console_formatter = CustomFormatter()
stream_handler = logging.StreamHandler()
coloredlogs.install(level='DEBUG', logger=logger)
file_handler_debug = logging.FileHandler(bot_config.LogFiles.database_main_log)
file_handler_debug.setFormatter(formatter)
stream_handler.setFormatter(console_formatter)
logger.addHandler(file_handler_debug)


class Databases:
    prefixes = Path('db_data/databases', 'prefixes.db')
    game = Path('db_data/databases', 'game.db')

class PrefixDatabase:
    @staticmethod
    async def new_prefix(guild_id, prefix):
        with sqlite3.connect(Databases.prefixes) as conn:
            c = conn.cursor()
            if prefix is None:
                c.execute(f"DELETE FROM prefixes WHERE guild_id = {guild_id};")
                conn.commit()
                return
            c.execute(f'''SELECT * FROM prefixes WHERE guild_id = {guild_id};''')
            prefix_data = c.fetchone()
            if prefix_data is None:
                c.execute(f"INSERT INTO prefixes (guild_id, prefix) VALUES ({guild_id}, '{prefix}');")
                conn.commit()
            else:
                c.execute(f"UPDATE prefixes SET prefix = '{prefix}' WHERE guild_id = {guild_id};")
                conn.commit()

    @staticmethod
    async def remove_prefix(guild_id):
        with sqlite3.connect(Databases.prefixes) as conn:
            c = conn.cursor()
            c.execute(f"DELETE FROM prefixes WHERE guild_id = {guild_id};")
            conn.commit()

    @staticmethod
    async def return_prefix(_id, user=False):
        with sqlite3.connect(Databases.prefixes) as conn:
            c = conn.cursor()
            c.execute(f'''SELECT prefix FROM prefixes WHERE guild_id = {_id};''')
            prefix = c.fetchone()
            if prefix is None and user is False:
                c.execute(f"INSERT INTO prefixes (guild_id, prefix) VALUES ({_id}, '.');")
                conn.commit()
                return '.'
            else: return prefix[0] if prefix is not None else None

class GameDb:
    @staticmethod
    def drop_table(table:str):
        with sqlite3.connect(Databases.game) as conn:
            c = conn.cursor()
            c.execute(f"DROP TABLE IF EXISTS {table};")
        logger.info(f"Dropping {table} table")
    
    @staticmethod
    def initiate_db():
        with sqlite3.connect(Databases.game) as conn:
            c = conn.cursor()
            c.execute(f'''CREATE TABLE IF NOT EXISTS weapons (id integer PRIMARY KEY,
                    name text NOT NULL,
                    description text NOT NULL,
                    damage integer NOT NULL,
                    second_attack text,
                    special_ability text,
                    element integer NOT NULL,
                    rarity integer NOT NULL,
                    weapon_type integer NOT NULL,
                    value integer NOT NULL,
                    craft text,
                    drops text,
                    image blob,
                    crit_chance text NOT NULL);''')
            c.execute(f'''CREATE TABLE IF NOT EXISTS armors (id integer PRIMARY KEY,
                    name text NOT NULL,
                    description text NOT NULL,
                    armor_points integer NOT NULL,
                    armor_resistance integer NOT NULL,
                    armor_type integer NOT NULL,
                    special_ability text,
                    element integer NOT NULL,
                    rarity integer NOT NULL,
                    set_bonus text,
                    value integer NOT NULL,
                    craft text,
                    drops text,
                    image blob);''')
            c.execute(f'''CREATE TABLE IF NOT EXISTS enemies (id integer PRIMARY KEY,
                    name text NOT NULL,
                    description text NOT NULL,
                    damage integer NOT NULL,
                    hp integer NOT NULL,
                    element integer NOT NULL,
                    weapon text,
                    armor text,
                    artefact text,
                    speed integer NOT NULL,
                    second_action text,
                    third_action text,
                    passive_ability text,
                    special_ability text,
                    drops text,
                    image blob);''')
            c.execute(f'''CREATE TABLE IF NOT EXISTS characters (id integer PRIMARY KEY,
                    name text NOT NULL,
                    description text NOT NULL,
                    damage integer NOT NULL,
                    hp integer NOT NULL,
                    element integer NOT NULL,
                    weapon text,
                    armor text,
                    artefact text,
                    speed integer NOT NULL,
                    second_action text,
                    third_action text,
                    passive_ability text,
                    special_ability text,
                    craft text,
                    drops text,
                    image blob);''')
            c.execute(f'''CREATE TABLE IF NOT EXISTS general_items (id integer PRIMARY KEY,
                    name text NOT NULL,
                    description text NOT NULL,
                    item_type interger NOT NULL,
                    value integer NOT NULL,
                    rarity integer NOT NULL,
                    crafted_by text,
                    craft text,
                    crafted_on text,
                    drops text,
                    image blob,
                    max_stock integer NOT NULL);''')
            c.execute(f'''CREATE TABLE IF NOT EXISTS artefacts (id integer PRIMARY KEY,
                    name text NOT NULL,
                    description text NOT NULL,
                    passive_effect text,
                    active_effect text,
                    synergy text,
                    element integer NOT NULL,
                    rarity integer NOT NULL,
                    value integer NOT NULL,
                    craft text,
                    drops text,
                    image blob);''')
        logger.info("Initiated 'game' database")
        
    
    @staticmethod
    def add_weapon(weapon_dict: GF.Weapon):
        '''Inserts a new weapon into the database

        Args:
            weapon_dict (GF.Weapon): Weapon object from GameFunctions
        '''
        assert type(weapon_dict) == GF.Weapon, f"No weapon object provided. Got: {weapon_dict}"
        
        with sqlite3.connect(Databases.game) as conn:
            c = conn.cursor()
            insert_query = f'''INSERT INTO weapons VALUES ({weapon_dict.id}, '{weapon_dict.name}', '{weapon_dict.description}', {weapon_dict.damage}, '{weapon_dict.second_attack}', '{weapon_dict.special_ability}', {weapon_dict.element._element_class._name}, {weapon_dict.rarity.value}, {weapon_dict.weapon_type.value}, {weapon_dict.value}, {weapon_dict.craft}, {weapon_dict.drops}, {weapon_dict.image}, {weapon_dict.crit_chance});'''
            print(insert_query)
            c.execute(insert_query)
            conn.commit()
            logger.info(f"Inserted {weapon_dict.name} weapon into Database")
    
    @staticmethod
    def get_weapon(where_clause: str, value):
        assert where_clause and type(value) is int, "Not enought data given to search"
        
        with sqlite3.connect(Databases.game) as conn:
            c = conn.cursor()
            select_query = f"SELECT * FROM weapons WHERE {where_clause} = {value};"
            c.execute(select_query)
            return c.fetchone()
    
    @staticmethod
    def get_armor(where_clause: str, value):
        assert where_clause and type(value) is int, "Not enought data given to search"
        
        with sqlite3.connect(Databases.game) as conn:
            c = conn.cursor()
            select_query = f"SELECT * FROM armors WHERE {where_clause} = {value};"
            c.execute(select_query)
            return c.fetchone()
    
    @staticmethod
    def get_gen_item(where_clause: str, value):
        assert where_clause and type(value) is int, "Not enought data given to search"
        
        with sqlite3.connect(Databases.game) as conn:
            c = conn.cursor()
            select_query = f"SELECT * FROM general_items WHERE {where_clause} = {value};"
            c.execute(select_query)
            return c.fetchone()
    
    @staticmethod
    def get_enemy(where_clause: str, value):
        assert where_clause and type(value) is int, "Not enought data given to search"
        
        with sqlite3.connect(Databases.game) as conn:
            c = conn.cursor()
            select_query = f"SELECT * FROM enemies WHERE {where_clause} = {value};"
            c.execute(select_query)
            return c.fetchone()
    
    @staticmethod
    def get_character(where_clause: str, value):
        assert where_clause and type(value) is int, "Not enought data given to search"
        
        with sqlite3.connect(Databases.game) as conn:
            c = conn.cursor()
            select_query = f"SELECT * FROM characters WHERE {where_clause} = {value};"
            c.execute(select_query)
            return c.fetchone()
    
    @staticmethod
    def get_artefact(where_clause: str, value):
        assert where_clause and type(value) is int, "Not enought data given to search"
        
        with sqlite3.connect(Databases.game) as conn:
            c = conn.cursor()
            select_query = f"SELECT * FROM artefacts WHERE {where_clause} = {value};"
            c.execute(select_query)
            return c.fetchone()

'''
def main():
    # conn = sqlite3.connect(':memory:')
    # Connect to database
    conn = sqlite3.connect(self.prefixes)
    # Create a cursor
    c = conn.cursor()

    # c.execute("DROP TABLE IF EXISTS players")

    # Create a table
    c.execute(CREATE TABLE IF NOT EXISTS prefixes (
        guild_id integer PRIMARY KEY,
        prefix text
        ))
    
    # Datatypes:
    # NULL
    # INTEGER
    # REAL
    # TEXT
    # BLOB

    # c.execute("INSERT INTO players VALUES (123456789, 'someDan')")

    # Query
    # c.execute(SELECT * FROM prefixes)
    # c.fetchone()
    # c.fetchmany(3)
    # c.fetchall()

    # Update
    # c.execute(fUPDATE prefixes SET prefix = {prefix} WHERE guild_id = {guild_id})

    # Commit our command
    conn.commit()

    # Close our connection
    conn.close()
'''


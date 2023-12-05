import datetime
import json
import os
import re
import builtins
from typing import Any, Union
import sqlalchemy as sa
from sqlalchemy.ext import declarative
from sqlalchemy.orm import Mapped, sessionmaker, relationship, joinedload
from dotenv import load_dotenv
import logging
import coloredlogs
from datetime import datetime as datetime_
import bot_util.bot_config as b_cfg
from db_data.mysql_tables import *


logger = logging.getLogger(__name__)
coloredlogs.install(level='INFO', logger=logger)
logger.setLevel(logging.INFO)
formatter = logging.Formatter('%(asctime)s:%(levelname)s --- %(message)s')
file_handler = logging.FileHandler(b_cfg.LogFiles.database_main_log)
file_handler.setFormatter(formatter)
logger.addHandler(file_handler)

load_dotenv('creds/.env')

class MySQLConnector:
    engine_db: sa.engine.Engine
    Session: sessionmaker
    connected: bool
    
    @classmethod
    def connect_to_local_db(cls): # ! In case of connection error, it will connect to local database. For testing purposes, shouldn't be in production
        logger.info("Connecting to local SQLite database")
        db_path = os.path.join(os.path.dirname(os.path.realpath(__file__)), "databases/local_mif.db")
        cls.engine_db = sa.create_engine(f"sqlite:///{db_path}")
        cls.Session = sessionmaker(bind=cls.engine_db)
        cls.connected = True

    @classmethod
    def engine_creation(cls):
        '''
        Creates engine for database connection
        '''
        try:
            if b_cfg.launch_variables['local_db']:
                cls.connect_to_local_db()
            else:
                cls.engine_db = sa.create_engine(f"mysql+pymysql://{os.getenv('HOST_USER')}:{os.getenv('HOST_PASSWORD')}@{os.getenv('HOST_IP')}:3306/mif")
                logger.info("Connection succeded for 'mif'")
                cls.Session = sessionmaker(bind=cls.engine_db)
                cls.connected = True
        except Exception as e:
            logger.exception("Connection refused for 'mif'")
            cls.connected = False
        
        if not cls.connected: # ! Scrape
            cls.connect_to_local_db()


class DatabaseFunctions(MySQLConnector):
    @classmethod
    def on_login(cls, id) -> None:
        '''
        Updates is_logged parameter to True
        '''
        try:
            session = cls.Session()
            session.query(Users).filter(Users.id == id).update({Users.is_logged: True})
            session.commit()
            logger.info(f"User with id {id} logged in")
        except Exception as e:
            logger.exception(f"Error while logging in user with id {id}")
        finally:
            session.close()

    @classmethod
    def create_tables(cls):
        try:
            session = cls.Session()
            Base.metadata.create_all(cls.engine_db)
            logger.info("Tables created")
        except Exception as e:
            logger.exception("Error while creating tables")
        finally:
            session.close()

    @classmethod
    def cache_check(cls, what_to_search: str, type_of_search: str, name: str) -> bool:
        '''
        Returns True or False based on if data exists in cache or no
        \nwhat_to_search: user, clan, clan_members
        \ntype_of_search - by the name of the column
        '''
        try:
            session = cls.Session()
            match what_to_search:
                case "user":
                    column_map = {"id": Wov_players.id, "personal_message": Wov_players.personal_message, "username": Wov_players.username, "previous_username": Wov_players.previous_username}
                    column = column_map[type_of_search]
                    info = session.query(Wov_players.id).filter(column.like(f"{name}%")).first()
                case "clan":
                    column_map = {"id": Wov_clans.id, "name": Wov_clans.name, "connected": Wov_clans.connected, "description": Wov_clans.description}
                    column = column_map[type_of_search]
                    info = session.query(Wov_clans.id).filter(column == name).first()
                case "clan_members": info = session.query(Wov_clans.members).filter(Wov_clans.id == name).first()
                case _: raise AttributeError("Unknown table name. Supported: user, clan, clan_members")
            
            if info is None or info[0] is None:
                return False
            else:
                return True
        except Exception as e:
            logger.exception(f"Error while checking cache for {what_to_search} with {type_of_search} = {name}")
        finally:
            session.close()
    
    @classmethod
    def json_caching(cls, cache_type, json_data, extra_data=None):
        '''
        Accepts json data from Wolvesville API, to update the cache
        \ncache_type: user, clan, clan_members
        '''
        try:
            session = cls.Session()
            if cache_type == "user":
                cache_file = json_data
                time_cached = datetimefix.utcnow()
                iso = time_cached.isoformat() + "Z"
                cache_file['caching_data'] = {'time_cached': iso}
                
                # SELECT id, username, previous_username FROM wov_players WHERE id = '{json_data['id']}'
                info = session.query(Wov_players.id, Wov_players.username, Wov_players.previous_username).filter(Wov_players.id == json_data['id']).first()
                
                # Process status message of the user 
                try:
                    if json_data['personalMessage'] == '':
                        bio = "*No personal message found*"
                    else: bio = json_data['personalMessage']
                except KeyError:
                    bio = "*No personal message found*"
                bio = re.sub('"', '\\"', bio)
                
                if info is not None:
                    prev_username = info['username'] if info['username'] != json_data['username'] else info['previous_username'] # Might break. Needs to be tested.
                    session.query(Wov_players).filter(Wov_players.id == json_data['id']).update({Wov_players.username: json_data['username'], Wov_players.json_data: cache_file, Wov_players.previous_username: prev_username, Wov_players.personal_message: bio}) 
                    session.commit()
                    logger.info("Updated cache file for player. ID - %s", json_data['id'])
                else:
                    session.add(Wov_players(id=json_data['id'], username=json_data['username'], personal_message=bio, json_data=cache_file, previous_username=None))
                    session.commit()
                    logger.info("Inserted cache file for player. ID - %s", json_data['id'])
            elif cache_type == "clan":
                cache_file = {}
                cache_file[json_data['id']] = json_data
                clan_description = re.sub('"', '\\"', json_data['description'])
                cache_file[json_data['id']].pop('description')
                time_cached = datetimefix.utcnow()
                iso = time_cached.isoformat() + "Z"
                cache_file[json_data['id']]['caching_data'] = {'time_cached': iso}
                info = session.query(Wov_clans.id, Wov_clans.name).filter(Wov_clans.id == json_data['id']).first()
                
                if info is not None:
                    # UPDATE wov_clans SET name = '{json_data['name']}', json_data = '{cache_file}', description = '{clan_description}' WHERE id = '{json_data['id']}';
                    session.query(Wov_clans).filter(Wov_clans.id == json_data['id']).update({Wov_clans.name: json_data['name'], Wov_clans.json_data: cache_file, Wov_clans.description: clan_description})
                    session.commit()
                    logger.info("Updated cache file for clan. ID - %s", json_data['id'])
                else:
                    # INSERT INTO wov_clans (id, name, json_data, description) VALUES ('{json_data['id']}', '{json_data['name']}', '{json_cache_file}', "{clan_description}");
                    session.add(Wov_clans(id=json_data['id'], name=json_data['name'], json_data=cache_file, description=clan_description))
                    session.commit()
                    logger.info("Inserted cache file for clan. ID - %s", json_data['id'])
            elif cache_type == "clan_members":
                session.query(Wov_clans).filter(Wov_clans.id == extra_data).update({Wov_clans.members: json_data})
                session.commit()
                logger.info("Updated clan members for clan. ID - %s", extra_data)
        except Exception as e:
            logger.exception(f"Error while caching {cache_type} data")
        finally:
            session.close()
    
    @classmethod
    def on_new_player(cls, member_id: int, info: dict):
        ''' Insert new player into the database

        Args:
            member_id (int): ID of the player
            info (dict): Information about the player. Should contain: login, password, nickname.
        '''        
        stat_dict = {
            "botUsage": {
                "commandsUsed": 0,
                "ngWins": {
                    "easy": 0,
                    "medium": 0,
                    "hard": 0
                },
                "hangman": {
                    "short": {
                        "wins": 0,
                        "losses": 0
                    },
                    "long": {
                        "wins": 0,
                        "losses": 0
                    }
                },
                "bulls": {
                    "word": {
                        "wins": 0,
                        "losses": 0
                    },
                    "number": {
                        "wins": 0,
                        "losses": 0
                    },
                    "pfb": {
                        "fast": {
                            "wins": 0,
                            "losses": 0,
                            "abandoned": 0
                        },
                        "classic": {
                            "wins": 0,
                            "losses": 0,
                            "abandoned": 0
                        },
                        "hard": {
                            "wins": 0,
                            "losses": 0,
                            "abandoned": 0
                        },
                        "long": {
                            "wins": 0,
                            "losses": 0,
                            "abandoned": 0
                        }
                    }
                },
                "dailyInfo": {
                    "dailyCount": 0,
                    "lastDailyTime": None
                }
            }
        }
        
        preferences_dict = {
            "language": "en",
            "prefix": None,
            "publicStats": True,
        }
        
        try:
            session = cls.Session()
            session.add(Users(id=member_id, login=info['login'], password=info['password'], nickname=info['nickname'], is_logged=True, atc=True, time_created=datetimefix.utcnow()))
            logger.info(f"Inserted {member_id} into 'users' table")
            session.add(User_data(user_id=member_id, cash=50, level=1, xp=0, max_xp=100, bg=0, json_stats=stat_dict, preferences=preferences_dict))
            logger.info(f"Inserted {member_id} into 'user_data' table")
            session.commit()
        except Exception as e:
            logger.exception("Error while inserting new player into the database")
        finally:
            session.close()
    
    @classmethod
    def insert_json(cls, json_to_insrt: dict, table: str):
        ''' Insert json data into the database

        Args:
            json_to_insrt (dict): Json data to insert
            table (str): Table to insert into
        '''
        try:
            session = cls.Session()
            if table == "bulls_records":
                players:dict[str, Union[int,str,None]] = {"player1": None, "player2": None, "player3": None, "player4": None}
                for player_num in json_to_insrt["meta"]["players"]:
                    u_id = json_to_insrt["meta"]["players"][player_num]["user_id"]
                    players[player_num] = int(u_id)
                state = json_to_insrt["meta"]["state"].split(" ")
                player_won = int(state[1])
                json_to_insrt['meta']['duration'] = json_to_insrt['meta']['duration'].total_seconds()
                session.add(Bulls_records(user_1=players['player1'], user_2=players['player2'], user_3=players['player3'], user_4=players['player4'], player_won=player_won, t1=datetime_.strptime(json_to_insrt['meta']['datetime_started'], '%Y-%m-%dT%H:%M:%S.%fZ'), json_game=json_to_insrt))
                session.commit()
                logger.info("Inserted bulls game into the database")
        except Exception as e:
            logger.exception("Error while inserting json into the database")
        finally:
            session.close()
    
    @classmethod
    def on_logout(cls, member_id: int):
        '''
        Updates is_logged parameter to False
        '''
        try:
            session = cls.Session()
            session.query(Users).filter(Users.id == member_id).update({Users.is_logged: False})
            session.commit()
            logger.info(f"User {member_id} logged out")
        except Exception as e:
            logger.exception("Error while logging out user")
        finally:
            session.close()
    
    @classmethod
    def on_nickname_change(cls, member_id: int, nickname: str):
        ''' Changes user's nickname in the database

        Args:
            member_id (int): Id of a discord member
            nickname (str): String to change nickname to
        '''
        try:
            session = cls.Session()
            session.query(Users).filter(Users.id == member_id).update({Users.nickname: nickname})
            session.commit()
            logger.info(f"User {member_id} changed nickname to {nickname}")
        except Exception as e:
            logger.exception("Error while changing nickname")
        finally:
            session.close()
    
    @classmethod
    def check_exists(cls, member_id) -> bool:
        '''
        Checks if member exists by it's id. Takes member's id to search. For example 'ctx.author.id'
        '''
        try:
            session = cls.Session()
            check = session.query(Users.id).filter(Users.id == member_id).first()
            if check is None:
                return False
            else: return True
        except Exception as e:
            logger.exception("Error while checking if user exists")
            return False
        finally:
            session.close()
    
    @classmethod
    def check_logged(cls, member_id: int) -> bool:
        ''' 
        Checks if user is logged in the database. Takes discord member's id to search. For example 'ctx.author.id'
        '''
        try:
            session = cls.Session()
            check = session.query(Users.is_logged).filter(Users.id == member_id).first()
            if check is not None and check['is_logged'] in [True, 1]:
                return True
            return False
        except Exception as e:
            logger.exception("Error while checking if user is logged")
            return False
        finally:
            session.close()

    @classmethod
    def local_checks(cls, user_ID):
        ''' Shortcut for checking if user exists and is logged in the database at the same time'''
        if cls.check_exists(user_ID) and cls.check_logged(user_ID): return True
        else: return False
    
    @classmethod
    def check_login(cls, login: str) -> Union[bool, None]:
        ''' Checks if login exists in the database. Returns True if exists, False if doesn't exist and None if error occured

        Args:
            login (str): A string to check

        Returns:
            Union[bool, None]: True if exists, False if doesn't exist and None if error occured
        '''
        try:
            session = cls.Session()
            check = session.query(Users.login).filter(Users.login == login).first()
            if check is None:
                logger.debug(f"Login {login} doesn't exist in the database. Returns False")
                return False
            else:
                logger.debug(f"Login {login} exists in the database. Returns True")
                return True
        except Exception as e:
            logger.exception("Error while checking if login exists")
            return None
        finally:
            session.close()
    
    @classmethod
    def get_user_by_login(cls, login: str) -> Union[dict[str, Any], bool]:
        ''' Returns data from the users table by user's login. If user doesn't exist, returns False

        Args:
            login (str): Login of the user to get data from.

        Returns:
            Union[dict[str, Any], bool]: Dictionary with data from the users table. If user doesn't exist, returns False
        '''
        try:
            session = cls.Session()
            info = session.query(Users).filter(Users.login == login).first()
            return False if info is None else info.__dict__
        except Exception as e:
            logger.exception("Error while getting user by login")
            return False
        finally:
            session.close()
    
    @classmethod
    def get_user_by_id(cls, member_id: int, INFO_NEEDED: list[str]) -> dict[str, Any] | None:
        ''' Returns data from the users table's columns specified in INFO_NEEDED list, by user's id. If user doesn't exist, returns None

        Args:
            member_id (int): Id of the user to get data from.
            INFO_NEEDED (list[str]): List of columns to get data from.

        Returns:
            dict[str, Any] | None: Dictionary with data from the columns specified in INFO_NEEDED list. If user doesn't exist, returns None.
        '''
        try:
            session = cls.Session()
            with session.begin():
                query = session.query(*[getattr(Users, attr) for attr in INFO_NEEDED]).filter_by(id=member_id).first()
                information = query._asdict() if query else None
                logger.info(f"Got user {member_id} from the database")
                return information
        except Exception as e:
            logger.exception("Error while getting user by id")
            return None
        finally:
            session.close()
    
    @classmethod
    def get_userdata_by_id(cls, member_id: int, INFO_NEEDED: list[str]) -> dict[str, int] | None:
        ''' Returns data from the user_data table's columns specified in INFO_NEEDED list, by user's id. If user doesn't exist, returns None.

        Args:
            member_id (int): Id of the user to get data from.
            INFO_NEEDED (list[str]): List of columns to fetch from the database.

        Returns:
            dict[str, int] | None: Dictionary with keys from INFO_NEEDED and values from the database. If user doesn't exist, returns None.
        '''
        try:
            session = cls.Session()
            with session.begin():
                query = session.query(*[getattr(User_data, attr) for attr in INFO_NEEDED]).filter_by(user_id=member_id).first()
                information = query._asdict() if query else None
                logger.info(f"Got userdata {member_id} from the database")
                return information
        except Exception as e:
            logger.exception("Error while getting userdata by id")
            return None
        finally:
            session.close()
    
    @classmethod
    def get_bac_records(cls, member_id:int, game_id: Union[int, None]=None, **kwargs):
        '''
    This function takes two parameters, a required `id` and an optional `game_id`. It can also take additional keyword arguments. 

    It connects to the database and then either fetches the records for the given `id` or the record specified by `game_id` if it is set. 

    Finally, it returns a dictionary with the relevant information. 


        Args:
            member_id (int): Id of a discord user.
            game_id (int, optional): Id of a BAC game.
        
        Kwargs:
            member_2 (int, optional): Id of a second discord user.
            member_3 (int, optional): Id of a third discord user.
            member_4 (int, optional): Id of a fourth discord user.

        Returns:
            dict: Returns the dictionary with all the games found, or a json of a specified one
        '''
        try:
            session = cls.Session()
            if game_id is None:
                members = [member_id]
                members.append(kwargs.get("member_2", None)), members.append(kwargs.get("member_3", None)), members.append(kwargs.get("member_4", None)) # type: ignore # Why? Chopping down "None" values is crucial
                members = [x for x in members if x is not None]
                if len(members) == 1:
                    # SELECT id, player_won, t1, user_1, user_2, user_3, user_4 FROM bulls_records WHERE user_1 = %s OR user_2 = %s OR user_3 = %s OR user_4 = %s
                    result = session.query(Bulls_records.id, Bulls_records.player_won, Bulls_records.t1, Bulls_records.user_1, Bulls_records.user_2, Bulls_records.user_3, Bulls_records.user_4).filter(
                        (Bulls_records.user_1 == member_id) |
                        (Bulls_records.user_2 == member_id) |
                        (Bulls_records.user_3 == member_id) |
                        (Bulls_records.user_4 == member_id)).all()
                    info = [dict(zip(['id', 'player_won', 't1', 'user_1', 'user_2', 'user_3', 'user_4'], row)) for row in result]
                else:
                    conditions, params = [], []
                    for i in range(len(members) - 1):
                        for j in range(i + 1, len(members)):
                            conditions.append(
                                (
                                    (Bulls_records.user_1 == members[i]) & (Bulls_records.user_2 == members[j]) |
                                    (Bulls_records.user_1 == members[i]) & (Bulls_records.user_3 == members[j]) |
                                    (Bulls_records.user_1 == members[i]) & (Bulls_records.user_4 == members[j]) |
                                    (Bulls_records.user_2 == members[i]) & (Bulls_records.user_3 == members[j]) |
                                    (Bulls_records.user_2 == members[i]) & (Bulls_records.user_4 == members[j]) |
                                    (Bulls_records.user_3 == members[i]) & (Bulls_records.user_4 == members[j])
                                )
                            )
                            params.extend([user for pair in [(members[i], members[j])] for user in pair])
                    info = session.query(Bulls_records.id, Bulls_records.player_won, Bulls_records.t1, Bulls_records.user_1, Bulls_records.user_2, Bulls_records.user_3, Bulls_records.user_4).where(sa.or_(*conditions)).all()
                return info if info is None else info
            else:
                # SELECT id, json_game->'$' AS json_game FROM bulls_records WHERE id = %s;
                get_record_ret = session.query(Bulls_records.id, Bulls_records.json_game, Bulls_records.t1).filter_by(id=game_id).first()
                
                if get_record_ret is not None:
                    dict_to_ret = get_record_ret[1]
                    dict_to_ret['meta']['id'] = get_record_ret[0]
                    dict_to_ret['meta']['datetime_started'] = get_record_ret[2]
                    for player in dict_to_ret['meta']['players']:
                        if dict_to_ret['meta']['players'][player]['user_id'] == member_id:
                            return dict_to_ret
                    return {"private": True}
                return None
        except Exception as e:
            logger.exception("Error while getting BAC records")
        finally:
            session.close()
    
    @classmethod
    def get_player_characters(cls, member_id: int) -> dict | None:
        ''' Gets all the characters for a given member id

        Args:
            member_id (int): Id of a discord user.

        Returns:
            dict | None: Returns a dictionary with all the characters found, or None if none were found
        '''
        try:
            session = cls.Session()
            characters = session.query(Characters).options(joinedload(Characters.user_storage_id)).filter(Characters.user_storage_id.has(user_id=member_id), Characters.active == True).all()
            return characters.__dict__ if characters else None
        except Exception as e:
            logger.exception("Error while getting player characters")
        finally:
            session.close()
    
    @classmethod
    def check_if_inv_exists(cls, member_id: int) -> bool:
        ''' Checks if an inventory exists for a given member id

        Args:
            member_id (int): Id of a discord user.

        Returns:
            bool: Returns True if an inventory exists, False otherwise
        '''
        try:
            session = cls.Session()
            info = session.query(Inventories).filter_by(user_id=member_id).first()
            logger.info(f"Checked if inventory exists for {member_id}. Returning {'True' if info else 'False'}")
            return True if info else False
        except Exception as e:
            logger.exception("Error while checking if inventory exists")
        finally:
            session.close()
    
    @classmethod
    def get_inventory(cls, member_id: int) -> dict | None:
        ''' Gets the inventory for a given member id

        Args:
            member_id (int): Id of a discord user.

        Returns:
            dict | None: Returns a dictionary with all the inventory slots found, or None if none were found
        '''
        try:
            session = cls.Session()
            info = session.query(Inventory_slots).options(joinedload(Inventory_slots.inventory_id)).filter(Inventory_slots.inventory_id.has(user_id=member_id)).first()
            logger.info(f"Got inventory for {member_id} from the database")
            return info.__dict__ if info else None
        except Exception as e:
            logger.exception("Error while getting inventory")
        finally:
            session.close()
    
    ''' # TODO: Rewrite this method. Reason: Trash, not ORM
    @classmethod
    def insert_item(cls, member_id: int, item_id: str, quantity: int):
        item_id = item_id.split('_')
        item_ids = {"w": 1, "a": 2, "i": 3}
        
        try:
            session = cls.Session()
            try:
                with session.begin():
                    inventory_slots = session.query(Inventory_slots.inventory_id, Inventory_slots.slot_id) \
                        .join(Inventories, Inventory_slots.inventory_id == Inventories.id) \
                        .filter(Inventories.user_id == member_id) \
                        .order_by(sa.desc(Inventory_slots.id)).limit(1).one_or_none()
                    if inventory_slots is None:
                        return
                    if inv_id[0]['slot_id'] == 50:
                        pass
                    else:
                        check_item = session.query(Inventory_slots.id).filter_by(inventory_id=inv_id[0]['inventory_id'], item_id=item_id[1], item_type_id=item_ids[item_id[0]]).first()
                        if check_item is None:
                            new_slot = Inventory_slots(inventory_id=inv_id[0]['inventory_id'], slot_id=inv_id[0]['slot_id'] + 1, item_id=int(item_id[1]), quantity=quantity, item_type_id=item_ids[item_id[0]])
                            session.add(new_slot)
                        else:
                            update_slot = session.query(Inventory_slots).filter_by(id=check_item[0]['id']).first()
                            update_slot.quantity += quantity
                            session.add(update_slot)
                with connection.cursor() as cursor:
                    select_query = f"SELECT inventory_id, slot_id FROM inventory_slots WHERE inventory_id IN (SELECT id FROM inventories WHERE user_id = {member.id});"
                    cursor.execute(select_query)
                    inv_id = cursor.fetchall()
                    if inv_id[0]['slot_id'] == 50:
                        pass
                    else:
                        select_query = f"SELECT id FROM inventory_slots WHERE inventory_id = {inv_id[0]['inventory_id']}, item_id = {item_id[1]}, item_type_id = {item_id[0]};"
                        try:
                            cursor.execute(select_query)
                            check_item = cursor.fetchone()
                        except:
                            check_item = None
                        if check_item is None:
                            insert_query = f"INSERT INTO inventory_slots (inventory_id, slot_id, item_id, quantity, item_type_id) " \
                                f"VALUES ('{inv_id[0]['inventory_id']}', {inv_id[0]['slot_id'] + 1}, {int(item_id[1])}, {quantity}, {int(item_id[0])});"
                            cursor.execute(insert_query)
                            connection.commit()
                        else:
                            update_query = f"UPDATE inventory_slots SET quantity = quantity + {quantity} WHERE id = {check_item['id']}"
                            cursor.execute(update_query)
                            connection.commit()
            finally:
                connection.close()
        except Exception as e:
            print("Connection refused...")
            print(e)
    '''

    @classmethod
    def delete_user(cls, member_id: int):
        ''' Deletes a user from the database

        Args:
            member_id (int): Id of a discord user.
        '''
        try:
            session = cls.Session()
            session.query(Users).filter_by(id=member_id).delete()
            session.commit()
            logger.info(f"Deleted user {member_id} from the database")
        except Exception as e:
            logger.exception("Error while deleting user")
        finally:
            session.close()
    
    @classmethod
    def account_switch(cls, user1_id: int, user2_id: int):
        ''' Switches the accounts of two users

        Args:
            user1_id (int): Id of first discord user. Their account will be deleted if exists.
            user2_id (int): Id of second discord user. Transfered to user1_id.
        '''        
        try:
            session = cls.Session()

            # Check if user1 exists
            user1 = session.query(Users).filter_by(id=user1_id).first()
            if user1 is not None:
                # If user1 exists, delete them
                session.delete(user1)
                session.commit()
            
            # Update the user2's id
            session.execute(
                sa.text("UPDATE users SET id = :new_id WHERE id = :old_id"),
                {"new_id": user1_id, "old_id": user2_id}
            )
            session.commit()
            logger.info(f"Switched accounts for {user1_id} and {user2_id}")

        except Exception as e:
            session.rollback()
            logger.exception("Error while switching accounts")

        finally:
            session.close()
    
    @classmethod
    def add_command_stats(cls, member_id: int) -> None:
        ''' Adds a command usage stat to the user.

        Args:
            member_id (int): Id of a discord user.
        '''        
        try:
            session = cls.Session()
            select_query = session.query(sa.func.json_extract(User_data.json_stats, '$.botUsage.commandsUsed')).filter_by(user_id=member_id).first()
            if select_query is None: return
            select_query = list(select_query)
            select_query = int(select_query[0])
            select_query += 1
            session.query(User_data).filter(User_data.user_id==member_id).update({"json_stats": sa.func.json_set(User_data.json_stats, "$.botUsage.commandsUsed", select_query)})
            session.commit()
            logger.info(f"Updated command usage for {member_id}. Func \"add_command_stats()\"")
        except Exception as e:
            logger.exception(f"Error while updating command usage for {member_id}")
        finally:
            session.close()
    
    @classmethod
    def add_stats(cls, member_id: int, stat_string: str, custom_amount:int=None) -> None:
        '''Update the user's statistics on the games in the database.

        Args:
            member_id (int): Id of a discord user.
            stat_string (str): Json path to the stat.
            custom_amount (int, optional): Update by the custom amount instead of '1'. Defaults to None.
        
        Extra:
            stat_string already contains the "$.botUsage." part.
        '''        
        try:
            session = cls.Session()
            select_query = session.query(sa.func.json_extract(User_data.json_stats, f"$.botUsage.{stat_string}")).filter_by(user_id=member_id).first()
            if select_query is None: return
            select_query = list(select_query)
            select_query = int(select_query[0].replace('"', ''))
            if custom_amount:
                select_query += custom_amount
            else: select_query += 1
            session.query(User_data).filter(User_data.user_id==member_id).update({"json_stats": sa.func.json_set(User_data.json_stats, f"$.botUsage.{stat_string}", select_query)})
            session.commit()
            logger.info(f"Updated stats for {member_id}. Func \"add_stats()\"")
        except Exception as e:
            logger.exception(f"Error while updating stats for {member_id}")
        finally:
            session.close()

    @classmethod
    def add_rickroll_stats(cls, member_id: int, list_of_users: list):
        ''' Add rickroll stats to the user, or list of users if there are more than one.

        Args:
            member_id (int): Id of the main user.
            list_of_users (list): List of users that were rickrolled in the voicechat.
        '''        
        try:
            session = cls.Session()
            
            def slct_query(member_id_: int):
                stat = session.query(sa.func.json_extract(User_data.json_stats, '$.botUsage.rickroll')).filter_by(user_id=member_id_).first()
                if stat != None:
                    full_json = {"rickroll": json.loads(stat[0])}
                else: full_json = None
                return full_json
            
            def updt_query(member_id_: int, update_data:int, update_key:str):
                session.query(User_data).filter(User_data.user_id==member_id_).update({"json_stats": sa.func.json_set(User_data.json_stats, f"$.botUsage.rickroll.{update_key}", update_data)})
                session.commit()
                logger.info(f"Updated rickroll stats for {member_id_}. Func \"add_rickroll_stats()\"")
            if len(list_of_users) > 2:
                if DatabaseFunctions.check_exists(member_id):
                    rickroll_stat = slct_query(member_id)
                    if rickroll_stat is None: rickroll_stat = { "rickroll": { "themselves": 0, "others": 0 } }
                    rickroll_stat["rickroll"]["others"] += len(list_of_users) - 2
                    updt_query(member_id, update_data=rickroll_stat['rickroll']['others'], update_key="others")
                for person in list_of_users:
                    if DatabaseFunctions.check_exists(person) is True and person != member_id:
                        stats2 = slct_query(person)
                        if stats2 is not None: stats2["rickroll"]["themselves"] += 1
                        else: stats2 = { "rickroll": { "themselves": 1, "others": 0 } }
                        updt_query(person, update_data=stats2['rickroll']['themselves'], update_key="themselves")
            else:
                if DatabaseFunctions.check_exists(member_id):
                    rickroll_stat = slct_query(member_id)
                    if rickroll_stat != None: rickroll_stat['rickroll']['themselves'] += 1
                    else: rickroll_stat = { "rickroll": { "themselves": 1, "others": 0 } }
                    updt_query(member_id, update_data=rickroll_stat['rickroll']['themselves'], update_key="themselves")
        except Exception as e:
            logger.exception(f"Error while updating rickroll stats for {member_id}")
        finally:
            session.close()
    
    @classmethod
    def add_xp(cls, member_id:int, amount:int):
        ''' Add XP to a user's account.

        Args:
            member_id (int): Id of the user
            amount (int): Amount of XP to add
        '''        
        try:
            session = cls.Session()
            level_info = session.query(User_data.level, User_data.xp, User_data.max_xp).filter_by(user_id=member_id).first()
            if level_info is None: return
            level_info = level_info.__dict__
            level_info['xp'] += amount
            while level_info['xp'] >= level_info['max_xp']:
                level_info['xp'] = level_info['xp'] - level_info['max_xp']
                if level_info['level'] <= 6:
                    level_info['max_xp'] = round(level_info['max_xp'] + level_info['max_xp']/2)
                elif 6 < level_info['level'] <= 10:
                    level_info['max_xp'] = 2000
                else:
                    level_info['max_xp'] = 2500
                level_info['level'] += 1
            session.query(User_data).filter(User_data.user_id==member_id).update({"level": level_info['level'], "xp": level_info['xp'], "max_xp": level_info['max_xp']})
            session.commit()
            logger.info(f"Updated xp for {member_id}. Added {amount} xp. Current level: {level_info['level']}. Func \"add_xp()\"")
        except Exception as e:
            logger.exception(f"Error while updating xp for {member_id}")
        finally:
            session.close()
    
    @classmethod
    def update_userdata(cls, member_id:int, column:str, replacement: Any):
        '''Updates userdata column for a specific member

        Args:
            member_id (int): Id of a discord member
            column (str): Column to update
            replacement (Any): Replacement for the column

        Returns:
            NoneType: If the column is not in the list of allowed columns
        
        Allowed columns:
            - cash
            - level
            - xp
            - max_xp
            - bg
        '''  
        try:
            session = cls.Session()
            if column in ["json_stats", "preferences", "user_id"]:
                logger.warning(f"Can't change '{column}' column. Please consider using safest functions for that")
                return None
            session.query(User_data).filter(User_data.user_id==member_id).update({column: replacement})
            session.commit()
            logger.info(f"Updated {column} for {member_id}. Func \"update_userdata()\"")
        except Exception as e:
            logger.exception(f"Error while updating {column} for {member_id}")
        finally:
            session.close()
    
    @classmethod
    async def iterate_userdata(cls, column: str):
        '''Iterates userdata column for all members

        Args:
            column (str): Column to iterate
        '''
        try:
            session = cls.Session()
            all_data = session.query(User_data.user_id, getattr(User_data, column)).all()
            match column:
                case "preferences":
                    for member_id, preferences in all_data:
                        if preferences is None: 
                            preferences = {"language": "en", "prefix": None, "publicStats": True}
                            session.query(User_data).filter(User_data.user_id==member_id).update({column: preferences})
                            session.commit()
                case "json_stats":
                    for member_id, json_stats in all_data:
                        if 'short' not in json_stats['botUsage']['hangman']:
                            json_stats['botUsage']['hangman']['legacy'] = {'wins': json_stats['botUsage']['hangman']['Wins'], 'losses': json_stats['botUsage']['hangman']['Losses']}
                            json_stats['botUsage']['hangman'].pop('Wins'), json_stats['botUsage']['hangman'].pop('Losses')
                            json_stats['botUsage']['hangman']['short'] = {'wins': 0, 'losses': 0}
                            json_stats['botUsage']['hangman']['long'] = {'wins': 0, 'losses': 0}
                            
                            session.query(User_data).filter(User_data.user_id==member_id).update({column: json_stats})
                            session.commit()

            logger.info(f"Iterated {column} for all members. Func \"iterate_userdata()\"")
        except Exception as e:
            logger.exception(f"Error while iterating {column} for all members")
        finally:
            session.close()

    
    @classmethod
    def update_preferences(cls, member_id:int, json_path:str, update_data:Any):
        '''Updates preferences for a specific member

        Args:
            member_id (int): Id of a discord member
            json_path (str): Path to the value to update
            update_data (Any): Replacement for the value
        '''        
        try:
            session = cls.Session()
            session.query(User_data).filter(User_data.user_id==member_id).update({"preferences": sa.func.json_set(User_data.preferences, f"$.{json_path}", update_data)})
            session.commit()
            logger.info(f"Updated preferences for {member_id}. Func \"update_preferences()\"")
        except Exception as e:
            logger.exception(f"Error while updating preferences for {member_id}")
        finally:
            session.close()
    
    @classmethod
    def get_user_preferences(cls, member_id:int):
        '''Gets preferences for a specific member

        Args:
            member_id (int): Id of a discord member

        Returns:
            dict: Preferences of the member
        '''        
        try:
            session = cls.Session()
            preferences = session.query(User_data.preferences).filter_by(user_id=member_id).first()[0]
            logger.info(f"Retrieved preferences for {member_id}. Func \"get_user_preferences()\"")
            if preferences is None: return None
            return preferences
        except Exception as e:
            logger.exception(f"Error while getting preferences for {member_id}")
        finally:
            session.close()
    

class JsonOperating(MySQLConnector):
    @classmethod
    def get_userdata_stats(cls, member_id:int):
        try:
            session = cls.Session()
            information = session.query(User_data.user_id, sa.func.json_extract(User_data.json_stats, '$.botUsage').label('bot_usage')).filter_by(user_id=member_id).first()
            logger.info(f"Retrieved information from json about {member_id}. Func \"get_userdata_stats()\"")
            if information is None: return None
            information = list(information)
            information[1] = json.loads(information[1])
            return information
        except Exception as e:
            logger.exception("Error while getting userdata")
        finally:
            session.close()
    
    @classmethod
    def get_lang_code(cls, member_id:int):
        try:
            session = cls.Session()
            lang_code = session.query(sa.func.json_extract(User_data.preferences, '$.language')).filter_by(user_id=member_id).first()
            # logger.info(f"Retrieved lang_code for {member_id}. Func \"get_lang_code()\"")
            if lang_code is None: return None
            lang_code = list(lang_code)[0]
            return lang_code.replace('"', '')
        except Exception as e:
            logger.exception(f"Error while getting lang_code for {member_id}")
        finally:
            session.close()
    
    @classmethod
    def store_lang_code(cls, member_id:int, lang_code:str):
        try:
            session = cls.Session()
            session.query(User_data).filter(User_data.user_id==member_id).update({"preferences": sa.func.json_set(User_data.preferences, '$.language', lang_code)})
            session.commit()
            logger.info(f"Updated lang_code for {member_id}. Func \"store_lang_code()\"")
        except Exception as e:
            logger.exception(f"Error while updating lang_code for {member_id}")
        finally:
            session.close()

    @classmethod
    def store_custom_prefix(cls, member_id: int, prefix: str):
        try:
            session = cls.Session()
            session.query(User_data).filter(User_data.user_id==member_id).update({"preferences": sa.func.json_set(User_data.preferences, '$.prefix', prefix)})
            session.commit()
            logger.info(f"Updated prefix for {member_id}. Func \"store_custom_prefix()\"")
        except Exception as e:
            logger.exception(f"Error while updating prefix for {member_id}")
        finally:
            session.close()
    
    @classmethod
    def get_wov_player_by_id(cls, player_id:str):
        try:
            session = cls.Session()
            # SELECT personal_message, json_data->'$.*' AS wov_data FROM wov_players WHERE id = '{player_id}';
            information = session.query(Wov_players.personal_message, sa.func.json_extract(Wov_players.json_data, '$.*').label('wov_data'), Wov_players.previous_username).filter_by(id=player_id).first()
            logger.info(f"Retrieved information from json about {player_id}. Func \"get_wov_player_by_id()\"")
            if information is None: return None
            information = list(information)
            information[1] = json.loads(information[1])
            return information
        except Exception as e:
            logger.exception(f"Error while getting wov_player by id. Player id: {player_id}.")
        finally:
            session.close()
    
    @classmethod
    def get_wov_player_by_username(cls, username:str):
        try:
            session = cls.Session()
            # SELECT personal_message, json_data->'$.*' AS wov_data FROM wov_players WHERE username = '{username}';
            information = session.query(Wov_players.personal_message, sa.func.json_extract(Wov_players.json_data, '$').label('wov_data'), Wov_players.previous_username).filter(Wov_players.username == username).first()
            logger.info(f"Retrieved information from json about {username}. Func \"get_wov_player_by_username()\"")
            if information is None: return None
            information = list(information)
            information[1] = json.loads(information[1])
            return information
        except Exception as e:
            logger.exception(f"Error while getting wov_player by username. Username: {username}.")
        finally:
            session.close()
    
    @classmethod
    def get_wov_player_by_prev_username(cls, username: str):
        try:
            session = cls.Session()
            information = session.query(Wov_players.personal_message, sa.func.json_extract(Wov_players.json_data, '$').label('wov_data'), Wov_players.previous_username).filter(Wov_players.previous_username == username).first()
            logger.info(f"Retrieved information from json about {username}. Func \"get_wov_player_by_prev_username()\"")
            if information is None: return None
            information = list(information)
            information[1] = json.loads(information[1])
            return information
        except Exception as e:
            logger.exception(f"Error while getting wov_player by previous username. Username: {username}.")
        finally:
            session.close()
    
    @classmethod
    def get_wov_clan_by_id(cls, clan_id:str):
        try:
            session = cls.Session()
            # SELECT description, json_data->'$.*' AS wov_data FROM wov_clans WHERE id = '{clan_id}';
            information = session.query(Wov_clans.description, sa.func.json_extract(Wov_clans.json_data, f'$."{clan_id}"').label('wov_data')).filter_by(id=clan_id).first()
            logger.info(f"Retrieved information from json about {clan_id}. Func \"get_wov_clan_by_id()\"")
            if information is None or information[0] is None: return None
            information = list(information)
            information[1] = json.loads(information[1])
            return information
        except Exception as e:
            logger.exception(f"Error while getting wov_clan by id. Clan id: {clan_id}.")
        finally:
            session.close()
    
    @classmethod
    def get_wov_clan_by_name(cls, clan_name:str):
        try:
            session = cls.Session()
            # SELECT description, json_data->'$.*' AS wov_data FROM wov_clans WHERE name = '{clan_name}';
            information = session.query(Wov_clans.description, sa.func.json_extract(Wov_clans.json_data, '$').label('wov_data'), Wov_clans.id).filter_by(name=clan_name).first()
            logger.info(f"Retrieved information from json about {clan_name}. Func \"get_wov_clan_by_name()\"")
            if information is None: return None
            information = list(information)
            information[1] = json.loads(information[1])
            information[1] = information[1][information[2]]
            information.pop(2)
            return information
        except Exception as e:
            logger.exception(f"Error while getting wov_clan by name. Clan name: {clan_name}.")
        finally:
            session.close()
    
    @classmethod
    def get_wov_clan_members(cls, clan_id:str):
        try:
            session = cls.Session()
            # SELECT json_data->'$.*' AS wov_data FROM wov_players WHERE clan_id = '{clan_id}';
            information = session.query(sa.func.json_extract(Wov_clans.members, '$').label('wov_data')).filter_by(id=clan_id).all()
            logger.info(f"Retrieved information from json about {clan_id}. Func \"get_wov_clan_members()\"")
            if information[0][0] is None: return None
            information = list(information[0])
            information = json.loads(information[0])
            return information
        except Exception as e:
            logger.exception(f"Error while getting wov_clan members. Clan id: {clan_id}.")
        finally:
            session.close()
    
    @classmethod
    def daily_info_json(cls, member_id: int):
        '''
        Get the daily information about a user from the database. If the user does not exist, create it.
        @param member_id - the user's id
        @returns the user's information in a dictionary
        '''
        try:
            session = cls.Session()
            information = session.query(User_data.user_id, sa.func.json_extract(User_data.json_stats, '$.botUsage.dailyInfo')).filter_by(user_id=member_id).first()
            logger.info(f"Retrieved information from json about {member_id}. Func \"daily_info_json()\"")
            if information is None: return None
            information = list(information)
            information[1] = json.loads(information[1])
            return information
        except Exception as e:
            logger.exception(f"Error while getting daily info about {member_id}")
        finally:
            session.close()
    
    @classmethod
    def daily_info_update(cls, member_id:int, daily_json:dict):
        ''' Update the information about a daily of the user in the database.

        Args:
            member_id (int): Id of the user
            daily_json (dict): The new daily information. Contains the following keys: 'dailyCount', 'lastDailyTime'
        '''
        try:
            session = cls.Session()
            assert 'dailyCount' in daily_json and 'lastDailyTime' in daily_json, 'daily_json must contain the following keys: \'dailyCount\', \'lastDailyTime\''
            session.query(User_data).filter(User_data.user_id==member_id).update({"json_stats": sa.func.json_set(User_data.json_stats, "$.botUsage.dailyInfo.dailyCount", daily_json['dailyCount'])})
            session.query(User_data).filter(User_data.user_id==member_id).update({"json_stats": sa.func.json_set(User_data.json_stats, "$.botUsage.dailyInfo.lastDailyTime", daily_json['lastDailyTime'])})
            session.commit()
            logger.info(f"Updated daily info for {member_id}. Func \"daily_info_update()\"")
        except Exception as e:
            logger.exception(f"Error while updating daily info about {member_id}")
        finally:
            session.close()

class LichessTables(MySQLConnector):
    @classmethod
    def get_lichess_player(cls, username:str):
        try:
            session = cls.Session()
            information = session.query(Lichess_players.username, Lichess_players.json_data).filter_by(username=username).first()
            logger.info(f"Retrieved information from json about {username}. Func \"get_lichess_player()\"")
            if information is None: return None
            information = dict(information)
            if information['json_data'] is None: return None
            information['json_data']['seenAt'] = datetime_.strptime(information['json_data']['seenAt'], "%Y-%m-%d %H:%M:%S")
            information['json_data']['createdAt'] = datetime_.strptime(information['json_data']['createdAt'], "%Y-%m-%d %H:%M:%S")
            information['json_data']['time_cached'] = datetime_.strptime(information['json_data']['time_cached'], "%Y-%m-%d %H:%M:%S")
            return information
        except Exception as e:
            logger.exception(f"Error while getting lichess_player by username. Username: {username}.")
        finally:
            session.close()

    @classmethod
    def get_lichess_top(cls, current_datetime:datetime_):
        try:
            session = cls.Session()
            information = session.query(sa.func.json_extract(LichessTop.json_data, '$'), LichessTop.time_cached).filter(LichessTop.time_cached>current_datetime-datetime.timedelta(days=1)).first()
            logger.info(f"Retrieved information from json about {current_datetime}. Func \"get_lichess_top()\"")
            if information is None: return None
            information = list(information)
            information[0] = json.loads(information[0])
            return information
        except Exception as e:
            logger.exception(f"Error while getting lichess_top by date. Date: {current_datetime}.")
        finally:
            session.close()
    
    @classmethod
    def store_lichess_top(cls, json_dict: dict):
        try:
            session = cls.Session()
            session.add(LichessTop(json_data=json_dict, time_cached=datetime_.utcnow()))
            session.commit()
            logger.info(f"Stored lichess_top. Func \"store_lichess_top()\"")
        except Exception as e:
            logger.exception(f"Error while storing lichess_top.")
        finally:
            session.close()
    
    @classmethod
    def store_lichess_player(cls, json_dict: dict):
        try:
            session = cls.Session()
            json_dict['seenAt'] = json_dict['seenAt'].strftime('%Y-%m-%d %H:%M:%S')
            json_dict['createdAt'] = json_dict['createdAt'].strftime('%Y-%m-%d %H:%M:%S')
            json_dict['time_cached'] = datetime_.utcnow().strftime('%Y-%m-%d %H:%M:%S')
            check = session.query(Lichess_players).filter_by(username=json_dict['username']).first()
            if check is not None:
                session.query(Lichess_players).filter_by(username=json_dict['username']).update({"json_data": json_dict, "time_cached": datetime_.now()})
            else: session.add(Lichess_players(username=json_dict['username'], json_data=json_dict, time_cached=datetime_.now()))
            session.commit()
            logger.info(f"Stored lichess_player. Func \"store_lichess_player()\"")
        except Exception as e:
            logger.exception(f"Error while storing lichess_player.")
        finally:
            session.close()
    
    @classmethod
    def get_lichess_perfs(cls, username: str, perf_type: str):
        try:
            session = cls.Session()
            information = session.query(Lichess_players.username, sa.func.json_extract(Lichess_players.json_perfs, f'$.{perf_type}')).filter_by(username=username).first()
            logger.info(f"Retrieved information from json about {username}. Func \"get_lichess_perfs()\"")
            if information is None or information[1] is None: return None
            information = {'username': information[0], 'json_data': json.loads(information[1])}
            return information
        except Exception as e:
            logger.exception(f"Error while getting lichess_perfs by username. Username: {username}.")
            return None
        finally:
            session.close()
    
    @classmethod
    def store_lichess_perfs(cls, username: str, json_dict: dict):
        try:
            session = cls.Session()
            json_dict['time_cached'] = datetime_.utcnow().strftime('%Y-%m-%d %H:%M:%S')
            check = session.query(Lichess_players.username).filter_by(username=username).first()
            if check is not None:
                session.query(Lichess_players).filter(Lichess_players.username==username).update({"json_perfs": {json_dict['stat']['perfType']['key']: json_dict}})
            else:
                session.add(Lichess_players(username=username, json_perfs={json_dict['stat']['perfType']['key']: json_dict}, time_cached=datetime_.now()))
            session.commit()
            logger.info(f"Stored lichess_perfs. Func \"store_lichess_perfs()\"")
        except Exception as e:
            logger.exception(f"Error while storing lichess_perfs.")
        finally:
            session.close()
    
    @classmethod
    def get_10_lichess_games_from_user(cls, username: str):
        try:
            session = cls.Session()
            game_id = session.query(Lichess_players.last_10_games).filter_by(username=username).first()
            logger.info(f"Retrieved 10 last games from {username}. Func \"get_10_lichess_games_from_user()\"")
            if game_id is None or game_id[0] is None or datetime_.strptime(game_id[0][-1], '%Y-%m-%d %H:%M:%S') < datetime_.utcnow()-datetime.timedelta(days=1, hours=12): return None
            game_id[0].remove(game_id[0][-1])
            return game_id
        except Exception as e:
            logger.exception(f"Error while getting 10 last games from user. Username: {username}.")
        finally:
            session.close()
    
    @classmethod
    def store_10_lichess_games_from_user(cls, username: str, game_ids: list):
        try:
            session = cls.Session()
            check = session.query(Lichess_players.username).filter_by(username=username).first()
            game_ids.append(datetime_.utcnow().strftime('%Y-%m-%d %H:%M:%S'))
            if check is not None:
                session.query(Lichess_players).filter_by(username=username).update({"last_10_games": game_ids})
            else:
                session.add(Lichess_players(username=username, last_10_games=game_ids))
            session.commit()
            logger.info(f"Stored 10 last games from {username}. Func \"store_10_lichess_games_from_user()\"")
        except Exception as e:
            logger.exception(f"Error while storing 10 last games from user.")
        finally:
            session.close()
    
    @classmethod
    def get_lichess_game(cls, game_id: str):
        try:
            session = cls.Session()
            information = session.query(Lichess_games.game_id, Lichess_games.json_data).filter_by(game_id=game_id).first()
            logger.info(f"Retrieved information from json about {game_id}. Func \"get_lichess_game()\"")
            if information is None: return None
            information = dict(information)
            try:
                information['json_data']['createdAt'] = datetime_.strptime(information['json_data']['createdAt'], '%Y-%m-%d %H:%M:%S')
                information['json_data']['lastMoveAt'] = datetime_.strptime(information['json_data']['lastMoveAt'], '%Y-%m-%d %H:%M:%S')
            except Exception as e:
                pass
            return information['json_data']
        except Exception as e:
            logger.exception(f"Error while getting lichess_game by game_id. Game_id: {game_id}.")
        finally:
            session.close()
    
    @classmethod
    def if_lichess_game_analysed(cls, game_id: str):
        try:
            session = cls.Session()
            information = session.query(Lichess_games.analysed).filter_by(game_id=game_id).first()
            logger.info(f"Retrieved information from json about {game_id}. Func \"if_lichess_game_analysed()\"")
            if information is None: return False
            return information[0]
        except Exception as e:
            logger.exception(f"Error while getting if lichess_game was analysed by game_id. Game_id: {game_id}.")
        finally:
            session.close()
    
    @classmethod
    def get_lichess_game_bulk(cls, game_ids: list):
        try:
            session = cls.Session()
            information = session.query(Lichess_games.game_id, Lichess_games.json_data).filter(Lichess_games.game_id.in_(game_ids)).all()
            logger.info(f"Retrieved information from json about {game_ids}. Func \"get_lichess_game_bulk()\"")
            if information is None: return None
            information = dict(information)
            for game in information:
                game['json_data']['createdAt'] = datetime_.strptime(game['json_data']['createdAt'], '%Y-%m-%d %H:%M:%S')
                game['json_data']['lastMoveAt'] = datetime_.strptime(game['json_data']['lastMoveAt'], '%Y-%m-%d %H:%M:%S')
            return information
        except Exception as e:
            logger.exception(f"Error while getting lichess_game by game_id. Game_id: {game_ids}.")
        finally:
            session.close()
    
    @classmethod
    def get_lichess_game_pgn(cls, game_id: str):
        try:
            session = cls.Session()
            information = session.query(Lichess_games.game_id, Lichess_games.pgn).filter_by(game_id=game_id).first()
            logger.info(f"Retrieved information from json about {game_id}. Func \"get_lichess_game_pgn()\"")
            if information is None: return None
            information = dict(information)
            return information['pgn']
        except Exception as e:
            logger.exception(f"Error while getting lichess_game_pgn by game_id. Game_id: {game_id}.")
        finally:
            session.close()
    
    @classmethod
    def store_lichess_game(cls, nxjson: dict):
        try:
            session = cls.Session()
            
            analysed = True if 'analysis' in nxjson else False
            check = session.query(Lichess_games.game_id, Lichess_games.analysed).filter_by(game_id=nxjson['id']).first()
            
            if check is not None and check[1] is True or check is not None and analysed == check[1]:
                return
            
            if 'pgn' in nxjson:
                pgn = nxjson['pgn']
                nxjson.pop('pgn')
            else: pgn = None
            
            
            match type(nxjson['createdAt']):
                case builtins.int:
                    nxjson['createdAt'] = datetime_.utcfromtimestamp(nxjson["createdAt"]/1000).strftime('%Y-%m-%d %H:%M:%S') # divide by 1000 because of milliseconds
                case builtins.str:
                    nxjson['createdAt'] = datetime_(nxjson['createdAt']).strftime('%Y-%m-%d %H:%M:%S')
                case _: # in case of a datetime object
                    nxjson['createdAt'] = nxjson['createdAt'].strftime('%Y-%m-%d %H:%M:%S')
            
            match type(nxjson['lastMoveAt']):
                case builtins.int:
                    nxjson['lastMoveAt'] = datetime_.utcfromtimestamp(nxjson["lastMoveAt"]/1000).strftime('%Y-%m-%d %H:%M:%S')
                case builtins.str:
                    nxjson['lastMoveAt'] = datetime_(nxjson['lastMoveAt']).strftime('%Y-%m-%d %H:%M:%S')
                case _:
                    nxjson['lastMoveAt'] = nxjson['lastMoveAt'].strftime('%Y-%m-%d %H:%M:%S')
        
            session.add(Lichess_games(game_id=nxjson['id'], json_data=nxjson, pgn=pgn, time_cached=datetime_.utcnow(), analysed=analysed)) if check is None else session.query(Lichess_games).filter_by(game_id=nxjson['id']).update({"json_data": nxjson, "time_cached": datetime_.utcnow(), "analysed": analysed})
            session.commit()
            logger.info(f"Stored lichess_game. Func \"store_lichess_game()\"")
        except Exception as e:
            logger.exception(f"Error while storing lichess_game.")
        finally:
            session.close()
    
    @classmethod
    def store_lichess_pgn(cls, game_id: str, pgn: str):
        try:
            session = cls.Session()
            session.query(Lichess_games).filter_by(game_id=game_id).update({"pgn": pgn})
            session.commit()
            logger.info(f"Stored lichess_pgn. Func \"store_lichess_pgn()\"")
        except Exception as e:
            logger.exception(f"Error while storing lichess_pgn.")
        finally:
            session.close()

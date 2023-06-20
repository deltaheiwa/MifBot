from pathlib import Path
from typing import Union

import httplib2
from googleapiclient.discovery import build
from oauth2client.service_account import ServiceAccountCredentials
import creds
# from bot_functions import *


def get_service_simple():
    return build('sheets', 'v4', developerKey=creds.api_key)


def get_service_sacc():
    creds_json = Path('creds', 'mifbotv2-26f3870ec212.json')
    scopes = 'https://www.googleapis.com/auth/spreadsheets'

    creds_service = ServiceAccountCredentials.from_json_keyfile_name(
        creds_json, scopes).authorize(httplib2.Http())
    return build('sheets', 'v4', http=creds_service)

class SheetsData:
    enemies = []
    general_items = []
    weapons = []
    armors = []
    characters = []
    artefacts = []
    
    def return_section(self, string_value: str) -> list[list[Union[str,int]]]:
        match string_value:
            case "weapons": return self.weapons
            case "armors": return self.armors
            case "characters": return self.characters
            case "general_items": return self.general_items
            case "enemies": return self.enemies
            case "artefacts": return self.artefacts
            case _: return []
    

def run():
    service = get_service_sacc()
    sheet = service.spreadsheets()
    resp_enemies = sheet.values().get(spreadsheetId=creds.sheet_id,range="Enemies!A2:S35").execute()
    resp_items = sheet.values().get(spreadsheetId=creds.sheet_id,range="Items!A2:S35").execute()
    resp_weapons = sheet.values().get(spreadsheetId=creds.sheet_id,range="Weapons!A2:S35").execute()
    resp_armor = sheet.values().get(spreadsheetId=creds.sheet_id,range="Armor!A2:S35").execute()
    resp_characters = sheet.values().get(spreadsheetId=creds.sheet_id, range="Characters!A2:S35").execute()
    resp_artefacts = sheet.values().get(spreadsheetId=creds.sheet_id, range="Artefacts!A2:S35").execute()
    SheetsData.enemies = resp_enemies['values']
    SheetsData.general_items = resp_items['values']
    SheetsData.weapons = resp_weapons['values']
    SheetsData.armors = resp_armor['values']
    SheetsData.characters = resp_characters['values']
    SheetsData.artefacts = resp_artefacts['values']

def delete_cache():
    del SheetsData.enemies, SheetsData.general_items, SheetsData.weapons, SheetsData.armors, SheetsData.characters
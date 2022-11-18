from pathlib import Path

import httplib2
from googleapiclient.discovery import build
from oauth2client.service_account import ServiceAccountCredentials
import creds
from functions import *


def get_service_simple():
    return build('sheets', 'v4', developerKey=creds.api_key)


def get_service_sacc():
    creds_json = Path('creds', 'mifbotv2-26f3870ec212.json')
    scopes = ['https://www.googleapis.com/auth/spreadsheets']

    creds_service = ServiceAccountCredentials.from_json_keyfile_name(
        creds_json, scopes).authorize(httplib2.Http())
    return build('sheets', 'v4', http=creds_service)

def run():
    service = get_service_sacc()
    sheet = service.spreadsheets()
    sheet_id = creds.sheet_id
    resp_enemies = sheet.values().get(spreadsheetId=sheet_id,range="Enemies!A2:P35").execute()
    resp_items = sheet.values().get(spreadsheetId=sheet_id,range="Items!A2:P35").execute()
    resp_weapons = sheet.values().get(spreadsheetId=sheet_id,range="Weapons!A2:P35").execute()
    resp_armor = sheet.values().get(spreadsheetId=sheet_id,range="Armor!A2:P35").execute()
    resp_characters = sheet.values().get(spreadsheetId=sheet_id, range="Characters!A2:P35").execute()
    global enemies
    enemies = resp_enemies['values']
    global items
    items = resp_items['values']
    global weapons
    weapons = resp_weapons['values']
    global armor
    armor = resp_armor['values']
    global characters
    characters = resp_characters['values']

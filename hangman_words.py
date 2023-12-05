"""Extracts words from json file and stores them in a list."""
import json


pics = [r'''
_______
|     |
|
|
|
|
========''',r'''
_______
|     |
|     O
|
|
|
========''',r'''
_______
|     |
|     O
|     |
| 
|
========''', r'''
_______
|     |
|     O
|    /|
|   
|
========''', r'''
_______
|     |
|     O
|    /|\
|   
|
========''', r'''
_______
|     |
|     O
|    /|\
|    / 
|
========''', r'''
_______
|     |
|     O
|    /|\
|    / \
|
========''']

with open('words.json', 'r', encoding="utf-8") as f:
    words = json.load(f)

words_short = words['short']
words_long = words['long']

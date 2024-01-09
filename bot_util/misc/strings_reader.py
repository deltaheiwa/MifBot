import csv
import discord
import random


class BotStringsReader:
    def __init__(self, bot, filename, author=None):
        self.filename = filename
        self.filepath = "./bot_strings/" + filename + ".csv"
        self.bot = bot
        self.author = author


    def return_string(self, query_info: dict = {}):
        with open(self.filepath, "r") as file:
            reader = csv.reader(file)
            reader_row_list = [row for row in reader]
            match self.filename:
                case "triggering":
                    times_called = query_info.get("times_called", 1)
                    if times_called > 3:
                        times_called = 3
                    amount_of_people = query_info.get("amount", 1)
                    row = random.choice(reader_row_list)
                    return self.parse_string(row[times_called-1], amount_of_people)

    def parse_string(self, string: str, amount):
        if '/m/' in string:
            multiple_strings = string.split('/m/')
            string = multiple_strings[0] if amount < 2 else multiple_strings[1]
        if '/e/' in string:
            sliced_string = string.removeprefix('/e/').split('/d/')
            title = sliced_string[0].format(user=self.author) if '{user}' in sliced_string[0] else sliced_string[0]
            embed = discord.Embed(title=title, description=sliced_string[1], color=discord.Color.red())
            return embed
        return string

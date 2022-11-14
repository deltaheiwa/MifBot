import sqlite3


def main():
    # conn = sqlite3.connect(':memory:')
    # Connect to database
    conn = sqlite3.connect('local.db')
    # Create a cursor
    c = conn.cursor()

    # c.execute("DROP TABLE IF EXISTS players")

    # Create a table
    c.execute('''CREATE TABLE IF NOT EXISTS prefixes (
        guild_id integer PRIMARY KEY,
        prefix text
        )''')
    
    # Datatypes:
    # NULL
    # INTEGER
    # REAL
    # TEXT
    # BLOB

    # c.execute("INSERT INTO players VALUES (123456789, 'someDan')")

    # Query
    # c.execute('''SELECT * FROM prefixes''')
    # c.fetchone()
    # c.fetchmany(3)
    # c.fetchall()

    # Update
    # c.execute(f'''UPDATE prefixes SET prefix = {prefix} WHERE guild_id = {guild_id}''')

    # Commit our command
    conn.commit()

    # Close our connection
    conn.close()

async def new_prefix(guild_id, prefix):
    with sqlite3.connect('local.db') as conn:
        c = conn.cursor()
        c.execute(f'''SELECT * FROM prefixes WHERE guild_id = {guild_id}''')
        prefix_data = c.fetchone()
        if prefix_data is None:
            c.execute(f"INSERT INTO prefixes (guild_id, prefix) VALUES ({guild_id}, '{prefix}')")
            conn.commit()
        else:
            c.execute(f"UPDATE prefixes SET prefix = '{prefix}' WHERE guild_id = {guild_id}")
            conn.commit()

async def remove_prefix(guild_id):
    with sqlite3.connect('local.db') as conn:
        c = conn.cursor()
        c.execute(f"DELETE FROM prefixes WHERE guild_id = {guild_id}")
        conn.commit()

async def return_prefix(guild_id):
    with sqlite3.connect('local.db') as conn:
        c = conn.cursor()
        c.execute(f'''SELECT prefix FROM prefixes WHERE guild_id = {guild_id}''')
        prefix = c.fetchone()
        if prefix is None:
            c.execute(f"INSERT INTO prefixes (guild_id, prefix) VALUES ({guild_id}, '.')")
            conn.commit()
            return '.'
        else: return prefix

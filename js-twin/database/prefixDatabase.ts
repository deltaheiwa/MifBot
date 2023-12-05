import * as sqlite3 from 'sqlite3';
import { open, Database } from 'sqlite';
import { prefixDatabaseLocation } from './databasePaths';

export default class PrefixDatabase {
    private static db: Database | null = null;

    static async new_prefix(guild_id: number, prefix: string): Promise<void> {
        const db = await this.getDatabase(); 
        if (prefix == null) {
            await db.run(`DELETE FROM prefixes WHERE guild_id = ?`, guild_id);
            return;
        }
        const prefix_data = await db.get(`SELECT * FROM prefixes WHERE guild_id = ?`, guild_id);
        if (!prefix_data) {
            await db.run(`INSERT INTO prefixes (guild_id, prefix) VALUES (?, ?)`, guild_id, prefix);
        } else {
            await db.run(`UPDATE prefixes SET prefix = ? WHERE guild_id = ?`, prefix, guild_id);
        }
    }

    static async getDatabase(): Promise<Database> {
        if (!this.db) {
                this.db = await open({
                    filename: prefixDatabaseLocation,
                    driver: sqlite3.Database
                });
                await this.db.run(`CREATE TABLE IF NOT EXISTS prefixes (
                    guildId TEXT PRIMARY KEY,
                    prefix TEXT
                )`);
            }
        return this.db;
    }

    static async remove_prefix(guild_id: number): Promise<void> {
        const db = await this.getDatabase();
        await db.run(`DELETE FROM prefixes WHERE guild_id = ?`, guild_id);
    }

    static async return_prefix(_id: number, user: boolean = false): Promise<string | null> {
        const db = await this.getDatabase();
        const prefix = await db.get(`SELECT prefix FROM prefixes WHERE guild_id = ?`, _id);
        if (!prefix && !user) {
            await db.run(`INSERT INTO prefixes (guild_id, prefix) VALUES (?, ?)`, _id, '.');
            return '.';
        } else {
            return prefix?.prefix || null;
        }
    }
}
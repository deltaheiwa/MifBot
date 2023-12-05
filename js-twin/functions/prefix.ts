import { Mif } from "../structures/Mif";
import PrefixDatabase from '../database/prefixDatabase';
import { Message } from "discord.js";

export async function determine_prefix(message: Message) {
    try {
        var prefix: string;
        const user_pref: string | null = await PrefixDatabase.return_prefix(+message.author.id, true);
        const guild_pref: string | null = message.guild ? await PrefixDatabase.return_prefix(+message.guild.id) : null;
        if (user_pref == null || user_pref != message.content.slice(0, user_pref.length)) {
            prefix = guild_pref || ".";
        } else {
            prefix = user_pref || ".";
        }
        return prefix;
    }
    catch (e) {
        console.log(`Error in determine_prefix: ${e}`);
        return ".";
    }
}
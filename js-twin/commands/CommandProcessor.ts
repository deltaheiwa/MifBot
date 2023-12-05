import { Message } from "discord.js";
import { Mif } from "../structures/Mif"
import { determine_prefix } from "../functions/prefix";

export class CommandProcessor {
    bot: Mif;
    prefix?: string;

    public constructor(bot: Mif) {
        this.bot = bot;
    }
    
    public async process(message: Message) {
        if (message.author.bot) return;
        this.prefix = await determine_prefix(message);
    }
}
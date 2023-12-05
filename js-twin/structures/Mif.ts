import {
    Client as DiscordClient,
    Collection,
    Events
} from 'discord.js';
import { TextCommand } from '../interfaces/Commands';
import { determine_prefix } from '../functions/prefix';
import { CommandProcessor } from '../commands/CommandProcessor';

require('dotenv').config();

export class Mif {
    public commands = new Collection<string, TextCommand>();
    public readonly client: DiscordClient;
    public readonly token: string = process.env.TOKEN || '';
    public commandProcessor: CommandProcessor = new CommandProcessor(this);

    public constructor(public readonly discordClient: DiscordClient) {
        this.client = discordClient;
        this.client.login(this.token);

        this.client.once('ready', () => {
            console.log('Discord JS Twin loaded!');
        });
    }

    
}
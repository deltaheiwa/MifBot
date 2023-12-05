import {
    Client as DiscordClient,
    GatewayIntentBits,
    Collection,
    Events
} from 'discord.js';
require('dotenv').config();
import fs from 'fs';
import path from 'path';
import { WebSocketServerWrapper } from './structures/WebSocketServer'
import { Mif } from './structures/Mif';

const intents = [
    GatewayIntentBits.Guilds,
    GatewayIntentBits.GuildMessages,
    GatewayIntentBits.GuildMembers,
    GatewayIntentBits.GuildMessageReactions,
    GatewayIntentBits.MessageContent,
    GatewayIntentBits.DirectMessages,
];

export const bot = new Mif(
    new DiscordClient({
        intents: intents
    })
)

const wss: WebSocketServerWrapper = new WebSocketServerWrapper();

// WebSocket server
wss.start();


// Command handler

const commandsPath = path.join(__dirname, 'commands');
const commandFiles = fs.readdirSync(commandsPath).filter(file => file.endsWith('.ts'));

for (const file of commandFiles) {
    const command = require(path.join(commandsPath, file));
    if ('data' in command && 'execute' in command) {
        bot.commands.set(command.data.name, command);
    } else {
        console.error(`[WARNING] Command file ${file} is missing data or execute function.`);
    }
}

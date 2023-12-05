import WebSocket from 'ws';

export class WebSocketServerWrapper {
    private wss: WebSocket.Server;
    public port: number;

    public constructor(port: number = 8080) {
        this.port = port;
        this.wss = new WebSocket.Server({ port: this.port });
    }

    public start() {
        this.wss.on('connection', (ws) => {
            ws.on('message', (message) => {
                console.log('received: %s', message);
            });
            ws.send('Got you!');
        });
    }
}
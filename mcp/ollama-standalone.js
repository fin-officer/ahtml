const WebSocket = require('ws');
const axios = require('axios');

class OllamaMCPServer {
    constructor(port = 8080, ollamaUrl = 'http://localhost:11434') {
        this.port = port;
        this.ollamaUrl = ollamaUrl;
        this.clients = new Set();
        this.models = [];
        this.init();
    }

    async init() {
        this.wss = new WebSocket.Server({ port: this.port });
        await this.loadAvailableModels();
        this.setupWebSocketServer();
        console.log(`🦙 Ollama MCP Server running on port ${this.port}`);
        console.log(`🔗 WebSocket URL: ws://localhost:${this.port}`);
    }

    async loadAvailableModels() {
        try {
            const response = await axios.get(`${this.ollamaUrl}/api/tags`);
            this.models = response.data.models || [];
            console.log(`Loaded ${this.models.length} Ollama models`);
            if (this.models.length > 0) {
                console.log('Available models:', this.models.map(m => m.name).join(', '));
            }
        } catch (error) {
            console.error('Error loading Ollama models:', error.message);
            console.log('Make sure Ollama is running and accessible at', this.ollamaUrl);
        }
    }

    setupWebSocketServer() {
        this.wss.on('connection', (ws) => {
            this.clients.add(ws);
            console.log('New MCP client connected');

            ws.on('message', async (data) => {
                try {
                    const message = JSON.parse(data.toString());
                    const response = await this.handleMCPMessage(message);
                    if (response) {
                        ws.send(JSON.stringify(response));
                    }
                } catch (error) {
                    this.sendError(ws, 'INVALID_JSON', error.message);
                }
            });

            ws.on('close', () => {
                this.clients.delete(ws);
                console.log('MCP client disconnected');
            });
        });
    }

    async handleMCPMessage(message) {
        const { method, params, id } = message;

        try {
            switch (method) {
                case 'initialize':
                    return this.handleInitialize(id, params);
                case 'tools/list':
                    return this.handleToolsList(id);
                case 'tools/call':
                    return await this.handleToolCall(id, params);
                case 'resources/list':
                    return this.handleResourcesList(id);
                case 'resources/read':
                    return await this.handleResourceRead(id, params);
                default:
                    return this.createError(id, 'METHOD_NOT_FOUND', `Unknown method: ${method}`);
            }
        } catch (error) {
            return this.createError(id, 'INTERNAL_ERROR', error.message);
        }
    }

    handleInitialize(id) {
        return {
            jsonrpc: '2.0',
            id,
            result: {
                protocolVersion: '1.0',
                serverInfo: {
                    name: 'Ollama MCP Server',
                    version: '1.0.0'
                },
                capabilities: {
                    tools: true,
                    resources: true
                }
            }
        };
    }

    handleToolsList(id) {
        const tools = [
            {
                name: 'ollama_generate',
                description: 'Generate text using Ollama',
                inputSchema: {
                    type: 'object',
                    properties: {
                        model: {
                            type: 'string',
                            description: 'Ollama model name',
                            enum: this.models.map(m => m.name)
                        },
                        prompt: {
                            type: 'string',
                            description: 'Prompt for generation'
                        },
                        temperature: {
                            type: 'number',
                            description: 'Generation temperature (0-1)',
                            default: 0.7
                        },
                        max_tokens: {
                            type: 'integer',
                            description: 'Maximum number of tokens',
                            default: 1000
                        }
                    },
                    required: ['model', 'prompt']
                }
            },
            {
                name: 'ollama_list_models',
                description: 'List available Ollama models',
                inputSchema: { type: 'object' }
            },
            {
                name: 'ollama_chat',
                description: 'Chat with Ollama model',
                inputSchema: {
                    type: 'object',
                    properties: {
                        model: { type: 'string' },
                        messages: {
                            type: 'array',
                            items: {
                                type: 'object',
                                properties: {
                                    role: { type: 'string', enum: ['user', 'assistant'] },
                                    content: { type: 'string' }
                                }
                            }
                        }
                    },
                    required: ['model', 'messages']
                }
            }
        ];

        return { jsonrpc: '2.0', id, result: { tools } };
    }

    async handleToolCall(id, params) {
        const { name, arguments: args } = params;

        try {
            switch (name) {
                case 'ollama_generate':
                    return await this.ollamaGenerate(id, args);
                case 'ollama_list_models':
                    return await this.ollamaListModels(id);
                case 'ollama_chat':
                    return await this.ollamaChat(id, args);
                default:
                    return this.createError(id, 'TOOL_NOT_FOUND', `Unknown tool: ${name}`);
            }
        } catch (error) {
            return this.createError(id, 'TOOL_EXECUTION_ERROR', error.message);
        }
    }

    async ollamaGenerate(id, { model, prompt, temperature = 0.7, max_tokens = 1000 }) {
        const response = await axios.post(`${this.ollamaUrl}/api/generate`, {
            model,
            prompt,
            options: { temperature, num_predict: max_tokens }
        });

        return {
            jsonrpc: '2.0',
            id,
            result: {
                content: [{ type: 'text', text: response.data.response }]
            }
        };
    }

    async ollamaListModels(id) {
        await this.loadAvailableModels();
        return {
            jsonrpc: '2.0',
            id,
            result: {
                content: [{ type: 'text', text: JSON.stringify(this.models, null, 2) }]
            }
        };
    }

    async ollamaChat(id, { model, messages }) {
        const response = await axios.post(`${this.ollamaUrl}/api/chat`, {
            model,
            messages,
            stream: false
        });

        return {
            jsonrpc: '2.0',
            id,
            result: {
                content: [{ type: 'text', text: response.data.message.content }]
            }
        };
    }

    handleResourcesList(id) {
        return {
            jsonrpc: '2.0',
            id,
            result: {
                resources: [
                    {
                        uri: 'ollama://models',
                        name: 'Ollama Models',
                        description: 'Available Ollama models',
                        mimeType: 'application/json'
                    },
                    {
                        uri: 'ollama://status',
                        name: 'Ollama Status',
                        description: 'Ollama server status',
                        mimeType: 'application/json'
                    }
                ]
            }
        };
    }

    async handleResourceRead(id, { uri }) {
        try {
            if (uri === 'ollama://models') {
                await this.loadAvailableModels();
                return {
                    jsonrpc: '2.0',
                    id,
                    result: {
                        contents: [{
                            uri,
                            mimeType: 'application/json',
                            text: JSON.stringify(this.models, null, 2)
                        }]
                    }
                };
            } else if (uri === 'ollama://status') {
                const status = await this.checkOllamaStatus();
                return {
                    jsonrpc: '2.0',
                    id,
                    result: {
                        contents: [{
                            uri,
                            mimeType: 'application/json',
                            text: JSON.stringify(status, null, 2)
                        }]
                    }
                };
            } else {
                return this.createError(id, 'RESOURCE_NOT_FOUND', `Unknown resource: ${uri}`);
            }
        } catch (error) {
            return this.createError(id, 'RESOURCE_READ_ERROR', error.message);
        }
    }

    async checkOllamaStatus() {
        try {
            const response = await axios.get(`${this.ollamaUrl}/api/version`);
            return {
                status: 'connected',
                version: response.data.version,
                url: this.ollamaUrl,
                models_count: this.models.length
            };
        } catch (error) {
            return {
                status: 'disconnected',
                error: error.message,
                url: this.ollamaUrl
            };
        }
    }

    createError(id, code, message) {
        return { jsonrpc: '2.0', id, error: { code, message } };
    }

    sendError(ws, code, message) {
        ws.send(JSON.stringify({
            jsonrpc: '2.0',
            error: { code, message }
        }));
    }
}

// Start the server if this file is run directly
if (require.main === module) {
    const port = process.env.PORT || 8080;
    const ollamaUrl = process.env.OLLAMA_URL || 'http://localhost:11434';
    
    console.log(`Starting Ollama MCP Server...`);
    console.log(`- Port: ${port}`);
    console.log(`- Ollama URL: ${ollamaUrl}`);
    
    try {
        new OllamaMCPServer(port, ollamaUrl);
    } catch (error) {
        console.error('Failed to start Ollama MCP Server:', error.message);
        process.exit(1);
    }
}

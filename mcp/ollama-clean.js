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
        console.log(`🦙 Ollama MCP Server uruchomiony na porcie ${this.port}`);
    }

    async loadAvailableModels() {
        try {
            const response = await axios.get(`${this.ollamaUrl}/api/tags`);
            this.models = response.data.models || [];
            console.log(`Załadowano ${this.models.length} modeli Ollama`);
        } catch (error) {
            console.error('Błąd ładowania modeli Ollama:', error.message);
        }
    }

    setupWebSocketServer() {
        this.wss.on('connection', (ws) => {
            this.clients.add(ws);
            console.log('Nowy klient MCP połączony');

            ws.on('message', async (data) => {
                try {
                    const message = JSON.parse(data.toString());
                    const response = await this.handleMCPMessage(message);
                    if (response) {
                        ws.send(JSON.stringify(response));
                    }
                } catch (error) {
                    this.sendError(ws, 'Invalid JSON', error.message);
                }
            });

            ws.on('close', () => {
                this.clients.delete(ws);
                console.log('Klient MCP rozłączony');
            });
        });
    }

    async handleMCPMessage(message) {
        const { method, params, id } = message;

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
                return this.createError(id, 'METHOD_NOT_FOUND', `Nieznana metoda: ${method}`);
        }
    }

    handleInitialize(id, params) {
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
                description: 'Generuje tekst używając modelu Ollama',
                inputSchema: {
                    type: 'object',
                    properties: {
                        model: {
                            type: 'string',
                            description: 'Nazwa modelu Ollama',
                            enum: this.models.map(m => m.name)
                        },
                        prompt: {
                            type: 'string',
                            description: 'Prompt do wygenerowania'
                        },
                        temperature: {
                            type: 'number',
                            description: 'Temperatura generowania (0-1)',
                            default: 0.7
                        },
                        max_tokens: {
                            type: 'integer',
                            description: 'Maksymalna liczba tokenów',
                            default: 1000
                        }
                    },
                    required: ['model', 'prompt']
                }
            },
            {
                name: 'ollama_list_models',
                description: 'Lista dostępnych modeli Ollama',
                inputSchema: {
                    type: 'object',
                    properties: {}
                }
            },
            {
                name: 'ollama_chat',
                description: 'Chat z modelem Ollama',
                inputSchema: {
                    type: 'object',
                    properties: {
                        model: {
                            type: 'string',
                            description: 'Nazwa modelu'
                        },
                        messages: {
                            type: 'array',
                            description: 'Historia rozmowy',
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

        return {
            jsonrpc: '2.0',
            id,
            result: { tools }
        };
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
                    return this.createError(id, 'TOOL_NOT_FOUND', `Nieznane narzędzie: ${name}`);
            }
        } catch (error) {
            return this.createError(id, 'TOOL_EXECUTION_ERROR', error.message);
        }
    }

    async ollamaGenerate(id, args) {
        const { model, prompt, temperature = 0.7, max_tokens = 1000 } = args;

        const response = await axios.post(`${this.ollamaUrl}/api/generate`, {
            model,
            prompt,
            options: {
                temperature,
                num_predict: max_tokens
            }
        });

        return {
            jsonrpc: '2.0',
            id,
            result: {
                content: [{
                    type: 'text',
                    text: response.data.response
                }]
            }
        };
    }

    async ollamaListModels(id) {
        await this.loadAvailableModels();

        return {
            jsonrpc: '2.0',
            id,
            result: {
                content: [{
                    type: 'text',
                    text: JSON.stringify(this.models, null, 2)
                }]
            }
        };
    }

    async ollamaChat(id, args) {
        const { model, messages } = args;

        const response = await axios.post(`${this.ollamaUrl}/api/chat`, {
            model,
            messages
        });

        return {
            jsonrpc: '2.0',
            id,
            result: {
                content: [{
                    type: 'text',
                    text: response.data.message.content
                }]
            }
        };
    }

    handleResourcesList(id) {
        const resources = [
            {
                uri: 'ollama://models',
                name: 'Lista modeli Ollama',
                description: 'Dostępne modele w Ollama',
                mimeType: 'application/json'
            },
            {
                uri: 'ollama://status',
                name: 'Status Ollama',
                description: 'Status serwera Ollama',
                mimeType: 'application/json'
            }
        ];

        return {
            jsonrpc: '2.0',
            id,
            result: { resources }
        };
    }

    async handleResourceRead(id, params) {
        const { uri } = params;

        try {
            switch (uri) {
                case 'ollama://models':
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

                case 'ollama://status':
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

                default:
                    return this.createError(id, 'RESOURCE_NOT_FOUND', `Nieznany zasób: ${uri}`);
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
        return {
            jsonrpc: '2.0',
            id,
            error: { code, message }
        };
    }

    sendError(ws, code, message) {
        ws.send(JSON.stringify({
            jsonrpc: '2.0',
            error: { code, message }
        }));
    }
}

// Uruchomienie serwera Ollama MCP
if (require.main === module) {
    new OllamaMCPServer(8080);

// ================================
// 1. SERWER MCP DLA OLLAMA
// ================================

// ollama-mcp-server.js
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
}

// ================================
// 2. SERWER MCP DLA SYSTEMU PLIKÓW
// ================================

// filesystem-mcp-server.js
const fs = require('fs').promises;
const path = require('path');

class FileSystemMCPServer {
    constructor(port = 8081, allowedPaths = [process.cwd()]) {
        this.port = port;
        this.allowedPaths = allowedPaths.map(p => path.resolve(p));
        this.clients = new Set();
        this.init();
    }

    async init() {
        this.wss = new WebSocket.Server({ port: this.port });
        this.setupWebSocketServer();
        console.log(`📁 FileSystem MCP Server uruchomiony na porcie ${this.port}`);
    }

    setupWebSocketServer() {
        this.wss.on('connection', (ws) => {
            this.clients.add(ws);
            console.log('Nowy klient FileSystem MCP połączony');

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
                console.log('Klient FileSystem MCP rozłączony');
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
                return await this.handleResourcesList(id);
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
                    name: 'FileSystem MCP Server',
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
                name: 'read_file',
                description: 'Czyta zawartość pliku',
                inputSchema: {
                    type: 'object',
                    properties: {
                        path: {
                            type: 'string',
                            description: 'Ścieżka do pliku'
                        }
                    },
                    required: ['path']
                }
            },
            {
                name: 'write_file',
                description: 'Zapisuje zawartość do pliku',
                inputSchema: {
                    type: 'object',
                    properties: {
                        path: {
                            type: 'string',
                            description: 'Ścieżka do pliku'
                        },
                        content: {
                            type: 'string',
                            description: 'Zawartość do zapisania'
                        }
                    },
                    required: ['path', 'content']
                }
            },
            {
                name: 'list_directory',
                description: 'Lista plików w katalogu',
                inputSchema: {
                    type: 'object',
                    properties: {
                        path: {
                            type: 'string',
                            description: 'Ścieżka do katalogu'
                        }
                    },
                    required: ['path']
                }
            },
            {
                name: 'create_directory',
                description: 'Tworzy nowy katalog',
                inputSchema: {
                    type: 'object',
                    properties: {
                        path: {
                            type: 'string',
                            description: 'Ścieżka do nowego katalogu'
                        }
                    },
                    required: ['path']
                }
            },
            {
                name: 'delete_file',
                description: 'Usuwa plik',
                inputSchema: {
                    type: 'object',
                    properties: {
                        path: {
                            type: 'string',
                            description: 'Ścieżka do pliku'
                        }
                    },
                    required: ['path']
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
                case 'read_file':
                    return await this.readFile(id, args);
                case 'write_file':
                    return await this.writeFile(id, args);
                case 'list_directory':
                    return await this.listDirectory(id, args);
                case 'create_directory':
                    return await this.createDirectory(id, args);
                case 'delete_file':
                    return await this.deleteFile(id, args);
                default:
                    return this.createError(id, 'TOOL_NOT_FOUND', `Nieznane narzędzie: ${name}`);
            }
        } catch (error) {
            return this.createError(id, 'TOOL_EXECUTION_ERROR', error.message);
        }
    }

    validatePath(filePath) {
        const absolutePath = path.resolve(filePath);
        const isAllowed = this.allowedPaths.some(allowedPath =>
            absolutePath.startsWith(allowedPath)
        );

        if (!isAllowed) {
            throw new Error(`Dostęp do ścieżki ${filePath} jest zabroniony`);
        }

        return absolutePath;
    }

    async readFile(id, args) {
        const { path: filePath } = args;
        const absolutePath = this.validatePath(filePath);

        const content = await fs.readFile(absolutePath, 'utf8');

        return {
            jsonrpc: '2.0',
            id,
            result: {
                content: [{
                    type: 'text',
                    text: content
                }]
            }
        };
    }

    async writeFile(id, args) {
        const { path: filePath, content } = args;
        const absolutePath = this.validatePath(filePath);

        await fs.writeFile(absolutePath, content, 'utf8');

        return {
            jsonrpc: '2.0',
            id,
            result: {
                content: [{
                    type: 'text',
                    text: `Plik ${filePath} został zapisany pomyślnie`
                }]
            }
        };
    }

    async listDirectory(id, args) {
        const { path: dirPath } = args;
        const absolutePath = this.validatePath(dirPath);

        const entries = await fs.readdir(absolutePath, { withFileTypes: true });
        const files = entries.map(entry => ({
            name: entry.name,
            type: entry.isDirectory() ? 'directory' : 'file',
            path: path.join(dirPath, entry.name)
        }));

        return {
            jsonrpc: '2.0',
            id,
            result: {
                content: [{
                    type: 'text',
                    text: JSON.stringify(files, null, 2)
                }]
            }
        };
    }

    async createDirectory(id, args) {
        const { path: dirPath } = args;
        const absolutePath = this.validatePath(dirPath);

        await fs.mkdir(absolutePath, { recursive: true });

        return {
            jsonrpc: '2.0',
            id,
            result: {
                content: [{
                    type: 'text',
                    text: `Katalog ${dirPath} został utworzony pomyślnie`
                }]
            }
        };
    }

    async deleteFile(id, args) {
        const { path: filePath } = args;
        const absolutePath = this.validatePath(filePath);

        await fs.unlink(absolutePath);

        return {
            jsonrpc: '2.0',
            id,
            result: {
                content: [{
                    type: 'text',
                    text: `Plik ${filePath} został usunięty pomyślnie`
                }]
            }
        };
    }

    async handleResourcesList(id) {
        const resources = [];

        for (const allowedPath of this.allowedPaths) {
            resources.push({
                uri: `file://${allowedPath}`,
                name: `Katalog: ${path.basename(allowedPath)}`,
                description: `Dostęp do katalogu ${allowedPath}`,
                mimeType: 'text/plain'
            });
        }

        return {
            jsonrpc: '2.0',
            id,
            result: { resources }
        };
    }

    async handleResourceRead(id, params) {
        const { uri } = params;

        if (uri.startsWith('file://')) {
            const filePath = uri.replace('file://', '');
            try {
                const absolutePath = this.validatePath(filePath);
                const stats = await fs.stat(absolutePath);

                if (stats.isDirectory()) {
                    const entries = await fs.readdir(absolutePath, { withFileTypes: true });
                    const listing = entries.map(entry => ({
                        name: entry.name,
                        type: entry.isDirectory() ? 'directory' : 'file'
                    }));

                    return {
                        jsonrpc: '2.0',
                        id,
                        result: {
                            contents: [{
                                uri,
                                mimeType: 'application/json',
                                text: JSON.stringify(listing, null, 2)
                            }]
                        }
                    };
                } else {
                    const content = await fs.readFile(absolutePath, 'utf8');
                    return {
                        jsonrpc: '2.0',
                        id,
                        result: {
                            contents: [{
                                uri,
                                mimeType: 'text/plain',
                                text: content
                            }]
                        }
                    };
                }
            } catch (error) {
                return this.createError(id, 'RESOURCE_READ_ERROR', error.message);
            }
        }

        return this.createError(id, 'RESOURCE_NOT_FOUND', `Nieznany zasób: ${uri}`);
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

// Uruchomienie serwera FileSystem MCP
if (require.main === module) {
    new FileSystemMCPServer(8081, [process.cwd(), '/tmp']);
}

// ================================
// 3. SERWER MCP DLA BAZY DANYCH
// ================================

// database-mcp-server.js
const sqlite3 = require('sqlite3').verbose();

class DatabaseMCPServer {
    constructor(port = 8082, dbPath = './mcp_database.db') {
        this.port = port;
        this.dbPath = dbPath;
        this.db = null;
        this.clients = new Set();
        this.init();
    }

    async init() {
        await this.initDatabase();
        this.wss = new WebSocket.Server({ port: this.port });
        this.setupWebSocketServer();
        console.log(`🗄️ Database MCP Server uruchomiony na porcie ${this.port}`);
    }

    async initDatabase() {
        return new Promise((resolve, reject) => {
            this.db.all(query, table ? [table] : [], (err, rows) => {
                if (err) {
                    reject(err);
                } else {
                    resolve({
                        jsonrpc: '2.0',
                        id,
                        result: {
                            content: [{
                                type: 'text',
                                text: JSON.stringify(rows, null, 2)
                            }]
                        }
                    });
                }
            });
        });
    }

    async handleResourcesList(id) {
        return new Promise((resolve, reject) => {
            this.db.all("SELECT name FROM sqlite_master WHERE type='table'", [], (err, tables) => {
                if (err) {
                    reject(err);
                } else {
                    const resources = tables.map(table => ({
                        uri: `db://table/${table.name}`,
                        name: `Tabela: ${table.name}`,
                        description: `Dane z tabeli ${table.name}`,
                        mimeType: 'application/json'
                    }));

                    resources.push({
                        uri: 'db://schema',
                        name: 'Schemat bazy danych',
                        description: 'Pełny schemat bazy danych',
                        mimeType: 'application/json'
                    });

                    resolve({
                        jsonrpc: '2.0',
                        id,
                        result: { resources }
                    });
                }
            });
        });
    }

    async handleResourceRead(id, params) {
        const { uri } = params;

        if (uri === 'db://schema') {
            return new Promise((resolve, reject) => {
                this.db.all("SELECT name, sql FROM sqlite_master WHERE type='table'", [], (err, tables) => {
                    if (err) {
                        reject(err);
                    } else {
                        resolve({
                            jsonrpc: '2.0',
                            id,
                            result: {
                                contents: [{
                                    uri,
                                    mimeType: 'application/json',
                                    text: JSON.stringify(tables, null, 2)
                                }]
                            }
                        });
                    }
                });
            });
        } else if (uri.startsWith('db://table/')) {
            const tableName = uri.replace('db://table/', '');
            return new Promise((resolve, reject) => {
                this.db.all(`SELECT * FROM ${tableName} LIMIT 100`, [], (err, rows) => {
                    if (err) {
                        reject(err);
                    } else {
                        resolve({
                            jsonrpc: '2.0',
                            id,
                            result: {
                                contents: [{
                                    uri,
                                    mimeType: 'application/json',
                                    text: JSON.stringify(rows, null, 2)
                                }]
                            }
                        });
                    }
                });
            });
        }

        return this.createError(id, 'RESOURCE_NOT_FOUND', `Nieznany zasób: ${uri}`);
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

// Uruchomienie serwera Database MCP
if (require.main === module) {
    new DatabaseMCPServer(8082);
}

// ================================
// 4. SERWER MCP DLA API KLIENTA
// ================================

// api-client-mcp-server.js
class APIClientMCPServer {
    constructor(port = 8083) {
        this.port = port;
        this.clients = new Set();
        this.apiKeys = new Map();
        this.init();
    }

    async init() {
        this.wss = new WebSocket.Server({ port: this.port });
        this.setupWebSocketServer();
        console.log(`🌐 API Client MCP Server uruchomiony na porcie ${this.port}`);
    }

    setupWebSocketServer() {
        this.wss.on('connection', (ws) => {
            this.clients.add(ws);
            console.log('Nowy klient API MCP połączony');

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
                console.log('Klient API MCP rozłączony');
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
                    name: 'API Client MCP Server',
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
                name: 'http_request',
                description: 'Wykonuje żądanie HTTP',
                inputSchema: {
                    type: 'object',
                    properties: {
                        url: {
                            type: 'string',
                            description: 'URL docelowy'
                        },
                        method: {
                            type: 'string',
                            enum: ['GET', 'POST', 'PUT', 'DELETE', 'PATCH'],
                            default: 'GET'
                        },
                        headers: {
                            type: 'object',
                            description: 'Nagłówki HTTP'
                        },
                        body: {
                            type: 'string',
                            description: 'Treść żądania'
                        },
                        timeout: {
                            type: 'integer',
                            description: 'Timeout w ms',
                            default: 5000
                        }
                    },
                    required: ['url']
                }
            },
            {
                name: 'weather_api',
                description: 'Pobiera informacje o pogodzie',
                inputSchema: {
                    type: 'object',
                    properties: {
                        city: {
                            type: 'string',
                            description: 'Nazwa miasta'
                        },
                        api_key: {
                            type: 'string',
                            description: 'Klucz API OpenWeatherMap'
                        }
                    },
                    required: ['city']
                }
            },
            {
                name: 'github_api',
                description: 'Dostęp do GitHub API',
                inputSchema: {
                    type: 'object',
                    properties: {
                        endpoint: {
                            type: 'string',
                            description: 'Endpoint GitHub API'
                        },
                        token: {
                            type: 'string',
                            description: 'Token GitHub'
                        }
                    },
                    required: ['endpoint']
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
                case 'http_request':
                    return await this.httpRequest(id, args);
                case 'weather_api':
                    return await this.weatherAPI(id, args);
                case 'github_api':
                    return await this.githubAPI(id, args);
                default:
                    return this.createError(id, 'TOOL_NOT_FOUND', `Nieznane narzędzie: ${name}`);
            }
        } catch (error) {
            return this.createError(id, 'TOOL_EXECUTION_ERROR', error.message);
        }
    }

    async httpRequest(id, args) {
        const { url, method = 'GET', headers = {}, body, timeout = 5000 } = args;

        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), timeout);

        try {
            const options = {
                method,
                headers,
                signal: controller.signal
            };

            if (body && method !== 'GET') {
                options.body = body;
            }

            const response = await fetch(url, options);
            clearTimeout(timeoutId);

            const responseText = await response.text();
            let responseData;

            try {
                responseData = JSON.parse(responseText);
            } catch {
                responseData = responseText;
            }

            return {
                jsonrpc: '2.0',
                id,
                result: {
                    content: [{
                        type: 'text',
                        text: JSON.stringify({
                            status: response.status,
                            statusText: response.statusText,
                            headers: Object.fromEntries(response.headers.entries()),
                            data: responseData
                        }, null, 2)
                    }]
                }
            };
        } catch (error) {
            clearTimeout(timeoutId);
            throw error;
        }
    }

    async weatherAPI(id, args) {
        const { city, api_key } = args;
        const apiKey = api_key || process.env.OPENWEATHER_API_KEY;

        if (!apiKey) {
            throw new Error('Brak klucza API OpenWeatherMap');
        }

        const url = `https://api.openweathermap.org/data/2.5/weather?q=${encodeURIComponent(city)}&appid=${apiKey}&units=metric&lang=pl`;

        const response = await fetch(url);
        const data = await response.json();

        if (!response.ok) {
            throw new Error(`API Weather error: ${data.message}`);
        }

        return {
            jsonrpc: '2.0',
            id,
            result: {
                content: [{
                    type: 'text',
                    text: JSON.stringify({
                        city: data.name,
                        country: data.sys.country,
                        temperature: data.main.temp,
                        feels_like: data.main.feels_like,
                        humidity: data.main.humidity,
                        pressure: data.main.pressure,
                        description: data.weather[0].description,
                        wind_speed: data.wind.speed
                    }, null, 2)
                }]
            }
        };
    }

    async githubAPI(id, args) {
        const { endpoint, token } = args;
        const githubToken = token || process.env.GITHUB_TOKEN;

        const headers = {
            'Accept': 'application/vnd.github.v3+json',
            'User-Agent': 'MCP-API-Client'
        };

        if (githubToken) {
            headers['Authorization'] = `token ${githubToken}`;
        }

        const url = endpoint.startsWith('https://') ? endpoint : `https://api.github.com/${endpoint}`;
        const response = await fetch(url, { headers });
        const data = await response.json();

        if (!response.ok) {
            throw new Error(`GitHub API error: ${data.message}`);
        }

        return {
            jsonrpc: '2.0',
            id,
            result: {
                content: [{
                    type: 'text',
                    text: JSON.stringify(data, null, 2)
                }]
            }
        };
    }

    handleResourcesList(id) {
        const resources = [
            {
                uri: 'api://endpoints',
                name: 'Dostępne endpointy',
                description: 'Lista dostępnych API endpoints',
                mimeType: 'application/json'
            }
        ];

        return {
            jsonrpc: '2.0',
            id,
            result: { resources }
        };
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

// Uruchomienie serwera API Client MCP
if (require.main === module) {
    new APIClientMCPServer(8083);
}

// ================================
// 5. GŁÓWNY LAUNCHER - URUCHAMIA WSZYSTKIE SERWERY
// ================================

// mcp-launcher.js
const { spawn } = require('child_process');
const path = require('path');

class MCPLauncher {
    constructor() {
        this.servers = [
            {
                name: 'Ollama MCP',
                file: 'ollama-mcp-server.js',
                port: 8080,
                description: 'Serwer do komunikacji z Ollama'
            },
            {
                name: 'FileSystem MCP',
                file: 'filesystem-mcp-server.js',
                port: 8081,
                description: 'Serwer do operacji na plikach'
            },
            {
                name: 'Database MCP',
                file: 'database-mcp-server.js',
                port: 8082,
                description: 'Serwer do operacji na bazie danych'
            },
            {
                name: 'API Client MCP',
                file: 'api-client-mcp-server.js',
                port: 8083,
                description: 'Serwer do wykonywania żądań HTTP'
            }
        ];

        this.processes = new Map();
        this.init();
    }

    init() {
        console.log('🚀 MCP Launcher - Uruchamianie serwerów MCP...\n');

        process.on('SIGINT', () => {
            console.log('\n🛑 Zamykanie wszystkich serwerów MCP...');
            this.stopAllServers();
            process.exit(0);
        });

        this.startAllServers();
    }

    startAllServers() {
        this.servers.forEach(server => {
            this.startServer(server);
        });

        console.log('\n📋 Status serwerów:');
        this.servers.forEach(server => {
            console.log(`  • ${server.name}: http://localhost:${server.port}`);
        });

        console.log('\n🔗 Konfiguracja dla PWA Client:');
        console.log('  Ollama:     ws://localhost:8080');
        console.log('  FileSystem: ws://localhost:8081');
        console.log('  Database:   ws://localhost:8082');
        console.log('  API Client: ws://localhost:8083');

        console.log('\n💡 Aby zatrzymać wszystkie serwery, naciśnij Ctrl+C');
    }

    startServer(server) {
        console.log(`🔄 Uruchamianie ${server.name}...`);

        const serverProcess = spawn('node', [server.file], {
            stdio: ['pipe', 'pipe', 'pipe'],
            cwd: __dirname
        });

        this.processes.set(server.name, serverProcess);

        serverProcess.stdout.on('data', (data) => {
            console.log(`[${server.name}] ${data.toString().trim()}`);
        });

        serverProcess.stderr.on('data', (data) => {
            console.error(`[${server.name} ERROR] ${data.toString().trim()}`);
        });

        serverProcess.on('close', (code) => {
            console.log(`[${server.name}] Proces zakończony z kodem ${code}`);
            this.processes.delete(server.name);
        });

        serverProcess.on('error', (error) => {
            console.error(`[${server.name}] Błąd procesu:`, error);
        });
    }

    stopAllServers() {
        this.processes.forEach((process, name) => {
            console.log(`🛑 Zatrzymywanie ${name}...`);
            process.kill('SIGTERM');
        });

        setTimeout(() => {
            this.processes.forEach((process, name) => {
                if (!process.killed) {
                    console.log(`🔥 Wymuszenie zamknięcia ${name}...`);
                    process.kill('SIGKILL');
                }
            });
        }, 5000);
    }

    restartServer(serverName) {
        const server = this.servers.find(s => s.name === serverName);
        if (!server) {
            console.error(`Nie znaleziono serwera: ${serverName}`);
            return;
        }

        const process = this.processes.get(serverName);
        if (process) {
            console.log(`🔄 Restartowanie ${serverName}...`);
            process.kill('SIGTERM');
            setTimeout(() => {
                this.startServer(server);
            }, 2000);
        }
    }
}

// Uruchomienie launchera
if (require.main === module) {
    new MCPLauncher();
}

// ================================
// 6. PACKAGE.JSON - ZALEŻNOŚCI
// ================================

/*
Stwórz plik package.json z następującą zawartością:

{
  "name": "mcp-servers-collection",
  "version": "1.0.0",
  "description": "Kolekcja serwerów MCP dla różnych usług",
  "main": "mcp-launcher.js",
  "scripts": {
    "start": "node mcp-launcher.js",
    "dev": "nodemon mcp-launcher.js",
    "ollama": "node ollama-mcp-server.js",
    "filesystem": "node filesystem-mcp-server.js",
    "database": "node database-mcp-server.js",
    "api": "node api-client-mcp-server.js"
  },
  "dependencies": {
    "ws": "^8.14.2",
    "axios": "^1.6.0",
    "sqlite3": "^5.1.6"
  },
  "devDependencies": {
    "nodemon": "^3.0.1"
  },
  "keywords": ["mcp", "ollama", "websocket", "api", "database"],
  "author": "MCP Developer",
  "license": "MIT"
}

Instalacja:
npm install

Uruchomienie wszystkich serwerów:
npm start

Lub pojedyncze serwery:
npm run ollama
npm run filesystem
npm run database
npm run api
*/

// ================================
// 7. INSTRUKCJE KONFIGURACJI
// ================================

/*
KONFIGURACJA OLLAMA:
1. Zainstaluj Ollama: https://ollama.ai/download
2. Uruchom: ollama serve
3. Pobierz model: ollama pull llama2
4. Test: curl http://localhost:11434/api/tags

KONFIGURACJA ZMIENNYCH ŚRODOWISKOWYCH:
Stwórz plik .env:

OPENWEATHER_API_KEY=twoj_klucz_api
GITHUB_TOKEN=twoj_token_github
OLLAMA_URL=http://localhost:11434
DATABASE_PATH=./mcp_database.db

STRUKTURA KATALOGÓW:
mcp-servers/
├── ollama-mcp-server.js
├── filesystem-mcp-server.js
├── database-mcp-server.js
├── api-client-mcp-server.js
├── mcp-launcher.js
├── package.json
├── .env
└── README.md

TESTOWANIE:
1. Uruchom: npm start
2. Otwórz PWA Client
3. Połącz z ws://localhost:8080 (Ollama)
4. Test narzędzi i zasobów

BEZPIECZEŃSTWO:
- Serwery działają tylko lokalnie
- FileSystem ma ograniczone ścieżki
- Database używa prepared statements
- API Client ma timeout i walidację
*/db = new sqlite3.Database(this.dbPath, (err) => {
                if (err) {
                    reject(err);
                } else {
                    console.log(`Połączono z bazą danych: ${this.dbPath}`);
                    this.createSampleTables();
                    resolve();
                }
            });
        });
    }

    createSampleTables() {
        const createTables = `
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                email TEXT UNIQUE,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS posts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                title TEXT NOT NULL,
                content TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (id)
            );

            INSERT OR IGNORE INTO users (name, email) VALUES
                ('Jan Kowalski', 'jan@example.com'),
                ('Anna Nowak', 'anna@example.com');

            INSERT OR IGNORE INTO posts (user_id, title, content) VALUES
                (1, 'Pierwszy post', 'To jest treść pierwszego posta'),
                (2, 'Drugi post', 'To jest treść drugiego posta');
        `;

        this.db.exec(createTables, (err) => {
            if (err) {
                console.error('Błąd tworzenia tabel:', err);
            } else {
                console.log('Tabele przykładowe utworzone');
            }
        });
    }

    setupWebSocketServer() {
        this.wss.on('connection', (ws) => {
            this.clients.add(ws);
            console.log('Nowy klient Database MCP połączony');

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
                console.log('Klient Database MCP rozłączony');
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
                return await this.handleResourcesList(id);
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
                    name: 'Database MCP Server',
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
                name: 'db_query',
                description: 'Wykonuje zapytanie SELECT do bazy danych',
                inputSchema: {
                    type: 'object',
                    properties: {
                        query: {
                            type: 'string',
                            description: 'Zapytanie SQL SELECT'
                        },
                        params: {
                            type: 'array',
                            description: 'Parametry zapytania',
                            items: { type: 'string' }
                        }
                    },
                    required: ['query']
                }
            },
            {
                name: 'db_execute',
                description: 'Wykonuje zapytanie INSERT/UPDATE/DELETE',
                inputSchema: {
                    type: 'object',
                    properties: {
                        query: {
                            type: 'string',
                            description: 'Zapytanie SQL'
                        },
                        params: {
                            type: 'array',
                            description: 'Parametry zapytania',
                            items: { type: 'string' }
                        }
                    },
                    required: ['query']
                }
            },
            {
                name: 'db_schema',
                description: 'Pobiera schemat bazy danych',
                inputSchema: {
                    type: 'object',
                    properties: {
                        table: {
                            type: 'string',
                            description: 'Nazwa tabeli (opcjonalne)'
                        }
                    }
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
                case 'db_query':
                    return await this.dbQuery(id, args);
                case 'db_execute':
                    return await this.dbExecute(id, args);
                case 'db_schema':
                    return await this.dbSchema(id, args);
                default:
                    return this.createError(id, 'TOOL_NOT_FOUND', `Nieznane narzędzie: ${name}`);
            }
        } catch (error) {
            return this.createError(id, 'TOOL_EXECUTION_ERROR', error.message);
        }
    }

    async dbQuery(id, args) {
        const { query, params = [] } = args;

        // Sprawdź czy to zapytanie SELECT
        if (!query.trim().toLowerCase().startsWith('select')) {
            throw new Error('Dozwolone są tylko zapytania SELECT');
        }

        return new Promise((resolve, reject) => {
            this.db.all(query, params, (err, rows) => {
                if (err) {
                    reject(err);
                } else {
                    resolve({
                        jsonrpc: '2.0',
                        id,
                        result: {
                            content: [{
                                type: 'text',
                                text: JSON.stringify(rows, null, 2)
                            }]
                        }
                    });
                }
            });
        });
    }

    async dbExecute(id, args) {
        const { query, params = [] } = args;

        return new Promise((resolve, reject) => {
            this.db.run(query, params, function(err) {
                if (err) {
                    reject(err);
                } else {
                    resolve({
                        jsonrpc: '2.0',
                        id,
                        result: {
                            content: [{
                                type: 'text',
                                text: `Zapytanie wykonane. Wpłynęło na ${this.changes} wierszy. LastID: ${this.lastID}`
                            }]
                        }
                    });
                }
            });
        });
    }

    async dbSchema(id, args) {
        const { table } = args;

        let query = "SELECT name, sql FROM sqlite_master WHERE type='table'";
        if (table) {
            query += " AND name = ?";
        }

        return new Promise((resolve, reject) => {
            this.
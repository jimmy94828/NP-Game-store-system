# Game Store System - NP HW3
#### 112550047 徐瑋晨
在這次的作業中，我基於HW1和HW2所設計的遊戲和client/server架構建構出一個遊戲商城系統，此遊戲商城系統可以讓開發者開發遊戲並上傳到遊戲商城，開發者也可以在需要時更新或移除自己所上架的遊戲。而玩家則是可以在遊戲商城中瀏覽各個已經上架的遊戲，也可以下載自己想玩的遊戲並創立房間邀請其他玩家一起共同遊玩遊戲。

## Table of Contents
- [System Overview](#-system-overview)
- [Start System](#-start-system)
- [Installation](#-installation)
- [Server Deployment](#-server-deployment)
- [Client Usage](#-client-usage)
- [System Architecture](#-system-architecture)
- [Network Protocol](#-network-protocol)
- [Demo Instructions](#-demo-instructions)
- [Troubleshooting](#-troubleshooting)

## System Overview

此遊戲商城系統主要可以分成三大部分，包含server端、client端和遊戲:

### **Server端** 
- **Database Server** 
   Database server 會跑在server 140.113.17.11，而port是設定為17047
   Database server主要負責所有關於資料庫的create, read, update, delete和query的處理，當database server收到來自lobby server或developer server對於資料庫的操作請求時，database server會檢查request的內容來判斷各個request是要對哪個欄位進行什麼操作，再根據request進行資料庫操作並回傳結果。database 會以.json的形式儲存，其中包含User、Gamelog、developer、game欄位，分別儲存玩家資訊、遊戲紀錄、開發者資訊和遊戲詳情。
- **Lobby Server** 
   Lobby server 會跑在server 140.113.17.11上，而port是設定成17048
   Lobby server主要負責處理玩家的所有操作與需求，會接收來自lobby_client的request判斷需要針對database做什麼操作或是是否要啟動遊戲，再根據玩家的request傳送相對應的database request到database server，當玩家的每個request被lobby server處理完後，lobby server會回傳成功或是錯誤訊息給送出request的玩家。
- **Developer Server** 
   Developer server 會跑在server 140.113.17.11上，而port是設定成17049
   Developer server主要負責處理開發者的所有操作，包含創建遊戲、修改或上架遊戲、瀏覽詳細的遊戲資訊。Developer server匯處理developer相關的所有操作，並接收來自於developer發出的request，當developer server接收到來自developer發出的request時，會判斷每個request是關於什麼操作，如果request牽涉到database的create, read, update, delete, query，則developer會發送相對應的database request到database server進行資料庫操作。當developer server處理完每個request後，會根據職結果回傳相對應的訊息給發出request的developer。
### **Client端**
- **Player Client**: Browse games, create/join rooms, play games, rate & review
- **Developer Client**: Upload games, manage versions, create from templates

### **Supported Games**
- **Connect Four** (2 players, CLI): Classic strategy game
- **Multiplayer Bingo** (3-5 players, CLI): Dynamic player count Bingo game
- **Tetris Battle** (2 players, GUI): Competitive Tetris with pygame

**Note**: GUI games require `pygame` installation on player's machine.

---

## Start System

### For TAs (Demo Setup)

```bash
# 1. Clone repository
git clone <repository-url>
cd test

# 2. Install pygame (required for GUI games like Tetris)
pip3 install pygame

# 3. Update connection settings (if needed)
# Edit player/lobby_client.py and developer/developer_client.py
# Change LOBBYSERVER_HOST and DEVELOPER_SERVER_HOST to server IP

# 4. Start Player Client
./start_player.py

# 5. Start Developer Client (in another terminal)
./start_developer.py
```

**Dependencies**: 
- Python 3.8+ (standard library only for server/CLI games)
- pygame (required for GUI games like Tetris)

---

## Installation

### Prerequisites
- **Python 3.8+**
- **Linux/macOS/Windows** with WSL
- **Network connectivity** to server

### Required Packages

#### For Players (GUI Games)
If you want to play **GUI games** like Tetris, you need pygame:

```bash
# Install pygame for GUI games
pip3 install pygame
```

#### For Developers/Servers
No external packages required - uses only Python standard library.

### Environment Setup

```bash
# Verify Python version
python3 --version

# Make scripts executable
chmod +x start_server.py start_player.py start_developer.py

# Optional: Create virtual environment (recommended)
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install pygame if playing GUI games
pip3 install pygame
```

### Quick Installation Script

```bash
# All-in-one setup
chmod +x start_*.py && pip3 install pygame
```

---

## Server Deployment

### Deployment on Linux Machine (140.113.203.91)

#### 1. Initial Setup
```bash
# SSH to server
ssh <username>@140.113.203.91

# Navigate to project directory
cd /path/to/test

# Make server executable
chmod +x start_server.py
```

#### 2. Start All Servers
```bash
# Start in background with nohup (survives SSH disconnection)
nohup ./start_server.py > server.log 2>&1 &

# Or use screen/tmux for persistent session
screen -S gameserver
./start_server.py
# Press Ctrl+A, D to detach
```

#### 3. Verify Server Status
```bash
# Check if servers are running
ps aux | grep "start_server.py"

# Check ports are listening
netstat -tuln | grep -E "17047|17048|17049"

# View logs
tail -f server.log
```

#### 4. Clear Database (Before Demo)
```bash
# Remove database file
rm -f database.json
# Server will create fresh database.json on restart
```

#### 5. Server Management
```bash
# Stop servers
pkill -f start_server.py

# Restart servers
./start_server.py

# Check server health
curl http://localhost:17048  # Should show connection
```

### Server Configuration

Default ports (edit in respective files if needed):
- `server/database_server.py`: Port 17047
- `server/lobby_server.py`: Port 17048
- `server/developer_server.py`: Port 17049

---

## Client Usage

### Player Client

```bash
./start_player.py
```

#### Connection Settings
Edit `player/lobby_client.py` if server is on different host:
```python
LOBBYSERVER_HOST = '140.113.203.91'  # Change to your server IP
LOBBYSERVER_PORT = 17048
```

#### Player Features
1. **Register/Login**: Create account or login
2. **Browse Store**: View available games with ratings
3. **Download Games**: Get latest game versions
4. **Create Room**: Host a game session
5. **Join Room**: Join existing game rooms
6. **Start Game**: Launch game when room is full
7. **Rate & Review**: Submit feedback (only after playing)
8. **View Game Logs**: Check match history

#### Example Flow
```
1. Register account (user1)
2. Browse store → Select "Connect Four"
3. Download game
4. Create room → Select "Connect Four"
5. Wait for player 2 to join
6. Start game
7. Play Connect Four
8. Rate game after completion
```

### Developer Client

```bash
./start_developer.py
```

#### Connection Settings
Edit `developer/developer_client.py` if server is on different host:
```python
DEVELOPER_SERVER_HOST = '140.113.203.91'  # Change to your server IP
DEVELOPER_SERVER_PORT = 17049
```

#### Developer Features
1. **Register/Login**: Create developer account
2. **Upload Game**: Upload new game with config
3. **Update Game**: Push new version
4. **List Games**: View published games
5. **Remove Game**: Delist game
6. **Create Template**: Generate game skeleton

#### Upload Game Workflow
```
1. Login as developer
2. Create game folder in developer/games/<dev_name>/<game_name>/
3. Add required files:
   - config.json (game metadata)
   - <server_file>.py (game server)
   - <main_file>.py (game client)
4. Select "Upload Game" → Choose game folder
5. Configure metadata (name, version, description, etc.)
6. System validates files and config
7. Upload completed → Players can download
```

#### Config.json Format
```json
{
  "name": "Game Name",
  "version": "1.0.0",
  "gameType": "CLI",
  "maxPlayers": 2,
  "description": "Game description",
  "mainFile": "game_client.py",
  "serverFile": "game_server.py"
}
```

**Validation Rules:**
- Version must be `x.y.z` format
- `mainFile` and `serverFile` must exist
- `maxPlayers` must be positive integer
- All fields are required

---

## System Architecture

### Component Diagram
```
┌─────────────────────────────────────────────────────────┐
│                    Client Side (Local)                  │
├──────────────────────────┬──────────────────────────────┤
│   Player Client          │   Developer Client           │
│   - lobby_client.py      │   - developer_client.py      │
│   - Browse/Download      │   - Upload/Update games      │
│   - Room Management      │   - Version control          │
│   - Start game           |   - Template creation        |
|   - Review and rating    │                              │
└───────────┬──────────────┴─────────────┬────────────────┘
            │                            │
            │ TCP/IP + JSON Protocol     │
            │                            │
┌───────────▼────────────────────────────▼────────────────┐
│              Server Side (140.113.203.91)               │
├──────────────────┬────────────────┬─────────────────────┤
│  Database Server │  Lobby Server  │ Developer Server    │
│  Port: 17047     │  Port: 17048   │ Port: 17049         │
│  - JSON storage  │  - Rooms       │ - Game upload       │
│  - CRUD ops      │  - GameServers │ - File transfer     │
│  - LPFP protocol │  - Port pool   │ - Version mgmt      │
└──────────────────┴────────────────┴─────────────────────┘
                           │
                           │ Spawns game instances
                           ▼
            ┌──────────────────────────────┐
            │   Dynamic Game Servers       │
            │   Ports: 10100-11000         │
            │   - Per-match instances      │
            │   - Auto-cleanup on end      │
            └──────────────────────────────┘
```

### Data Flow

#### 1. Game Upload (Developer → Server)
```
Developer Client → Developer Server → Database Server
                 ↓ (stores files)
              server/games/<dev>/<game>/<version>/
```

#### 2. Game Download (Player → Server)
```
Player Client → Lobby Server → reads from server/games/
            ← file transfer ← 
```

#### 3. Game Matchmaking
```
Player 1: Create Room → Lobby Server (assigns port from pool)
Player 2: Join Room → Lobby Server (adds to room)
Host: Start Game → Lobby Server spawns GameServer on assigned port
            ↓
    GameServer (port 10100-11000)
            ↓
Players connect directly → Game logic executes
            ↓
Game ends → Results to Lobby → Write to Database → GameLog
```

### Module Breakdown

#### Server Side
- **`server/database_server.py`**: JSON persistence, LPFP protocol
- **`server/lobby_server.py`**: Room management, game orchestration
- **`server/developer_server.py`**: Game upload/update handling

#### Player Side
- **`player/lobby_client.py`**: Main player interface
- **`player/games/<game>/<game_client.py>`**: Downloaded game clients

#### Developer Side
- **`developer/developer_client.py`**: Developer interface
- **`developer/games/<dev>/<game>/`**: Game development folders
- **`developer/template/`**: Game skeleton templates

#### Game Servers
- **`developer/games/<dev>/<game>/<server>.py`**: Game server logic
- Launched dynamically by Lobby Server
- Clean up after match ends

---

##  Network Protocol

### LPFP Protocol (Length-Prefixed Framing Protocol)

All client-server communication uses LPFP:

```
┌─────────────┬──────────────────────────┐
│   Header    │         Payload          │
│  4 bytes    │       N bytes            │
│ (uint32_t)  │    (JSON UTF-8)          │
└─────────────┴──────────────────────────┘
```

#### Message Format
- **Header**: 4-byte unsigned integer (network byte order)
- **Payload**: JSON object encoded in UTF-8
- **Max Size**: 65536 bytes per message

#### Example Messages

**Player Login:**
```json
{
  "command": "login",
  "username": "player1",
  "password": "hashed_password"
}
```

**Create Room:**
```json
{
  "command": "create_room",
  "userId": "player1",
  "gameId": "game_123"
}
```

**Game State Update:**
```json
{
  "type": "game_state",
  "current_player": 1,
  "board": [[0,0,0], ...],
  "winner": null
}
```

### Error Handling
- **Connection Lost**: Client shows error, returns to menu
- **Invalid Message**: Server sends error response with message
- **Timeout**: 30-second socket timeout on operations
- **Port Exhaustion**: Lobby queues room creation

---

## Demo Instructions

### Pre-Demo Checklist

#### For Developer (You)
1. ✅ **Deploy servers** on 140.113.203.91
2. ✅ **Clear database**: `./clear_database.py`
3. ✅ **Verify servers running**: Check ports 17047, 17048, 17049
4. ✅ **Test connectivity**: From local machine to server
5. ✅ **Push to GitHub**: All code with clear README
6. ✅ **Submit GitHub link** to E3 before demo

#### For TAs
1. **Clone repository** from GitHub
2. **Update connection settings** (if needed)
   - Edit `player/lobby_client.py`: `LOBBYSERVER_HOST = '140.113.203.91'`
   - Edit `developer/developer_client.py`: `DEVELOPER_SERVER_HOST = '140.113.203.91'`
3. **Start clients**:
   ```bash
   ./start_player.py      # Player client
   ./start_developer.py   # Developer client
   ```

### Demo Scenarios

#### Scenario 1: Developer Workflow
```
1. Run ./start_developer.py
2. Register developer account (dev1)
3. Login
4. Upload "Multiplayer Bingo" game
   - Select game folder
   - Verify config.json validation
   - Upload completes successfully
5. List games to verify upload
6. Update game version (2.0.0 → 2.0.1)
7. Remove game (optional)
```

#### Scenario 2: Player Workflow
```
1. Run ./start_player.py (2 terminals)
2. Terminal 1: Register player1, login
3. Terminal 2: Register player2, login
4. Both: Browse store, view "Connect Four"
5. Both: Download "Connect Four"
6. Player1: Create room, select "Connect Four"
7. Player2: List rooms, join player1's room
8. Player1: Start game
9. Both: Play Connect Four
10. Winner: Game ends, results saved
11. Both: Rate and review game
```

#### Scenario 3: Multi-player Bingo (3-5 players)
```
1. Run ./start_player.py (3-5 terminals)
2. All: Register/Login
3. All: Download "Multiplayer Bingo"
4. Player1: Create room, select "Multiplayer Bingo"
5. Players 2-5: Join room
6. Player1: Start game (when 3-5 players ready)
7. All: Take turns calling numbers
8. First to complete line wins
```

### Expected Questions from TAs

Be prepared to explain:

1. **System Architecture**
   - Why separate Database/Lobby/Developer servers?
   - How does dynamic game server spawning work?
   - Port pool management strategy

2. **Communication Protocol**
   - Why LPFP instead of simple JSON?
   - Error handling and recovery mechanisms
   - Message format design decisions

3. **Version Management**
   - How are game versions stored?
   - Client auto-update mechanism
   - Backward compatibility handling

4. **Concurrency**
   - Thread safety in server components
   - Multiple rooms running simultaneously
   - Race condition prevention

5. **Security**
   - Password storage (currently plaintext - note limitation)
   - File upload validation
   - Input sanitization

6. **Scalability**
   - Port pool limits (10100-11000)
   - Database performance considerations
   - Future improvements

---

## 🔧 Troubleshooting

### Connection Issues

**Problem**: "Connection refused" error
```bash
# Solution 1: Check server is running
ssh user@140.113.203.91
ps aux | grep start_server

# Solution 2: Check firewall
netstat -tuln | grep 17048

# Solution 3: Verify IP in client code
grep "LOBBYSERVER_HOST" player/lobby_client.py
```

**Problem**: "Connection timeout"
```bash
# Check network connectivity
ping 140.113.203.91

# Test port accessibility
telnet 140.113.203.91 17048
```

### Server Issues

**Problem**: Server crashes or stops
```bash
# Check logs
tail -f server.log

# Restart server
pkill -f start_server.py
nohup ./start_server.py > server.log 2>&1 &
```

**Problem**: Port already in use
```bash
# Find process using port
lsof -i :17048

# Kill process
kill -9 <PID>
```

### Game Issues

**Problem**: Game doesn't start
- Check game files exist in `server/games/`
- Verify config.json is valid JSON
- Check mainFile and serverFile paths
- **For GUI games**: Ensure pygame is installed (`pip3 install pygame`)

**Problem**: "ModuleNotFoundError: No module named 'pygame'"
```bash
# Install pygame
pip3 install pygame

# Verify installation
python3 -c "import pygame; print('OK')"
```

**Problem**: Game disconnects mid-match
- Check game server logs
- Verify network stability
- Check for game logic errors

### Database Issues

**Problem**: Corrupted database.json
```bash
# Backup current database
cp database.json database.json.backup

# Clear and restart
rm database.json
./start_server.py
```

**Problem**: Data inconsistency
```bash
# Validate database structure
python3 -c "import json; print(json.load(open('database.json')))"

# Clear specific collections
./clear_database.py
```

---

## 📁 Project Structure

```
test/
├── README.md                    # This file
├── start_server.py              # Server startup script
├── start_player.py              # Player client launcher
├── start_developer.py           # Developer client launcher
├── clear_database.py            # Database cleanup script
├── validate_system.py           # System validation tool
├── database.json                # Persistent data store
│
├── server/
│   ├── database_server.py       # Database server (port 17047)
│   ├── lobby_server.py          # Lobby server (port 17048)
│   ├── developer_server.py      # Developer server (port 17049)
│   └── games/                   # Uploaded games storage
│       └── <dev>/
│           └── <game>/
│               └── <version>/
│
├── player/
│   ├── lobby_client.py          # Player client interface
│   └── games/                   # Downloaded games
│       └── <game>/
│           ├── config.json
│           ├── <main_file>.py
│           └── version.txt
│
└── developer/
    ├── developer_client.py      # Developer client interface
    ├── template/                # Game templates
    │   ├── game_server.py
    │   ├── game_client.py
    │   └── config.json
    └── games/                   # Game development folders
        └── <dev>/
            └── <game>/
                ├── config.json
                ├── <server_file>.py
                ├── <main_file>.py
                └── README.md
```

---

## Available Games

### Connect Four
- **Type**: CLI
- **Players**: 2
- **Dependencies**: None (standard library)
- **Description**: Classic Connect Four strategy game
- **Features**: 6x7 board, gravity-based drops, win detection

### Multiplayer Bingo
- **Type**: CLI
- **Players**: 3-5 (dynamic)
- **Dependencies**: None (standard library)
- **Description**: 5x5 Bingo with customizable player count
- **Features**: Random card generation, turn-based calling, multiple winning patterns

### Tetris Battle
- **Type**: GUI
- **Players**: 2
- **Dependencies**: `pygame` (install with `pip3 install pygame`)
- **Description**: Competitive Tetris with real-time gameplay
- **Features**: Classic Tetris mechanics, 2-player battle mode, pygame graphics

---

## 📝 Development Notes

### Adding New Games
1. Create game folder: `developer/games/<dev>/<game>/`
2. Create required files:
   - `config.json`: Game metadata
   - `<server>.py`: Game server logic
   - `<client>.py`: Game client interface
3. Use developer client to upload
4. Players can download and play


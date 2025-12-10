# Game Store System - NP HW3
#### 112550047 徐瑋晨
在這次的作業中，我基於HW1和HW2所設計的遊戲和client/server架構建構出一個遊戲商城系統，此遊戲商城系統可以讓開發者開發遊戲並上傳到遊戲商城，開發者也可以在需要時更新或移除自己所上架的遊戲。而玩家則是可以在遊戲商城中瀏覽各個已經上架的遊戲，也可以下載自己想玩的遊戲並創立房間邀請其他玩家一起共同遊玩遊戲。

## System Overview

此遊戲商城系統主要可以分成三大部分，包含server端、client端和遊戲:

### **Server** 
- **Database Server**: 
   - Database server主要負責所有關於資料庫的create, read, update, delete和query的處理，當database server收到來自lobby server或developer server對於資料庫的操作請求時，database server會檢查request的內容來判斷各個request是要對哪個欄位進行什麼操作，再根據request進行資料庫操作並回傳結果。database 會以.json的形式儲存，其中包含User、Gamelog、developer、game欄位，分別儲存玩家資訊、遊戲紀錄、開發者資訊和遊戲詳情。
- **Lobby Server**:
   - Lobby server主要負責處理玩家的所有操作與需求，會接收來自lobby_client的request判斷需要針對database做什麼操作或是是否要啟動遊戲，再根據玩家的request傳送相對應的database request到database server，當玩家的每個request被lobby server處理完後，lobby server會回傳成功或是錯誤訊息給送出request的玩家。
- **Developer Server**:
   - Developer server主要負責處理開發者的所有操作，包含創建遊戲、修改或上架遊戲、瀏覽詳細的遊戲資訊。Developer server匯處理developer相關的所有操作，並接收來自於developer發出的request，當developer server接收到來自developer發出的request時，會判斷每個request是關於什麼操作，如果request牽涉到database的create, read, update, delete, query，則developer會發送相對應的database request到database server進行資料庫操作。當developer server處理完每個request後，會根據職結果回傳相對應的訊息給發出request的developer。
### **Client**
- **Player Client**: 
  在player登入後，會進入main menu:
  ```
  1. Game Store         -> 進入game store
  2. Lobby              -> 進入lobby
  3. Logout             -> 登出
  4. Exit               -> 結束程式
  ```
  當player第一個選項進入Game Store時會看到game store menu:
  ```
  1. Browse Game Store        -> 查看game store裡面可以下載的遊戲
  2. View Game Details        -> 查看game store中可下載遊戲的詳細資訊
  3. Download/Update Game     -> 下載或更新遊戲
  4. My Downloaded Games      -> 查看已下載的遊戲
  5. Rate & Review Game       -> 對遊戲進行review和評分
  0. Back                     -> 回到main menu
  ```
  而當player在main menu選擇第二個選項進入lobby時，會看到lobby menu:
  ```
  1. View Online Players      -> 查看線上玩家
  2. View Active Rooms        -> 查看房間
  3. Create Room & Play       -> 選擇要玩的遊戲創建房間並進入房間
  4. Join Room & Play         -> 加入房間
  5. View Invitations         -> 查看邀請
  6. Accept Invitation        -> 接受邀請並進入房間
  0. Back                     -> 回到main menu
  ```
   在player選擇3. Create Room & Play並成功進入房間後，該player會成為房間的host，並會看到host menu:
   ```
   1. Start Game               -> 開始遊戲
   2. Invite Player            -> 邀請其他完機加入房間
   3. Leave Room               -> 離開房間
   ```
   在player選擇4. Join Room & Play 或6. Accept Invitation並成功進入房間後，如果player不是該房間的創建者，則player會以非host的身分進入房間，會看到room menu並開始等待房間的host開始遊戲:
   ```
   1. Leave Room               -> 離開房間
   ```
  player 可以自由的在game store和lobby間進行切換來達到瀏覽遊戲->下載遊戲->選擇遊戲創建房間->邀請玩家->開始遊戲的流程，在遊戲結束時player會回到room。
- **Developer Client**: 
  在developer登入之後，developer會看到developer main menu:
  ```
  1. Upload New Game             -> 上傳新的遊戲
  2. Update Existing Game        -> 更新現在在game server上的遊戲
  3. Remove Game                 -> 移除game store上的遊戲
  4. List My Games               -> 列出自己所有的遊戲(包含已移除版本)
  5. Create Game from Template   -> 由template新增遊戲框架
  6. Logout                      -> 登出
  0. Exit                        -> 結束程式
  ```

### **Supported Games**
#### Extened Connect Four
  - **Type**: CLI
  - **Players**: 2
  - **Dependencies**: None (standard library)
  - **Description**: Extened Connect Four game allow two player to play in turn
  - **Rule**: 6x7 board, two players put a piece in turn until game end.
  - **Finish condition**: When a player's four pieces form a connected horizontal, vertical, diagonal line, the game will finish. If the board is full and there does exist any free space to put a new piece, the game will also finish (draw).

#### Multiplayer Bingo
  - **Type**: CLI
  - **Players**: 3
  - **Dependencies**: None (standard library)
  - **Description**: 5x5 Bingo game allows three players to play and call the number in turn.
  - **Rule**: Each player's bingo card is randomly generated and the numbers are in range 1~75. Players will call a number in turn until game finishes. The called number can not be called again.
  - **Finish condition**: When a player's board has five number be called and those five called numbers form a vertical, horizontal, or diagonal line, the game will end.

#### Tetris Battle
  - **Type**: GUI
  - **Players**: 2
  - **Dependencies**: `pygame` (install with `pip install pygame`)
  - **Description**: Classical GUI Tetris game allow player to use keyboard to control the block's movement.
  - **Rule**: Two player can control the movement of block using keyboard:
   ```
   left/right  : Move left or right
   up          : Rotate clockwise
   N           : Rotate counter-clockwise
   down        : Soft Drop
   B           : Hard Drop
   SPACE       : Hold
   ESC         : Quit
   ```
   When the block fill a horizontal line in the board, the line will be cleared and the score will increase based on how many lines is cleared at the same time:
   ```
   {1: 100, 2: 300, 3: 500, 4: 800}
   ```
   As the remaining time of the game decrease, the dropping speed of each block will increase to increase the difficulty of the game.
  - **Finish condition**: 
   The time limit of the game is set to 3 minutes and the player with higher score will be the winner of the game. If the next block generated can not be dropped into the board (the board do not have enough space for the new block to drop), the player's game will also finish.

**Note**: The new game can be created if the developer follow the format of template.
Each game will have their own client.py, server.py, and config.json files to allow each game can be started by server correctly.
#### Config.json Format example
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
- Version must be `x.y.z` format
- `mainFile` and `serverFile` must be python file
- `maxPlayers` must be positive integer
- All fields are required
---

## Start System

### Setup
**Dependencies**: 
- Python 3.10+ (standard library only for server/CLI games)
- pygame (required for GUI games like Tetris)

#### download the code and setup environment

```bash
# 1. Clone repository
git clone https://github.com/jimmy94828/NP-Game-store-system
cd NP-Game-store-system
# 2. install pygame for GUI game
pip install pygame

# 3. start servers
chmod +x start_server.py
./start_server.py

# 4. Start Player Client (in other terminal)
chmod +x start_player.py
./start_player.py

# 5. Start Developer Client (in another terminal)
chmod +x start_developer.py
./start_developer.py
```
---

### Connections

#### Servers
Default ports:
- `server/database_server.py`: Port 17047
- `server/lobby_server.py`: Port 17048
- `server/developer_server.py`: Port 17049

#### Player client
```python
LOBBYSERVER_HOST = '140.113.17.11'
LOBBYSERVER_PORT = 17048
```

#### Developer client
```python
DEVELOPER_SERVER_HOST = '140.113.17.11'
DEVELOPER_SERVER_PORT = 17049
```
---

### Example Flows
#### Player Play Game flow
```
1.  Register account and login
2.  Go to Game store
3.  Browse store -> Select "Extend Connect Four"
4.  Download game
5.  Go to Lobby
6.  Create room -> Select "Extend Connect Four"
7.  Wait for player 2 to join
8.  Start game
9.  Play Connect Four
10. Return to room after game finishes
```

#### Developer Upload Game flow
```
1. Login as developer
2. Create game folder in developer/games/<dev_name>/<game_name>/
3. Add required files:
   - config.json (game metadata)
   - <server_file>.py (game server)
   - <main_file>.py (game client)
4. Select "Upload Game" -> Select the game folder to upload
5. Configure metadata (name, version, description, etc.)
6. System validates files and config
7. Upload completed -> Players can download
```

## System Architecture

### Component Diagram
```
┌─────────────────────────────────────────────────────────┐
│                    Client Side                          │
├──────────────────────────┬──────────────────────────────┤
│   Player Client          │   Developer Client           │
│   - lobby_client.py      │   - developer_client.py      │
│   - Browse/Download      │   - Upload/Update games      │
│   - Room Management      │   - Version control          │
│   - Start game           |   - Template creation        |
|   - Review and rating    │                              │
└───────────↑──────────────┴─────────────↑────────────────┘
            │                            │
            │    TCP/IP + JSON + LPFP    │
            │                            │
┌───────────↓────────────────────────────↓────────────────┐
│              Server Side (140.113.17.11)                │
├──────────────────┬────────────────┬─────────────────────┤
│  Database Server │  Lobby Server  │ Developer Server    │
│  Port: 17047     │  Port: 17048   │ Port: 17049         │
│  - JSON storage  │  - Player ops  │ - Game upload       │
│  - CRUDQ ops     │  - Start       | - File transfer     |
|  - LPFP protocol |    GameServers │ - Manage Games      │
└──────────────────┴───────↑────────┴─────────────────────┘
                           │
                           │ Start the game server
            ┌──────────────↓───────────────┐
            │   Dynamic Game Servers       │
            │   Ports: 10100-11000         │
            └──────────────────────────────┘
```

## System Structure

```
test/
├── README.md                    # README file (This file)
├── start_server.py              # Server startup script
├── start_player.py              # Player client launcher
├── start_developer.py           # Developer client launcher
├── clear_database.py            # Database cleanup script
├── validate_system.py           # System validation tool
├── database.json                # Persistent data store
├── server/
│   ├── database_server.py       # Database server (port 17047)
│   ├── lobby_server.py          # Lobby server (port 17048)
│   ├── developer_server.py      # Developer server (port 17049)
│   └── uploaded_games/          # Uploaded games storage   
│       └── <game>/
│           └── <version>/
│
├── player/
│   ├── lobby_client.py          # Player client interface
│   └── downloads/               # Downloaded games
|       └──<player name>/        # The folder to store player's downloaded games
│           └── <game>/
│               ├── config.json
│               ├── <main_file>.py
│               ├── <Server_file>.py
│               └── version.txt
└── developer/
    ├── developer_client.py      # Developer client interface
    ├── Create_game_template.py  # Create template
    ├── template/                # Game templates
    │   ├── game_server.py
    │   ├── game_client.py
    │   └── config.json
    └── games/                   # Game development folders
        ├── <developer name>/    # The folder for developer
        |   └── <game>/
        |       ├── config.json
        |       ├── <server_file>.py
        |       └── <main_file>.py
        └── weichen/             # Three supported games
            ├── bingo
            │   ├── bingo_client.py
            │   ├── bingo_server.py
            │   └── config.json
            ├── connect_four
            │   ├── config.json
            │   ├── connect_four_client.py
            │   └── connect_four_server.py
            └── tetris
                ├── config.json
                ├── tetris_client.py
                └── tetris_server.py
```
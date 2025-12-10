# Database server: handle client's data
# Lobby server: handle client connections and matchmaking
# Game server: handle game logic and player interactions
# using Length-Prefixed Framing Protocol
import socket
import threading
import json
import hashlib
import random
import struct
import time
from datetime import datetime
from typing import Dict, List, Tuple, Optional, Set, Any

DATABASE_SERVER_HOST = '140.113.17.11'
DATABASE_SERVER_PORT = 17047
LOBBYSERVER_HOST = '140.113.17.11'
LOBBYSERVER_PORT = 17048

###### protocol part start ######
# Length-Prefixed Framing Protocol
LENGTH_LIMIT = 65536

class ProtocolError(Exception):             # the protocol error occurs
    pass

def send_message(sock: socket.socket, data: Dict[Any, Any]) -> None:
    # send the message and follow the LPFP protocol
    try:
        message = json.dumps(data, ensure_ascii=False).encode('utf-8')
        length = len(message)
        
        if length > LENGTH_LIMIT:               # the message is too large
            raise ProtocolError(f"Message too large: {length} > {LENGTH_LIMIT}")
        header = struct.pack('!I', length)      # turn the header into 4 bytes
        sock.sendall(header + message)
        
    except socket.error as error:
        raise ProtocolError(f"Socket error while sending: {error}")
    except Exception as error:
        raise ProtocolError(f"Error sending message: {error}")

def recv_message(sock: socket.socket) -> Optional[Dict[Any, Any]]:
    # receive the message and follow the LPFP protocol
    try:
        header = b''                # read the 4 bytes header
        while len(header) < 4:
            chunk = sock.recv(4 - len(header))
            if not chunk:
                return None
            header += chunk
            
        if not header:              # connection closed
            return None
        
        length = struct.unpack('!I', header)[0]
        if length <= 0 or length > LENGTH_LIMIT:
            raise ProtocolError(f"Invalid message length: {length}")
        
        message = b''
        while len(message) < length:    # read the message body
            chunk = sock.recv(length - len(message))
            if not chunk:
                return None
            message += chunk
            
        if not message:
            raise ProtocolError("Connection closed while reading message body")
        
        data = json.loads(message.decode('utf-8'))
        return data
    
    except socket.error as error:
        raise ProtocolError(f"Socket error while receiving: {error}")
    except json.JSONDecodeError as error:
        raise ProtocolError(f"Invalid JSON: {error}")
    except Exception as error:
        raise ProtocolError(f"Error receiving message: {error}")
###### protocol part end ######

###### blocks setting part start ######
SHAPE_NAMES = ['I', 'O', 'T', 'S', 'Z', 'J', 'L']       # names of different shape of the tetris
SHAPES = {
    'I': [
        [(0,1), (1,1), (2,1), (3,1)],
        [(2,0), (2,1), (2,2), (2,3)],
        [(0,2), (1,2), (2,2), (3,2)],
        [(1,0), (1,1), (1,2), (1,3)]
    ],
    'O': [
        [(1,0), (2,0), (1,1), (2,1)],
        [(1,0), (2,0), (1,1), (2,1)],
        [(1,0), (2,0), (1,1), (2,1)],
        [(1,0), (2,0), (1,1), (2,1)]
    ],
    'T': [
        [(1,0), (0,1), (1,1), (2,1)],
        [(1,0), (1,1), (2,1), (1,2)],
        [(0,1), (1,1), (2,1), (1,2)],
        [(1,0), (0,1), (1,1), (1,2)]
    ],
    'S': [
        [(1,0), (2,0), (0,1), (1,1)],
        [(1,0), (1,1), (2,1), (2,2)],
        [(1,1), (2,1), (0,2), (1,2)],
        [(0,0), (0,1), (1,1), (1,2)]
    ],
    'Z': [
        [(0,0), (1,0), (1,1), (2,1)],
        [(2,0), (1,1), (2,1), (1,2)],
        [(0,1), (1,1), (1,2), (2,2)],
        [(1,0), (0,1), (1,1), (0,2)]
    ],
    'J': [
        [(0,0), (0,1), (1,1), (2,1)],
        [(1,0), (2,0), (1,1), (1,2)],
        [(0,1), (1,1), (2,1), (2,2)],
        [(1,0), (1,1), (0,2), (1,2)]
    ],
    'L': [
        [(2,0), (0,1), (1,1), (2,1)],
        [(1,0), (1,1), (1,2), (2,2)],
        [(0,1), (1,1), (2,1), (0,2)],
        [(0,0), (1,0), (1,1), (1,2)]
    ]
}
###### blocks setting part end ######

###### game part start ######
class playerState:
    def __init__(self, user_id, width=10, height=20):
        self.user_id = user_id
        self.role = None
        self.width = width
        self.height = height
        self.board = [[0 for _ in range(width)] for _ in range(height)]
        
        self.current_shape = None           # shape of block
        self.current_type = None            # type of block
        self.current_rotation = 0           # record rotation
        self.current_x = 0                  # position of current block
        self.current_y = 0
        
        self.hold_piece = None
        self.can_hold = True
        self.next_pieces = []
        
        self.score = 0
        self.lines_cleared = 0
        self.level = 1
        self.combo = 0
        self.max_combo = 0
        
        self.game_over = False

    def get_snapshot(self):                         # return game states of the user//
        current_piece = None
        if not self.game_over and self.current_type:
            current_piece = {
                'type': self.current_type,
                'rotation': self.current_rotation,
                'x': self.current_x,
                'y': self.current_y
            }
        return {
            'userId': self.user_id,
            'role': self.role,
            'board': self.board,
            'currentPiece': current_piece,
            'holdPiece': self.hold_piece,
            'nextPieces': self.next_pieces,
            'score': self.score,
            'lines': self.lines_cleared,
            'level': self.level,
            'combo': self.combo,
            'maxCombo': self.max_combo,
            'gameOver': self.game_over
        }

    def generate_pieces(self, piece_type):          # generate a new piece for the player
        self.current_type = piece_type
        self.current_rotation = 0
        self.current_x = self.width // 2 - 2        # start position (3, 0)
        self.current_y = 0
        self.current_shape = SHAPES[piece_type][0]  # initialize the shape
        self.can_hold = True
        
        if not self.check_position():
            self.game_over = True
            self.current_type = None
            self.current_shape = None
    
    def check_position(self, x = None, y = None, rotation = None):
        if x is None:
            x = self.current_x
        if y is None:
            y = self.current_y
        if rotation is None:
            rotation = self.current_rotation

        if self.game_over or not self.current_type:
            return False
    
        shape = SHAPES[self.current_type][rotation]     # current shape of the piece
        for dx, dy in shape:
            board_x = x + dx
            board_y = y + dy
            if board_x < 0 or board_x >= self.width or board_y < 0 or board_y >= self.height:       # the piece will out of board
                return False
            if self.board[board_y][board_x]:            # the piece collides with existing blocks
                return False
        return True

    def lock_piece(self):                               # when the piece can not move down, lock the piece
        shape = SHAPES[self.current_type][self.current_rotation]        # get current piece's shape
        piece_value = SHAPE_NAMES.index(self.current_type) + 1
        
        for dx, dy in shape:
            nowx, nowy = self.current_x + dx, self.current_y + dy
            if 0 <= nowy < self.height:
                self.board[nowy][nowx] = piece_value

        lines = self.clear_lines()                      # check whether line is cleared
        if lines > 0:
            self.lines_cleared += lines
            self.score += self.calculate_score(lines)   # update the user's score
            self.combo += 1
            self.max_combo = max(self.max_combo, self.combo)
        else:
            self.combo = 0

        self.level = self.lines_cleared // 10 + 1

    def clear_lines(self):                              # check is there exist a line that can be cleared
        lines_cleared = 0
        y = self.height - 1
        
        while y >= 0:
            if all(self.board[y][x] != 0 for x in range(self.width)):       # all cells in a row is filled
                del self.board[y]
                self.board.insert(0, [0 for _ in range(self.width)])
                lines_cleared += 1
            else:
                y -= 1
                
        return lines_cleared
    
    def calculate_score(self, lines):
        base_scores = {1: 100, 2: 300, 3: 500, 4: 800}      # 1 line 100, 2 lines 300, 3 lines 500, 4 lines 800
        return base_scores.get(lines, 0) * self.level + self.combo * 50

class GameServer:
    def __init__(self, port, room_id, players, game_id=None, game_name=None, game_version=None, lobby_host = LOBBYSERVER_HOST, lobby_port = LOBBYSERVER_PORT):
        self.port = port
        self.room_id = room_id
        self.players = players
        self.game_id = game_id
        self.game_name = game_name
        self.game_version = game_version
        self.lobby_host = lobby_host
        self.lobby_port = lobby_port
        self.game_states = {}
        self.player_sockets = {}
        self.socket_to_user = {}
        self.spectator_sockets = {}

        self.seed = random.randint(0, 10000)
        self.bag = []
        self.drop_interval = 1.0
        self.game_mode = 'time'                 # gaming time mode  
        self.game_duration = 180                # each game 180 seconds
        self.running = False
        self.lock = threading.Lock()
        self.game_started = False
        self.start_time = None
        self.match_id = f"match_{room_id}_{int(time.time())}"       # create match id for gamelog

    def start(self):                            # staart the game server and waiting for player connections
        self.running = True
        server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)   # TCP socket
        server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server_socket.bind((LOBBYSERVER_HOST, self.port))
        server_socket.listen(10)
        
        print(f"[Game] Server started on port {self.port} for room {self.room_id}")
        
        try:
            while self.running:
                try:
                    client_socket, address = server_socket.accept()
                    thread = threading.Thread(target=self.handle_connection, args=(client_socket,))
                    thread.daemon = True
                    thread.start()
                except Exception as error:
                    if self.running:
                        print(f"[Game] Error accepting connection: {error}")
        except KeyboardInterrupt:
            print("\n[Game] Server shutting down...")
        finally:
            self.running = False
            server_socket.close()
            print("[Game] Server stopped")

    def handle_connection(self, client_socket):         # players in a room will connect to the game server
        try:
            # Accept either LPFP-wrapped HELLO or a simple JSON identification (compat with connect_four_client)
            hello = None
            try:
                # peek first 4 bytes to detect LPFP header
                header = client_socket.recv(4, socket.MSG_PEEK)
                if len(header) == 4:
                    length = struct.unpack('!I', header)[0]
                    if 0 < length <= LENGTH_LIMIT:
                        # It's LPFP-framed; use recv_message to read full message
                        hello = recv_message(client_socket)
                else:
                    # not enough data for LPFP header, fall through to try raw JSON
                    pass
            except (BlockingIOError, OSError):
                # MSG_PEEK may not be available or other error; try recv_message first
                try:
                    hello = recv_message(client_socket)
                except Exception:
                    hello = None

            if hello is None:
                # try reading a small raw JSON identification
                try:
                    raw = client_socket.recv(4096)
                    if not raw:
                        print("[Game] No data received on initial read")
                        return
                    info = json.loads(raw.decode())
                    # map simple identification to HELLO format
                    if 'username' in info or 'userId' in info:
                        hello = {
                            'type': 'HELLO',
                            'userId': info.get('userId') or info.get('username'),
                            'spectator': info.get('spectator', False),
                            'roomId': info.get('roomId')
                        }
                    else:
                        print(f"[Game] Invalid initial identification: {info}")
                        return
                except Exception as e:
                    print(f"[Game] Failed to parse initial identification: {e}")
                    return

            if not hello or hello.get('type') != 'HELLO':
                print(f"[Game] Invalid HELLO message: {hello}")
                return
                
            user_id = hello['userId']
            is_spectator = hello.get('spectator', False)
            
            if is_spectator:                            # spectator mode
                self.handle_spectator(client_socket, user_id)
            else:                                       # player mode
                if user_id not in self.players:
                    send_message(client_socket, {'type': 'ERROR', 'message': 'Not in this game'})
                    return
                self.handle_player(client_socket, user_id)
                
        except Exception as error:
            print(f"[Game] Error handling connection: {error}")
        finally:
            client_socket.close()

    def handle_spectator(self, client_socket, user_id):     # spectator mode
        try:
            with self.lock:
                self.spectator_sockets[user_id] = client_socket
            response = {                                    # send game information to the spectator
                'type': 'WELCOME',
                'role': 'SPECTATOR',
                'seed': self.seed,
                'bagRule': '7bag',
                'gravityPlan': {
                    'mode': 'fixed',
                    'dropMs': int(self.drop_interval * 1000)
                },
                'gameMode': self.game_mode,
                'duration': self.game_duration,
                'spectator': True
            }
            if self.game_started and self.start_time:       # If the game has started, send additional info
                response['gameStarted'] = True
                response['startTime'] = self.start_time.isoformat()
                elapsed = (datetime.now() - self.start_time).total_seconds()
                response['elapsedTime'] = elapsed

            send_message(client_socket, response)
            if self.game_started:
                self.broadcast_snapshots()
            print(f"[Game] Spectator {user_id} joined")
            while self.running:
                time.sleep(0.5)
        
        except ProtocolError:
            pass
        except Exception as error:
            print(f"[Game] Error handling spectator: {error}")
        finally:
            with self.lock:
                if user_id in self.spectator_sockets:
                    del self.spectator_sockets[user_id]

    def handle_player(self, client_socket, user_id):        # player mode
        try:
            with self.lock:
                self.player_sockets[user_id] = client_socket
                self.socket_to_user[client_socket] = user_id
                self.game_states[user_id] = playerState(user_id, width=10, height=20)
                
            role = f"P{self.players.index(user_id) + 1}"
            self.game_states[user_id].role = role
            welcome = {
                'type': 'WELCOME',
                'role': role,
                'seed': self.seed,
                'bagRule': '7bag',
                'gravityPlan': {
                    'mode': 'fixed',
                    'dropMs': int(self.drop_interval * 1000)
                },
                'gameMode': self.game_mode,
                'duration': self.game_duration
            }
            send_message(client_socket, welcome)
            
            print(f"[Game] Player {user_id} ({role}) joined")
            
            with self.lock:                     # start the game when all players have connected
                if len(self.player_sockets) == len(self.players) and not self.game_started:
                    self.game_started = True
                    threading.Thread(target=self.game_loop, daemon=True).start()
                    
            while self.running:
                message = recv_message(client_socket)
                if not message:                         # client disconnected
                    break
                self.handle_input(user_id, message)     # handle player input to play the game
                
        except ProtocolError:
            pass
        except Exception as error:
            print(f"[Game] Error handling player: {error}")
        finally:
            with self.lock:
                if client_socket in self.socket_to_user:
                    user_id = self.socket_to_user[client_socket]
                    del self.socket_to_user[client_socket]
                    if user_id in self.player_sockets:
                        del self.player_sockets[user_id]

    def handle_input(self, user_id, message):
        if message.get('type') != 'INPUT':
            return

        action = message.get('action')                  # check user input action

        with self.lock:
            state = self.game_states.get(user_id)       # get user's current game state
            if not state or state.game_over:
                return
            if not state.current_type:                  # no current piece
                return
            if action == 'LEFT':                        # move left
                if state.check_position(x=state.current_x - 1):
                    state.current_x -= 1
            elif action == 'RIGHT':                     # move right
                if state.check_position(x=state.current_x + 1):
                    state.current_x += 1
            elif action == 'CW':                        # clockwise rotate
                new_rotation = (state.current_rotation + 1) % len(SHAPES[state.current_type])
                if state.check_position(rotation=new_rotation):
                    state.current_rotation = new_rotation
            elif action == 'CCW':                       # counter-clockwise rotate
                new_rotation = (state.current_rotation - 1) % len(SHAPES[state.current_type])
                if state.check_position(rotation=new_rotation):
                    state.current_rotation = new_rotation
            elif action == 'SOFT_DROP':                 # soft drop
                if state.check_position(y=state.current_y + 1):
                    state.current_y += 1
                else:
                    state.lock_piece()                  # can not move down
                    self.generate_next_piece(user_id)
            elif action == 'HARD_DROP':
                while state.check_position(y=state.current_y + 1):
                    state.current_y += 1
                state.lock_piece()                      # can not move down
                self.generate_next_piece(user_id)
            elif action == 'HOLD':
                if state.can_hold:
                    old_hold = state.hold_piece         # store the old hold piece
                    state.hold_piece = state.current_type
                    if old_hold:                        # if there is already a hold piece
                        state.generate_pieces(old_hold)
                    else:
                        self.generate_next_piece(user_id)
                    state.can_hold = False
    
    def get_next_piece(self):           # randomly get the next piece according to 7-bag rule
        if len(self.bag) < 7:
            bag = SHAPE_NAMES.copy()
            random.shuffle(bag)
            self.bag.extend(bag)
        return self.bag.pop(0)
    
    def generate_next_piece(self, user_id):                 # generate the next piece for the user
        state = self.game_states[user_id]
        if state.next_pieces:
            next_piece = state.next_pieces.pop(0)
            state.next_pieces.append(self.get_next_piece()) # get a piece from the bag
            state.generate_pieces(next_piece)
    
    def game_loop(self):
        self.start_time = datetime.now()
        print(f"[Game] Game started at {self.start_time}")
        
        random.seed(self.seed)
        for _ in range(3):                  # initialize the bag with 3 sets of pieces
            bag = SHAPE_NAMES.copy()
            random.shuffle(bag)
            self.bag.extend(bag)
            
        for user_id in self.players:
            for _ in range(5):              # pre-generate 5 next pieces for each player
                self.game_states[user_id].next_pieces.append(self.get_next_piece())
            self.generate_next_piece(user_id)
            
        self.broadcast({                    # notify all players that the game has started
            'type': 'GAME_START',
            'startTime': self.start_time.isoformat()
        })
        
        last_drop_time = time.time()
        last_snapshot_time = time.time()
        
        while self.running and self.game_started:
            current_time = time.time()
            game_elapsed = (datetime.now() - self.start_time).total_seconds()   # the time since the game started

            # drop interval decreases as time progresses (decrease 0.2 / 35s)
            current_drop_interval = max(0.2, self.drop_interval - (game_elapsed // 35) * 0.2)

            if (current_time - last_drop_time) >= current_drop_interval:        # time to drop pieces
                with self.lock:
                    for user_id, state in self.game_states.items():
                        if not state.game_over and state.current_type:
                            if state.check_position(y=state.current_y + 1):
                                state.current_y += 1
                            else:
                                state.lock_piece()
                                self.generate_next_piece(user_id)
                last_drop_time = current_time
                
            if current_time - last_snapshot_time >= 0.1:            # broadcast game snapshots every 0.1 seconds
                self.broadcast_snapshots()
                last_snapshot_time = current_time
                
            if self.check_game_end():                               # check if the game has ended
                self.end_game()
                break
    
    def broadcast(self, message):                           # broadcast message to all players and spectators
        with self.lock:
            for socket in self.player_sockets.values():
                try:
                    send_message(socket, message)
                except:
                    pass
            for socket in self.spectator_sockets.values():
                try:
                    send_message(socket, message)
                except:
                    pass
    
    def broadcast_snapshots(self):                  # broadcast game snapshots to all players and spectators
        with self.lock:
            snapshots = []
            for user_id, state in self.game_states.items():
                snapshots.append(state.get_snapshot())
                
        self.broadcast({
            'type': 'SNAPSHOTS',
            'data': snapshots,
            'timestamp': time.time()
        })

    def check_game_end(self):
        with self.lock:
            # if all players exit the game
            if not self.player_sockets:
                return True
            if all(state.game_over for state in self.game_states.values()):     # all players game over
                return True
            if self.game_mode == 'time':                                        # game time run out
                elapsed = (datetime.now() - self.start_time).total_seconds()
                if elapsed >= self.game_duration:
                    return True
        return False

    def end_game(self):
        end_time = datetime.now()
        print(f"[Game] Game ended at {end_time}")
        
        results = []
        with self.lock:
            for user_id, state in self.game_states.items():
                results.append({
                    'userId': user_id,
                    'score': state.score,
                    'lines': state.lines_cleared,
                    'maxCombo': state.max_combo
                })

        results.sort(key=lambda x: x['score'], reverse=True)        # sort by the user's score

        self.broadcast({
            'type': 'GAME_END',
            'results': results,
            'endTime': end_time.isoformat(),
            'timestamp': time.time()
        })
        time.sleep(0.2)
        try:
            lobby_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            lobby_socket.connect((self.lobby_host, self.lobby_port))
            send_message(lobby_socket, {                            # notify lobby that the game has ended
                'command': 'game_ended',
                'roomId': self.room_id,
                'matchId': self.match_id,
                'game_id': self.game_id,
                'game_name': self.game_name,
                'game_version': self.game_version,
                'users': self.players,
                'startAt': self.start_time.isoformat(),
                'endAt': end_time.isoformat(),
                'results': results
            })
            lobby_socket.close()
        except Exception as error:
            print(f"[Game] Error notifying lobby: {error}")
            
        self.running = False
        self.game_started = False
###### game part end ######

def main():
    print("======= TETRIS GAME SERVERS =======")
    print("This module provides GameServer(port, room_id, players, ...).\nRun with: python3 tetris_server.py <port> <room> [player1 player2 ...] for a quick test.")

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n\nShutting down servers...")
        
        print("Servers stopped. Exiting...")
        
if __name__ == '__main__':
    # If arguments are provided, start a standalone GameServer for quick testing
    import sys
    if len(sys.argv) >= 8:  # New format with game info
        try:
            port = int(sys.argv[1])
            room = sys.argv[2]
            game_id = sys.argv[3]
            game_name = sys.argv[4]
            game_version = sys.argv[5]
            players = sys.argv[6:]
            print(f"[GameServer] Starting Tetris on port {port}, room {room}, game: {game_name} v{game_version}, players: {players}")
            gs = GameServer(port, room, players, game_id, game_name, game_version)
            gs.start()
        except KeyboardInterrupt:
            print("\n[GameServer] Interrupted by user")
        except Exception as e:
            print(f"Failed to start GameServer: {e}")
    elif len(sys.argv) >= 3:  # Old format without game info (fallback)
        try:
            port = int(sys.argv[1])
            room = sys.argv[2]
            players = sys.argv[3:] if len(sys.argv) > 3 else ['1', '2']
            print(f"[GameServer] Starting Tetris on port {port}, room {room}, players: {players}")
            gs = GameServer(port, room, players)
            gs.start()
        except KeyboardInterrupt:
            print("\n[GameServer] Interrupted by user")
        except Exception as e:
            print(f"Failed to start GameServer: {e}")
    else:
        main()
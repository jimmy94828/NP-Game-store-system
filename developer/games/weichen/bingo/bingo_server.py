#!/usr/bin/env python3
"""
Multiplayer Bingo game server for lobby integration (3-5 players).
Messages:
- Server -> Clients: {"type": "assign", "player": 1|2|3|4|5}
- Server -> Clients: {"type": "card", "numbers": [[...], ...]}
- Server -> Clients: {"type": "game_state", ...}
- Client -> Server: {"type": "call", "number": <int>}
"""
import socket
import threading
import json
import time
import random
import struct
from datetime import datetime
import sys

DATABASE_SERVER_HOST = '140.113.17.11'
DATABASE_SERVER_PORT = 17047

LENGTH_LIMIT = 65536

############## protocol part start ##############
class ProtocolError(Exception):
    pass

def send_message(sock: socket.socket, data: dict) -> None:
    try:
        message = json.dumps(data, ensure_ascii=False).encode('utf-8')
        length = len(message)
        if length > LENGTH_LIMIT:
            raise ProtocolError(f"Message too large: {length} > {LENGTH_LIMIT}")
        header = struct.pack('!I', length)
        sock.sendall(header + message)
    except socket.error as e:
        raise ProtocolError(f"Socket error while sending: {e}")

def recv_message(sock: socket.socket):
    try:
        header = b''
        while len(header) < 4:
            chunk = sock.recv(4 - len(header))
            if not chunk:
                return None
            header += chunk
        length = struct.unpack('!I', header)[0]
        if length <= 0 or length > LENGTH_LIMIT:
            raise ProtocolError(f"Invalid message length: {length}")
        message = b''
        while len(message) < length:
            chunk = sock.recv(length - len(message))
            if not chunk:
                return None
            message += chunk
        return json.loads(message.decode('utf-8'))
    except Exception as e:
        raise ProtocolError(str(e))

################ protocol part end ##############

class BingoGame:
    def __init__(self):
        self.board_size = 5
        self.called_numbers = set()
        
    def generate_card(self):                        # generate a random bingo card
        card = []
        ranges = [(1, 15), (16, 30), (31, 45), (46, 60), (61, 75)]
        
        for col_range in ranges:                    # generate each column
            column = random.sample(range(col_range[0], col_range[1] + 1), 5)
            card.append(column)
        
        card = [[card[col][row] for col in range(5)] for row in range(5)]
        # card[2][2] = 0
        return card
    
    def check_winner(self, marked):                 # check if the marked positions have a winning pattern
        for row in marked:                          # check rows
            if all(row):
                return True
        for col in range(self.board_size):          # check columns
            if all(marked[row][col] for row in range(self.board_size)):
                return True
        if all(marked[i][i] for i in range(self.board_size)):       # check main diagonal
            return True
        if all(marked[i][self.board_size - 1 - i] for i in range(self.board_size)):       # check anti-diagonal
            return True
        return False

class GameServer:
    def __init__(self, port, room_id, players, game_id=None, game_name=None, game_version=None, lobby_host='140.113.17.11', lobby_port=17048):
        self.port = int(port)
        self.room_id = room_id
        self.players = players      # List of 3-5 usernames
        self.num_players = len(players)  # Dynamic player count
        self.game_id = game_id
        self.game_name = game_name
        self.game_version = game_version
        self.lobby_host = lobby_host
        self.lobby_port = lobby_port
        self.running = False
        self.server_socket = None

        self.sockets = []           # accepted player sockets
        self.usernames = []         # usernames from command line
        self.player_map = {}        # player_number -> socket
        self.cards = {}             # player_number -> card
        self.marked = {}            # player_number -> marked positions
        self.game = BingoGame()
        self.current_player = 1
        self.lock = threading.Lock()

    def start(self):
        self.running = True
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server_socket.bind(('', self.port))
        self.server_socket.listen(self.num_players)

        print(f"[GameServer] Listening on port {self.port} for {self.num_players} players...")

        try:
            while len(self.sockets) < self.num_players and self.running:  # accept dynamic number of players
                try:
                    client_sock, addr = self.server_socket.accept()
                    print(f"[GameServer] Player {len(self.sockets)+1}/{self.num_players} connected from {addr}")
                    username = self.players[len(self.sockets)]
                    
                    self.sockets.append(client_sock)
                    self.usernames.append(username)
                except KeyboardInterrupt:
                    raise
                except Exception as e:
                    if self.running:
                        print(f"[GameServer] Error accepting connection: {e}")

            if len(self.sockets) < self.num_players:
                print(f"[GameServer] Not enough players (got {len(self.sockets)}, need {self.num_players}).")
                self.close_all()
                return

            for i in range(self.num_players):                       # map player numbers to sockets
                self.player_map[i + 1] = self.sockets[i]                
                card = self.game.generate_card()                    # generate bingo card for each player
                self.cards[i + 1] = card
                
                marked = [[False] * 5 for _ in range(5)]            # initialize marked positions (all False)
                self.marked[i + 1] = marked

            for i in range(self.num_players):                       # send assignments and cards to players   
                player_num = i + 1
                try:
                    self._send(self.player_map[player_num], {       # send player assignment
                        "type": "assign",
                        "player": player_num,
                        "player_name": self.usernames[i]
                    })
                    self._send(self.player_map[player_num], {       # send player card
                        "type": "card",
                        "numbers": self.cards[player_num]
                    })
                except Exception as e:
                    print(f"[GameServer] Failed to send assignment: {e}")

            start_time = datetime.now().isoformat()                 # record start time
            match_id = random.randint(100000, 999999)               # generate match ID
            game_over = False
            winner = None
            
            # Broadcast initial game state so Player 1 knows it's their turn
            print(f"[GameServer] Game starting! Player {self.current_player}'s turn.")
            self.broadcast_game_state(None)

            while not game_over and self.running:                   # main game loop
                current = self.current_player
                current_socket = self.player_map[current]

                try:
                    # Receive length prefix (4 bytes)
                    header = current_socket.recv(4)
                    if not header or len(header) < 4:
                        print(f"[GameServer] Player {current} disconnected")
                        # Notify all players that game ended due to disconnection
                        self.broadcast_game_state(None, winner='disconnected', disconnected_player=current)
                        break
                    
                    length = int.from_bytes(header, 'big')
                    # Receive the actual payload
                    raw_data = b''
                    while len(raw_data) < length:
                        chunk = current_socket.recv(min(4096, length - len(raw_data)))
                        if not chunk:
                            break
                        raw_data += chunk
                    
                    if len(raw_data) < length:
                        print(f"[GameServer] Player {current} disconnected")
                        # Notify all players that game ended due to disconnection
                        self.broadcast_game_state(None, winner='disconnected', disconnected_player=current)
                        break

                    message = json.loads(raw_data.decode('utf-8'))
                    
                    if message.get('type') == 'call':
                        number = message.get('number')
                        
                        if not isinstance(number, int) or number < 1 or number > 75:
                            self._send(current_socket, {
                                "type": "error", 
                                "message": "Invalid number! Must be between 1-75",
                                "current_player": current
                            })
                            continue
                        
                        if number in self.game.called_numbers:
                            self._send(current_socket, {
                                "type": "error", 
                                "message": f"Number {number} has already been called!",
                                "current_player": current
                            })
                            continue
                        
                        self.game.called_numbers.add(number)            # record called number
                        print(f"[GameServer] Player {current} called number {number}")
                        
                        for player_num in range(1, self.num_players + 1):  # mark number on all players' cards
                            card = self.cards[player_num]
                            for row in range(5):
                                for col in range(5):
                                    if card[row][col] == number:
                                        self.marked[player_num][row][col] = True
                        
                        winner_found = None                             # check for winner
                        for player_num in range(1, self.num_players + 1):
                            if self.game.check_winner(self.marked[player_num]):
                                winner_found = player_num
                                winner = player_num
                                game_over = True
                                break
                        
                        if not game_over:                               # go to next player's turn BEFORE broadcasting
                            self.current_player = (self.current_player % self.num_players) + 1
                        
                        self.broadcast_game_state(number, winner_found) # broadcast game state with updated current_player
                    
                except json.JSONDecodeError:
                    continue
                except Exception as e:
                    print(f"[GameServer] Error handling move: {e}")
                    break

            end_time = datetime.now().isoformat()                       # record end time

            try:
                results_payload = {                                     # save results to lobby and database
                    'matchId': match_id,
                    'roomId': self.room_id,
                    'game_id': self.game_id,
                    'game_name': self.game_name,
                    'game_version': self.game_version,
                    'users': self.players,
                    'startAt': start_time,
                    'endAt': end_time,
                    'results': []
                }
                
                for idx, pid in enumerate(self.players, start=1):       # compile results
                    entry = {'userId': pid}
                    if winner is None:
                        entry['winner'] = False
                    else:
                        entry['winner'] = (idx == winner)
                    results_payload['results'].append(entry)

                # notify lobby - lobby will write GameLog with complete game info
                self.notify_lobby(results_payload)

            except Exception as e:
                print(f"[GameServer] Error sending results: {e}")

        except Exception as e:
            print(f"[GameServer] Server error: {e}")
        finally:
            self.close_all()

    def _send(self, sock, data):
        try:
            payload = json.dumps(data).encode('utf-8')
            length = len(payload)
            header = length.to_bytes(4, 'big')
            sock.sendall(header + payload)
        except Exception as e:
            print(f"[GameServer] Send error: {e}")

    def broadcast_game_state(self, last_called, winner=None, disconnected_player=None):
        state = {
            'type': 'game_state',
            'current_player': self.current_player,
            'last_called': last_called,
            'called_numbers': sorted(list(self.game.called_numbers)),
            'game_over': winner is not None or disconnected_player is not None,
            'winner': winner if winner != 'disconnected' else None,
            'disconnected_player': disconnected_player
        }
        for sock in self.sockets:
            try:
                self._send(sock, state)
            except Exception:
                pass

    def notify_lobby(self, payload):
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.connect((self.lobby_host, int(self.lobby_port)))
            send_message(s, {"command": "game_ended", **payload})  # Use LPFP protocol
            s.close()
        except Exception as e:
            print(f"[GameServer] Could not notify lobby: {e}")

    def write_game_log_to_db(self, payload):
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.connect((DATABASE_SERVER_HOST, int(DATABASE_SERVER_PORT)))
            send_message(s, {
                'collection': 'GameLog',
                'action': 'create',
                'data': payload
            })
            try:
                response = recv_message(s)
            except Exception:
                response = None
            s.close()
        except Exception as e:
            print(f"[GameServer] DB write error: {e}")

    def close_all(self):                        # close all sockets and clean up
        self.running = False
        for sock in self.sockets:
            try:
                sock.close()
            except:
                pass
        if self.server_socket:
            try:
                self.server_socket.close()
            except:
                pass

def main():
    '''Usage: python3 bingo_server.py <port> <room_id> <game_id> <game_name> <game_version> <player1> <player2> <player3> [<player4> <player5>]'''
    if len(sys.argv) >= 9:  # New format with game info
        port = sys.argv[1]
        room_id = sys.argv[2]
        game_id = sys.argv[3]
        game_name = sys.argv[4]
        game_version = sys.argv[5]
        players = sys.argv[6:]  # Get all players from command line (3-5 players)
    elif len(sys.argv) >= 6:  # Old format without game info (fallback)
        port = sys.argv[1]
        room_id = sys.argv[2]
        game_id = None
        game_name = None
        game_version = None
        players = sys.argv[3:]  # Get all players from command line (3-5 players)
    else:
        print("Error: Need at least 3 players")
        sys.exit(1)
    
    if len(players) < 3 or len(players) > 5:
        print(f"Error: Need 3-5 players, got {len(players)}")
        sys.exit(1)
    
    print(f"[GameServer] Starting Bingo on port {port}, room {room_id}, game: {game_name} v{game_version}, players: {players}")
    try:
        server = GameServer(port, room_id, players, game_id, game_name, game_version)
        server.start()
    except KeyboardInterrupt:
        print("\n[GameServer] Interrupted by user")

if __name__ == '__main__':
    main()

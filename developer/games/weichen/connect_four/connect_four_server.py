#!/usr/bin/env python3
"""
Messages:
- Client -> Server: {"username": "..."} (on connect)
- Client -> Server: {"type": "move", "column": <int>} (player move)
- Server -> Clients: {"type": "assign", "player": 1|2}
- Server -> Clients: {"type": "game_state", "board": [...], "current_player": 1|2, "game_over": bool, "winner": None|1|2|-1}
"""
import socket
import threading
import json
import time
import random
import struct
from datetime import datetime
import os

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

############### protocol part end ##############

class exconnectFour:                # game logic for connect four
    def __init__(self):
        self.rows = 6               #6 rows
        self.columns = 7            #7 columns
        self.board = [[0 for _ in range(self.columns)] for _ in range(self.rows)]
        #self.current_player = random.choice([1, 2])   #randomly choose which player start first(1 for player A, 2 for player B)
        self.current_player = 1     #let player A start first
        
    def reset(self):                #reset the board
        self.board = [[0 for _ in range(self.columns)] for _ in range(self.rows)]
        self.current_player = 1     #let player A start first

    def display_board(self):        #display the current board
        print("-----------------")
        for row in range(self.rows):
            print("|", end=" ")
            for col in range(self.columns):
                if self.board[row][col] == 1:
                    print("X", end=" ")     #player A
                elif self.board[row][col] == 2:
                    print("O", end=" ")     #player B
                else:
                    print(".", end=" ")     #empty cell
            print("|")
        print("-----------------")
        print("  0 1 2 3 4 5 6")            #column indexes

    def check_move(self, choose):           #check whether the column is full or not
        if choose < 0 or choose >= self.columns:
            return False
        return self.board[0][choose] == 0

    def put_piece(self, choose):            #put piece into board
        if not self.check_move(choose):
            return False
        
        for row in range(self.rows - 1, -1, -1):
            if self.board[row][choose] == 0:
                self.board[row][choose] = self.current_player
                if self.current_player == 1:
                    self.current_player = 2
                else:
                    self.current_player = 1
                return True
        return False

    def check_state(self):                  #check whether the game is end
        #horizontal - with wrap around
        for row in range(self.rows):
            for col in range(self.columns):
                current = self.board[row][col]      #current block player
                if current == 0:
                    continue
                check = True
                for i in range(4):
                    if self.board[row][(col + i) % self.columns] != current:
                        check = False
                        break
                if check:
                    return current         #return the winner
        #vertical |
        for row in range(self.rows - 3):
            for col in range(self.columns):
                if (self.board[row][col] != 0 and
                    self.board[row][col] == self.board[row + 1][col] ==
                    self.board[row + 2][col] == self.board[row + 3][col]):
                    return self.board[row][col]         #return the winner
        # \ with wrap around
        for row in range(self.rows - 3):
            for col in range(self.columns):
                current = self.board[row][col]      #current block player
                if current == 0:
                    continue
                check = True
                for i in range(4):
                    if self.board[row + i][(col + i) % self.columns] != current:
                        check = False
                        break
                if check:
                    return current         #return the winner
        # / with wrap around
        for row in range(3, self.rows):
            for col in range(self.columns):
                current = self.board[row][col]      #current block player
                if current == 0:
                    continue
                check = True
                for i in range(4):
                    if self.board[row - i][(col + i) % self.columns] != current:
                        check = False
                        break
                if check:
                    return current         #return the winner
        draw = True
        for row in range(self.rows):
            for col in range(self.columns):
                if self.board[row][col] == 0:
                    return 0            #continue
        
        return -1   #draw


class GameServer:
    def __init__(self, port, room_id, players, game_id=None, game_name=None, game_version=None, lobby_host='140.113.17.11', lobby_port=17048):
        # players is an array/list of player identifiers (from lobby)
        self.port = int(port)
        self.room_id = room_id
        self.players = players
        self.game_id = game_id
        self.game_name = game_name
        self.game_version = game_version
        self.lobby_host = lobby_host
        self.lobby_port = lobby_port
        self.running = False
        self.server_socket = None

        self.sockets = []          # accepted player sockets
        self.usernames = []        # usernames reported by players
        self.player_map = {}       # player_number -> socket

    def start(self):
        self.running = True
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server_socket.bind(('', self.port))
        self.server_socket.listen(2)

        print(f"[GameServer] Listening on port {self.port} for two players...")

        try:
            while len(self.sockets) < 2 and self.running:           # player connections
                client_sock, addr = self.server_socket.accept()
                print(f"[GameServer] Player connected from {addr}")
                try:
                    raw = client_sock.recv(4096)
                    if not raw:
                        client_sock.close()
                        continue
                    info = json.loads(raw.decode())
                    username = info.get('username', f'Player{len(self.sockets)+1}')
                except Exception:
                    username = f'Player{len(self.sockets)+1}'

                self.sockets.append(client_sock)
                self.usernames.append(username)

            if len(self.sockets) < 2:
                print("[GameServer] Not enough players, aborting.")
                self.close_all()
                return

            # assign player numbers: first connected -> player 1 (A), second -> player 2 (B)
            self.player_map[1] = self.sockets[0]
            self.player_map[2] = self.sockets[1]

            # inform clients of their player number
            try:
                self._send(self.player_map[1], {"type": "assign", "player": 1, "player_name": self.usernames[0]})
                self._send(self.player_map[2], {"type": "assign", "player": 2, "player_name": self.usernames[1]})
            except Exception as e:
                print(f"[GameServer] Failed to send assignment: {e}")

            # create game and run loop
            game = exconnectFour()
            start_time = datetime.now().isoformat()

            match_id = random.randint(100000, 999999)           # random match ID
            game_over = False

            # send initial state
            self.broadcast_game_state(game, None)

            while not game_over and self.running:
                cur = game.current_player
                cur_sock = self.player_map[cur]

                try:
                    raw = cur_sock.recv(4096)
                    if not raw:
                        print(f"[GameServer] Player {cur} disconnected")
                        break
                    data = json.loads(raw.decode())
                except Exception as e:
                    print(f"[GameServer] Error receiving from player {cur}: {e}")
                    break

                if data.get('type') == 'move':
                    col = data.get('column')
                    if not isinstance(col, int) or not game.check_move(col):
                        # invalid move; notify the player
                        try:
                            self._send(cur_sock, {"type": "invalid_move", "message": "Invalid move"})
                        except Exception:
                            pass
                        continue

                    game.put_piece(col)
                    winner = game.check_state()
                    self.broadcast_game_state(game, winner)

                    if winner != 0:
                        game_over = True
                        break

                else:
                    # unknown message type: ignore
                    continue

            end_time = datetime.now().isoformat()

            # notify lobby and write to database that the game ended
            try:
                results_payload = {
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
                # build per-player result entries (winner flag or draw)
                for idx, pid in enumerate(self.players, start=1):
                    entry = {'userId': pid}
                    if winner == -1:
                        entry['winner'] = 'draw'
                    else:
                        entry['winner'] = (idx == winner)
                    results_payload['results'].append(entry)

                # notify lobby - lobby will write GameLog with complete game info
                self.notify_lobby(results_payload)

            except Exception as e:
                print(f"[GameServer] Failed to notify lobby or DB: {e}")

        finally:
            self.close_all()

    def _send(self, sock, obj):                         # send JSON object to socket
        try:
            sock.sendall(json.dumps(obj).encode())
        except Exception:
            pass

    def broadcast_game_state(self, game, winner):       # broadcast current game state to all players
        state = {
            'type': 'game_state',
            'board': game.board,
            'current_player': game.current_player,
            'game_over': winner != 0 if winner is not None else False,
            'winner': winner if winner is not None and winner != 0 else ( -1 if winner == -1 else None )
        }
        for sock in self.sockets:
            try:
                self._send(sock, state)
            except Exception:
                pass

    def notify_lobby(self, payload):                    # notify lobby that the game ended
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.connect((self.lobby_host, int(self.lobby_port)))
            send_message(s, {"command": "game_ended", **payload})  # Use LPFP protocol
            s.close()
        except Exception as e:
            print(f"[GameServer] Could not notify lobby: {e}")

    def write_game_log_to_db(self, payload):            # write game log to database server
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.connect((DATABASE_SERVER_HOST, int(DATABASE_SERVER_PORT)))
            send_message(s, {
                'collection': 'GameLog',
                'action': 'create',
                'data': payload
            })
            try:
                response = recv_message(s)                  # wait for response
            except Exception:
                response = None
            s.close()
            return response
        except Exception as e:
            raise

    def close_all(self):                        # close all sockets and clean up
        try:
            for sock in self.sockets:
                try:
                    sock.close()
                except Exception:
                    pass
        finally:
            if self.server_socket:
                try:
                    self.server_socket.close()
                except Exception:
                    pass


def main():
    import sys
    # Command-line format: python3 server.py <port> <room_id> <game_id> <game_name> <game_version> <player1_username> <player2_username>
    if len(sys.argv) >= 8:          # command-line arguments provided with game info
        port = int(sys.argv[1])
        room = sys.argv[2]
        game_id = sys.argv[3]
        game_name = sys.argv[4]
        game_version = sys.argv[5]
        players = sys.argv[6:]  # Get actual usernames from command line
    elif len(sys.argv) >= 5:        # old format without game info (fallback)
        port = int(sys.argv[1])
        room = sys.argv[2]
        game_id = None
        game_name = None
        game_version = None
        players = sys.argv[3:]  # Get actual usernames from command line
    else:                           # use environment variables (fallback for testing)
        port = int(os.environ.get('CF_PORT', os.environ.get('GAME_PORT', 17070)))
        room = os.environ.get('CF_ROOM', os.environ.get('GAME_ROOM', 'testroom'))
        game_id = None
        game_name = None
        game_version = None
        players = ['A', 'B']  # Default for testing only
    
    print(f"[GameServer] Starting on port {port}, room {room}, game: {game_name} v{game_version}, players: {players}")
    gs = GameServer(port, room, players, game_id, game_name, game_version)
    gs.start()


if __name__ == '__main__':
    main()

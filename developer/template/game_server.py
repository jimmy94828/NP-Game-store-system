#!/usr/bin/env python3
"""
Game Server Template
This is a template for creating a game server that manages game logic.
"""
import socket
import threading
import sys
import json
import struct
from typing import Optional, Dict, Any, List

############## protocol part start ###########
def send_message(sock: socket.socket, data: Dict[Any, Any]) -> None:
    try:
        message = json.dumps(data, ensure_ascii=False).encode('utf-8')
        length = len(message)
        header = struct.pack('!I', length)
        sock.sendall(header + message)
    except Exception as e:
        print(f"Error sending message: {e}")

def recv_message(sock: socket.socket) -> Optional[Dict[Any, Any]]:
    try:
        header = b''
        while len(header) < 4:
            chunk = sock.recv(4 - len(header))
            if not chunk:
                return None
            header += chunk
        
        length = struct.unpack('!I', header)[0]
        message = b''
        while len(message) < length:
            chunk = sock.recv(length - len(message))
            if not chunk:
                return None
            message += chunk
        
        return json.loads(message.decode('utf-8'))
    except Exception as e:
        print(f"Error receiving message: {e}")
        return None

############# protocol part end ###########

class GameServer:
    def __init__(self, host, port):
        self.host = host
        self.port = port
        self.server_socket = None
        self.running = False
        self.players = {}  # {user_id: {'socket': sock, 'name': name}}
        self.lock = threading.Lock()
        self.game_started = False
        
    def start(self):            # start the game server
        try:
            self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.server_socket.bind((self.host, self.port))
            self.server_socket.listen(5)
            self.running = True
            
            print(f"[GameServer] Started on {self.host}:{self.port}")
            
            while self.running and len(self.players) < 2:  # TODO: Change max players as needed
                try:
                    client_socket, address = self.server_socket.accept()
                    print(f"[GameServer] Player connected from {address}")
                    thread = threading.Thread(
                        target=self.handle_player,
                        args=(client_socket,),
                        daemon=True
                    )
                    thread.start()
                except Exception as e:
                    if self.running:
                        print(f"[GameServer] Error accepting connection: {e}")

            if len(self.players) >= 2:                      # TODO: Change condition as needed
                print("[GameServer] All players connected. Starting game...")
                self.start_game()
            while self.running:
                threading.Event().wait(1)
                
        except Exception as e:
            print(f"[GameServer] Error: {e}")
        finally:
            self.cleanup()
    
    def handle_player(self, client_socket):                 # handle individual player connection
        user_id = None
        try:
            identification = recv_message(client_socket)        # receive player identification to connect
            if not identification:
                print("[GameServer] Failed to receive identification")
                return
            
            user_id = identification.get('userId')
            room_id = identification.get('roomId')
            
            if not user_id:
                send_message(client_socket, {
                    'status': 'error',
                    'message': 'Invalid identification'
                })
                return
            with self.lock:
                self.players[user_id] = {
                    'socket': client_socket,
                    'user_id': user_id,
                    'room_id': room_id
                }
            send_message(client_socket, {                       # response
                'status': 'success',
                'message': 'Connected to game server'
            })
            
            print(f"[GameServer] Player {user_id} registered")

            while self.running:
                message = recv_message(client_socket)
                if not message:
                    break
                
                # TODO: Handle different message types
                self.handle_player_message(user_id, message)
                
        except Exception as e:
            print(f"[GameServer] Error handling player {user_id}: {e}")
        finally:
            if user_id and user_id in self.players:
                with self.lock:
                    del self.players[user_id]
                print(f"[GameServer] Player {user_id} disconnected")
            client_socket.close()
    
    def handle_player_message(self, user_id: int, message: dict):           # handle messages from players
        # TODO: Implement game-specific message handling
        message_type = message.get('type')
        
        if message_type == 'action':                        # player action
            self.process_action(user_id, message)
        elif message_type == 'disconnect':                  # player disconnect
            self.running = False
        else:
            print(f"[GameServer] Unknown message type from {user_id}: {message_type}")
    
    def start_game(self):                                   # start the game logic
        self.game_started = True
        
        # TODO: Implement game initialization logic
        print("[GameServer] Game initialized")
        
        self.broadcast({                                    # broadcast game start message
            'type': 'game_start',
            'message': 'Game is starting!'
        })
        
        # TODO: Start game loop or state management
    
    def process_action(self, user_id: int, action: dict):   # process player action
        # TODO: Implement game-specific action processing
        print(f"[GameServer] Processing action from player {user_id}: {action}")
        
        # Update game state
        self.broadcast_game_state()             # broadcast updated game state to all players   
    
    def broadcast_game_state(self):             # broadcast current game state to all players
        # TODO: Construct game state message
        state = {
            'type': 'game_state',
        }
        self.broadcast(state)
    
    def broadcast(self, message: dict):         # send message to all players
        with self.lock:
            for user_id, player in list(self.players.items()):
                try:
                    send_message(player['socket'], message)
                except Exception as e:
                    print(f"[GameServer] Failed to send to player {user_id}: {e}")
    
    def send_to_player(self, user_id: int, message: dict):         # send message to specific player    
        with self.lock:
            if user_id in self.players:
                try:
                    send_message(self.players[user_id]['socket'], message)
                except Exception as e:
                    print(f"[GameServer] Failed to send to player {user_id}: {e}")
    
    def end_game(self, winner_id: Optional[int] = None):           # end the game and notify players
        self.broadcast({
            'type': 'game_over',
            'winner': winner_id,
            'message': f'Game Over! Winner: Player {winner_id}' if winner_id else 'Game Over!'
        })
        
        print(f"[GameServer] Game ended. Winner: {winner_id}")
        self.running = False
    
    def cleanup(self):
        """Clean up server resources"""
        print("[GameServer] Shutting down...")
        self.running = False
        
        with self.lock:
            for player in self.players.values():
                try:
                    player['socket'].close()
                except:
                    pass
            self.players.clear()
        
        if self.server_socket:
            self.server_socket.close()
        
        print("[GameServer] Server stopped")

def main():
    if len(sys.argv) < 3:
        print("Usage: python3 game_server.py <host> <port>")
        sys.exit(1)
    
    host = sys.argv[1]
    port = int(sys.argv[2])
    
    server = GameServer(host, port)
    
    try:
        server.start()
    except KeyboardInterrupt:
        print("\n[GameServer] Interrupted by user")
        server.cleanup()

if __name__ == '__main__':
    main()

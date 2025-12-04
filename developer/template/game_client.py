#!/usr/bin/env python3
"""
Game Client Template
This is a template for creating a game client that connects to the game server.
"""
import socket
import sys
import json
import struct
from typing import Optional, Dict, Any

########### protocol part start ###########
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

class GameClient:
    def __init__(self, host, port, user_id, room_id):
        self.host = host
        self.port = port
        self.user_id = user_id
        self.room_id = room_id
        self.socket = None
        self.connected = False
        
    def connect(self):              # connect to game server
        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.connect((self.host, self.port))
            
            identification = {      # send player identification info
                'type': 'player_join',
                'userId': self.user_id,
                'roomId': self.room_id
            }
            send_message(self.socket, identification)
            
            response = recv_message(self.socket)
            if response and response.get('status') == 'success':
                self.connected = True
                print(f"Connected to game server")
                return True
            else:
                print(f"Connection failed: {response.get('message', 'Unknown error')}")
                return False
        except Exception as e:
            print(f"Failed to connect: {e}")
            return False
    
    def run(self):                  # main game loop
        if not self.connect():
            return
        
        print("\n" + "="*60)
        print("    GAME STARTED")
        
        try:
            # TODO: Implement your game initialization here
            self.initialize_game()
            
            # TODO: Implement your game loop here
            while self.connected:
                message = recv_message(self.socket)
                if not message:
                    print("Connection lost")
                    break
                # TODO: Handle different message types
                self.handle_message(message)
                
        except KeyboardInterrupt:
            print("\n\nGame interrupted by user")
        except Exception as e:
            print(f"\nGame error: {e}")
        finally:
            self.cleanup()
    
    def initialize_game(self):                      # initialize game state
        # TODO: Set up game's initial state
        print("Initializing game...")
        pass
    
    def handle_message(self, message: dict):        # handle messages from server
        # TODO: Implement message handling logic
        message_type = message.get('type')
        
        if message_type == 'game_state':
            pass
        elif message_type == 'game_over':
            print(f"\nGame Over!")
            self.connected = False
        else:
            print(f"Unknown message type: {message_type}")
    
    def send_action(self, action: dict):            # send player action to server
        try:
            send_message(self.socket, action)
        except Exception as e:
            print(f"Failed to send action: {e}")
    
    def cleanup(self):                              # clean up resources
        print("\nCleaning up...")
        if self.socket:
            try:
                send_message(self.socket, {'type': 'disconnect'})
            except:
                pass
            self.socket.close()
        print("Disconnected from server")

def main():
    '''Usage: python3 game_client.py <host> <port> <user_id> <room_id>'''
    if len(sys.argv) < 5:
        sys.exit(1)
    host = sys.argv[1]
    port = int(sys.argv[2])
    user_id = int(sys.argv[3])
    room_id = int(sys.argv[4])
    
    client = GameClient(host, port, user_id, room_id)
    client.run()

if __name__ == '__main__':
    main()

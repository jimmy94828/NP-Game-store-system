#!/usr/bin/env python3
"""
Connect Four client used to play a match with the game server.
"""
import socket
import threading
import struct
import json
import time
import sys
import random
import math
from typing import Dict, Optional, Any

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
        header = b''                    # read the 4 bytes header
        while len(header) < 4:
            chunk = sock.recv(4 - len(header))
            if not chunk:
                return None
            header += chunk
            
        if not header:                  # connection closed
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

def display_board(board):               # display the connect four board
    print("-----------------")
    for row in board:
        print("|", end=" ")
        for cell in row:
            if cell == 1:
                print('X', end=' ')
            elif cell == 2:
                print('O', end=' ')
            else:
                print('.', end=' ')
        print('|')
    print("-----------------")
    print("  0 1 2 3 4 5 6")


class ConnectFourClient:
    def __init__(self, host, port, username, room_id):
        self.host = host
        self.port = int(port)
        self.username = username
        self.room_id = room_id
        self.sock = None
        self.player_no = None
        self.running = False
        self.last_state = None
        self.first_board = True     # Flag to track first board display
        self.waiting_for_input = False  # Flag to track if waiting for player input

    def connect(self):              # connect to game server
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.connect((self.host, self.port))
        self.sock.sendall(json.dumps({'username': self.username}).encode())     
        self.running = True

    def run(self):
        buffer = ''
        try:
            while self.running:
                raw = self.sock.recv(8192)
                if not raw:
                    print("Server closed the connection")
                    break
                buffer += raw.decode('utf-8', errors='ignore')              # accumulate received data
                while buffer:                         # process all complete messages in buffer
                    buffer = buffer.lstrip()
                    if not buffer:
                        break
                    try:                                # try to decode a complete JSON message
                        decoder = json.JSONDecoder()
                        message, idx = decoder.raw_decode(buffer)
                        buffer = buffer[idx:]           # Remove parsed message from buffer
                    except json.JSONDecodeError:
                        break
                    
                    try:
                        self.process_message(message)
                    except Exception as e:
                        print(f"Error processing message: {e}")
                        continue
        except KeyboardInterrupt:
            print('\nInterrupted, exiting')
        finally:
            try:
                self.sock.close()
            except Exception:
                pass
    
    def request_move(self):                            # request player move input
        while self.waiting_for_input:
            if self.player_no == 1:
                print(">>> YOUR TURN (Player 1 - X)")
            else:
                print(">>> YOUR TURN (Player 2 - O)")
            try:
                raw_in = input("Your move (column 0-6): ").strip()
            except (KeyboardInterrupt, EOFError):
                print("\n\nGame interrupted, exiting...")
                self.running = False
                self.waiting_for_input = False
                return
            if raw_in == '':
                continue
            try:
                c = int(raw_in)                         # validate input
                if c < 0 or c > 6:                      # Check if number is in valid range (0-6)
                    print("Invalid number! Please enter a number between 0-6")
                    continue
            except ValueError:
                print("Invalid input! Please enter a number between 0-6")
                continue
            self.sock.sendall(json.dumps({'type': 'move', 'column': c}).encode())       # send move to server
            self.waiting_for_input = False              # clear flag after sending move
            break
    
    def process_message(self, message):                # process a received message  

        message_type = message.get('type')
        if message_type == 'assign':                    # receive player assignment
            self.player_no = int(message.get('player'))
            print(f"Assigned as player {self.player_no} ({message.get('player_name')})")
        elif message_type == 'game_state':              # receive game state update
            self.last_state = message            
            if self.first_board:                        # wait for user to start playing
                self.first_board = False
                try:
                    input("\nPress Enter(twice if you are not host) to start playing...")
                except (KeyboardInterrupt, EOFError):
                    print("\n\nGame interrupted, exiting...")
                    self.running = False
                    return
                print()
            
            display_board(message.get('board', []))     # display the board
            winner = message.get('winner')              # check for game over
            if message.get('game_over'):
                if winner == -1:
                    print("Game ended in a draw")
                elif winner is None:
                    print("Game ended")
                else:
                    if winner == self.player_no:
                        print("You won!")
                    else:
                        print("You lost.")
                self.running = False
                return

            cur = message.get('current_player')         # check if it's this player's turn
            if cur == self.player_no:
                self.waiting_for_input = True
                self.request_move()

        elif message_type == 'invalid_move':            # receive invalid move notification
            print("Invalid move, try again")
            self.waiting_for_input = True               # reset flag to request new input
            self.request_move()
        else:
            pass


def main():
    host = sys.argv[1]                                  # get host from command line argument
    port = int(sys.argv[2])                             # get port from command line argument
    user_id = sys.argv[3]                               # get user ID from command line argument
    room_id = sys.argv[4]                               # get room ID from command line argument
    client = ConnectFourClient(host, port, user_id, room_id)
    try:
        client.connect()
        client.run()
    except Exception as e:
        print(f"Failed to run client: {e}")
        sys.exit(1)

if __name__ == '__main__':
    main()

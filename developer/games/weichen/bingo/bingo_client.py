#!/usr/bin/env python3
"""
Multiplayer Bingo game client (3-5 players).
This client connects to the Bingo game server and allows multiple players to play Bingo.
"""
import socket
import json
import sys
import os
import signal

class BingoClient:
    def __init__(self, host, port, username):
        self.host = host
        self.port = int(port)
        self.username = username
        self.socket = None
        self.player_num = None
        self.card = None
        self.marked = [[False] * 5 for _ in range(5)]  # All positions start unmarked
        self.called_numbers = []
        
    def connect(self):                          # connect to game server
        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.connect((self.host, self.port))
            print(f"Connected to game server at {self.host}:{self.port}")
            return True
        except Exception as e:
            print(f"Connection failed: {e}")
            return False
    
    def receive_message(self):                  # receive a JSON message from game server
        try:
            # Receive length prefix (4 bytes)
            header = self.socket.recv(4)
            if not header or len(header) < 4:
                return None
            
            length = int.from_bytes(header, 'big')
            # Receive the actual payload
            data = b''
            while len(data) < length:
                chunk = self.socket.recv(min(4096, length - len(data)))
                if not chunk:
                    return None
                data += chunk
            
            return json.loads(data.decode('utf-8'))
        except Exception as e:
            print(f"Receive error: {e}")
            return None
    
    def send_message(self, message):                # send a JSON message to game server
        try:
            payload = json.dumps(message).encode('utf-8')
            length = len(payload)
            header = length.to_bytes(4, 'big')
            self.socket.sendall(header + payload)
        except Exception as e:
            print(f"Send error: {e}")
    
    def display_card(self):                     # display the bingo card  
        print("\n" + "="*40)
        print(f"       Your Bingo Card (Player {self.player_num})")
        print("="*40)
        print("   B    I    N    G    O")
        print("-" * 30)
        for row in range(5):
            print("|", end="")
            for col in range(5):
                num = self.card[row][col]
                if self.marked[row][col]:
                    marker = f"[{num:2d}]"  # Marked numbers shown in brackets
                else:
                    marker = f" {num:2d} "   # Unmarked numbers
                print(f"{marker:5s}", end="|")
            print()
        print("-" * 30)
        
        if self.called_numbers:
            print(f"\nCalled numbers: {', '.join(map(str, sorted(self.called_numbers)))}")
        print("="*40)
    
    def play(self):
        if not self.connect():                              # connect to server
            return
        
        print("\n" + "="*50)
        print("       Welcome to 3-Player Bingo! ")
        print(f"Player: {self.username}")
        message = self.receive_message()                    # receive the player number
        if message and message.get('type') == 'assign':
            self.player_num = message['player']
            print(f"\nYou are Player {self.player_num}")

        message = self.receive_message()                    # receive the bingo card
        if message and message.get('type') == 'card':
            self.card = message['numbers']
            self.display_card()
        
        print("\nWaiting for game to start...")
        input("\nPress Enter(twice if you are not host) to start playing...")
        game_over = False
        
        while not game_over:
            try:
                message = self.receive_message()            # receive game state updates
                if not message:
                    print("\nConnection lost!")
                    break
                
                if message.get('type') == 'game_state':
                    current_player = message.get('current_player')
                    last_called = message.get('last_called')
                    self.called_numbers = message.get('called_numbers', [])
                    if last_called:                         # mark the called number
                        for row in range(5):
                            for col in range(5):
                                if self.card[row][col] == last_called:
                                    self.marked[row][col] = True
                        print(f"\n>>> Number {last_called} was called!")
                    
                    self.display_card()
                    
                    # Check if game is over (server determines winner)
                    if message.get('game_over'):
                        winner = message.get('winner')
                        disconnected_player = message.get('disconnected_player')
                        print("\n" + "="*50)
                        if disconnected_player:
                            print(f"       Player {disconnected_player} disconnected!")
                            print("       Game ended.")
                        elif winner == self.player_num:
                            print("        BINGO! YOU WIN! ")
                        else:
                            print(f"       Game Over - Player {winner} wins!")
                        print("="*50)
                        game_over = True
                        break
                    
                    if current_player == self.player_num:   # player's turn to call a number
                        print(f"\n>>> YOUR TURN (Player {self.player_num})")
                        
                        # Keep asking until valid input is provided
                        interrupted = False
                        while True:
                            try:
                                print("Enter a number (1-75) to call: ", end="", flush=True)
                                try:
                                    user_input = input()
                                except KeyboardInterrupt:
                                    print("\n\nGame interrupted by user!")
                                    interrupted = True
                                    break
                                
                                try:
                                    number = int(user_input)
                                except ValueError:
                                    print("Invalid input! Please enter a number.")
                                    continue
                                
                                if number < 1 or number > 75:
                                    print("Invalid number! Must be between 1-75")
                                    continue  # Stay in input loop
                                
                                # Valid input, send to server
                                self.send_message({
                                    'type': 'call',
                                    'number': number
                                })
                                break  # Exit input loop after sending
                                
                            except EOFError:
                                print("\nInput closed, exiting...")
                                interrupted = True
                                break
                        
                        if interrupted:
                            game_over = True
                            break
                    else:
                        print(f"\n>>> Waiting for Player {current_player}'s turn...")
                
                elif message.get('type') == 'error':
                    error_msg = message.get('message', 'Unknown error')
                    print(f"\nError: {error_msg}")
                    # input invalid number - only current player needs to retry
                    if message.get('current_player') == self.player_num:
                        print("Please try again.")
                        interrupted = False
                        while True:
                            try:
                                print("Enter a number (1-75) to call: ", end="", flush=True)
                                try:
                                    user_input = input()
                                except KeyboardInterrupt:
                                    print("\n\nGame interrupted by user!")
                                    interrupted = True
                                    break
                                
                                try:
                                    number = int(user_input)
                                except ValueError:
                                    print("Invalid input! Please enter a number.")
                                    continue
                                
                                if number < 1 or number > 75:
                                    print("Invalid number! Please enter a number between 1-75.")
                                    continue
                                self.send_message({
                                    'type': 'call',
                                    'number': number
                                })
                                break               # the number sent successfully, break the loop
                                
                            except EOFError:
                                print("\nInput closed, exiting...")
                                interrupted = True
                                break
                            except Exception as e:
                                print(f"Error: {e}")
                                continue
                        
                        if interrupted:
                            game_over = True
                            break
            
            except KeyboardInterrupt:
                print("\n\nGame interrupted!")
                break
            except Exception as e:
                print(f"\nError: {e}")
                break
        
        if not game_over:
            print("\n" + "="*50)
            print("  Connection lost or game interrupted")
            print("="*50)
        
        input("\nPress Enter to exit...")
        
        try:
            self.socket.close()
        except:
            pass

def main():
    '''Usage: python3 bingo_client.py <host> <port> <username> <room_id>'''
    if len(sys.argv) < 4:
        sys.exit(1)
    
    host = sys.argv[1]
    port = sys.argv[2]
    username = sys.argv[3]
    # room_id = sys.argv[4]  # Not used in client, but kept for compatibility
    
    client = BingoClient(host, port, username)
    client.play()

if __name__ == '__main__':
    main()

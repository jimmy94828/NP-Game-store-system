"""
Developer Client
"""
import socket
import struct
import json
import os
import hashlib
import subprocess
from typing import Dict, Optional, Any

DEVELOPER_SERVER_HOST = '140.113.17.11'
DEVELOPER_SERVER_PORT = 17049

LENGTH_LIMIT = 65536

############# protocol part start ###########
class ProtocolError(Exception):
    pass

def send_message(sock: socket.socket, data: Dict[Any, Any]) -> None:        # send a message to the server
    try:
        message = json.dumps(data, ensure_ascii=False).encode('utf-8')
        length = len(message)
        if length > LENGTH_LIMIT:
            raise ProtocolError(f"Message too large: {length} > {LENGTH_LIMIT}")
        header = struct.pack('!I', length)
        sock.sendall(header + message)
    except socket.error as error:
        raise ProtocolError(f"Socket error while sending: {error}")

def recv_message(sock: socket.socket) -> Optional[Dict[Any, Any]]:          # receive a message from the server
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
        data = json.loads(message.decode('utf-8'))
        return data
    except Exception as error:
        raise ProtocolError(f"Error receiving message: {error}")

def send_file(sock: socket.socket, file_path: str) -> bool:         # send a file to the server
    try:
        file_size = os.path.getsize(file_path)
        metadata = {
            'type': 'FILE_METADATA',
            'size': file_size,
            'name': os.path.basename(file_path)
        }
        send_message(sock, metadata)
        
        with open(file_path, 'rb') as f:
            sent = 0
            while sent < file_size:
                chunk = f.read(8192)
                if not chunk:
                    break
                sock.sendall(chunk)
                sent += len(chunk)
        return True
    except Exception as e:
        print(f"Error sending file: {e}")
        return False

############## protocol part end ###########

class DeveloperClient:
    def __init__(self, host=DEVELOPER_SERVER_HOST, port=DEVELOPER_SERVER_PORT):
        self.host = host
        self.port = port
        self.socket = None
        self.dev_id = None
        self.username = None
        self.running = False
        # Local development games root the developer games folder
        self.games_root = os.path.join(os.path.dirname(__file__), 'games')
        self.games_dir = self.games_root
        if not os.path.exists(self.games_root):
            # create per-developer folder on login
            print(f"Note: expected developer games root '{self.games_root}' not found. It will be created when you login.")
    
    def connect(self):                                  # connect to developer server
        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.connect((self.host, self.port))
            print(f"Connected to Developer Server at {self.host}:{self.port}")
            return True
        except Exception as error:
            print(f"Failed to connect: {error}")
            return False
    
    def send_command(self, command, data=None):     # send a command to the server and wait for response
        try:
            request = {'command': command}
            if data:
                request.update(data)
            send_message(self.socket, request)
            response = recv_message(self.socket)
            if response is None:
                print("\n[Error] Server disconnected. Exiting...")
                self.running = False
                import sys
                sys.exit(0)
            return response
        except Exception as error:
            print(f"Error sending command: {error}")
            print("\n[Error] Lost connection to server. Exiting...")
            self.running = False
            import sys
            sys.exit(0)
    
    def main_menu(self):                                # display main menu options
        print("\n" + "="*50)
        print("=== Developer Client - Main Menu ===")
        print(f"Logged in as: {self.username} (Dev ID: {self.dev_id})")
        print()
        print("1. Check My Game / Upload New Game")
        print("2. Update Existing Game")
        print("3. Remove Game")
        print("4. List My Uploaded Games")
        print("5. Create Game from Template")
        print("6. Logout")
        print("0. Exit")
        print("="*50)
    
    def register(self):                                 # register a new developer account
        print("\n=== Developer Registration ===")
        try:
            username = input("Username: ").strip()
            password = input("Password: ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\n\nRegistration cancelled")
            return False
        
        if not username or not password:
            print("Username and password cannot be empty")
            return False
        
        response = self.send_command('dev_register', {
            'username': username,
            'password': password
        })
        
        if response and response['status'] == 'success':
            print(f"Registration successful! Developer ID: {response['devId']}")
            print("Please login to continue.")
            return True
        else:
            print(f"Registration failed: {response.get('message', 'Unknown error')}")
            return False
    
    def login(self):                                    # developer login
        print("\n=== Developer Login ===")
        try:
            username = input("Username: ").strip()
            password = input("Password: ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\n\nLogin cancelled")
            return False
        
        if not username or not password:
            print("Username and password are required")
            return False
        
        response = self.send_command('dev_login', {
            'username': username,
            'password': password
        })
        
        if response and response['status'] == 'success':
            self.dev_id = response['devId']
            self.username = username
            try:                                        # create per-developer games directory
                self.games_dir = os.path.join(self.games_root, self.username)
                check = not os.path.exists(self.games_dir)              # auto load three supported games
                os.makedirs(self.games_dir, exist_ok=True)
                if check:
                    ssupport_dir = os.path.join(self.games_root, 'weichen')
                    if os.path.exists(ssupport_dir):
                        import shutil
                        for game in ['bingo', 'connect_four', 'tetris']:
                            source = os.path.join(ssupport_dir, game)
                            distination = os.path.join(self.games_dir, game)
                            if os.path.exists(source) and not os.path.exists(distination):
                                try:
                                    shutil.copytree(source, distination)
                                    print(f"Copied supported game: {game}")
                                except Exception as e:
                                    print(f"Warning: failed to copy {game}: {e}")
            except Exception:
                print(f"Warning: failed to create developer games directory '{self.games_dir}'")

            print(f"Login successful! Welcome, {username}")
            return True
        else:
            print(f"Login failed: {response.get('message', 'Unknown error')}")
            return False
    
    def logout(self):                                   # developer logout
        if not self.dev_id:
            print("You are not logged in")
            return False
        
        response = self.send_command('dev_logout', {'devId': self.dev_id})
        
        if response and response['status'] == 'success':
            print("Logout successful!")
            self.dev_id = None
            self.username = None
            return True
        else:
            print(f"Logout failed: {response.get('message', 'Unknown error')}")
            return False
    
    def list_local_games(self):                         # list local games in development directory
        try:
            games = [d for d in os.listdir(self.games_dir) if os.path.isdir(os.path.join(self.games_dir, d))]
            return games
        except Exception as e:
            print(f"Error listing games: {e}")
            return []
    
    def upload_game(self):                              # upload a new game to the server
        print("\n=== Upload New Game ===")
        
        local_games = self.list_local_games()           # list local game folders
        if not local_games:
            print(f"No games found in development directory ({self.games_dir})")
            print("Please create a game folder first.")
            return
        
        print("\nAvailable games in development directory:")
        for i, game in enumerate(local_games, 1):
            print(f"{i}. {game}")
        
        try:
            choice = int(input("\nSelect game number (Enter to return): ").strip())
            if choice < 1 or choice > len(local_games):
                print("Invalid selection")
                return
            
            game_folder = local_games[choice - 1]
            game_path = os.path.join(self.games_dir, game_folder)
            
        except ValueError:
            print("Invalid input")
            return
        
        config_path = os.path.join(game_path, 'config.json')        # read or create config.json
        game_info = {}
        
        if os.path.exists(config_path):                             # load existing config file
            try:
                with open(config_path, 'r', encoding='utf-8') as f:
                    game_info = json.load(f)
                print(f"\n=== Current Configuration ===")
                print(json.dumps(game_info, indent=2, ensure_ascii=False))
            except json.JSONDecodeError as e:
                print(f"\nWarning: Invalid JSON in config.json: {e}")
                print("Starting with empty config...")
                game_info = {}
            except Exception as e:
                print(f"\nWarning: Error reading config.json: {e}")
                print("Starting with empty config...")
                game_info = {}
        else:
            print(f"\nNo existing config.json found. Creating new configuration...")
        
        print("\n=== Configure Game Information ===")                   # prompt for required fields
        print("Please enter the following information (all fields required):\n")
        print("You can press Enter to keep the current value shown in [brackets].\n")
        
        required_fields = [
            ('name', 'Game Name', 'string'),
            ('version', 'Version (e.g., 1.0.0)', 'string'),
            ('gameType', 'Game Type (e.g., GUI, CLI)', 'string'),
            ('maxPlayers', 'Maximum Players', 'int'),
            ('description', 'Game Description', 'string'),
            ('mainFile', 'Client File (e.g., game_client.py)', 'string'),
            ('serverFile', 'Server File (e.g., game_server.py)', 'string')
        ]
        
        for field_name, field_prompt, field_type in required_fields:        # prompt for each field
            while True:
                current = game_info.get(field_name, '')
                if current:
                    prompt_text = f"{field_prompt} [{current}]: "
                else:
                    prompt_text = f"{field_prompt}: "
                
                value = input(prompt_text).strip()                          # get user input
                
                if not value and current:                   # keep current value if input is empty
                    value = str(current)
                if not value:                               # validate non-empty
                    print("  This field cannot be empty. Please enter a value.")
                    continue                
                if field_name == 'version':                 # version format validation (x.y.z)
                    import re
                    version_pattern = r'^\d+\.\d+\.\d+$'
                    if not re.match(version_pattern, value):
                        print(f"     Invalid version format: {value}")
                        print(f"     Version must follow x.y.z format (e.g., 1.0.0, 2.1.3)")
                        print(f"     Where x, y, z are non-negative integers")
                        continue
                    else:
                        print(f"     Version format validated: {value}")
                
                if field_name == 'maxPlayers':              # maxPlayers validation
                    try:
                        max_players = int(value)
                        if max_players < 2:
                            print("     Maximum players must be at least 2")
                            continue
                    except ValueError:
                        print("     Please enter a valid number for maximum players")
                        continue
                
                if field_name in ['mainFile', 'serverFile']:        # file existence validation
                    file_path = os.path.join(game_path, value)
                    if not os.path.exists(file_path):
                        print(f"     File not found: {value}")
                        print(f"     Full path: {file_path}")
                        print(f"     Please ensure this file exists in the game directory")
                        retry = input("     Enter 'r' to retry, 's' to skip validation: ").strip().lower()
                        if retry != 's':
                            continue
                        else:
                            print(f"  WARNING: Proceeding with non-existent file!")
                    elif not os.path.isfile(file_path):
                        print(f"     Path exists but is not a file: {value}")
                        print(f"     Please specify a file, not a directory")
                        continue
                    else:
                        print(f"     File validated: {value}")
                
                if field_type == 'int':
                    try:
                        value = int(value)
                    except ValueError:
                        print("  Please enter a valid number.")
                        continue
                
                game_info[field_name] = value
                break
        
        print("\n=== Final Configuration ===")                  # display final configuration
        print(json.dumps(game_info, indent=2, ensure_ascii=False))
        
        try:                                                    # save to config.json               
            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump(game_info, f, indent=2, ensure_ascii=False)
            print(f"\nConfiguration saved to {config_path}")
        except Exception as e:
            print(f"\nError saving config.json: {e}")
            return
        
        confirm = input("\nProceed with upload? (y/n): ").strip().lower()       # confirm upload
        if confirm != 'y':
            print("Upload cancelled")
            return
        
        files_to_upload = []                                    # collect files to upload
        for root, dirs, files in os.walk(game_path):
            for file in files:
                file_path = os.path.join(root, file)
                rel_path = os.path.relpath(file_path, game_path)
                files_to_upload.append((file_path, rel_path))
        
        if not files_to_upload:
            print("No files found in game directory")
            return
        
        print(f"\nFound {len(files_to_upload)} files to upload")
        
        response = self.send_command('upload_game', {           # send upload request
            'devId': self.dev_id,
            'gameInfo': game_info,
            'fileCount': len(files_to_upload)
        })
        
        if not response or response['status'] != 'ready':
            print(f"Upload failed: {response.get('message', 'Unknown error')}")
            return
        
        print("\nUploading files...")
        for i, (file_path, rel_path) in enumerate(files_to_upload, 1):
            print(f"  [{i}/{len(files_to_upload)}] {rel_path}", end='... ')
            
            send_message(self.socket, {'name': rel_path})
            
            if not send_file(self.socket, file_path):
                print("Upload incomplete")
                return
            print("uploaded")
        
        final_response = recv_message(self.socket)              # get final response
        if final_response and final_response['status'] == 'success':
            print(f"\nGame uploaded successfully! Game ID: {final_response['gameId']}")
        else:
            print(f"\nUpload failed: {final_response.get('message', 'Unknown error')}")
    
    def list_my_games(self, return_prompt="or press Enter to return"):  # list games uploaded by the developer
        print("\n=== My Games ===")
        response = self.send_command('list_my_games', {'devId': self.dev_id})
        if not response or response['status'] != 'success':
            print(f"Failed to retrieve games: {response.get('message', 'Unknown error')}")
            return []
        
        games = response.get('games', [])
        if not games:
            print("You haven't uploaded any games yet.")
            return []
        
        print(f"\nFound {len(games)} game(s):\n")
        for i, game in enumerate(games, 1):
            status_icon = "V" if game['status'] == 'active' else "X"
            avg_rating = game.get('averageRating', 'N/A')
            rating_count = len(game.get('ratings', []))
            review_count = len(game.get('reviews', []))
            
            print(f"{i}. [{status_icon}] {game['name']}")
            print(f"   ID: {game['id']} | Version: {game['currentVersion']} | Type: {game['gameType']}")
            print(f"   Players: {game['maxPlayers']} | Status: {game['status']}")
            print(f"   Rating: {avg_rating} ({rating_count} ratings, {review_count} reviews)")
            print(f"   Description: {game['description']}")
        
        while True:                                 # view game details loop
            choice = input(f"\nEnter game number to view details ({return_prompt}): ").strip()
            if not choice:
                break
            try:
                game_num = int(choice)
                if 1 <= game_num <= len(games):
                    self.view_game_details(games[game_num - 1])
                else:
                    print(f"Invalid number. Please enter 1-{len(games)}")
            except ValueError:
                print("Invalid input. Please enter a number or press Enter to return.")
        
        return games
    
    def view_game_details(self, game):              # view detailed information about a game
        print(f"=== Game Details: {game['name']} ===")
        print(f"Game ID: {game['id']}")
        print(f"Version: {game['currentVersion']}")
        print(f"Type: {game['gameType']} | Max Players: {game['maxPlayers']}")
        print(f"Status: {game['status']}")
        print(f"Description: {game.get('description', 'N/A')}")
        print(f"Uploaded: {game.get('uploadedAt', 'N/A')}")
        print(f"Last Updated: {game.get('updatedAt', 'N/A')}")
        
        ratings = game.get('ratings', [])           # display ratings summary
        print(f"\n--- Ratings ({len(ratings)} total) ---")
        if ratings:
            total = sum(ratings)
            avg = total / len(ratings)
            print(f"Average Rating: {avg:.2f} / 5.0")
            print(f"Rating Distribution:")
            for star in range(5, -1, -1):
                count = ratings.count(star)
                bar = '+' * count
                if star != 1 and star != 0:
                    print(f"  {star} stars: {bar} ({count})")
                else:
                    print(f"  {star} star : {bar} ({count})")
        else:
            print("No ratings yet.")
        
        reviews = game.get('reviews', [])            # display reviews
        print(f"\n--- Reviews ({len(reviews)} total) ---")
        if reviews:
            for i, review in enumerate(reviews, 1):
                print(f"\n{i}. User: {review.get('userId', 'Unknown')}")
                print(f"   Comment: {review.get('text', 'No comment')}")
                print(f"   Reviewed at: {review.get('timestamp', 'N/A')}")
        else:
            print("No reviews yet.")
        
        input("\nPress Enter to continue...")
    
    def update_game(self):                          # update an existing game
        print("\n=== Update Game ===")
        games = self.list_my_games(return_prompt="or press Enter to continue update")
        if not games:
            return
        try:
            choice = int(input("Select game number to update: ").strip())
            if choice < 1 or choice > len(games):
                print("Invalid selection")
                return
            
            game = games[choice - 1]
            
            if game['status'] != 'active':
                print("Cannot update inactive game")
                return
            
        except ValueError:
            print("Invalid input")
            return
        
        local_games = self.list_local_games()           # list local game folders
        if not local_games:
            print(f"No games found in development directory ({self.games_dir})")
            return
        
        print("\nSelect updated game folder:")
        for i, game_folder in enumerate(local_games, 1):
            print(f"{i}. {game_folder}")
        
        try:
            folder_choice = int(input("Select folder number: ").strip())
            if folder_choice < 1 or folder_choice > len(local_games):
                print("Invalid selection")
                return
            
            game_folder = local_games[folder_choice - 1]
            game_path = os.path.join(self.games_dir, game_folder)
            
        except ValueError:
            print("Invalid input")
            return
        
        config_path = os.path.join(game_path, 'config.json')
        game_info = {}
        
        if os.path.exists(config_path):                 # load existing config file
            try:
                with open(config_path, 'r', encoding='utf-8') as f:
                    game_info = json.load(f)
                print(f"\n=== Current Configuration ===")
                print(json.dumps(game_info, indent=2, ensure_ascii=False))
            except json.JSONDecodeError as e:
                print(f"\nWarning: Invalid JSON in config.json: {e}")
                print("Starting with empty config...")
                game_info = {}
            except Exception as e:
                print(f"\nWarning: Error reading config.json: {e}")
                print("Starting with empty config...")
                game_info = {}
        else:
            print(f"\nError: config.json not found in {game_path}")
            print("Creating new configuration...")
        
        # Prompt for each required field
        print(f"\n=== Update Game Configuration ===")
        print(f"Current game version in database: {game['currentVersion']}")
        print("\nPlease input the following information (all fields required \n enter to keep value in []):\n")
        
        required_fields = [
            ('name', 'Game Name', 'string'),
            ('version', 'Version (e.g., 1.0.0)', 'string'),
            ('gameType', 'Game Type (e.g., GUI, Terminal)', 'string'),
            ('maxPlayers', 'Maximum Players', 'int'),
            ('description', 'Game Description', 'string'),
            ('mainFile', 'Main Client File (e.g., game_client.py)', 'string'),
            ('serverFile', 'Server File (e.g., game_server.py)', 'string')
        ]
        
        for field_name, field_prompt, field_type in required_fields:
            while True:
                current = game_info.get(field_name, '')
                if current:
                    prompt_text = f"{field_prompt} [{current}]: "
                else:
                    prompt_text = f"{field_prompt}: "
                
                value = input(prompt_text).strip()
                
                if not value and current:                   # keep current value if input is empty
                    value = str(current)
                
                if not value:                               # validate non-empty
                    print("  This field cannot be empty. Please enter a value.")
                    continue
                
                if field_name == 'version':                 # version format validation (x.y.z)
                    import re
                    version_pattern = r'^\d+\.\d+\.\d+$'
                    if not re.match(version_pattern, value):
                        print(f"     Invalid version format: {value}")
                        print(f"     Version must follow x.y.z format (e.g., 1.0.0, 2.1.3)")
                        print(f"     Where x, y, z are non-negative integers")
                        continue
                    else:
                        print(f"     Version format validated: {value}")
                
                if field_name in ['mainFile', 'serverFile']:        # check file existence
                    file_path = os.path.join(game_path, value)
                    if not os.path.exists(file_path):
                        print(f"     File not found: {value}")
                        print(f"     Full path: {file_path}")
                        print(f"     Please ensure this file exists in the game directory")
                        retry = input("     Enter 'r' to retry, 's' to skip validation: ").strip().lower()
                        if retry != 's':
                            continue
                        else:
                            print(f"   WARNING: Proceeding with non-existent file!")
                    elif not os.path.isfile(file_path):
                        print(f"     Path exists but is not a file: {value}")
                        print(f"     Please specify a file, not a directory")
                        continue
                    else:
                        print(f"     File validated: {value}")
                
                if field_type == 'int':
                    try:
                        value = int(value)
                    except ValueError:
                        print("  Please enter a valid number.")
                        continue
                
                game_info[field_name] = value
                break
        
        new_version = game_info.get('version')
        if not new_version:
            print("Error: version field missing")
            return
        
        print(f"\n=== Final Configuration ===")             # display final configuration   
        print(f"Current version: {game['currentVersion']}")
        print(f"New version: {new_version}")
        print(f"\nConfig content:")
        print(json.dumps(game_info, indent=2, ensure_ascii=False))
        
        try:                                                # save to config.json
            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump(game_info, f, indent=2, ensure_ascii=False)
            print(f"\nConfiguration saved to {config_path}")
        except Exception as e:
            print(f"\nError saving config.json: {e}")
            return
        
        files_to_upload = []                                # collect files to upload
        for root, dirs, files in os.walk(game_path):
            for file in files:
                file_path = os.path.join(root, file)
                rel_path = os.path.relpath(file_path, game_path)
                files_to_upload.append((file_path, rel_path))
        
        if not files_to_upload:
            print("No files found")
            return
        
        print(f"\nFound {len(files_to_upload)} files to upload")
        confirm = input("Proceed with update? (y/n): ").strip().lower()
        if confirm != 'y':
            print("Update cancelled")
            return
        
        response = self.send_command('update_game', {       # send update request
            'devId': self.dev_id,
            'gameId': game['id'],
            'gameInfo': game_info,
            'fileCount': len(files_to_upload)
        })
        
        if not response or response['status'] != 'ready':   # check server readiness
            print(f"Update failed: {response.get('message', 'Unknown error')}")
            return

        print("\nUploading files...")
        for i, (file_path, rel_path) in enumerate(files_to_upload, 1):
            print(f"  [{i}/{len(files_to_upload)}] {rel_path}", end='... ')
            
            send_message(self.socket, {'name': rel_path})
            
            if not send_file(self.socket, file_path):
                print("Failed")
                return
            print("uploaded")
        
        final_response = recv_message(self.socket)              # get final response
        if final_response and final_response['status'] == 'success':
            print(f"\nGame updated successfully to version {new_version}!")
        else:
            print(f"\nUpdate failed: {final_response.get('message', 'Unknown error')}")
    
    def remove_game(self):                                      # remove a game from the server
        print("\n=== Remove Game ===")
        games = self.list_my_games(return_prompt="or press Enter to continue removing a game")                            # list developer's games
        if not games:
            return
        try:
            choice = int(input("Select game number to remove: ").strip())
            if choice < 1 or choice > len(games):
                print("Invalid selection")
                return
            
            game = games[choice - 1]
            
            if game['status'] != 'active':                      # the game is already inactive
                print("Game is already inactive")
                return
            
        except ValueError:
            print("Invalid input")
            return
        
        print(f"\nWARNING: This will delist '{game['name']}' from the store.")
        print("Players will no longer be able to download or create new rooms for this game.")
        confirm = input("Are you sure? (y/n): ").strip().lower()
        
        if confirm != 'y':
            print("Removal cancelled")
            return
        
        response = self.send_command('remove_game', {           # send remove request
            'devId': self.dev_id,
            'gameId': game['id']
        })
        
        if response and response['status'] == 'success':
            print(f"Game '{game['name']}' has been removed successfully")
        else:
            print(f"Removal failed: {response.get('message', 'Unknown error')}")
    
    def create_from_template(self):                             # create a new game template
        print("\n=== Create Game from Template ===")        
        confirm = input("Continue? (y/n): ").strip().lower()
        if confirm != 'y':
            print("Cancelled")
            return        
        script_path = os.path.join(os.path.dirname(__file__), 'create_game_template.py')
        
        if not os.path.exists(script_path):
            print(f"\nError: Template script not found at {script_path}")
            print("Please ensure create_game_template.py exists in the developer folder.")
            return
        
        import subprocess
        try:
            # Pass the current developer username as an argument
            result = subprocess.run(
                ['python3', script_path, self.username],
                cwd=os.path.dirname(__file__)
            )            
            if result.returncode == 0:
                print("\nTemplate creation completed!")
                print("\nYour new game is ready in the games folder.")
            else:
                print("\nTemplate creation was interrupted or failed.")
        except Exception as e:
            print(f"\nError running template script: {e}")
        
        input("\nPress Enter to continue...")
    
    def run(self):                  # start developer client
        if not self.connect():
            return
        
        self.running = True
        logged_in = False
              
        try:
            while self.running:
                if not logged_in:
                    print("\n" + "="*50)
                    print("         Game Developer Platform")  
                    print("\n1. Register")
                    print("2. Login")
                    print("0. Exit")
                    
                    try:
                        choice = input("\nEnter choice: ").strip()
                    except (KeyboardInterrupt, EOFError):
                        print("\n\nExiting...")
                        self.running = False
                        break
                    
                    if choice == '1':
                        self.register()
                    elif choice == '2':
                        logged_in = self.login()
                    elif choice == '0':
                        print("\nExit!")
                        self.running = False
                    else:
                        print("Invalid choice")
                else:
                    self.main_menu()
                    try:
                        choice = input("\nEnter choice: ").strip()
                    except (KeyboardInterrupt, EOFError):
                        print("\n\nExiting...")
                        self.running = False
                        break
                    
                    if choice == '1':
                        self.upload_game()
                    elif choice == '2':
                        self.update_game()
                    elif choice == '3':
                        self.remove_game()
                    elif choice == '4':
                        self.list_my_games()
                    elif choice == '5':
                        self.create_from_template()
                    elif choice == '6':
                        if self.logout():
                            logged_in = False
                    elif choice == '0':
                        print("\nExit!")
                        self.running = False
                    else:
                        print("Invalid choice")
        except KeyboardInterrupt:
            print("\n\nExiting...")
            self.running = False
        except EOFError:
            print("\n\nExiting...")
            self.running = False
        finally:
            if self.socket:
                try:
                    self.socket.close()
                except:
                    pass

def main():
    import sys
    host = sys.argv[1] if len(sys.argv) > 1 else DEVELOPER_SERVER_HOST
    port = int(sys.argv[2]) if len(sys.argv) > 2 else DEVELOPER_SERVER_PORT
    
    client = DeveloperClient(host, port)
    client.run()

if __name__ == '__main__':
    main()
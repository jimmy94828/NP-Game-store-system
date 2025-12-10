"""
Lobby Client
"""
import socket
import threading
import struct
import json
import time
import sys
import os
import subprocess
from datetime import datetime
from typing import Dict, Optional, Any

LOBBYSERVER_HOST = '140.113.17.11'
LOBBYSERVER_PORT = 17048

LENGTH_LIMIT = 65536
############ protocol part start ############
class ProtocolError(Exception):
    pass

def send_message(sock: socket.socket, data: Dict[Any, Any]) -> None:
    try:
        message = json.dumps(data, ensure_ascii=False).encode('utf-8')
        length = len(message)
        if length > LENGTH_LIMIT:
            raise ProtocolError(f"Message too large: {length} > {LENGTH_LIMIT}")
        header = struct.pack('!I', length)
        sock.sendall(header + message)
    except socket.error as error:
        raise ProtocolError(f"Socket error while sending: {error}")

def recv_message(sock: socket.socket) -> Optional[Dict[Any, Any]]:
    try:
        header = b''
        while len(header) < 4:
            chunk = sock.recv(4 - len(header))
            if not chunk:
                return None
            header += chunk
        if not header:
            return None
        length = struct.unpack('!I', header)[0]
        if length <= 0 or length > LENGTH_LIMIT:
            raise ProtocolError(f"Invalid message length: {length}")
        message = b''
        while len(message) < length:
            chunk = sock.recv(length - len(message))
            if not chunk:
                return None
            message += chunk
        if not message:
            raise ProtocolError("Connection closed")
        data = json.loads(message.decode('utf-8'))
        return data
    except socket.error as error:
        raise ProtocolError(f"Socket error: {error}")
    except json.JSONDecodeError as error:
        raise ProtocolError(f"Invalid JSON: {error}")

def recv_file(sock: socket.socket, save_path: str) -> bool:     # receive a file over socket with chunked transfer
    try:
        metadata = recv_message(sock)
        if not metadata or metadata.get('type') != 'FILE_METADATA':
            return False
        
        file_size = metadata['size']
        received = 0
        
        os.makedirs(os.path.dirname(save_path), exist_ok=True)
        
        with open(save_path, 'wb') as f:
            while received < file_size:
                chunk_size = min(8192, file_size - received)
                chunk = sock.recv(chunk_size)
                if not chunk:
                    break
                f.write(chunk)
                received += len(chunk)
        
        return received == file_size
    except Exception as e:
        print(f"Error receiving file: {e}")
        return False
#################### protocol part end ################

class EnhancedLobbyClient:
    def __init__(self, host=LOBBYSERVER_HOST, port=LOBBYSERVER_PORT, player_name=None):
        self.host = host
        self.port = port
        self.socket = None
        self.user_id = None
        self.username = None
        self.current_room_id = None
        self.is_host = False
        self.running = False
        self.notification_thread = None
        self.waiting_for_game = False
        self.game_just_ended = False
        self.game_in_progress = False                               # flag to prevent menu input during CLI game
        
        self.player_name = player_name or "Player1"                 # default player name
        player_dir = os.path.dirname(__file__)
        downloads_root = os.path.join(player_dir, 'downloads')
        self.downloads_dir = os.path.join(downloads_root, self.player_name)         # downloads/<player>
        try:
            os.makedirs(self.downloads_dir, exist_ok=True)
        except Exception:
            print(f"Warning: failed to ensure downloads directory '{self.downloads_dir}'.")
    
    def connect_lobby(self):                                        # connect to lobby server
        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.connect((self.host, self.port))
            print(f"Connected to lobby server at {self.host}:{self.port}")
            return True
        except Exception as error:
            print(f"Failed to connect: {error}")
            return False
    
    def send_command(self, command, data=None):                     # send a command to lobby server and wait for response
        try:
            request = {'command': command}
            if data:
                request.update(data)
            send_message(self.socket, request)
            response = recv_message(self.socket)
            return response
        except Exception as error:
            print(f"Error sending command: {error}")
            return {'status': 'error', 'message': str(error)}
    
    def main_menu(self):                                            # main menu display
        print("=== MAIN MENU ===")
        print(f"Player: {self.username} (ID: {self.user_id})")
        print()
        print("1. Game Store")
        print("2. Lobby")
        print("3. Logout")
        print("4. Exit")

    def game_store_menu(self):                                      # game store menu   
        while True:
            print("\n=== GAME STORE ===")
            print("1. Browse Game Store")
            print("2. View Game Details")
            print("3. Download/Update Game")
            print("4. My Downloaded Games")
            print("5. Rate & Review Game")
            print("0. Back")
            choice = input("\nEnter choice: ").strip()
            if choice == '1':
                self.browse_store()
            elif choice == '2':
                self.view_game_details()
            elif choice == '3':
                self.download_game()
            elif choice == '4':
                self.list_downloaded_games()
            elif choice == '5':
                self.rate_and_review_game()
            elif choice == '0':
                break
            else:
                print("Invalid choice")

    def lobby_menu(self):                                   # lobby menu
        while True:
            try:
                print("\n=== LOBBY MENU ===")
                print("1. View Online Players")
                print("2. View Active Rooms")
                print("3. Create Room & Play")
                print("4. Join Room & Play")
                print("5. View Invitations")
                print("6. Accept Invitation")
                print("0. Back")
                choice = input("\nEnter choice: ").strip()
                if choice == '1':
                    self.list_users()
                elif choice == '2':
                    self.list_rooms()
                elif choice == '3':
                    self.create_room_and_play()
                    if self.current_room_id:                # If room was created successfully, exit lobby menu
                        break
                elif choice == '4':
                    self.join_room()
                    if self.current_room_id:                # If joined successfully, exit lobby menu
                        break
                elif choice == '5':
                    self.list_invitations()
                elif choice == '6':
                    self.accept_invitation()
                    if self.current_room_id:                # If accepted successfully, exit lobby menu
                        break
                elif choice == '0':
                    break
                else:
                    print("Invalid choice")
            except Exception as error:
                print(f"Error in lobby menu: {error}")
                break
    
    def host_menu(self):
        print("\n=== HOST MENU ===")
        print(f"Room ID: {self.current_room_id} (You are the HOST)")
        print()
        print("1. Start Game")
        print("2. Invite Player")
        print("3. Leave Room")
    
    def member_menu(self):
        print("\n=== ROOM MENU ===")
        print(f"Room ID: {self.current_room_id} (Waiting for host...)")
        print()
        print("1. Leave Room")
    
    def register(self):                 # player registration
        print("\n=== Player Registration ===")
        try:
            username = input("Username: ").strip()
            password = input("Password: ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\n\nRegistration cancelled")
            return False
        
        if not username or not password:
            print("Username and password cannot be empty")
            return False
        
        response = self.send_command('register', {
            'username': username,
            'password': password
        })
        
        if response and response['status'] == 'success':
            print(f"Registration successful! User ID: {response['userId']}")
            print("Please login to continue.")
            return True
        else:
            print(f"Registration failed: {response.get('message', 'Unknown error')}")
            return False
    
    def login(self):                    # player login
        print("\n=== Player Login ===")
        try:
            username = input("Username: ").strip()
            password = input("Password: ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\n\nLogin cancelled")
            return False
        
        if not username or not password:
            print("Username and password are required")
            return False
        
        response = self.send_command('login', {
            'username': username,
            'password': password
        })
        
        if response and response['status'] == 'success':
            self.user_id = response['userId']
            self.username = username
            player_dir = os.path.dirname(__file__)
            downloads_root = os.path.join(player_dir, 'downloads')
            self.downloads_dir = os.path.join(downloads_root, self.username)            # the directory for this player's downloads
            try:
                os.makedirs(self.downloads_dir, exist_ok=True)
                print(f"Downloads directory set to: {self.downloads_dir}")
            except Exception as e:
                print(f"Warning: failed to ensure downloads directory '{self.downloads_dir}': {e}")
            print(f"Login successful! Welcome, {username}")
            return True
        else:
            print(f"Login failed: {response.get('message', 'Unknown error')}")
            return False

    def logout(self):                   # player logout
        response = self.send_command('logout')
        if response and response['status'] == 'success':
            print("Logged out successfully")
            self.user_id = None
            self.username = None
            return True
        return False

    def browse_store(self):             # check what games are available in the store
        print("\n=== GAME STORE ===")
        response = self.send_command('browse_store')
        
        if not response or response['status'] != 'success':
            print(f"Failed to load store: {response.get('message', 'Unknown error')}")
            return []
        games = response.get('games', [])
        if not games:
            print("\nNo games available in store yet.")
            return []
        
        print(f"\nFound {len(games)} game(s) available:\n")
        
        for i, game in enumerate(games, 1):
            avg_rating = self.calculate_avg_rating(game.get('ratings', []))
            
            print(f"{i}. {game['name']} v{game['currentVersion']}")
            print(f"   Type: {game['gameType']} | Players: {game['maxPlayers']}")
            print(f"   Rating: {avg_rating:.1f}/5.0")
            print(f"   {game['description'][:60]}...")
            print()
        
        return games
    
    def calculate_avg_rating(self, ratings):
        if not ratings:
            return 0.0
        return sum(ratings) / len(ratings)
    
    def view_game_details(self):                        # view detailed information about a game
        print("\n=== View Game Details ===")
        
        games = self.browse_store()
        if not games:
            return
        
        try:
            choice = int(input("\nSelect game number (0 to cancel): ").strip())
            if choice == 0:
                return
            if choice < 1 or choice > len(games):
                print("Invalid selection")
                return
            
            game = games[choice - 1]
            
        except ValueError:
            print("Invalid input")
            return
        
        # display detailed game information
        print("\n" + "="*60)
        print(f"GAME: {game['name']}")
        print(f"Game ID: {game['id']}")
        print(f"Version: {game['currentVersion']}")
        print(f"Developer ID: {game['developerId']}")
        print(f"Type: {game['gameType']}")
        print(f"Max Players: {game['maxPlayers']}")
        print(f"Status: {game['status']}")
        print(f"Uploaded: {game.get('uploadedAt', 'N/A')}")
        print(f"Updated: {game.get('updatedAt', 'N/A')}")
        print(f"\nDescription:\n{game['description']}")
        
        # Ratings
        ratings = game.get('ratings', [])
        if ratings:
            avg_rating = self.calculate_avg_rating(ratings)
            print(f"\nRatings: {avg_rating:.1f}/5.0")
            print(f"Total ratings: {len(ratings)}")
        else:
            print("\nNo ratings yet")
        
        # Reviews
        reviews = game.get('reviews', [])
        if reviews:
            print(f"\nReviews ({len(reviews)}):")
            for i, review in enumerate(reviews[:3], 1):                     # show first 3 reviews
                print(f"  {i}. User {review.get('userId', 'Unknown')}: {review.get('text', '')}")
                print(f"     --review at {review.get('timestamp', 'N/A')}")
            if len(reviews) > 3:
                print(f"  ... and {len(reviews) - 3} more")
        else:
            print("\nNo reviews yet")
        input("\nPress Enter to continue...")
    
    def download_game(self):                            # download or update a game from the store
        print("\n=== Download/Update Game ===")
        
        games = self.browse_store()
        if not games:
            return
        
        try:
            choice = int(input("\nSelect game number to download (0 to cancel): ").strip())
            if choice == 0:
                return
            if choice < 1 or choice > len(games):
                print("Invalid selection")
                return
            
            game = games[choice - 1]
            
        except ValueError:
            print("Invalid input")
            return
        
        # check if game is active before downloading
        if game.get('status') != 'active':
            print(f"\nCannot download: {game['name']} is not active")
            print(f"   Status: {game.get('status', 'unknown')}")
            print(f"   This game has been removed from the store")
            return
        
        game_id = game['id']
        game_name = game['name']
        version = game['currentVersion']
        
        # check if already downloaded
        game_dir = os.path.join(self.downloads_dir, game_name)
        version_file = os.path.join(game_dir, 'version.txt')
        
        if os.path.exists(version_file):
            with open(version_file, 'r') as f:
                local_version = f.read().strip()
            
            if local_version == version:
                print(f"\nYou already have the latest version ({version})")
                update = input("Re-download anyway? (y/n): ").strip().lower()
                if update != 'y':
                    return
            else:
                print(f"\nUpdate available: {local_version} → {version}")
        else:
            print(f"\nDownloading {game_name} v{version}...")
        
        # Attempt download with retry mechanism
        max_retries = 3
        retry_count = 0
        
        while retry_count < max_retries:
            if retry_count > 0:
                print(f"\nRetry attempt {retry_count}/{max_retries-1}")

            response = self.send_command('download_game', {             # request game files
                'gameId': game_id,
                'version': version
            })
            
            if not response or response['status'] != 'ready':
                error_message = response.get('message', 'Unknown error') if response else 'Connection failed'
                print(f"Download failed: {error_message}")
                
                # Check if error is retryable
                if response and ('removed' in error_message.lower() or 'not available' in error_message.lower()):
                    print("   This error cannot be retried (game removed)")
                    return
                
                retry_count += 1
                if retry_count < max_retries:
                    retry = input(f"\nRetry download? (y/n, {max_retries - retry_count} attempts left): ").strip().lower()
                    if retry != 'y':
                        print("Download cancelled")
                        return
                    continue
                else:
                    print(f"\nMaximum retry attempts ({max_retries}) reached")
                    return
            
            file_count = response.get('fileCount', 0)
            print(f"\nReceiving {file_count} file(s)...")
            
            # Receive files
            download_success = True
            for i in range(file_count):
                file_info = recv_message(self.socket)
                if not file_info:
                    print("Failed to receive file info")
                    download_success = False
                    break
                
                file_name = file_info['name']
                file_path = os.path.join(game_dir, file_name)
                
                print(f"  [{i+1}/{file_count}] {file_name}", end='... ')
                
                if not recv_file(self.socket, file_path):
                    print("Failed")
                    download_success = False
                    break
                print("Done")
            
            if not download_success:
                retry_count += 1
                if retry_count < max_retries:
                    retry = input(f"\nRetry download? (y/n, {max_retries - retry_count} attempts left): ").strip().lower()
                    if retry != 'y':
                        print("Download cancelled")
                        return
                    # Reconnect to server before retry
                    print("Reconnecting to server...")
                    self.disconnect()
                    time.sleep(1)
                    if not self.connect():
                        print("Failed to reconnect. Please try again later.")
                        return
                    continue
                else:
                    print(f"\nMaximum retry attempts ({max_retries}) reached")
                    return
            
            with open(version_file, 'w') as f:          # save version info
                f.write(version)
            
            print(f"\nDownload complete! Game saved to: {game_dir}")
            return
    
    def check_and_update_game(self, game_name, required_version):       # check local game version and update if needed
        game_dir = os.path.join(self.downloads_dir, game_name)
        version_file = os.path.join(game_dir, 'version.txt')
        
        if not os.path.exists(game_dir):                # game not found locally    
            print(f"\nGame '{game_name}' not found locally. Downloading...")
            return self.download_game_by_name(game_name, required_version)
        
        current_version = "Unknown"                     # read local version    
        if os.path.exists(version_file):
            try:
                with open(version_file, 'r') as f:
                    current_version = f.read().strip()
            except Exception:
                pass
        
        # compare versions and make the update if needed
        if current_version != required_version:
            print(f"\nGame version mismatch!")
            print(f"   Current version: {current_version}")
            print(f"   Required version: {required_version}")
            print(f"   Updating game automatically...\n")
            
            # delete old version
            import shutil
            try:
                shutil.rmtree(game_dir)
                print(f"Removed old version")
            except Exception as e:
                print(f"Warning: Could not remove old version: {e}")
            
            # download new version
            return self.download_game_by_name(game_name, required_version)
        
        print(f"Game version is up to date (v{current_version})")
        return True
    
    def download_game_by_name(self, game_name, version):        # download a game by its name and version
        # query game info from database
        response = self.send_command('get_game_by_name', {'gameName': game_name})
        
        if not response or response['status'] != 'success':
            print(f"Failed to get game info: {response.get('message', 'Unknown error')}")
            return False
        
        game = response.get('game')
        if not game:
            print(f"Game '{game_name}' not found")
            return False
        
        # Download the game
        print(f"Downloading {game_name} v{version}...")
        return self.download_game_files(game['id'], game_name, version)     # helper function to download game files
    
    def download_game_files(self, game_id, game_name, version):
        import shutil
        import tempfile
        
        game_dir = os.path.join(self.downloads_dir, game_name)        
        temp_dir = tempfile.mkdtemp(prefix=f"download_{game_name}_")        # temporary directory for download
        
        try:
            response = self.send_command('download_game', {                 # request game files
                'gameId': game_id,
                'version': version
            })
            
            if not response:
                print(f"Network error: Failed to connect to server")
                return False
            
            if response['status'] not in ['success', 'ready']:
                error_message = response.get('message', 'Unknown error')
                if 'removed' in error_message.lower() or 'not available' in error_message.lower():
                    print(f"Game error: {error_message}")
                    print("   This game version has been removed or is no longer available")
                else:
                    print(f"Download failed: {error_message}")
                return False
            
            file_count = response.get('fileCount', 0)               # number of files to download
            if file_count == 0:
                print(f"No files to download")
                return False
            
            print(f"Downloading {file_count} files to temporary location...")
            
            downloaded_files = []                                   # track downloaded files for cleanup
            for i in range(file_count):
                try:
                    file_info = recv_message(self.socket)           # receive file metadata
                    if not file_info:
                        print(f"\nNetwork error: Connection lost while receiving file info ({i+1}/{file_count})")
                        print("   Download incomplete - cleaning up...")
                        return False
                    
                    file_name = file_info['name']
                    file_path = os.path.join(temp_dir, file_name)
                    os.makedirs(os.path.dirname(file_path), exist_ok=True)
                    
                    print(f"   [{i+1}/{file_count}] {file_name}...", end=' ', flush=True)
                    
                    if not recv_file(self.socket, file_path):
                        print(f"\nNetwork error: Failed to download {file_name}")
                        print("   Download incomplete - cleaning up...")
                        return False
                    
                    downloaded_files.append(file_name)
                    print("Done")
                    
                except Exception as e:
                    print(f"\nUnexpected error while downloading file {i+1}: {e}")
                    print("   Download incomplete - cleaning up...")
                    return False
            
            print(f"\nAll files downloaded successfully!")
            print(f"Installing to {game_dir}...")                   # move files to final location
            
            if os.path.exists(game_dir):                            # remove old version if exists
                try:
                    shutil.rmtree(game_dir)
                except Exception as e:
                    print(f"Warning: Could not remove old version: {e}")
            
            try:                                                    # move temp dir to final location
                shutil.move(temp_dir, game_dir)
            except Exception as e:
                print(f"Error: Failed to install game: {e}")
                return False
            
            version_file = os.path.join(game_dir, 'version.txt')    # save version info
            try:
                with open(version_file, 'w') as f:
                    f.write(version)
            except Exception as e:
                print(f"Warning: Could not save version info: {e}")
            
            print(f"Installation complete!")
            return True
            
        except KeyboardInterrupt:
            print(f"\n\nDownload cancelled by user")
            print("   Cleaning up incomplete download...")
            return False
            
        except Exception as e:
            print(f"\nUnexpected error during download: {e}")
            print("   Cleaning up incomplete download...")
            return False
            
        finally:
            if os.path.exists(temp_dir):
                try:
                    shutil.rmtree(temp_dir)
                except Exception as e:
                    print(f"Warning: Could not clean up temporary files: {e}")
    
    def list_downloaded_games(self):                # list downloaded games
        print("\n=== My Downloaded Games ===")
        if not os.path.exists(self.downloads_dir):
            print("No games downloaded yet")
            return []
        
        games = [d for d in os.listdir(self.downloads_dir)
                if os.path.isdir(os.path.join(self.downloads_dir, d))]
        
        if not games:
            print("No games downloaded yet")
            return []
        
        print(f"\nYou have {len(games)} game(s) downloaded:\n")
        
        for i, game_name in enumerate(games, 1):
            game_dir = os.path.join(self.downloads_dir, game_name)
            version_file = os.path.join(game_dir, 'version.txt')
            
            if os.path.exists(version_file):
                with open(version_file, 'r') as f:
                    version = f.read().strip()
            else:
                version = "Unknown"
            
            print(f"{i}. {game_name} (v{version})")
        
        return games
    
    def launch_game(self, game_name, host, port, user_id, room_id, spectator=False):    # launch a downloaded game
        game_dir = os.path.join(self.downloads_dir, game_name)                          # game directory

        if not os.path.exists(game_dir):
            print(f"Game not found: {game_name}")
            print(f"  Expected at: {game_dir}")
            return False
        
        config_file = os.path.join(game_dir, 'config.json')                             # game config file
        if not os.path.exists(config_file):
            print("Game config.json not found")
            print("  Game may be corrupted. Try re-downloading.")
            return False
        
        try:
            with open(config_file, 'r') as f:
                config = json.load(f)
        except Exception as e:
            print(f"Error reading config: {e}")
            return False
        
        main_file = config.get('mainFile', 'game.py')
        launch_cmd = f'python3 {main_file} {host} {port} {user_id} {room_id}'           # launch the client
        if spectator:
            launch_cmd += ' --spectator'
        
        game_type = config.get('gameType', 'GUI')                               # determine game type
        
        print(f"\nLaunching game...")
        print(f"   Command: {launch_cmd}")
        print(f"   Directory: {game_dir}")
        
        try:
            if game_type.upper() == 'CLI':                                      # CLI game
                # Use os.system for synchronous execution with terminal I/O
                self.game_in_progress = True                                    # set flag before starting
                time.sleep(0.1)
                print(f"Starting CLI game...\n")
                
                # change to game directory and run
                import os as os_module
                old_cwd = os_module.getcwd()
                os_module.chdir(game_dir)
                exit_code = os_module.system(launch_cmd)
                os_module.chdir(old_cwd)
                
                print(f"\nGame finished (exit code: {exit_code})")
                self.game_in_progress = False  # Clear flag after finishing
                return True
            else:                                                    # GUI game 
                process = subprocess.Popen(
                    launch_cmd,
                    shell=True,
                    cwd=game_dir
                )                
                time.sleep(0.5)
                poll_result = process.poll()
                
                if poll_result is not None:
                    print(f"Game process exited immediately (code: {poll_result})")
                    print(f"  Command: {launch_cmd}")
                    print(f"  Directory: {game_dir}")
                    return False
                
                print(f"Game launched (PID: {process.pid})")
                
                if not hasattr(self, 'game_processes'):             # store game processes
                    self.game_processes = []
                self.game_processes.append(process)
                
                return True
            
        except Exception as e:
            print(f"Failed to launch game: {e}")
            return False
    
    def rate_and_review_game(self):                                 # rate and review a downloaded game 
        import json as json_lib
        
        print("\n=== Rate & Review Game ===")        
        pending_file = os.path.join(self.downloads_dir, '.pending_review.json')
        pending_review = None
        
        if os.path.exists(pending_file):                            # check for pending review from last session    
            try:
                with open(pending_file, 'r') as f:
                    pending_review = json_lib.load(f)
                print("\nFound unsent review from previous session:")
                print(f"   Game: {pending_review.get('game_name')}")
                print(f"   Rating: {pending_review.get('rating')} stars")
                if pending_review.get('review'):
                    print(f"   Review: {pending_review.get('review')[:50]}...")
                
                retry = input("\nWould you like to retry sending this review? (y/n): ").strip().lower()
                if retry == 'y':
                    response = self.send_command('submit_review', {             # send review to server
                        'userId': self.user_id,
                        'gameId': pending_review.get('game_id'),
                        'rating': pending_review.get('rating'),
                        'review': pending_review.get('review')
                    })
                    
                    if response and response['status'] == 'success':
                        print(f"\nPreviously saved review submitted successfully!")
                        try:
                            os.remove(pending_file)
                        except:
                            pass
                        return
                    else:
                        print(f"\nStill failed to submit: {response.get('message', 'Unknown error')}")
                        print("   The review will remain saved for later retry")
                        return
                else:
                    try:
                        os.remove(pending_file)
                        print("   Pending review discarded")
                    except:
                        pass
            except Exception as e:
                print(f"Warning: Could not load pending review: {e}")
                try:
                    os.remove(pending_file)
                except:
                    pass
        
        games = self.browse_store()                                 # list available games
        if not games:
            return
        
        try:
            choice = int(input("\nSelect game number to review (0 to cancel): ").strip())
            if choice == 0:
                return
            if choice < 1 or choice > len(games):
                print("Invalid selection")
                return
            game = games[choice - 1]
        except ValueError:
            print("Invalid input")
            return
        
        print(f"\nReviewing: {game['name']}")
        
        # check if user has played this game before allowing rating/review
        check_response = self.send_command('check_play_history', {
            'userId': self.user_id,
            'gameId': game['id']
        })
        
        if not check_response or check_response.get('status') != 'success':
            print(f"\n✗ Failed to verify play history: {check_response.get('message', 'Unknown error')}")
            return
        
        if not check_response.get('hasPlayed', False):
            print(f"\n You must play \"{game['name']} v{game['currentVersion']}\" before rating or reviewing it")
            return
        
        rating = None
        while True:
            try:
                rating = int(input("Rating (int: 0-5): ").strip())
                if 0 <= rating <= 5:
                    break
                print("Rating must be integer between 0 and 5")
            except ValueError:
                print("Invalid input")
            except KeyboardInterrupt:
                print("\n\nReview cancelled")
                return
        try:
            review_text = input("Review (press Enter to skip): ").strip()
        except KeyboardInterrupt:
            print("\n\nReview cancelled")
            return
        
        review_data = {                           # prepare review data
            'userId': self.user_id,
            'gameId': game['id'],
            'rating': rating,
            'review': review_text if review_text else None
        }
        
        try:
            response = self.send_command('submit_review', review_data)      # send review to server
            if response and response['status'] == 'success':
                print(f"\nThank you for your review!")
                try:
                    if os.path.exists(pending_file):
                        os.remove(pending_file)
                except:
                    pass
            else:
                error_message = response.get('message', 'Unknown error') if response else 'Connection failed'
                print(f"\nFailed to submit review: {error_message}")

                try:
                    os.makedirs(self.downloads_dir, exist_ok=True)          # save review for later retry
                    saved_data = {
                        'game_id': game['id'],
                        'game_name': game['name'],
                        'rating': rating,
                        'review': review_text if review_text else None,
                        'timestamp': datetime.now().isoformat()
                    }
                    with open(pending_file, 'w') as f:
                        json_lib.dump(saved_data, f, indent=2)
                    print("\nYour review has been saved locally")
                    print("   You can retry submitting it later from this menu")
                    print(f"   Saved to: {pending_file}")
                except Exception as e:
                    print(f"\nWarning: Could not save review for retry: {e}")
                    print("   Please try submitting again later")
                
        except Exception as e:
            print(f"\nNetwork error: {e}")
            try:
                os.makedirs(self.downloads_dir, exist_ok=True)              # save review for later retry
                saved_data = {
                    'game_id': game['id'],
                    'game_name': game['name'],
                    'rating': rating,
                    'review': review_text if review_text else None,
                    'timestamp': datetime.now().isoformat()
                }
                with open(pending_file, 'w') as f:
                    json_lib.dump(saved_data, f, indent=2)
                print("\nYour review has been saved locally due to network error")
                print("   You can retry submitting it later from this menu")
            except Exception as save_err:
                print(f"\nWarning: Could not save review: {save_err}")
    
    def list_users(self):                   # list online players
        response = self.send_command('list_users')
        if response and response['status'] == 'success':
            print("\n=== Online Players ===")
            users = response.get('users', [])
            if not users:
                print("No players online")
            else:
                for user in users:
                    marker = " (You)" if user['id'] == self.user_id else ""
                    print(f"  • User ID: {user['id']} | Name: {user['name']}{marker}")
        else:
            print(f"Error: {response.get('message', 'Unknown error')}")
    
    def list_rooms(self):                   # list active rooms
        response = self.send_command('list_rooms')
        if response and response['status'] == 'success':
            print("\n=== Active Rooms ===")
            rooms = response.get('rooms', [])
            if not rooms:
                print("No active rooms")
            else:
                for room in rooms:
                    game_name = room.get('game_name', 'Unknown Game')
                    max_players = room.get('max_players', 2)
                    print(f"  • Room {room['id']}: {room['name']}")
                    print(f"    Game: {game_name}")
                    print(f"    Host: {room['host']} | Players: {room['members']}/{max_players}")
                    print(f"    Status: {room['status']} | Visibility: {room['visibility']}")
        else:
            print(f"Error: {response.get('message', 'Unknown error')}")
    
    def create_room_and_play(self):         # create a room and start a game
        print("\n=== Create Room & Play Game ===")
        games = self.list_downloaded_games()        # show the downloaded games of the player
        if not games:
            print("\nNo games downloaded!")
            print("   Go to 'Game store/Update Game' first")
            return
        # select a game to bind with the room
        try:
            game_choice = int(input("\nSelect game to play (0 to cancel): ").strip())
            if game_choice == 0:
                return
            if game_choice < 1 or game_choice > len(games):
                print("Invalid selection")
                return
            selected_game = games[game_choice - 1]
        except ValueError:
            print("Invalid input")
            return
        # ask host for room details
        room_name = input("\nRoom name (press Enter for default): ").strip()
        if not room_name:
            room_name = f"{self.username}'s {selected_game} Room"
        print("\nRoom visibility(default 1):")
        print("1. Public")
        print("2. Private")
        visibility_choice = input("Select (1-2): ").strip()
        visibility = 'private' if visibility_choice == '2' else 'public'

        response = self.send_command('create_room', {           # create room on server
            'room_name': room_name,
            'visibility': visibility,
            'game_name': selected_game
        })
        
        if response and response['status'] == 'success':
            self.current_room_id = response['roomId']
            self.is_host = True
            
            print(f"\n{'='*60}")
            print("  ROOM CREATED SUCCESSFULLY!")
            print(f"   Room ID: {self.current_room_id}")
            print(f"   Name: {room_name}")
            print(f"   Game: {selected_game}")
            print(f"   Visibility: {visibility}")
            print("="*60)
            print("\nYou are the HOST")
            print("Invite players or start game when ready")
        else:
            print(f"\nFailed to create room: {response.get('message', 'Unknown error')}")
    
    def join_room(self):                                        # join an existing room
        self.list_rooms()
        print("\n=== Join Room ===")
        try:
            room_id = int(input("Room ID: ").strip())
        except ValueError:
            print("Invalid room ID")
            return
        
        response = self.send_command('join_room', {'roomId': room_id})
        
        if response and response['status'] == 'success':
            self.current_room_id = room_id
            self.is_host = response.get('isHost', False)
            print(f"Joined room {room_id}!")
            
            if not self.is_host:                                # start notification thread if not host
                self.waiting_for_game = True
                self.notification_thread = threading.Thread(
                    target=self.check_game_start, daemon=True)
                self.notification_thread.start()
        else:
            print(f"Failed to join: {response.get('message', 'Unknown error')}")
    
    def leave_room(self):                                       # leave the current room  
        if not self.current_room_id:
            print("You are not in a room")
            return

        response = self.send_command('leave_room', {'roomId': self.current_room_id})

        if response and response['status'] == 'success':
            print(f"Left room {self.current_room_id}")
            self.current_room_id = None
            self.is_host = False
            self.waiting_for_game = False
        else:
            print(f"Failed to leave: {response.get('message', 'Unknown error')}")
    
    def invite_user(self):                                      # invite another player to the current room 
        if not self.is_host:
            print("Only host can invite players")
            return
        
        self.list_users()                                       # list online players
        
        try:
            user_id = int(input("\nUser ID to invite: ").strip())
            if user_id == self.user_id:
                print("You cannot invite yourself")
                return
        except ValueError:
            print("Invalid user ID")
            return
        
        response = self.send_command('invite_user', {
            'roomId': self.current_room_id,
            'targetUserId': user_id
        })
        
        if response and response['status'] == 'success':
            print(f"Invitation sent to user {user_id}")
        else:
            print(f"Failed: {response.get('message', 'Unknown error')}")
    
    def list_invitations(self):                                 # list pending room invitations 
        response = self.send_command('list_invitations')
        
        if response and response['status'] == 'success':
            print("\n=== Pending Invitations ===")
            invitations = response.get('invitations', [])
            if not invitations:
                print("No pending invitations")
            else:
                for inv in invitations:
                    game_name = inv.get('gameName', 'Unknown Game')
                    print(f"  • Room {inv['roomId']}: {inv['roomName']}")
                    print(f"    Host: {inv['host']} | Game: {game_name}")
        else:
            print(f"Error: {response.get('message', 'Unknown error')}")
    
    def accept_invitation(self):                                # accept a room invitation
        self.list_invitations()                                 # list pending invitations
        try:
            room_id = int(input("\nRoom ID to join: ").strip())
        except ValueError:
            print("Invalid room ID")
            return
        
        response = self.send_command('accept_invitation', {'roomId': room_id})
        
        if response and response['status'] == 'success':
            self.current_room_id = room_id
            self.is_host = False
            print(f"Joined room {room_id}!")
            
            self.waiting_for_game = True                        # after joining, start notification thread
            self.notification_thread = threading.Thread(
                target=self.check_game_start, daemon=True)
            self.notification_thread.start()
        else:
            print(f"Failed: {response.get('message', 'Unknown error')}")
    
    def start_game(self):                                      # host starts the game in the current room   
        if not self.is_host:
            print("Only host can start the game")
            return
        
        if not self.current_room_id:
            print("Not in a room")
            return
        
        response = self.send_command('start_game', {'roomId': self.current_room_id})
        
        if not response or response['status'] != 'success':
            print(f"Failed to start game: {response.get('message', 'Unknown error')}")
            return
        
        print("Game server starting...")
        
        game_name = response.get('gameName', 'Unknown Game')
        game_port = response['gameServerPort']
        game_version = response.get('gameVersion', 'Unknown')
        
        print(f"   Game: {game_name}")
        print(f"   Version: {game_version}")
        print(f"   Port: {game_port}")
        
        # check and update game version if needed
        print("\nChecking game version...")
        if not self.check_and_update_game(game_name, game_version):
            print("\nFailed to prepare game. Cannot start.")
            return        
        time.sleep(3.0)
        
        # check game type to determine post-launch behavior
        game_dir = os.path.join(self.downloads_dir, game_name)
        config_file = os.path.join(game_dir, 'config.json')
        game_type = 'GUI'  # Default type = GUI
        
        try:
            with open(config_file, 'r') as f:
                config = json.load(f)
                game_type = config.get('gameType', 'GUI')
        except Exception:
            pass
        
        success = self.launch_game(                             # auto-launch the game
            game_name=game_name,
            host=self.host,
            port=game_port,
            user_id=self.username,                              # use username instead of user_id
            room_id=self.current_room_id,
            spectator=False
        )
        
        if success:
            if game_type.upper() == 'CLI':                      # CLI game finished upon return
                print("\nReturning...")
            else:
                input("\nPress Enter when game is finished...")
                print("Returning to room...")
        else:
            print("\nFailed to launch game automatically")
            print("  You may need to launch it manually")
    
    def spectate_game(self):                                    # spectate an ongoing game not used
        self.list_rooms()
        
        print("\n=== Spectate Game ===")
        try:
            room_id = int(input("Room ID to spectate: ").strip())
        except ValueError:
            print("Invalid room ID")
            return
        
        response = self.send_command('spectate_game', {'roomId': room_id})
        
        if not response or response['status'] != 'success':
            print(f"Failed to spectate: {response.get('message', 'Unknown error')}")
            return
        
        game_name = response.get('gameName', 'Unknown Game')
        game_port = response['gameServerPort']
        
        print(f"Spectating: {game_name}")
        print(f"   Port: {game_port}")
        
        time.sleep(0.5)
        
        # auto-launch spectator mode
        success = self.launch_game(
            game_name=game_name,
            host=self.host,
            port=game_port,
            user_id=self.username,  # use username instead of user_id
            room_id=room_id,
            spectator=True
        )
        
        if success:
            print("\nSpectator mode launched")
            input("Press Enter when done spectating...")
        else:
            print("\nFailed to launch spectator")
    
    def check_game_start(self):                  # thread function to monitor game start in the current room 
        last_port = None
        
        while self.waiting_for_game and self.current_room_id and not self.is_host:
            try:
                response = self.send_command('check_room_status',           # check if game has started
                                            {'roomId': self.current_room_id})
                
                if response and response.get('status') == 'success':
                    if response.get('gameStarted'):                     # game has started
                        port = response.get('gameServerPort')
                        game_name = response.get('gameName', 'Unknown Game')
                        game_version = response.get('gameVersion', 'Unknown')
                        
                        if port and port != last_port:
                            last_port = port
                            
                            print(f"\n{'='*60}")
                            print("   HOST STARTED THE GAME!")
                            print(f"   Game: {game_name}")
                            print(f"   Version: {game_version}")
                            print(f"   Port: {port}")

                            print("\nChecking game version...")             # check and update game if needed
                            if not self.check_and_update_game(game_name, game_version):
                                print("\nFailed to prepare game. Cannot join.")
                                break
                            
                            time.sleep(2.0)
                            game_dir = os.path.join(self.downloads_dir, game_name)  # game directory
                            config_file = os.path.join(game_dir, 'config.json') 
                            game_type = 'GUI'
                            
                            try:
                                with open(config_file, 'r') as f:
                                    config = json.load(f)
                                    game_type = config.get('gameType', 'GUI')
                            except Exception:
                                pass

                            success = self.launch_game(                     # launch the game client
                                game_name=game_name,
                                host=self.host,
                                port=port,
                                user_id=self.username,                      # use username instead of user_id
                                room_id=self.current_room_id,
                                spectator=False
                            )
                            
                            if success:
                                if game_type.upper() == 'CLI':
                                    print("\n  Game finished!")
                                else:
                                    print("\n  Game launched successfully!")
                                self.game_just_ended = True
                            else:
                                print("\n  Failed to launch game")
                
                time.sleep(2)
                
            except Exception as e:
                print(f"Error checking game start: {e}")
                time.sleep(2)
    
    def run(self):                              # client main loop
        if not self.connect_lobby():            # connect to lobby server
            return
        
        self.running = True
        logged_in = False
        
        print("\n" + "="*60)
        print(" " * 15 + "GAME STORE SYSTEM")
        print("=" * 60)
        try:
            while self.running:
                if not logged_in:
                    print("\n" + "="*60)
                    print(" " * 15 + "GAME STORE SYSTEM")
                    print("=" * 60)
                    print("\n1. Register")
                    print("2. Login")
                    print("0. Exit")
                    
                    choice = input("\nEnter choice: ").strip()
                    
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
                    if not self.current_room_id:
                        self.main_menu()
                        choice = input("\nEnter choice: ").strip()
                        
                        if choice == '1':
                            self.game_store_menu()
                        elif choice == '2':
                            self.lobby_menu()
                        elif choice == '3':
                            if self.logout():
                                logged_in = False
                        elif choice == '4':
                            print("\nExit!")
                            self.running = False
                        else:
                            print("Invalid choice")
                    elif self.is_host:              # host menu when in a room
                        if self.game_in_progress:
                            time.sleep(0.2)
                            continue
                        
                        self.host_menu()
                        try:
                            choice = input("\nEnter choice: ").strip()
                        except (KeyboardInterrupt, EOFError):
                            print("\n\nExiting...")
                            self.running = False
                            break
                        
                        if choice == '1':
                            self.start_game()
                        elif choice == '2':
                            self.invite_user()
                        elif choice == '3':
                            self.leave_room()
                        else:
                            print("Invalid choice")
                    else:
                        if self.game_just_ended:
                            self.game_just_ended = False
                            continue                        
                        if self.game_in_progress:       # if game is in progress, skip menu
                            time.sleep(0.2)
                            continue
                        
                        self.member_menu()
                        try:
                            choice = input("\nEnter choice: ").strip()
                        except (KeyboardInterrupt, EOFError):
                            print("\n\nExiting...")
                            self.running = False
                            break
                        
                        if choice == '1':
                            self.waiting_for_game = False
                            self.leave_room()
                        elif choice == '':
                            continue
                        else:
                            print("Invalid choice")
        except KeyboardInterrupt:
            print("\nExit")
            self.running = False
        finally:
            if self.socket:
                try:
                    self.socket.close()
                except Exception:
                    pass

def main():
    import sys
    host = sys.argv[1] if len(sys.argv) > 1 else LOBBYSERVER_HOST
    port = int(sys.argv[2]) if len(sys.argv) > 2 else LOBBYSERVER_PORT
    player_name = sys.argv[3] if len(sys.argv) > 3 else "Player1"
    
    client = EnhancedLobbyClient(host, port, player_name)
    client.run()

if __name__ == '__main__':
    main()
#!/usr/bin/env python3
"""Developer Server for handling developer client requests."""
import socket
import threading
import json
import hashlib
import struct
import time
from datetime import datetime
from typing import Dict, List, Tuple, Optional, Set, Any
import os
import sys
DATABASE_SERVER_HOST = '140.113.17.11'
DATABASE_SERVER_PORT = 17047
LOBBYSERVER_HOST = '140.113.17.11'
LOBBYSERVER_PORT = 17048
DEVELOPER_SERVER_HOST = '140.113.17.11'
DEVELOPER_SERVER_PORT = 17049

sys.path.insert(0, os.path.dirname(__file__))

GAMES_STORAGE_PATH = os.path.join(os.path.dirname(__file__), 'uploaded_games') # uploaded games storage path
import re
def sanitize_name(name: str) -> str:            # sanitize game name for directory
    safe = re.sub(r'[^A-Za-z0-9 _\-]', '', name)
    safe = safe.strip().replace(' ', '_')
    if not safe:
        safe = 'unnamed_game'
    return safe

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

def send_file(sock: socket.socket, file_path: str) -> bool:         # send a file over socket with chunked transfer
    try:
        file_size = os.path.getsize(file_path)
        metadata = {                                    # send file metadata first
            'type': 'FILE_METADATA',
            'size': file_size,
            'name': os.path.basename(file_path)
        }
        send_message(sock, metadata)

        with open(file_path, 'rb') as f:                # send file data in chunks
            sent = 0
            while sent < file_size:
                chunk = f.read(8192)  # 8KB chunks
                if not chunk:
                    break
                sock.sendall(chunk)
                sent += len(chunk)
        return True
    except Exception as e:
        print(f"Error sending file: {e}")
        return False

def recv_file(sock: socket.socket, save_path: str) -> bool:         # receive a file over socket with chunked transfer
    try:
        metadata = recv_message(sock)
        if not metadata or metadata.get('type') != 'FILE_METADATA':
            return False
        
        file_size = metadata['size']
        received = 0
        
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
###### protocol part end ######

###### developer part start ######
class DeveloperServer:
    def __init__(self, host=DEVELOPER_SERVER_HOST, port=DEVELOPER_SERVER_PORT,
                 db_host=DATABASE_SERVER_HOST, db_port=DATABASE_SERVER_PORT):
        self.host = host
        self.port = port
        self.db_host = db_host
        self.db_port = db_port
        self.running = False
        self.lock = threading.Lock()
        
        # ensure games storage directory exists
        os.makedirs(GAMES_STORAGE_PATH, exist_ok=True)
        
    def start(self):
        self.running = True
        server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server_socket.bind((self.host, self.port))
        server_socket.listen(5)
        
        print(f"[DevServer] Developer Server started on {self.host}:{self.port}")
        
        while self.running:
            try:
                client_socket, address = server_socket.accept()
                thread = threading.Thread(target=self.handle_client, args=(client_socket,))
                thread.daemon = True
                thread.start()
            except Exception as error:
                if self.running:
                    print(f"[DevServer] Error accepting connection: {error}")
    
    def database_request(self, request):            # communicate with database server
        try:
            database_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            database_socket.connect((self.db_host, self.db_port))
            send_message(database_socket, request)
            response = recv_message(database_socket)
            database_socket.close()
            return response
        except Exception as error:
            print(f"[DevServer] DB request error: {error}")
            return {'status': 'error', 'message': str(error)}
    
    def handle_client(self, client_socket):         # handle individual developer client connection
        try:
            while True:
                request = recv_message(client_socket)
                if not request:
                    break
                command = request.get('command')

                if command == 'dev_register':
                    response = self.register_developer(request)
                elif command == 'dev_login':
                    response = self.login_developer(request)
                elif command == 'upload_game':
                    response = self.upload_game(client_socket, request)
                elif command == 'update_game':
                    response = self.update_game(client_socket, request)
                elif command == 'remove_game':
                    response = self.remove_game(request)
                elif command == 'list_my_games':
                    response = self.list_my_games(request)
                else:
                    response = {'status': 'error', 'message': f'Unknown command: {command}'}

                send_message(client_socket, response)           # send back the response

        except ProtocolError:
            pass
        except Exception as error:
            print(f"[DevServer] Error handling client: {error}")
        finally:
            client_socket.close()
    
    def register_developer(self, request):          # developer registration
        response = self.database_request({
            'collection': 'Developer',
            'action': 'create',
            'data': {
                'name': request['username'],
                'password': request['password']
            }
        })
        
        if response['status'] == 'success':
            return {'status': 'success', 'message': 'Developer registration successful', 
                    'devId': response.get('userId')}
        return response
    
    def login_developer(self, request):             # developer login
        response = self.database_request({
            'collection': 'Developer',
            'action': 'query',
            'data': {'name': request['username']}
        })

        if response['status'] != 'success' or not response['data']:
            return {'status': 'error', 'message': 'Developer account not found'}

        dev = response['data'][0]
        password_hash = hashlib.sha256(request['password'].encode()).hexdigest()
        
        if dev['password_hashed'] != password_hash:
            return {'status': 'error', 'message': 'Invalid password'}
        
        return {'status': 'success', 'message': 'Login successful', 'devId': dev['id']}
    
    def upload_game(self, client_socket, request):  # handle game upload from developer
        try:
            dev_id = request.get('devId')
            game_info = request.get('gameInfo')
            
            if not dev_id or not game_info:
                return {'status': 'error', 'message': 'Missing required fields'}
            # validate all required config fields            
            required_fields = ['name', 'description', 'gameType', 'maxPlayers', 'version', 'mainFile', 'serverFile']
            for field in required_fields:
                if field not in game_info:
                    return {'status': 'error', 'message': f'Missing required field in config.json: {field}'}
            # check if this version already exists            
            existing_games = self.database_request({
                'collection': 'Game',
                'action': 'query',
                'data': {'developerId': dev_id, 'name': game_info['name']}
            })
            
            if existing_games.get('status') == 'success':
                for existing in existing_games.get('data', []):
                    if existing.get('currentVersion') == game_info['version']:
                        return {'status': 'error', 'message': f"Version {game_info['version']} already exists for game '{game_info['name']}'"}

            # create game entry in database
            game_data = {
                'name': game_info['name'],
                'developerId': dev_id,
                'description': game_info['description'],
                'gameType': game_info['gameType'],
                'maxPlayers': game_info['maxPlayers'],
                'currentVersion': game_info['version'],
                'mainFile': game_info['mainFile'],              # client main file
                'serverFile': game_info['serverFile'],          # server main file
                'uploadedAt': datetime.now().isoformat(),
                'updatedAt': datetime.now().isoformat(),
                'status': 'active',
                'ratings': [],
                'reviews': []
            }
            
            database_response = self.database_request({
                'collection': 'Game',
                'action': 'create',
                'data': game_data
            })
            
            if database_response['status'] != 'success':
                return database_response
            
            game_id = database_response['gameId']

            # prepare directory for game files using the game name
            game_name_safe = sanitize_name(game_info['name'])
            game_dir = os.path.join(GAMES_STORAGE_PATH, game_name_safe, game_info['version'])
            os.makedirs(game_dir, exist_ok=True)
            
            # send ready signal to client to start file transfer
            send_message(client_socket, {'status': 'ready', 'message': 'Ready to receive files'})
            
            file_count = request.get('fileCount', 0)                        # receive game files
            for i in range(file_count):
                file_info = recv_message(client_socket)
                if not file_info:
                    return {'status': 'error', 'message': 'Failed to receive file info'}
                
                file_name = file_info['name']
                file_path = os.path.join(game_dir, file_name)
                os.makedirs(os.path.dirname(file_path), exist_ok=True)      # ensure directory exists
                
                if not recv_file(client_socket, file_path):
                    return {'status': 'error', 'message': f'Failed to receive file: {file_name}'}
            
            print(f"[DevServer] Game {game_id} uploaded successfully")
            return {
                'status': 'success',
                'message': 'Game uploaded successfully',
                'gameId': game_id
            }
            
        except Exception as e:
            print(f"[DevServer] Error uploading game: {e}")
            return {'status': 'error', 'message': str(e)}
    
    def update_game(self, client_socket, request):              # handle game update from developer
        try:
            dev_id = request.get('devId')
            game_id = request.get('gameId')
            game_info = request.get('gameInfo')
            
            if not all([dev_id, game_id, game_info]):           # check required fields
                return {'status': 'error', 'message': 'Missing required fields'}
            
            new_version = game_info.get('version')              # check new version
            if not new_version:
                return {'status': 'error', 'message': 'Missing version in config.json'}

            required_fields = ['name', 'description', 'gameType', 'maxPlayers', 'version', 'mainFile', 'serverFile']
            for field in required_fields:
                if field not in game_info:
                    return {'status': 'error', 'message': f'Missing required field in config.json: {field}'}

            game_response = self.database_request({             # retrieve existing game info
                'collection': 'Game',
                'action': 'read',
                'data': {'id': game_id}
            })
            
            if game_response['status'] != 'success':
                return {'status': 'error', 'message': 'Game not found'}
            
            game = game_response['data']
            if game['developerId'] != dev_id:                   # verify ownership
                return {'status': 'error', 'message': 'Permission denied: not your game'}
            
            old_version = game.get('currentVersion')            
            game_name_safe = sanitize_name(game.get('name', 'unnamed_game'))            # prepare directory for new version
            version_dir = os.path.join(GAMES_STORAGE_PATH, game_name_safe, new_version)
            if os.path.exists(version_dir):
                return {'status': 'error', 'message': f"Version {new_version} already exists for this game"}
            
            if old_version:                                     # delete old version files
                old_version_dir = os.path.join(GAMES_STORAGE_PATH, game_name_safe, old_version)
                if os.path.exists(old_version_dir):
                    import shutil
                    try:
                        shutil.rmtree(old_version_dir)
                        print(f"[DevServer] Deleted old version {old_version} from {old_version_dir}")
                    except Exception as e:
                        print(f"[DevServer] Warning: Failed to delete old version: {e}")
            
            game_dir = version_dir                              # create new version directory
            os.makedirs(game_dir, exist_ok=True)
            
            self.database_request({                             # update database
                'collection': 'Game',
                'action': 'update',
                'data': {
                    'id': game_id,
                    'fields': {
                        'currentVersion': new_version,
                        'mainFile': game_info['mainFile'],
                        'serverFile': game_info['serverFile'],
                        'updatedAt': datetime.now().isoformat()
                    }
                }
            })

            send_message(client_socket, {'status': 'ready', 'message': 'Ready to receive files'})
            
            file_count = request.get('fileCount', 0)            # receive updated game files
            for i in range(file_count):
                file_info = recv_message(client_socket)
                if not file_info:
                    return {'status': 'error', 'message': 'Failed to receive file info'}
                
                file_name = file_info['name']
                file_path = os.path.join(game_dir, file_name)
                os.makedirs(os.path.dirname(file_path), exist_ok=True)
                
                if not recv_file(client_socket, file_path):     # not receive file
                    return {'status': 'error', 'message': f'Failed to receive file: {file_name}'}
            
            print(f"[DevServer] Game {game_id} updated to version {new_version}")
            return {'status': 'success', 'message': 'Game updated successfully'}
            
        except Exception as e:
            print(f"[DevServer] Error updating game: {e}")
            return {'status': 'error', 'message': str(e)}
    
    def remove_game(self, request):                             # developer removes a game
        try:
            dev_id = request.get('devId')
            game_id = request.get('gameId')
            
            if not dev_id or not game_id:
                return {'status': 'error', 'message': 'Missing devId or gameId'}
            
            game_response = self.database_request({             # retrieve game info
                'collection': 'Game',
                'action': 'read',
                'data': {'id': game_id}
            })
            
            if game_response['status'] != 'success':
                return {'status': 'error', 'message': 'Game not found'}
            
            game = game_response['data']
            
            if game['developerId'] != dev_id:                   # verify ownership
                print(f"[DevServer] Permission denied: Developer {dev_id} attempted to remove game {game_id} owned by {game['developerId']}")
                return {'status': 'error', 'message': 'Permission denied: You are not the developer of this game'}
            
            self.database_request({                             # mark game as inactive in database
                'collection': 'Game',
                'action': 'update',
                'data': {
                    'id': game_id,
                    'fields': {'status': 'inactive'}
                }
            })
            # delete game files from server storage
            game_name_safe = sanitize_name(game.get('name', 'unnamed_game'))
            game_base_dir = os.path.join(GAMES_STORAGE_PATH, game_name_safe)
            
            if os.path.exists(game_base_dir):
                import shutil
                try:
                    shutil.rmtree(game_base_dir)
                    print(f"[DevServer] Deleted game files: {game_base_dir}")
                except Exception as e:
                    print(f"[DevServer] Warning: Failed to delete game files at {game_base_dir}: {e}")
            
            print(f"[DevServer] Game {game_id} ({game.get('name')}) removed by developer {dev_id}")
            return {'status': 'success', 'message': 'Game removed successfully and files deleted'}
            
        except Exception as e:
            print(f"[DevServer] Error in remove_game: {e}")
            return {'status': 'error', 'message': str(e)}
    
    def list_my_games(self, request):                           # list all games by this developer
        try:
            dev_id = request.get('devId')
            games_response = self.database_request({
                'collection': 'Game',
                'action': 'query',
                'data': {'developerId': dev_id}
            })
            
            if games_response['status'] != 'success':
                return games_response
            
            # calculate average rating for each game
            games = games_response['data']
            for game in games:
                ratings = game.get('ratings', [])
                if ratings and len(ratings) > 0:
                    avg = sum(ratings) / len(ratings)
                    game['averageRating'] = round(avg, 2)
                else:
                    game['averageRating'] = None
            
            return {
                'status': 'success',
                'games': games
            }
            
        except Exception as e:
            return {'status': 'error', 'message': str(e)}
###### developer part end ######

def main():
    dev = DeveloperServer(db_host=DATABASE_SERVER_HOST, db_port=DATABASE_SERVER_PORT)
    t = threading.Thread(target=dev.start, daemon=True)
    t.start()
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        try:
            dev.cleanup()
        except Exception:
            pass
        dev.running = False


if __name__ == '__main__':
    main()

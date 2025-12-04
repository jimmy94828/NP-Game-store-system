#!/usr/bin/env python3
import socket
import threading
import json
import hashlib
import random
import struct
import time
from datetime import datetime
from typing import Dict, List, Tuple, Optional, Set, Any
import os
GAMES_STORAGE_PATH = os.path.join(os.path.dirname(__file__), 'uploaded_games')

DATABASE_SERVER_HOST = '140.113.17.11'
DATABASE_SERVER_PORT = 17047
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

def send_file(sock: socket.socket, file_path: str) -> bool:     # send a file over socket with chunked transfer
    try:
        file_size = os.path.getsize(file_path)
        metadata = {                                            # send file metadata first
            'type': 'FILE_METADATA',
            'size': file_size,
            'name': os.path.basename(file_path)
        }
        send_message(sock, metadata)
        
        # send file in chunks
        with open(file_path, 'rb') as f:
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

def recv_file(sock: socket.socket, save_path: str) -> bool:     # receive a file over socket with chunked transfer
    try:
        metadata = recv_message(sock)                           # receive file metadata first   
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

class DatabaseServer:
    def __init__(self, host = DATABASE_SERVER_HOST, port = DATABASE_SERVER_PORT, database_file = 'database.json'):
        self.host = host
        self.port = port
        self.database_file = database_file
        self.running = False
        self.lock = threading.Lock()            # protect shared data
        self.load_database()
    
    def start(self):                            # start the database server
        self.running = True
        server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)       # TCP socket
        server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server_socket.bind((self.host, self.port))
        server_socket.listen(5)
        
        print(f"[DB] Database Server started on {self.host}:{self.port}")
        
        while self.running:
            try:
                client_socket, address = server_socket.accept()                 # handling client connection
                thread = threading.Thread(target=self.handle_request, args=(client_socket,))
                thread.daemon = True
                thread.start()
            except Exception as error:
                if self.running:
                    print(f"[DB] Error accepting connection: {error}")

    def load_database(self):                    # load the database file
        try:
            with open(self.database_file, 'r', encoding='utf-8') as f:
                self.data = json.load(f)
                if self.data['counters']['Room'] != 1:       ##/
                    self.data['counters']['Room'] = 1
                if 'Developer' not in self.data.get('counters', {}):
                    self.data['counters']['Developer'] = 1
                if 'Game' not in self.data.get('counters', {}):
                    self.data['counters']['Game'] = 1
        except FileNotFoundError:               # if the file does not exist, create a new one
            self.data = {                       # user data
                'User': {},
                'Room': {},
                'GameLog': {},
                'Developer': {},
                'Game': {},
                'counters': {
                    'User': 1,
                    'Room': 1,
                    'GameLog': 1,
                    'Developer': 1,
                    'Game': 1
                }
            }
            self.save_database()
        print(f"[DB] Database: {self.database_file}")
    
    def save_database(self):                     # save the database file
        try:
            with open(self.database_file, 'w') as f:
                json.dump(self.data, f, indent=2)
        except Exception as error:
            print(f"Error saving database: {error}")
            return {"status": "ERROR", "message": "Failed to save database."}
                    
    def handle_request(self, client_socket):      # handle client requests
        try:
            while True:
                request = recv_message(client_socket)           # receive client request
                #print(f"[DB] Received request: {request}")
                if not request:                                 # connection closed
                    break
                try:
                    collection = request.get('collection')
                    action = request.get('action')
                    data = request.get('data', {})
                    
                    if collection == 'User':
                        response = self.handle_user(action, data)
                    elif collection == 'Room':
                        response = self.handle_room(action, data)
                    elif collection == 'GameLog':
                        response = self.handle_gamelog(action, data)
                    elif collection == 'Developer':
                        response = self.handle_developer(action, data)
                    elif collection == 'Game':
                        response = self.handle_game(action, data)
                    else:
                        response = {'status': 'error', 'message': f'Unknown collection: {collection}'}
                except Exception as error:
                    response = {'status': 'error', 'message': str(error)}
                #print(f"[DB] Sending response: {response}")
                send_message(client_socket, response)
        except ProtocolError:
            pass
        except Exception as error:
            print(f"[DB] Error handling client: {error}")
        finally:
            client_socket.close()                       # close the client connection when done

    def handle_developer(self, action, data):           # handle Developer collection operations
        with self.lock:
            try:
                if action == 'create':                  # Developer registration
                    for dev in self.data.get('Developer', {}).values():
                        if dev['name'] == data['name']:
                            return {'status': 'error', 'message': 'Developer name already exists'}

                    dev_id = self.data['counters'].get('Developer', 1)
                    self.data['counters']['Developer'] = dev_id + 1
                    
                    import hashlib
                    password = hashlib.sha256(data['password'].encode()).hexdigest()        # hash the password using sha 256
                    
                    new_dev = {
                        'id': dev_id,
                        'name': data['name'],
                        'password_hashed': password,
                        'createdAt': datetime.now().isoformat()
                    }
                    
                    if 'Developer' not in self.data:
                        self.data['Developer'] = {}
                    
                    self.data['Developer'][str(dev_id)] = new_dev
                    self.save_database()
                    return {'status': 'success', 'userId': dev_id}
                
                elif action == 'read':
                    dev_id = str(data['id'])
                    if 'Developer' in self.data and dev_id in self.data['Developer']:
                        return {'status': 'success', 'data': self.data['Developer'][dev_id]}
                    return {'status': 'error', 'message': 'Developer not found'}
                
                elif action == 'query':
                    results = []
                    for dev in self.data.get('Developer', {}).values():
                        match = True
                        if 'id' in data and dev['id'] != data['id']:
                            match = False
                        if 'name' in data and dev['name'] != data['name']:
                            match = False
                        if match:
                            results.append(dev)
                    return {'status': 'success', 'data': results}
                
                elif action == 'update':
                    dev_id = str(data['id'])
                    if 'Developer' not in self.data or dev_id not in self.data['Developer']:
                        return {'status': 'error', 'message': 'Developer not found'}
                    
                    for key, value in data['fields'].items():
                        self.data['Developer'][dev_id][key] = value
                    
                    self.save_database()
                    return {'status': 'success'}
                
            except Exception as error:
                return {'status': 'error', 'message': str(error)}
        
        return {'status': 'error', 'message': f'Unknown action: {action}'}
    
    def handle_game(self, action, data):                # handle Game collection operations
        with self.lock:
            try:
                if action == 'create':                  # upload new game
                    game_id = self.data['counters'].get('Game', 1)
                    self.data['counters']['Game'] = game_id + 1
                    
                    new_game = {
                        'id': game_id,
                        'name': data['name'],
                        'developerId': data['developerId'],
                        'description': data['description'],
                        'gameType': data['gameType'],
                        'maxPlayers': data['maxPlayers'],
                        'currentVersion': data['currentVersion'],
                        'mainFile': data.get('mainFile', ''),
                        'serverFile': data.get('serverFile', ''),
                        'uploadedAt': data['uploadedAt'],
                        'updatedAt': data.get('uploadedAt'),
                        'status': 'active',
                        'ratings': [],
                        'reviews': []
                    }
                    if 'Game' not in self.data:
                        self.data['Game'] = {}
                    
                    self.data['Game'][str(game_id)] = new_game
                    self.save_database()
                    return {'status': 'success', 'gameId': game_id}
                
                elif action == 'read':
                    game_id = str(data['id'])
                    if 'Game' in self.data and game_id in self.data['Game']:
                        return {'status': 'success', 'data': self.data['Game'][game_id]}
                    return {'status': 'error', 'message': 'Game not found'}
                
                elif action == 'query':
                    results = []
                    for game in self.data.get('Game', {}).values():
                        match = True
                        if 'status' in data and game['status'] != data['status']:
                            match = False
                        elif 'status' not in data and 'browsing' in data and game['status'] != 'active':
                            match = False
                        
                        if 'developerId' in data and game['developerId'] != data['developerId']:
                            match = False
                        if 'id' in data and game['id'] != data['id']:
                            match = False
                        if 'name' in data and game['name'] != data['name']:
                            match = False
                        
                        if match:
                            results.append(game)
                    return {'status': 'success', 'data': results}
                
                elif action == 'update':
                    game_id = str(data['id'])
                    if 'Game' not in self.data or game_id not in self.data['Game']:
                        return {'status': 'error', 'message': 'Game not found'}
                    
                    for key, value in data['fields'].items():
                        self.data['Game'][game_id][key] = value
                    
                    self.save_database()
                    return {'status': 'success'}
                
                elif action == 'add_rating':
                    game_id = str(data['gameId'])
                    if 'Game' not in self.data or game_id not in self.data['Game']:
                        return {'status': 'error', 'message': 'Game not found'}
                    
                    self.data['Game'][game_id]['ratings'].append(data['rating'])

                    if data.get('review'):
                        review = {
                            'userId': data['userId'],
                            'text': data['review'],
                            'timestamp': datetime.now().isoformat()
                        }
                        self.data['Game'][game_id]['reviews'].append(review)

                    self.save_database()
                    return {'status': 'success'}

                elif action == 'delete':
                    game_id = str(data['id'])
                    if 'Game' in self.data and game_id in self.data['Game']:
                        del self.data['Game'][game_id]
                        self.save_database()
                        return {'status': 'success'}
                    return {'status': 'error', 'message': 'Game not found'}
                
            except Exception as error:
                return {'status': 'error', 'message': str(error)}
        
        return {'status': 'error', 'message': f'Unknown action: {action}'}
        
    def handle_user(self, action, data):            # create read update delete, user operations
        with self.lock:
            try:
                if action == 'create':              # user registration
                    for user in self.data['User'].values():
                        if user['name'] == data['name']:
                            return {'status': 'error', 'message': 'Username already exists'}

                    user_id = self.data['counters']['User']                             # create a new user and give it a unique ID
                    self.data['counters']['User'] += 1
                    password = hashlib.sha256(data['password'].encode()).hexdigest()    # hash the password using sha 256
                    new_user = {
                        'id': user_id,
                        'name': data['name'],
                        'password_hashed': password,
                        'createdAt': datetime.now().isoformat(),
                        'lastLoginAt': None,
                        'online': 0
                    }
                    
                    self.data['User'][str(user_id)] = new_user
                    #print(f"[DB] Created user: {new_user}")
                    self.save_database()
                    return {'status': 'success', 'userId': user_id}
                    
                elif action == 'read':              # read user information
                    user_id = str(data['id'])
                    if user_id in self.data['User']:
                        return {'status': 'success', 'data': self.data['User'][user_id]}
                    return {'status': 'error', 'message': 'User not found'}
                    
                elif action == 'update':            # update user information
                    user_id = str(data['id'])
                    if user_id not in self.data['User']:
                        return {'status': 'error', 'message': 'User not found'}
                    
                    for key, value in data['fields'].items():
                        self.data['User'][user_id][key] = value
                    
                    self.save_database()
                    return {'status': 'success'}
                    
                elif action == 'delete':            # delete user
                    user_id = str(data['id'])
                    if user_id in self.data['User']:
                        del self.data['User'][user_id]
                        self.save_database()
                        return {'status': 'success'}
                    return {'status': 'error', 'message': 'User not found'}
                    
                elif action == 'query':             # query users based on criteria
                    results = []
                    for user in self.data['User'].values():
                        match = True
                        if 'id' in data and user['id'] != data['id']:
                            match = False
                        if 'name' in data and user['name'] != data['name']:
                            match = False
                        if 'online' in data and user['online'] != data['online']:
                            match = False
                        
                        if match:
                            results.append(user)
                    
                    return {'status': 'success', 'data': results}
                    
            except Exception as error:
                return {'status': 'error', 'message': str(error)}
                
        return {'status': 'error', 'message': f'Unknown action: {action}'}

    def handle_room(self, action, data):            # create read update delete, room operations
        with self.lock:
            try:
                if action == 'create':              # create a new room and give it a unique ID 
                    room_id = self.data['counters']['Room']
                    self.data['counters']['Room'] += 1
                    
                    new_room = {
                        'id': room_id,
                        'name': data['name'],
                        'host_user_id': data['host_user_id'],
                        'visibility': data['visibility'],
                        'invitelist': data.get('invitelist', []),
                        'game_name': data.get('game_name'),  # Store game name
                        'game_id': data.get('game_id'),      # Store game ID
                        'status': 'idle',
                        'createdAt': datetime.now().isoformat(),
                        'gameServerPort': None
                    }
                    
                    self.data['Room'][str(room_id)] = new_room
                    self.save_database()
                    return {'status': 'success', 'roomId': room_id}
                    
                elif action == 'read':              # read room information
                    room_id = str(data['id'])
                    if room_id in self.data['Room']:
                        return {'status': 'success', 'data': self.data['Room'][room_id]}
                    return {'status': 'error', 'message': 'Room not found'}
                    
                elif action == 'update':            # update room information
                    room_id = str(data['id'])
                    if room_id not in self.data['Room']:
                        return {'status': 'error', 'message': 'Room not found'}
                    
                    for key, value in data['fields'].items():
                        self.data['Room'][room_id][key] = value
                    
                    self.save_database()
                    return {'status': 'success'}
                    
                elif action == 'delete':            # delete room
                    room_id = str(data['id'])
                    if room_id in self.data['Room']:
                        del self.data['Room'][room_id]
                        self.save_database()
                        return {'status': 'success'}
                    return {'status': 'error', 'message': 'Room not found'}
                    
                elif action == 'query':
                    results = []
                    for room in self.data['Room'].values():
                        match = True
                        if 'visibility' in data and room['visibility'] != data['visibility']:
                            match = False
                        if 'status' in data and room['status'] != data['status']:
                            match = False
                        
                        if match:
                            results.append(room)
                    
                    return {'status': 'success', 'data': results}
                    
            except Exception as error:
                return {'status': 'error', 'message': str(error)}
                
        return {'status': 'error', 'message': f'Unknown action: {action}'}

    def handle_gamelog(self, action, data):                 # handle gamelog information
        with self.lock:
            try:
                if action == 'create':                      # create a new gamelog and give it a unique ID    
                    log_id = self.data['counters']['GameLog']
                    self.data['counters']['GameLog'] += 1
                    
                    new_log = {
                        'id': log_id,
                        'matchId': data['matchId'],
                        'roomId': data['roomId'],
                        'game_id': data.get('game_id'),
                        'game_name': data.get('game_name'),
                        'game_version': data.get('game_version'),
                        'users': data['users'],
                        'startAt': data['startAt'],
                        'endAt': data.get('endAt'),
                        'results': data.get('results', [])
                    }
                    
                    self.data['GameLog'][str(log_id)] = new_log
                    self.save_database()
                    return {'status': 'success', 'logId': log_id}
                    
                elif action == 'read':                      # read gamelog information
                    log_id = str(data['id'])
                    if log_id in self.data['GameLog']:
                        return {'status': 'success', 'data': self.data['GameLog'][log_id]}
                    return {'status': 'error', 'message': 'GameLog not found'}
                    
                elif action == 'update':                    # update gamelog information
                    log_id = str(data['id'])
                    if log_id not in self.data['GameLog']:
                        return {'status': 'error', 'message': 'GameLog not found'}
                    
                    for key, value in data['fields'].items():
                        self.data['GameLog'][log_id][key] = value
                    
                    self.save_database()
                    return {'status': 'success'}
                    
                elif action == 'query':                     # query gamelogs based on criteria
                    results = []
                    for log in self.data['GameLog'].values():
                        match = True
                        if 'roomId' in data and log['roomId'] != data['roomId']:
                            match = False
                        
                        if match:
                            results.append(log)
                    
                    return {'status': 'success', 'data': results}
                    
            except Exception as error:
                return {'status': 'error', 'message': str(error)}
                
        return {'status': 'error', 'message': f'Unknown action: {action}'}
    
    def cleanup(self):                                      # log out all users when server shuts down
        print("[Database] Log out all users...")
        with self.lock:
            for user in self.data['User'].values():
                if user['online'] == 1:
                    user['online'] = 0
            self.save_database()
        
        print("[Database] Cleanup completed")


def main():
    db = DatabaseServer()
    t = threading.Thread(target=db.start, daemon=True)
    t.start()
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        db.cleanup()
        db.running = False


if __name__ == '__main__':
    main()

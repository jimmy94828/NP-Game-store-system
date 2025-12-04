#!/usr/bin/env python3
"""Wrapper to run LobbyServer from servers.py"""
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
import sys

sys.path.insert(0, os.path.dirname(__file__))
LOBBYSERVER_HOST = '140.113.17.11'
LOBBYSERVER_PORT = 17048
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

def send_file(sock: socket.socket, file_path: str) -> bool:         # send file over socket with chunked transfer
    try:
        file_size = os.path.getsize(file_path)
        # Send file metadata first
        metadata = {
            'type': 'FILE_METADATA',
            'size': file_size,
            'name': os.path.basename(file_path)
        }
        send_message(sock, metadata)
        
        # Send file in chunks
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

def recv_file(sock: socket.socket, save_path: str) -> bool:             # receive file over socket with chunked transfer
    try:
        metadata = recv_message(sock)                                   # receive file metadata first
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


###### lobby part start ######
class LobbyServer:
    def __init__(self, host = LOBBYSERVER_HOST, port = LOBBYSERVER_PORT, database_host = DATABASE_SERVER_HOST, database_port = DATABASE_SERVER_PORT):
        self.host = host
        self.port = port
        self.database_host = database_host
        self.database_port = database_port
        self.running = False
        self.lock = threading.Lock()
        self.online_users = {}               # user_id -> client_socket
        self.user_sessions = {}              # client_socket -> user_id
        self.user_names = {}                 # user_id -> username
        self.rooms = {}                      # room_id -> room_info
        self.room_members = {}               # room_id -> set(user_id)
        self.invitations = {}                # user_id -> list(invitation)
        self.game_servers = {}
        self.used_ports = set()

    def start(self):                #start the lobby server
        self.running = True
        server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)       # TCP socket
        server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server_socket.bind((self.host, self.port))
        server_socket.listen(5)
        
        print(f"[Lobby] Lobby Server started on {self.host}:{self.port}")
        
        while self.running:
            try:
                client_socket, address = server_socket.accept()                 # handling client connection
                thread = threading.Thread(target=self.handle_request, args=(client_socket,))
                thread.daemon = True
                thread.start()
            except Exception as error:
                if self.running:
                    print(f"[Lobby] Error accepting connection: {error}")

    def handle_request(self, client_socket):        # handle client requests 
        try:
            while True:
                request = recv_message(client_socket)
                if not request:
                    break
                command = request.get('command')
                try:
                    if command == 'register':
                        response = self.register_user(request)
                    elif command == 'login':
                        response = self.login_user(client_socket, request)
                    elif command == 'logout':
                        response = self.logout_user(client_socket)
                    elif command == 'list_users':
                        response = self.list_online_users()
                    elif command == 'list_rooms':
                        response = self.list_rooms()
                    elif command == 'create_room':
                        response = self.create_room(client_socket, request)
                    elif command == 'join_room':
                        response = self.join_room(client_socket, request)
                    elif command == 'leave_room':
                        response = self.leave_room(client_socket, request)
                    elif command == 'invite_user':
                        response = self.invite_user(client_socket, request)
                    elif command == 'list_invitations':
                        response = self.list_invitations(client_socket)
                    elif command == 'accept_invitation':
                        response = self.accept_invitation(client_socket, request)
                    elif command == 'start_game':
                        response = self.start_game(client_socket, request)
                    #elif command == 'spectate_game':
                    #    response = self.spectate_game(client_socket, request)
                    elif command == 'game_ended':
                        response = self.game_ended(request)
                    elif command == 'check_room_status':
                        response = self.check_room_status(request)
                    elif command == 'browse_store':
                        response = self.browse_store()
                    elif command == 'get_game_by_name':
                        response = self.get_game_by_name(request)
                    elif command == 'download_game':
                        response = self.download_game(client_socket, request)
                        if response is None:  # Already sent
                            continue
                    elif command == 'submit_review':
                        response = self.submit_review(request)
                    elif command == 'check_play_history':
                        response = self.check_play_history(request)
                    else:
                        response = {'status': 'error', 'message': f'Unknown command: {command}'}
                except Exception as error:
                    response = {'status': 'error', 'message': str(error)}
                send_message(client_socket, response)
        except ProtocolError:
            pass
        except Exception as error:
            print(f"[Lobby] Error handling client: {error}")
        finally:
            self.handle_disconnect(client_socket)
            client_socket.close()

    def handle_disconnect(self, client_socket):     # handle client disconnection
        with self.lock:
            user_id = self.user_sessions.get(client_socket)
            if user_id:
                self.database_request({             # the user is offline use query
                    'collection': 'User',
                    'action': 'update',
                    'data': {
                        'id': user_id,
                        'fields': {'online': 0}
                    }
                })

                if user_id in self.online_users:
                    del self.online_users[user_id]
                if client_socket in self.user_sessions:
                    del self.user_sessions[client_socket]
                if user_id in self.user_names:
                    del self.user_names[user_id]
                if user_id in self.invitations:
                    del self.invitations[user_id]
                for room_id, members in list(self.room_members.items()):
                    if user_id in members:
                        members.discard(user_id)
                        '''if not members:             # delete empty room ##/
                            del self.room_members[room_id]
                            self.database_request({
                                'collection': 'Room',
                                'action': 'delete',
                                'data': {'id': room_id}
                            })'''
                print(f"[Lobby] User ID {user_id} disconnected")

    def database_request(self, request):            # send request to database server
        try:
            db_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)   # TCP socket
            db_socket.connect((self.database_host, self.database_port))
            send_message(db_socket, request)
            response = recv_message(db_socket)
            db_socket.close()
            return response
        except Exception as error:
            print(f"[Lobby] DB request error: {error}")
            return {'status': 'error', 'message': str(error)}

    def register_user(self, request):                   # user registration
        print(f"[Lobby] Register request: {request}")
        
        check_response = self.database_request({        # check if username already exists
            'collection': 'User',
            'action': 'query',
            'data': {'name': request['username']}
        })
        if check_response['status'] == 'success' and check_response['data']:
            return {'status': 'error', 'message': 'Username already exists'}

        response = self.database_request({
            'collection': 'User',
            'action': 'create',
            'data': {
                'name': request['username'],
                'password': request['password']
            }
        })
        print(f"[Lobby] Register response: {response}")
        if response['status'] == 'success':
            return {'status': 'success', 'message': 'Registration successful', 'userId': response['userId']}
        return response

    def login_user(self, client_socket, request):       # user login
        response = self.database_request({              # search user information in database
            'collection': 'User',
            'action': 'query',
            'data': {'name': request['username']}
        })

        if response['status'] != 'success' or not response['data']:     # failed or account not found
            return {'status': 'error', 'message': 'User not found'}
            
        user = response['data'][0]
        password = hashlib.sha256(request['password'].encode()).hexdigest()

        if user['online'] == 1:                       # already logged in
            return {'status': 'error', 'message': 'User already logged in'}
        
        if user['password_hashed'] != password:         # incorrect password
            return {'status': 'error', 'message': 'Invalid password'}
            
        with self.lock:
            user_id = user['id']
            self.online_users[user_id] = client_socket  # record current user's socket
            self.user_sessions[client_socket] = user_id
            self.user_names[user_id] = user['name']

        self.database_request({                         # update user information
            'collection': 'User',
            'action': 'update',
            'data': {
                'id': user_id,
                'fields': {
                    'online': 1,
                    'lastLoginAt': datetime.now().isoformat()
                }
            }
        })
        
        print(f"[Lobby] User {user['name']} (ID: {user_id}) logged in")
        return {'status': 'success', 'message': 'Login successful', 'userId': user_id}

    def logout_user(self, client_socket):              # user logout
        with self.lock:
            user_id = self.user_sessions.get(client_socket)
            if not user_id:
                return {'status': 'error', 'message': 'Not logged in'}

            self.database_request({                    # update user information
                'collection': 'User',
                'action': 'update',
                'data': {
                    'id': user_id,
                    'fields': {'online': 0}
                }
            })
            del self.online_users[user_id]
            del self.user_sessions[client_socket]
            if user_id in self.user_names:
                del self.user_names[user_id]
                
        print(f"[Lobby] User ID {user_id} logged out")
        return {'status': 'success', 'message': 'Logout successful'}

    def list_online_users(self):                    # list online users
        response = self.database_request({          # query online users
            'collection': 'User',
            'action': 'query',
            'data': {'online': 1}
        })
        
        if response['status'] == 'success':
            users = [{'id': u['id'], 'name': u['name']} for u in response['data']]
            return {'status': 'success', 'users': users}
        return response

    def list_rooms(self):                           # list available rooms
        response = self.database_request({
            'collection': 'Room',
            'action': 'query',
            'data': {}
        })

        if response['status'] == 'success':
            rooms = []
            for room in response['data']:
                user_response = self.database_request({          # query host name in database
                    'collection': 'User',
                    'action': 'query',
                    'data': {'id': room['host_user_id']}
                })
                host_name = user_response['data'][0]['name'] if user_response['status'] == 'success' and user_response['data'] else 'Unknown'
                
                max_players = 2  # default to 2 players
                game_id = room.get('game_id')
                if game_id:
                    game_response = self.database_request({     # query game info in database
                        'collection': 'Game',
                        'action': 'read',
                        'data': {'id': game_id}
                    })
                    if game_response['status'] == 'success':
                        max_players = game_response['data'].get('maxPlayers', 2)
                
                rooms.append({                                  # append room info
                    'id': room['id'],
                    'name': room['name'],
                    'host': host_name,
                    'visibility': room['visibility'],
                    'status': room['status'],
                    'members': len(self.room_members.get(room['id'], set())),
                    'max_players': max_players,
                    'game_name': room.get('game_name', 'Unknown Game')
                })
            return {'status': 'success', 'rooms': rooms}        # return all rooms info
        return response

    def create_room(self, client_socket, request):      # create a new room
        user_id = self.user_sessions.get(client_socket)
        if not user_id:
            return {'status': 'error', 'message': 'Not logged in'}
        
        game_name = request.get('game_name')
        game_id = None
        if game_name:
            game_query_response = self.database_request({       # query game info in database
                'collection': 'Game',
                'action': 'query',
                'data': {'name': game_name, 'status': 'active'}
            })
            print(f"[Lobby] Game query for '{game_name}': {game_query_response.get('status')}")
            if game_query_response['status'] == 'success':
                games = game_query_response.get('data', game_query_response.get('games', []))
                if games:
                    game_id = games[0]['id']
                    print(f"[Lobby] Found game_id: {game_id}")
                else:
                    all_games_response = self.database_request({    # query all games to check if removed
                        'collection': 'Game',
                        'action': 'query',
                        'data': {'name': game_name}
                    })
                    if all_games_response['status'] == 'success' and all_games_response.get('data'):
                        return {
                            'status': 'error',
                            'message': f'Game "{game_name}" has been removed by developer and is no longer available \n please choose another game!'
                        }
                    else:
                        return {
                            'status': 'error',
                            'message': f'Game "{game_name}" not found'
                        }
            else:
                print(f"[Lobby] Warning: Query failed for game '{game_name}'")
                return {
                    'status': 'error',
                    'message': 'Failed to query game information'
                }
        else:
            print(f"[Lobby] Warning: No game_name provided in create_room request")
            return {
                'status': 'error',
                'message': 'Game name is required to create a room'
            }
        
        response = self.database_request({
            'collection': 'Room',
            'action': 'create',
            'data': {
                'name': request['room_name'],
                'host_user_id': user_id,
                'visibility': request.get('visibility', 'public'),
                'invitelist': [],
                'game_name': game_name,                     # store game name for display
                'game_id': game_id                          # store game_id for version lookup
            }
        })
        
        if response['status'] == 'success':
            room_id = response['roomId']
            with self.lock:
                self.room_members[room_id] = {user_id}
            
            print(f"[Lobby] Room {room_id} created with game: {game_name}")
            return {
                'status': 'success',
                'message': 'Room created',
                'roomId': room_id
            }
        return response

    def join_room(self, client_socket, request, from_invitation=False):        # join an existing room
        user_id = self.user_sessions.get(client_socket)
        if not user_id:
            return {'status': 'error', 'message': 'Not logged in'}

        room_id = request['roomId']
        room_response = self.database_request({         # read room information from database
            'collection': 'Room',
            'action': 'read',
            'data': {'id': room_id}
        })
        
        if room_response['status'] != 'success':
            return {'status': 'error', 'message': 'Room not found'}
            
        room = room_response['data']
        
        if room['visibility'] == 'private':             # private room need invitation
            if user_id != room['host_user_id'] and not from_invitation:         # only host can join directly, others must use invitation
                return {'status': 'error', 'message': 'This is a private room. Please use accept invitation to join.'}
                
        if room['status'] == 'playing':                 # cannot join a game in progress
            return {'status': 'error', 'message': 'Game already started'}
        
        # get game info to check maxPlayers
        game_id = room.get('game_id')
        max_players = 2  # Default to 2 players
        if game_id:
            game_response = self.database_request({     # query game info in database
                'collection': 'Game',
                'action': 'read',
                'data': {'id': game_id}
            })
            if game_response['status'] == 'success':
                max_players = game_response['data'].get('maxPlayers', 2)
            
        with self.lock:
            if room_id not in self.room_members:
                self.room_members[room_id] = set()      # record all members in the room
            if len(self.room_members[room_id]) >= max_players:
                return {'status': 'error', 'message': 'Room is full'}
            self.room_members[room_id].add(user_id)
        
        is_host = (room['host_user_id'] == user_id)     # check if user is the host of this room
            
        print(f"[Lobby] User {user_id} joined room {room_id}")
        return {'status': 'success', 'message': 'Joined room', 'roomId': room_id, 'isHost': is_host}

    def leave_room(self, client_socket, request):       # leave a room
        user_id = self.user_sessions.get(client_socket)
        if not user_id:
            return {'status': 'error', 'message': 'Not logged in'}

        room_id = request['roomId']
        with self.lock:
            if room_id in self.room_members:
                self.room_members[room_id].discard(user_id)
                '''if not self.room_members[room_id]:      # if room is empty, delete it    ##/
                    del self.room_members[room_id]
                    self.database_request({
                        'collection': 'Room',
                        'action': 'delete',
                        'data': {'id': room_id}
                    })'''
            else:
                return {'status': 'error', 'message': 'Not in this room'}
                    
        print(f"[Lobby] User {user_id} left room {room_id}")
        return {'status': 'success', 'message': 'Left room'}

    def invite_user(self, client_socket, request):      # invite a user to a room
        user_id = self.user_sessions.get(client_socket)
        if not user_id:
            return {'status': 'error', 'message': 'Not logged in'}
            
        room_id = request['roomId']
        target_user_id = request['targetUserId']
        
        room_response = self.database_request({         # check the room exist amd get information
            'collection': 'Room',
            'action': 'read',
            'data': {'id': room_id}
        })
        
        if room_response['status'] != 'success':
            return {'status': 'error', 'message': 'Room not found'}
            
        room = room_response['data']
        
        if room['host_user_id'] != user_id:             # set that only host can invite player to join rooom
            return {'status': 'error', 'message': 'Only host can invite'}
            
        with self.lock:
            if target_user_id not in self.online_users:
                return {'status': 'error', 'message': 'User not online'}
            if target_user_id not in self.invitations:
                self.invitations[target_user_id] = []

            # check if already invited
            for invitation in self.invitations[target_user_id]:
                if invitation['roomId'] == room_id:
                    return {'status': 'error', 'message': 'Already invited'}
                    
            self.invitations[target_user_id].append({
                'roomId': room_id,
                'roomName': room['name'],
                'host': self.user_names.get(user_id, 'Unknown'),
                'gameName': room.get('game_name', 'Unknown Game')  # Add game name to invitation
            })
                
        invite_list = room['invitelist']                # record the users that are invited to the room
        if target_user_id not in invite_list:
            invite_list.append(target_user_id)
            self.database_request({
                'collection': 'Room',
                'action': 'update',
                'data': {
                    'id': room_id,
                    'fields': {'invitelist': invite_list}
                }
            })
            
        print(f"[Lobby] User {user_id} invited user {target_user_id} to room {room_id}")
        return {'status': 'success', 'message': 'Invitation sent'}

    def list_invitations(self, client_socket):         # list invitations for a user
        user_id = self.user_sessions.get(client_socket)
        if not user_id:
            return {'status': 'error', 'message': 'Not logged in'}
            
        with self.lock:
            invitations = self.invitations.get(user_id, [])     # the invitations of the user
            
        return {'status': 'success', 'invitations': invitations}

    def accept_invitation(self, client_socket, request):    # accept an invitation to a room
        user_id = self.user_sessions.get(client_socket)
        if not user_id:
            return {'status': 'error', 'message': 'Not logged in'}

        room_id = request['roomId']
        with self.lock:
            if user_id not in self.invitations:
                return {'status': 'error', 'message': 'No invitation found'}
                
            invitation_found = False
            for inv in self.invitations[user_id]:
                if inv['roomId'] == room_id:
                    invitation_found = True
                    self.invitations[user_id].remove(inv)       # remove the invitation once accepted
                    break
                    
            if not invitation_found:
                return {'status': 'error', 'message': 'No invitation for this room'}

            self.invitations[user_id] = [invitation for invitation in self.invitations[user_id] if invitation['roomId'] != room_id]
        return self.join_room(client_socket, {'roomId': room_id}, from_invitation=True)

    def start_game(self, client_socket, request):           # start a game in a room
        user_id = self.user_sessions.get(client_socket)
        if not user_id:
            return {'status': 'error', 'message': 'Not logged in'}

        room_id = request['roomId']
        room_response = self.database_request({             # read room information from database
            'collection': 'Room',
            'action': 'read',
            'data': {'id': room_id}
        })
        
        if room_response['status'] != 'success':
            return {'status': 'error', 'message': 'Room not found'}
        
        room = room_response['data']
        
        if room['host_user_id'] != user_id:
            return {'status': 'error', 'message': 'Only host can start game'}
        
        game_id = room.get('game_id')                       # get game_id from room info
        if not game_id:
            return {'status': 'error', 'message': 'Room missing game information'}
        
        game_response = self.database_request({             # read game information from database
            'collection': 'Game',
            'action': 'read',
            'data': {'id': game_id}
        })
        
        if game_response['status'] != 'success':
            return {'status': 'error', 'message': 'Game not found'}
        
        game_data = game_response['data']
        max_players = game_data.get('maxPlayers', 2)
        
        with self.lock:
            if room_id not in self.room_members or len(self.room_members[room_id]) != max_players:
                return {'status': 'error', 'message': f'Need exactly {max_players} players'}
        
        with self.lock:
            for test_port in range(10100, 11000):           # find an available port for the game server
                if test_port in self.used_ports:
                    continue
                try:
                    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    sock.bind((self.host, test_port))
                    sock.close()
                    break
                except:
                    continue
            self.used_ports.add(test_port)
        
        port = test_port
        with self.lock:
            self.game_servers[room_id] = port
            players = list(self.room_members[room_id])
        
        player_usernames = []
        for player_id in players:
            user_response = self.database_request({                 # get player username from database
                'collection': 'User',
                'action': 'read',
                'data': {'id': player_id}
            })
            if user_response['status'] == 'success':
                player_usernames.append(user_response['data']['name'])
            else:
                player_usernames.append(f'Player{player_id}')
        
        self.database_request({                 # update room status to 'playing' and set game server port
            'collection': 'Room',
            'action': 'update',
            'data': {
                'id': room_id,
                'fields': {
                    'status': 'playing',
                    'gameServerPort': port
                }
            }
        })
        
        game_name = room.get('game_name', 'Unknown Game')       # read game info from room
        game_id = room.get('game_id')                           # read game_id from room
        game_version = 'Unknown'
        
        print(f"[Lobby] Room data: game_name={game_name}, game_id={game_id}")
        
        # if game info is missing from room, try to infer it
        if not game_name or game_name == 'Unknown Game' or not game_id:
            print(f"[Lobby] Warning: Room {room_id} missing game information")
            return {
                'status': 'error',
                'message': 'Room was created without game information. Please recreate the room.'
            }
        
        # start the game server subprocess
        game_server_script = None
        if game_id:
            game_response = self.database_request({             # read the game information from database
                'collection': 'Game',
                'action': 'read',
                'data': {'id': game_id}
            })
            if game_response['status'] == 'success':
                game_data = game_response['data']
                
                if game_data.get('status') != 'active':         # the game has been removed by developer
                    with self.lock:
                        self.used_ports.discard(port)           # release the port since we won't use it    
                        if room_id in self.game_servers:
                            del self.game_servers[room_id]

                    self.database_request({                     # update the room status back to 'waiting'
                        'collection': 'Room',
                        'action': 'update',
                        'data': {
                            'id': room_id,
                            'fields': {
                                'status': 'waiting'
                            }
                        }
                    })
                    return {
                        'status': 'error',
                        'message': f'Game "{game_name}" has been removed by developer and is no longer available \n please choose another game and create a new room!'
                    }
                
                game_version = game_data.get('currentVersion', 'Unknown')
                server_file = game_data.get('serverFile', 'game_server.py')
                
                # Locate game server script
                import re
                def sanitize_name(name: str) -> str:
                    safe = re.sub(r'[^A-Za-z0-9 _\-]', '', name)
                    safe = safe.strip().replace(' ', '_')
                    if not safe:
                        safe = 'unnamed_game'
                    return safe
                
                game_name_safe = sanitize_name(game_name)
                server_dir = os.path.dirname(os.path.abspath(__file__))
                game_server_script = os.path.join(                  # construct path to game server script
                    server_dir, 'uploaded_games', game_name_safe, 
                    game_version, server_file
                )
        
        if game_server_script and os.path.exists(game_server_script):       # launch game server process
            import subprocess
            game_dir = os.path.dirname(game_server_script)
            env = os.environ.copy()
            env['CF_PORT'] = str(port)
            env['CF_ROOM'] = str(room_id)
            env['GAME_PORT'] = str(port)
            env['GAME_ROOM'] = str(room_id)
            
            # Try to start with command-line arguments (standard way)
            # Format: python3 server_file.py <port> <room_id> <game_id> <game_name> <game_version> <player1_username> <player2_username> [<player3_username>]
            cmd = ['python3', server_file, str(port), str(room_id), str(game_id), game_name, game_version] + [str(username) for username in player_usernames]
            
            try:
                # Launch game server
                print(f"[Lobby] Launching game server with command: {' '.join(cmd)}")
                print(f"[Lobby] Working directory: {game_dir}")
                process = subprocess.Popen(
                    cmd, 
                    cwd=game_dir,
                    env=env
                )
                time.sleep(2.5)
                poll_result = process.poll()
                
                if poll_result is not None:             # error starting process
                    # Process died immediately
                    print(f"[Lobby] Game server failed to start (exit code {poll_result})")
                    print(f"[Lobby] Command: {' '.join(cmd)}")
                    print(f"[Lobby] Working dir: {game_dir}")
                    return {
                        'status': 'error',
                        'message': f'Game server failed to start (exit code {poll_result})'
                    }
                else:
                    print(f"[Lobby] Game server launched successfully!")
                    print(f"[Lobby] Script: {server_file}")
                    print(f"[Lobby] PID: {process.pid}")
                    print(f"[Lobby] Port: {port}, Room: {room_id}")
                    
            except Exception as e:
                print(f"[Lobby] Failed to launch game server: {e}")
                import traceback
                traceback.print_exc()
        else:
            print(f"[Lobby] Warning: Game server script not found: {game_server_script}")
            if game_server_script:
                print(f"[Lobby] Expected path: {game_server_script}")
                print(f"[Lobby] Directory exists: {os.path.exists(os.path.dirname(game_server_script))}")
        
        time.sleep(1.5)                                     # wait for server to fully start
        
        print(f"[Lobby] Game started for room {room_id} on port {port}")
        
        return {                                            # return game server port and game info
            'status': 'success',
            'message': 'Game started',
            'gameServerPort': port,
            'gameName': game_name,
            'gameVersion': game_version,
            'players': players
        }

    def spectate_game(self, client_socket, request):        # spectate an ongoing game not used
        user_id = self.user_sessions.get(client_socket)
        if not user_id:
            return {'status': 'error', 'message': 'Not logged in'}

        room_id = request['roomId']
        room_response = self.database_request({
            'collection': 'Room',
            'action': 'read',
            'data': {'id': room_id}
        })
        
        if room_response['status'] != 'success':
            return {'status': 'error', 'message': 'Room not found'}
            
        room = room_response['data']
        
        if room['status'] != 'playing':
            return {'status': 'error', 'message': 'Game not started yet'}
            
        with self.lock:
            if room_id not in self.game_servers:
                return {'status': 'error', 'message': 'Game server not found'}
            port = self.game_servers[room_id]
            players = list(self.room_members.get(room_id, []))
            
        print(f"[Lobby] User {user_id} spectating room {room_id}")
        
        return {
            'status': 'success',
            'message': 'Spectating game',
            'gameServerPort': port,
            'players': players,
            'spectator': True
        }

    def game_ended(self, request):                      # handle game end
        room_id = request['roomId']
        game_id = request.get('game_id')                # get the game info from request
        game_name = request.get('game_name')
        game_version = request.get('game_version')
        
        print(f"[Lobby] game_ended - Received from game server: game_id={game_id}, game_name={game_name}, game_version={game_version}")
        
        self.database_request({                         # update room status to idle
            'collection': 'Room',
            'action': 'update',
            'data': {
                'id': room_id,
                'fields': {'status': 'idle'}
            }
        })
        
        with self.lock:                                 # free up the game server port  
            if room_id in self.game_servers:
                port = self.game_servers[room_id]
                self.used_ports.discard(port)           # release the port since we won't use it    
                del self.game_servers[room_id]

        if 'matchId' in request:
            self.database_request({                     # save game log
                'collection': 'GameLog',
                'action': 'create',
                'data': {
                    'matchId': request['matchId'],
                    'roomId': room_id,
                    'game_id': game_id,
                    'game_name': game_name,
                    'game_version': game_version,       # Add version to GameLog
                    'users': request['users'],
                    'startAt': request['startAt'],
                    'endAt': request['endAt'],
                    'results': request.get('results', [])
                }
            })
            
        print(f"[Lobby] Game ended for room {room_id}")
        return {'status': 'success', 'message': 'Game ended'}

    def check_room_status(self, request):           # check if game has started in a room
        room_id = request.get('roomId')
        if not room_id:
            return {'status': 'error', 'message': 'Room ID required'}
        
        room_response = self.database_request({     # read room information from database
            'collection': 'Room',
            'action': 'read',
            'data': {'id': room_id}
        })
        
        if room_response['status'] != 'success':
            return {'status': 'error', 'message': 'Room not found'}
        
        room = room_response['data']

        # check if game has started
        if room['status'] == 'playing':
            with self.lock:
                game_port = self.game_servers.get(room_id)      # get game server port
            
            if game_port:
                game_name = room.get('game_name', 'Unknown Game')
                game_version = 'Unknown'
                game_id = room.get('game_id')
                if game_id:
                    game_response = self.database_request({     # query game info in database
                        'collection': 'Game',
                        'action': 'read',
                        'data': {'id': game_id}
                    })
                    if game_response['status'] == 'success':
                        game_version = game_response['data'].get('currentVersion', 'Unknown')
                
                return {                                # return the game info to client
                    'status': 'success',
                    'gameStarted': True,
                    'gameServerPort': game_port,
                    'gameName': game_name,
                    'gameVersion': game_version
                }

        return {'status': 'success', 'gameStarted': False}

    def cleanup(self):                              # cleanup all rooms when server shuts down
        print("[Lobby] Cleaning up all rooms...")
        
        # query all rooms from database
        room_response = self.database_request({
            'collection': 'Room',
            'action': 'query',
            'data': {}
        })
        
        if room_response['status'] == 'success' and room_response['data']:
            room_count = len(room_response['data'])
            for room in room_response['data']:
                room_id = room['id']
                self.database_request({             # delete all rooms from database
                    'collection': 'Room',
                    'action': 'delete',
                    'data': {'id': room_id}
                })
            print(f"[Lobby] Deleted {room_count} room(s)")
        else:
            print("[Lobby] No rooms to delete")
        
        # clear data
        with self.lock:
            self.rooms.clear()
            self.room_members.clear()
            self.game_servers.clear()
            self.used_ports.clear()
        
        print("[Lobby] Cleanup completed")

    def browse_store(self):                     # retrieve list of available games
        response = self.database_request({
            'collection': 'Game',
            'action': 'query',
            'data': {'browsing': True}          # Only get active games
        })
        
        if response['status'] == 'success':
            return {
                'status': 'success',
                'games': response['data']
            }
        return response
    
    def get_game_by_name(self, request):        # retrieve game info by name
        game_name = request.get('gameName')
        if not game_name:
            return {'status': 'error', 'message': 'Missing gameName'}
        
        response = self.database_request({      # query game by name to receive game info
            'collection': 'Game',
            'action': 'query',
            'data': {'name': game_name, 'status': 'active'}
        })
        
        if response['status'] == 'success' and response['data']:
            return {
                'status': 'success',
                'game': response['data'][0]     # Return first matching active game
            }
        return {'status': 'error', 'message': 'Game not found'}
    
    def download_game(self, client_socket, request):            # send game files to player for download
        try:
            game_id = request.get('gameId')
            version = request.get('version')
            
            if not game_id or not version:
                return {'status': 'error', 'message': 'Missing gameId or version'}
            
            game_response = self.database_request({             # read game information from database
                'collection': 'Game',
                'action': 'read',
                'data': {'id': game_id}
            })
            
            if game_response['status'] != 'success':
                return {'status': 'error', 'message': 'Game not found'}
            
            game = game_response['data']
            
            if game['status'] != 'active':                      # check if game is active
                return {'status': 'error', 'message': 'Game is no longer available'}
            
            import re
            def sanitize_name(name: str) -> str:
                safe = re.sub(r'[^A-Za-z0-9 _\-]', '', name)
                safe = safe.strip().replace(' ', '_')
                if not safe:
                    safe = 'unnamed_game'
                return safe
            
            game_name_safe = sanitize_name(game.get('name', 'unnamed_game'))
            server_dir = os.path.dirname(os.path.abspath(__file__))
            game_path = os.path.join(server_dir, 'uploaded_games', game_name_safe, version)
            
            if not os.path.exists(game_path):
                return {'status': 'error', 'message': 'Game files not found on server'}
            
            files_to_send = []                                  # gather all files to send  
            for root, dirs, files in os.walk(game_path):
                for file in files:
                    file_path = os.path.join(root, file)
                    rel_path = os.path.relpath(file_path, game_path)
                    files_to_send.append((file_path, rel_path))
            
            if not files_to_send:
                return {'status': 'error', 'message': 'No game files found'}
            
            send_message(client_socket, {                       # notify client ready to receive files
                'status': 'ready',
                'message': 'Ready to send files',
                'fileCount': len(files_to_send)
            })
            
            for file_path, rel_path in files_to_send:           # send each file
                send_message(client_socket, {'name': rel_path})
                
                if not self.send_file(client_socket, file_path):
                    return {'status': 'error', 'message': f'Failed to send file: {rel_path}'}
            
            print(f"[Lobby] Sent {len(files_to_send)} files for game {game_id} v{version}")
            return None  # Response already sent
            
        except Exception as e:
            print(f"[Lobby] Error in download_game: {e}")
            return {'status': 'error', 'message': str(e)}
    
    def send_file(self, sock, file_path):              # send a single file over socket
        try:
            file_size = os.path.getsize(file_path)
            metadata = {
                'type': 'FILE_METADATA',
                'size': file_size,
                'name': os.path.basename(file_path)
            }
            send_message(sock, metadata)
            
            with open(file_path, 'rb') as f:            # send file data in chunks
                sent = 0
                while sent < file_size:
                    chunk = f.read(8192)
                    if not chunk:
                        break
                    sock.sendall(chunk)
                    sent += len(chunk)
            
            return sent == file_size
        except Exception as e:
            print(f"[Lobby] Error sending file: {e}")
            return False
    
    def submit_review(self, request):                   # submit rating and review for a game
        try:
            user_id = request.get('userId')
            game_id = request.get('gameId')
            rating = request.get('rating')
            review = request.get('review')
            
            if not all([user_id, game_id, rating]):
                return {'status': 'error', 'message': 'Missing required fields'}
            
            if not (0 <= rating <= 5):
                return {'status': 'error', 'message': 'Rating must be between 0 and 5'}
            
            user_response = self.database_request({     # get user info
                'collection': 'User',
                'action': 'read',
                'data': {'id': user_id}
            })
            
            if user_response['status'] != 'success':
                return {'status': 'error', 'message': 'User not found'}
            
            username = user_response['data']['name']
            game_response = self.database_request({     # get game info 
                'collection': 'Game',
                'action': 'read',
                'data': {'id': game_id}
            })
            
            if game_response['status'] != 'success':
                return {'status': 'error', 'message': 'Game not found'}
            
            game_name = game_response['data'].get('name')
            game_version = game_response['data'].get('currentVersion')  # Get current version
            gamelog_response = self.database_request({  # check game logs to verify user has played the game
                'collection': 'GameLog',
                'action': 'query',
                'data': {}
            })
            
            if gamelog_response['status'] != 'success':
                return {'status': 'error', 'message': 'Failed to query game logs'}
            has_played = False
            for log in gamelog_response['data']:            # check each log entry
                log_game_name = log.get('game_name')
                log_game_id = log.get('game_id')
                log_game_version = log.get('game_version')
                
                is_same_game = (log_game_id == game_id) or \
                              (log_game_name == game_name and log_game_version == game_version)
                
                if is_same_game and username in log.get('users', []):
                    has_played = True
                    break
                
                if not is_same_game:
                    room_id = log.get('roomId')
                    if room_id:
                        room_response = self.database_request({
                            'collection': 'Room',
                            'action': 'read',
                            'data': {'id': int(room_id)}
                        })
                        
                        if room_response['status'] == 'success':
                            room_game_name = room_response['data'].get('game_name')
                            room_game_id = room_response['data'].get('game_id')
                            
                            is_same_game = (room_game_id == game_id) or (room_game_name == game_name)
                            
                            if is_same_game and username in log.get('users', []):
                                has_played = True
                                break
            
            if not has_played:
                return {'status': 'error', 'message': f'You must play "{game_name}" before rating or reviewing it'}
            
            response = self.database_request({              # add rating and review to database
                'collection': 'Game',
                'action': 'add_rating',
                'data': {
                    'gameId': game_id,
                    'userId': user_id,
                    'rating': rating,
                    'review': review
                }
            })
            
            if response['status'] == 'success':
                print(f"[Lobby] User {username} (ID: {user_id}) rated game {game_id}: {rating} stars")
                return {'status': 'success', 'message': 'Review submitted successfully'}
            
            return response
            
        except Exception as e:
            print(f"[Lobby] Error submitting review: {e}")
            return {'status': 'error', 'message': str(e)}
    
    def check_play_history(self, request):              # check if user has played a game
        try:
            user_id = request.get('userId')
            game_id = request.get('gameId')
            
            if not all([user_id, game_id]):
                return {'status': 'error', 'message': 'Missing required fields'}
            
            # get user info
            user_response = self.database_request({
                'collection': 'User',
                'action': 'read',
                'data': {'id': user_id}
            })
            
            if user_response['status'] != 'success':
                return {'status': 'error', 'message': 'User not found'}
            
            username = user_response['data']['name']
            
            # get game info
            game_response = self.database_request({
                'collection': 'Game',
                'action': 'read',
                'data': {'id': game_id}
            })
            
            if game_response['status'] != 'success':
                return {'status': 'error', 'message': 'Game not found'}
            
            game_name = game_response['data'].get('name')
            game_version = game_response['data'].get('currentVersion')  # Get current version
            
            # check game logs
            gamelog_response = self.database_request({
                'collection': 'GameLog',
                'action': 'query',
                'data': {}
            })
            
            if gamelog_response['status'] != 'success':
                return {'status': 'error', 'message': 'Failed to query game logs'}
            
            has_played = False
            for log in gamelog_response['data']:
                log_game_name = log.get('game_name')                # check game info in log
                log_game_id = log.get('game_id')
                log_game_version = log.get('game_version')
                
                is_same_game = (log_game_id == game_id) or \
                              (log_game_name == game_name and log_game_version == game_version)
                
                if is_same_game and username in log.get('users', []):
                    has_played = True
                    break
            
            return {
                'status': 'success',
                'hasPlayed': has_played,
                'gameName': game_name
            }
            
        except Exception as e:
            print(f"[Lobby] Error checking play history: {e}")
            return {'status': 'error', 'message': str(e)}

###### lobby part end ######

def main():
    lobby = LobbyServer(database_host=DATABASE_SERVER_HOST, database_port=DATABASE_SERVER_PORT)
    t = threading.Thread(target=lobby.start, daemon=True)
    t.start()
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        lobby.cleanup()
        lobby.running = False


if __name__ == '__main__':
    main()

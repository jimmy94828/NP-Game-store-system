# client of the game
import socket
import threading
import struct
import json
import time
import sys
import pygame
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

###### game part start ######
SHAPE_NAMES = ['I', 'O', 'T', 'S', 'Z', 'J', 'L']
SHAPES = {                                          # piece shapes and rotation shapes
    'I': [
        [(0,1), (1,1), (2,1), (3,1)],
        [(2,0), (2,1), (2,2), (2,3)],
        [(0,2), (1,2), (2,2), (3,2)],
        [(1,0), (1,1), (1,2), (1,3)]
    ],
    'O': [
        [(1,0), (2,0), (1,1), (2,1)],
        [(1,0), (2,0), (1,1), (2,1)],
        [(1,0), (2,0), (1,1), (2,1)],
        [(1,0), (2,0), (1,1), (2,1)]
    ],
    'T': [
        [(1,0), (0,1), (1,1), (2,1)],
        [(1,0), (1,1), (2,1), (1,2)],
        [(0,1), (1,1), (2,1), (1,2)],
        [(1,0), (0,1), (1,1), (1,2)]
    ],
    'S': [
        [(1,0), (2,0), (0,1), (1,1)],
        [(1,0), (1,1), (2,1), (2,2)],
        [(1,1), (2,1), (0,2), (1,2)],
        [(0,0), (0,1), (1,1), (1,2)]
    ],
    'Z': [
        [(0,0), (1,0), (1,1), (2,1)],
        [(2,0), (1,1), (2,1), (1,2)],
        [(0,1), (1,1), (1,2), (2,2)],
        [(1,0), (0,1), (1,1), (0,2)]
    ],
    'J': [
        [(0,0), (0,1), (1,1), (2,1)],
        [(1,0), (2,0), (1,1), (1,2)],
        [(0,1), (1,1), (2,1), (2,2)],
        [(1,0), (1,1), (0,2), (1,2)]
    ],
    'L': [
        [(2,0), (0,1), (1,1), (2,1)],
        [(1,0), (1,1), (1,2), (2,2)],
        [(0,1), (1,1), (2,1), (0,2)],
        [(0,0), (1,0), (1,1), (1,2)]
    ]
}

COLORS = {
    0: (0, 0, 0),          # empty
    1: (255, 0, 0),        # red    I
    2: (0, 255, 0),        # green  O
    3: (0, 0, 255),        # blue   T
    4: (255, 255, 0),      # yellow S
    5: (255, 165, 0),      # orange Z
    6: (128, 0, 128),      # purple J
    7: (0, 255, 255),      # cyan   L
}
BACKGROUND_COLOR = (20, 20, 20)
GRID_COLOR = (50, 50, 50)
TEXT_COLOR = (255, 255, 255)

###### effect part start ######
class element:                                  # single particle of firework
    def __init__(self, x, y, color):
        self.x = x                              # position, direction, velocity
        self.y = y
        angle = random.uniform(0, 2 * math.pi)
        speed = random.uniform(2, 8)
        self.vx = math.cos(angle) * speed
        self.vy = math.sin(angle) * speed
        self.color = color
        self.lifetime = random.uniform(0.5, 1.5)
        self.age = 0
        self.size = random.randint(2, 5)
    
    def update(self, dt):
        self.x += self.vx
        self.y += self.vy
        self.vy += 0.3              # acceleration
        self.vx *= 0.98             # decrease speed
        self.age += dt
    
    def draw(self, screen):         # draw the elements and make the color become darker
        if self.age < self.lifetime:
            color = tuple(int(c * (1.0 - (self.age / self.lifetime))) for c in self.color)
            pygame.draw.circle(screen, color, (int(self.x), int(self.y)), self.size)

class firework:                     # draw the firework
    def __init__(self, x, y, color, element_count=30):
        self.elements = []
        for _ in range(element_count):
            self.elements.append(element(x, y, color))
    
    def update(self, dt):           # update elements
        for element in self.elements:
            element.update(dt)
        self.elements = [p for p in self.elements if (p.age < p.lifetime)]
    
    def draw(self, screen):         # draw elements
        for element in self.elements:
            element.draw(screen)

class control_firework:             # manage multiple fireworks
    def __init__(self):
        self.fireworks = []
    
    def generate_firework(self, board_x, board_y, board_width, cell_size, lines_cleared):
        colors = [
            (255, 100, 100),  # red
            (100, 255, 100),  # green
            (100, 100, 255),  # blue
            (255, 255, 100),  # yellow
            (128, 0, 128),    # purple
            (100, 255, 255),  # cyan
        ]
        
        firework_count = lines_cleared * 3  # 3/ line
        
        for i in range(firework_count):
            fx = board_x + random.randint(0, board_width * cell_size)
            fy = board_y + random.randint(0, 100)
            color = random.choice(colors)
            element_count = 20 + lines_cleared * 10
            self.fireworks.append(firework(fx, fy, color, element_count))
    
    def update(self, dt):                   # update fireworks
        for firework in self.fireworks:
            firework.update(dt)
        self.fireworks = [f for f in self.fireworks if not len(f.elements) == 0]        # remove finished fireworks
    
    def draw(self, screen):                 # draw fireworks
        for firework in self.fireworks:
            firework.draw(screen)
    
    def clear(self):
        self.fireworks.clear()
###### effect part end ######

class gameClient:
    def __init__(self, host, port, user_id, room_id, spectator = False):
        self.host = host
        self.port = port
        self.user_id = user_id
        self.room_id = room_id
        self.spectator = spectator
        self.socket = None
        self.running = False
        
        self.my_state = None
        self.opponent_state = None
        self.game_config = None
        self.game_started = False
        self.game_ended = False
        self.results = None
        self.match_id = None
        self.start_time = None
        self.end_time = None
        self.game_duration = 180  # game time = 180 seconds
        self.game_starttime = None
        self.game_end_stamp = None
        self.closed = False
        self.connected = False
        self.connecting = False
        
        self.screen = None
        self.clock = None
        self.font = None
        self.large_font = None
        
        self.cell_size = 25
        self.board_width = 10
        self.board_height = 20
        ## effect part firework
        self.firework_manager = control_firework()
        self.number_cleared = 0
        self.lock = threading.Lock()
    
    def initial_pygame(self):                   # initialize the pygame window
        pygame.init()

        board_area_width = self.board_width * self.cell_size
        board_area_height = self.board_height * self.cell_size
        info_width = 200
        gap = 40

        screen_width = board_area_width * 2 + gap + info_width * 2      # two boards and info areas
        screen_height = board_area_height + 150
        
        self.screen = pygame.display.set_mode((screen_width, screen_height))
        if self.spectator:                                              # set the title of the window
            pygame.display.set_caption("Tetris Battle - Spectator Mode")
        else:
            pygame.display.set_caption("Tetris Battle")
        
        self.clock = pygame.time.Clock()        # control the frame rate
        self.font = pygame.font.Font(None, 24)
        self.large_font = pygame.font.Font(None, 48)

    def background_connect(self):               # connect to the game server in background
        try:
            if self.connect_game():
                self.connected = True
                recv_thread = threading.Thread(target=self.receive_messages, daemon=True)
                recv_thread.start()
            else:
                print("Failed to connect to game server")
                self.running = False
        finally:
            self.connecting = False

    def connect_game(self):
        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)     # TCP socket
            self.socket.settimeout(10.0)
            self.socket.connect((self.host, self.port))             # connect to the game server
            # Send a small plain JSON identification first (compatible with connect_four_client)
            try:
                ident = {
                    'username': self.user_id,
                    'roomId': self.room_id,
                    'spectator': self.spectator
                }
                self.socket.sendall(json.dumps(ident).encode())
            except Exception:
                # fallback to LPFP HELLO if raw send fails
                send_message(self.socket, {
                    'type': 'HELLO',
                    'version': 1,
                    'roomId': self.room_id,
                    'userId': self.user_id,
                    'spectator': self.spectator
                })
            
            # Expect the server to reply using LPFP (WELCOME message)
            welcome = recv_message(self.socket)
            if welcome and welcome['type'] == 'WELCOME':
                self.game_config = welcome
                print(f"Connected to game server as {welcome['role']}")
                self.role = welcome['role']
                # get game duration from config if available
                if 'duration' in welcome:
                    self.game_duration = welcome['duration']
                if self.spectator and welcome.get('gameStarted'):
                    with self.lock:
                        self.game_started = True
                        self.start_time = welcome.get('startTime')
                        elapsed = welcome.get('elapsedTime', 0)
                        self.game_starttime = time.time() - elapsed
                self.socket.settimeout(None)
                return True
            else:
                print(f"Failed to receive WELCOME message. Got: {welcome}")
                return False
                
        except Exception as error:
            print(f"Connection failed: {error}")
            import traceback
            traceback.print_exc()               # print the error stack trace
            return False
    
    def receive_messages(self):                 # receive messages from the game server
        try:
            while self.running:
                message = recv_message(self.socket)
                if not message and self.spectator:
                    time.sleep(10)
                if not message:
                    break
                message_type = message.get('type')

                if message_type == 'GAME_START':    # game start message
                    with self.lock:
                        self.game_started = True
                        self.start_time = message.get('startTime')
                        # Only set game_starttime if not already set (for spectators joining mid-game)
                        if not self.game_starttime:
                            self.game_starttime = time.time()  # Record local timestamp
                    print("Game started!")
                    print("Press Enter when game is finished...")
                elif message_type == 'SNAPSHOTS':   # receive game state snapshots
                    with self.lock:
                        if self.spectator:          # receive both players' states
                            snapshots = message['data']
                            if len(snapshots) >= 2:
                                if snapshots[0]['role'] == 'P1':
                                    self.my_state = snapshots[0]
                                    self.opponent_state = snapshots[1]
                                else:
                                    self.my_state = snapshots[1]
                                    self.opponent_state = snapshots[0]
                        else:                       # receive own and opponent's states
                            for snapshot in message['data']:
                                if snapshot['userId'] == self.user_id:
                                    self.my_state = snapshot
                                else:
                                    self.opponent_state = snapshot
                elif message_type == 'GAME_END':    # game end message
                    with self.lock:
                        self.game_ended = True
                        self.results = message['results']
                        self.end_time = message.get('endTime')
                        self.game_end_stamp = message['timestamp']
                    print("Game ended!")

        except ProtocolError:
            pass
        except Exception as error:
            print(f"Error receiving messages: {error}")
        finally:
            self.running = False

    def send_input(self, action):               # send player input to the game server
        try:
            send_message(self.socket, {
                'type': 'INPUT',
                'userId': self.user_id,
                'action': action,
                'timestamp': time.time()
            })
        except Exception as error:
            print(f"Error sending input: {error}")

    def cleared_lines(self, board_x, board_y):          # check how many lines is cleared
        if not self.spectator and self.my_state:
            cleared_lines = self.my_state.get('lines', 0)
            if cleared_lines > self.number_cleared:
                lines_cleared = cleared_lines - self.number_cleared
                self.firework_manager.generate_firework(
                    board_x, board_y, self.board_width, self.cell_size, lines_cleared
                )
            self.number_cleared = cleared_lines

    def draw_board(self, board, x_offset, y_offset, current_piece=None, cell_size=None):    # draw the Tetris board
        if cell_size is None:
            cell_size = self.cell_size
            
        board_width = len(board[0]) if board else 10
        board_height = len(board) if board else 20
        
        board_rect = pygame.Rect(               # board area
            x_offset,                           # left
            y_offset,                           # top
            board_width * cell_size,            # width
            board_height * cell_size            # height
        )
        pygame.draw.rect(self.screen, (30, 30, 40), board_rect)     # color: dark background

        # draw the locked pieces one by one
        for y in range(board_height):
            for x in range(board_width):
                rect = pygame.Rect(x_offset + x * cell_size, y_offset + y * cell_size, cell_size, cell_size)
                color = COLORS[board[y][x]]
                pygame.draw.rect(self.screen, color, rect)
                pygame.draw.rect(self.screen, GRID_COLOR, rect, 1)  # grid lines

        # draw current falling piece
        if current_piece and current_piece.get('type'):
            piece_type = current_piece['type']
            rotation = current_piece.get('rotation', 0)
            piece_x = current_piece.get('x', 0)
            piece_y = current_piece.get('y', 0)
            
            if piece_type in SHAPES:
                shape = SHAPES[piece_type][rotation]        # current piece's shape
                piece_value = SHAPE_NAMES.index(piece_type) + 1
                color = COLORS[piece_value]
                
                for dx, dy in shape:
                    board_x = piece_x + dx
                    board_y = piece_y + dy
                    # only draw if within board bounds
                    if 0 <= board_x < board_width and 0 <= board_y < board_height:
                        rect = pygame.Rect(x_offset + board_x * cell_size, y_offset + board_y * cell_size, cell_size, cell_size)
                        pygame.draw.rect(self.screen, color, rect)
                        pygame.draw.rect(self.screen, GRID_COLOR, rect, 1)      # grid lines
                
        pygame.draw.rect(self.screen, (100, 100, 120), board_rect, 3)           # board border

    def draw_info(self, state, x_offset, y_offset, title):                      # draw players' info
        title_surface = self.font.render(title, True, TEXT_COLOR)
        self.screen.blit(title_surface, (x_offset, y_offset))
        if self.spectator:
            y = y_offset + 40   
            score_text = f"Score: {state['score']}"
            score_surface = self.font.render(score_text, True, TEXT_COLOR)
            self.screen.blit(score_surface, (x_offset, y))
            y += 30
            
            lines_text = f"Lines: {state['lines']}"
            lines_surface = self.font.render(lines_text, True, TEXT_COLOR)
            self.screen.blit(lines_surface, (x_offset, y))
            y -= 30
            x = x_offset + 120
            
            level_text = f"Level: {state['level']}"
            level_surface = self.font.render(level_text, True, TEXT_COLOR)
            self.screen.blit(level_surface, (x, y))
            y += 30

            combo_text = f"Combo: {state['combo']}"
            combo_surface = self.font.render(combo_text, True, TEXT_COLOR)
            self.screen.blit(combo_surface, (x, y))
            y += 30
            
            if state.get('gameOver'):
                game_surface = self.font.render("GAME OVER", True, (255, 0, 0))
                self.screen.blit(game_surface, (x_offset + 100, y_offset))
        else:
            y = y_offset + 40
            score_text = f"Score: {state['score']}"
            score_surface = self.font.render(score_text, True, TEXT_COLOR)
            self.screen.blit(score_surface, (x_offset, y))
            y += 30
            
            lines_text = f"Lines: {state['lines']}"
            lines_surface = self.font.render(lines_text, True, TEXT_COLOR)
            self.screen.blit(lines_surface, (x_offset, y))
            y += 30
            
            level_text = f"Level: {state['level']}"
            level_surface = self.font.render(level_text, True, TEXT_COLOR)
            self.screen.blit(level_surface, (x_offset, y))
            y += 30
            
            combo_text = f"Combo: {state['combo']}"
            combo_surface = self.font.render(combo_text, True, TEXT_COLOR)
            self.screen.blit(combo_surface, (x_offset, y))
            y += 30
            
            if state.get('gameOver'):
                game_surface = self.font.render("GAME OVER", True, (255, 0, 0))
                self.screen.blit(game_surface, (x_offset, y))

    def draw_controls(self):            # draw the control instructions at the bottom left
        if self.spectator:
            controls = [
                "Spectator Mode",
                "",
                "You are watching the ",
                "game in Room ID: {}".format(self.room_id),
                "ESC : Quit"
            ]
        else:
            controls = [
                "Player Controls:",
                "left/right : Move",
                "up   : Rotate clockwise",
                "N    : Rotate counter-clockwise",
                "down : Soft Drop",
                "B    : Hard Drop",
                "SPACE    : Hold",
                "ESC : Quit"
            ]
        # position to draw controls
        x = 20
        y = self.screen.get_height() - 300
        
        for line in controls:
            surface = self.font.render(line, True, TEXT_COLOR)
            self.screen.blit(surface, (x, y))
            y += 25

    def draw_timer(self):               # draw the count down timer to show the remaining game time
        if not self.game_started or self.game_ended or self.game_starttime is None:
            return
        
        elapsed_time = time.time() - self.game_starttime            # used time
        remaining_time = max(0, self.game_duration - elapsed_time)  # remaining time in seconds
        minutes = int(remaining_time // 60)
        seconds = int(remaining_time % 60)
        time_text = f"Remaining Time: {minutes:02d}:{seconds:02d}"
        if remaining_time > 60:             # change color based on remaining time
            timer_color = (255, 255, 255)   # white
        elif remaining_time > 30:
            timer_color = (255, 255, 0)     # yellow
        else:
            timer_color = (255, 0, 0)       # red
        if self.spectator:
            spectator_surface = self.large_font.render(time_text, True, timer_color)
            spectator_rect = spectator_surface.get_rect(center=(self.screen.get_width() // 2, 20))
            self.screen.blit(spectator_surface, spectator_rect)
        else:
            timer_surface = self.large_font.render(time_text, True, timer_color)
            timer_rect = timer_surface.get_rect(center=(self.screen.get_width() // 2, 20))  # get the rect and put at center top
            self.screen.blit(timer_surface, timer_rect)

    def draw_results(self, time_remaining=None):                    # draw the game results after game ended
        overlay = pygame.Surface(self.screen.get_size())
        overlay.set_alpha(200)
        overlay.fill((0, 0, 0))
        self.screen.blit(overlay, (0, 0))
        
        title_surface = self.large_font.render("GAME OVER", True, (255, 255, 0))        # display game over title
        title_rect = title_surface.get_rect(center=(self.screen.get_width() // 2, 100))
        self.screen.blit(title_surface, title_rect)
        
        y = 200
        for i, result in enumerate(self.results):
            rank = i + 1
            me = result['userId'] == self.user_id
            color = (0, 255, 0) if me else TEXT_COLOR               # highlight the player's own result
            
            text = f"#{rank} - User {result['userId']}: {result['score']} pts ({result['lines']} lines)"
            surface = self.font.render(text, True, color)
            rect = surface.get_rect(center=(self.screen.get_width() // 2, y))
            self.screen.blit(surface, rect)
            y += 40
        
        # show the winner with larger font
        if self.results[0]['score'] != self.results[1]['score']:
            winner = self.results[0]
            winner_text = f"Winner: User {winner['userId']} with {winner['score']} pts!"
            winner_surface = self.large_font.render(winner_text, True, (255, 215, 0))
            winner_rect = winner_surface.get_rect(center=(self.screen.get_width() // 2, y + 30))
            self.screen.blit(winner_surface, winner_rect)
        else:                       # draw
            tie_text = "It's a tie!"
            tie_surface = self.large_font.render(tie_text, True, (255, 215, 0))
            tie_rect = tie_surface.get_rect(center=(self.screen.get_width() // 2, y + 30))
            self.screen.blit(tie_surface, tie_rect)
        
        if self.spectator:
            hint_text = "Press ESC to exit or after 10 seconds, the window will close automatically."
        elif time_remaining is not None:
            hint_text = f"Returning to menu in {int(time_remaining)}s... (or press ESC to close)"
        else:
            hint_text = "Press ESC to exit"

        hint_surface = self.font.render(hint_text, True, TEXT_COLOR)
        hint_rect = hint_surface.get_rect(center=(self.screen.get_width() // 2, y + 70))
        self.screen.blit(hint_surface, hint_rect)

    def run(self):
        self.initial_pygame()
        self.running = True
        
        self.connecting = True              # connect to game server
        connect_thread = threading.Thread(target=self.background_connect, daemon=True)
        connect_thread.start()
        
        result_display_time = None                # check when to auto-close after game ends
        while self.running:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self.running = False
                elif event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE:
                        self.running = False
            
            if self.game_ended and result_display_time is None:
                if hasattr(self, 'game_end_stamp') and self.game_end_stamp:
                    result_display_time = self.game_end_stamp
                else:
                    result_display_time = time.time()

            if result_display_time:
                elapsed = time.time() - result_display_time
                if elapsed > 10.0:
                    print("\n[Game] Auto-closing game window...")
                    print("input enter to continue...")
                    self.running = False
                        
            if self.game_started and not self.game_ended:
                if not self.spectator:                      # player mode
                    keys = pygame.key.get_pressed()
                    
                    current_time = pygame.time.get_ticks()
                    if not hasattr(self, 'last_input_time'):
                        self.last_input_time = 0
                    if current_time - self.last_input_time < 150:
                        pass
                    elif keys[pygame.K_LEFT]:               # move block left
                        self.send_input('LEFT')
                        self.last_input_time = current_time
                    elif keys[pygame.K_RIGHT]:              # move block right
                        self.send_input('RIGHT')
                        self.last_input_time = current_time
                    elif keys[pygame.K_UP]:
                        self.send_input('CW')               # rotate block clockwise
                        self.last_input_time = current_time
                    elif keys[pygame.K_n]:
                        self.send_input('CCW')              # rotate block counter-clockwise
                        self.last_input_time = current_time
                    elif keys[pygame.K_DOWN]:
                        self.send_input('SOFT_DROP')        # soft drop
                        self.last_input_time = current_time
                    elif keys[pygame.K_b]:
                        self.send_input('HARD_DROP')        # hard drop
                        self.last_input_time = current_time
                    elif keys[pygame.K_SPACE]:
                        self.send_input('HOLD')             # hold piece
                        self.last_input_time = current_time
                    
            self.screen.fill(BACKGROUND_COLOR)              # clear the screen
            
            dt = self.clock.get_time() / 1000.0
            self.firework_manager.update(dt)
            
            if self.connecting:
                text = "Connecting to game server..."
                surface = self.large_font.render(text, True, TEXT_COLOR)
                rect = surface.get_rect(center=(self.screen.get_width() // 2, self.screen.get_height() // 2))
                self.screen.blit(surface, rect)
            elif not self.connected:
                text = "Connection failed. Press ESC to exit."
                surface = self.large_font.render(text, True, (255, 0, 0))
                rect = surface.get_rect(center=(self.screen.get_width() // 2, self.screen.get_height() // 2))
                self.screen.blit(surface, rect)
            else:
                # Normal game rendering (only when connected)
                with self.lock:                
                    if self.my_state and self.opponent_state:
                        if self.spectator:                      # spectator mode: two equal sized boards
                            board_spacing = 50
                            total_width = self.board_width * self.cell_size * 2 + board_spacing
                            start_x = (self.screen.get_width() - total_width) // 2                        
                            self.draw_board(                    # draw Player 1 board
                                self.my_state['board'],
                                start_x,
                                50,
                                self.my_state.get('currentPiece'),
                                self.cell_size
                            )

                            player2_x = start_x + self.board_width * self.cell_size + board_spacing
                            self.draw_board(                    # draw Player 2 board
                                self.opponent_state['board'],
                                player2_x,
                                50,
                                self.opponent_state.get('currentPiece'),
                                self.cell_size
                            )
                            self.draw_info(self.my_state, start_x, 50 + self.board_height * self.cell_size + 10, "P1")
                            self.draw_info(self.opponent_state, player2_x, 50 + self.board_height * self.cell_size + 10, "P2")
                        else:                                # player mode: own board large, opponent board small
                            center_x = (self.screen.get_width() - self.board_width * self.cell_size) // 2
                            self.draw_board(
                                self.my_state['board'],
                                center_x,
                                50,
                                self.my_state.get('currentPiece'),
                                self.cell_size
                            )
                            
                            small_cell_size = int(self.cell_size * 0.4)             # opponent board smaller(0.4x)
                            opponent_x = center_x + self.board_width * self.cell_size + 20
                            opponent_y = 50
                            self.draw_board(
                                self.opponent_state['board'],
                                opponent_x,
                                opponent_y,
                                self.opponent_state.get('currentPiece'),
                                small_cell_size
                            )
                            self.cleared_lines(center_x, 50)
                            # draw information of the two players
                            self.draw_info(self.my_state, center_x - self.board_width * self.cell_size + 100, 50, f"YOU: {self.role.upper()}")
                            if self.role == 'P1':
                                self.opponent_role = 'P2'
                            else:
                                self.opponent_role = 'P1'
                            self.draw_info(self.opponent_state, opponent_x + self.board_height * small_cell_size - 50, opponent_y, f"OPPONENT: {self.opponent_role.upper()}")

                    elif not self.game_started:         # waiting for game to start
                        text = "Waiting for game to start..."
                        surface = self.large_font.render(text, True, TEXT_COLOR)
                        rect = surface.get_rect(center=(self.screen.get_width() // 2, self.screen.get_height() // 2))
                        self.screen.blit(surface, rect)
            
            # Only draw game UI elements when connected
            if self.connected:
                if self.game_ended and self.results:
                    if 10.0 - (time.time() - result_display_time) == 0:
                        self.closed = True
                    time_left = 10.0 - (time.time() - result_display_time) if result_display_time else None
                    self.draw_results(time_left)

                self.firework_manager.draw(self.screen)         # draw fireworks
                self.draw_timer()
                self.draw_controls()
            
            pygame.display.flip()               # update the full display
            self.clock.tick(100)                # limit to 100 FPS   
            
        if self.socket:
            self.socket.close()
        pygame.quit()

###### game part end ######

def main():
    host = sys.argv[1]
    port = int(sys.argv[2])
    user_id = sys.argv[3]
    room_id = sys.argv[4]
    spectator = False
    if len(sys.argv) >= 6 and sys.argv[5].lower() == 'spectator':
        spectator = True
    client = gameClient(host, port, user_id, room_id, spectator)
    client.run()

if __name__ == '__main__':
    main()
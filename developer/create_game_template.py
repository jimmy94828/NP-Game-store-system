#!/usr/bin/env python3
"""
Create Game Template Script
"""
import os
import sys
import shutil
import json
import re

TEMPLATE_DIR = os.path.join(os.path.dirname(__file__), 'template')
GAMES_DIR = os.path.join(os.path.dirname(__file__), 'games')

def sanitize_folder_name(name):                 # sanitize folder name
    safe = re.sub(r'[^A-Za-z0-9 _\-]', '', name)    # Remove special characters, keep alphanumeric, spaces, dashes, underscores
    safe = safe.strip().replace(' ', '_')           # Replace spaces with underscores
    safe = safe.lower()
    if not safe:
        safe = 'my_game'
    return safe

def get_input(prompt, default=None, required=True):     # get user input with default and required option
    if default:
        prompt_text = f"{prompt} [{default}]: "
    else:
        prompt_text = f"{prompt}: "
    
    while True:
        value = input(prompt_text).strip()
        if not value and default:
            return default
        
        if not value and required:
            print("This field is required. Please enter a value.")
            continue
        
        return value

def get_int_input(prompt, default=None):
    while True:
        value = get_input(prompt, default, required=True)
        try:
            return int(value)
        except ValueError:
            print("Please enter a valid number.")

def main():
    print("="*60)
    print("Create New Game from Template")
    print()
    
    if not os.path.exists(TEMPLATE_DIR):                # check if template directory exists
        print(f"Error: Template directory not found at {TEMPLATE_DIR}")
        sys.exit(1)
    
    if len(sys.argv) > 1:                               # get username from command line argument  
        username = sys.argv[1]
    else:
        username = os.environ.get('USER', 'default')
    
    user_games_dir = os.path.join(GAMES_DIR, username)
    
    os.makedirs(user_games_dir, exist_ok=True)          # create user games directory if not exists
    print(f"Games will be created in: {user_games_dir}")
    print()
    print("  Game Configuration")                       # ask developer to input game details
    game_name = get_input("Game Name", "My Game")
    game_version = get_input("Version", "1.0.0")
    game_type = get_input("Game Type (GUI/CLI)", "GUI")
    max_players = get_int_input("Maximum Players", "2")
    description = get_input("Description", "A new game for the platform")
    
    folder_name = sanitize_folder_name(game_name)       # sanitize folder name
    game_dir = os.path.join(user_games_dir, folder_name)
    
    if os.path.exists(game_dir):                        # check if game directory already exists
        print(f"\nWarning: A game folder '{folder_name}' already exists.")
        overwrite = get_input("Overwrite existing folder? (yes/no)", "no", required=True)
        if overwrite.lower() not in ['yes', 'y']:
            print("\nOperation cancelled.")
            sys.exit(0)
        shutil.rmtree(game_dir)
    
    print(f"\nCreating game project: {folder_name}")    # create game directory
    os.makedirs(game_dir, exist_ok=True)
    
    print("Copying template files...")                  # copy template files to game directory
    for item in os.listdir(TEMPLATE_DIR):
        src = os.path.join(TEMPLATE_DIR, item)
        dst = os.path.join(game_dir, item)
        
        if os.path.isfile(src):
            shutil.copy2(src, dst)
            print(f"{item}")
    
    config_path = os.path.join(game_dir, 'config.json') # create config.json file
    config = {
        "name": game_name,
        "version": game_version,
        "gameType": game_type,
        "maxPlayers": max_players,
        "description": description,
        "mainFile": "game_client.py",
        "serverFile": "game_server.py"
    }
    
    with open(config_path, 'w', encoding='utf-8') as f:
        json.dump(config, f, indent=2, ensure_ascii=False)
    print(f"config.json configured")

    print("  Game Project Created Successfully!")
    print(f"Location: {game_dir}")
    print()
    print("Documentation:")
    print(f"  - Read README.md in the game folder for detailed guide")

if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nOperation cancelled by user")
        sys.exit(1)
    except Exception as e:
        print(f"\nError: {e}")
        sys.exit(1)

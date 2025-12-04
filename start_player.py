#!/usr/bin/env python3
"""launch player client.
Usage: start_player.py [PLAYER_NAME] [HOST] [PORT]
"""
import os
import sys

ROOT = os.path.dirname(__file__)
PLAYER_CLIENT = os.path.join(ROOT, 'player', 'lobby_client.py')

# start format : python3 start_player.py [PLAYER_NAME] [HOST] [PORT]
if __name__ == '__main__':
    player = sys.argv[1] if len(sys.argv) > 1 else 'weichen'
    host = sys.argv[2] if len(sys.argv) > 2 else '140.113.17.11'
    port = sys.argv[3] if len(sys.argv) > 3 else '17048'
    os.execvp('python3', ['python3', PLAYER_CLIENT, host, port, player])

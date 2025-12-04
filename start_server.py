#!/usr/bin/env python3
"""
Start all servers (database, lobby, developer).
"""
import os
import sys
import time
import threading
import signal

ROOT = os.path.dirname(__file__)
sys.path.insert(0, os.path.join(ROOT, 'server'))
from server.database_server import DatabaseServer, DATABASE_SERVER_HOST, DATABASE_SERVER_PORT
from server.lobby_server import LobbyServer, LOBBYSERVER_HOST, LOBBYSERVER_PORT
from server.developer_server import DeveloperServer, DEVELOPER_SERVER_HOST, DEVELOPER_SERVER_PORT

def main():
    database_server = DatabaseServer(host=DATABASE_SERVER_HOST, port=DATABASE_SERVER_PORT)
    database_thread = threading.Thread(target=database_server.start, daemon=True)
    database_thread.start()

    time.sleep(1)

    lobby_server = LobbyServer(host=LOBBYSERVER_HOST, port=LOBBYSERVER_PORT, database_host=DATABASE_SERVER_HOST, database_port=DATABASE_SERVER_PORT)
    lobby_thread = threading.Thread(target=lobby_server.start, daemon=True)
    lobby_thread.start()

    time.sleep(1)

    developer_server = DeveloperServer(host=DEVELOPER_SERVER_HOST, port=DEVELOPER_SERVER_PORT, db_host=DATABASE_SERVER_HOST, db_port=DATABASE_SERVER_PORT)
    developer_thread = threading.Thread(target=developer_server.start, daemon=True)
    developer_thread.start()

    time.sleep(1)
    print("==============================")
    print("  servers start successfully  ")
    print("==============================")
    print(f"Database Server: Port {DATABASE_SERVER_PORT}")
    print(f"Lobby Server:    Port {LOBBYSERVER_PORT}")
    print(f"Developer Server: Port {DEVELOPER_SERVER_PORT}")
    print("==============================")
    print("\nPress Ctrl+C to stop all servers...")

    def shutdown(signum, frame):
        print('\n\nShutting down servers...')
        try:
            lobby_server.cleanup()
        except Exception:
            pass
        try:
            database_server.cleanup()
        except Exception:
            pass
        try:
            developer_server.cleanup()
        except Exception:
            pass
        database_server.running = False
        lobby_server.running = False
        try:
            developer_server.running = False
        except Exception:
            pass
        print('Servers stopped. Exiting...')
        sys.exit(0)

    signal.signal(signal.SIGINT, shutdown)
    signal.pause()


if __name__ == '__main__':
    main()

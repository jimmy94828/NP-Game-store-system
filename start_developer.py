#!/usr/bin/env python3
"""launch developer client connecting to remote developer server"""
import os
import sys
import subprocess

ROOT = os.path.dirname(__file__)
DEV_CLIENT = os.path.join(ROOT, 'developer', 'developer_client.py')

if __name__ == '__main__':
    host = sys.argv[1] if len(sys.argv) > 1 else '140.113.17.11'
    port = sys.argv[2] if len(sys.argv) > 2 else '17049'
    os.execvp('python3', ['python3', DEV_CLIENT, host, port])

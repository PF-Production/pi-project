#!/usr/bin/env python3
"""
Remote control client for Pi Project.
Connects to the running main.py service via TCP.
"""

import argparse
import os
import socket
import sys

from dotenv import load_dotenv

# Load environment variables
load_dotenv(".env.local")


def handle_command_loop(sock):
    """Handle the interactive command loop with the remote server."""
    buffer = ""
    while True:
        try:
            cmd = input("> ").strip()
            if not cmd:
                continue
            if cmd.lower() in ("exit", "quit"):
                break
            if cmd.lower() == "help":
                print(
                    "Commands: status, play (start playback now), stop (stop playback now), "
                    "centre <val>, sub <val>, stereo <val>, save"
                )
                continue

            # Send command
            sock.sendall((cmd + "\n").encode("utf-8"))

            # Read response until we get a newline
            while "\n" not in buffer:
                chunk = sock.recv(1024).decode("utf-8")
                if not chunk:
                    raise ConnectionError("Server closed connection")
                buffer += chunk

            # Extract the response line
            if "\n" in buffer:
                response, buffer = buffer.split("\n", 1)
                print(response.strip())

        except KeyboardInterrupt:
            break
        except Exception as e:
            print(f"Error: {e}")
            break


def main():
    parser = argparse.ArgumentParser(description="Remote control for Pi Project")
    parser.add_argument("host", nargs="?", default="localhost", help="Hostname or IP of the Pi")
    parser.add_argument("--port", type=int, help="Remote port (defaults to REMOTE_PORT in .env.local or 5000)")
    args = parser.parse_args()

    port = args.port or int(os.getenv("REMOTE_PORT", "5000"))

    if port == 0:
        print("Error: Remote port is not configured (0).")
        print("Run 'just config' to set a remote port.")
        sys.exit(1)

    print(f"Connecting to {args.host}:{port}...")

    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.connect((args.host, port))
        sock.settimeout(5.0)
    except Exception as e:
        print(f"Failed to connect: {e}")
        sys.exit(1)

    print("Connected! Type 'help' for commands, 'exit' to quit.")

    with sock:
        handle_command_loop(sock)


if __name__ == "__main__":
    main()

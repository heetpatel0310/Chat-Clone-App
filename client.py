import os
import select
import socket
import sys
import termios
import tty


def init_client():
    # Default hostname and port
    default_host = "hawk.cs.umanitoba.ca"
    default_port = 8635

    # Parse command-line arguments
    if len(sys.argv) >= 2:
        host = sys.argv[1]
    else:
        host = default_host

    if len(sys.argv) >= 3:
        try:
            port = int(sys.argv[2])
        except ValueError:
            print("Invalid port number. Using default port.")
            port = default_port
    else:
        port = default_port

    clientsocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        clientsocket.connect((host, port))
    except ConnectionRefusedError:
        print(f"Could not connect to server {host}:{port}")
        return
    clientsocket.setblocking(False)

    username = None
    input_buffer = ""
    recv_buffer = b""

    # Save the terminal settings
    original_settings = termios.tcgetattr(sys.stdin)

    try:
        # Set terminal to cbreak mode
        tty.setcbreak(sys.stdin.fileno())

        inputs = [clientsocket, sys.stdin]

        while True:
            readable, _, _ = select.select(inputs, [], [])

            for s in readable:
                if s == clientsocket:
                    data = clientsocket.recv(4096)
                    if data:
                        recv_buffer += data
                        while b"\n" in recv_buffer:
                            line, recv_buffer = recv_buffer.split(b"\n", 1)
                            message = line.decode("utf-8")
                            # Clear current line
                            sys.stdout.write("\r")
                            sys.stdout.flush()
                            # Determine the prompt length
                            if username is None:
                                prompt_length = len(input_buffer)
                            else:
                                prompt_length = len(f"{username}: ") + len(input_buffer)
                            # Clear the line
                            sys.stdout.write(" " * (prompt_length + 10))
                            sys.stdout.write("\r")
                            sys.stdout.flush()
                            # Print the incoming message
                            print(message)
                            # Reprint prompt and input buffer only if username is set
                            if username is not None:
                                prompt = f"{username}: "
                                sys.stdout.write(prompt + input_buffer)
                                sys.stdout.flush()
                    else:
                        print("\nServer closed the connection. Goodbye.")
                        return
                elif s == sys.stdin:
                    char = os.read(sys.stdin.fileno(), 1).decode(
                        "utf-8", errors="replace"
                    )
                    if char == "\n":
                        message = input_buffer.strip()
                        if message:
                            if username is None:
                                username = message
                                clientsocket.sendall((username + "\n").encode("utf-8"))
                            else:
                                clientsocket.sendall((message + "\n").encode("utf-8"))
                                if message.lower() == "quit":
                                    print("\nExiting chat. Goodbye.")
                                    return
                        input_buffer = ""
                        sys.stdout.write("\n")
                        if username is not None:
                            prompt = f"{username}: "
                            sys.stdout.write(prompt)
                            sys.stdout.flush()
                    elif char == "\x7f":  # Backspace
                        if len(input_buffer) > 0:
                            input_buffer = input_buffer[:-1]
                            # Move cursor back, overwrite character with space, move cursor back
                            sys.stdout.write("\b \b")
                            sys.stdout.flush()
                    else:
                        input_buffer += char
                        sys.stdout.write(char)
                        sys.stdout.flush()
    except KeyboardInterrupt:
        print("\nExiting chat. Goodbye.")
    except Exception as e:
        print(f"\nError: {e}")
    finally:
        # Restore terminal settings
        termios.tcsetattr(sys.stdin, termios.TCSADRAIN, original_settings)
        clientsocket.close()


if __name__ == "__main__":
    init_client()

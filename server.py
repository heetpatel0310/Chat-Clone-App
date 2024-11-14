import json
import select
import socket
import sqlite3
import threading
import time

# Server configuration
SERVER_HOST = "hawk.cs.umanitoba.ca"
SERVER_PORT = 8635
CONNECTION_BACKLOG = 5
MAX_BUFFER_SIZE = 1024

# List to keep track of connected clients
active_clients = []
clients_lock = threading.Lock()


def initialize_database():
    connection = sqlite3.connect("chat_database.db", check_same_thread=False)
    cursor = connection.cursor()
    # Create messages table if it doesn't exist
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT,
            message TEXT
        )
    """
    )
    connection.commit()
    return connection


def client_connection_handler(client_socket, client_address, db_connection):
    username = None
    try:
        client_socket.setblocking(False)
        client_socket.sendall(b"Enter your username:\n")
        username = receive_username_line(client_socket)
        if username is None:
            print(
                f"Client {client_address[0]}:{client_address[1]} disconnected before sending username."
            )
            return

        if username == "__WebClient__":
            print(f"New web client connected {client_address}")
            print("Waiting for input")
            handle_web_client_commands(client_socket, db_connection, client_address)
            return

        print(
            f"User '{username}' connected from {client_address[0]}:{client_address[1]}"
        )
        message_buffer = b""

        # Add client to active_clients list
        with clients_lock:
            active_clients.append({"socket": client_socket, "username": username})

        # Send all messages to client
        messages = retrieve_all_messages(db_connection)
        if messages:
            for msg in messages:
                message_line = f"{msg['username']}: {msg['message']}\n"
                try:
                    client_socket.sendall(message_line.encode("utf-8"))
                except (ConnectionResetError, OSError):
                    print(
                        f"Client {client_address[0]}:{client_address[1]} disconnected during message sending."
                    )
                    return
        while True:
            ready = select.select([client_socket], [], [], 0.1)
            if ready[0]:
                try:
                    data = client_socket.recv(MAX_BUFFER_SIZE)
                    if not data:
                        break
                    message_buffer += data
                    while b"\n" in message_buffer:
                        message_line, message_buffer = message_buffer.split(b"\n", 1)
                        message = message_line.decode("utf-8").strip()
                        if message.lower() == "quit":
                            print(f"User '{username}' disconnected.")
                            return
                        store_message(db_connection, username, message)
                        distribute_message(
                            db_connection, sender_username=username, message=message
                        )
                except (ConnectionResetError, OSError):
                    print(
                        f"Client {client_address[0]}:{client_address[1]} disconnected."
                    )
                    break
            else:
                continue
    except Exception as e:
        print(f"Error handling client {client_address[0]}:{client_address[1]}: {e}")
    finally:
        # Remove client from active_clients list
        with clients_lock:
            active_clients[:] = [
                client for client in active_clients if client["socket"] != client_socket
            ]
        client_socket.close()
        if username and username != "__WebClient__":
            print(f"{username} disconnected")


def handle_web_client_commands(client_socket, db_connection, client_address):
    try:
        client_socket.setblocking(False)
        message_buffer = b""
        while True:
            ready = select.select([client_socket], [], [], 0.1)
            if ready[0]:
                data = client_socket.recv(MAX_BUFFER_SIZE)
                if not data:
                    break
                message_buffer += data
                while b"\n" in message_buffer:
                    command_line, message_buffer = message_buffer.split(b"\n", 1)
                    command = command_line.decode("utf-8").strip()
                    if command.startswith("GET_MESSAGES"):
                        parts = command.split()
                        if len(parts) == 2:
                            _, last_id_str = parts
                            try:
                                last_id = int(last_id_str)
                            except ValueError:
                                client_socket.sendall(b"INVALID_COMMAND\n")
                                return
                            messages = get_messages_since_id(db_connection, last_id)
                            client_socket.sendall(json.dumps(messages).encode("utf-8"))
                        else:
                            client_socket.sendall(b"INVALID_COMMAND\n")
                        return  # Close connection after handling the command
                    elif command.startswith("DELETE_MESSAGE"):
                        parts = command.split()
                        if len(parts) == 3:
                            _, message_id_str, req_username = parts
                            try:
                                message_id = int(message_id_str)
                            except ValueError:
                                client_socket.sendall(b"INVALID_COMMAND\n")
                                return
                            success = remove_message(
                                db_connection, message_id, req_username
                            )
                            if success:
                                client_socket.sendall(b"SUCCESS\n")
                            else:
                                client_socket.sendall(b"FAIL\n")
                        else:
                            client_socket.sendall(b"INVALID_COMMAND\n")
                        return
                    elif command.startswith("SEND_MESSAGE"):
                        parts = command.split(" ", 2)
                        if len(parts) == 3:
                            _, sender_username, message = parts
                            store_message(db_connection, sender_username, message)
                            distribute_message(
                                db_connection,
                                sender_username=sender_username,
                                message=message,
                            )
                            client_socket.sendall(b"SUCCESS\n")
                        else:
                            client_socket.sendall(b"INVALID_COMMAND\n")
                        return
                    else:
                        client_socket.sendall(b"INVALID_COMMAND\n")
                        return
            else:
                continue
    except Exception as e:
        print(f"Error handling web client {client_address[0]}:{client_address[1]}: {e}")
    finally:
        client_socket.close()


def receive_username_line(sock):
    data = b""
    sock.settimeout(5)  # Set a timeout to prevent blocking indefinitely
    try:
        while True:
            chunk = sock.recv(1)
            if not chunk:
                return None
            data += chunk
            if chunk == b"\n":
                return data.decode("utf-8").strip()
    except socket.timeout:
        return None
    except Exception as e:
        print(f"Error receiving username line: {e}")
        return None


def store_message(db_connection, username, message):
    cursor = db_connection.cursor()
    cursor.execute(
        "INSERT INTO messages (username, message) VALUES (?, ?)", (username, message)
    )
    db_connection.commit()
    print(f"Message from '{username}': {message}")


def remove_message(db_connection, message_id, requesting_username):
    cursor = db_connection.cursor()
    cursor.execute("SELECT username FROM messages WHERE id = ?", (message_id,))
    result = cursor.fetchone()
    if result and result[0] == requesting_username:
        cursor.execute("DELETE FROM messages WHERE id = ?", (message_id,))
        db_connection.commit()
        print(f"Message {message_id} deleted by '{requesting_username}'")
        return True
    else:
        return False


def distribute_message(db_connection, sender_username, message):
    with clients_lock:
        clients_copy = active_clients.copy()
    for client in clients_copy:
        if client["username"] != sender_username:
            try:
                message_line = f"{sender_username}: {message}\n"
                client["socket"].sendall(message_line.encode("utf-8"))
            except Exception as e:
                print(f"Error sending message to {client['username']}: {e}")
                with clients_lock:
                    if client in active_clients:
                        client["socket"].close()
                        active_clients.remove(client)


def get_messages_since_id(db_connection, last_id):
    cursor = db_connection.cursor()
    cursor.execute(
        "SELECT id, username, message FROM messages WHERE id > ? ORDER BY id",
        (last_id,),
    )
    rows = cursor.fetchall()
    messages = [{"id": row[0], "username": row[1], "message": row[2]} for row in rows]
    return messages


def retrieve_all_messages(db_connection):
    cursor = db_connection.cursor()
    cursor.execute("SELECT id, username, message FROM messages ORDER BY id")
    rows = cursor.fetchall()
    messages = [{"id": row[0], "username": row[1], "message": row[2]} for row in rows]
    return messages


def main():
    db_connection = initialize_database()

    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.bind((SERVER_HOST, SERVER_PORT))
    server_socket.listen(CONNECTION_BACKLOG)
    print(f"Chat server listening on {SERVER_HOST}:{SERVER_PORT}")

    try:
        while True:
            client_socket, client_address = server_socket.accept()
            client_thread = threading.Thread(
                target=client_connection_handler,
                args=(client_socket, client_address, db_connection),
                daemon=True,
            )
            client_thread.start()
    except KeyboardInterrupt:
        print("Shutting down chat server.")
    finally:
        server_socket.close()
        db_connection.close()


if __name__ == "__main__":
    main()

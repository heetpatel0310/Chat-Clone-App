import json
import os
import re
import select
import socket
import sys
import threading
import time
import uuid

# Web server configuration
WEB_SERVER_HOST = ""
WEB_SERVER_PORT = 8636

# Chat server configuration
CHAT_SERVER_HOST = "hawk.cs.umanitoba.ca"
CHAT_SERVER_PORT = 8635

user_sessions = {}
session_lock = threading.Lock()


def main():
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        server_socket.bind((WEB_SERVER_HOST, WEB_SERVER_PORT))
    except socket.error as e:
        print(f"Failed to bind server on port {WEB_SERVER_PORT}: {e}")
        sys.exit(1)
    server_socket.listen(5)
    print(f"Web server started on port {WEB_SERVER_PORT}")

    try:
        while True:
            client_socket, client_address = server_socket.accept()
            client_thread = threading.Thread(
                target=handle_http_client, args=(client_socket,), daemon=True
            )
            client_thread.start()
    except KeyboardInterrupt:
        print("\nShutting down web server. Goodbye.")
    finally:
        server_socket.close()
        sys.exit(0)


def handle_http_client(client_socket):
    try:
        request_data = read_http_request(client_socket)
        if not request_data:
            client_socket.close()
            return
        try:
            method, path, version, headers, body = parse_http_request(request_data)
        except ValueError as ve:
            response = "HTTP/1.1 400 Bad Request\r\n"
            response += "Content-Type: text/plain\r\n"
            response += "Content-Length: 11\r\n"
            response += "\r\n"
            response += "Bad Request"
            try:
                client_socket.sendall(response.encode("utf-8"))
            except socket.error as se:
                print(f"Failed to send response: {se}")
            print(f"Error handling HTTP client: {ve}")
            return
        response = process_http_request(method, path, headers, body)
        if isinstance(response, bytes):
            client_socket.sendall(response)
        else:
            client_socket.sendall(response.encode("utf-8"))
    except Exception as e:
        print(f"Error handling HTTP client: {e}")
    finally:
        client_socket.close()


def read_http_request(client_socket):
    request_data = b""
    client_socket.settimeout(1.0)
    try:
        while True:
            data = client_socket.recv(4096)
            if not data:
                break
            request_data += data
            if b"\r\n\r\n" in request_data:
                headers_end = request_data.find(b"\r\n\r\n") + 4
                headers = request_data[:headers_end].decode("utf-8", errors="replace")
                match = re.search(r"Content-Length:\s*(\d+)", headers, re.IGNORECASE)
                if match:
                    content_length = int(match.group(1))
                    total_length = headers_end + content_length
                    while len(request_data) < total_length:
                        data = client_socket.recv(4096)
                        if not data:
                            break
                        request_data += data
                break
    except socket.timeout:
        pass
    except Exception as e:
        print(f"Error reading HTTP request: {e}")
    return request_data


def parse_http_request(request_data):
    request_text = request_data.decode("utf-8", errors="replace")
    lines = request_text.split("\r\n")

    if not lines:
        raise ValueError("Empty request received")

    request_line = lines[0]
    print(f"Received request line: '{request_line}'")

    try:
        method, path, version = request_line.split()
    except ValueError:
        raise ValueError("Malformed request line")

    headers = {"Path": path}
    i = 1
    while i < len(lines) and lines[i]:
        header_line = lines[i]
        if ":" in header_line:
            key, value = header_line.split(":", 1)
            headers[key.strip()] = value.strip()
        i += 1
    i += 1
    body = "\r\n".join(lines[i:])
    return method, path, version, headers, body


def process_http_request(method, path, headers, body):
    if path == "/":
        if method == "GET":
            return serve_static_file("index.html", headers)
        else:
            return method_not_allowed()
    elif path.startswith("/api/"):
        return handle_api_request(method, path, headers, body)
    else:
        if method != "GET":
            return method_not_allowed()
        sanitized_path = os.path.normpath(path)
        sanitized_path = sanitized_path.lstrip("/")
        if ".." in sanitized_path:
            response = "HTTP/1.1 403 Forbidden\r\n"
            response += "Content-Type: text/plain\r\n"
            response += "Content-Length: 9\r\n"
            response += "\r\n"
            response += "Forbidden"
            return response
        file_path = os.path.join(".", sanitized_path)
        print(f"Requested file: {file_path}")
        if os.path.isfile(file_path):
            return serve_static_file(file_path, headers)
        else:
            response = "HTTP/1.1 404 Not Found\r\n"
            response += "Content-Type: text/plain\r\n"
            response += "Content-Length: 13\r\n"
            response += "\r\n"
            response += "404 Not Found"
            return response


def method_not_allowed():
    response = "HTTP/1.1 405 Method Not Allowed\r\n"
    response += "Content-Type: text/plain\r\n"
    response += "Content-Length: 18\r\n"
    response += "\r\n"
    response += "Method Not Allowed"
    return response


def serve_static_file(file_path, headers):
    try:
        with open(file_path, "rb") as f:
            content = f.read()

        # Determine the content type based on file extension
        if file_path.endswith(".html"):
            content_type = "text/html"
        elif file_path.endswith(".css"):
            content_type = "text/css"
        elif file_path.endswith(".js"):
            content_type = "application/javascript"
        elif file_path.endswith(".png"):
            content_type = "image/png"
        elif file_path.endswith(".jpg") or file_path.endswith(".jpeg"):
            content_type = "image/jpeg"
        elif file_path.endswith(".gif"):
            content_type = "image/gif"
        elif file_path.endswith(".ico"):
            content_type = "image/x-icon"
        else:
            content_type = "application/octet-stream"

        response = "HTTP/1.1 200 OK\r\n"
        response += f"Content-Type: {content_type}\r\n"
        response += f"Content-Length: {len(content)}\r\n"
        response += "\r\n"
        response = response.encode("utf-8") + content
        return response
    except Exception as e:
        print(f"Error serving file {file_path}: {e}")
        response = "HTTP/1.1 500 Internal Server Error\r\n"
        response += "Content-Type: text/plain\r\n"
        response += "Content-Length: 21\r\n"
        response += "\r\n"
        response += "Internal Server Error"
        return response


def handle_api_request(method, path, headers, body):
    if path == "/api/login" and method == "POST":
        return api_user_login(headers, body)
    elif path == "/api/login" and method == "DELETE":
        return api_user_logout(headers)
    elif path == "/api/login" and method == "GET":
        return api_check_user_login(headers)
    elif path.startswith("/api/messages") and method == "GET":
        return api_retrieve_messages(headers)
    elif path == "/api/messages" and method == "POST":
        return api_send_message(headers, body)
    elif path.startswith("/api/messages/") and method == "DELETE":
        return api_remove_message(method, path, headers)
    else:
        response = "HTTP/1.1 404 Not Found\r\n"
        response += "Content-Type: text/plain\r\n"
        response += "Content-Length: 13\r\n"
        response += "\r\n"
        response += "404 Not Found"
        return response


def parse_cookie_header(cookie_header):
    cookies = {}
    if not cookie_header:
        return cookies
    cookie_pairs = cookie_header.split(";")
    for pair in cookie_pairs:
        if "=" in pair:
            key, value = pair.strip().split("=", 1)
            cookies[key] = value
    return cookies


def api_user_login(headers, body):
    try:
        data = json.loads(body)
        username = data.get("username")
        if not username:
            raise ValueError("No username provided")
        session_id = str(uuid.uuid4())
        with session_lock:
            user_sessions[session_id] = username
        response = "HTTP/1.1 200 OK\r\n"
        response += (
            f"Set-Cookie: session_id={session_id}; Path=/; Max-Age=86400; HttpOnly\r\n"
        )
        response += "Content-Type: application/json\r\n"
        response += "Content-Length: 2\r\n"
        response += "\r\n"
        response += "{}"
        return response
    except Exception as e:
        print(f"Error in api_user_login: {e}")
        response = "HTTP/1.1 400 Bad Request\r\n"
        response += "Content-Type: application/json\r\n"
        response += "Content-Length: 2\r\n"
        response += "\r\n"
        response += "{}"
        return response


def api_user_logout(headers):
    cookies = parse_cookie_header(headers.get("Cookie", ""))
    session_id = cookies.get("session_id")
    with session_lock:
        if session_id and session_id in user_sessions:
            del user_sessions[session_id]
    response = "HTTP/1.1 200 OK\r\n"
    response += "Set-Cookie: session_id=; Path=/; Max-Age=0; HttpOnly\r\n"
    response += "Content-Type: application/json\r\n"
    response += "Content-Length: 2\r\n"
    response += "\r\n"
    response += "{}"
    return response


def api_check_user_login(headers):
    cookies = parse_cookie_header(headers.get("Cookie", ""))
    session_id = cookies.get("session_id")
    with session_lock:
        if session_id and session_id in user_sessions:
            username = user_sessions[session_id]
            response_body = json.dumps({"username": username})
            response = "HTTP/1.1 200 OK\r\n"
            response += "Content-Type: application/json\r\n"
            response += f"Content-Length: {len(response_body)}\r\n"
            response += "\r\n"
            response += response_body
        else:
            response_body = json.dumps({})
            response = "HTTP/1.1 401 Unauthorized\r\n"
            response += "Content-Type: application/json\r\n"
            response += f"Content-Length: {len(response_body)}\r\n"
            response += "\r\n"
            response += response_body
    return response


def api_retrieve_messages(headers):
    cookies = parse_cookie_header(headers.get("Cookie", ""))
    session_id = cookies.get("session_id")
    with session_lock:
        if not session_id or session_id not in user_sessions:
            response = "HTTP/1.1 401 Unauthorized\r\n"
            response += "Content-Type: application/json\r\n"
            response += "Content-Length: 2\r\n"
            response += "\r\n"
            response += "{}"
            return response
        username = user_sessions[session_id]

    path = headers.get("Path", "")
    match = re.search(r"\?last=(\d+)", path)
    if match:
        last_id = int(match.group(1))
    else:
        last_id = 0

    messages = fetch_messages_from_chat_server(last_id)
    if messages is None:
        # Chat server is unavailable
        response_body = json.dumps({"error": "Chat server is unavailable."})
        response = "HTTP/1.1 503 Service Unavailable\r\n"
        response += "Content-Type: application/json\r\n"
        response += f"Content-Length: {len(response_body)}\r\n"
        response += "\r\n"
        response += response_body
        return response

    messages_json = json.dumps(messages)
    response = "HTTP/1.1 200 OK\r\n"
    response += "Content-Type: application/json\r\n"
    response += f"Content-Length: {len(messages_json)}\r\n"
    response += "\r\n"
    response += messages_json
    return response


def api_send_message(headers, body):
    cookies = parse_cookie_header(headers.get("Cookie", ""))
    session_id = cookies.get("session_id")
    with session_lock:
        if not session_id or session_id not in user_sessions:
            response = "HTTP/1.1 401 Unauthorized\r\n"
            response += "Content-Type: application/json\r\n"
            response += "Content-Length: 2\r\n"
            response += "\r\n"
            response += "{}"
            return response
        username = user_sessions[session_id]
    try:
        data = json.loads(body)
        message = data.get("message")
        if not message:
            raise ValueError("No message provided")
        success = send_message_to_chat_server(username, message)
        if success:
            response = "HTTP/1.1 200 OK\r\n"
            response += "Content-Type: application/json\r\n"
            response += "Content-Length: 2\r\n"
            response += "\r\n"
            response += "{}"
        else:
            # Sending message failed
            response_body = json.dumps(
                {"error": "Failed to send message to chat server."}
            )
            response = "HTTP/1.1 503 Service Unavailable\r\n"
            response += "Content-Type: application/json\r\n"
            response += f"Content-Length: {len(response_body)}\r\n"
            response += "\r\n"
            response += response_body
        return response
    except Exception as e:
        print(f"Error in api_send_message: {e}")
        response = "HTTP/1.1 400 Bad Request\r\n"
        response += "Content-Type: application/json\r\n"
        response += "Content-Length: 2\r\n"
        response += "\r\n"
        response += "{}"
        return response


def api_remove_message(method, path, headers):
    # Extract message ID from the path
    match = re.match(r"/api/messages/(\d+)", path)
    if not match:
        response = "HTTP/1.1 400 Bad Request\r\n"
        response += "Content-Type: application/json\r\n"
        response += "Content-Length: 2\r\n"
        response += "\r\n"
        response += "{}"
        return response

    message_id = int(match.group(1))

    cookies = parse_cookie_header(headers.get("Cookie", ""))
    session_id = cookies.get("session_id")
    with session_lock:
        if not session_id or session_id not in user_sessions:
            response = "HTTP/1.1 401 Unauthorized\r\n"
            response += "Content-Type: application/json\r\n"
            response += "Content-Length: 2\r\n"
            response += "\r\n"
            response += "{}"
            return response
        username = user_sessions[session_id]

    # Send delete request to the chat server
    success = delete_message_on_chat_server(username, message_id)
    if success:
        response = "HTTP/1.1 200 OK\r\n"
        response += "Content-Type: application/json\r\n"
        response += "Content-Length: 2\r\n"
        response += "\r\n"
        response += "{}"
    else:
        response = "HTTP/1.1 403 Forbidden\r\n"
        response += "Content-Type: application/json\r\n"
        response += "Content-Length: 2\r\n"
        response += "\r\n"
        response += "{}"
    return response


def send_message_to_chat_server(username, message):
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(5)
        print(
            f"Attempting to connect to chat server at {CHAT_SERVER_HOST}:{CHAT_SERVER_PORT}"
        )
        sock.connect((CHAT_SERVER_HOST, CHAT_SERVER_PORT))
        print("Connected to chat server successfully.")

        # Wait for the prompt from the chat server
        data = receive_from_chat_server(sock, b"Enter your username:", timeout=2)
        if data is None:
            print("Did not receive username prompt from chat server.")
            return False

        # Send special username to identify as web client
        sock.sendall("__WebClient__\n".encode("utf-8"))
        print("Sent identifier '__WebClient__' to chat server.")

        # Send command to send message
        command = f"SEND_MESSAGE {username} {message}\n"
        sock.sendall(command.encode("utf-8"))
        print(f"Sent command to chat server: {command.strip()}")

        # Wait for acknowledgment
        response = receive_from_chat_server(sock, b"", timeout=2)
        if response:
            response_decoded = response.decode("utf-8").strip()
            print(f"Received acknowledgment from chat server: '{response_decoded}'")
            if response_decoded == "SUCCESS":
                return True
            else:
                print("Failed to send message as per chat server response.")
                return False
        else:
            print("No response from chat server after sending message.")
            return False

    except Exception as e:
        print(f"Error connecting to chat server: {e}")
        return False
    finally:
        sock.close()
        print("Closed connection to chat server.")


def delete_message_on_chat_server(username, message_id):
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(5)
        print(
            f"Attempting to connect to chat server at {CHAT_SERVER_HOST}:{CHAT_SERVER_PORT}"
        )
        sock.connect((CHAT_SERVER_HOST, CHAT_SERVER_PORT))
        print("Connected to chat server successfully.")

        # Wait for the prompt from the chat server
        data = receive_from_chat_server(sock, b"Enter your username:", timeout=2)
        if data is None:
            print("Did not receive username prompt from chat server.")
            return False

        # Send special username to identify as web client
        sock.sendall("__WebClient__\n".encode("utf-8"))
        print("Sent identifier '__WebClient__' to chat server.")

        # Send delete command
        command = f"DELETE_MESSAGE {message_id} {username}\n"
        sock.sendall(command.encode("utf-8"))
        print(f"Sent command to chat server: {command.strip()}")

        # Receive response from chat server
        response = receive_from_chat_server(sock, b"", timeout=2)
        if response:
            response_decoded = response.decode("utf-8").strip()
            print(f"Received acknowledgment from chat server: '{response_decoded}'")
            if response_decoded == "SUCCESS":
                return True
            else:
                print("Failed to delete message as per chat server response.")
                return False
        else:
            print("No response from chat server after sending delete command.")
            return False
    except Exception as e:
        print(f"Error deleting message from chat server: {e}")
        return False
    finally:
        sock.close()
        print("Closed connection to chat server.")


def fetch_messages_from_chat_server(last_id):
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(5)
        print(
            f"Attempting to connect to chat server at {CHAT_SERVER_HOST}:{CHAT_SERVER_PORT}"
        )
        sock.connect((CHAT_SERVER_HOST, CHAT_SERVER_PORT))
        print("Connected to chat server successfully.")

        # Wait for the prompt from the chat server
        data = receive_from_chat_server(sock, b"Enter your username:", timeout=2)
        if data is None:
            print("Did not receive username prompt from chat server.")
            return None

        # Send special username to identify as web client
        sock.sendall("__WebClient__\n".encode("utf-8"))
        print("Sent identifier '__WebClient__' to chat server.")

        # Send command to get messages after last_id
        command = f"GET_MESSAGES {last_id}\n"
        sock.sendall(command.encode("utf-8"))
        print(f"Sent command to chat server: {command.strip()}")

        # Receive messages from chat server
        json_data = receive_all_from_chat_server(sock, timeout=2)
        if json_data:
            print("Received messages from chat server.")
            messages = json.loads(json_data.decode("utf-8"))
            return messages
        else:
            print("No messages received from chat server.")
            return []
    except Exception as e:
        print(f"Error fetching messages from chat server: {e}")
        return None
    finally:
        sock.close()
        print("Closed connection to chat server.")


def receive_from_chat_server(sock, delimiter, timeout):
    sock.setblocking(0)
    data = b""
    start_time = time.time()
    while True:
        if time.time() - start_time > timeout:
            return None
        ready = select.select([sock], [], [], timeout)
        if ready[0]:
            try:
                chunk = sock.recv(4096)
                if not chunk:
                    return None
                data += chunk
                if delimiter in data:
                    return data
            except socket.error as e:
                print(f"Socket error while receiving data: {e}")
                return None
        else:
            continue


def receive_all_from_chat_server(sock, timeout):
    sock.setblocking(0)
    data = b""
    start_time = time.time()
    while True:
        if time.time() - start_time > timeout:
            break
        ready = select.select([sock], [], [], timeout)
        if ready[0]:
            try:
                chunk = sock.recv(4096)
                if not chunk:
                    break
                data += chunk
            except socket.error as e:
                print(f"Socket error while receiving data: {e}")
                break
        else:
            continue
    return data


if __name__ == "__main__":
    main()

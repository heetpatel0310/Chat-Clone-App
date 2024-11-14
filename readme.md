Assignment 2: Multi-threaded API Web Server - Discordn't

**Overview**
This project is an extension of Assignment 1, implementing a multi-threaded web server that serves dynamic content for a chat application named "Discordn't". The web server provides an API and a web interface for users to interact with the chat system, allowing users to log in, post messages, retrieve messages, and delete their own messages.

**The project includes**
Chat Server (server.py): Handles storing messages and managing connected clients.
Web Server (webserver.py): Serves the web interface (index.html) and provides API endpoints.
Web Interface (index.html): A single-page application that interacts with the web server via JavaScript.
Command-Line Chat Client (client.py): Allows interaction with the chat server directly.
C Screen Scraper (scraper.c): Tests the web server's API endpoints.
Makefile: Used to build the C program.

**Bonus Features**
Message Deletion Implemented: Users can delete their own messages. There are buttons on the frontend to delete messages, and the frontend updates appropriately. This feature is implemented as per the bonus requirements.
Session Management: Sessions are managed using cookies, and users remain logged in across sessions until they log out.

**Prerequisites**
Python 3.6 or higher.
GCC or Clang compiler to build the C program.
Make utility to use the provided Makefile.
Bash Shell (for running any scripts).
WSL (Windows Subsystem for Linux), if you're on Windows.
SQLite3 (Python's sqlite3 module is used for database operations).
Running the Code
Port Numbers
The following default port numbers are used:

Chat Server (server.py): Port 8635.
Web Server (webserver.py): Port 8636.
Ensure that these ports are available on your machine before running the servers.

1. Starting the Chat Server
   The chat server handles storing and broadcasting messages.

Command:
python3 server.py 8635

2. Starting the Web Server
   The web server serves the web interface and provides API endpoints for client interactions.

Command:
python3 webserver.py

Notes:
The web server connects to the chat server using the host and port specified in webserver.py (default is hawk.cs.umanitoba.ca:8635). Ensure that the chat server is running before starting the web server.
If you change the port in server.py, update the CHAT_SERVER_PORT in webserver.py to match.

3. Using the Web Application
   Open a web browser (preferably Google Chrome) and navigate to:

http://hawk.cs.umanitoba.ca:8636/
Login: Enter a username to log in. No password is required.
Chat: After logging in, you can send messages, which will be broadcasted to all connected clients.
Delete Messages: You can delete messages that you have posted by clicking the "Delete" button next to your message.
Logout: Click the "Logout" button to log out.

4. Running the Command-Line Chat Client (Optional)
   You can interact with the chat server directly using the command-line client.

Command:
python3 client.py hawk.cs.umanitoba.ca 8635

Notes:
Replace hawk.cs.umanitoba.ca and 8635 with the appropriate host and port if they differ.
The client will prompt you to enter a username and then allow you to send messages.

5. Building and Running the C Screen Scraper
   The scraper.c program is a screen scraper that tests the web server's API endpoints.

Building the Scraper
Use the provided Makefile to build the scraper.

Command:
make

Notes:
This will compile scraper.c and produce an executable named scraper.
Ensure you have either GCC or Clang installed.

Running the Scraper
The scraper requires the following arguments:

./scraper [HOST] [PORT] [USERNAME] [MESSAGE]

Example:
./scraper hawk.cs.umanitoba.ca 8636 heet How are you

Clean Build:
Run make clean (if you have a clean target in your Makefile) and then make to ensure a fresh build.

Notes:
The scraper performs several tests:
Logs in as the specified username.
Fetches messages to verify the message does not already exist.
Posts the specified message.
Fetches messages again to verify the message was posted.
Tests unauthorized access by making requests without proper authentication.

**How to Run Everything Together**
Start the Chat Server:
python3 server.py 8635

Start the Web Server:
python3 webserver.py

Start the Command-Line Client (Optional):
python3 client.py hawk.cs.umanitoba.ca 8635

Build the Scraper:
make

Run the Scraper (Testing):
./scraper hawk.cs.umanitoba.ca 8636 heet How are you

Access the Web Application:
Open your browser and navigate to:
http://hawk.cs.umanitoba.ca:8636/

**Access the Static Files:**
Open a web browser and go to `http://hawk.cs.umanitoba.ca:8636/files/images.html` to test image serving.
Navigate to `http://hawk.cs.umanitoba.ca:8636/files/test.html` to test serving a simple HTML page.
Visit `http://hawk.cs.umanitoba.ca:8636/files/link.html` to test page linking.

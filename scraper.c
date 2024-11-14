#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <assert.h>
#include <sys/socket.h>
#include <netinet/in.h> 
#include <arpa/inet.h>
#include <unistd.h>
#include <netdb.h> 

#define BUFFER_SIZE 65536 

// Function to send HTTP request and receive response
int send_http_request(const char *host, int port, const char *request, char *response, int response_size) {
    int sock;
    struct sockaddr_in server_addr;
    char server_ip[16];

    // Resolve host to IP
    struct hostent *he = gethostbyname(host);
    if (he == NULL) {
        printf("Could not resolve hostname.\n");
        return -1;
    }
    strcpy(server_ip, inet_ntoa(*(struct in_addr *)he->h_addr_list[0]));

    // Create socket
    sock = socket(AF_INET, SOCK_STREAM, 0);
    if (sock < 0) {
        printf("Could not create socket.\n");
        return -1;
    }

    // Setup server address
    server_addr.sin_family = AF_INET;
    server_addr.sin_port = htons(port);
    server_addr.sin_addr.s_addr = inet_addr(server_ip);

    // Connect to server
    if (connect(sock, (struct sockaddr *)&server_addr, sizeof(server_addr)) < 0) {
        printf("Could not connect to server.\n");
        close(sock);
        return -1;
    }

    // Send request
    if (send(sock, request, strlen(request), 0) < 0) {
        printf("Failed to send request.\n");
        close(sock);
        return -1;
    }

    // Receive response
    int total_received = 0;
    int bytes_received;
    char buffer[1024];
    int header_received = 0;
    int content_length = 0;

    while ((bytes_received = recv(sock, buffer, sizeof(buffer) - 1, 0)) > 0) {
        buffer[bytes_received] = '\0';

        if (total_received + bytes_received >= response_size - 1) {
            printf("Response buffer full, response may be truncated.\n");
            break;
        }

        // Append received data to response
        memcpy(response + total_received, buffer, bytes_received);
        total_received += bytes_received;

        if (!header_received) {
            char *header_end = strstr(response, "\r\n\r\n");
            if (header_end != NULL) {
                header_received = 1;

                // Parse headers to find Content-Length
                char *content_length_str = strstr(response, "Content-Length:");
                if (content_length_str != NULL) {
                    content_length_str += strlen("Content-Length:");
                    while (*content_length_str == ' ') content_length_str++;
                    content_length = atoi(content_length_str);
                }

                // Calculate total expected size (headers + content)
                int headers_size = header_end - response + 4; // 4 for "\r\n\r\n"
                int total_expected = headers_size + content_length;

                if (total_received >= total_expected) {
                    break;
                }
            }
        } else {
            char *header_end = strstr(response, "\r\n\r\n");
            int headers_size = header_end - response + 4;
            int total_expected = headers_size + content_length;
            if (total_received >= total_expected) {
                break;
            }
        }
    }

    if (bytes_received < 0) {
        printf("Error receiving response.\n");
        close(sock);
        return -1;
    }

    response[total_received] = '\0';

    close(sock);
    return 0;
}

void escape_json_string(const char *input, char *output) {
    const char *p = input;
    char *q = output;
    while (*p) {
        if (*p == '"' || *p == '\\') {
            *q++ = '\\';
        }
        *q++ = *p++;
    }
    *q = '\0';
}

// Main function
int main(int argc, char *argv[]) {
    if (argc < 5) {
        printf("Usage: %s host port username message\n", argv[0]);
        return 1;
    }

    char *host = argv[1];
    int port = atoi(argv[2]);
    char *username = argv[3];

    char message[1024] = "";
    for (int i = 4; i < argc; i++) {
        strcat(message, argv[i]);
        if (i < argc - 1) {
            strcat(message, " ");
        }
    }

    char session_id[128] = "";
    char response[BUFFER_SIZE];

    // Step 1: Login and capture session_id
    char login_request[2048];
    char login_body[256];

    sprintf(login_body, "{\"username\":\"%s\"}", username);

    sprintf(login_request,
            "POST /api/login HTTP/1.1\r\n"
            "Host: %s\r\n"
            "Content-Type: application/json\r\n"
            "Content-Length: %zu\r\n"
            "Connection: close\r\n"
            "\r\n"
            "%s",
            host, strlen(login_body), login_body);

    memset(response, 0, sizeof(response));

    if (send_http_request(host, port, login_request, response, sizeof(response)) == 0) {
        char *set_cookie = strstr(response, "Set-Cookie:");
        if (set_cookie != NULL) {
            char *session_id_start = strstr(set_cookie, "session_id=");
            if (session_id_start != NULL) {
                session_id_start += strlen("session_id=");
                char *session_id_end = strstr(session_id_start, ";");
                int session_id_length = session_id_end - session_id_start;
                strncpy(session_id, session_id_start, session_id_length);
                session_id[session_id_length] = '\0';
                printf("Session ID: %s\n", session_id);
            } else {
                printf("Session ID not found in login response.\n");
                return 1;
            }
        } else {
            printf("Set-Cookie header not found in login response.\n");
            return 1;
        }
    } else {
        printf("Failed to send login request.\n");
        return 1;
    }

    // Step 2: Fetch messages before posting
    char get_request[512];

    sprintf(get_request,
            "GET /api/messages HTTP/1.1\r\n"
            "Host: %s\r\n"
            "Cookie: session_id=%s\r\n"
            "Connection: close\r\n"
            "\r\n",
            host, session_id);

    memset(response, 0, sizeof(response));

    if (send_http_request(host, port, get_request, response, sizeof(response)) == 0) {
        if (strstr(response, message) == NULL) {
            printf("Message not found before posting, as expected.\n");
        } else {
            printf("Message already exists before posting.\n");
            return 1;
        }
    } else {
        printf("Failed to send GET request before posting.\n");
        return 1;
    }

    // Step 3: Post a new message
    char post_request[4096];
    char post_body[2048];
    char escaped_message[2048];

    escape_json_string(message, escaped_message);

    sprintf(post_body, "{\"message\":\"%s\"}", escaped_message);

    sprintf(post_request,
            "POST /api/messages HTTP/1.1\r\n"
            "Host: %s\r\n"
            "Content-Type: application/json\r\n"
            "Content-Length: %zu\r\n"
            "Cookie: session_id=%s\r\n"
            "Connection: close\r\n"
            "\r\n"
            "%s",
            host, strlen(post_body), session_id, post_body);

    printf("POST Request:\n%s\n", post_request);

    memset(response, 0, sizeof(response));

    if (send_http_request(host, port, post_request, response, sizeof(response)) == 0) {
        printf("Response from POST request:\n%s\n", response);
        if (strstr(response, "200 OK") != NULL) {
            printf("Message posted successfully.\n");
        } else {
            printf("Failed to post message.\n");
            return 1;
        }
    } else {
        printf("Failed to send POST request.\n");
        return 1;
    }

    // Step 4: Fetch messages after posting and verify
    memset(response, 0, sizeof(response));

    if (send_http_request(host, port, get_request, response, sizeof(response)) == 0) {
        printf("Response after posting:\n%s\n", response);
        printf("Response length: %zu\n", strlen(response));
        if (strstr(response, message) != NULL) {
            printf("Message found after posting.\n");
        } else {
            printf("Message not found after posting.\n");
            assert(0);
        }
    } else {
        printf("Failed to send GET request after posting.\n");
        return 1;
    }

    // Step 5: Test unauthorized access
    char unauth_get_request[512];

    sprintf(unauth_get_request,
            "GET /api/messages HTTP/1.1\r\n"
            "Host: %s\r\n"
            "Connection: close\r\n"
            "\r\n",
            host);
    memset(response, 0, sizeof(response));

    if (send_http_request(host, port, unauth_get_request, response, sizeof(response)) == 0) {
        if (strstr(response, "401 Unauthorized") != NULL) {
            printf("Unauthorized GET request correctly handled.\n");
        } else {
            printf("Unauthorized GET request not handled properly.\n");
            assert(0); 
        }
    } else {
        printf("Failed to send unauthorized GET request.\n");
        return 1;
    }

    sprintf(post_request,
            "POST /api/messages HTTP/1.1\r\n"
            "Host: %s\r\n"
            "Content-Type: application/json\r\n"
            "Content-Length: %zu\r\n"
            "Connection: close\r\n"
            "\r\n"
            "%s",
            host, strlen(post_body), post_body);

    memset(response, 0, sizeof(response));

    if (send_http_request(host, port, post_request, response, sizeof(response)) == 0) {
        if (strstr(response, "401 Unauthorized") != NULL) {
            printf("Unauthorized POST request correctly handled.\n");
        } else {
            printf("Unauthorized POST request not handled properly.\n");
            assert(0); 
        }
    } else {
        printf("Failed to send unauthorized POST request.\n");
        return 1;
    }

    printf("All tests passed successfully.\n");
    return 0;
}

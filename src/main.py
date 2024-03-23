"""
This module defines the structure and functionality of a simple web and socket server application. 

It includes classes and functions for handling HTTP requests, managing socket connections,
and interacting with a MongoDB database. The module sets up a basic web server capable of
serving static files and dynamic content, and a socket server for processing data received
over network sockets.
"""

# Standard library imports
from datetime import datetime
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path
import logging
import mimetypes
import socket
from urllib.parse import urlparse, unquote_plus
import multiprocessing
import argparse


# Related third-party imports
from pymongo import MongoClient, errors


# Configuration class for maintaining global settings
class Config:
    """Configuration settings for the application."""

    HTTP_HOST = ""
    HTTP_PORT = 3000
    SOCKET_HOST = ""
    SOCKET_PORT = 5000
    DB_URI = "mongodb://mongo:27017"
    BUFFER_SIZE = 1024
    BASE_DIR = Path(__file__).parent
    TEMPLATES_DIR = BASE_DIR.joinpath("templates")


# Class for MongoDB connection handling
class MongoDBClient:
    """Handles database operations."""

    def __init__(self, uri):
        self.client = MongoClient(uri)
        self.db = self.client.get_database("homework")

    def save_message_from_udp_data(self, data):
        """Parses data from UDP and saves it as a message document in the database."""
        try:
            parsed_data = unquote_plus(data.decode())
            # Attempt to parse the received data
            parsed_data = {
                key: value
                for key, value in [el.split("=") for el in parsed_data.split("&")]
            }
            # Add the current date and time to the document
            parsed_data["date"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")
            # Insert the document into the database
            self.db.messages.insert_one(parsed_data)
        except ValueError as e:
            logging.error("Data parsing error: %s", e)
        except errors.ConnectionFailure as e:
            logging.error("Could not connect to MongoDB: %s", e)
        except Exception as e:
            logging.error("Failed to save data: %s", e)

    def close(self):
        """Closes the database connection."""
        self.client.close()


# Custom HTTP request handler
class CatFramework(BaseHTTPRequestHandler):
    """HTTP request handler with GET and POST commands."""

    def do_GET(self):
        """Handle GET requests."""
        router = urlparse(self.path).path
        if router == "/":
            self.send_html("index.html")
        else:
            file = Config.BASE_DIR.joinpath(router[1:])
            if file.exists():
                self.send_static(file)
            else:
                self.send_html("error.html", 404)

    def do_POST(self):
        """Handle POST requests."""
        size = int(self.headers.get("Content-Length", 0))
        data = self.rfile.read(size).decode()
        client_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        client_socket.sendto(data.encode(), (Config.SOCKET_HOST, Config.SOCKET_PORT))
        client_socket.close()
        self.send_response(302)
        self.send_header("Location", "/")
        self.end_headers()

    def send_html(self, filename, status=200):
        """Send an HTML response."""
        self.send_response(status)
        self.send_header("Content-type", "text/html")
        self.end_headers()
        with open(Config.TEMPLATES_DIR.joinpath(filename), "rb") as f:
            self.wfile.write(f.read())

    def send_static(self, filename, status=200):
        """Send a static file response."""
        self.send_response(status)
        mimetype = mimetypes.guess_type(filename)[0] or "text/plain"
        self.send_header("Content-type", mimetype)
        self.end_headers()
        with open(filename, "rb") as f:
            self.wfile.write(f.read())


# Function to run the HTTP server
def run_http_server():
    """Starts the HTTP server."""
    http_server = HTTPServer((Config.HTTP_HOST, Config.HTTP_PORT), CatFramework)
    logging.info("HTTP Server running on %s:%s", Config.HTTP_HOST, Config.HTTP_PORT)
    try:
        http_server.serve_forever()
    except KeyboardInterrupt:
        pass
    except Exception as e:
        logging.error("HTTP Server error: %s", e)
    finally:
        http_server.server_close()
        logging.info("HTTP Server stopped.")


# Function to run the socket server
def run_socket_server():
    """Starts and runs the socket server.

    This server listens for incoming data on a predetermined socket, processes the data,
    and saves it to a MongoDB database. It operates in an infinite loop, continuously
    listening for data until an exception occurs or the server is manually stopped.
    """
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        sock.bind((Config.SOCKET_HOST, Config.SOCKET_PORT))
        logging.info(
            "Socket Server running on %s:%s", Config.SOCKET_HOST, Config.SOCKET_PORT
        )
        client = MongoDBClient(Config.DB_URI)
        try:
            while True:
                data, _ = sock.recvfrom(Config.BUFFER_SIZE)
                logging.info("Received data: %s", data)
                client.save_message_from_udp_data(data)
        except KeyboardInterrupt:
            pass
        except Exception as e:
            logging.error("Socket Server error: %s", e)
        finally:
            client.close()
            logging.info("Socket Server stopped.")


# Main entry point of the script
if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
    )

    parser = argparse.ArgumentParser(description="Run the web or socket server")
    parser.add_argument("--http", action="store_true", help="Run the HTTP server")
    parser.add_argument("--socket", action="store_true", help="Run the Socket server")

    args = parser.parse_args()

    if args.http and args.socket:
        logging.error("Please specify only one server at a time.")
    elif args.http:
        logging.info("Starting HTTP server...")
        run_http_server()
    elif args.socket:
        logging.info("Starting Socket server...")
        run_socket_server()
    else:
        logging.info("Starting both HTTP and Socket servers...")
        http_process = multiprocessing.Process(target=run_http_server)
        socket_process = multiprocessing.Process(target=run_socket_server)

        http_process.start()
        socket_process.start()

        http_process.join()
        socket_process.join()

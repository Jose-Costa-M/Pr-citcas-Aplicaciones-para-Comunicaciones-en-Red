import os
import socket
import signal
import sys
import shutil

# Server Configuration
BUFFER_SIZE = 1024
FRAGMENT_SIZE = 200
WINDOW_SIZE = 5
END_SIGNAL = b"END"
END_SESSION = b"END_SESSION"
DELETE_REQUEST = b"DELETE"
DELETE_FOLDER_REQUEST = b"DELETE_FOLDER"  # New command for folder deletion

SERVER_DIRECTORY = r"Poner la ruta de la carpeta donde se encuentre este documento"

class Server:
    def __init__(self, host='localhost', port=9000):
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.server_socket.bind((host, port))
        self.is_running = True
        print(f"Server started on {host}:{port}")

        # Set up signal handling for graceful shutdown
        signal.signal(signal.SIGINT, self.shutdown)

    def receive_files(self):
        while self.is_running:
            try:
                # Receive the initial packet for filename and folder structure
                data, client_address = self.server_socket.recvfrom(BUFFER_SIZE + 4)

                # Check for session end signal
                if data == END_SESSION:
                    print("End session signal received. Shutting down server.")
                    self.shutdown(None, None)
                    break

                # Handle delete requests or file reception
                if data.startswith(DELETE_FOLDER_REQUEST):
                    folder_path = data[len(DELETE_FOLDER_REQUEST):].decode('utf-8').strip()
                    self.handle_delete_request(folder_path, client_address, is_folder=True)
                    continue
                elif data.startswith(DELETE_REQUEST):
                    filename = data[len(DELETE_REQUEST):].decode('utf-8').strip()
                    self.handle_delete_request(filename, client_address, is_folder=False)
                    continue

                # Extract sequence number and filepath from the packet
                seq_num = int.from_bytes(data[:4], 'big')
                filepath = data[4:].decode('utf-8')
                full_path = os.path.join(SERVER_DIRECTORY, filepath)
                
                # Create necessary folder structure if specified in filepath
                folder_path = os.path.dirname(full_path)
                if folder_path and not os.path.exists(folder_path):
                    os.makedirs(folder_path)

                # Open the file for writing
                with open(full_path, 'wb') as file:
                    print(f"Receiving file: {full_path}")
                    expected_seq_num = 1
                    window = {}
                    fragment_buffers = {}

                    while True:
                        data, client_address = self.server_socket.recvfrom(FRAGMENT_SIZE + 8)

                        # If END_SIGNAL is received, finalize the file
                        if data == END_SIGNAL:
                            print(f"File {full_path} received successfully.")
                            for seq in sorted(window.keys()):
                                file.write(window[seq])
                            break

                        # Parse the sequence number and fragment data
                        received_seq_num = int.from_bytes(data[:4], 'big')
                        fragment_index = int.from_bytes(data[4:6], 'big')
                        num_fragments = int.from_bytes(data[6:8], 'big')
                        fragment_data = data[8:]

                        print(f"Received packet: Seq #{received_seq_num}, Fragment #{fragment_index}/{num_fragments}")

                        if expected_seq_num <= received_seq_num < expected_seq_num + WINDOW_SIZE:
                            # Buffer the fragment data
                            if received_seq_num not in fragment_buffers:
                                fragment_buffers[received_seq_num] = [None] * num_fragments
                            fragment_buffers[received_seq_num][fragment_index] = fragment_data

                            # Check if all fragments of this packet have arrived
                            if all(fragment is not None for fragment in fragment_buffers[received_seq_num]):
                                # Reassemble the full packet
                                full_packet_data = b''.join(fragment_buffers[received_seq_num])
                                window[received_seq_num] = full_packet_data
                                del fragment_buffers[received_seq_num]

                                # Send acknowledgment
                                ack_packet = received_seq_num.to_bytes(4, 'big')
                                self.server_socket.sendto(ack_packet, client_address)
                                print(f"Sent ACK for Seq #{received_seq_num}")

                                # Write any in-sequence packets to the file
                                while expected_seq_num in window:
                                    file.write(window.pop(expected_seq_num))
                                    expected_seq_num += 1
                        else:
                            # Resend last ACK if out-of-window packet received
                            last_ack_packet = (expected_seq_num - 1).to_bytes(4, 'big')
                            self.server_socket.sendto(last_ack_packet, client_address)
                            print(f"Resent last ACK for Seq #{expected_seq_num - 1}")

            except Exception as e:
                print(f"An error occurred during file reception: {e}")

    def handle_delete_request(self, relative_path, client_address, is_folder):
        """Deletes a file or folder given a relative path from SERVER_DIRECTORY."""
        target_path = os.path.join(SERVER_DIRECTORY, relative_path)

        # Ensure that the target path exists and is within the SERVER_DIRECTORY
        if os.path.exists(target_path) and os.path.commonpath([SERVER_DIRECTORY, target_path]) == SERVER_DIRECTORY:
            try:
                if is_folder:
                    shutil.rmtree(target_path)
                    response = f"Folder '{relative_path}' deleted successfully.".encode('utf-8')
                else:
                    os.remove(target_path)
                    response = f"File '{relative_path}' deleted successfully.".encode('utf-8')
            except Exception as e:
                response = f"Error deleting '{relative_path}': {e}".encode('utf-8')
            print(response.decode('utf-8'))
        else:
            response = f"File or folder '{relative_path}' not found.".encode('utf-8')
            print(response.decode('utf-8'))
        
        # Send the response back to the client
        self.server_socket.sendto(response, client_address)

    def shutdown(self, signum, frame):
        print("\nShutting down server...")
        self.is_running = False
        self.server_socket.close()
        sys.exit(0)

    def start(self):
        print("Server is waiting for files...")
        self.receive_files()

# Start the server
if __name__ == "__main__":
    server = Server()
    server.start()

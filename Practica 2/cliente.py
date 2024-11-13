import os
import socket
import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog
from PIL import Image, ImageTk
import subprocess
import sys

# Client Configuration
BUFFER_SIZE = 1024
FRAGMENT_SIZE = 200
WINDOW_SIZE = 5
END_SIGNAL = b"END"
END_SESSION = b"END_SESSION"
DELETE_REQUEST = b"DELETE"
DELETE_FOLDER_REQUEST = b"DELETE_FOLDER"  # New command for folder deletion

GLOBAL_DIRECTORY = r"Poner la ruta donde se encuentre este documento"

class Client:
    def __init__(self, server_ip='localhost', server_port=9000):
        self.client_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.server_address = (server_ip, server_port)
        self.client_socket.settimeout(2)

    def send_file(self, filepath, folder=""):
        try:
            filename = os.path.join(folder, os.path.basename(filepath)) if folder else os.path.basename(filepath)
            print(f"Attempting to upload file: {filepath}")
            print(f"Destination filename on server: {filename}")

            filename_packet = (0).to_bytes(4, 'big') + filename.encode('utf-8')
            self.client_socket.sendto(filename_packet, self.server_address)
            
            with open(filepath, 'rb') as file:
                seq_num = 1
                window = {}

                while True:
                    while len(window) < WINDOW_SIZE:
                        data = file.read(BUFFER_SIZE)
                        if not data:
                            break

                        num_fragments = (len(data) + FRAGMENT_SIZE - 1) // FRAGMENT_SIZE
                        for fragment_index in range(num_fragments):
                            fragment_start = fragment_index * FRAGMENT_SIZE
                            fragment_data = data[fragment_start:fragment_start + FRAGMENT_SIZE]

                            packet = (
                                seq_num.to_bytes(4, 'big') +
                                fragment_index.to_bytes(2, 'big') +
                                num_fragments.to_bytes(2, 'big') +
                                fragment_data
                            )
                            self.client_socket.sendto(packet, self.server_address)

                        window[seq_num] = (data, num_fragments)
                        seq_num += 1

                    try:
                        ack, _ = self.client_socket.recvfrom(4)
                        ack_num = int.from_bytes(ack, 'big')

                        if ack_num in window:
                            del window[ack_num]

                    except socket.timeout:
                        print("Timeout occurred, resending packets...")
                        for seq, (data, num_fragments) in window.items():
                            for fragment_index in range(num_fragments):
                                fragment_start = fragment_index * FRAGMENT_SIZE
                                fragment_data = data[fragment_start:fragment_start + FRAGMENT_SIZE]
                                packet = (
                                    seq.to_bytes(4, 'big') +
                                    fragment_index.to_bytes(2, 'big') +
                                    num_fragments.to_bytes(2, 'big') +
                                    fragment_data
                                )
                                self.client_socket.sendto(packet, self.server_address)

                    if not data and not window:
                        break

            self.client_socket.sendto(END_SIGNAL, self.server_address)
            print(f"File upload completed: {filepath}")

        except Exception as e:
            print(f"Error occurred while uploading file: {e}")
            messagebox.showerror("Upload Error", f"Failed to upload file: {e}")

    def delete_file(self, filepath):
        delete_packet = DELETE_REQUEST + filepath.encode('utf-8')
        self.client_socket.sendto(delete_packet, self.server_address)
        
        try:
            response, _ = self.client_socket.recvfrom(BUFFER_SIZE)
            return response.decode('utf-8')
        except socket.timeout:
            return "Error: Server did not respond to delete request."

    def delete_folder(self, folderpath):
        delete_packet = DELETE_FOLDER_REQUEST + folderpath.encode('utf-8')
        self.client_socket.sendto(delete_packet, self.server_address)
        
        try:
            response, _ = self.client_socket.recvfrom(BUFFER_SIZE)
            return response.decode('utf-8')
        except socket.timeout:
            return "Error: Server did not respond to delete folder request."

    def close_connection(self):
        try:
            self.client_socket.sendto(END_SESSION, self.server_address)
            self.client_socket.close()
        except Exception as e:
            print(f"Error closing connection: {e}")

class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.client = Client()
        self.title("File Manager with Folder Support")
        self.geometry("600x600")

        self.icons = {
            "audio": self.load_icon("audio_icon.png"),
            "video": self.load_icon("video_icon.png"),
            "pdf": self.load_icon("pdf_icon.png"),
            "text": self.load_icon("text_icon.png"),
            "image": self.load_icon("image_icon.png")
        }

        self.folders = {"": []}
        self.selected_folder = ""
        self.filepaths = {"": []}

        self.protocol("WM_DELETE_WINDOW", self.on_close)

        self.create_folder_button = tk.Button(self, text="Create Folder", command=self.create_folder)
        self.create_folder_button.pack(pady=5)

        self.folder_listbox = tk.Listbox(self, selectmode=tk.SINGLE, width=60, height=6)
        self.folder_listbox.pack(pady=5)
        self.folder_listbox.bind("<<ListboxSelect>>", self.on_folder_select)
        self.update_folder_listbox()

        self.select_button = tk.Button(self, text="Select Files", command=self.select_files)
        self.select_button.pack(pady=10)

        self.file_listbox = tk.Listbox(self, selectmode=tk.SINGLE, width=60, height=8)
        self.file_listbox.pack(pady=5)
        self.file_listbox.bind("<Double-Button-1>", self.open_selected_file)
        self.file_listbox.bind("<<ListboxSelect>>", self.on_file_select)

        self.preview_label = tk.Label(self, text="Preview:", font=("Arial", 12))
        self.preview_label.pack(pady=5)

        self.preview_text = tk.Text(self, height=10, width=60, wrap='word')
        self.preview_image_label = tk.Label(self)

        self.upload_button = tk.Button(self, text="Upload to Selected Folder", command=self.upload_files)
        self.upload_button.pack(pady=10)

        self.delete_button = tk.Button(self, text="Delete Selected File", command=self.delete_selected_file)
        self.delete_button.pack(pady=5)

        # New button to delete the selected folder
        self.delete_folder_button = tk.Button(self, text="Delete Selected Folder", command=self.delete_selected_folder)
        self.delete_folder_button.pack(pady=5)

    def delete_selected_folder(self):
        """Delete the selected folder and all its contents from the server."""
        if self.selected_folder:
            confirm = messagebox.askyesno("Delete Folder", f"Are you sure you want to delete the entire folder '{self.selected_folder}' and all its contents?")
            if confirm:
                # Send the deletion request to the server
                result = self.client.delete_folder(self.selected_folder)
                messagebox.showinfo("Delete Folder Status", result)
                
                # Remove folder from the local display if deletion was successful
                if "deleted successfully" in result:
                    del self.folders[self.selected_folder]
                    del self.filepaths[self.selected_folder]
                    self.selected_folder = ""
                    self.update_folder_listbox()
                    self.update_file_listbox()

    def load_icon(self, icon_name):
        icon_path = os.path.join(GLOBAL_DIRECTORY, icon_name)
        try:
            icon = ImageTk.PhotoImage(Image.open(icon_path).resize((20, 20)))
            print(f"Loaded icon: {icon_path}")
        except FileNotFoundError:
            icon = None
            print(f"{icon_name} not found in {GLOBAL_DIRECTORY}.")
        return icon

    def on_close(self):
        self.client.close_connection()
        self.destroy()

    def create_folder(self):
        folder_name = simpledialog.askstring("Create Folder", "Enter folder name:")
        if folder_name and folder_name not in self.folders:
            self.folders[folder_name] = []
            self.filepaths[folder_name] = []
            self.update_folder_listbox()

    def update_folder_listbox(self):
        self.folder_listbox.delete(0, tk.END)
        self.folder_listbox.insert(tk.END, "Global (Root Directory)")
        for folder in self.folders.keys():
            if folder:
                self.folder_listbox.insert(tk.END, folder)

    def on_folder_select(self, event):
        selection = self.folder_listbox.curselection()
        if selection:
            index = selection[0]
            self.selected_folder = "" if index == 0 else self.folder_listbox.get(index)
            self.update_file_listbox()

    def update_file_listbox(self):
        self.file_listbox.delete(0, tk.END)
        for file in self.folders.get(self.selected_folder, []):
            icon = self.get_icon_for_file(file)
            self.file_listbox.insert(tk.END, file)
            if icon:
                self.file_listbox.image_create(tk.END, image=icon)

    def get_icon_for_file(self, filename):
        ext = os.path.splitext(filename)[1].lower()
        if ext in ['.mp3', '.wav']:
            return self.icons.get("audio")
        elif ext in ['.mp4', '.avi', '.mov']:
            return self.icons.get("video")
        elif ext == '.pdf':
            return self.icons.get("pdf")
        elif ext in ['.txt', '.csv']:
            return self.icons.get("text")
        elif ext in ['.jpg', '.jpeg', '.png']:
            return self.icons.get("image")
        return None

    def select_files(self):
        files = filedialog.askopenfilenames()
        if files:
            for filepath in files:
                filename = os.path.basename(filepath)
                abs_path = os.path.abspath(filepath)
                if self.selected_folder not in self.folders:
                    self.folders[self.selected_folder] = []
                if self.selected_folder not in self.filepaths:
                    self.filepaths[self.selected_folder] = []
                self.folders[self.selected_folder].append(filename)
                self.filepaths[self.selected_folder].append(abs_path)
            self.update_file_listbox()

    def delete_selected_file(self):
        """Delete the selected file from the global directory and the list if it exists."""
        selection = self.file_listbox.curselection()
        if selection:
            index = selection[0]
            filename = self.file_listbox.get(index)
            file_path = os.path.join(self.selected_folder, filename)
            
            # Request deletion from the server
            result = self.client.delete_file(file_path)
            messagebox.showinfo("Delete Status", result)
            
            # Check if deletion was successful and update the display
            if "deleted successfully" in result:
                # Remove the file from folders and filepaths dictionaries
                if filename in self.folders[self.selected_folder]:
                    self.folders[self.selected_folder].remove(filename)
                self.filepaths[self.selected_folder] = [
                    fp for fp in self.filepaths[self.selected_folder]
                    if os.path.basename(fp).lower() != filename.lower()
                ]
                self.update_file_listbox()
                self.clear_preview()

    def open_selected_file(self, event):
        selection = self.file_listbox.curselection()
        if selection:
            index = selection[0]
            filename = self.file_listbox.get(index)
            file_path = os.path.join(GLOBAL_DIRECTORY, filename)

            if os.path.isfile(file_path):
                try:
                    if sys.platform == "win32":
                        os.startfile(file_path)
                    elif sys.platform == "darwin":
                        subprocess.Popen(["open", file_path])
                    else:
                        subprocess.Popen(["xdg-open", file_path])
                except Exception as e:
                    messagebox.showerror("Error", f"Could not open file: {e}")

    def on_file_select(self, event):
        pass

    def upload_files(self):
        if not self.filepaths[self.selected_folder]:
            messagebox.showwarning("Warning", "Please select files first.")
            return

        for filepath in self.filepaths[self.selected_folder]:
            self.client.send_file(filepath, self.selected_folder)
        messagebox.showinfo("Upload Complete", f"All files uploaded to {self.selected_folder or 'Global'} folder.")
        self.filepaths[self.selected_folder] = []
        self.update_file_listbox()

    def clear_preview(self):
        self.preview_text.delete('1.0', tk.END)
        self.preview_text.pack_forget()
        self.preview_image_label.config(image='')
        self.preview_image_label.pack_forget()

app = App()
app.mainloop()

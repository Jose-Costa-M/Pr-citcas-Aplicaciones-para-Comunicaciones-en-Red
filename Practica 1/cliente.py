import tkinter as tk
from tkinter import messagebox
import socket
import threading
import time

class MinesweeperGUI:
    def __init__(self, master, client_socket):
        self.master = master
        self.client_socket = client_socket
        self.master.title("Buscaminas - Cliente")
        
        self.timer_label = tk.Label(master, text="Tiempo: 00:00", font=("Helvetica", 12))
        self.timer_label.pack_forget()  # Initially hidden

        self.difficulty_frame = tk.Frame(master)
        self.difficulty_frame.pack(pady=10)
        
        tk.Label(self.difficulty_frame, text="Elige el nivel:").pack()
        
        tk.Button(self.difficulty_frame, text="Principiante (9x9, 10 minas)", 
                  command=lambda: self.start_game('principiante')).pack(pady=2)
        tk.Button(self.difficulty_frame, text="Intermedio (16x16, 40 minas)", 
                  command=lambda: self.start_game('intermedio')).pack(pady=2)
        tk.Button(self.difficulty_frame, text="Experto (16x30, 99 minas)", 
                  command=lambda: self.start_game('experto')).pack(pady=2)
        
        self.board_frame = tk.Frame(master)
        self.buttons = []
        self.board = []
        self.rows, self.cols = 0, 0
        self.game_active = False
        self.start_time = None

    def start_game(self, level):
        self.client_socket.send(level.encode('utf-8'))
        self.rows, self.cols = {'principiante': (9, 9), 'intermedio': (16, 16), 'experto': (16, 30)}[level]
        
        self.difficulty_frame.pack_forget()
        self.timer_label.pack(pady=10)
        self.board_frame.pack()

        self.game_active = True
        self.start_time = time.time()
        self.update_timer()
        
        self.board = [['' for _ in range(self.cols)] for _ in range(self.rows)]
        self.buttons = [[None for _ in range(self.cols)] for _ in range(self.rows)]
        
        for row in range(self.rows):
            for col in range(self.cols):
                button = tk.Button(self.board_frame, width=2, height=1)
                button.grid(row=row, column=col)
                button.bind('<Button-1>', lambda e, r=row, c=col: self.send_move(r, c, 'left'))
                button.bind('<Button-3>', lambda e, r=row, c=col: self.send_move(r, c, 'right'))
                self.buttons[row][col] = button

        threading.Thread(target=self.listen_to_server, daemon=True).start()

    def update_timer(self):
        if self.game_active:
            elapsed_time = int(time.time() - self.start_time)
            minutes, seconds = divmod(elapsed_time, 60)
            self.timer_label.config(text=f"Tiempo: {minutes:02}:{seconds:02}")
            self.master.after(1000, self.update_timer)

    def send_move(self, row, col, click_type):
        if self.game_active:
            if click_type == 'left' and self.buttons[row][col].cget("text") == "F":
                self.buttons[row][col].config(text="", state=tk.NORMAL)
                self.client_socket.send(f"{row},{col},remove_flag".encode('utf-8'))
            else:
                move = f"{row},{col},{click_type}"
                self.client_socket.send(move.encode('utf-8'))

    def listen_to_server(self):
        try:
            while True:
                response = self.client_socket.recv(1024).decode('utf-8')
                if "Regresando al menú" in response:
                    messagebox.showinfo("Fin del Juego", response)
                    self.reset_game()
                    break
                elif "Has revelado" in response:
                    parts = response.split(" ")
                    revealed_value = parts[-1]
                    x, y = map(int, parts[-2].strip('()').split(','))
                    self.update_board(x, y, revealed_value)
                elif "Marcado" in response:
                    x, y = map(int, response.split("(")[1].split(")")[0].split(","))
                    self.update_flag(x, y)
                elif "Bandera eliminada" in response:
                    x, y = map(int, response.split("(")[1].split(")")[0].split(","))
                    self.buttons[x][y].config(text="", state=tk.NORMAL)
        except Exception as e:
            print(f"Error: {e}")
            self.game_active = False

    def update_board(self, row, col, value):
        self.buttons[row][col].config(text=value, state=tk.DISABLED)

    def update_flag(self, row, col):
        self.buttons[row][col].config(text="F", fg="red", state=tk.NORMAL)

    def reset_game(self):
        self.board_frame.pack_forget()
        self.difficulty_frame.pack()
        self.game_active = False
        self.timer_label.pack_forget()

def start_client():
    ip = input("Ingrese la dirección IP del servidor: ")
    port = int(input("Ingrese el puerto del servidor: "))

    client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    client_socket.connect((ip, port))

    root = tk.Tk()
    gui = MinesweeperGUI(root, client_socket)
    root.protocol("WM_DELETE_WINDOW", lambda: (client_socket.close(), root.destroy()))
    root.mainloop()

start_client()

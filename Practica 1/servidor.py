#importamos las bibliotecas
import socket #para la conexión
import random #para generar números aleatorios
import sys #para la salida del programa
import time #para medir el tiempo

#definimos un diccionario con los niveles de dificultad con tuplas que contienen el número de filas, columnas y minas
LEVELS = {
    'principiante': (9, 9, 10),
    'intermedio': (16, 16, 40),
    'experto': (16, 30, 99)
}

#función para generar el tablero
def generate_board(rows, cols, mines):
    board = [['0' for _ in range(cols)] for _ in range(rows)] # lista de listas con ceros
    mines_positions = set() # Conjunto de posiciones de minas únicas
    while len(mines_positions) < mines: 
        x, y = random.randint(0, rows - 1), random.randint(0, cols - 1) #generamos posiciones aleatorias
        if (x, y) not in mines_positions: 
            mines_positions.add((x, y)) #agregamos la posición a las minas
            board[x][y] = 'M' #colocamos la mina en la posición
    #Actualización de celdas vecinas
    for x, y in mines_positions: #recorre cada posición de mina en mines_positions
        for i in range(max(0, x-1), min(rows, x+2)): 
            for j in range(max(0, y-1), min(cols, y+2)): #define un rango de posiciones, el máx y el min asegura que no salgan del tablero
                if board[i][j] != 'M': #si la celda no es una mina
                    board[i][j] = str(int(board[i][j]) + 1) #incrementa el valor de la celda en 1
    return board
#función para revelar las celdas adyacentes vacias en el tablero cuando hace click
def reveal_adjacent(board, revealed, x, y):
    if board[x][y] != '0':
        return
    for i in range(max(0, x-1), min(len(board), x+2)):
        for j in range(max(0, y-1), min(len(board[0]), y+2)):
            if revealed[i][j] == ' ' and board[i][j] == '0':
                revealed[i][j] = '0'
                reveal_adjacent(board, revealed, i, j)
            elif board[i][j] != 'M':
                revealed[i][j] = board[i][j]
#función para manejar la interacción servidor cliente
def handle_client(client_socket, board, flag_board, start_time, num_mines):
    revealed = [[' ' for _ in range(len(board[0]))] for _ in range(len(board))] #tablero de celdas reveladas
    
    while True: #para procesar los movimientos del cliente
        try:
            move = client_socket.recv(1024).decode('utf-8') #recibe el movimiento del cliente
            if not move: #si no hay movimiento se rompe el ciclo
                break
            x, y, click_type = move.split(',') #extraemos las coordenadas y el tipo de click
            x, y = int(x), int(y) #convertimos las coordenadas a enteros
            
            if click_type == 'right':  # Flagging 
                flags_count = sum(row.count('F') for row in flag_board) #contamos las banderas en el tablero
                if flags_count < num_mines and flag_board[x][y] != 'F': #si el número de banderas es menor al número de minas y no hay bandera en la celda
                    flag_board[x][y] = 'F' #colocamos la bandera
                    client_socket.send(f"Marcado ({x},{y})".encode('utf-8')) #enviamos un mensaje al cliente
                else:
                    client_socket.send("Número máximo de banderas alcanzado.".encode('utf-8')) #enviamos un mensaje al cliente
            
            elif click_type == 'remove_flag':  # Remove flag
                flag_board[x][y] = '' #eliminamos la bandera
                client_socket.send(f"Bandera eliminada en ({x},{y})".encode('utf-8')) #enviamos un mensaje al cliente
                
            elif click_type == 'left':  # Reveal cell
                if flag_board[x][y] == 'F':  # Left-click on flagged cell removes flag 
                    flag_board[x][y] = '' #eliminamos la bandera
                    client_socket.send(f"Bandera eliminada en ({x},{y})".encode('utf-8')) #enviamos un mensaje al cliente
                elif board[x][y] == 'M': # Left-click on mine ends the game
                    client_socket.send(f"¡Perdiste! Has detonado una mina en ({x},{y}). Regresando al menú.".encode('utf-8')) 
                    break
                else:
                    if board[x][y] == '0': #si la celda es vacía
                        reveal_adjacent(board, revealed, x, y) #revelamos las celdas adyacentes
                    revealed[x][y] = board[x][y] #revelamos la celda
                    if all(revealed[i][j] != ' ' for i in range(len(board)) for j in range(len(board[0])) if board[i][j] != 'M'): #si todas las celdas están reveladas
                        end_time = time.time() #finalizamos el tiempo
                        duration = end_time - start_time #calculamos la duración del juego
                        with open("records.txt", "a") as f: #abrimos el archivo records.txt
                            f.write(f"Game duration: {duration:.2f} seconds\n") #escribimos la duración del juego
                        client_socket.send(f"¡Ganaste! Duración del juego: {duration:.2f} segundos. Regresando al menú.".encode('utf-8')) #enviamos un mensaje al cliente
                        break
                    client_socket.send(f"Has revelado ({x},{y}) {board[x][y]}.".encode('utf-8')) #enviamos un mensaje al cliente
        
        except Exception as e:
            print(f"Error: {e}") #imprimimos el error
            break
#función para iniciar el servidor
def start_server():
    port = int(input("Ingrese el puerto para aceptar jugadores: ")) #pedimos al usuario el puerto
    # BLOCKING FLOW SOCKETS
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM) #creamos el socket del servidor
    server.bind(('0.0.0.0', port)) #asociamos el socket a la dirección y puerto
    server.listen(1)  # One client at a time
    print(f"[*] Servidor escuchando en el puerto {port}") #imprimimos un mensaje

    try:
        while True:
            client_socket, addr = server.accept() #aceptamos la conexión del cliente
            print(f"[*] Conexión aceptada de {addr}") #imprimimos un mensaje
            
            while True:
                client_socket.send("Elige el nivel: principiante, intermedio, experto.".encode('utf-8')) #enviamos un mensaje al cliente
                level = client_socket.recv(1024).decode('utf-8').strip().lower() #recibimos el nivel del cliente
                
                if level in LEVELS: #si el nivel es válido
                    rows, cols, mines = LEVELS[level] #extraemos las filas, columnas y minas del nivel
                    board = generate_board(rows, cols, mines) #generamos el tablero
                    
                    # Print the generated board to the server terminal
                    print("Generated Board:")
                    for row in board:
                        print(" ".join(row))
                    
                    flag_board = [['' for _ in range(cols)] for _ in range(rows)] #tablero de banderas vacio para el cliente
                    start_time = time.time() #iniciamos el tiempo del juego
                    handle_client(client_socket, board, flag_board, start_time, mines) #manejamos la interacción cliente servidor
                else:
                    client_socket.send("Nivel no válido.".encode('utf-8')) #enviamos un mensaje al cliente
                    
    except KeyboardInterrupt: #si se presiona Ctrl+C
        print("\n[*] Servidor detenido.") #imprimimos un mensaje
        server.close() #cerramos el servidor
        sys.exit(0) #salimos del programa

start_server()

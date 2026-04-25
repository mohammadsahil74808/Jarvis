
def display_board(board):
    print(f"| {board[0]} | {board[1]} | {board[2]} |")
    print(f"| {board[3]} | {board[4]} | {board[5]} |")
    print(f"| {board[6]} | {board[7]} | {board[8]} |")

def check_win(board, player):
    win_conditions = [
        (0, 1, 2), (3, 4, 5), (6, 7, 8), # Rows
        (0, 3, 6), (1, 4, 7), (2, 5, 8), # Columns
        (0, 4, 8), (2, 4, 6)             # Diagonals
    ]
    for condition in win_conditions:
        if all(board[i] == player for i in condition):
            return True
    return False

def tic_tac_toe():
    board = [' ' for _ in range(9)]
    current_player = 'X'
    game_running = True
    
    print("Welcome to Tic Tac Toe!")
    
    while game_running:
        display_board(board)
        try:
            move = int(input(f"Player {current_player}, enter your move (1-9): ")) - 1
            
            if 0 <= move <= 8 and board[move] == ' ':
                board[move] = current_player
                
                if check_win(board, current_player):
                    display_board(board)
                    print(f"Player {current_player} wins!")
                    game_running = False
                elif ' ' not in board:
                    display_board(board)
                    print("It's a draw!")
                    game_running = False
                else:
                    current_player = 'O' if current_player == 'X' else 'X'
            else:
                print("Invalid move. Try again.")
        except ValueError:
            print("Invalid input. Please enter a number between 1 and 9.")

if __name__ == "__main__":
    tic_tac_toe()

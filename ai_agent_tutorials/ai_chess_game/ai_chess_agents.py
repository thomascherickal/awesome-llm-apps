import chess
import chess.svg
import streamlit as st
from autogen import ConversableAgent, register_function

# Initialize session state for the OpenAI API key and game state
if "openai_api_key" not in st.session_state:
    st.session_state.openai_api_key = None
if "board" not in st.session_state:
    st.session_state.board = chess.Board()
if "made_move" not in st.session_state:
    st.session_state.made_move = False
if "board_svg" not in st.session_state:
    st.session_state.board_svg = None
if "move_history" not in st.session_state:
    st.session_state.move_history = []

# Streamlit sidebar for OpenAI API key input
st.sidebar.title("Chess Agent Configuration")
openai_api_key = st.sidebar.text_input("Enter your OpenAI API key:", type="password")
if openai_api_key:
    st.session_state.openai_api_key = openai_api_key
    st.sidebar.success("API key saved!")

# Function to get legal moves
def available_moves() -> str:
    available_moves = [str(move) for move in st.session_state.board.legal_moves]
    return "Available moves are: " + ",".join(available_moves)

# Function to make a move
def make_move(move: str) -> str:
    try:
        chess_move = chess.Move.from_uci(move)
        if chess_move not in st.session_state.board.legal_moves:
            return f"Invalid move: {move}. Please call get_legal_moves() to see valid moves."
        
        st.session_state.board.push(chess_move)
        st.session_state.made_move = True

        # Render board visualization
        board_svg = chess.svg.board(
            st.session_state.board,
            arrows=[(chess_move.from_square, chess_move.to_square)],
            fill={chess_move.from_square: "gray"},
            size=400
        )
        st.session_state.board_svg = board_svg  # Save SVG to session state
        st.session_state.move_history.append(board_svg)  # Save move history

        # Get moved piece details
        moved_piece = st.session_state.board.piece_at(chess_move.to_square)
        piece_unicode = moved_piece.unicode_symbol()
        piece_type_name = chess.piece_name(moved_piece.piece_type)
        piece_name = piece_type_name.capitalize() if piece_unicode.isupper() else piece_type_name
        
        # Build move description
        move_desc = f"Moved {piece_name} ({piece_unicode}) from {chess.SQUARE_NAMES[chess_move.from_square]} to {chess.SQUARE_NAMES[chess_move.to_square]}."
        
        # Check game state
        if st.session_state.board.is_checkmate():
            winner = 'White' if st.session_state.board.turn == chess.BLACK else 'Black'
            move_desc += f"\nCheckmate! {winner} wins!"
        elif st.session_state.board.is_stalemate():
            move_desc += "\nGame ended in stalemate!"
        elif st.session_state.board.is_insufficient_material():
            move_desc += "\nGame ended - insufficient material to checkmate!"
        elif st.session_state.board.is_check():
            move_desc += "\nCheck!"

        return move_desc
    except ValueError:
        return f"Invalid move format: {move}. Please use UCI format (e.g., 'e2e4')."

# Check if the player has made a move, and reset the flag if move is made.
def check_made_move(msg):
    if st.session_state.made_move:
        st.session_state.made_move = False
        return True
    else:
        return False

# Initialize players and proxy agent if API key is provided
if st.session_state.openai_api_key:
    try:
        player_white_config_list = [
            {
                "model": "gpt-4o-mini",
                "api_key": st.session_state.openai_api_key,
            },
        ]

        player_black_config_list = [
            {
                "model": "gpt-4o-mini",
                "api_key": st.session_state.openai_api_key,
            },
        ]

        player_white = ConversableAgent(
            name="Player_White",  
            system_message="You are a professional chess player and you play as white. "
            "First call get_legal_moves() first, to get list of legal moves. "
            "Then call make_move(move) to make a move.",
            llm_config={"config_list": player_white_config_list, "cache_seed": None},
        )

        player_black = ConversableAgent(
            name="Player_Black",  
            system_message="You are a professional chess player and you play as black. "
            "First call get_legal_moves() first, to get list of legal moves. "
            "Then call make_move(move) to make a move.",
            llm_config={"config_list": player_black_config_list, "cache_seed": None},
        )

        # Proxy agent to manage the board and validate moves
        board_proxy = ConversableAgent(
            name="Board_Proxy",  
            llm_config=False,
            is_termination_msg=check_made_move,
            default_auto_reply="Please make a move.",
            human_input_mode="NEVER",
        )

        # Register functions for both players
        register_function(
            make_move,
            caller=player_white,
            executor=board_proxy,
            name="make_move",
            description="Call this tool to make a move.",
        )

        register_function(
            available_moves,
            caller=player_white,
            executor=board_proxy,
            name="available_moves",
            description="Get legal moves.",
        )

        register_function(
            make_move,
            caller=player_black,
            executor=board_proxy,
            name="make_move",
            description="Call this tool to make a move.",
        )

        register_function(
            available_moves,
            caller=player_black,
            executor=board_proxy,
            name="available_moves",
            description="Get legal moves.",
        )

        # Register nested chats for both players
        player_white.register_nested_chats(
            trigger=player_black,
            chat_queue=[
                {
                    "sender": board_proxy,
                    "recipient": player_white,
                    "summary_method": "last_msg",
                }
            ],
        )

        player_black.register_nested_chats(
            trigger=player_white,
            chat_queue=[
                {
                    "sender": board_proxy,
                    "recipient": player_black,
                    "summary_method": "last_msg",
                }
            ],
        )

        # Streamlit UI for playing the game
        st.title("Chess with AG2 Agents")
        st.info("""
This chess game is played between two AutoGen AI agents:
- **Player White**: A GPT-4o-mini powered chess player controlling white pieces
- **Player Black**: A GPT-4o-mini powered chess player controlling black pieces

The game is managed by a **Board Proxy Agent** that:
- Validates all moves
- Updates the chess board
- Manages turn-taking between players
- Provides legal move information
""")

        # Display the initial board state before the game starts
        initial_board_svg = chess.svg.board(st.session_state.board, size=300)
        st.subheader("Initial Board")
        st.image(initial_board_svg)

        if st.button("Start Game"):
            st.session_state.board.reset()
            st.session_state.made_move = False
            st.session_state.move_history = []  # Reset move history
            st.session_state.board_svg = chess.svg.board(st.session_state.board, size=300)
            st.info("The AI agents will now play against each other. Each agent will analyze the board, " 
                   "request legal moves, and make strategic decisions.")
            st.write("Game started! White's turn.")

            # Initiate the chat between Player_White and Board_Proxy
            chat_result = player_black.initiate_chat(
                recipient=player_white, 
                message="Let's play chess! You go first, its your move.",
                max_turns=5, 
                summary_method="reflection_with_llm"
            )
            st.markdown(chat_result.summary)

            # Display the move history (boards for each move)
            st.subheader("Move History")
            for i, move_svg in enumerate(st.session_state.move_history):
                st.write(f"Move {i + 1}")
                st.image(move_svg)

        # Reset Game button
        if st.button("Reset Game"):
            st.session_state.board.reset()
            st.session_state.made_move = False
            st.session_state.move_history = []
            st.session_state.board_svg = None
            st.write("Game reset! Click 'Start Game' to begin a new game.")

    except Exception as e:
        st.error(f"An error occurred: {e}. Please check your API key and try again.")

else:
    st.warning("Please enter your OpenAI API key in the sidebar to start the game.")
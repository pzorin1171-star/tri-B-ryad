from flask import Flask, request
from flask_socketio import SocketIO, emit, join_room, leave_room
import os
import random
import time

app = Flask(__name__)
app.config['SECRET_KEY'] = 'match3-multiplayer-competition'

socketio = SocketIO(app, cors_allowed_origins="*")

# Хранилище игр и игроков
games = {}
players = {}

# Типы фишек
TILE_TYPES = ['red', 'blue', 'green', 'yellow', 'purple']
MAX_PLAYERS = 4  # Максимум игроков в комнате
BOARD_WIDTH = 8
BOARD_HEIGHT = 8

def create_game_board():
    """Создает игровое поле без начальных совпадений"""
    board = []
    for _ in range(BOARD_HEIGHT):
        row = [random.choice(TILE_TYPES) for _ in range(BOARD_WIDTH)]
        board.append(row)
    
    # Убеждаемся, что нет начальных совпадений
    while check_matches(board):
        board = []
        for _ in range(BOARD_HEIGHT):
            row = [random.choice(TILE_TYPES) for _ in range(BOARD_WIDTH)]
            board.append(row)
    
    return board

def check_matches(board):
    """Проверяет совпадения на поле"""
    matches = set()
    
    # Проверка горизонтальных совпадений
    for row in range(BOARD_HEIGHT):
        for col in range(BOARD_WIDTH - 2):
            if (board[row][col] == board[row][col + 1] == board[row][col + 2] and 
                board[row][col] is not None):
                matches.add((row, col))
                matches.add((row, col + 1))
                matches.add((row, col + 2))
    
    # Проверка вертикальных совпадений
    for row in range(BOARD_HEIGHT - 2):
        for col in range(BOARD_WIDTH):
            if (board[row][col] == board[row + 1][col] == board[row + 2][col] and 
                board[row][col] is not None):
                matches.add((row, col))
                matches.add((row + 1, col))
                matches.add((row + 2, col))
    
    return list(matches)

def remove_matches_and_refill(board, matches):
    """Удаляет совпадения и заполняет поле новыми фишками"""
    # Удаляем совпадения
    for row, col in matches:
        board[row][col] = None
    
    # Фишки падают вниз
    for col in range(BOARD_WIDTH):
        empty_cells = []
        for row in range(BOARD_HEIGHT - 1, -1, -1):
            if board[row][col] is None:
                empty_cells.append(row)
            elif empty_cells:
                lowest_empty = empty_cells.pop(0)
                board[lowest_empty][col] = board[row][col]
                board[row][col] = None
                empty_cells.append(row)
    
    # Заполняем пустые места новыми фишками
    for col in range(BOARD_WIDTH):
        for row in range(BOARD_HEIGHT):
            if board[row][col] is None:
                board[row][col] = random.choice(TILE_TYPES)
    
    return board

def is_valid_move(board, row1, col1, row2, col2):
    """Проверяет валидность хода (только соседние клетки)"""
    if (row1 < 0 or row1 >= BOARD_HEIGHT or col1 < 0 or col1 >= BOARD_WIDTH or
        row2 < 0 or row2 >= BOARD_HEIGHT or col2 < 0 or col2 >= BOARD_WIDTH):
        return False
    
    # Проверяем, что клетки соседние
    if abs(row1 - row2) + abs(col1 - col2) != 1:
        return False
    
    return True

def swap_tiles(board, row1, col1, row2, col2):
    """Меняет фишки местами"""
    board[row1][col1], board[row2][col2] = board[row2][col2], board[row1][col1]
    return board

def get_player_position(game, player_id):
    """Возвращает позицию игрока в списке (1, 2, 3, ...)"""
    if player_id in game['players']:
        return game['players'].index(player_id) + 1
    return 0

@app.route('/')
def home():
    return '''
    <!DOCTYPE html>
    <html>
    <head>
        <title>Три в ряд - Соревнование</title>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <style>
            * {
                box-sizing: border-box;
                margin: 0;
                padding: 0;
                font-family: 'Arial', sans-serif;
            }
            
            body {
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                min-height: 100vh;
                display: flex;
                justify-content: center;
                align-items: center;
                padding: 20px;
            }
            
            .container {
                background: white;
                border-radius: 15px;
                padding: 30px;
                box-shadow: 0 10px 30px rgba(0,0,0,0.2);
                max-width: 900px;
                width: 100%;
                text-align: center;
            }
            
            h1 {
                color: #333;
                margin-bottom: 20px;
                font-size: 2.5em;
            }
            
            .game-info {
                margin: 15px 0;
            }
            
            .players-board {
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
                gap: 15px;
                margin: 20px 0;
            }
            
            .player-card {
                padding: 15px;
                border-radius: 10px;
                background: #f8f9fa;
                transition: all 0.3s;
                border: 3px solid transparent;
            }
            
            .player-card.current {
                background: #e3f2fd;
                border-color: #2196f3;
                transform: scale(1.05);
            }
            
            .player-card .player-name {
                font-weight: bold;
                font-size: 1.2em;
                margin-bottom: 10px;
            }
            
            .player-card .player-score {
                font-size: 1.5em;
                color: #333;
            }
            
            .game-board {
                display: grid;
                grid-template-columns: repeat(8, 60px);
                gap: 3px;
                margin: 25px auto;
                justify-content: center;
                background: #f0f0f0;
                padding: 10px;
                border-radius: 10px;
            }
            
            .tile {
                width: 60px;
                height: 60px;
                border: 2px solid #ddd;
                border-radius: 8px;
                cursor: pointer;
                display: flex;
                align-items: center;
                justify-content: center;
                font-size: 24px;
                transition: all 0.2s;
                background: white;
            }
            
            .tile.red { background: #ff6b6b; }
            .tile.blue { background: #4ecdc4; }
            .tile.green { background: #a3d9a5; }
            .tile.yellow { background: #ffe66d; }
            .tile.purple { background: #b19cd9; }
            
            .tile.selected {
                border: 3px solid #333;
                transform: scale(0.95);
                box-shadow: 0 0 10px rgba(0,0,0,0.3);
            }
            
            .tile.matched {
                animation: pulse 0.5s;
            }
            
            @keyframes pulse {
                0% { transform: scale(1); }
                50% { transform: scale(1.1); }
                100% { transform: scale(1); }
            }
            
            .status {
                margin: 20px 0;
                padding: 15px;
                border-radius: 10px;
                font-size: 18px;
                font-weight: bold;
            }
            
            .waiting { background: #fff3cd; color: #856404; }
            .playing { background: #d4edda; color: #155724; }
            .my-turn { background: #cce5ff; color: #004085; }
            
            .controls {
                margin: 20px 0;
            }
            
            input, button {
                padding: 12px 20px;
                margin: 8px;
                border: 2px solid #ddd;
                border-radius: 8px;
                font-size: 16px;
            }
            
            input {
                width: 250px;
                text-align: center;
            }
            
            button {
                background: #667eea;
                color: white;
                border: none;
                cursor: pointer;
                transition: background 0.3s;
                font-weight: bold;
            }
            
            button:hover {
                background: #5a6fd8;
                transform: translateY(-2px);
            }
            
            button:disabled {
                background: #ccc;
                cursor: not-allowed;
                transform: none;
            }
            
            .hidden {
                display: none;
            }
            
            .room-info {
                background: #e9ecef;
                padding: 10px;
                border-radius: 8px;
                margin: 10px 0;
                font-size: 14px;
            }
            
            @media (max-width: 768px) {
                .container {
                    padding: 20px;
                }
                
                .game-board {
                    grid-template-columns: repeat(8, 40px);
                }
                
                .tile {
                    width: 40px;
                    height: 40px;
                    font-size: 18px;
                }
                
                h1 {
                    font-size: 2em;
                }
                
                input {
                    width: 200px;
                }
            }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>🎮 Три в ряд - Соревнование</h1>
            
            <div id="connectSection">
                <div class="game-info">
                    <input type="text" id="roomInput" value="competition-room" placeholder="Название комнаты">
                    <input type="text" id="playerName" placeholder="Ваше имя" maxlength="15">
                    <button onclick="connectToGame()">Присоединиться к соревнованию</button>
                </div>
                <div id="status" class="status waiting">
                    Введите название комнаты и ваше имя
                </div>
                <div class="room-info">
                    Максимум игроков: 4 | Победа при 500 очках
                </div>
            </div>
            
            <div id="gameSection" class="hidden">
                <div class="players-board" id="playersBoard"></div>
                
                <div id="gameStatus" class="status waiting">Подготовка к игре...</div>
                
                <div class="game-board" id="gameBoard"></div>
                
                <div class="controls">
                    <button onclick="leaveGame()">Покинуть соревнование</button>
                </div>
            </div>
        </div>

        <script src="https://cdn.socket.io/4.5.0/socket.io.min.js"></script>
        <script>
            let socket = null;
            let currentRoom = '';
            let myPlayerId = '';
            let myPlayerName = '';
            let currentPlayer = '';
            let gameBoard = [];
            let selectedTile = null;
            let players = {};
            let gameActive = false;
            
            function connectToGame() {
                currentRoom = document.getElementById('roomInput').value.trim() || 'default';
                myPlayerName = document.getElementById('playerName').value.trim() || 'Игрок';
                
                if (myPlayerName.length === 0) {
                    alert('Пожалуйста, введите ваше имя');
                    return;
                }
                
                if (socket) {
                    socket.disconnect();
                }
                
                socket = io();
                
                socket.on('connect', function() {
                    updateStatus('Подключено к серверу', 'playing');
                    socket.emit('join_room', { 
                        room: currentRoom,
                        playerName: myPlayerName
                    });
                });
                
                socket.on('joined', function(data) {
                    myPlayerId = data.playerId;
                    players = data.players;
                    
                    updateStatus(data.message, 'playing');
                    document.getElementById('connectSection').classList.add('hidden');
                    document.getElementById('gameSection').classList.remove('hidden');
                    
                    updatePlayersBoard();
                });
                
                socket.on('player_joined', function(data) {
                    players = data.players;
                    updatePlayersBoard();
                    updateStatus(`Игрок ${data.playerName} присоединился! (${Object.keys(players).length}/4 игроков)`, 'playing');
                });
                
                socket.on('player_left', function(data) {
                    players = data.players;
                    updatePlayersBoard();
                    updateStatus(`Игрок ${data.playerName} покинул игру`, 'waiting');
                });
                
                socket.on('game_start', function(data) {
                    gameBoard = data.board;
                    currentPlayer = data.currentPlayer;
                    gameActive = true;
                    updateBoard();
                    updateGameStatus();
                });
                
                socket.on('board_update', function(data) {
                    gameBoard = data.board;
                    currentPlayer = data.currentPlayer;
                    players = data.players;
                    updateBoard();
                    updatePlayersBoard();
                    updateGameStatus();
                    
                    // Анимация для совпадений
                    if (data.matches && data.matches.length > 0) {
                        animateMatches(data.matches);
                    }
                });
                
                socket.on('move_result', function(data) {
                    if (!data.valid) {
                        alert('Неверный ход! ' + data.message);
                    }
                });
                
                socket.on('game_over', function(data) {
                    gameActive = false;
                    let message = '';
                    
                    if (data.winner === myPlayerId) {
                        message = '🎉 Поздравляем! Вы победили! 🎉';
                    } else if (data.winner === 'draw') {
                        message = 'Ничья!';
                    } else {
                        const winnerName = players[data.winner]?.name || 'Неизвестный игрок';
                        message = `Победил ${winnerName}! Сыграем еще?`;
                    }
                    
                    updateStatus(message, 'playing');
                    
                    // Автоперезапуск через 5 секунд
                    setTimeout(() => {
                        socket.emit('restart_game', { room: currentRoom });
                    }, 5000);
                });
                
                socket.on('error', function(data) {
                    updateStatus('Ошибка: ' + data.message, 'waiting');
                });
            }
            
            function updatePlayersBoard() {
                const playersBoard = document.getElementById('playersBoard');
                playersBoard.innerHTML = '';
                
                Object.keys(players).forEach(playerId => {
                    const player = players[playerId];
                    const playerCard = document.createElement('div');
                    playerCard.className = 'player-card';
                    
                    if (playerId === currentPlayer) {
                        playerCard.classList.add('current');
                    }
                    
                    if (playerId === myPlayerId) {
                        playerCard.style.background = '#e8f5e8';
                    }
                    
                    playerCard.innerHTML = `
                        <div class="player-name">${player.name} ${playerId === myPlayerId ? '(Вы)' : ''}</div>
                        <div class="player-score">${player.score} очков</div>
                        <div style="font-size: 0.9em; color: #666;">${player.position || ''}</div>
                    `;
                    
                    playersBoard.appendChild(playerCard);
                });
            }
            
            function updateBoard() {
                const boardElement = document.getElementById('gameBoard');
                boardElement.innerHTML = '';
                
                for (let row = 0; row < gameBoard.length; row++) {
                    for (let col = 0; col < gameBoard[row].length; col++) {
                        const tile = document.createElement('div');
                        tile.className = `tile ${gameBoard[row][col]}`;
                        tile.dataset.row = row;
                        tile.dataset.col = col;
                        tile.onclick = () => selectTile(row, col);
                        boardElement.appendChild(tile);
                    }
                }
            }
            
            function selectTile(row, col) {
                if (!gameActive || currentPlayer !== myPlayerId) return;
                
                const tileElement = document.querySelector(`[data-row="${row}"][data-col="${col}"]`);
                
                if (!selectedTile) {
                    // Первое нажатие - выбираем фишку
                    selectedTile = { row, col };
                    tileElement.classList.add('selected');
                } else {
                    // Второе нажатие - пытаемся поменять фишки
                    const firstTile = document.querySelector(`[data-row="${selectedTile.row}"][data-col="${selectedTile.col}"]`);
                    firstTile.classList.remove('selected');
                    
                    // Проверяем, что фишки соседние
                    const rowDiff = Math.abs(selectedTile.row - row);
                    const colDiff = Math.abs(selectedTile.col - col);
                    
                    if ((rowDiff === 1 && colDiff === 0) || (rowDiff === 0 && colDiff === 1)) {
                        socket.emit('make_move', {
                            room: currentRoom,
                            from: selectedTile,
                            to: { row, col }
                        });
                    }
                    
                    selectedTile = null;
                }
            }
            
            function animateMatches(matches) {
                matches.forEach(([row, col]) => {
                    const tile = document.querySelector(`[data-row="${row}"][data-col="${col}"]`);
                    if (tile) {
                        tile.classList.add('matched');
                        setTimeout(() => {
                            tile.classList.remove('matched');
                        }, 500);
                    }
                });
            }
            
            function updateGameStatus() {
                const statusElement = document.getElementById('gameStatus');
                
                if (!gameActive) {
                    statusElement.textContent = 'Игра не активна';
                    statusElement.className = 'status waiting';
                    return;
                }
                
                if (currentPlayer === myPlayerId) {
                    statusElement.textContent = '🎯 Ваш ход! Выберите две соседние фишки для обмена';
                    statusElement.className = 'status my-turn';
                } else {
                    const currentPlayerName = players[currentPlayer]?.name || 'Соперник';
                    statusElement.textContent = `⏳ Ход игрока ${currentPlayerName}...`;
                    statusElement.className = 'status waiting';
                }
            }
            
            function updateStatus(message, type) {
                const statusElement = document.getElementById('status');
                statusElement.textContent = message;
                statusElement.className = 'status ' + type;
            }
            
            function leaveGame() {
                if (socket) {
                    socket.emit('leave_room', { room: currentRoom });
                    socket.disconnect();
                }
                document.getElementById('gameSection').classList.add('hidden');
                document.getElementById('connectSection').classList.remove('hidden');
                updateStatus('Введите название комнаты и ваше имя', 'waiting');
            }
        </script>
    </body>
    </html>
    '''

@app.route('/health')
def health():
    return {'status': 'healthy', 'active_games': len(games)}

@socketio.on('connect')
def handle_connect():
    print(f'Player connected: {request.sid}')

@socketio.on('disconnect')
def handle_disconnect():
    print(f'Player disconnected: {request.sid}')
    if request.sid in players:
        player_data = players[request.sid]
        room = player_data['room']
        
        if room in games:
            game = games[room]
            
            # Удаляем игрока из игры
            if request.sid in game['players']:
                player_name = game['players'][request.sid]['name']
                del game['players'][request.sid]
                
                # Уведомляем других игроков
                emit('player_left', {
                    'playerName': player_name,
                    'players': game['players']
                }, room=room)
                
                # Если игроков не осталось, удаляем игру
                if len(game['players']) == 0:
                    del games[room]
                # Если остался 1 игрок, завершаем игру
                elif len(game['players']) == 1 and game['game_active']:
                    remaining_player_id = list(game['players'].keys())[0]
                    emit('game_over', {'winner': remaining_player_id}, room=room)
                    game['game_active'] = False
        
        del players[request.sid]

@socketio.on('join_room')
def handle_join_room(data):
    room = data.get('room', 'default')
    player_name = data.get('playerName', 'Игрок')
    
    join_room(room)
    players[request.sid] = {
        'room': room,
        'name': player_name
    }
    
    if room not in games:
        # Создаем новую игру
        games[room] = {
            'players': {},
            'board': create_game_board(),
            'current_player': None,
            'game_active': False,
            'move_count': 0
        }
    
    game = games[room]
    
    # Проверяем, не заполнена ли комната
    if len(game['players']) >= MAX_PLAYERS:
        emit('error', {'message': 'Комната заполнена (максимум 4 игрока)'})
        leave_room(room)
        return
    
    # Добавляем игрока
    game['players'][request.sid] = {
        'name': player_name,
        'score': 0,
        'position': len(game['players']) + 1
    }
    
    # Уведомляем игрока о успешном присоединении
    emit('joined', {
        'playerId': request.sid,
        'message': f'Вы присоединились к комнате. Игроков: {len(game["players"])}/{MAX_PLAYERS}',
        'players': game['players']
    })
    
    # Уведомляем других игроков
    emit('player_joined', {
        'playerName': player_name,
        'players': game['players']
    }, room=room, include_self=False)
    
    # Если игроков достаточно, начинаем игру
    if len(game['players']) >= 2 and not game['game_active']:
        start_game(room)

def start_game(room):
    """Начинает игру в комнате"""
    if room not in games:
        return
    
    game = games[room]
    game['game_active'] = True
    game['move_count'] = 0
    
    # Выбираем случайного первого игрока
    player_ids = list(game['players'].keys())
    game['current_player'] = random.choice(player_ids)
    
    # Сбрасываем очки
    for player_id in game['players']:
        game['players'][player_id]['score'] = 0
    
    print(f'Game started in room {room} with {len(player_ids)} players')
    
    # Уведомляем всех игроков
    emit('game_start', {
        'board': game['board'],
        'currentPlayer': game['current_player'],
        'players': game['players']
    }, room=room)

@socketio.on('make_move')
def handle_make_move(data):
    room = data.get('room')
    from_pos = data.get('from')
    to_pos = data.get('to')
    
    if room not in games:
        emit('move_result', {'valid': False, 'message': 'Игра не найдена'})
        return
    
    game = games[room]
    
    # Проверяем, что ход делает текущий игрок
    if game['current_player'] != request.sid:
        emit('move_result', {'valid': False, 'message': 'Не ваш ход'})
        return
    
    # Проверяем валидность хода
    if not is_valid_move(game['board'], from_pos['row'], from_pos['col'], to_pos['row'], to_pos['col']):
        emit('move_result', {'valid': False, 'message': 'Неверный ход'})
        return
    
    # Меняем фишки местами
    game['board'] = swap_tiles(game['board'], from_pos['row'], from_pos['col'], to_pos['row'], to_pos['col'])
    
    # Проверяем совпадения
    matches = check_matches(game['board'])
    
    if matches:
        # Начисляем очки
        points = len(matches) * 10
        game['players'][request.sid]['score'] += points
        game['move_count'] += 1
        
        # Удаляем совпадения и заполняем поле
        game['board'] = remove_matches_and_refill(game['board'], matches)
        
        # Проверяем каскадные совпадения
        cascade_matches = check_matches(game['board'])
        while cascade_matches:
            points = len(cascade_matches) * 10
            game['players'][request.sid]['score'] += points
            game['board'] = remove_matches_and_refill(game['board'], cascade_matches)
            cascade_matches = check_matches(game['board'])
        
        # Проверяем условие победы
        winner = check_winner(game)
        if winner:
            emit('game_over', {'winner': winner}, room=room)
            game['game_active'] = False
        else:
            # Передаем ход следующему игроку
            next_player(room)
            
            # Обновляем поле для всех игроков
            emit('board_update', {
                'board': game['board'],
                'currentPlayer': game['current_player'],
                'players': game['players'],
                'matches': matches
            }, room=room)
    else:
        # Если нет совпадений, отменяем ход
        game['board'] = swap_tiles(game['board'], from_pos['row'], from_pos['col'], to_pos['row'], to_pos['col'])
        emit('move_result', {'valid': False, 'message': 'Нет совпадений'})

def next_player(room):
    """Передает ход следующему игроку"""
    if room not in games:
        return
    
    game = games[room]
    player_ids = list(game['players'].keys())
    
    if not player_ids:
        return
    
    current_index = player_ids.index(game['current_player'])
    next_index = (current_index + 1) % len(player_ids)
    game['current_player'] = player_ids[next_index]

def check_winner(game):
    """Проверяет, достиг ли какой-либо игрок условия победы"""
    # Победа при 500 очках
    for player_id, player_data in game['players'].items():
        if player_data['score'] >= 500:
            return player_id
    
    # Если сделано 50 ходов, побеждает игрок с наибольшим количеством очков
    if game['move_count'] >= 50:
        max_score = -1
        winner = None
        
        for player_id, player_data in game['players'].items():
            if player_data['score'] > max_score:
                max_score = player_data['score']
                winner = player_id
            elif player_data['score'] == max_score:
                # Ничья, если несколько игроков с одинаковым счетом
                winner = 'draw'
        
        return winner
    
    return None

@socketio.on('leave_room')
def handle_leave_room(data):
    room = data.get('room')
    leave_room(room)
    
    if request.sid in players:
        del players[request.sid]

@socketio.on('restart_game')
def handle_restart_game(data):
    room = data.get('room')
    if room in games:
        game = games[room]
        if len(game['players']) >= 2:
            # Пересоздаем игру
            game['board'] = create_game_board()
            start_game(room)

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 10000))
    print(f"🎮 Сервер 'Три в ряд - Соревнование' запущен на порту {port}")
    print(f"👥 Максимальное количество игроков в комнате: {MAX_PLAYERS}")
    socketio.run(app, host='0.0.0.0', port=port, debug=False, allow_unsafe_werkzeug=True)

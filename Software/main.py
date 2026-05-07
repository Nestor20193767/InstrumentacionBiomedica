from flask import Flask, render_template, request
from flask_socketio import SocketIO, emit, join_room, leave_room

# Inicialización de la app Flask y SocketIO
app = Flask(__name__)
app.config['SECRET_KEY'] = 'clave_secreta_para_sesiones_seguras'

# cors_allowed_origins="*" permite conexiones desde cualquier origen (útil en desarrollo local con ngrok/celulares)
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='eventlet')

# --- RUTAS HTTP ---

@app.route('/')
def index():
    """Renderiza el frontend principal (Dashboard, Leaderboard, Rooms)"""
    return render_template('index.html')


# --- EVENTOS WEBSOCKET (SALAS DE ESTUDIO Y WEARABLE) ---

@socketio.on('join_study_room')
def handle_join_room(data):
    """Maneja cuando un usuario se une a una sala de estudio colaborativo"""
    room = data.get('room_code')
    user = data.get('username', 'Usuario Anonimo')
    
    join_room(room)
    
    # Notificar a los demás en la sala que alguien entró
    emit('user_joined', {'message': f'{user} se ha unido a la sala.', 'user': user}, to=room)
    print(f"[{request.sid}] {user} se unió a la sala: {room}")

@socketio.on('leave_study_room')
def handle_leave_room(data):
    """Maneja la salida de un usuario de la sala"""
    room = data.get('room_code')
    user = data.get('username', 'Usuario Anonimo')
    
    leave_room(room)
    
    # Notificar a los demás en la sala
    emit('user_left', {'message': f'{user} ha salido de la sala.', 'user': user}, to=room)
    print(f"[{request.sid}] {user} abandonó la sala: {room}")

@socketio.on('wearable_data_sync')
def handle_wearable_data(data):
    """
    (Opcional) Recibe los datos fisiológicos desde el cliente (Web Bluetooth API) 
    y los retransmite a la sala para métricas compartidas o promedios grupales.
    """
    room = data.get('room_code')
    stress_level = data.get('stress_level')
    user = data.get('username')
    
    # Retransmitir la métrica de estrés/HRV a los demás participantes de la sala
    emit('update_peer_stress', {'user': user, 'stress_level': stress_level}, to=room)


# --- EJECUCIÓN DEL SERVIDOR ---

if __name__ == '__main__':
    print("Iniciando servidor StudySync en http://0.0.0.0:5000")
    # debug=True recarga el servidor automáticamente si haces cambios en el código
    # host='0.0.0.0' permite que la app sea accesible desde otros dispositivos en tu red local
    socketio.run(app, host='0.0.0.0', port=5000, debug=True)
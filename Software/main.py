import eventlet
eventlet.monkey_patch()   # debe ir ANTES de cualquier otro import de red

from flask import Flask, render_template, request, jsonify
from flask_socketio import SocketIO, emit, join_room, leave_room
import math
import time
import random
import string

# ─────────────────────────────────────────────────────────────
#  Inicialización
# ─────────────────────────────────────────────────────────────
app = Flask(__name__)
app.config['SECRET_KEY'] = 'clave_secreta_para_sesiones_seguras'

socketio = SocketIO(
    app,
    cors_allowed_origins="*",
    async_mode='eventlet',
    ping_timeout=60,   # Tolerancia de 60 segundos para el lag de ngrok
    ping_interval=25   # Latido cada 25 segundos
)

# ─────────────────────────────────────────────────────────────
#  Almacenes en memoria
# ─────────────────────────────────────────────────────────────
sessions: dict = {}

# rooms[code] = {
#   'created_at': float,
#   'members': {
#       sid: { 'username': str, 'avatar_seed': str,
#              'stress_level': str|None, 'rmssd': float|None }
#   }
# }
# La sala persiste mientras tenga al menos 1 miembro.
# Se elimina SOLO cuando el último miembro sale o se desconecta.
rooms: dict = {}


# ═════════════════════════════════════════════════════════════
#  UTILIDADES
# ═════════════════════════════════════════════════════════════

def generate_room_code(length: int = 6) -> str:
    """Genera código alfanumérico único de 6 caracteres en mayúsculas."""
    chars = string.ascii_uppercase + string.digits
    while True:
        code = ''.join(random.choices(chars, k=length))
        if code not in rooms:
            return code


def room_members_payload(code: str) -> list:
    """Serializa la lista de miembros de una sala para emitir al cliente."""
    if code not in rooms:
        return []
    return [
        {
            'sid':          sid,
            'username':     m['username'],
            'avatar_seed':  m['avatar_seed'],
            'stress_level': m['stress_level'],
            'rmssd':        m['rmssd'],
        }
        for sid, m in rooms[code]['members'].items()
    ]


def broadcast_members(code: str):
    """Emite la lista actualizada de miembros a toda la sala."""
    socketio.emit(
        'room_members',
        {'members': room_members_payload(code), 'room_code': code},
        to=code,
    )


def broadcast_system(code: str, msg: str):
    """Emite un mensaje de sistema a toda la sala."""
    socketio.emit('system_message', {'message': msg}, to=code)


# ═════════════════════════════════════════════════════════════
#  FUNCIONES DE HRV / RMSSD
# ═════════════════════════════════════════════════════════════

def compute_rmssd(rr_intervals: list) -> float:
    """RMSSD = sqrt( 1/(N-1) * Σ (RR_{i+1} - RR_i)² )"""
    n = len(rr_intervals)
    if n < 2:
        return 0.0
    diffs_sq = [(rr_intervals[i+1] - rr_intervals[i])**2 for i in range(n-1)]
    return round(math.sqrt(sum(diffs_sq) / (n-1)), 2)


def clean_rr_artifacts(rr_intervals: list) -> list:
    """Descarta intervalos que se desvíen >20% de la mediana local."""
    if not rr_intervals:
        return []
    s = sorted(rr_intervals)
    mid = len(s) // 2
    median = s[mid] if len(s) % 2 != 0 else (s[mid-1] + s[mid]) / 2
    threshold = 0.20 * median
    return [rr for rr in rr_intervals if abs(rr - median) <= threshold]


def classify_stress(rmssd_current: float, baseline_rmssd: float) -> dict:
    """Clasifica el nivel de estrés por variación % respecto al baseline."""
    if not baseline_rmssd:
        return {'level': 'Desconocido', 'variation_pct': 0.0, 'color': 'gray'}
    variation_pct = abs((rmssd_current - baseline_rmssd) / baseline_rmssd * 100)
    if variation_pct < 15:
        level, color = 'Normal', '#10B981'
    elif variation_pct < 30:
        level, color = 'Moderado', '#F59E0B'
    else:
        level, color = 'Elevado', '#EF4444'
    return {'level': level, 'variation_pct': round(variation_pct, 2), 'color': color}


def compute_ies(session: dict) -> dict:
    """IES = T_efectivo - P_estres + B_descanso + B_retorno"""
    elapsed    = time.time() - session.get('session_start', time.time())
    t_efectivo = session.get('effective_seconds', 0) // 60
    p_estres   = session.get('stress_penalty_periods', 0) * 5
    b_descanso = session.get('rest_accepted', 0) * 3
    b_retorno  = session.get('rest_returned', 0) * 2
    ies = max(0, t_efectivo - p_estres + b_descanso + b_retorno)
    return {
        'ies':            ies,
        'xp':             ies * 10,
        't_efectivo_min': t_efectivo,
        'p_estres':       p_estres,
        'b_descanso':     b_descanso,
        'b_retorno':      b_retorno,
        'duration_sec':   int(elapsed),
    }


# ═════════════════════════════════════════════════════════════
#  RUTAS HTTP
# ═════════════════════════════════════════════════════════════

@app.route('/')
def index():
    return render_template('index.html')


@app.route('/api/health')
def health():
    return jsonify({
        'status':          'ok',
        'sessions_active': len(sessions),
        'rooms_active':    len(rooms),
    })


@app.route('/api/room/<code>')
def room_info(code: str):
    """Verifica si una sala existe (útil para links compartidos)."""
    if code in rooms:
        return jsonify({'exists': True, 'member_count': len(rooms[code]['members'])})
    return jsonify({'exists': False}), 404


# ═════════════════════════════════════════════════════════════
#  WEBSOCKET — CONEXIÓN / DESCONEXIÓN
# ═════════════════════════════════════════════════════════════

@socketio.on('connect')
def handle_connect():
    sessions[request.sid] = {
        'baseline_rmssd':            None,
        'baseline_captured':         False,
        'baseline_window':           [],
        'session_start':             None,
        'effective_seconds':         0,
        'consecutive_high_windows':  0,
        'sustained_high_minutes':    0,
        'rest_accepted':             0,
        'rest_returned':             0,
        'stress_penalty_periods':    0,
        'rr_buffer':                 [],
        'window_count':              0,
        'eva_score':                 None,
        'confounders':               {},
        'current_room':              None,
        'username':                  'Anónimo',
    }
    print(f"[CONNECT] {request.sid}")


@socketio.on('disconnect')
def handle_disconnect():
    sid      = request.sid
    session  = sessions.get(sid, {})
    room_code = session.get('current_room')

    if room_code and room_code in rooms:
        username = rooms[room_code]['members'].get(sid, {}).get('username', 'Alguien')
        rooms[room_code]['members'].pop(sid, None)

        if not rooms[room_code]['members']:
            del rooms[room_code]
            print(f"[ROOM DELETED] {room_code} — vacía")
        else:
            broadcast_members(room_code)
            broadcast_system(room_code, f'{username} se desconectó.')

    sessions.pop(sid, None)
    print(f"[DISCONNECT] {sid}")


# ═════════════════════════════════════════════════════════════
#  WEBSOCKET — HRV / SESIÓN
# ═════════════════════════════════════════════════════════════

@socketio.on('submit_eva')
def handle_eva(data):
    sid = request.sid
    if sid not in sessions:
        return
    sessions[sid]['eva_score']   = data.get('eva', 5)
    sessions[sid]['confounders'] = {
        'caffeine': data.get('caffeine', False),
        'sleep':    data.get('sleep', False),
        'exercise': data.get('exercise', False),
    }
    emit('eva_saved', {'ok': True})


@socketio.on('rr_data')
def handle_rr_data(data):
    sid = request.sid
    if sid not in sessions:
        return

    session  = sessions[sid]
    clean_rr = clean_rr_artifacts(data.get('rr_intervals', []))

    # ── Fase baseline ──────────────────────────────────────
    if not session['baseline_captured']:
        session['baseline_window'].extend(clean_rr)
        if len(session['baseline_window']) >= 300:
            baseline_val = compute_rmssd(session['baseline_window'])
            session['baseline_rmssd']    = baseline_val
            session['baseline_captured'] = True
            session['session_start']     = time.time()
            emit('baseline_ready', {'baseline_rmssd': baseline_val})
        else:
            pct = round(len(session['baseline_window']) / 300 * 100)
            emit('baseline_progress', {'pct': pct})
        return

    # ── Fase monitoreo ─────────────────────────────────────
    session['rr_buffer'].extend(clean_rr)

    if len(session['rr_buffer']) >= 2:
        window = session['rr_buffer'][-20:] if len(session['rr_buffer']) >= 20 else session['rr_buffer']
        instant_rmssd  = compute_rmssd(window)
        classification = classify_stress(instant_rmssd, session['baseline_rmssd'])
        emit('rmssd_update', {'rmssd': instant_rmssd, **classification})

        if classification['variation_pct'] < 30:
            session['effective_seconds'] += 1

        # Sincronizar nivel de estrés a la sala
        room_code = session.get('current_room')
        if room_code and room_code in rooms and sid in rooms[room_code]['members']:
            rooms[room_code]['members'][sid]['stress_level'] = classification['level']
            rooms[room_code]['members'][sid]['rmssd']        = instant_rmssd
            broadcast_members(room_code)

    if len(session['rr_buffer']) >= 75:
        window_rmssd   = compute_rmssd(session['rr_buffer'])
        classification = classify_stress(window_rmssd, session['baseline_rmssd'])
        session['rr_buffer']    = []
        session['window_count'] += 1

        if classification['level'] == 'Elevado':
            session['consecutive_high_windows'] += 1
        else:
            session['consecutive_high_windows'] = 0

        if session['consecutive_high_windows'] >= 2:
            session['sustained_high_minutes'] += 5
            if session['sustained_high_minutes'] >= 10:
                emit('rest_alert', {'sustained_minutes': session['sustained_high_minutes']})

        emit('window_result', {
            'window_number': session['window_count'],
            'rmssd':         window_rmssd,
            **classification,
        })


@socketio.on('rest_response')
def handle_rest_response(data):
    sid = request.sid
    if sid not in sessions:
        return
    if data.get('accepted', False):
        sessions[sid]['rest_accepted']           += 1
        sessions[sid]['sustained_high_minutes']   = 0
        sessions[sid]['consecutive_high_windows'] = 0
        emit('rest_response_ack', {'ok': True})
    else:
        sessions[sid]['stress_penalty_periods'] += 1
        emit('rest_response_ack', {'ok': False})


@socketio.on('rest_return')
def handle_rest_return():
    sid = request.sid
    if sid not in sessions:
        return
    sessions[sid]['rest_returned'] += 1
    emit('return_ack', {'ok': True})


@socketio.on('end_session')
def handle_end_session():
    sid = request.sid
    if sid not in sessions:
        return
    result = compute_ies(sessions[sid])
    emit('session_summary', result)
    print(f"[SESSION END] {sid} → IES={result['ies']} XP={result['xp']}")


# ═════════════════════════════════════════════════════════════
#  WEBSOCKET — SALAS DE ESTUDIO
# ═════════════════════════════════════════════════════════════

@socketio.on('create_room')
def handle_create_room(data):
    """
    Crea una sala nueva y devuelve el código al creador.
    data = { 'username': str, 'avatar_seed': str }
    """
    sid      = request.sid
    username = data.get('username', 'Anónimo')
    avatar   = data.get('avatar_seed', username[:2].upper())
    code     = generate_room_code()

    rooms[code] = {
        'created_at': time.time(),
        'members': {
            sid: {
                'username':     username,
                'avatar_seed':  avatar,
                'stress_level': None,
                'rmssd':        None,
            }
        },
    }

    if sid in sessions:
        sessions[sid]['current_room'] = code
        sessions[sid]['username']     = username

    join_room(code)
    emit('room_created', {'room_code': code, 'member_count': 1})
    # Emitir lista inicial solo al creador
    emit('room_members', {'members': room_members_payload(code), 'room_code': code})
    print(f"[ROOM CREATED] {code} por {username} ({sid})")


@socketio.on('join_study_room')
def handle_join_room(data):
    """
    Une a un usuario a una sala existente.
    data = { 'room_code': str, 'username': str, 'avatar_seed': str }
    """
    sid      = request.sid
    code     = data.get('room_code', '').strip().upper()
    username = data.get('username', 'Anónimo')
    avatar   = data.get('avatar_seed', username[:2].upper())

    if code not in rooms:
        emit('room_error', {'message': f'La sala "{code}" no existe. Verifica el código.'})
        return

    rooms[code]['members'][sid] = {
        'username':     username,
        'avatar_seed':  avatar,
        'stress_level': None,
        'rmssd':        None,
    }

    if sid in sessions:
        sessions[sid]['current_room'] = code
        sessions[sid]['username']     = username

    join_room(code)

    # Primero notificar al nuevo que entró con éxito
    emit('room_joined', {'room_code': code, 'member_count': len(rooms[code]['members'])})

    # Luego broadcast de lista completa a TODA la sala
    broadcast_members(code)
    broadcast_system(code, f'{username} se unió a la sala.')
    print(f"[JOIN] {username} ({sid}) → sala {code}")


@socketio.on('leave_study_room')
def handle_leave_room(data):
    """
    Saca a un usuario de su sala actual.
    data = { 'room_code': str }
    """
    sid  = request.sid

    # Obtener código: del payload o del estado de sesión (fallback)
    code = data.get('room_code', '').strip().upper()
    if not code and sid in sessions:
        code = sessions[sid].get('current_room', '') or ''

    # Si el código no existe en rooms, igual emitir room_left para limpiar el cliente
    if not code or code not in rooms:
        emit('room_left', {'room_code': code})
        if sid in sessions:
            sessions[sid]['current_room'] = None
        return

    username = rooms[code]['members'].get(sid, {}).get('username', 'Alguien')

    # PASO 1: notificar al cliente que salió (mientras aún está en el room de socketio)
    emit('room_left', {'room_code': code})

    # PASO 2: limpiar sesión
    if sid in sessions:
        sessions[sid]['current_room'] = None

    # PASO 3: quitar de la lista de miembros
    rooms[code]['members'].pop(sid, None)

    # PASO 4: salir del room de socketio
    leave_room(code)

    # PASO 5: si la sala quedó vacía, borrarla; si no, notificar a los restantes
    if not rooms[code]['members']:
        del rooms[code]
        print(f"[ROOM DELETED] {code} — vacía")
    else:
        broadcast_members(code)
        broadcast_system(code, f'{username} salió de la sala.')

    print(f"[LEAVE] {username} ({sid}) ← sala {code}")


@socketio.on('wearable_data_sync')
def handle_wearable_data(data):
    """Canal directo para sincronizar estrés a la sala sin pasar por rr_data."""
    sid  = request.sid
    code = data.get('room_code', '').strip().upper()
    if code in rooms and sid in rooms[code]['members']:
        rooms[code]['members'][sid]['stress_level'] = data.get('stress_level')
        rooms[code]['members'][sid]['rmssd']        = data.get('rmssd')
        broadcast_members(code)


# ═════════════════════════════════════════════════════════════
#  EJECUCIÓN
# ═════════════════════════════════════════════════════════════

if __name__ == '__main__':
    print("Iniciando StudySync en http://0.0.0.0:5000")
    socketio.run(app, host='0.0.0.0', port=5000, debug=True)

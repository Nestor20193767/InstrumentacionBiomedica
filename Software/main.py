from flask import Flask, render_template, request, jsonify
from flask_socketio import SocketIO, emit, join_room, leave_room
import math
import time

# ─────────────────────────────────────────────────────────────
#  Inicialización
# ─────────────────────────────────────────────────────────────
app = Flask(__name__)
app.config['SECRET_KEY'] = 'clave_secreta_para_sesiones_seguras'

socketio = SocketIO(app, cors_allowed_origins="*")

# ─────────────────────────────────────────────────────────────
#  Almacén en memoria de sesiones activas
#  Estructura por sid:
#  {
#    'baseline_rmssd': float,
#    'baseline_captured': bool,
#    'baseline_window': [float, ...],   # valores RR durante baseline
#    'session_start': float,            # timestamp
#    'effective_seconds': int,
#    'consecutive_high_windows': int,
#    'sustained_high_minutes': int,
#    'rest_accepted': int,
#    'rest_returned': int,
#    'stress_penalty_periods': int,
#    'rr_buffer': [float, ...],         # buffer RR inter-latido (ms) para ventana actual
#    'window_count': int,
#    'eva_score': int,
#    'confounders': dict,
#  }
# ─────────────────────────────────────────────────────────────
sessions: dict = {}


# ═════════════════════════════════════════════════════════════
#  FUNCIONES DE HRV / RMSSD
# ═════════════════════════════════════════════════════════════

def compute_rmssd(rr_intervals: list[float]) -> float:
    """
    RMSSD = sqrt( 1/(N-1) * Σ (RR_{i+1} - RR_i)² )
    rr_intervals: lista de intervalos RR en milisegundos.
    Retorna RMSSD en ms; retorna 0.0 si hay menos de 2 intervalos.
    """
    n = len(rr_intervals)
    if n < 2:
        return 0.0
    successive_diffs_sq = [(rr_intervals[i + 1] - rr_intervals[i]) ** 2
                           for i in range(n - 1)]
    rmssd = math.sqrt(sum(successive_diffs_sq) / (n - 1))
    return round(rmssd, 2)


def clean_rr_artifacts(rr_intervals: list[float]) -> list[float]:
    """
    Elimina latidos ectópicos y artefactos:
    descarta intervalos que se desvíen >20% de la mediana local.
    """
    if not rr_intervals:
        return []
    sorted_rr = sorted(rr_intervals)
    mid = len(sorted_rr) // 2
    median = (sorted_rr[mid] if len(sorted_rr) % 2 != 0
              else (sorted_rr[mid - 1] + sorted_rr[mid]) / 2)
    threshold = 0.20 * median
    return [rr for rr in rr_intervals if abs(rr - median) <= threshold]


def classify_stress(rmssd_current: float, baseline_rmssd: float) -> dict:
    """
    Clasifica el nivel de estrés según la variación porcentual del RMSSD
    respecto al baseline.

    Returns:
        dict con 'level' (str), 'variation_pct' (float), 'color' (str)
    """
    if baseline_rmssd == 0:
        return {'level': 'Desconocido', 'variation_pct': 0.0, 'color': 'gray'}

    variation_pct = abs((rmssd_current - baseline_rmssd) / baseline_rmssd * 100)

    if variation_pct < 15:
        level, color = 'Normal', '#10B981'
    elif variation_pct < 30:
        level, color = 'Moderado', '#F59E0B'
    else:
        level, color = 'Elevado', '#EF4444'

    return {
        'level': level,
        'variation_pct': round(variation_pct, 2),
        'color': color,
    }


def compute_ies(session: dict) -> dict:
    """
    IES = T_efectivo - P_estres_sostenido + B_descanso_aceptado + B_retorno

    Pesos:
      T_efectivo           → minutos con variación RMSSD < 30%
      P_estres_sostenido   → -5 pts por cada período ≥10 min ignorado
      B_descanso_aceptado  → +3 pts por descanso aceptado a tiempo
      B_retorno            → +2 pts por retorno completado
    """
    elapsed = time.time() - session.get('session_start', time.time())
    t_efectivo = session.get('effective_seconds', 0) // 60
    p_estres   = session.get('stress_penalty_periods', 0) * 5
    b_descanso = session.get('rest_accepted', 0) * 3
    b_retorno  = session.get('rest_returned', 0) * 2

    ies = max(0, t_efectivo - p_estres + b_descanso + b_retorno)
    xp  = ies * 10

    return {
        'ies': ies,
        'xp': xp,
        't_efectivo_min': t_efectivo,
        'p_estres': p_estres,
        'b_descanso': b_descanso,
        'b_retorno': b_retorno,
        'duration_sec': int(elapsed),
    }


# ═════════════════════════════════════════════════════════════
#  RUTAS HTTP
# ═════════════════════════════════════════════════════════════

@app.route('/')
def index():
    """Renderiza el frontend principal."""
    return render_template('index.html')


@app.route('/api/health')
def health():
    return jsonify({'status': 'ok', 'sessions_active': len(sessions)})


# ═════════════════════════════════════════════════════════════
#  EVENTOS WEBSOCKET — SESIÓN Y HRV
# ═════════════════════════════════════════════════════════════

@socketio.on('connect')
def handle_connect():
    """Inicializa el estado de sesión para el cliente conectado."""
    sessions[request.sid] = {
        'baseline_rmssd': None,
        'baseline_captured': False,
        'baseline_window': [],
        'session_start': None,
        'effective_seconds': 0,
        'consecutive_high_windows': 0,
        'sustained_high_minutes': 0,
        'rest_accepted': 0,
        'rest_returned': 0,
        'stress_penalty_periods': 0,
        'rr_buffer': [],
        'window_count': 0,
        'eva_score': None,
        'confounders': {},
    }
    print(f"[CONNECT] {request.sid}")


@socketio.on('disconnect')
def handle_disconnect():
    sessions.pop(request.sid, None)
    print(f"[DISCONNECT] {request.sid}")


@socketio.on('submit_eva')
def handle_eva(data):
    """
    Recibe la puntuación EVA y los factores confundentes del usuario.
    data = { 'eva': int(0-10), 'caffeine': bool, 'sleep': bool, 'exercise': bool }
    """
    sid = request.sid
    if sid not in sessions:
        return
    sessions[sid]['eva_score']   = data.get('eva', 5)
    sessions[sid]['confounders'] = {
        'caffeine': data.get('caffeine', False),
        'sleep':    data.get('sleep',    False),
        'exercise': data.get('exercise', False),
    }
    emit('eva_saved', {'ok': True})


@socketio.on('rr_data')
def handle_rr_data(data):
    """
    Recibe un lote de intervalos RR desde el cliente (vía BLE → Web Bluetooth → WS).
    data = { 'rr_intervals': [float, ...] }  — intervalos en ms

    Lógica:
      1. Acumula en buffer de ventana actual.
      2. Si no hay baseline, acumula hasta tener suficiente señal (≥ 250 muestras ≈ 5 min a 250 Hz).
      3. Si ya hay baseline, calcula RMSSD de ventana, clasifica y emite al cliente.
    """
    sid = request.sid
    if sid not in sessions:
        return

    session = sessions[sid]
    raw_rr  = data.get('rr_intervals', [])
    clean_rr = clean_rr_artifacts(raw_rr)

    # ── Fase baseline (primeros 5 minutos de señal válida) ──────────
    if not session['baseline_captured']:
        session['baseline_window'].extend(clean_rr)

        # 250 Hz × 300 s = 75 000 puntos de ECG → aprox 300-400 intervalos RR
        # Usamos 300 intervalos como umbral práctico
        if len(session['baseline_window']) >= 300:
            baseline_val = compute_rmssd(session['baseline_window'])
            session['baseline_rmssd']    = baseline_val
            session['baseline_captured'] = True
            session['session_start']     = time.time()
            emit('baseline_ready', {
                'baseline_rmssd': baseline_val,
                'message': 'Baseline capturado. Iniciando monitoreo.',
            })
        else:
            # Progreso del baseline
            pct = round(len(session['baseline_window']) / 300 * 100)
            emit('baseline_progress', {'pct': pct})
        return

    # ── Fase monitoreo (ventanas de 5 minutos ≈ 75 intervalos RR) ───
    session['rr_buffer'].extend(clean_rr)

    # Emitir RMSSD instantáneo con cada lote para animación ECG
    if len(session['rr_buffer']) >= 2:
        instant_rmssd = compute_rmssd(session['rr_buffer'][-20:] if len(session['rr_buffer']) >= 20
                                       else session['rr_buffer'])
        classification = classify_stress(instant_rmssd, session['baseline_rmssd'])
        emit('rmssd_update', {
            'rmssd': instant_rmssd,
            **classification,
        })

        # Tiempo efectivo: solo cuenta si variación < 30%
        if classification['variation_pct'] < 30:
            session['effective_seconds'] += 1  # aprox 1 s por lote BLE

    # ── Cierre de ventana de análisis (≥75 intervalos RR ≈ 5 min) ──
    if len(session['rr_buffer']) >= 75:
        window_rmssd   = compute_rmssd(session['rr_buffer'])
        classification = classify_stress(window_rmssd, session['baseline_rmssd'])
        session['rr_buffer'] = []
        session['window_count'] += 1

        if classification['level'] == 'Elevado':
            session['consecutive_high_windows'] += 1
        else:
            session['consecutive_high_windows'] = 0

        # ≥2 ventanas consecutivas elevadas = ≥10 min de estrés sostenido
        if session['consecutive_high_windows'] >= 2:
            session['sustained_high_minutes'] += 5
            if session['sustained_high_minutes'] >= 10:
                emit('rest_alert', {
                    'message': 'Estrés elevado sostenido ≥10 min. Recomendamos un descanso.',
                    'sustained_minutes': session['sustained_high_minutes'],
                })

        emit('window_result', {
            'window_number': session['window_count'],
            'rmssd': window_rmssd,
            **classification,
        })


@socketio.on('rest_response')
def handle_rest_response(data):
    """
    data = { 'accepted': bool }
    Si accepted=True: bono de descanso + resetear contadores de estrés.
    Si accepted=False: penalización.
    """
    sid = request.sid
    if sid not in sessions:
        return

    session = sessions[sid]
    accepted = data.get('accepted', False)

    if accepted:
        session['rest_accepted']           += 1
        session['sustained_high_minutes']   = 0
        session['consecutive_high_windows'] = 0
        emit('rest_response_ack', {
            'ok': True,
            'message': 'Bono de descanso registrado. Regresa cuando estés listo.',
        })
    else:
        session['stress_penalty_periods'] += 1
        emit('rest_response_ack', {
            'ok': False,
            'message': 'Penalización aplicada por ignorar la alerta.',
        })


@socketio.on('rest_return')
def handle_rest_return():
    """El usuario regresó después del descanso y completó la pausa mínima de 5 min."""
    sid = request.sid
    if sid not in sessions:
        return

    # Verificar recuperación: RMSSD debe haber alcanzado el 85% del baseline
    # (la verificación real ocurre en rr_data; aquí solo registramos el retorno)
    sessions[sid]['rest_returned'] += 1
    emit('return_ack', {'ok': True, 'message': 'Bono de retorno registrado. ¡Bienvenido de vuelta!'})


@socketio.on('end_session')
def handle_end_session():
    """Finaliza la sesión, calcula IES y lo emite al cliente."""
    sid = request.sid
    if sid not in sessions:
        return

    result = compute_ies(sessions[sid])
    emit('session_summary', result)
    print(f"[SESSION END] {sid} → IES={result['ies']}  XP={result['xp']}")


# ═════════════════════════════════════════════════════════════
#  EVENTOS WEBSOCKET — SALAS DE ESTUDIO COLABORATIVAS
# ═════════════════════════════════════════════════════════════

@socketio.on('join_study_room')
def handle_join_room(data):
    """Maneja cuando un usuario se une a una sala de estudio colaborativo."""
    room = data.get('room_code')
    user = data.get('username', 'Usuario Anónimo')

    join_room(room)
    emit('user_joined', {'message': f'{user} se unió a la sala.', 'user': user}, to=room)
    print(f"[JOIN] {request.sid} / {user} → sala {room}")


@socketio.on('leave_study_room')
def handle_leave_room(data):
    """Maneja la salida de un usuario de la sala."""
    room = data.get('room_code')
    user = data.get('username', 'Usuario Anónimo')

    leave_room(room)
    emit('user_left', {'message': f'{user} salió de la sala.', 'user': user}, to=room)
    print(f"[LEAVE] {request.sid} / {user} ← sala {room}")


@socketio.on('wearable_data_sync')
def handle_wearable_data(data):
    """
    Recibe datos fisiológicos del cliente (BLE → Frontend) y los
    retransmite a la sala para métricas grupales compartidas.
    """
    room         = data.get('room_code')
    stress_level = data.get('stress_level')
    rmssd        = data.get('rmssd')
    user         = data.get('username', 'Anónimo')

    emit('update_peer_stress', {
        'user':         user,
        'stress_level': stress_level,
        'rmssd':        rmssd,
    }, to=room)


# ═════════════════════════════════════════════════════════════
#  EJECUCIÓN
# ═════════════════════════════════════════════════════════════

if __name__ == '__main__':
    print("Iniciando StudySync en http://0.0.0.0:8000")
    # Añadimos el parámetro allow_unsafe_werkzeug=True al final:
    socketio.run(app, host='0.0.0.0', port=5000, debug=True, allow_unsafe_werkzeug=True)

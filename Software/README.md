
# StudySync ⏱️🧠

Plataforma web de gamificación y estudio colaborativo en tiempo real. Integra métricas fisiológicas (estrés/HRV) a través de dispositivos wearables para monitorizar la carga cognitiva de los usuarios durante sus sesiones de enfoque.

## 🏗️ Arquitectura del Sistema

El proyecto emplea una arquitectura modular (microfrontends) que separa la interfaz en componentes independientes, con un flujo de datos bidireccional optimizado para el procesamiento en tiempo real de bioseñales.


[ Wearable (RP2040 / BLE) ]
            │
            │ (Web Bluetooth API)
            ▼
[ Frontend (Navegador Móvil/Tablet) ] 
  ├─ Microfrontend: Dashboard (Métricas)
  ├─ Microfrontend: Leaderboard
  └─ Microfrontend: Study Rooms
            │
            │ (WebSockets / Socket.IO)
            ▼
[ Backend (Servidor Flask) ]
  └─ Eventlet (Servidor Asíncrono)

---

##📂 Estructura Inicial del Proyecto
Plaintext
StudySync/
│
├── main.py                # Servidor principal Flask y configuración WebSocket
├── requirements.txt       # Dependencias de Python
└── templates/
    └── index.html         # Interfaz orquestadora (Microfrontends + JS)

    ---
##🛠️ Stack Tecnológico y Librerías
Backend (Python)
Flask: Framework ligero para servir la aplicación web.

Flask-SocketIO: Habilita la comunicación bidireccional y de baja latencia entre el cliente y el servidor. Esencial para la sincronización de temporizadores en las "Salas de Estudio".

Eventlet: Servidor asíncrono de alto rendimiento. Flask-SocketIO lo requiere para manejar múltiples conexiones concurrentes sin bloquear el hilo principal.

Frontend
Bootstrap 5: Framework CSS utilizado para el diseño responsive (mobile-first), ideal para visualización en celulares y tablets.

Web Bluetooth API: API nativa de JavaScript (sin dependencias externas) que permite al navegador conectarse directamente al servidor GATT del wearable para recibir datos fisiológicos vía Bluetooth Low Energy (BLE).

Socket.IO Client: Librería de JS para establecer la conexión WebSocket con el servidor Flask.

##🚀 Despliegue y Ejecución Local (Pruebas con Hardware)
Debido a estrictas políticas de seguridad de los navegadores modernos, el Web Bluetooth API solo funciona bajo un contexto seguro (HTTPS). Para probar la conexión con el wearable desde tu celular hacia tu servidor local, utilizaremos ngrok.

Paso 1: Instalar dependencias e iniciar el servidor
Bash
# Crear y activar entorno virtual (opcional pero recomendado)
uv venv
source .venv/bin/activate  # En Windows: .venv\Scripts\activate

# Instalar librerías
pip install -r requirements.txt

# Iniciar el servidor (¡No usar 'flask run'!)
python main.py
El servidor iniciará en http://localhost:5000 o http://0.0.0.0:5000.

Paso 2: Exponer el servidor con HTTPS (ngrok)
En una nueva terminal, ejecuta:

Bash
ngrok http 5000
Paso 3: Probar en el celular
Copia la URL generada por ngrok (ejemplo: https://abcd-123.ngrok.app).

Ábrela en el navegador (Chrome) de tu celular o tablet.

Enciende tu wearable y presiona el botón "Conectar Wearable" en la interfaz para iniciar el emparejamiento Bluetooth.

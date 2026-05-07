
````markdown
# StudySync ⏱️🧠

> Plataforma web de estudio colaborativo y gamificación en tiempo real que integra métricas fisiológicas (estrés y HRV) mediante dispositivos *wearables* para monitorear la carga cognitiva durante sesiones de enfoque.

---

# ✨ Características Principales

- 📚 Salas de estudio colaborativas en tiempo real.
- 🧠 Monitoreo de estrés y variabilidad cardíaca (HRV).
- 📊 Dashboard de métricas fisiológicas y productividad.
- 🏆 Sistema de gamificación y leaderboard.
- 📱 Diseño responsive (*mobile-first*).
- 🔗 Integración BLE (*Bluetooth Low Energy*) con wearables RP2040.
- ⚡ Comunicación en tiempo real mediante WebSockets.

---

# 🏗️ Arquitectura del Sistema

El proyecto utiliza una arquitectura modular basada en **microfrontends**, permitiendo desacoplar funcionalidades independientes y optimizar el procesamiento de bioseñales en tiempo real.

```text
[ Wearable (RP2040 / BLE) ]
            │
            │ Web Bluetooth API
            ▼
[ Frontend (Mobile / Tablet Browser) ]
  ├── Dashboard (Métricas)
  ├── Leaderboard
  └── Study Rooms
            │
            │ WebSockets / Socket.IO
            ▼
[ Backend (Flask Server) ]
  └── Eventlet (Servidor Asíncrono)
````

---

# 📂 Estructura Inicial del Proyecto

```text
StudySync/
│
├── main.py                # Servidor principal Flask + configuración Socket.IO
├── requirements.txt       # Dependencias Python
└── templates/
    └── index.html         # Interfaz principal y orquestación de microfrontends
```

---

# 🛠️ Stack Tecnológico

## Backend (Python)

### Flask

Framework web ligero utilizado para servir la aplicación y gestionar rutas HTTP.

### Flask-SocketIO

Permite comunicación bidireccional en tiempo real entre cliente y servidor. Fundamental para sincronizar sesiones y temporizadores colaborativos.

### Eventlet

Servidor asíncrono de alto rendimiento requerido por Flask-SocketIO para manejar múltiples conexiones concurrentes sin bloquear el hilo principal.

---

## Frontend

### Bootstrap 5

Framework CSS utilizado para construir una interfaz responsive optimizada para celulares y tablets.

### Web Bluetooth API

API nativa de JavaScript que permite conectarse directamente a dispositivos BLE desde el navegador sin dependencias externas.

### Socket.IO Client

Cliente JavaScript encargado de establecer y mantener la conexión WebSocket con el backend Flask.

---

# 🚀 Ejecución Local y Pruebas con Hardware

> ⚠️ **Importante:**
> La Web Bluetooth API solo funciona bajo un contexto seguro (**HTTPS**) debido a las políticas de seguridad de los navegadores modernos.

Para probar la conexión BLE desde un celular hacia tu servidor local, se recomienda utilizar **ngrok**.

---

## 1️⃣ Instalar dependencias e iniciar el servidor

```bash
# Crear entorno virtual (opcional pero recomendado)
uv venv

# Activar entorno virtual
source .venv/bin/activate

# Windows
.venv\Scripts\activate

# Instalar dependencias
pip install -r requirements.txt

# Iniciar servidor
python main.py
```

El servidor quedará disponible en:

```text
http://localhost:5000
```

o

```text
http://0.0.0.0:5000
```

---

## 2️⃣ Exponer el servidor mediante HTTPS usando ngrok

En una nueva terminal:

```bash
ngrok http 5000
```

ngrok generará una URL HTTPS similar a:

```text
https://abcd-123.ngrok.app
```

---

## 3️⃣ Probar desde el celular o tablet

1. Abrir la URL HTTPS generada por ngrok en **Google Chrome**.
2. Encender el wearable BLE.
3. Presionar el botón **"Conectar Wearable"** en la interfaz.
4. Aceptar el emparejamiento Bluetooth.

---

# 📡 Flujo de Datos

```text
Wearable BLE
   ↓
Web Bluetooth API
   ↓
Frontend Dashboard
   ↓
Socket.IO
   ↓
Backend Flask
   ↓
Broadcast en tiempo real a Study Rooms y Leaderboards
```

---

# 🔮 Roadmap

* [ ] Persistencia de métricas en base de datos.
* [ ] Autenticación de usuarios.
* [ ] Historial de sesiones de estudio.
* [ ] IA para análisis de fatiga cognitiva.
* [ ] Integración con más dispositivos wearables.
* [ ] Sistema avanzado de recompensas y logros.

---

# 🤝 Contribuciones

Las contribuciones son bienvenidas.
Puedes abrir un *issue* o enviar un *pull request* para proponer mejoras.

---

# 📄 Licencia

Este proyecto se distribuye bajo la licencia MIT.

```
```

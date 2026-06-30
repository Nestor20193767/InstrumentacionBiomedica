
# StudySync ⏱️🧠

> Plataforma web de estudio colaborativo y gamificación en tiempo real que integra métricas fisiológicas (estrés y HRV) mediante dispositivos *wearables* para monitorear la carga cognitiva durante sesiones de enfoque.

---

# ✨ Características Principales

- 📚 Salas de estudio colaborativas en tiempo real.
- 🧠 Monitoreo de estrés y variabilidad cardíaca (HRV) basado en RMSSD.
- 📊 Dashboard de métricas fisiológicas y productividad (Índice de Eficiencia de Estudio - IES).
- 🏆 Sistema de gamificación y recompensa por experiencia (XP).
- 📱 Diseño responsive (*mobile-first*).
- 🔗 Integración BLE (*Bluetooth Low Energy*) con dispositivos biomédicos (ej. HealthyPi 5 / RP2040).
- ⚡ Comunicación en tiempo real mediante WebSockets (Flask-SocketIO) adaptada para desarrollo ágil.

---

# 🏗️ Arquitectura del Sistema y Red

El proyecto utiliza una arquitectura modular que conecta el hardware biomédico con un backend en Flask, permitiendo procesar bioseñales en tiempo real sin saturar la experiencia del usuario.

```text
[ Wearable (HealthyPi 5 / BLE) ]
            │
            │ Web Bluetooth API (Filtros: Pasa-altas, Pasa-bajas, Notch 60 Hz)
            ▼
[ Frontend (Dashboard Web) ]
  ├── Animación de ECG e Ingesta de Lotes RR
  ├── Formulario EVA (Escala Visual Analógica) y Confundidores
  └── Study Rooms (Salas Colaborativas)
            │
            │ WebSockets / Socket.IO (Tráfico bidireccional en tiempo real)
            ▼
[ Puerto Local 5000 ] <─── [ Túnel Seguro NGROK ] <─── [ Internet / Dispositivo Móvil ]
            │
            ▼
[ Backend (Flask Server) ]
  └── Procesamiento HRV (Filtro de artefactos, Cómputo de RMSSD, Algoritmo IES)
````

### 🔌 ¿Por qué usamos Flask-SocketIO y ngrok juntos?

1. **Flask-SocketIO (El Motor de Tiempo Real):** A diferencia de las peticiones HTTP convencionales donde el cliente debe preguntar constantemente si hay cambios, Socket.IO mantiene un canal abierto y bidireccional. Permite que en cuanto el backend detecte **estrés elevado sostenido (≥10 min)**, emita inmediatamente una alerta (`rest_alert`) hacia el frontend de forma instantánea.

2. **ngrok (El Puente de Red Seguro):** Cuando corres Flask en tu entorno local, el servidor solo es accesible en tu propia máquina (`localhost:5000`). Para conectar un celular real, una tablet o probar el emparejamiento Web Bluetooth (que **exige estrictamente un origen seguro HTTPS**), ngrok crea un túnel público inverso en internet redirigiendo el tráfico de forma segura hacia tu puerto local.

---

# 📂 Estructura del Proyecto

```text
StudySync/
│
├── main.py                # Servidor Flask, gestión de estados de sesión y eventos WebSocket
├── requirements.txt       # Dependencias del proyecto (Flask, Flask-SocketIO, etc.)
└── templates/
    └── index.html         # Dashboard principal, gráficos en Canvas y orquestación de Web Bluetooth
```

---

# 🚀 Guía de Instalación y Despliegue Local

Sigue estos pasos detallados para configurar y ejecutar el entorno de desarrollo en tu máquina.

## 1️⃣ Clonar o posicionarse en el proyecto

Abre tu terminal (o PowerShell si estás en PyCharm) y asegúrate de estar dentro de la carpeta raíz del proyecto:

```powershell
cd proyecto_intrus
```

## 2️⃣ Crear el Entorno Virtual (`.venv`)

### En Windows

```powershell
py -m venv .venv
```

### En macOS / Linux

```bash
python3 -m venv .venv
```

## 3️⃣ Activar el Entorno Virtual

### Windows (PowerShell)

```powershell
.\.venv\Scripts\Activate.ps1
```

> Si aparece un error de permisos de ejecución, ejecuta primero:

```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope Process
```

### Windows (CMD)

```cmd
.\.venv\Scripts\activate.bat
```

### macOS / Linux

```bash
source .venv/bin/activate
```

Cuando el entorno esté activo aparecerá el prefijo `(.venv)` en la consola.

## 4️⃣ Instalar Dependencias

```powershell
pip install -r requirements.txt
```

## 5️⃣ Levantar el Servidor Flask

```powershell
python main.py
```

El servidor se iniciará en el puerto **5000** utilizando `allow_unsafe_werkzeug=True`.

---

# 🌐 Configuración del Túnel con ngrok (Pruebas en Dispositivos Reales)

1. Abre una nueva terminal.
2. Ejecuta:

```bash
ngrok http 5000
```

3. Copia la URL HTTPS generada (por ejemplo `https://xxxx-xxxx.ngrok-free.app`).
4. Ábrela desde Google Chrome en tu dispositivo móvil para utilizar Web Bluetooth.

---

# 🔄 Flujo de Usuario Completo

```mermaid
flowchart TD

%%==========================
%% ESTILOS
%%==========================

classDef start fill:#7c3aed,stroke:#4c1d95,color:#ffffff,stroke-width:2px;
classDef process fill:#2563eb,stroke:#1e40af,color:#ffffff,stroke-width:2px;
classDef decision fill:#059669,stroke:#065f46,color:#ffffff,stroke-width:2px;
classDef warning fill:#dc2626,stroke:#991b1b,color:#ffffff,stroke-width:2px;
classDef success fill:#16a34a,stroke:#166534,color:#ffffff,stroke-width:2px;
classDef end fill:#ea580c,stroke:#9a3412,color:#ffffff,stroke-width:2px;

%%==========================
%% PASO 1
%%==========================

A([🟢 Usuario abre la app]):::start

subgraph PASO1["PASO 1 · Configuración y Conexión BLE"]

B[Mostrar diagrama de colocación<br/>RA · LA · LL]:::process

C[Instrucciones de electrodos<br/>e inspección de piel]:::process

D[Botón → Conectar HealthyPi 5]:::process

E{¿BLE disponible<br/>en el navegador?}:::decision

E1[⚠️ Requiere HTTPS<br/>Chrome + ngrok]:::warning

F[Pop-up Bluetooth<br/>Seleccionar dispositivo]:::process

G{¿Emparejamiento<br/>aceptado?}:::decision

G1[Error BLE<br/>Reintentar]:::warning

H[✅ Dispositivo conectado<br/>Actualizar estado UI]:::success

B --> C
C --> D
D --> E
E -- No --> E1
E1 --> D
E -- Sí --> F
F --> G
G -- No --> G1
G1 --> D
G -- Sí --> H

end

A --> B

%%==========================
%% PASO 2
%%==========================

subgraph PASO2["PASO 2 · Validación de Señal e Ingesta Basal"]

I[Iniciar análisis automático<br/>de calidad de señal]:::process

J[Aplicar filtros<br/>Pasa-altas, Pasa-bajas,<br/>Notch 60 Hz]:::process

K[Detectar picos R<br/>≥250 Hz]:::process

L{¿Calidad de señal<br/>óptima?}:::decision

L1[⚠️ Ajustar electrodos]:::warning

M[Fase Baseline<br/>Capturar 300 RR<br/>≈5 min]:::process

N{¿Baseline<br/>completado?}:::decision

O[Emitir evento<br/>baseline_progress]:::process

P[Calcular RMSSD Basal<br/>baseline_ready]:::success

I --> J
J --> K
K --> L

L -- No --> L1
L1 --> I

L -- Sí --> M

M --> N

N -- No --> O
O --> M

N -- Sí --> P

end

H --> I

%%==========================
%% PASO 3
%%==========================

subgraph PASO3["PASO 3 · Monitoreo Activo y Gamificación"]

Q[Ingresar EVA Score<br/>+ Confundidores]:::process

R[Monitoreo en tiempo real<br/>Ventanas de 5 min]:::process

S[Procesar RMSSD<br/>Clasificar estrés]:::process

T{¿Variación RMSSD<br/>vs Basal?}:::decision

T1[Estrés Normal<br/>🟢 Verde]:::success

T2[Estrés Moderado<br/>🟡 Ámbar]:::process

T3[Estrés Elevado<br/>🔴 Rojo]:::warning

U[Actualizar Dashboard<br/>Tiempo efectivo]:::process

V{¿Estrés elevado<br/>≥2 ventanas?}:::decision

W[🚨 Emitir evento<br/>rest_alert]:::warning

X[Continuar estudio]:::success

Q --> R
R --> S
S --> T

T -- "<15%" --> T1
T -- "15-30%" --> T2
T -- ">30%" --> T3

T1 --> U
T2 --> U
T3 --> U

U --> V

V -- Sí --> W
V -- No --> X

end

P --> Q

%%==========================
%% PASO 4
%%==========================

subgraph PASO4["PASO 4 · Toma de Decisiones e Interacción"]

Y{¿Usuario acepta<br/>el descanso?}:::decision

Z[Registrar Bono de Descanso<br/>Resetear contadores]:::success

ZA[Usuario completa descanso<br/>Evento rest_return]:::success

ZB[Aplicar penalización<br/>stress_penalty_periods]:::warning

ZC{¿Terminar<br/>Sesión?}:::decision

ZD[Evento end_session<br/>Calcular IES y XP]:::process

ZE([🏁 Mostrar Resumen Final]):::end

Y -- Sí --> Z
Z --> ZA

Y -- No --> ZB

ZA --> ZC
ZB --> ZC
X --> ZC

ZC -- No --> R

ZC -- Sí --> ZD
ZD --> ZE

end

W --> Y
```

---

# 📊 Fórmulas Clave Implementadas en el Backend

### RMSSD

$$
\text{RMSSD} =
\sqrt{
\frac{1}{N-1}
\sum_{i=1}^{N-1}
(RR_{i+1}-RR_i)^2
}
$$

### Variación porcentual

$$
\text{Variación %} =
\left|
\frac{\text{RMSSD}*{actual}-\text{RMSSD}*{basal}}
{\text{RMSSD}_{basal}}
\right|
\times100
$$

### Índice de Eficiencia de Estudio (IES)

$$
\text{IES}
==========

## T_{\text{efectivo(min)}}

P_{\text{estrés}}
+
B_{\text{descanso}}
+
B_{\text{retorno}}
$$

Donde:

* (P_{\text{estrés}} = \text{periodos ignorados} \times 5)
* (B_{\text{descanso}} = \text{aceptados} \times 3)
* (B_{\text{retorno}} = \text{retornos completados} \times 2)

### Puntos de Experiencia

$$
\text{XP} = \text{IES} \times 10
$$

---

Desarrollado para el proyecto de **Instrumentación Biomédica (C0688)** — *Universidad Peruana Cayetano Heredia*.


Si lo prefieres, también puedo entregártelo como un archivo **`README.md`** descargable.
```


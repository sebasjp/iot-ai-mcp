# Definición del proyecto — Monitor inteligente de rack de TI

**Actividad 4 · IA aplicada a IoT · UAO**
Documento de referencia del equipo. Lo marcado como **Propuesta** es un punto de partida técnico que el responsable puede ajustar, avisando al equipo, porque afecta a los demás.

---

## 1. Caso de uso

Un rack de TI enfrenta tres riesgos: **el ambiente, la máquina y las personas**. El sistema monitorea los tres con modelos de IA que corren en el borde (ESP32-S3 y Raspberry Pi), guarda todo en AWS y permite consultarlo en lenguaje natural mediante un servidor MCP.

| Riesgo | Modelo | Pregunta que responde |
|---|---|---|
| Ambiente | Temperatura y humedad (DHT22) | ¿Se está calentando o humedeciendo el rack? |
| Máquina | Vibración del ventilador (MPU-6050) | ¿El sistema de enfriamiento está por fallar? |
| Personas | Clasificación de imágenes (webcam USB) | ¿Hay alguien frente al rack? ¿Está la puerta abierta? |

El montaje es un **prototipo a escala**: el ventilador de pie representa la bandeja de ventilación del rack y un mueble con puerta representa el rack.

---

## 2. Responsables

| Componente | Responsable | Dispositivo |
|---|---|---|
| Modelo de temperatura y humedad | **César** | ESP32-S3 (propio) |
| Modelo de vibración (acelerómetro) | **Sebas** | ESP32-S3 (propio) |
| Modelo de imágenes | **Juan** | Raspberry Pi 3 (la tiene Juan) y webcam USB |
| Servidor MCP (FastMCP) | **Julián** | Desarrolla en su portátil y despliega de forma remota en la Raspberry Pi 3 |
| Infraestructura AWS (Things, certificados, políticas, regla IoT, DynamoDB, IAM) | **Juan** | AWS |
| Backend (Lambda y API que consultan DynamoDB) y dashboard | **Juan** | AWS (Lambda, API Gateway, S3) |
| Lógica de alarmas (en el backend) y su visualización en el dashboard | **Juan** | AWS |
| Bot de Telegram y envío de las notificaciones | **Julián** | Telegram |

### Prioridad de Juan: desbloquear al equipo

Estas tareas de Juan bloquean a los demás, así que van primero:

1. Crear los tres Things (`rack01-env`, `rack01-vibration`, `rack01-camera`) con sus certificados y políticas. Repartirlos a cada responsable **por un canal privado, nunca por el repositorio**.
2. Crear la tabla de DynamoDB y la regla IoT que guarda los mensajes.
3. Crear un usuario IAM de **solo lectura** sobre la tabla para el MCP de Julián.

Mientras tanto, los demás pueden capturar datos y entrenar en Edge Impulse sin depender de AWS.

Cada modelo del ESP32-S3 corre en **su propia placa**. Así se evita integrar dos librerías de Edge Impulse en el mismo firmware.

---

## 3. Arquitectura general

```
ESP32-S3 #1 (César)   DHT22    → modelo T/H       ─┐
ESP32-S3 #2 (Sebas)   MPU-6050 → modelo vibración ─┼─ MQTT/TLS ─> AWS IoT Core ─> Regla IoT ─> DynamoDB
Raspberry Pi (Juan)   webcam   → modelo imágenes  ─┘                                              │
                                                                                                  ├─> Dashboard (S3)
Raspberry Pi (Julián) servidor MCP  ── consulta ───────────────────────────────────────────────────┤
                                                                                                  └─> Alarmas → Telegram
```

- **Todo con Edge Impulse:** un proyecto por modelo, a cargo de su responsable.
- **Todas las predicciones se guardan en DynamoDB.** El MCP consulta **solo DynamoDB**: no habla directamente con los dispositivos.
- **Alarmas por Telegram, solo texto.**
- Se reutiliza la infraestructura AWS de la entrega anterior (IoT Core, DynamoDB, Lambda, API Gateway, S3).

---

## 4. Modelos

### 4.1 Temperatura y humedad — César

| Aspecto | Definición |
|---|---|
| Sensor | DHT22 en el ESP32-S3 |
| Tipo de modelo | **Clasificador** (opción A) sobre ventanas de tiempo |
| Clases | `normal`, `falla_enfriamiento`, `riesgo_condensacion` |
| Qué detecta | La **tendencia**, antes de que se cruce un umbral fijo |

**Significado de las clases:**

- **`normal`:** temperatura y humedad estables dentro del rango.
- **`falla_enfriamiento`:** el aire acondicionado falla o la ventilación está obstruida.
  - **Firma en los datos:** la temperatura sube de forma sostenida (≈0,3–1 °C/min) y la humedad relativa baja.
  - **Simulación:** secador de pelo a distancia, o el sensor en una caja cerrada con una fuente de calor.
- **`riesgo_condensacion`:** aire húmedo que puede condensarse sobre los equipos.
  - **Firma en los datos:** la humedad sube rápido hacia >70–80 % con la temperatura estable o bajando.
  - **Simulación:** vapor de olla o hervidor a distancia, o un trapo húmedo cerca del sensor.

**Consideraciones:**
- El DHT22 entrega como máximo **1 lectura cada 2 s**, y los eventos duran minutos.
- **Propuesta:** ventanas de ~2 min con solapamiento, y 20–30 min de grabación por clase.
- **Es el modelo que más tiempo de reloj consume en la captura. Hay que empezar primero.**

### 4.2 Vibración del ventilador — Sebas

| Aspecto | Definición |
|---|---|
| Sensor | MPU-6050 (acelerómetro y giroscopio) en el ESP32-S3 |
| Objeto monitoreado | Ventilador de pie, 3 velocidades, cabeza oscilante o fija |
| Tipo de modelo | Clasificador de la **condición** del ventilador |
| Clases | `apagado`, `normal`, `desbalanceado` |
| Qué detecta | Señales tempranas de falla. **No** predice el tiempo restante de vida (no sobreprometer en el pitch) |

**Significado de las clases:**

- **`apagado`:** ventilador detenido; representa una falla total.
- **`normal`:** funcionamiento sano.
- **`desbalanceado`:** polvo acumulado o aspa dañada. **Simulación:** moneda o plastilina pegada en una aspa.

**Montaje:**
- El sensor va **firme a la carcasa del motor**, con silicona caliente o cinta doble faz más un amarre plástico. No va en la rejilla.
- Cable I2C corto, de menos de 30–50 cm. El ESP32 puede ir en la base del ventilador.

**Señal (Propuesta):**
- Muestreo a 100–200 Hz.
- Ventanas de 2 s → bloque *Spectral Analysis* (FFT) → clasificador.
- Captura con el *data forwarder* de Edge Impulse: 3–5 min por clase **y por cada velocidad**.

### 4.3 Seguridad física — Juan

| Aspecto | Definición |
|---|---|
| Sensor | Webcam USB (UVC) en la Raspberry Pi 3 |
| Tipo de modelo | Clasificación de imágenes, variante **B1: presencia** |
| Clases | `vacio`, `persona`, `puerta_abierta` |
| Qué resuelve | Registro auditable de quién está frente al rack (ISO 27001 / TIA-942) y cruce con los otros sensores |

**Consideraciones:**
- El "rack" es un mueble con puerta, fijo frente a la cámara.
- **Captura:** con `edge-impulse-linux` la webcam se conecta al estudio de Edge Impulse.
- **Cantidad de datos:** de 50 a 100 o más fotos por clase, variando la persona, la ropa, la luz y la posición.
- **Propuesta de modelo:** transfer learning con MobileNetV2 a 96×96 o 160×160 px.
- **Rendimiento:** en la Pi 3 una inferencia tarda cientos de milisegundos. Se clasifica cada pocos segundos, no en video continuo.

---

## 5. Servidor MCP — Julián

Se implementa con **FastMCP** (Python), como pidió el profesor. Corre en la Raspberry Pi 3 y **solo consulta DynamoDB**.

- Julián lo desarrolla y prueba en su portátil con Windows, porque el código no depende del hardware de la Pi.
- **El despliegue final y la demo son en la Raspberry.** Julián accede a ella de forma remota (ver sección 8).
- **Requisito:** FastMCP necesita Python ≥ 3.10 en la Pi. Se instala con `uv`, como en la entrega anterior.
- **Transporte (Propuesta):** HTTP en la red local, para que los clientes se conecten a `http://<ip-de-la-pi>:8000/mcp`.
  - Los clientes en la nube, como ChatGPT, necesitarían una URL pública con HTTPS (túnel de Cloudflare o ngrok).

| Tool (nombre propuesto) | Qué responde |
|---|---|
| `consultar_prediccion_imagenes` | Último estado de la cámara y eventos recientes (presencia, puerta abierta) |
| `consultar_prediccion_sensores` | Última predicción y lectura de temperatura/humedad y de vibración |
| `consultar_historico` | Lecturas y predicciones en un rango de tiempo, filtradas por fuente |

Ejemplo de la demo: *"¿Qué pasó anoche en el rack?"* → *"A las 2:14 a. m. el ventilador mostró desbalance, la temperatura subió 3 °C en 10 minutos y nadie estuvo frente al rack."*

---

## 6. Contratos entre componentes (Propuesta)

Esta es la parte que permite trabajar en paralelo. **Cualquier cambio aquí se avisa a todo el equipo.**

### 6.1 Etiquetas: deben escribirse exactamente igual en firmware, DynamoDB, dashboard y MCP

| Fuente | Etiquetas |
|---|---|
| `env` | `normal`, `falla_enfriamiento`, `riesgo_condensacion` |
| `vibration` | `apagado`, `normal`, `desbalanceado` |
| `camera` | `vacio`, `persona`, `puerta_abierta` |

### 6.2 Dispositivos (Things en AWS IoT), uno por dispositivo y cada uno con su certificado

| Thing / `device_id` | Responsable | Tópico donde publica |
|---|---|---|
| `rack01-env` | César | `datacenter/rack01/env` |
| `rack01-vibration` | Sebas | `datacenter/rack01/vibration` |
| `rack01-camera` | Juan | `datacenter/rack01/camera` |

### 6.3 Payloads JSON

Campos comunes en todos los mensajes:
- `device_id`
- `ts`: epoch en milisegundos, hora de la lectura.
- `label`: etiqueta ganadora.
- `confidence`: probabilidad de la etiqueta ganadora.
- `scores`: probabilidades de todas las clases.

```json
// datacenter/rack01/env
{"device_id":"rack01-env","ts":1795400000000,"temperature":24.6,"humidity":55.1,
 "label":"normal","confidence":0.93,
 "scores":{"normal":0.93,"falla_enfriamiento":0.05,"riesgo_condensacion":0.02}}

// datacenter/rack01/vibration — no se envían datos crudos (100–200 Hz), solo un resumen y la predicción
{"device_id":"rack01-vibration","ts":1795400000000,"accel_rms":0.42,
 "label":"desbalanceado","confidence":0.88,
 "scores":{"apagado":0.01,"normal":0.11,"desbalanceado":0.88}}

// datacenter/rack01/camera
{"device_id":"rack01-camera","ts":1795400000000,
 "label":"persona","confidence":0.91,
 "scores":{"vacio":0.04,"persona":0.91,"puerta_abierta":0.05}}
```

**Frecuencia de publicación (Propuesta):** cada 10 s, y de inmediato cuando cambia la etiqueta.

### 6.4 DynamoDB (Propuesta)

- Una sola tabla con el mismo esquema de la entrega anterior: partición `device_id` (S) y ordenación `ts` (N).
- Una regla IoT `SELECT *, timestamp() AS received_at FROM 'datacenter/rack01/+'` escribe todos los mensajes.
- El MCP filtra por `device_id`.

---

## 7. Alarmas (Telegram, solo texto)

- **Juan:** la lógica de las alarmas vive en el **backend** (AWS). Juan también la muestra en el **dashboard**.
- **Julián:** se encarga del **bot de Telegram** y del envío de las notificaciones.
- **Por acordar entre los dos:** cómo se conecta la lógica de Juan con el envío de Julián (ver sección 11).

### 7.1 Alarmas individuales (Propuesta: disparar solo si la etiqueta se repite en N predicciones seguidas, para evitar falsos positivos)

| Fuente | Condición | Mensaje de ejemplo |
|---|---|---|
| env | `falla_enfriamiento` o `riesgo_condensacion` | "Rack01: tendencia de falla de enfriamiento (24,8 °C, subiendo)" |
| vibration | `desbalanceado` o `apagado` | "Rack01: ventilador desbalanceado, revisar" |
| camera | `persona` o `puerta_abierta` | "Rack01: puerta del rack abierta" |

### 7.2 Alarmas cruzadas (planeadas)

| Combinación | Interpretación | Prioridad |
|---|---|---|
| vibration anómala + env `falla_enfriamiento` | Falla de enfriamiento confirmada por dos fuentes | Alta |
| camera `persona` + vibration anómala | Probable intervención de un técnico: aporta contexto y evita una falsa alarma | Informativa |
| camera `puerta_abierta` sin `persona` | Puerta abierta y nadie a la vista | Media |

---

## 8. Trabajo en la Raspberry Pi compartida (Juan y Julián)

Juan y Julián viven lejos. **La Raspberry se queda con Juan**, que trabaja con ella en persona. **Julián se conecta de forma remota.**

### Logística

- **Única entrega física:** Julián le pasa la **webcam USB** a Juan.
- Juan se encarga de la caja que hace de "rack" y del encuadre de la cámara. La misma caja va a la demo.

### Acceso remoto de Julián

- Por **Tailscale** (VPN gratuita): se instala en la Pi, en el portátil de Juan y en el de Julián.
- Julián entra por SSH, por ejemplo con VS Code Remote-SSH desde Windows.
- Despliega el MCP con `git pull` y deja corriendo su servicio.
- Juan solo debe mantener la Pi encendida y conectada.

### Tareas iniciales de Juan en la Pi (hacerlas primero)

1. Ejecutar `uname -m` para saber si el sistema es de 32 bits (`armv7l`) o de 64 bits (`aarch64`). Edge Impulse lo necesita para generar el modelo correcto.
2. Instalar Python ≥ 3.10 con `uv`, que FastMCP requiere.
3. Instalar Tailscale y darle acceso a Julián.

### Convivencia en la Pi

- **Carpetas, entornos de Python y servicios `systemd` separados**: `raspberry/vision/` (Juan) y `raspberry/mcp/` (Julián).
- **Solo el servicio de Juan usa la cámara** (`/dev/video0`).
- **Credenciales separadas:**
  - Juan publica por MQTT con el certificado de `rack01-camera`.
  - Julián lee DynamoDB con credenciales IAM de **solo lectura**.
- **La Pi 3 tiene 1 GB de RAM:** no se entrena nada en la Pi, solo inferencia y el MCP.
- Usen una fuente de 5 V / 2,5 A; la webcam consume corriente.

### Red para la demo

Configuren de antemano en la Pi un **hotspot de celular** como red Wi-Fi. Así funciona en clase sin tener que reconfigurar nada.

---

## 9. Notas de hardware para el ESP32-S3 (N16R8)

- **No usar GPIO 35, 36 y 37**: están ocupados por la PSRAM octal.
- Evitar los pines de arranque (*strapping*): GPIO 0, 3, 45 y 46.
- Evitar GPIO 19 y 20, que son del USB nativo.
- **Pines sugeridos (Propuesta):**
  - DHT22 en GPIO 4.
  - MPU-6050 por I2C: SDA en GPIO 8, SCL en GPIO 9.

---

## 10. Estructura del repositorio (Propuesta)

```
iot-ai-mcp/
├── README.md              # entrega final: caso, arquitectura, inconvenientes, resultados, conclusiones
├── docs/                  # guía, este documento, diagrama, matrices de confusión
├── esp32/
│   ├── env/               # César
│   └── vibration/         # Sebas
├── raspberry/
│   ├── vision/            # Juan
│   └── mcp/               # Julián
├── aws/                   # regla IoT, Lambdas (alarmas, API)
└── dashboard/             # dashboard extendido
```

**Cada responsable de modelo entrega para el README:**
- Matriz de confusión y accuracy (pantallazo de Edge Impulse).
- Tiempo de inferencia y uso de RAM/flash en el dispositivo.
- Cómo capturó los datos y cuántas muestras tiene por clase.
- Inconvenientes que encontró y cómo los resolvió.

---

## 11. Pendiente por definir

- [ ] **Responsables sin asignar:** integración del README y del diagrama de arquitectura (cada responsable aporta la sección de su componente), pitch de 3 minutos.
- [ ] **Carga de Juan:** tiene el modelo de imágenes, AWS, backend, dashboard y la lógica de alarmas. Hay que vigilarla y redistribuir si se atrasa.
- [ ] **Interfaz entre las alarmas y Telegram:** por ejemplo, si el backend llama directamente a la API de Telegram con el token del bot de Julián, o si Julián entrega una función de envío que el backend invoca.
- [ ] **Ventilador:** ¿se entrena solo con la cabeza fija, o se incluye la oscilación dentro de `normal` y `desbalanceado`?
- [ ] **Alarmas:** ya se decidió que van en el backend de AWS. Falta definir cuántas predicciones seguidas hacen falta para disparar y si la presencia alerta siempre o solo fuera de horario.
- [ ] **MCP:** confirmar el transporte (la propuesta es HTTP en la red local) y con qué cliente se hace la demo (Claude, VS Code, etc.).
- [ ] **Validar con el profesor:** la cámara USB en la Pi en lugar del ESP32-CAM. El MCP con FastMCP en la Pi ya lo pidió él.

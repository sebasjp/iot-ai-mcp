# esp32-s3-mpu6050 — Vibración del ventilador del rack

Clasifica la condición del ventilador (`apagado`, `normal`, `desbalanceado`) con un modelo de Edge Impulse
que corre en el ESP32-S3, y publica el resultado en AWS IoT Core.

## Conexión

| MPU-6050 | ESP32-S3 |
|---|---|
| VCC | 3V3 |
| GND | GND |
| SDA | GPIO 8 |
| SCL | GPIO 9 |

## Contenido

| Archivo | Descripción |
|---|---|
| `esp32-s3-mpu6050.ino` | Sketch principal: captura, inferencia y publicación MQTT |
| `secrets.example.h` | Plantilla de WiFi, endpoint y certificados. Se copia como `secrets.h` (no se sube al repo) |
| `rack01-vibration_inferencing/` | Librería Arduino exportada desde Edge Impulse (el modelo) |

## Preparación

1. **Placa** (Arduino IDE, paquete *esp32* de Espressif): `ESP32S3 Dev Module`, Flash Size `16MB`, PSRAM `OPI PSRAM`.
2. **Librerías:**
   - El modelo: copiar la carpeta `rack01-vibration_inferencing` a `Documentos\Arduino\libraries\`
     (o instalar el `.zip` con *Sketch → Include Library → Add .ZIP Library*).
   - **PubSubClient** (Nick O'Leary), desde el gestor de librerías.
3. **Credenciales:** copiar `secrets.example.h` como `secrets.h` y completar:
   - WiFi (SSID y clave).
   - Endpoint de AWS IoT.
   - Amazon Root CA 1, certificado y llave privada del Thing `rack01-vibration`.
4. **AWS IoT:** la política del Thing debe permitir:
   - `iot:Connect` con el client ID `rack01-vibration`.
   - `iot:Publish` en `datacenter/rack01/vibration`.

## Funcionamiento

- Captura ventanas de **2 s a 100 Hz** (6 ejes), con la misma configuración del sensor usada al capturar
  los datos de entrenamiento (±4 g, ±500 °/s, filtro ~94 Hz).
- Clasifica cada ventana en el dispositivo.
- Publica en `datacenter/rack01/vibration`:
  - **Cada 10 s**, el promedio de las predicciones del periodo.
  - **De inmediato**, cuando dos ventanas seguidas coinciden en una etiqueta distinta a la última publicada.
- Si no hay WiFi o MQTT, sigue clasificando (y lo muestra por serial). Reintenta la conexión MQTT cada 5 s.

Ejemplo de mensaje:

```json
{"device_id":"rack01-vibration","ts":1795400000000,"accel_rms":0.0421,
 "label":"desbalanceado","confidence":0.880,
 "scores":{"apagado":0.010,"desbalanceado":0.880,"normal":0.110}}
```

`accel_rms` es la intensidad de la vibración: la desviación estándar de la magnitud de la aceleración (en g).

## Verificación

1. Monitor Serie a 115200: cada 2 s aparece la clase detectada, el tiempo de DSP e inferencia y el RMS.
2. Consola de AWS IoT → *MQTT test client* → suscribirse a `datacenter/rack01/vibration`.
3. DynamoDB: los mensajes aparecen con `device_id = rack01-vibration` (requiere la regla IoT).

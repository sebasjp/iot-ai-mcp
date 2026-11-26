/*
 * esp32-s3-mpu6050 — Clasificación de la vibración del ventilador del rack
 *
 * ESP32-S3 + MPU-6050 + modelo de Edge Impulse (rack01-vibration) + AWS IoT Core (MQTT sobre TLS)
 *
 * Flujo:
 *   1. Captura una ventana de 2 s a 100 Hz (6 ejes: ax, ay, az en g; gx, gy, gz en °/s).
 *   2. La clasifica en el dispositivo: apagado / normal / desbalanceado.
 *   3. Publica en datacenter/rack01/vibration:
 *      - cada 10 s, el promedio de las predicciones del periodo;
 *      - de inmediato, si dos ventanas seguidas coinciden en una etiqueta distinta a la última publicada.
 *
 * La inferencia sigue funcionando aunque no haya WiFi o MQTT (solo se deja de publicar).
 */
#include <Wire.h>
#include <WiFi.h>
#include <WiFiClientSecure.h>
#include <PubSubClient.h>
#include <sys/time.h>
#include <rack01-vibration_inferencing.h>
#include "secrets.h"

// ---------------- Configuración ----------------
#define DEVICE_ID   "rack01-vibration"            // = nombre del Thing en AWS IoT
#define MQTT_TOPIC  "datacenter/rack01/vibration"

const int      SDA_PIN  = 8;
const int      SCL_PIN  = 9;
const uint8_t  MPU_ADDR = 0x68;

const uint32_t PUBLISH_PERIOD_MS  = 10000;  // publicación periódica
const uint32_t MQTT_RETRY_MS      = 5000;   // espera entre reintentos de conexión MQTT
const uint16_t MQTT_PORT          = 8883;

#define N_LABELS EI_CLASSIFIER_LABEL_COUNT

// ---------------- Estado ----------------
static float buffer[EI_CLASSIFIER_DSP_INPUT_FRAME_SIZE];
const char *labels[N_LABELS];

WiFiClientSecure net;
PubSubClient mqtt(net);
bool timeSynced = false;
uint32_t lastMqttAttempt = 0;

// Acumuladores del periodo de publicación
float scoreSum[N_LABELS];
float rmsSum = 0;
int windowsInPeriod = 0;
uint32_t periodStart = 0;

// Para detectar cambios de estado
int lastPublished = -1;
int prevLabel = -1;
float prevScores[N_LABELS];
float prevRms = 0;

// ---------------- MPU-6050 ----------------
void mpuWrite(uint8_t reg, uint8_t val) {
  Wire.beginTransmission(MPU_ADDR);
  Wire.write(reg);
  Wire.write(val);
  Wire.endTransmission();
}

// Misma configuración que en la captura de datos: si cambia, el modelo recibe datos distintos
void mpuInit() {
  Wire.begin(SDA_PIN, SCL_PIN, 400000);
  mpuWrite(0x6B, 0x00);  // despertar
  mpuWrite(0x1A, 0x02);  // filtro paso bajo ~94 Hz
  mpuWrite(0x1B, 0x08);  // giroscopio ±500 °/s  -> 65.5 LSB por °/s
  mpuWrite(0x1C, 0x08);  // acelerómetro ±4 g    -> 8192 LSB por g
  delay(100);
}

void mpuRead(float *out) {
  uint8_t b[14];
  Wire.beginTransmission(MPU_ADDR);
  Wire.write(0x3B);
  Wire.endTransmission(false);
  Wire.requestFrom(MPU_ADDR, (uint8_t)14);
  for (int i = 0; i < 14; i++) b[i] = Wire.read();

  int16_t r[7];
  for (int i = 0; i < 7; i++) r[i] = (b[2 * i] << 8) | b[2 * i + 1];

  out[0] = r[0] / 8192.0f;  out[1] = r[1] / 8192.0f;  out[2] = r[2] / 8192.0f;  // g
  out[3] = r[4] / 65.5f;    out[4] = r[5] / 65.5f;    out[5] = r[6] / 65.5f;    // °/s
}

// Llena el buffer con una ventana a frecuencia fija.
// Devuelve el RMS de la vibración: desviación estándar de la magnitud de la aceleración (g).
float captureWindow() {
  const uint32_t periodUs = EI_CLASSIFIER_INTERVAL_MS * 1000;
  double sum = 0, sumSq = 0;
  const int n = EI_CLASSIFIER_RAW_SAMPLE_COUNT;

  uint32_t next = micros();
  for (int s = 0; s < n; s++) {
    while ((int32_t)(micros() - next) < 0) {}
    next += periodUs;

    float *sample = &buffer[s * EI_CLASSIFIER_RAW_SAMPLES_PER_FRAME];
    mpuRead(sample);

    float mag = sqrtf(sample[0] * sample[0] + sample[1] * sample[1] + sample[2] * sample[2]);
    sum += mag;
    sumSq += mag * mag;
  }
  double mean = sum / n;
  double var = sumSq / n - mean * mean;
  return var > 0 ? sqrt(var) : 0;
}

// ---------------- Inferencia ----------------
bool classify(float *scores) {
  signal_t signal;
  numpy::signal_from_buffer(buffer, EI_CLASSIFIER_DSP_INPUT_FRAME_SIZE, &signal);

  ei_impulse_result_t result = {0};
  EI_IMPULSE_ERROR err = run_classifier(&signal, &result, false);
  if (err != EI_IMPULSE_OK) {
    Serial.printf("Error en run_classifier: %d\n", err);
    return false;
  }
  for (int i = 0; i < N_LABELS; i++) {
    labels[i] = result.classification[i].label;
    scores[i] = result.classification[i].value;
  }
  Serial.printf("DSP %d ms, inferencia %d ms | ", result.timing.dsp, result.timing.classification);
  return true;
}

int argmax(const float *v) {
  int best = 0;
  for (int i = 1; i < N_LABELS; i++)
    if (v[i] > v[best]) best = i;
  return best;
}

// ---------------- Conectividad ----------------
void connectWiFi() {
  Serial.printf("WiFi: conectando a %s", WIFI_SSID);
  WiFi.mode(WIFI_STA);
  WiFi.setAutoReconnect(true);
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  uint32_t start = millis();
  while (WiFi.status() != WL_CONNECTED && millis() - start < 15000) {
    delay(500);
    Serial.print(".");
  }
  Serial.println(WiFi.status() == WL_CONNECTED ? " OK" : " sin conexion (se reintenta en segundo plano)");
}

// La hora (NTP) se necesita para el campo ts del mensaje
void syncTime() {
  configTime(0, 0, "pool.ntp.org", "time.nist.gov");
  uint32_t start = millis();
  while (time(nullptr) < 1700000000 && millis() - start < 10000) delay(200);
  timeSynced = time(nullptr) >= 1700000000;
  Serial.println(timeSynced ? "NTP: hora sincronizada" : "NTP: no se pudo sincronizar");
}

void ensureConnections() {
  if (WiFi.status() != WL_CONNECTED) return;  // el ESP32 reconecta solo (setAutoReconnect)
  if (!timeSynced) syncTime();

  if (!mqtt.connected() && millis() - lastMqttAttempt > MQTT_RETRY_MS) {
    lastMqttAttempt = millis();
    Serial.print("MQTT: conectando a AWS IoT... ");
    if (mqtt.connect(DEVICE_ID)) {
      Serial.println("OK");
    } else {
      Serial.printf("fallo (estado %d)\n", mqtt.state());
    }
  }
}

int64_t epochMs() {
  struct timeval tv;
  gettimeofday(&tv, nullptr);
  return (int64_t)tv.tv_sec * 1000 + tv.tv_usec / 1000;
}

// ---------------- Publicación ----------------
bool publish(const float *scores, float rms, const char *reason) {
  if (!mqtt.connected() || !timeSynced) return false;

  int best = argmax(scores);
  char scoresJson[160];
  int len = snprintf(scoresJson, sizeof(scoresJson), "{");
  for (int i = 0; i < N_LABELS; i++) {
    len += snprintf(scoresJson + len, sizeof(scoresJson) - len, "%s\"%s\":%.3f",
                    i ? "," : "", labels[i], scores[i]);
  }
  snprintf(scoresJson + len, sizeof(scoresJson) - len, "}");

  char payload[384];
  snprintf(payload, sizeof(payload),
           "{\"device_id\":\"%s\",\"ts\":%lld,\"accel_rms\":%.4f,"
           "\"label\":\"%s\",\"confidence\":%.3f,\"scores\":%s}",
           DEVICE_ID, (long long)epochMs(), rms, labels[best], scores[best], scoresJson);

  bool ok = mqtt.publish(MQTT_TOPIC, payload);
  Serial.printf("MQTT [%s] %s: %s\n", reason, ok ? "publicado" : "ERROR al publicar", payload);
  if (ok) lastPublished = best;
  return ok;
}

void resetPeriod() {
  for (int i = 0; i < N_LABELS; i++) scoreSum[i] = 0;
  rmsSum = 0;
  windowsInPeriod = 0;
  periodStart = millis();
}

// ---------------- Programa principal ----------------
void setup() {
  Serial.begin(115200);
  delay(2000);
  Serial.println("\n== rack01-vibration ==");

  if (EI_CLASSIFIER_RAW_SAMPLES_PER_FRAME != 6) {
    Serial.println("ERROR: el modelo no espera 6 ejes");
    while (true) delay(1000);
  }

  mpuInit();

  net.setCACert(AWS_CERT_CA);
  net.setCertificate(AWS_CERT_CRT);
  net.setPrivateKey(AWS_CERT_PRIVATE);
  mqtt.setServer(AWS_IOT_ENDPOINT, MQTT_PORT);
  mqtt.setBufferSize(512);
  mqtt.setKeepAlive(60);

  connectWiFi();
  ensureConnections();
  resetPeriod();
}

void loop() {
  ensureConnections();
  mqtt.loop();

  // 1. Capturar y clasificar una ventana
  float rms = captureWindow();
  float scores[N_LABELS];
  if (!classify(scores)) return;

  int label = argmax(scores);
  Serial.printf("%s (%.2f) rms=%.4f g\n", labels[label], scores[label], rms);

  // 2. Acumular para el promedio del periodo
  for (int i = 0; i < N_LABELS; i++) scoreSum[i] += scores[i];
  rmsSum += rms;
  windowsInPeriod++;

  // 3. Publicar
  if (label != lastPublished && label == prevLabel) {
    // Cambio de estado confirmado por dos ventanas seguidas: publicar de inmediato
    float avg[N_LABELS];
    for (int i = 0; i < N_LABELS; i++) avg[i] = (scores[i] + prevScores[i]) / 2;
    publish(avg, (rms + prevRms) / 2, "cambio");
    resetPeriod();
  } else if (millis() - periodStart >= PUBLISH_PERIOD_MS) {
    float avg[N_LABELS];
    for (int i = 0; i < N_LABELS; i++) avg[i] = scoreSum[i] / windowsInPeriod;
    publish(avg, rmsSum / windowsInPeriod, "periodico");
    resetPeriod();
  }

  prevLabel = label;
  prevRms = rms;
  for (int i = 0; i < N_LABELS; i++) prevScores[i] = scores[i];
}

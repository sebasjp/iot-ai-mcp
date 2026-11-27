// Firmware final del Thing rack01-env (Cesar)
// DHT22 -> ventana de 2 min -> modelo Edge Impulse -> MQTT/TLS a AWS IoT Core.
// Publica cada 10 s y de inmediato cuando cambia la etiqueta.
// Antes de compilar: copiar secrets.h.example a secrets.h y llenarlo.

#include <rack1-env-temp-humedad_inferencing.h>
#include <DHT.h>
#include <WiFi.h>
#include <WiFiClientSecure.h>
#include <PubSubClient.h>
#include <sys/time.h>
#include "secrets.h"

#define DHT_PIN   4
#define DHT_TYPE  DHT22

#define DEVICE_ID   "rack01-env"
#define MQTT_TOPIC  "datacenter/rack01/env"

#define INTERVALO_LECTURA_MS   2000
#define INTERVALO_PUBLICAR_MS  10000

DHT dht(DHT_PIN, DHT_TYPE);
WiFiClientSecure red;
PubSubClient mqtt(red);

static float ventana[EI_CLASSIFIER_DSP_INPUT_FRAME_SIZE];
static int   lecturas = 0;

unsigned long ultimaLectura = 0;
unsigned long ultimaPublicacion = 0;
unsigned long ultimoIntentoRed = 0;
int etiquetaAnterior = -1;

// ---------- Ventana de lecturas ----------
void agregarLectura(float t, float h) {
  const int N = EI_CLASSIFIER_RAW_SAMPLE_COUNT;
  if (lecturas < N) {
    ventana[lecturas * 2]     = t;
    ventana[lecturas * 2 + 1] = h;
    lecturas++;
  } else {
    memmove(ventana, ventana + 2, (EI_CLASSIFIER_DSP_INPUT_FRAME_SIZE - 2) * sizeof(float));
    ventana[(N - 1) * 2]     = t;
    ventana[(N - 1) * 2 + 1] = h;
  }
}

// ---------- Red ----------
void conectarWifi() {
  if (WiFi.status() == WL_CONNECTED) return;
  Serial.print("Conectando a WiFi");
  WiFi.mode(WIFI_STA);
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  unsigned long inicio = millis();
  while (WiFi.status() != WL_CONNECTED && millis() - inicio < 15000) {
    delay(500);
    Serial.print(".");
  }
  if (WiFi.status() == WL_CONNECTED) {
    Serial.print(" OK, IP: ");
    Serial.println(WiFi.localIP());
    configTime(0, 0, "pool.ntp.org", "time.nist.gov");   // hora para el campo ts
  } else {
    Serial.println(" fallo, se reintenta luego");
  }
}

void conectarMqtt() {
  if (WiFi.status() != WL_CONNECTED || mqtt.connected()) return;
  Serial.print("Conectando a AWS IoT... ");
  if (mqtt.connect(DEVICE_ID)) {
    Serial.println("OK");
  } else {
    Serial.print("fallo, codigo ");
    Serial.println(mqtt.state());
  }
}

bool horaLista() {
  struct timeval tv;
  gettimeofday(&tv, NULL);
  return tv.tv_sec > 1700000000;   // ya sincronizo con NTP
}

// ---------- Publicar ----------
void publicar(float t, float h, const ei_impulse_result_t &r, int mejor) {
  if (!mqtt.connected() || !horaLista()) {
    Serial.println("Sin conexion o sin hora: no se publica");
    return;
  }
  struct timeval tv;
  gettimeofday(&tv, NULL);
  long long ts = (long long)tv.tv_sec * 1000LL + tv.tv_usec / 1000;

  char json[512];
  int n = snprintf(json, sizeof(json),
    "{\"device_id\":\"%s\",\"ts\":%lld,\"temperature\":%.1f,\"humidity\":%.1f,"
    "\"label\":\"%s\",\"confidence\":%.2f,\"scores\":{",
    DEVICE_ID, ts, t, h, r.classification[mejor].label, r.classification[mejor].value);
  for (size_t i = 0; i < EI_CLASSIFIER_LABEL_COUNT; i++) {
    n += snprintf(json + n, sizeof(json) - n, "%s\"%s\":%.2f",
                  i ? "," : "", r.classification[i].label, r.classification[i].value);
  }
  snprintf(json + n, sizeof(json) - n, "}}");

  bool ok = mqtt.publish(MQTT_TOPIC, json);
  Serial.print(ok ? "Publicado: " : "ERROR al publicar: ");
  Serial.println(json);
}

// ---------- Clasificar ----------
void clasificarYPublicar(float t, float h) {
  signal_t senal;
  if (numpy::signal_from_buffer(ventana, EI_CLASSIFIER_DSP_INPUT_FRAME_SIZE, &senal) != 0) return;

  ei_impulse_result_t r;
  if (run_classifier(&senal, &r, false) != EI_IMPULSE_OK) {
    Serial.println("Error del clasificador");
    return;
  }

  int mejor = 0;
  for (size_t i = 1; i < EI_CLASSIFIER_LABEL_COUNT; i++) {
    if (r.classification[i].value > r.classification[mejor].value) mejor = i;
  }

  bool cambio = (mejor != etiquetaAnterior);
  bool toca   = (millis() - ultimaPublicacion >= INTERVALO_PUBLICAR_MS);

  Serial.print("T="); Serial.print(t, 1);
  Serial.print(" H="); Serial.print(h, 1);
  Serial.print(" -> "); Serial.print(r.classification[mejor].label);
  Serial.print(" ("); Serial.print(r.classification[mejor].value, 2); Serial.println(")");

  if (cambio || toca) {
    publicar(t, h, r, mejor);
    ultimaPublicacion = millis();
    etiquetaAnterior = mejor;
  }
}

void setup() {
  Serial.begin(115200);
  dht.begin();

  red.setCACert(AWS_CERT_CA);
  red.setCertificate(AWS_CERT_CRT);
  red.setPrivateKey(AWS_CERT_PRIVATE);
  mqtt.setServer(AWS_IOT_ENDPOINT, 8883);
  mqtt.setBufferSize(512);

  conectarWifi();
  Serial.println("rack01-env listo. Calentando ventana de 2 min...");
}

void loop() {
  unsigned long ahora = millis();

  // Mantener conexion sin bloquear las lecturas por mucho tiempo
  if (ahora - ultimoIntentoRed > 5000 && (WiFi.status() != WL_CONNECTED || !mqtt.connected())) {
    ultimoIntentoRed = ahora;
    conectarWifi();
    conectarMqtt();
  }
  mqtt.loop();

  if (ahora - ultimaLectura >= INTERVALO_LECTURA_MS) {
    ultimaLectura = ahora;
    float t = dht.readTemperature();
    float h = dht.readHumidity();
    if (isnan(t) || isnan(h)) {
      Serial.println("Lectura invalida del DHT22, se omite");
      return;
    }
    agregarLectura(t, h);

    if (lecturas < EI_CLASSIFIER_RAW_SAMPLE_COUNT) {
      Serial.print("Calentando: "); Serial.print(lecturas);
      Serial.print("/"); Serial.println(EI_CLASSIFIER_RAW_SAMPLE_COUNT);
    } else {
      clasificarYPublicar(t, h);
    }
  }
}

// Clasificador en el ESP32-S3 - temperatura y humedad del rack (Cesar)
// Paso 1: solo lee el DHT22, clasifica la ventana de 2 minutos y muestra el
// resultado por el Monitor Serie. (WiFi y MQTT se agregan despues.)

#include <rack1-env-temp-humedad_inferencing.h>
#include <DHT.h>

#define DHT_PIN   4
#define DHT_TYPE  DHT22
#define INTERVALO_LECTURA_MS   2000    // el DHT22 da 1 lectura cada 2 s
#define INTERVALO_CLASIF_MS    10000   // clasificar cada 10 s

DHT dht(DHT_PIN, DHT_TYPE);

// Ventana: 60 lecturas x 2 ejes (temperatura, humedad) = 120 valores = 2 min
static float ventana[EI_CLASSIFIER_DSP_INPUT_FRAME_SIZE];
static int   lecturas = 0;             // cuantas lecturas llevamos (max 60)

unsigned long ultimaLectura = 0;
unsigned long ultimaClasif  = 0;

void agregarLectura(float t, float h) {
  const int N = EI_CLASSIFIER_RAW_SAMPLE_COUNT;           // 60
  if (lecturas < N) {
    ventana[lecturas * 2]     = t;
    ventana[lecturas * 2 + 1] = h;
    lecturas++;
  } else {
    // ventana llena: corre todo una posicion y agrega la nueva al final
    memmove(ventana, ventana + 2, (EI_CLASSIFIER_DSP_INPUT_FRAME_SIZE - 2) * sizeof(float));
    ventana[(N - 1) * 2]     = t;
    ventana[(N - 1) * 2 + 1] = h;
  }
}

void clasificar(float t, float h) {
  signal_t senal;
  int err = numpy::signal_from_buffer(ventana, EI_CLASSIFIER_DSP_INPUT_FRAME_SIZE, &senal);
  if (err != 0) {
    Serial.println("Error creando la senal");
    return;
  }

  ei_impulse_result_t resultado;
  EI_IMPULSE_ERROR r = run_classifier(&senal, &resultado, false);
  if (r != EI_IMPULSE_OK) {
    Serial.print("Error del clasificador: ");
    Serial.println((int)r);
    return;
  }

  // Etiqueta con mayor probabilidad
  int mejor = 0;
  for (size_t i = 1; i < EI_CLASSIFIER_LABEL_COUNT; i++) {
    if (resultado.classification[i].value > resultado.classification[mejor].value) mejor = i;
  }

  Serial.print("T=");  Serial.print(t, 1);
  Serial.print(" H="); Serial.print(h, 1);
  Serial.print(" -> "); Serial.print(resultado.classification[mejor].label);
  Serial.print(" ("); Serial.print(resultado.classification[mejor].value, 2); Serial.println(")");

  for (size_t i = 0; i < EI_CLASSIFIER_LABEL_COUNT; i++) {
    Serial.print("   ");
    Serial.print(resultado.classification[i].label);
    Serial.print(": ");
    Serial.println(resultado.classification[i].value, 2);
  }

  // Tiempo real de inferencia en la placa (para el README)
  Serial.print("   tiempo: DSP ");
  Serial.print(resultado.timing.dsp);
  Serial.print(" ms, clasificador ");
  Serial.print(resultado.timing.classification);
  Serial.println(" ms");
}

void setup() {
  Serial.begin(115200);
  dht.begin();
  Serial.println("Clasificador de rack listo. Calentando ventana de 2 min...");
}

void loop() {
  unsigned long ahora = millis();

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
      Serial.print("Calentando: ");
      Serial.print(lecturas);
      Serial.print("/");
      Serial.println(EI_CLASSIFIER_RAW_SAMPLE_COUNT);
    } else if (ahora - ultimaClasif >= INTERVALO_CLASIF_MS) {
      ultimaClasif = ahora;
      clasificar(t, h);
    }
  }
}

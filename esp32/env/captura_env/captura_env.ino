// Programa de CAPTURA - modelo de temperatura y humedad (Cesar)
// Solo lee el DHT22 cada 2 s y escribe "temperatura,humedad" por el cable USB.
// Edge Impulse recibe esas lineas con edge-impulse-data-forwarder.
// IMPORTANTE: no imprimir nada mas por Serial, o el forwarder se confunde.

#include <DHT.h>

#define DHT_PIN   4        // GPIO 4, segun definicion del equipo
#define DHT_TYPE  DHT22
#define INTERVALO_MS 2000  // el DHT22 entrega maximo 1 lectura cada 2 s

DHT dht(DHT_PIN, DHT_TYPE);
unsigned long ultimo = 0;

void setup() {
  Serial.begin(115200);
  dht.begin();
}

void loop() {
  unsigned long ahora = millis();
  if (ahora - ultimo < INTERVALO_MS) return;
  ultimo = ahora;

  float t = dht.readTemperature();  // grados C
  float h = dht.readHumidity();     // % humedad relativa

  if (isnan(t) || isnan(h)) return; // lectura fallida: se omite sin imprimir

  Serial.print(t, 1);
  Serial.print(",");
  Serial.println(h, 1);
}

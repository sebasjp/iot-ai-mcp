#include <Wire.h>

const uint8_t MPU = 0x68;
const uint32_t PERIOD_US = 10000;  // 100 Hz
uint32_t nextUs;

void writeReg(uint8_t reg, uint8_t val) {
  Wire.beginTransmission(MPU); Wire.write(reg); Wire.write(val); Wire.endTransmission();
}

void setup() {
  Serial.begin(115200);
  Wire.begin(8, 9, 400000);
  writeReg(0x6B, 0x00);  // despertar
  writeReg(0x1A, 0x02);  // filtro paso bajo ~94 Hz
  writeReg(0x1B, 0x08);  // giroscopio ±500 °/s
  writeReg(0x1C, 0x08);  // acelerometro ±4 g
  delay(100);
  nextUs = micros();
}

void loop() {
  if ((int32_t)(micros() - nextUs) < 0) return;
  nextUs += PERIOD_US;

  uint8_t b[14];
  Wire.beginTransmission(MPU); Wire.write(0x3B); Wire.endTransmission(false);
  Wire.requestFrom(MPU, (uint8_t)14);
  for (int i = 0; i < 14; i++) b[i] = Wire.read();

  int16_t r[7];
  for (int i = 0; i < 7; i++) r[i] = (b[2 * i] << 8) | b[2 * i + 1];

  Serial.printf("%.4f,%.4f,%.4f,%.2f,%.2f,%.2f\n",
                r[0] / 8192.0, r[1] / 8192.0, r[2] / 8192.0,   // ax ay az en g
                r[4] / 65.5,   r[5] / 65.5,   r[6] / 65.5);    // gx gy gz en °/s
}
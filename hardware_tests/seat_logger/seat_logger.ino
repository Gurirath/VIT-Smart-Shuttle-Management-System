#include <Wire.h>
#include <OneWire.h>
#include <DallasTemperature.h>

#define FSR_PIN 34
#define ONEWIRE_PIN 18
#define SDA_PIN 21
#define SCL_PIN 22
#define MPU_ADDR 0x68

int median5();
void mpuInit();
bool mpuRead(float &ax, float &ay, float &az);

const uint32_t SAMPLE_MS = 100;
const uint32_t TEMP_MS = 1000;
const float EMA_ALPHA = 0.25f;
const int ENTER_COUNTS = 1200;
const int EXIT_COUNTS = 1000;
const float BASELINE_RATE = 0.002f;
const float BASELINE_CAP = 400.0f;

OneWire oneWire(ONEWIRE_PIN);
DallasTemperature sensors(&oneWire);
DeviceAddress probeA, probeB;
int probeCount = 0;
bool mpuOk = false;

int window5[5] = {0, 0, 0, 0, 0};
int windowIdx = 0;
bool windowFull = false;
float ema = 0.0f;
bool emaInit = false;
float baseline = 0.0f;
bool loaded = false;
uint32_t transitions = 0;

float tempA = NAN, tempB = NAN;
uint32_t lastSample = 0, lastTemp = 0;

int median5() {
  int n = windowFull ? 5 : windowIdx;
  if (n == 0) return 0;
  int v[5];
  for (int i = 0; i < n; i++) v[i] = window5[i];
  for (int i = 1; i < n; i++) {
    int k = v[i], j = i - 1;
    while (j >= 0 && v[j] > k) { v[j + 1] = v[j]; j--; }
    v[j + 1] = k;
  }
  return v[n / 2];
}

void mpuInit() {
  Wire.begin(SDA_PIN, SCL_PIN);
  Wire.beginTransmission(MPU_ADDR);
  if (Wire.endTransmission() != 0) { mpuOk = false; return; }
  Wire.beginTransmission(MPU_ADDR);
  Wire.write(0x6B);
  Wire.write(0x00);
  Wire.endTransmission();
  Wire.beginTransmission(MPU_ADDR);
  Wire.write(0x1C);
  Wire.write(0x08);
  Wire.endTransmission();
  mpuOk = true;
}

bool mpuRead(float &ax, float &ay, float &az) {
  if (!mpuOk) return false;
  Wire.beginTransmission(MPU_ADDR);
  Wire.write(0x3B);
  if (Wire.endTransmission(false) != 0) return false;
  if (Wire.requestFrom((uint8_t)MPU_ADDR, (uint8_t)6) != 6) return false;
  int16_t x = (Wire.read() << 8) | Wire.read();
  int16_t y = (Wire.read() << 8) | Wire.read();
  int16_t z = (Wire.read() << 8) | Wire.read();
  ax = x / 8192.0f;
  ay = y / 8192.0f;
  az = z / 8192.0f;
  return true;
}

void setup() {
  Serial.begin(115200);
  delay(500);
  analogReadResolution(12);
  analogSetPinAttenuation(FSR_PIN, ADC_11db);
  sensors.begin();
  sensors.setResolution(12);
  sensors.setWaitForConversion(false);
  probeCount = sensors.getDeviceCount();
  if (probeCount > 0) sensors.getAddress(probeA, 0);
  if (probeCount > 1) sensors.getAddress(probeB, 1);
  sensors.requestTemperatures();
  mpuInit();
  Serial.print("# probes=");
  Serial.print(probeCount);
  Serial.print(" mpu=");
  Serial.println(mpuOk ? 1 : 0);
  if (probeCount > 1) {
    Serial.print("# probeA=");
    for (int i = 0; i < 8; i++) { if (probeA[i] < 16) Serial.print("0"); Serial.print(probeA[i], HEX); }
    Serial.print(" probeB=");
    for (int i = 0; i < 8; i++) { if (probeB[i] < 16) Serial.print("0"); Serial.print(probeB[i], HEX); }
    Serial.println();
  }
  Serial.println("ms,raw,median,ema,baseline,net,state,transitions,t_a,t_b,ax,ay,az");
  lastSample = millis();
  lastTemp = millis();
}

void loop() {
  uint32_t now = millis();
  if (now - lastTemp >= TEMP_MS) {
    lastTemp = now;
    if (probeCount > 0) tempA = sensors.getTempC(probeA);
    if (probeCount > 1) tempB = sensors.getTempC(probeB);
    sensors.requestTemperatures();
  }
  if (now - lastSample < SAMPLE_MS) return;
  lastSample += SAMPLE_MS;

  int raw = analogRead(FSR_PIN);
  window5[windowIdx] = raw;
  windowIdx = (windowIdx + 1) % 5;
  if (windowIdx == 0) windowFull = true;
  int med = median5();
  if (!emaInit) { ema = med; emaInit = true; }
  else ema = EMA_ALPHA * med + (1.0f - EMA_ALPHA) * ema;

  float net = ema - baseline;
  bool prev = loaded;
  if (!loaded && net >= ENTER_COUNTS) loaded = true;
  else if (loaded && net < EXIT_COUNTS) loaded = false;
  if (loaded != prev) transitions++;
  if (!loaded) {
    baseline += BASELINE_RATE * (ema - baseline);
    if (baseline < 0) baseline = 0;
    if (baseline > BASELINE_CAP) baseline = BASELINE_CAP;
  }

  float ax = NAN, ay = NAN, az = NAN;
  mpuRead(ax, ay, az);

  Serial.print(now); Serial.print(',');
  Serial.print(raw); Serial.print(',');
  Serial.print(med); Serial.print(',');
  Serial.print(ema, 1); Serial.print(',');
  Serial.print(baseline, 1); Serial.print(',');
  Serial.print(net, 1); Serial.print(',');
  Serial.print(loaded ? 1 : 0); Serial.print(',');
  Serial.print(transitions); Serial.print(',');
  Serial.print(tempA, 2); Serial.print(',');
  Serial.print(tempB, 2); Serial.print(',');
  Serial.print(ax, 3); Serial.print(',');
  Serial.print(ay, 3); Serial.print(',');
  Serial.println(az, 3);
}

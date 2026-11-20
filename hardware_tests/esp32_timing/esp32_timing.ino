#include <WiFi.h>
#include <WiFiClientSecure.h>
#include <PubSubClient.h>
#include <math.h>

const char* WIFI_SSID = "YOUR_SSID";
const char* WIFI_PASS = "YOUR_PASSWORD";
const char* BROKER = "test.mosquitto.org";
const int BROKER_PORT = 8883;
const char* TOPIC = "vit-shuttle/timing/echo";
const int PUBLISHES = 100;
const int CLASSIFY_CALLS = 10000;

WiFiClientSecure tlsClient;
PubSubClient mqtt(tlsClient);
volatile bool echoed = false;

const float EPS_THERMAL = 1.5f;
const float CONTACT_MIN = 29.0f;
const float CONTACT_MAX = 38.5f;
const float CONTACT_NOMINAL = 35.0f;
const float SKIN_PULL = 0.15f;
const float CONTACT_TOL = 2.0f;
const float BLIND_MARGIN = 1.2f;
const float DECAY_TOL = 0.8f;

int window5[5];
int widx = 0;
float ema = 300.0f;
float base = 0.0f;
bool loaded = false;

int classify(float seatNow, float cabinNow, float deltaNow, float deltaThen)
{
  if (seatNow > CONTACT_MAX || seatNow < CONTACT_MIN) return 1;
  float a = fabs(deltaNow);
  float b = fabs(deltaThen);
  if (a >= EPS_THERMAL)
  {
    float expected = CONTACT_NOMINAL + SKIN_PULL * (cabinNow - CONTACT_NOMINAL);
    if (fabs(seatNow - expected) > CONTACT_TOL) return 1;
    return (a < b - DECAY_TOL) ? 1 : 2;
  }
  float half = EPS_THERMAL / (1.0f - SKIN_PULL) + BLIND_MARGIN;
  return (cabinNow >= CONTACT_NOMINAL - half && cabinNow <= CONTACT_NOMINAL + half) ? 2 : 1;
}

bool filterStep(int raw)
{
  window5[widx] = raw;
  widx = (widx + 1) % 5;
  int v[5];
  for (int i = 0; i < 5; i++) v[i] = window5[i];
  for (int i = 1; i < 5; i++)
  {
    int k = v[i];
    int j = i - 1;
    while (j >= 0 && v[j] > k) { v[j + 1] = v[j]; j--; }
    v[j + 1] = k;
  }
  ema = 0.25f * v[2] + 0.75f * ema;
  float net = ema - base;
  loaded = loaded ? net >= 1000.0f : net >= 1200.0f;
  if (!loaded) base += 0.002f * (ema - base);
  return loaded;
}

void onMessage(char* topic, byte* payload, unsigned int len)
{
  echoed = true;
}

void report(const char* name, unsigned long* v, int n)
{
  unsigned long lo = v[0], hi = v[0];
  double sum = 0;
  for (int i = 0; i < n; i++) { sum += v[i]; if (v[i] < lo) lo = v[i]; if (v[i] > hi) hi = v[i]; }
  Serial.printf("%s: n=%d mean=%.1f min=%lu max=%lu\n", name, n, sum / n, lo, hi);
}

void setup()
{
  Serial.begin(115200);
  delay(500);
  Serial.printf("CPU MHz=%d free_heap_boot=%u\n", getCpuFrequencyMhz(), ESP.getFreeHeap());

  volatile int sink = 0;
  unsigned long t0 = micros();
  for (int i = 0; i < CLASSIFY_CALLS; i++) sink += classify(33.0f + (i % 7) * 0.5f, 26.0f + (i % 5), 7.0f, 7.2f);
  unsigned long t1 = micros();
  for (int i = 0; i < CLASSIFY_CALLS; i++) sink += filterStep(300 + (i % 50) * 60);
  unsigned long t2 = micros();
  Serial.printf("classify_us_per_call=%.3f filter_us_per_sample=%.3f sink=%d\n",
                (t1 - t0) / (double)CLASSIFY_CALLS, (t2 - t1) / (double)CLASSIFY_CALLS, sink);

  WiFi.begin(WIFI_SSID, WIFI_PASS);
  while (WiFi.status() != WL_CONNECTED) delay(200);
  Serial.printf("wifi_ok free_heap=%u\n", ESP.getFreeHeap());

  tlsClient.setInsecure();
  mqtt.setServer(BROKER, BROKER_PORT);
  mqtt.setCallback(onMessage);
  uint32_t heapBefore = ESP.getFreeHeap();
  unsigned long c0 = millis();
  bool ok = mqtt.connect("vit-shuttle-timing");
  unsigned long c1 = millis();
  Serial.printf("tls_connect_ok=%d tls_connect_ms=%lu heap_drop_bytes=%d min_free_heap=%u\n",
                ok, c1 - c0, (int)heapBefore - (int)ESP.getFreeHeap(), ESP.getMinFreeHeap());
  if (!ok) return;
  mqtt.subscribe(TOPIC);

  static unsigned long pub[PUBLISHES];
  static unsigned long rtt[PUBLISHES];
  String payload = "{\"schema\":\"seat-summary/1.0\",\"bus\":\"bus001\",\"route\":\"21\",\"seq\":1,\"free_seats\":12,\"objects\":1,\"occupied\":31,\"door_open\":false}";
  int got = 0;
  for (int i = 0; i < PUBLISHES; i++)
  {
    echoed = false;
    unsigned long p0 = micros();
    mqtt.publish(TOPIC, payload.c_str());
    unsigned long p1 = micros();
    unsigned long w0 = millis();
    while (!echoed && millis() - w0 < 5000) mqtt.loop();
    pub[i] = p1 - p0;
    if (echoed) rtt[got++] = millis() - w0 + (p1 - p0) / 1000;
    delay(200);
  }
  report("publish_call_us", pub, PUBLISHES);
  if (got) report("broker_round_trip_ms", rtt, got);
  Serial.printf("echoes=%d/%d min_free_heap=%u\n", got, PUBLISHES, ESP.getMinFreeHeap());
}

void loop()
{
  mqtt.loop();
  delay(10);
}

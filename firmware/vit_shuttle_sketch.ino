#include <WiFi.h>
#include <PubSubClient.h>
#include <OneWire.h>
#include <DallasTemperature.h>
#include <math.h>

// ============================================================
//              VIT SMART SHUTTLE SYSTEM
//                 WOKWI ESP32 SIMULATION
//                  (Revision 2 — see change log)
// ============================================================
//
// CHANGE LOG (this revision vs. previous version):
//  1. Seat state "BAG" renamed to "OBJECT" throughout — the sensor
//     cannot actually tell a bag from any other non-human item, so
//     the generic term is more accurate and matches the disclosure
//     document's wording (non-human occupant / object / luggage).
//  2. HUMAN_TEMP_MIN / HUMAN_TEMP_MAX widened. The previous band
//     (36.1-37.2 C) was "normal resting body temperature" only, so
//     a student running a fever (38-41 C, or even hyperpyrexia
//     above 41.5 C) would have been WRONGLY classified as OBJECT.
//     The band is now widened to keep any plausible live human
//     reading (including a medical-emergency fever) inside the
//     HUMAN classification, while still rejecting typical ambient/
//     surface temperatures of an inanimate object.
//  3. New DOOR_SWITCH input + vehicle-stationary check. Face scans
//     are now only accepted when the vehicle is stationary AND the
//     door is open, to avoid an accidental scan while the shuttle
//     is moving or the door is shut.
//
// ============================================================


// ============================================================
// PINS
// ============================================================

#define SEAT_PIN        34   // potentiometer — simulates seat pressure sensor
#define GPS_PIN         35   // potentiometer — simulates GPS position along route
#define FACE_BUTTON      4   // pushbutton — simulates a face-scan attempt
#define WIFI_SWITCH      5   // slide switch — HIGH = WiFi available, LOW = GSM fallback
#define DOOR_SWITCH     19   // slide switch — HIGH = door open,      LOW = door closed
#define TEMP_PIN        18   // DS18B20 data pin


// ============================================================
// TEMPERATURE SENSOR
// ============================================================

OneWire oneWire(TEMP_PIN);
DallasTemperature tempSensor(&oneWire);

float currentTemperature = 36.7;
float lastTemperature = -999.0;

unsigned long lastTempRequest = 0;
const unsigned long TEMP_INTERVAL = 1000;


// ============================================================
// SEAT CLASSIFICATION
// ============================================================

const int PRESSURE_THRESHOLD = 1200;

// ---- Human temperature band (see change-log item 2) ----
// Reference points used to size this band (cite these in the
// disclosure write-up, not just here):
//   Normal body temperature   : 36.1 C - 37.2 C
//   Standard fever            : >= 38.0 C
//   High fever                : 39.4 C - 41.0 C
//   Hyperpyrexia (emergency)  : >  41.5 C, can exceed 41.5-42 C
// The lower bound is relaxed to 34.0 C to allow for the
// surface-vs-core temperature offset any contact/IR sensor reads
// (a live human's *skin* reading is always somewhat below their
// core temperature), while remaining safely above a typical
// inanimate object at cabin ambient temperature.
const float HUMAN_TEMP_MIN = 34.0;
const float HUMAN_TEMP_MAX = 42.0;

// 0 = EMPTY
// 1 = OBJECT   (non-human occupant: bag, luggage, or any other item)
// 2 = STUDENT  (human occupant, including a feverish/unwell student)

int seatState = 0;
int previousSeatState = -1;


// ============================================================
// GPS ROUTE
// ============================================================

const double START_LAT = 12.9692;
const double START_LNG = 79.1559;
const double END_LAT   = 12.9725;
const double END_LNG   = 79.1630;

double currentLat = START_LAT;
double currentLng = START_LNG;

int routeProgress = 0;
int previousRouteProgress = -1;
const int GPS_CHANGE_STEP = 5;


// ============================================================
// VEHICLE-STATIONARY DETECTION (new — change-log item 3)
// ============================================================
// Re-uses the existing GPS potentiometer as the only signal: if the
// raw GPS reading has not moved by more than STATIONARY_EPSILON
// counts since the last check, the vehicle is considered stationary.
// No extra hardware is needed for this half of the gate.

const unsigned long STATIONARY_CHECK_INTERVAL = 1000; // ms
const int STATIONARY_EPSILON = 15;                    // ~0.4% of the 0-4095 ADC range

int stationaryRefGPSRaw = -1;
unsigned long lastStationaryCheck = 0;
bool vehicleStationary = true;

void updateStationaryStatus()
{
  int rawGPS = analogRead(GPS_PIN);

  if (stationaryRefGPSRaw < 0)
  {
    stationaryRefGPSRaw = rawGPS;
    lastStationaryCheck = millis();
    return;
  }

  if (millis() - lastStationaryCheck >= STATIONARY_CHECK_INTERVAL)
  {
    int diff = abs(rawGPS - stationaryRefGPSRaw);
    vehicleStationary = (diff < STATIONARY_EPSILON);
    stationaryRefGPSRaw = rawGPS;
    lastStationaryCheck = millis();
  }
}

bool isVehicleStationary() { return vehicleStationary; }
bool isDoorOpen()          { return digitalRead(DOOR_SWITCH) == HIGH; }


// ============================================================
// DOOR / MOTION STATE EVENTS (published for the vehicle log —
// lets the backend record every enforcement transition, not just
// the fact that a scan was accepted or rejected)
// ============================================================

bool previousDoorState = true;    // true = open
bool previousMotionState = true;  // true = stationary

void checkDoorEvent()
{
  bool doorOpenNow = isDoorOpen();
  if (doorOpenNow != previousDoorState)
  {
    previousDoorState = doorOpenNow;
    String payload = doorOpenNow ? "OPEN" : "CLOSED";
    Serial.println();
    Serial.print("[DOOR EVENT] ");
    Serial.println(payload);
    publishMQTT("vit/shuttle1/door", payload);
  }
}

void checkMotionEvent()
{
  bool stationaryNow = isVehicleStationary();
  if (stationaryNow != previousMotionState)
  {
    previousMotionState = stationaryNow;
    String payload = stationaryNow ? "STATIONARY" : "MOVING";
    Serial.println();
    Serial.print("[MOTION EVENT] ");
    Serial.println(payload);
    publishMQTT("vit/shuttle1/motion", payload);
  }
}


// ============================================================
// PASSENGERS
// ============================================================

const int MAX_PASSENGERS = 30;
const long FIRST_STUDENT_ID = 21001;

int passengerCount = 0;
long passengerIDs[MAX_PASSENGERS];
double entryLat[MAX_PASSENGERS];
double entryLng[MAX_PASSENGERS];


// ============================================================
// FARE
// ============================================================

const double FARE_PER_KM = 5.0;
const double MINIMUM_FARE = 2.0;


// ============================================================
// BUTTON (short press = ENTRY, long press = EXIT — unchanged)
// ============================================================

bool previousButtonState = HIGH;
unsigned long buttonPressStart = 0;
bool longPressHandled = false;
const unsigned long LONG_PRESS_TIME = 1500;


// ============================================================
// WIFI / MQTT
// ============================================================

const char* WIFI_SSID   = "Wokwi-GUEST";
const char* WIFI_PASS   = "";
const char* MQTT_BROKER = "broker.hivemq.com";
const int   MQTT_PORT   = 1883;

WiFiClient wifiClient;
PubSubClient mqtt(wifiClient);
bool previousWifiState = true;


// ============================================================
// SEAT NAME
// ============================================================

const char* getSeatName()
{
  if (seatState == 0) return "EMPTY";
  if (seatState == 1) return "OBJECT";
  return "STUDENT";
}


// ============================================================
// TEMPERATURE REQUEST / UPDATE
// ============================================================

void requestTemperature()
{
  tempSensor.requestTemperatures();
  lastTempRequest = millis();
}

void updateTemperature()
{
  if (millis() - lastTempRequest >= 1000)
  {
    float newTemperature = tempSensor.getTempCByIndex(0);
    if (newTemperature > -100 && newTemperature < 150)
    {
      currentTemperature = newTemperature;
    }
    requestTemperature();
  }
}


// ============================================================
// DISTANCE CALCULATION
// ============================================================

double calculateDistanceKm(double lat1, double lon1, double lat2, double lon2)
{
  const double EARTH_RADIUS = 6371.0;
  double dLat = radians(lat2 - lat1);
  double dLon = radians(lon2 - lon1);
  double a = sin(dLat / 2.0) * sin(dLat / 2.0)
             + cos(radians(lat1)) * cos(radians(lat2)) * sin(dLon / 2.0) * sin(dLon / 2.0);
  double c = 2.0 * atan2(sqrt(a), sqrt(1.0 - a));
  return EARTH_RADIUS * c;
}


// ============================================================
// WIFI STATUS
// ============================================================

bool wifiAvailable() { return digitalRead(WIFI_SWITCH) == HIGH; }


// ============================================================
// MQTT PUBLISH (falls back to GSM-style log line if WiFi is down)
// ============================================================

void publishMQTT(const char* topic, String payload)
{
  bool wifiDisabled = digitalRead(WIFI_SWITCH) == LOW;

  if (!wifiDisabled && WiFi.status() == WL_CONNECTED && mqtt.connected())
  {
    mqtt.publish(topic, payload.c_str());
    Serial.print("[MQTT] ");
    Serial.print(topic);
    Serial.print(" -> ");
    Serial.println(payload);
  }
  else
  {
    Serial.print("[GSM FALLBACK] ");
    Serial.print(topic);
    Serial.print(" -> ");
    Serial.println(payload);
  }
}


// ============================================================
// MQTT / WIFI CONNECTION
// ============================================================

void reconnectMQTT()
{
  if (WiFi.status() != WL_CONNECTED) return;
  if (mqtt.connected()) return;

  Serial.print("[MQTT] Connecting... ");
  String clientID = "VIT-Shuttle-ESP32-";
  clientID += String((uint32_t)ESP.getEfuseMac(), HEX);

  if (mqtt.connect(clientID.c_str()))
  {
    Serial.println("OK");
  }
  else
  {
    Serial.print("FAILED rc=");
    Serial.println(mqtt.state());
  }
}

void connectWiFi()
{
  Serial.println();
  Serial.println("[WiFi] Connecting to Wokwi-GUEST...");
  WiFi.begin(WIFI_SSID, WIFI_PASS);

  unsigned long start = millis();
  while (WiFi.status() != WL_CONNECTED && millis() - start < 10000)
  {
    delay(250);
    Serial.print(".");
  }
  Serial.println();

  if (WiFi.status() == WL_CONNECTED)
  {
    Serial.println("[WiFi] CONNECTED");
    Serial.print("[WiFi] IP: ");
    Serial.println(WiFi.localIP());
    mqtt.setServer(MQTT_BROKER, MQTT_PORT);
    reconnectMQTT();
  }
  else
  {
    Serial.println("[WiFi] CONNECTION FAILED");
    Serial.println("[Network] GSM FALLBACK MODE");
  }
}


// ============================================================
// GPS UPDATE / EVENT
// ============================================================

void updateGPS()
{
  int rawGPS = analogRead(GPS_PIN);
  double ratio = (double)rawGPS / 4095.0;

  currentLat = START_LAT + ratio * (END_LAT - START_LAT);
  currentLng = START_LNG + ratio * (END_LNG - START_LNG);

  routeProgress = (int)(ratio * 100.0);
  if (routeProgress < 0) routeProgress = 0;
  if (routeProgress > 100) routeProgress = 100;
}

void checkGPS()
{
  updateGPS();

  if (previousRouteProgress == -1)
  {
    previousRouteProgress = routeProgress;
    return;
  }

  int difference = abs(routeProgress - previousRouteProgress);

  if (difference >= GPS_CHANGE_STEP)
  {
    previousRouteProgress = routeProgress;

    Serial.println();
    Serial.println("----------------------------------------");
    Serial.println("[GPS EVENT]");
    Serial.print("Location : ");
    Serial.print(currentLat, 6);
    Serial.print(", ");
    Serial.println(currentLng, 6);
    Serial.print("Route    : ");
    Serial.print(routeProgress);
    Serial.println("%");
    Serial.println("----------------------------------------");

    String payload = String(currentLat, 6) + "," + String(currentLng, 6);
    publishMQTT("vit/shuttle1/gps", payload);
  }
}


// ============================================================
// SEAT CLASSIFICATION
// ============================================================

void checkSeat()
{
  int pressure = analogRead(SEAT_PIN);
  bool pressureDetected = pressure >= PRESSURE_THRESHOLD;
  bool humanTemperature = currentTemperature >= HUMAN_TEMP_MIN && currentTemperature <= HUMAN_TEMP_MAX;

  int newState;
  if (!pressureDetected)       newState = 0;       // EMPTY
  else if (humanTemperature)   newState = 2;        // STUDENT
  else                         newState = 1;        // OBJECT

  seatState = newState;

  if (seatState != previousSeatState)
  {
    previousSeatState = seatState;

    Serial.println();
    Serial.println("========================================");
    Serial.println("             SEAT STATUS");
    Serial.println("========================================");
    Serial.print("State       : ");
    Serial.println(getSeatName());
    Serial.print("Pressure    : ");
    Serial.println(pressure);
    Serial.print("Temperature : ");
    Serial.print(currentTemperature, 1);
    Serial.println(" C");
    Serial.println("----------------------------------------");

    if (seatState == 0)      Serial.println("Result      : SEAT EMPTY");
    else if (seatState == 1) Serial.println("Result      : NON-HUMAN OBJECT (e.g. bag / luggage)");
    else                     Serial.println("Result      : HUMAN OCCUPANT (STUDENT)");

    Serial.println("========================================");

    String payload = String(getSeatName()) + ",TEMP=" + String(currentTemperature, 1) + ",PRESSURE=" + String(pressure);
    publishMQTT("vit/shuttle1/seat", payload);
  }
}


// ============================================================
// TEMPERATURE EVENT (standalone display / classification log)
// ============================================================

void checkTemperatureDisplay()
{
  if (lastTemperature < -900)
  {
    lastTemperature = currentTemperature;
    return;
  }

  if (fabs(currentTemperature - lastTemperature) >= 0.5)
  {
    lastTemperature = currentTemperature;

    Serial.println();
    Serial.println("[TEMPERATURE]");
    Serial.print("Temperature : ");
    Serial.print(currentTemperature, 1);
    Serial.println(" C");

    if (currentTemperature >= HUMAN_TEMP_MIN && currentTemperature <= HUMAN_TEMP_MAX)
    {
      Serial.println("Classification: HUMAN-PLAUSIBLE RANGE");
      if (currentTemperature >= 41.5)
        Serial.println("Note          : HYPERPYREXIA RANGE (>41.5 C) - medical emergency, still classified HUMAN");
      else if (currentTemperature >= 38.0)
        Serial.println("Note          : FEVER RANGE (>=38.0 C) - still classified HUMAN, not OBJECT");
    }
    else
    {
      Serial.println("Classification: OUTSIDE HUMAN-PLAUSIBLE RANGE");
    }
    Serial.println();
  }
}


// ============================================================
// NETWORK EVENT
// ============================================================

void checkNetwork()
{
  bool currentWifi = wifiAvailable();

  if (currentWifi != previousWifiState)
  {
    previousWifiState = currentWifi;

    Serial.println();
    Serial.println("========================================");
    Serial.println("             NETWORK STATUS");
    Serial.println("========================================");

    if (currentWifi)
    {
      Serial.println("WiFi : ONLINE");
      Serial.println("MQTT : ONLINE");
      Serial.println("Mode : NORMAL");
      if (WiFi.status() != WL_CONNECTED) connectWiFi();
      reconnectMQTT();
    }
    else
    {
      Serial.println("WiFi : OFFLINE");
      Serial.println("MQTT : OFFLINE");
      Serial.println("Mode : GSM FALLBACK");
    }
    Serial.println("========================================");
  }
}


// ============================================================
// BOARDING GATE (new — change-log item 3)
// ============================================================
// Both passengerEntry() and passengerExit() are now only reachable
// through this gate, so a face-scan attempt while the vehicle is
// moving or the door is shut is rejected before it can register.

bool scanAllowed(const char* attemptedAction)
{
  bool stationary = isVehicleStationary();
  bool doorOpen = isDoorOpen();

  if (stationary && doorOpen) return true;

  Serial.println();
  Serial.println("========================================");
  Serial.println("        FACE SCAN REJECTED");
  Serial.println("========================================");
  Serial.print("Attempted   : ");
  Serial.println(attemptedAction);
  if (!stationary) Serial.println("Reason      : VEHICLE IS MOVING");
  if (!doorOpen)   Serial.println("Reason      : DOOR IS CLOSED");
  Serial.println("Action      : scan not logged, re-attempt once stationary/door open");
  Serial.println("========================================");

  return false;
}


// ============================================================
// PASSENGER ENTRY
// ============================================================

void passengerEntry()
{
  if (!scanAllowed("ENTRY")) return;

  if (passengerCount >= MAX_PASSENGERS)
  {
    Serial.println();
    Serial.println("[ENTRY DENIED] SHUTTLE FULL");
    return;
  }

  int index = passengerCount;
  passengerIDs[index] = FIRST_STUDENT_ID + index;
  entryLat[index] = currentLat;
  entryLng[index] = currentLng;
  passengerCount++;

  Serial.println();
  Serial.println("========================================");
  Serial.println("           FACE SCAN - ENTRY");
  Serial.println("========================================");
  Serial.println("Face scan : VERIFIED");
  Serial.print("Student   : VIT");
  Serial.println(passengerIDs[index]);
  Serial.print("Location  : ");
  Serial.print(currentLat, 6);
  Serial.print(", ");
  Serial.println(currentLng, 6);
  Serial.print("Passengers: ");
  Serial.print(passengerCount);
  Serial.print(" / ");
  Serial.println(MAX_PASSENGERS);
  Serial.print("Seats free: ");
  Serial.println(MAX_PASSENGERS - passengerCount);
  Serial.println("Status    : ON BOARD");
  Serial.println("========================================");

  String payload = "ENTRY,VIT" + String(passengerIDs[index]) + "," + String(currentLat, 6) + "," + String(currentLng, 6);
  publishMQTT("vit/shuttle1/billing", payload);
}


// ============================================================
// PASSENGER EXIT
// ============================================================

void passengerExit()
{
  if (!scanAllowed("EXIT")) return;

  if (passengerCount <= 0)
  {
    Serial.println();
    Serial.println("[EXIT DENIED] NO PASSENGERS");
    return;
  }

  int index = passengerCount - 1;
  double distance = calculateDistanceKm(entryLat[index], entryLng[index], currentLat, currentLng);
  double fare = distance * FARE_PER_KM;
  if (fare < MINIMUM_FARE) fare = MINIMUM_FARE;

  Serial.println();
  Serial.println("========================================");
  Serial.println("            TRIP COMPLETED");
  Serial.println("========================================");
  Serial.println("Face scan : VERIFIED");
  Serial.print("Student   : VIT");
  Serial.println(passengerIDs[index]);
  Serial.print("Distance  : ");
  Serial.print(distance, 2);
  Serial.println(" km");
  Serial.print("Fare      : Rs ");
  Serial.println(fare, 2);

  passengerCount--;

  Serial.print("Passengers: ");
  Serial.print(passengerCount);
  Serial.print(" / ");
  Serial.println(MAX_PASSENGERS);
  Serial.println("Payment   : FEE ACCOUNT");
  Serial.println("Status    : COMPLETED");
  Serial.println("========================================");

  String payload = "EXIT,VIT" + String(passengerIDs[index]) + "," + String(distance, 2) + "km,Rs" + String(fare, 2);
  publishMQTT("vit/shuttle1/billing", payload);
}


// ============================================================
// BUTTON (short press = ENTRY, long press = EXIT — unchanged)
// ============================================================

void checkButton()
{
  bool currentState = digitalRead(FACE_BUTTON);

  if (currentState == LOW && previousButtonState == HIGH)
  {
    buttonPressStart = millis();
    longPressHandled = false;
  }

  if (currentState == LOW && !longPressHandled)
  {
    if (millis() - buttonPressStart >= LONG_PRESS_TIME)
    {
      longPressHandled = true;
      passengerExit();
    }
  }

  if (currentState == HIGH && previousButtonState == LOW)
  {
    if (!longPressHandled) passengerEntry();
  }

  previousButtonState = currentState;
}


// ============================================================
// SETUP
// ============================================================

void setup()
{
  Serial.begin(115200);

  pinMode(FACE_BUTTON, INPUT_PULLUP);
  pinMode(WIFI_SWITCH, INPUT_PULLUP);
  pinMode(DOOR_SWITCH, INPUT_PULLUP);

  tempSensor.begin();
  tempSensor.setResolution(9);
  tempSensor.setWaitForConversion(false);

  delay(1000);

  Serial.println();
  Serial.println("============================================================");
  Serial.println("              VIT SMART SHUTTLE SYSTEM");
  Serial.println("                 WOKWI SIMULATION  (Rev. 2)");
  Serial.println("============================================================");
  Serial.println("[SYSTEM] ESP32 initialized");
  Serial.println("[SYSTEM] GPIO34 = seat pressure sensor");
  Serial.println("[SYSTEM] GPIO35 = GPS simulator");
  Serial.println("[SYSTEM] GPIO18 = temperature sensor (DS18B20)");
  Serial.println("[SYSTEM] GPIO4  = face scan button");
  Serial.println("[SYSTEM] GPIO5  = WiFi/GSM switch");
  Serial.println("[SYSTEM] GPIO19 = door open/closed switch");

  updateGPS();
  previousRouteProgress = routeProgress;
  stationaryRefGPSRaw = -1;

  requestTemperature();
  delay(150);
  currentTemperature = tempSensor.getTempCByIndex(0);
  if (currentTemperature < -100 || currentTemperature > 150) currentTemperature = 36.7;

  int pressure = analogRead(SEAT_PIN);
  if (pressure < PRESSURE_THRESHOLD) seatState = 0;
  else if (currentTemperature >= HUMAN_TEMP_MIN && currentTemperature <= HUMAN_TEMP_MAX) seatState = 2;
  else seatState = 1;
  previousSeatState = seatState;

  previousWifiState = wifiAvailable();

  connectWiFi();

  Serial.println();
  Serial.println("============================================================");
  Serial.println("                         READY");
  Serial.println("============================================================");
  Serial.println("CONTROLS");
  Serial.println("  Left Pot   = Seat pressure");
  Serial.println("  Right Pot  = GPS position (also used to detect 'stationary')");
  Serial.println("  DS18B20    = Temperature");
  Serial.println("  Button     = Face scan (short = entry, long = exit)");
  Serial.println("  WiFi Switch  = WiFi / GSM fallback");
  Serial.println("  Door Switch  = Door open / closed (gates face scan)");
  Serial.println("============================================================");
  Serial.println();
}


// ============================================================
// MAIN LOOP
// ============================================================

void loop()
{
  updateTemperature();
  checkTemperatureDisplay();
  checkSeat();
  checkGPS();
  updateStationaryStatus();
  checkDoorEvent();
  checkMotionEvent();
  checkNetwork();
  checkButton();

  if (WiFi.status() == WL_CONNECTED)
  {
    reconnectMQTT();
    mqtt.loop();
  }

  delay(10);
}

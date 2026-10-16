/*
  servo-follow — Arduino Uno + HC-SR04 + hobby servo (closed loop)
  Author: Alp Serkan Merkit (2026), MIT License
  Rewritten in 2026 · not tested with a servo — on the bench the same proximity loop drove a propeller motor in place of the servo (according to the owner).

  What it does
    The servo arm "points" at how far the object is:
      5 cm  -> 0 deg      50 cm -> 180 deg      (linear in between)
    Move your hand and the arm follows. If the object is lost for
    1.5 s, the arm slowly returns to the 90 deg home position.

  Wiring (see docs/wiring.png)
    HC-SR04  VCC -> 5V, GND -> GND, TRIG -> D9, ECHO -> D10
    Servo    brown/black -> GND, red -> 5V, orange/yellow (signal) -> D11
    A micro servo (SG90) can run from the Uno 5 V pin. Bigger servos
    (MG996R etc.) need their own 5-6 V supply with GND shared with the Uno.

  Smoothing chain (each step removes a different kind of noise)
    1. median of the last 3 pings   -> kills single spikes / missed echoes
    2. exponential moving average   -> removes jitter
    3. deadband of 2 deg            -> servo is not re-commanded for tiny changes
    4. slew limit of 4 deg per step -> no violent jumps

  Note: the Servo library uses Timer1, which disables analogWrite() on D9/D10.
  We only use D9/D10 as plain digital pins, so that is fine.
*/
#include <Servo.h>

// ---------------------------------------------------------------- pins
const uint8_t PIN_TRIG  = 9;
const uint8_t PIN_ECHO  = 10;
const uint8_t PIN_SERVO = 11;

// ---------------------------------------------------------------- tuning
const float    NEAR_CM        = 5.0;     // -> ANGLE_NEAR
const float    FAR_CM         = 50.0;    // -> ANGLE_FAR
const float    MAX_RANGE_CM   = 400.0;   // "no echo" value
const int      ANGLE_NEAR     = 0;
const int      ANGLE_FAR      = 180;
const int      ANGLE_HOME     = 90;
const float    EMA_ALPHA      = 0.35;    // 0..1, higher = faster but noisier
const int      DEADBAND_DEG   = 2;
const int      MAX_STEP_DEG   = 4;       // per update (every MEASURE_MS)
const unsigned long ECHO_TIMEOUT_US = 25000UL;
const unsigned long MEASURE_MS      = 60;
const unsigned long LOST_MS         = 1500;
const unsigned long PRINT_MS        = 250;

Servo arm;

float samples[3] = {MAX_RANGE_CM, MAX_RANGE_CM, MAX_RANGE_CM};
uint8_t sampleIdx = 0;
float filteredCm = (NEAR_CM + FAR_CM) / 2;
float rawMedianCm = MAX_RANGE_CM;
int   targetDeg  = ANGLE_HOME;
int   servoDeg   = ANGLE_HOME;
bool  tracking   = false;

unsigned long lastMeasure = 0;
unsigned long lastSeen    = 0;
unsigned long lastPrint   = 0;

float readDistanceCm() {
  digitalWrite(PIN_TRIG, LOW);
  delayMicroseconds(2);
  digitalWrite(PIN_TRIG, HIGH);
  delayMicroseconds(10);
  digitalWrite(PIN_TRIG, LOW);

  unsigned long us = pulseIn(PIN_ECHO, HIGH, ECHO_TIMEOUT_US);
  if (us == 0) return MAX_RANGE_CM;
  float cm = us / 58.0;
  return (cm > MAX_RANGE_CM) ? MAX_RANGE_CM : cm;
}

float median3(float a, float b, float c) {
  if (a > b) { float t = a; a = b; b = t; }
  if (b > c) { float t = b; b = c; c = t; }
  if (a > b) { float t = a; a = b; b = t; }
  return b;
}

int angleFor(float cm) {
  if (cm < NEAR_CM) cm = NEAR_CM;
  if (cm > FAR_CM)  cm = FAR_CM;
  float k = (cm - NEAR_CM) / (FAR_CM - NEAR_CM);         // 0..1
  return (int)(ANGLE_NEAR + k * (ANGLE_FAR - ANGLE_NEAR) + 0.5);
}

void updateControl(unsigned long now) {
  samples[sampleIdx] = readDistanceCm();
  sampleIdx = (sampleIdx + 1) % 3;
  rawMedianCm = median3(samples[0], samples[1], samples[2]);

  // Only readings inside a sensible window count as "object seen".
  bool valid = rawMedianCm < FAR_CM * 1.5;
  if (valid) {
    filteredCm = tracking ? filteredCm + EMA_ALPHA * (rawMedianCm - filteredCm)
                          : rawMedianCm;               // first sight: no lag
    tracking = true;
    lastSeen = now;
    int wanted = angleFor(filteredCm);
    if (abs(wanted - targetDeg) > DEADBAND_DEG) targetDeg = wanted;
  } else if (now - lastSeen > LOST_MS) {
    tracking = false;
    targetDeg = ANGLE_HOME;                           // object gone: go home
  }

  // Slew limit: move at most MAX_STEP_DEG toward the target per update.
  int step = constrain(targetDeg - servoDeg, -MAX_STEP_DEG, MAX_STEP_DEG);
  if (step != 0) {
    servoDeg += step;
    arm.write(servoDeg);
  }
}

void setup() {
  pinMode(PIN_TRIG, OUTPUT);
  pinMode(PIN_ECHO, INPUT);
  digitalWrite(PIN_TRIG, LOW);
  arm.attach(PIN_SERVO);
  arm.write(servoDeg);
  Serial.begin(9600);
  Serial.println(F("servo-follow ready"));
}

void loop() {
  unsigned long now = millis();

  if (now - lastMeasure >= MEASURE_MS) {
    lastMeasure = now;
    updateControl(now);
  }

  if (now - lastPrint >= PRINT_MS) {
    lastPrint = now;
    Serial.print(F("median_cm="));
    if (rawMedianCm >= MAX_RANGE_CM) Serial.print(F("none"));
    else Serial.print(rawMedianCm, 1);
    Serial.print(F(" filtered_cm="));
    Serial.print(filteredCm, 1);
    Serial.print(F(" target_deg="));
    Serial.print(targetDeg);
    Serial.print(F(" servo_deg="));
    Serial.print(servoDeg);
    Serial.println(tracking ? F(" tracking") : F(" idle"));
  }
}

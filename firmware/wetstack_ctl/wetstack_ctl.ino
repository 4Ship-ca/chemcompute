// WetStack-0 controller firmware
// Board: classic ESP32 (ESP32-WROOM-32 DevKit V1). Arduino-ESP32 core 2.x or 3.x.
// Libraries (Library Manager): Adafruit ADS1X15, Adafruit AS7341, Adafruit INA219,
//                               OneWire, DallasTemperature.
// Protocol: one text command per line at 115200 baud; one JSON object per reply line.
// Long commands (IV, SINE) stream rows and end with {"done":true}.

#include <Wire.h>
#include <Preferences.h>
#include <Adafruit_ADS1X15.h>
#include <Adafruit_AS7341.h>
#include <Adafruit_INA219.h>
#include <OneWire.h>
#include <DallasTemperature.h>
#include "esp_system.h"

// ---------------------------------------------------------------- pins
const int PIN_SDA = 21, PIN_SCL = 22;
const int PIN_DAC1 = 25, PIN_DAC2 = 26;
const int PIN_RELAY_EN = 16;           // CH1 master enable
const int PIN_RELAY_POL = 17;          // CH2 + CH3 (both IN pins) polarity pair
const int PIN_WELL[5] = {18, 19, 23, 32, 33};   // CH4..CH8
const int PIN_MIX = 13;                // MOSFET module: vibration motor
const int PIN_LED = 14;                // MOSFET module: fiber LED
const int PIN_ONEWIRE = 4;
const int PIN_STATUS = 2;

const bool RELAY_ACTIVE_LOW = true;    // most opto relay boards switch on a LOW input
const float OVERCURRENT_MA = 15.0;
const float NO_CURRENT_MA = 0.05;
const float MAX_DOSE_MC = 2000.0;
const char *FW = "wetstack-1.0";

Adafruit_ADS1115 ads1;                 // 0x48: electrolysis shunt (A0-A1)
Adafruit_ADS1115 ads2;                 // 0x49: diode sense (A0-A1) and cell (A2-A3)
Adafruit_AS7341 as7341;
Adafruit_INA219 ina219;
OneWire oneWire(PIN_ONEWIRE);
DallasTemperature temps(&oneWire);
Preferences prefs;

bool hasAds1 = false, hasAds2 = false, hasSpec = false, hasIna = false, hasTemp = false;
float shuntOhm = 100.0;
float senseOhm = 1000.0;
uint32_t boots = 0;
int activeWell = 0;                    // 0 = none; firmware interlock guarantees at most one

// ---------------------------------------------------------------- relays
void relayWrite(int pin, bool on) {
  digitalWrite(pin, (on ^ RELAY_ACTIVE_LOW) ? HIGH : LOW);
}

void relayInit(int pin) {
  digitalWrite(pin, RELAY_ACTIVE_LOW ? HIGH : LOW);   // off before becoming an output
  pinMode(pin, OUTPUT);
  relayWrite(pin, false);
}

void allOff() {
  relayWrite(PIN_RELAY_EN, false);
  delay(30);
  for (int i = 0; i < 5; i++) relayWrite(PIN_WELL[i], false);
  relayWrite(PIN_RELAY_POL, false);
  activeWell = 0;
  analogWrite(PIN_MIX, 0);
  digitalWrite(PIN_LED, LOW);
  dacWrite(PIN_DAC1, 0);
  dacWrite(PIN_DAC2, 0);
  digitalWrite(PIN_STATUS, LOW);
}

// Interlock: every well relay is switched off before one is switched on.
void selectWell(int w) {
  for (int i = 0; i < 5; i++) relayWrite(PIN_WELL[i], false);
  delay(30);
  if (w >= 1 && w <= 5) {
    relayWrite(PIN_WELL[w - 1], true);
    activeWell = w;
  } else {
    activeWell = 0;
  }
}

int countActiveWells() {
  int n = 0;
  for (int i = 0; i < 5; i++) {
    bool level = digitalRead(PIN_WELL[i]);
    bool on = RELAY_ACTIVE_LOW ? (level == LOW) : (level == HIGH);
    if (on) n++;
  }
  return n;
}

// ---------------------------------------------------------------- helpers
float shuntmA() {
  int16_t raw = ads1.readADC_Differential_0_1();
  return ads1.computeVolts(raw) / shuntOhm * 1000.0;
}

void setDiff(float v) {
  if (v > 3.2) v = 3.2;
  if (v < -3.2) v = -3.2;
  int code = (int)(fabs(v) / 3.3 * 255.0 + 0.5);
  if (code > 255) code = 255;
  if (v >= 0) { dacWrite(PIN_DAC1, code); dacWrite(PIN_DAC2, 0); }
  else        { dacWrite(PIN_DAC1, 0);    dacWrite(PIN_DAC2, code); }
}

void readDiode(float &vCell, float &iuA) {
  float vs = 0, vc = 0;
  const int n = 8;
  for (int k = 0; k < n; k++) {
    ads2.setGain(GAIN_EIGHT);          // +/-0.512 V across the 1 kohm sense resistor
    vs += ads2.computeVolts(ads2.readADC_Differential_0_1());
    ads2.setGain(GAIN_ONE);            // +/-4.096 V across the cell
    vc += ads2.computeVolts(ads2.readADC_Differential_2_3());
  }
  vs /= n; vc /= n;
  iuA = vs / senseOhm * 1e6;
  vCell = vc;
}

void err(const char *msg) {
  Serial.printf("{\"ok\":false,\"err\":\"%s\"}\n", msg);
}

// ---------------------------------------------------------------- commands
void cmdPing() {
  esp_reset_reason_t rr = esp_reset_reason();
  Serial.printf("{\"ok\":true,\"fw\":\"%s\",\"ads1\":%s,\"ads2\":%s,\"as7341\":%s,\"ina219\":%s,"
                "\"ds18b20\":%s,\"boots\":%lu,\"reset_reason\":%d,\"brownout_reset\":%s,\"uptime_ms\":%lu,"
                "\"shunt_ohm\":%.3f}\n",
                FW, hasAds1 ? "true" : "false", hasAds2 ? "true" : "false", hasSpec ? "true" : "false",
                hasIna ? "true" : "false", hasTemp ? "true" : "false", (unsigned long)boots, (int)rr,
                rr == ESP_RST_BROWNOUT ? "true" : "false", (unsigned long)millis(), shuntOhm);
}

void cmdRelayTest() {
  allOff();
  int pins[7] = {PIN_RELAY_EN, PIN_RELAY_POL, PIN_WELL[0], PIN_WELL[1], PIN_WELL[2], PIN_WELL[3], PIN_WELL[4]};
  for (int i = 0; i < 7; i++) {
    relayWrite(pins[i], true);
    delay(300);
    relayWrite(pins[i], false);
    delay(150);
  }
  bool pass = true;
  for (int w = 1; w <= 5; w++) {
    selectWell(w);
    selectWell((w % 5) + 1);
    if (countActiveWells() != 1) pass = false;
  }
  allOff();
  Serial.printf("{\"ok\":true,\"channels\":8,\"interlock\":\"%s\"}\n", pass ? "PASS" : "FAIL");
}

void cmdDose(int well, const char *mode, float targetmC, float maxS) {
  if (!hasAds1) { err("ADS1115 #1 (0x48) not found"); return; }
  if (well < 1 || well > 5) { err("well must be 1-5"); return; }
  bool acid = strcmp(mode, "ACID") == 0;
  bool base = strcmp(mode, "BASE") == 0;
  if (!acid && !base) { err("mode must be ACID or BASE"); return; }
  if (targetmC <= 0 || targetmC > MAX_DOSE_MC) { err("charge out of range"); return; }
  if (maxS <= 0 || maxS > 1800) maxS = 300;

  allOff();
  digitalWrite(PIN_STATUS, HIGH);
  relayWrite(PIN_RELAY_POL, base);     // off = ACID (well electrode is the anode)
  delay(30);
  selectWell(well);
  delay(30);
  relayWrite(PIN_RELAY_EN, true);

  uint32_t t0 = micros(), tLast = t0, tIna = t0;
  float qmC = 0, peak = 0, sumI = 0, lastI = 0, energymJ = 0;
  uint32_t samples = 0, overSince = 0;
  bool over = false, timeout = false, noCurrent = false, saturated = false;
  while (true) {
    float i = shuntmA();
    uint32_t t = micros();
    float dt = (t - tLast) / 1e6;
    tLast = t;
    qmC += 0.5 * (i + lastI) * dt;     // mA * s = mC
    lastI = i;
    sumI += i; samples++;
    if (i > peak) peak = i;
    if (i > 20.0) saturated = true;
    if (hasIna && (t - tIna) > 20000) {
      energymJ += ina219.getPower_mW() * ((t - tIna) / 1e6);
      tIna = t;
    }
    if (i > OVERCURRENT_MA) {
      if (overSince == 0) overSince = t;
      if (t - overSince > 200000) { over = true; break; }
    } else {
      overSince = 0;
    }
    float elapsed = (t - t0) / 1e6;
    if (elapsed > 3.0 && (sumI / samples) < NO_CURRENT_MA) { noCurrent = true; break; }
    if (qmC >= targetmC) break;
    if (elapsed > maxS) { timeout = true; break; }
  }
  relayWrite(PIN_RELAY_EN, false);
  delay(30);
  selectWell(0);
  relayWrite(PIN_RELAY_POL, false);
  digitalWrite(PIN_STATUS, LOW);
  float dur = (tLast - t0) / 1e6;
  bool ok = !over && !noCurrent;
  char energy[24];
  if (hasIna) snprintf(energy, sizeof(energy), "%.2f", energymJ);
  else snprintf(energy, sizeof(energy), "null");
  Serial.printf("{\"ok\":%s,\"well\":%d,\"mode\":\"%s\",\"target_mC\":%.4f,\"delivered_mC\":%.4f,"
                "\"duration_s\":%.3f,\"mean_mA\":%.4f,\"peak_mA\":%.4f,\"overrange\":%s,\"overcurrent\":%s,"
                "\"timeout\":%s,\"no_current\":%s,\"energy_mJ\":%s%s}\n",
                ok ? "true" : "false", well, acid ? "ACID" : "BASE", targetmC, qmC, dur,
                samples ? sumI / samples : 0.0, peak, saturated ? "true" : "false",
                over ? "true" : "false", timeout ? "true" : "false", noCurrent ? "true" : "false",
                energy,
                noCurrent ? ",\"err\":\"no current: check salt bridge and electrode\"" :
                over ? ",\"err\":\"overcurrent: check for a short\"" : "");
}

void cmdMix(float seconds, int duty) {
  if (seconds < 0 || seconds > 120) { err("mix seconds 0-120"); return; }
  if (duty < 0) duty = 0;
  if (duty > 100) duty = 100;
  analogWrite(PIN_MIX, duty * 255 / 100);
  delay((uint32_t)(seconds * 1000));
  analogWrite(PIN_MIX, 0);
  Serial.printf("{\"ok\":true,\"mixed_s\":%.1f}\n", seconds);
}

bool readSpec(uint16_t out[10]) {
  uint16_t r[12];
  if (!as7341.readAllChannels(r)) return false;
  // F1-F4 = r[0..3], F5-F8 = r[6..9], clear = r[10], NIR = r[11]
  out[0] = r[0]; out[1] = r[1]; out[2] = r[2]; out[3] = r[3];
  out[4] = r[6]; out[5] = r[7]; out[6] = r[8]; out[7] = r[9];
  out[8] = r[10]; out[9] = r[11];
  return true;
}

void printArr(const char *name, uint16_t *a, int n, bool comma) {
  Serial.printf("\"%s\":[", name);
  for (int i = 0; i < n; i++) Serial.printf("%u%s", a[i], i < n - 1 ? "," : "");
  Serial.printf("]%s", comma ? "," : "");
}

void cmdSpec(bool diff, bool boardLed) {
  if (!hasSpec) { err("AS7341 not found"); return; }
  uint16_t on[10], off[10], d[10];
  if (boardLed) { as7341.setLEDCurrent(10); as7341.enableLED(true); }
  else digitalWrite(PIN_LED, HIGH);
  delay(50);
  bool okOn = readSpec(on);
  if (boardLed) as7341.enableLED(false); else digitalWrite(PIN_LED, LOW);
  delay(50);
  bool okOff = readSpec(off);
  if (!okOn || !okOff) { err("AS7341 read failed"); return; }
  for (int i = 0; i < 10; i++) {
    int32_t v = (int32_t)on[i] - (int32_t)off[i];
    d[i] = v < 0 ? 0 : (uint16_t)v;
  }
  Serial.print("{\"ok\":true,\"bands_nm\":[415,445,480,515,555,590,630,680],");
  uint16_t onB[8], offB[8], dB[8];
  for (int i = 0; i < 8; i++) { onB[i] = on[i]; offB[i] = off[i]; dB[i] = diff ? d[i] : on[i]; }
  printArr("on", onB, 8, true);
  printArr("off", offB, 8, true);
  printArr("diff", dB, 8, true);
  Serial.printf("\"clear_on\":%u,\"nir_on\":%u}\n", on[8], on[9]);
}

void cmdTemp() {
  if (!hasTemp) { err("DS18B20 not found"); return; }
  temps.requestTemperatures();
  float c = temps.getTempCByIndex(0);
  if (c == DEVICE_DISCONNECTED_C) { err("DS18B20 disconnected"); return; }
  Serial.printf("{\"ok\":true,\"temp_C\":%.3f}\n", c);
}

void cmdPower() {
  if (!hasIna) { err("INA219 not found"); return; }
  Serial.printf("{\"ok\":true,\"bus_V\":%.3f,\"current_mA\":%.2f,\"power_mW\":%.1f}\n",
                ina219.getBusVoltage_V(), ina219.getCurrent_mA(), ina219.getPower_mW());
}

void cmdIV(float vmin, float vmax, float step, int dwellMs) {
  if (!hasAds2) { err("ADS1115 #2 (0x49) not found"); return; }
  if (step == 0 || (vmax - vmin) / step < 0) { err("step sign does not reach vmax"); return; }
  int n = (int)lroundf((vmax - vmin) / step) + 1;
  if (n > 400) { err("too many points"); return; }
  if (dwellMs < 50) dwellMs = 50;
  for (int k = 0; k < n; k++) {
    float v = vmin + k * step;
    setDiff(v);
    delay(dwellMs);
    float vc, i;
    readDiode(vc, i);
    Serial.printf("{\"v_set\":%.4f,\"v_cell\":%.5f,\"i_uA\":%.4f}\n", v, vc, i);
  }
  setDiff(0);
  Serial.println("{\"done\":true}");
}

void cmdSine(float freq, float amp, int cycles) {
  if (!hasAds2) { err("ADS1115 #2 (0x49) not found"); return; }
  if (freq <= 0 || freq > 5 || amp <= 0 || amp > 3.2 || cycles < 1 || cycles > 20) { err("sine args"); return; }
  const uint32_t stepMs = 50;
  uint32_t steps = (uint32_t)(cycles / freq * 1000.0 / stepMs);
  uint32_t t0 = millis();
  for (uint32_t k = 0; k < steps; k++) {
    float t = (millis() - t0) / 1000.0;
    float v = amp * sinf(2 * PI * freq * t);
    setDiff(v);
    float vc, i;
    readDiode(vc, i);
    Serial.printf("{\"t_s\":%.3f,\"v_set\":%.4f,\"v_cell\":%.5f,\"i_uA\":%.4f}\n", t, v, vc, i);
    while (millis() - t0 < (k + 1) * stepMs) delay(1);
  }
  setDiff(0);
  Serial.println("{\"done\":true}");
}

void cmdHelp() {
  Serial.println("{\"ok\":true,\"commands\":\"PING|RELAYTEST|DOSE w ACID|BASE mC [max_s]|MIX s [duty]|"
                 "SPEC [DIFF|ON] [EXT|BOARD]|TEMP|POWER|IV vmin vmax step dwell_ms|SINE f amp cycles|"
                 "SET SHUNT ohm|SET SENSE ohm|SAFE|HELP\"}");
}

// ---------------------------------------------------------------- main
char line[160];
size_t lineLen = 0;

void handle(char *buf) {
  char *argv[8];
  int argc = 0;
  for (char *tok = strtok(buf, " \t\r"); tok && argc < 8; tok = strtok(nullptr, " \t\r")) argv[argc++] = tok;
  if (argc == 0) return;
  for (char *p = argv[0]; *p; p++) *p = toupper(*p);
  String c = argv[0];
  if (c == "PING") cmdPing();
  else if (c == "RELAYTEST") cmdRelayTest();
  else if (c == "DOSE" && argc >= 4) {
    for (char *p = argv[2]; *p; p++) *p = toupper(*p);
    cmdDose(atoi(argv[1]), argv[2], atof(argv[3]), argc >= 5 ? atof(argv[4]) : 300);
  }
  else if (c == "MIX" && argc >= 2) cmdMix(atof(argv[1]), argc >= 3 ? atoi(argv[2]) : 100);
  else if (c == "SPEC") {
    bool diff = true, board = false;
    for (int i = 1; i < argc; i++) {
      for (char *p = argv[i]; *p; p++) *p = toupper(*p);
      if (strcmp(argv[i], "ON") == 0) diff = false;
      if (strcmp(argv[i], "BOARD") == 0) board = true;
    }
    cmdSpec(diff, board);
  }
  else if (c == "TEMP") cmdTemp();
  else if (c == "POWER") cmdPower();
  else if (c == "IV" && argc >= 5) cmdIV(atof(argv[1]), atof(argv[2]), atof(argv[3]), atoi(argv[4]));
  else if (c == "SINE" && argc >= 4) cmdSine(atof(argv[1]), atof(argv[2]), atoi(argv[3]));
  else if (c == "SET" && argc >= 3) {
    for (char *p = argv[1]; *p; p++) *p = toupper(*p);
    float v = atof(argv[2]);
    if (v <= 0) { err("value must be positive"); return; }
    if (strcmp(argv[1], "SHUNT") == 0) { shuntOhm = v; prefs.putFloat("shunt", v); }
    else if (strcmp(argv[1], "SENSE") == 0) { senseOhm = v; prefs.putFloat("sense", v); }
    else { err("SET SHUNT|SENSE"); return; }
    Serial.printf("{\"ok\":true,\"shunt_ohm\":%.3f,\"sense_ohm\":%.3f}\n", shuntOhm, senseOhm);
  }
  else if (c == "SAFE") { allOff(); Serial.println("{\"ok\":true}"); }
  else if (c == "HELP") cmdHelp();
  else err("unknown command or missing arguments; send HELP");
}

void setup() {
  relayInit(PIN_RELAY_EN);
  relayInit(PIN_RELAY_POL);
  for (int i = 0; i < 5; i++) relayInit(PIN_WELL[i]);
  pinMode(PIN_MIX, OUTPUT);
  pinMode(PIN_LED, OUTPUT);
  pinMode(PIN_STATUS, OUTPUT);
  Serial.begin(115200);
  Wire.begin(PIN_SDA, PIN_SCL);
  allOff();

  prefs.begin("wetstack", false);
  boots = prefs.getUInt("boots", 0) + 1;
  prefs.putUInt("boots", boots);
  shuntOhm = prefs.getFloat("shunt", 100.0);
  senseOhm = prefs.getFloat("sense", 1000.0);

  hasAds1 = ads1.begin(0x48);
  if (hasAds1) { ads1.setGain(GAIN_TWO); ads1.setDataRate(RATE_ADS1115_860SPS); }
  hasAds2 = ads2.begin(0x49);
  if (hasAds2) { ads2.setGain(GAIN_TWO); ads2.setDataRate(RATE_ADS1115_475SPS); }
  hasSpec = as7341.begin();
  if (hasSpec) { as7341.setATIME(100); as7341.setASTEP(999); as7341.setGain(AS7341_GAIN_256X); }
  hasIna = ina219.begin();
  temps.begin();
  hasTemp = temps.getDeviceCount() > 0;
  cmdPing();
}

void loop() {
  while (Serial.available()) {
    char ch = (char)Serial.read();
    if (ch == '\n') {
      line[lineLen] = 0;
      handle(line);
      lineLen = 0;
    } else if (lineLen < sizeof(line) - 1) {
      line[lineLen++] = ch;
    }
  }
}

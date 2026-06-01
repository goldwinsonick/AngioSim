// AngioSim ESP32 Firmware
// Controls 4x 12V PWM channels via LEDC.
// Serial protocol (115200 baud, line-delimited ASCII):
//   PC -> ESP32: SET_PWM:<ch>:<val>\n  (ch=1-4, val=0-255)
//                BOARD_ENABLE:<0|1>\n
//                PING\n
//   ESP32 -> PC: ACK:...\n  or  ERR:<msg>\n

const int CHANNEL_PINS[4] = {25, 26, 27, 14};
const int CHANNEL_LEDC[4] = {0, 1, 2, 3};

// PWM frequency per channel (Hz)
// Ch1 pump: 1kHz, Ch2 valve: 200Hz, Ch3 LED: 5kHz, Ch4 unused: 1kHz
const int PWM_FREQ[4] = {1000, 200, 5000, 1000};
const int PWM_RESOLUTION = 8;  // 8-bit => 0-255

bool boardEnabled = false;
uint8_t dutyCycles[4] = {0, 0, 0, 0};

void setup() {
    Serial.begin(115200);
    for (int i = 0; i < 4; i++) {
        ledcSetup(CHANNEL_LEDC[i], PWM_FREQ[i], PWM_RESOLUTION);
        ledcAttachPin(CHANNEL_PINS[i], CHANNEL_LEDC[i]);
        ledcWrite(CHANNEL_LEDC[i], 0);
    }
    Serial.println("READY");
}

void loop() {
    if (Serial.available()) {
        String cmd = Serial.readStringUntil('\n');
        cmd.trim();
        if (cmd.length() > 0) {
            parseCommand(cmd);
        }
    }
}

void applyDutyCycles() {
    for (int i = 0; i < 4; i++) {
        ledcWrite(CHANNEL_LEDC[i], boardEnabled ? dutyCycles[i] : 0);
    }
}

void parseCommand(String cmd) {
    if (cmd == "PING") {
        Serial.println("ACK:PING");
        return;
    }

    if (cmd.startsWith("BOARD_ENABLE:")) {
        int state = cmd.substring(13).toInt();
        boardEnabled = (state != 0);
        applyDutyCycles();
        Serial.println("ACK:BOARD_ENABLE:" + String(state));
        return;
    }

    if (cmd.startsWith("SET_PWM:")) {
        // Format: SET_PWM:<ch>:<val>  (ch is 1-indexed)
        int firstColon = 8;  // after "SET_PWM:"
        int secondColon = cmd.indexOf(':', firstColon);
        if (secondColon == -1) {
            Serial.println("ERR:MALFORMED_SET_PWM");
            return;
        }
        int ch = cmd.substring(firstColon, secondColon).toInt() - 1;  // 0-indexed
        int val = cmd.substring(secondColon + 1).toInt();

        if (ch < 0 || ch > 3) {
            Serial.println("ERR:INVALID_CHANNEL");
            return;
        }
        if (val < 0 || val > 255) {
            Serial.println("ERR:INVALID_VALUE");
            return;
        }

        dutyCycles[ch] = (uint8_t)val;
        if (boardEnabled) {
            ledcWrite(CHANNEL_LEDC[ch], dutyCycles[ch]);
        }
        Serial.println("ACK:SET_PWM:" + String(ch + 1) + ":" + String(val));
        return;
    }

    Serial.println("ERR:UNKNOWN_CMD");
}

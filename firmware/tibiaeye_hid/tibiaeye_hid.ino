/*
 * TibiaEye HID Firmware — Arduino Leonardo (ATmega32U4)
 *
 * Receives text commands over Serial (115200 baud) and translates
 * them into USB HID keyboard/mouse events.
 *
 * Protocol (one line per command, terminated by \n):
 *   PING                          → responds PONG
 *   PRESS <key>                   → press and release key
 *   KEYDOWN <key>                 → hold key
 *   KEYUP <key>                   → release key
 *   CLICK <x> <y> [RIGHT] [n]    → move + click
 *   MOVETO <x> <y> [dur_ms]      → move mouse to absolute position
 *   MOUSEDOWN [button]            → press mouse button
 *   MOUSEUP [button]              → release mouse button
 *   SCROLL <amount> [x] [y]      → scroll wheel
 *   TYPE <text>                   → type string
 *   HOTKEY <k1> <k2> ...         → press key combo
 *
 * Requires:
 *   - Arduino Leonardo or Pro Micro (ATmega32U4)
 *   - Keyboard.h and Mouse.h (built-in)
 *
 * Mouse movement uses relative deltas from a reset-to-origin approach:
 *   1. Move to (0,0) by large negative deltas
 *   2. Move to target by positive deltas
 *   This works because Mouse.h only supports relative movement.
 */

#include <Keyboard.h>
#include <Mouse.h>

#define SERIAL_BAUD 115200
#define LINE_BUFFER_SIZE 256
#define MOUSE_STEP 127   // Max relative move per Mouse.move() call

char lineBuffer[LINE_BUFFER_SIZE];
int linePos = 0;

// Current assumed mouse position (best-effort tracking)
int curX = 0;
int curY = 0;

// Screen dimensions (set via SCREEN command or hardcoded)
int screenW = 1920;
int screenH = 1080;

// ---- Key name to HID keycode mapping ----

uint8_t nameToKeycode(const char* name) {
  // Modifier keys
  if (strcasecmp(name, "ctrl") == 0 || strcasecmp(name, "control") == 0)
    return KEY_LEFT_CTRL;
  if (strcasecmp(name, "shift") == 0)
    return KEY_LEFT_SHIFT;
  if (strcasecmp(name, "alt") == 0)
    return KEY_LEFT_ALT;
  if (strcasecmp(name, "gui") == 0 || strcasecmp(name, "win") == 0 ||
      strcasecmp(name, "command") == 0 || strcasecmp(name, "super") == 0)
    return KEY_LEFT_GUI;

  // Navigation
  if (strcasecmp(name, "enter") == 0 || strcasecmp(name, "return") == 0)
    return KEY_RETURN;
  if (strcasecmp(name, "esc") == 0 || strcasecmp(name, "escape") == 0)
    return KEY_ESC;
  if (strcasecmp(name, "backspace") == 0)
    return KEY_BACKSPACE;
  if (strcasecmp(name, "tab") == 0)
    return KEY_TAB;
  if (strcasecmp(name, "space") == 0)
    return ' ';
  if (strcasecmp(name, "delete") == 0)
    return KEY_DELETE;
  if (strcasecmp(name, "insert") == 0)
    return KEY_INSERT;
  if (strcasecmp(name, "home") == 0)
    return KEY_HOME;
  if (strcasecmp(name, "end") == 0)
    return KEY_END;
  if (strcasecmp(name, "pageup") == 0)
    return KEY_PAGE_UP;
  if (strcasecmp(name, "pagedown") == 0)
    return KEY_PAGE_DOWN;

  // Arrow keys
  if (strcasecmp(name, "up") == 0)
    return KEY_UP_ARROW;
  if (strcasecmp(name, "down") == 0)
    return KEY_DOWN_ARROW;
  if (strcasecmp(name, "left") == 0)
    return KEY_LEFT_ARROW;
  if (strcasecmp(name, "right") == 0)
    return KEY_RIGHT_ARROW;

  // Function keys
  if (strcasecmp(name, "f1") == 0) return KEY_F1;
  if (strcasecmp(name, "f2") == 0) return KEY_F2;
  if (strcasecmp(name, "f3") == 0) return KEY_F3;
  if (strcasecmp(name, "f4") == 0) return KEY_F4;
  if (strcasecmp(name, "f5") == 0) return KEY_F5;
  if (strcasecmp(name, "f6") == 0) return KEY_F6;
  if (strcasecmp(name, "f7") == 0) return KEY_F7;
  if (strcasecmp(name, "f8") == 0) return KEY_F8;
  if (strcasecmp(name, "f9") == 0) return KEY_F9;
  if (strcasecmp(name, "f10") == 0) return KEY_F10;
  if (strcasecmp(name, "f11") == 0) return KEY_F11;
  if (strcasecmp(name, "f12") == 0) return KEY_F12;

  // Caps lock
  if (strcasecmp(name, "capslock") == 0)
    return KEY_CAPS_LOCK;

  // Single character — return ASCII
  if (strlen(name) == 1)
    return name[0];

  return 0;
}

// ---- Mouse movement helpers ----

void moveMouseAbsolute(int targetX, int targetY) {
  // Reset to origin by moving large negatives
  for (int i = 0; i < (screenW / MOUSE_STEP) + 2; i++)
    Mouse.move(-MOUSE_STEP, 0, 0);
  for (int i = 0; i < (screenH / MOUSE_STEP) + 2; i++)
    Mouse.move(0, -MOUSE_STEP, 0);

  // Now at (0,0) — move to target
  int remainX = targetX;
  int remainY = targetY;

  while (remainX > 0 || remainY > 0) {
    int dx = min(remainX, MOUSE_STEP);
    int dy = min(remainY, MOUSE_STEP);
    Mouse.move(dx, dy, 0);
    remainX -= dx;
    remainY -= dy;
  }

  curX = targetX;
  curY = targetY;
}

uint8_t parseMouseButton(const char* name) {
  if (name == NULL || strcasecmp(name, "left") == 0)
    return MOUSE_LEFT;
  if (strcasecmp(name, "right") == 0)
    return MOUSE_RIGHT;
  if (strcasecmp(name, "middle") == 0)
    return MOUSE_MIDDLE;
  return MOUSE_LEFT;
}

// ---- Command parser ----

void processLine(char* line) {
  // Tokenize
  char* tokens[16];
  int tokenCount = 0;

  char* tok = strtok(line, " ");
  while (tok != NULL && tokenCount < 16) {
    tokens[tokenCount++] = tok;
    tok = strtok(NULL, " ");
  }

  if (tokenCount == 0) return;

  const char* cmd = tokens[0];

  // PING
  if (strcasecmp(cmd, "PING") == 0) {
    Serial.println("PONG");
    return;
  }

  // PRESS <key>
  if (strcasecmp(cmd, "PRESS") == 0 && tokenCount >= 2) {
    uint8_t kc = nameToKeycode(tokens[1]);
    if (kc) {
      Keyboard.press(kc);
      delay(10);
      Keyboard.release(kc);
    }
    return;
  }

  // KEYDOWN <key>
  if (strcasecmp(cmd, "KEYDOWN") == 0 && tokenCount >= 2) {
    uint8_t kc = nameToKeycode(tokens[1]);
    if (kc) Keyboard.press(kc);
    return;
  }

  // KEYUP <key>
  if (strcasecmp(cmd, "KEYUP") == 0 && tokenCount >= 2) {
    uint8_t kc = nameToKeycode(tokens[1]);
    if (kc) Keyboard.release(kc);
    return;
  }

  // CLICK <x> <y> [RIGHT] [clicks]
  if (strcasecmp(cmd, "CLICK") == 0 && tokenCount >= 3) {
    int x = atoi(tokens[1]);
    int y = atoi(tokens[2]);
    uint8_t btn = MOUSE_LEFT;
    int clicks = 1;

    for (int i = 3; i < tokenCount; i++) {
      if (strcasecmp(tokens[i], "RIGHT") == 0)
        btn = MOUSE_RIGHT;
      else
        clicks = atoi(tokens[i]);
    }

    moveMouseAbsolute(x, y);
    for (int c = 0; c < clicks; c++) {
      Mouse.press(btn);
      delay(10);
      Mouse.release(btn);
      if (c < clicks - 1) delay(50);
    }
    return;
  }

  // MOVETO <x> <y> [dur_ms]
  if (strcasecmp(cmd, "MOVETO") == 0 && tokenCount >= 3) {
    int x = atoi(tokens[1]);
    int y = atoi(tokens[2]);
    moveMouseAbsolute(x, y);
    return;
  }

  // MOUSEDOWN [button]
  if (strcasecmp(cmd, "MOUSEDOWN") == 0) {
    uint8_t btn = (tokenCount >= 2) ? parseMouseButton(tokens[1]) : MOUSE_LEFT;
    Mouse.press(btn);
    return;
  }

  // MOUSEUP [button]
  if (strcasecmp(cmd, "MOUSEUP") == 0) {
    uint8_t btn = (tokenCount >= 2) ? parseMouseButton(tokens[1]) : MOUSE_LEFT;
    Mouse.release(btn);
    return;
  }

  // SCROLL <amount> [x] [y]
  if (strcasecmp(cmd, "SCROLL") == 0 && tokenCount >= 2) {
    int amount = atoi(tokens[1]);
    if (tokenCount >= 4) {
      int x = atoi(tokens[2]);
      int y = atoi(tokens[3]);
      moveMouseAbsolute(x, y);
    }
    Mouse.move(0, 0, amount);
    return;
  }

  // TYPE <text...>
  if (strcasecmp(cmd, "TYPE") == 0 && tokenCount >= 2) {
    // Reconstruct the text (everything after "TYPE ")
    char* textStart = line + 5; // skip "TYPE "
    // strtok already modified line, so rebuild from tokens
    for (int i = 1; i < tokenCount; i++) {
      Keyboard.print(tokens[i]);
      if (i < tokenCount - 1) Keyboard.print(" ");
    }
    return;
  }

  // HOTKEY <k1> <k2> ...
  if (strcasecmp(cmd, "HOTKEY") == 0 && tokenCount >= 2) {
    // Press all keys
    for (int i = 1; i < tokenCount; i++) {
      uint8_t kc = nameToKeycode(tokens[i]);
      if (kc) Keyboard.press(kc);
    }
    delay(10);
    // Release all keys in reverse
    for (int i = tokenCount - 1; i >= 1; i--) {
      uint8_t kc = nameToKeycode(tokens[i]);
      if (kc) Keyboard.release(kc);
    }
    return;
  }

  // SCREEN <w> <h>  — set screen dimensions for mouse
  if (strcasecmp(cmd, "SCREEN") == 0 && tokenCount >= 3) {
    screenW = atoi(tokens[1]);
    screenH = atoi(tokens[2]);
    Serial.print("SCREEN_SET ");
    Serial.print(screenW);
    Serial.print("x");
    Serial.println(screenH);
    return;
  }
}

// ---- Main ----

void setup() {
  Serial.begin(SERIAL_BAUD);
  Keyboard.begin();
  Mouse.begin();

  // Wait for serial connection
  while (!Serial) {
    delay(10);
  }

  Serial.println("TIBIAEYE_READY");
}

void loop() {
  while (Serial.available()) {
    char c = Serial.read();

    if (c == '\n' || c == '\r') {
      if (linePos > 0) {
        lineBuffer[linePos] = '\0';
        processLine(lineBuffer);
        linePos = 0;
      }
    } else if (linePos < LINE_BUFFER_SIZE - 1) {
      lineBuffer[linePos++] = c;
    }
  }
}

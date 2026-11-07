/*
 * 喷气发动机模型驱动固件 —— USB 串口版（替代原 WiFi HTTP 版）
 *
 * 硬件：ESP32-C3 SuperMini + DRV8871
 *   GPIO3  --1kΩ-->  DRV8871 IN1   (20 kHz PWM)
 *   DRV8871 IN2 -->  GND            (固定滑行，单方向)
 *   DRV8871 ILIM --47kΩ--> GND      (限流 1.36 A)
 *   GPIO8  板载 LED（低电平点亮）
 *
 * 数据链：USB-CDC 串口（115200，实际速率由 USB 决定）
 *   电脑上的 engine_host.py 测 CPU 占用率 → 发 "T <duty>" → 固件按斜坡加到目标
 *   "T" 同时是心跳：2 秒收不到任何命令 → 滑行停转（关机/休眠/拔线一视同仁）
 *
 * 开关（硬件使能）：
 *   GPIO4 --/ -- GND    开关导通(ON) = 允许转动；断开(OFF) = 立即滑行停转
 *   内部上拉：不接开关时 GPIO4 悬空读到高 = OFF（失效安全，宁可不动）
 *   开关状态每 20 ms 去抖一次，状态变化打一行 "# switch ON/OFF"
 *
 * 命令（ASCII 行，\n 结尾）：
 *   T <duty>   目标占空比 0-100（固件夹到 DUTY_MAX，当前 100），同时刷新心跳
 *   I          怠速（= T 10）
 *   S          停机（目标归零，斜坡滑行）
 *   K          清故障
 *   ?          立即回报一次状态
 *   V          版本
 *   P          引脚自检：把 9 个候选 GPIO 的原始电平全打一行（查"开关到底接在哪个脚"）
 *   E <0|1>    强制放行开关（E 1 = 忽略开关，直接允许转；调试电机通路用，断电即复位成 0）
 *
 * 回报（5 Hz）：
 *   R <duty> <target> <state> <ms自上次命令> <sw 1=允许 0=禁止>
 *
 * 防抖在主机侧做（迟滞+停留时间），固件只负责斜坡与看门狗。
 */

#include <Arduino.h>

// ---------------- 参数 ----------------
static const int      PIN_PWM      = 3;
static const int      PIN_LED      = 8;      // SuperMini 板载 LED，低电平亮
static const int      PIN_SW       = 4;      // 使能开关：GPIO4 与 GND 之间，导通=允许转
static const uint32_t PWM_FREQ     = 20000;  // 20 kHz，避开人耳
static const uint8_t  PWM_RES      = 10;     // 1024 级

static const float    DUTY_MAX     = 100.0f; // 上限：100% = 12V 全压（N20 铭牌上限，长转会烫）
static const float    DUTY_MIN_RUN = 15.0f;  // 运行下限：N20 时代机械实测 75% 只能撑几秒就停（静摩擦门槛），
                                             // 2026-11-05 换 N30 后扭矩足够，降到 15% 让 20% 低速档能真正生效
                                             // 80% 是可靠起步值。任何 >0 的目标一律抬到 ≥80%，0 仍是停机
static const float    DUTY_IDLE    = 80.0f;  // 怠速 = 运行下限
static const float    RAMP_PER_SEC = 75.0f;  // 0→90% 约 1.2 s
static const uint32_t TICK_MS      = 20;     // 斜坡更新周期
static const uint32_t WD_MS        = 2000;   // 心跳超时（串口版）
static const uint32_t KICK_MS      = 250;    // 起转冲一脚，越过静摩擦
static const float    KICK_ABS     = 45.0f;  // 起转的最小冲击值
static const float    KICK_BOOST   = 10.0f;  // 起转在目标上再加 10%（封顶 100）
static const uint32_t REPORT_MS    = 200;    // 5 Hz 回报

// ---------------- 状态 ----------------
enum State : uint8_t { ST_IDLE = 0, ST_RUN = 1, ST_COAST = 2 };
static const char *STATE_NAME[] = {"IDLE", "RUN", "COAST"};

static float    g_target = 0.0f;
static float    g_duty   = 0.0f;
static State    g_state  = ST_IDLE;

static bool     g_kick     = false;
static uint32_t g_kickAt   = 0;
static float    g_kickPeak = 0.0f;

static uint32_t g_lastRx   = 0;
static uint32_t g_lastTick = 0;
static uint32_t g_lastRep  = 0;
static uint32_t g_bootMs   = 0;

static char     g_line[40];
static uint8_t  g_len = 0;

// 引脚自检用：所有可以安全当输入的候选脚（排除 PWM=3、LED=8、BOOT/strapping=2/9、USB=18/19）
static const uint8_t PROBE_PINS[] = {0, 1, 4, 5, 6, 7, 10, 20, 21};

// 使能开关（内部上拉，低电平=导通=允许转）
static bool     g_swEnabled = false;
static bool     g_force     = false;   // E 1：忽略开关，调试用
static bool     g_swRawHigh = true;    // true = 开关断开
static uint32_t g_swAt      = 0;

// ---------------- PWM ----------------
static inline uint32_t dutyToDutyQ(float d)
{
    if (d < 0) d = 0;
    if (d > 100.0f) d = 100.0f;
    return (uint32_t)(d / 100.0f * ((1u << PWM_RES) - 1) + 0.5f);
}

static inline void applyPwm(float d)
{
    ledcWrite(PIN_PWM, dutyToDutyQ(d));
}

// ---------------- 命令处理 ----------------
static void reportNow(uint32_t now)
{
    char buf[64];
    snprintf(buf, sizeof(buf), "R %.1f %.1f %s %lu %d\r\n",
             g_duty, g_target, STATE_NAME[g_state],
             (unsigned long)(now - g_lastRx), (g_swEnabled || g_force) ? 1 : 0);
    Serial.print(buf);
}

static void setTarget(float d, uint32_t now)
{
    if (d < 0) d = 0;
    if (d > DUTY_MAX) d = DUTY_MAX;
    if (d > 0.0f && d < DUTY_MIN_RUN) d = DUTY_MIN_RUN;   // 低速死区：要么停，要么 ≥80%

    // 开关关着：拒绝一切起转请求（但照样刷新心跳，避免刷屏告警）
    if (!(g_swEnabled || g_force) && d > 0.0f) {
        static uint32_t lastHint = 0;
        g_lastRx = now;
        if (now - lastHint > 5000) {          // 5 s 最多提示一次
            lastHint = now;
            Serial.println("# refused: switch OFF (GPIO4 not connected to GND)");
        }
        g_target = 0.0f;
        if (g_state == ST_RUN) g_state = (g_duty > 0.5f) ? ST_COAST : ST_IDLE;
        return;
    }

    // 从停转状态起转：先给一脚大的越过静摩擦
    // 注意：这一脚必须**绕过斜坡**直接跳上去，否则 75%/s 的斜坡在 250 ms 内只爬 19%，
    // 冲量根本到不了静摩擦阈值（2026-10-31 台架实测：kick 打印了但 duty 只爬到 55%）。
    if (g_state == ST_IDLE && d > 0 && g_duty < 1.0f) {
        g_kick     = true;
        g_kickAt   = now;
        g_kickPeak = d + KICK_BOOST;                  // 起转在当前目标上再冲 10%，确保越过静摩擦
        if (g_kickPeak < KICK_ABS) g_kickPeak = KICK_ABS;
        if (g_kickPeak > DUTY_MAX) g_kickPeak = DUTY_MAX;
        g_duty     = g_kickPeak;
        applyPwm(g_duty);
        Serial.printf("# kick to %.0f%% for %lums\r\n", g_kickPeak, (unsigned long)KICK_MS);
    }

    g_target = d;
    g_state  = (d > 0) ? ST_RUN : ST_COAST;
    g_lastRx = now;
}

static void printPins()
{
    Serial.print("# pins");
    for (uint8_t i = 0; i < sizeof(PROBE_PINS); i++) {
        Serial.printf(" %u:%d", PROBE_PINS[i], digitalRead(PROBE_PINS[i]));
    }
    Serial.println("   (1=悬空/高, 0=被拉到地)");
    // 直接读 PWM 脚：pad 电平 + LEDC 寄存器里的 duty，用来区分"没驱动"和"线没接上"
    Serial.printf("# pwm gpio%u pad=%d ledc=%lu/1023 | led8 pad=%d  boot9 pad=%d\r\n",
                  PIN_PWM, digitalRead(PIN_PWM), (unsigned long)ledcRead(PIN_PWM),
                  digitalRead(PIN_LED), digitalRead(9));
}

static void handleLine(char *s, uint32_t now)
{
    // 去首尾空白
    while (*s == ' ') s++;
    size_t n = strlen(s);
    while (n && (s[n - 1] == '\r' || s[n - 1] == ' ')) s[--n] = 0;
    if (n == 0) return;

    char cmd = toupper(s[0]);
    const char *arg = s + 1;
    while (*arg == ' ') arg++;

    switch (cmd) {
    case 'T':
        if (*arg) {
            setTarget(atof(arg), now);
            return;
        }
        break;
    case 'I':
        setTarget(DUTY_IDLE, now);
        return;
    case 'S':
        setTarget(0.0f, now);
        return;
    case 'K':
        g_target = 0.0f;
        g_state  = ST_IDLE;
        g_kick   = false;
        g_lastRx = now;
        Serial.println("# fault cleared");
        return;
    case '?':
        reportNow(now);
        return;
    case 'E':
        g_force = (*arg == '1');
        Serial.printf("# force enable = %d (switch %s)\r\n", g_force,
                      g_swEnabled ? "ON" : "OFF");
        if (!g_force && !g_swEnabled) {
            g_target = 0.0f;
            if (g_state == ST_RUN) g_state = (g_duty > 0.5f) ? ST_COAST : ST_IDLE;
        }
        return;
    case 'P':
        printPins();
        return;
    case 'V':
        Serial.printf("# jetengine-usb 1.1  pwm=GPIO%d 20kHz idle=%.0f%% kick=%.0f%% max=%.0f%% wd=%lums\r\n",
                  PIN_PWM, DUTY_IDLE, KICK_ABS, DUTY_MAX, (unsigned long)WD_MS);
        return;
    case '#':   // 注释
    case '\0':
        return;
    default:
        break;
    }
    Serial.printf("# ERR unknown cmd: %s\r\n", s);
}

static void pollSerial(uint32_t now)
{
    while (Serial.available() > 0) {
        char c = (char)Serial.read();
        if (c == '\n') {
            g_line[g_len] = 0;
            if (g_len) handleLine(g_line, now);
            g_len = 0;
        } else if (c != '\r') {
            if (g_len < sizeof(g_line) - 1) g_line[g_len++] = c;
            else g_len = 0;   // 溢出丢整行
        }
    }
}

// ---------------- 使能开关 ----------------
static void pollSwitch(uint32_t now)
{
    bool rawHigh = (digitalRead(PIN_SW) == HIGH);
    if (rawHigh != g_swRawHigh) {       // 电平变了，重新计时去抖
        g_swRawHigh = rawHigh;
        g_swAt      = now;
        return;
    }
    if (now - g_swAt < 20) return;      // 还没稳定 20 ms

    bool en = !rawHigh;
    if (en == g_swEnabled) return;

    g_swEnabled = en;
    if (en) {
        Serial.println("# switch ON  -> run enabled");
    } else {
        Serial.println("# switch OFF -> motor stopped");
        g_target = 0.0f;
        g_kick   = false;
        if (g_state == ST_RUN) g_state = (g_duty > 0.5f) ? ST_COAST : ST_IDLE;
    }
}

// ---------------- setup / loop ----------------
void setup()
{
    pinMode(PIN_LED, OUTPUT);
    digitalWrite(PIN_LED, HIGH);          // 灭（低电平亮）

    for (uint8_t i = 0; i < sizeof(PROBE_PINS); i++)
        pinMode(PROBE_PINS[i], INPUT_PULLUP);   // 自检候选脚一律上拉输入
    pinMode(PIN_SW, INPUT_PULLUP);        // 开关：导通到 GND = 允许转
    g_swRawHigh = (digitalRead(PIN_SW) == HIGH);
    g_swEnabled = !g_swRawHigh;

    ledcAttach(PIN_PWM, PWM_FREQ, PWM_RES);
    applyPwm(0.0f);

    Serial.begin(115200);
    uint32_t t0 = millis();
    while (!Serial && millis() - t0 < 2000) delay(10);

    g_bootMs   = millis();
    g_lastRx   = g_bootMs;   // 上电即开始计心跳
    g_lastTick = g_bootMs;
    g_lastRep  = g_bootMs;

    Serial.println();
    Serial.println("# jetengine-usb 1.0  ESP32-C3 SuperMini + DRV8871");
    Serial.printf("# pwm=GPIO%d %lukHz  runrange=%.0f-%.0f%%  idle=%.0f%%  kick=+%.0f%%  wd=%lums  ramp=%.0f%%/s\r\n",
                  PIN_PWM, (unsigned long)(PWM_FREQ / 1000), DUTY_MIN_RUN, DUTY_MAX,
                  DUTY_IDLE, KICK_BOOST, (unsigned long)WD_MS, RAMP_PER_SEC);
    Serial.println("# cmds: T <duty> | I | S | K | ? | V | P(pin probe)   (T is heartbeat)");
    Serial.printf("# switch(GPIO%d) = %s   (E 1 = bypass switch)\r\n", PIN_SW,
                  g_swEnabled ? "ON  (run enabled)" : "OFF (motor disabled)");
    Serial.println("# ready");
    digitalWrite(PIN_LED, LOW);
    delay(80);
    digitalWrite(PIN_LED, HIGH);
}

void loop()
{
    uint32_t now = millis();
    pollSwitch(now);
    pollSerial(now);

    // ---- 看门狗：超时滑行 ----
    if (now - g_lastRx > WD_MS) {
        if (g_state == ST_RUN) Serial.println("# watchdog: coast");
        g_target = 0.0f;
        if (g_state != ST_COAST) g_state = (g_duty > 0.5f) ? ST_COAST : ST_IDLE;
    }

    // ---- 斜坡 ----
    if (now - g_lastTick >= TICK_MS) {
        float dt    = (now - g_lastTick) / 1000.0f;
        g_lastTick  = now;
        float step  = RAMP_PER_SEC * dt;
        float goal  = g_target;

        if (g_kick) {
            if (now - g_kickAt >= KICK_MS) g_kick = false;
            else goal = g_kickPeak;
        }

        if (g_duty < goal) {
            g_duty += step;
            if (g_duty > goal) g_duty = goal;
        } else if (g_duty > goal) {
            g_duty -= step;
            if (g_duty < goal) g_duty = goal;
        }
        applyPwm(g_duty);

        if (g_duty <= 0.01f) {
            g_duty = 0.0f;
            if (g_state == ST_COAST) g_state = ST_IDLE;
        }
    }

    // ---- 回报 ----
    if (now - g_lastRep >= REPORT_MS) {
        g_lastRep = now;
        reportNow(now);
    }

    // ---- LED：开关断开=每 1.5 s 短闪一次（提示"电在、但被开关禁止"）
    //            RUN=慢闪(1 Hz)  COAST=快闪(4 Hz)  使能且怠速=常灭
    static bool ledOn = false;
    bool want;
    if (!(g_swEnabled || g_force)) want = ((now % 1500) < 80);
    else if (g_state == ST_RUN)    want = ((now % 1000) < 500);
    else if (g_state == ST_COAST)  want = ((now % 240) < 120);
    else                           want = false;
    if (want != ledOn) {
        ledOn = want;
        digitalWrite(PIN_LED, want ? LOW : HIGH);
    }

    delay(1);
}

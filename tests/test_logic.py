"""Tests for firmware/logic.py - plain asserts, so the same file runs under
CPython and MicroPython:

    python3 tests/test_logic.py
    micropython tests/test_logic.py
"""
import sys

sys.path.insert(0, "firmware")
sys.path.insert(0, "../firmware")
import logic as L

S = 1000  # ms


def run(c, seconds, rpm=(800, 800, 800), amb=None, fault=False, start=None):
    """Tick once a second; returns all alarm lines."""
    out = []
    t0 = c.last_ms if start is None else start
    for k in range(1, seconds + 1):
        out += c.tick(t0 + k * S, list(rpm), amb, fault)
    return out


def feed(c, temp, seconds, **kw):
    """Host sends TEMP every second for `seconds`."""
    out = []
    for _ in range(seconds):
        c.command("TEMP %s" % temp, c.last_ms)
        out += run(c, 1, **kw)
    return out


def test_curve_points():
    pts = L.DEFAULTS["curve"]
    assert L.curve_duty(pts, 20) == 20
    assert L.curve_duty(pts, 35) == 20
    assert abs(L.curve_duty(pts, 42.5) - 27.5) < 1e-9
    assert L.curve_duty(pts, 75) == 100
    assert L.curve_duty(pts, 90) == 100


def test_start_then_failsafe_without_host():
    c = L.Controller(now_ms=0)
    assert run(c, 30) == []
    assert c.mode == "start" and round(c.duty[0]) == 60
    out = run(c, 1)                       # 31 s without a single TEMP
    assert c.mode == "failsafe"
    assert out == ["ALARM TEMP STALE"]
    assert c.duty == [100.0, 100.0, 100.0]  # no ramp on the way up to safety


def test_auto_follows_curve_with_ramp_down():
    c = L.Controller(now_ms=0)
    feed(c, 38, 60)                       # 60 s at idle temperature
    assert c.mode == "auto"
    want = L.curve_duty(c.cfg["curve"], 38)   # 23 %
    assert abs(c.duty[0] - want) < 0.01, c.duty
    feed(c, 70, 3)
    assert 23 < c.duty[0] < 80            # ramping up at 10 %/s, not a jump
    feed(c, 70, 10)
    assert abs(c.duty[0] - L.curve_duty(c.cfg["curve"], 70)) < 0.01


def test_hysteresis_holds_until_three_degrees():
    c = L.Controller(now_ms=0)
    feed(c, 60, 60)
    hold = c.target[0]
    feed(c, 58, 30)                       # 2 degC down: stays
    assert c.target[0] == hold
    feed(c, 56, 5)                        # 4 degC down: follows (t_eff = 59)
    assert c.target[0] < hold
    assert abs(c.target[0] - L.curve_duty(c.cfg["curve"], 59)) < 1e-9


def test_stale_host_goes_to_100_and_recovers():
    c = L.Controller(now_ms=0)
    feed(c, 40, 10)
    out = run(c, 31)                      # host silent
    assert "ALARM TEMP STALE" in out and c.mode == "failsafe"
    assert c.duty[1] == 100.0
    out = feed(c, 40, 1)
    assert out == ["INFO TEMP OK"] and c.mode == "auto"


def test_bye_rests_at_20_forever():
    c = L.Controller(now_ms=0)
    feed(c, 50, 10)
    assert c.command("BYE", c.last_ms) == ["OK REST"]
    out = run(c, 600)                     # 10 min without TEMP: still rest, no alarm
    assert c.mode == "rest" and out == []
    assert abs(c.duty[0] - 20) < 0.01
    feed(c, 50, 1)
    assert c.mode == "auto"


def test_bye_shows_rest_in_status_at_once():
    c = L.Controller(now_ms=0)
    feed(c, 50, 5)
    assert c.command("BYE", c.last_ms) == ["OK REST"]
    assert c.command("STATUS", c.last_ms)[0].startswith("STAT mode=rest ")


def test_hello_leaves_rest_and_goes_failsafe_without_temp():
    c = L.Controller(now_ms=0)
    feed(c, 50, 5)
    c.command("BYE", c.last_ms)
    run(c, 60)
    assert c.mode == "rest"
    assert c.command("HELLO", c.last_ms) == ["OK HELLO"]
    run(c, 5)                             # ramp 20 -> 60 % at 10 %/s
    assert c.mode == "start" and abs(c.duty[0] - 60) < 0.01
    out = run(c, 26)                      # 31 s after HELLO without a TEMP
    assert c.mode == "failsafe" and c.duty == [100.0] * 3
    assert "ALARM TEMP STALE" in out


def test_min_duty_floor():
    c = L.Controller(now_ms=0)
    c.command("MIN 2 35", 0)
    feed(c, 30, 60)                       # curve says 20 %
    assert abs(c.duty[0] - 20) < 0.01 and abs(c.duty[1] - 35) < 0.01


def test_ambient_overrides_host():
    c = L.Controller(now_ms=0)
    feed(c, 38, 60)
    out = feed(c, 38, 1, amb=41.0)
    assert out == ["ALARM AMB HIGH"]
    feed(c, 38, 10, amb=41.0)
    assert abs(c.duty[0] - 60) < 0.01
    out = feed(c, 38, 1, amb=46.0)
    assert "ALARM AMB CRIT" in out and c.duty == [100.0] * 3
    out = feed(c, 38, 1, amb=30.0)
    assert "INFO AMB OK" in out


def test_ambient_warn_to_normal_reports_ok():
    c = L.Controller(now_ms=0)
    feed(c, 38, 30)
    assert feed(c, 38, 1, amb=41.0) == ["ALARM AMB HIGH"]
    assert feed(c, 38, 1, amb=30.0) == ["INFO AMB OK"]


def test_ambient_crit_to_warn_reports_high_not_ok():
    c = L.Controller(now_ms=0)
    feed(c, 38, 30)
    assert feed(c, 38, 1, amb=46.0) == ["ALARM AMB CRIT"]
    assert feed(c, 38, 1, amb=42.0) == ["INFO AMB HIGH"]
    feed(c, 38, 30, amb=42.0)
    assert abs(c.duty[0] - 60) < 0.01


def test_ambient_hysteresis_no_flapping():
    c = L.Controller(now_ms=0)
    feed(c, 38, 30)
    out = feed(c, 38, 1, amb=40.0)
    for a in (39.5, 40.0, 39.2, 40.1, 39.5):
        out += feed(c, 38, 1, amb=a)
    assert out == ["ALARM AMB HIGH"], out
    feed(c, 38, 10, amb=39.5)
    assert abs(c.duty[0] - 60) < 0.01     # still overridden inside the band
    assert feed(c, 38, 1, amb=38.9) == ["INFO AMB OK"]


def test_stall_alarm_after_5_s_and_disabled_fan_silent():
    c = L.Controller(now_ms=0)
    feed(c, 70, 20)                       # well above stall_duty
    out = feed(c, 70, 4, rpm=(800, 0, 0))
    assert out == []
    c.command("ENABLE 3 0", c.last_ms)
    out = feed(c, 70, 2, rpm=(800, 0, 0))
    assert out == ["ALARM FAN2 STALL"], out
    out = feed(c, 70, 1, rpm=(800, 700, 0))
    assert out == ["INFO FAN2 OK"]


def test_fault_edge_reported_once():
    c = L.Controller(now_ms=0)
    feed(c, 40, 5)
    assert feed(c, 40, 3, fault=True) == ["ALARM FAULT"]
    assert feed(c, 40, 1) == ["INFO FAULT OK"]


def test_manual_and_auto():
    c = L.Controller(now_ms=0)
    feed(c, 40, 30)
    assert c.command("SET 1 80", c.last_ms) == ["OK"]
    feed(c, 40, 10)
    assert abs(c.duty[0] - 80) < 0.01
    assert "f1=80m/" in c.command("STATUS", c.last_ms)[0]
    c.command("AUTO", c.last_ms)
    feed(c, 40, 60)
    assert abs(c.duty[0] - L.curve_duty(c.cfg["curve"], 40)) < 0.01


def test_manual_cannot_beat_failsafe():
    c = L.Controller(now_ms=0)
    feed(c, 40, 5)
    c.command("SET 1 10", c.last_ms)
    run(c, 31)
    assert c.duty[0] == 100.0


def test_commands_and_errors():
    c = L.Controller(now_ms=0)
    assert c.command("ping", 0) == ["PONG"]
    assert c.command("VER", 0) == ["VER FanCtrl3 " + L.VERSION]
    assert c.command("TEMP abc", 0) == ["ERR ARGS TEMP"]
    assert c.command("TEMP 500", 0) == ["ERR TEMP out of range"]
    assert c.command("SET 4 50", 0) == ["ERR ARGS SET"]
    assert c.command("FOO", 0) == ["ERR UNKNOWN FOO"]
    assert c.command("CURVE 40:30 30:50", 0)[0].startswith("ERR CURVE")
    assert c.command("CURVE 30:20 60:100", 0) == ["OK"]
    assert c.cfg["curve"] == [[30.0, 20.0], [60.0, 100.0]]
    assert c.command("", 0) == []
    assert c.command("SAVE", 0) == ["OK SAVE"] and c.save_requested
    s = c.command("STATUS", 0)[0]
    assert s.startswith("STAT mode=start cpu=- age=- amb=- fault=0 f1=")


def test_config_merge_rejects_garbage():
    cfg = L.merge_config({"curve": [[50, 10], [40, 20]], "min_duty": "x",
                          "stale_s": 10, "hyst": 2, "unknown": 1})
    assert cfg["curve"] == L.DEFAULTS["curve"]
    assert cfg["min_duty"] == [20, 20, 20]
    assert cfg["stale_s"] == 10 and cfg["hyst"] == 2.0
    assert "unknown" not in cfg
    c = L.Controller(cfg)
    import json
    assert json.loads(c.config_json())["stale_s"] == 10


def test_config_merge_rejects_wrong_list_lengths():
    cfg = L.merge_config({"min_duty": [10], "enabled": [1, 0], "curve": [[30, 20], [60, 100]]})
    assert cfg["min_duty"] == [20, 20, 20] and cfg["enabled"] == [1, 1, 1]
    assert cfg["curve"] == [[30, 20], [60, 100]]   # a curve may have any number of points
    cfg = L.merge_config({"min_duty": ["a", "b", "c"], "enabled": [1, "x", 0]})
    assert cfg["min_duty"] == [20, 20, 20] and cfg["enabled"] == [1, 1, 1]
    c = L.Controller(L.merge_config({"min_duty": [10]}))
    run(c, 3)                             # must not raise


def main():
    tests = [(k, v) for k, v in sorted(globals().items()) if k.startswith("test_")]
    failed = 0
    for name, fn in tests:
        try:
            fn()
            print("ok   ", name)
        except Exception as e:
            failed += 1
            print("FAIL ", name, repr(e))
    print("%d tests, %d failed" % (len(tests), failed))
    sys.exit(1 if failed else 0)


main()

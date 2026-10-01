"""Serial link to the ESP32 firmware (firmware/wetstack_ctl).

Protocol: one text command per line; the controller answers with one JSON
object per line. Long operations stream rows and finish with {"done": true}.
"""
from __future__ import annotations

import json
import time


class LinkError(RuntimeError):
    pass


class SerialController:
    def __init__(self, port: str, baud: int = 115200, timeout: float = 2.0):
        try:
            import serial
        except ImportError as exc:
            raise LinkError("pyserial missing: pip install pyserial") from exc
        self.ser = serial.Serial(port, baud, timeout=timeout)
        time.sleep(2.0)                  # ESP32 resets when the port opens
        self.ser.reset_input_buffer()

    def _send(self, line: str) -> None:
        self.ser.write((line.strip() + "\n").encode("ascii"))
        self.ser.flush()

    def _read_json(self, deadline_s: float) -> dict:
        end = time.time() + deadline_s
        while time.time() < end:
            raw = self.ser.readline().decode("ascii", errors="replace").strip()
            if not raw:
                continue
            if raw.startswith("{"):
                try:
                    return json.loads(raw)
                except json.JSONDecodeError:
                    continue
        raise LinkError(f"No reply within {deadline_s:.0f} s")

    def call(self, line: str, deadline_s: float = 10.0) -> dict:
        self._send(line)
        reply = self._read_json(deadline_s)
        if not reply.get("ok", False) and "done" not in reply:
            raise LinkError(f"{line!r} -> {reply.get('err', reply)}")
        return reply

    def stream(self, line: str, deadline_s: float) -> list[dict]:
        self._send(line)
        rows, end = [], time.time() + deadline_s
        while time.time() < end:
            msg = self._read_json(max(1.0, end - time.time()))
            if msg.get("done"):
                return rows
            if "err" in msg:
                raise LinkError(msg["err"])
            rows.append(msg)
        raise LinkError("Stream did not finish in time")

    # Same method names as sim.SimController
    def ping(self) -> dict:
        return self.call("PING")

    def relay_test(self) -> dict:
        return self.call("RELAYTEST", deadline_s=30)

    def dose(self, well_index: int, mode: str, charge_mC: float, max_s: float = 300) -> dict:
        return self.call(f"DOSE {well_index} {mode.upper()} {charge_mC:.4f} {max_s:.0f}", deadline_s=max_s + 10)

    def mix(self, seconds: float, duty: int = 100) -> dict:
        return self.call(f"MIX {seconds:.1f} {duty}", deadline_s=seconds + 5)

    def spec(self, well_index: int = 1, diff: bool = True) -> dict:
        return self.call(f"SPEC {'DIFF' if diff else 'ON'}", deadline_s=10)

    def temp(self) -> dict:
        return self.call("TEMP")

    def power(self) -> dict:
        return self.call("POWER")

    def safe(self) -> dict:
        return self.call("SAFE")

    def iv(self, vmin: float, vmax: float, step: float, dwell_ms: int, device: str = "diode") -> list[dict]:
        n = int(round((vmax - vmin) / step)) + 1
        return self.stream(f"IV {vmin:.3f} {vmax:.3f} {step:.3f} {dwell_ms}", deadline_s=n * dwell_ms / 1000 + 20)

    def sine(self, freq_hz: float, amp_v: float, cycles: int, device: str = "diode") -> list[dict]:
        return self.stream(f"SINE {freq_hz:.4f} {amp_v:.3f} {cycles}", deadline_s=cycles / freq_hz + 20)

    def close(self) -> None:
        try:
            self.safe()
        finally:
            self.ser.close()

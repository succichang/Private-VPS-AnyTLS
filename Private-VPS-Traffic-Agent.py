#!/usr/bin/env python3
"""Private traffic counter API for a VPS.

The HTTP server only listens on 127.0.0.1. Surge reaches it through the
authenticated AnyTLS proxy, so no additional public port is required.
"""

import calendar
import json
import os
import signal
import socket
import threading
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

STATE_PATH = Path(os.getenv("STATE_PATH", "/var/lib/private-vps-traffic/state.json"))
LISTEN_HOST = "127.0.0.1"
LISTEN_PORT = int(os.getenv("LISTEN_PORT", "18080"))
RESET_DAY = max(1, min(31, int(os.getenv("RESET_DAY", "1"))))
TOTAL_GB = max(0.0, float(os.getenv("TOTAL_GB", "0")))
SAMPLE_INTERVAL = 30
VERSION = 1


def utc_now():
    return datetime.now(timezone.utc)


def month_date(year, month, day):
    last_day = calendar.monthrange(year, month)[1]
    return datetime(year, month, min(day, last_day), tzinfo=timezone.utc)


def previous_month(year, month):
    return (year - 1, 12) if month == 1 else (year, month - 1)


def next_month(year, month):
    return (year + 1, 1) if month == 12 else (year, month + 1)


def billing_period(now):
    candidate = month_date(now.year, now.month, RESET_DAY)
    if now < candidate:
        year, month = previous_month(now.year, now.month)
        start = month_date(year, month, RESET_DAY)
    else:
        start = candidate

    year, month = next_month(start.year, start.month)
    return start, month_date(year, month, RESET_DAY)


def default_interface():
    with open("/proc/net/route", encoding="ascii") as routes:
        next(routes, None)
        for line in routes:
            fields = line.split()
            if len(fields) > 1 and fields[1] == "00000000":
                return fields[0]
    raise RuntimeError("无法识别默认网络接口")


def read_counter(interface, name):
    path = Path("/sys/class/net") / interface / "statistics" / name
    return int(path.read_text(encoding="ascii").strip())


def read_boot_id():
    return Path("/proc/sys/kernel/random/boot_id").read_text(
        encoding="ascii"
    ).strip()


def load_state():
    try:
        data = json.loads(STATE_PATH.read_text(encoding="utf-8"))
        if data.get("version") == VERSION:
            return data
    except (FileNotFoundError, json.JSONDecodeError, OSError, TypeError):
        pass
    return {}


class TrafficCounter:
    def __init__(self):
        self.lock = threading.Lock()
        self.interface = os.getenv("INTERFACE") or default_interface()
        self.state = load_state()
        self.stop_event = threading.Event()
        self.sample(initial=True)

    def save(self):
        STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
        temporary = STATE_PATH.with_suffix(".tmp")
        temporary.write_text(
            json.dumps(self.state, separators=(",", ":")), encoding="utf-8"
        )
        os.replace(temporary, STATE_PATH)

    def sample(self, initial=False):
        with self.lock:
            now = utc_now()
            period_start, _ = billing_period(now)
            raw_rx = read_counter(self.interface, "rx_bytes")
            raw_tx = read_counter(self.interface, "tx_bytes")
            boot_id = read_boot_id()
            state = self.state
            current_period = period_start.isoformat()
            same_period = state.get("period_start") == current_period
            same_boot = state.get("boot_id") == boot_id

            if not same_period:
                state = {
                    "version": VERSION,
                    "period_start": current_period,
                    "rx_bytes": 0,
                    "tx_bytes": 0,
                }

            if (
                not initial
                and same_period
                and same_boot
                and raw_rx >= int(state.get("last_raw_rx", raw_rx))
                and raw_tx >= int(state.get("last_raw_tx", raw_tx))
            ):
                state["rx_bytes"] = int(state.get("rx_bytes", 0)) + (
                    raw_rx - int(state.get("last_raw_rx", raw_rx))
                )
                state["tx_bytes"] = int(state.get("tx_bytes", 0)) + (
                    raw_tx - int(state.get("last_raw_tx", raw_tx))
                )

            state.update(
                {
                    "version": VERSION,
                    "period_start": current_period,
                    "boot_id": boot_id,
                    "last_raw_rx": raw_rx,
                    "last_raw_tx": raw_tx,
                    "updated_at": now.isoformat(),
                }
            )
            self.state = state
            self.save()

    def run(self):
        while not self.stop_event.wait(SAMPLE_INTERVAL):
            try:
                self.sample()
            except Exception:
                # Keep the API available; the next sample will retry.
                pass

    def snapshot(self):
        self.sample()
        now = utc_now()
        period_start, next_reset = billing_period(now)

        with self.lock:
            rx_bytes = int(self.state.get("rx_bytes", 0))
            tx_bytes = int(self.state.get("tx_bytes", 0))

        total_bytes = rx_bytes + tx_bytes
        quota_bytes = int(TOTAL_GB * 1024**3) if TOTAL_GB else 0
        usage_percent = (
            min(total_bytes / quota_bytes * 100, 999.9) if quota_bytes else None
        )

        with open("/proc/uptime", encoding="ascii") as uptime_file:
            uptime_seconds = int(float(uptime_file.read().split()[0]))

        return {
            "ok": True,
            "hostname": socket.gethostname(),
            "interface": self.interface,
            "rx_bytes": rx_bytes,
            "tx_bytes": tx_bytes,
            "total_bytes": total_bytes,
            "quota_bytes": quota_bytes,
            "usage_percent": usage_percent,
            "period_start": period_start.isoformat(),
            "next_reset": next_reset.isoformat(),
            "uptime_seconds": uptime_seconds,
            "load_1m": os.getloadavg()[0],
            "updated_at": now.isoformat(),
        }


COUNTER = TrafficCounter()


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path.rstrip("/") != "/status":
            self.send_error(404)
            return

        try:
            body = json.dumps(COUNTER.snapshot(), separators=(",", ":")).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)
        except Exception as error:
            body = json.dumps(
                {"ok": False, "error": str(error)}, separators=(",", ":")
            ).encode()
            self.send_response(500)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    def log_message(self, *_):
        return


def shutdown(*_):
    COUNTER.stop_event.set()
    threading.Thread(target=server.shutdown, daemon=True).start()


threading.Thread(target=COUNTER.run, daemon=True).start()
server = ThreadingHTTPServer((LISTEN_HOST, LISTEN_PORT), Handler)
signal.signal(signal.SIGTERM, shutdown)
signal.signal(signal.SIGINT, shutdown)
server.serve_forever()

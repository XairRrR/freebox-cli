"""Tests des fonctions pures de fbx (aucun accès réseau ni à une vraie Freebox)."""
import copy
import importlib.machinery
import importlib.util
import json
import threading
import urllib.error
import urllib.request
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parent.parent / "fbx"
_loader = importlib.machinery.SourceFileLoader("fbx", str(SCRIPT))
_spec = importlib.util.spec_from_loader("fbx", _loader)
fbx = importlib.util.module_from_spec(_spec)
_loader.exec_module(fbx)


@pytest.fixture(autouse=True)
def isolated_state(tmp_path, monkeypatch):
    monkeypatch.setattr(fbx, "STATE_DIR", tmp_path)
    monkeypatch.setattr(fbx, "EVENT_LOG", tmp_path / "events.jsonl")


# ── formatage ──────────────────────────────────────────────────────────────

@pytest.mark.parametrize("sec,expected", [(5, "0m05s"), (125, "2m05s"), (3600, "1h00m"), (35640, "9h54m"),
                                          (90061, "1j 1h01m")])
def test_fmt_dur(sec, expected):
    assert fbx.fmt_dur(sec) == expected


def test_fmt_bits():
    assert fbx.fmt_bits(8_000_000_000) == "8.0 Gbit/s"
    assert fbx.fmt_bits(None) == "—"


def test_wifi_rate_units():
    # HT MCS15 20 MHz short GI = 144,4 Mbit/s, renvoyé par l'API comme 1444
    assert fbx.wifi_rate({"bitrate": 1444}) == "144.4 Mbit/s"


def test_sparkline_time_buckets():
    pts = [(0, 0), (10, 10), (20, None), (30, 5)]
    line = fbx.sparkline(pts, width=4)
    assert len(line) == 4
    assert line[0] == "▁" and line[1] == "█"
    assert fbx.sparkline([(0, None)]) == ""


# ── détection de coupures dans le RRD ─────────────────────────────────────

def _pt(t, up=True, empty=False):
    if empty:
        return {"time": t}
    return {"time": t, "bw_down": 1_000_000_000 if up else 0, "rate_down": 10}


def test_find_outages_none():
    data = [_pt(t) for t in range(0, 3600, 120)]
    assert fbx.find_outages(data) == []


def test_find_outages_empty_points_then_gap():
    # cas réel du 05/11 : points vides à 16:08 puis plus rien pendant ~10 h
    data = [_pt(t) for t in range(0, 1200, 120)] + [_pt(1200, empty=True)] + [_pt(1200 + 35640 + i * 120) for i in range(5)]
    (start, end, why), = fbx.find_outages(data)
    assert start == 1200 and end == 1200 + 35640
    assert why == {"WAN coupé (points vides)", "aucune mesure enregistrée"}


def test_find_outages_resolution_change_is_not_a_gap():
    # passage d'une résolution 2 min à 14 min : ce n'est pas une coupure
    data = [_pt(t) for t in range(0, 8400, 840)] + [_pt(8400 + t) for t in range(0, 2400, 120)]
    assert fbx.find_outages(data) == []


def test_find_outages_ongoing():
    data = [_pt(0), _pt(120), _pt(240, up=False), _pt(360, up=False)]
    (start, end, why), = fbx.find_outages(data)
    assert start == 240 and end is None and why == {"débit disponible = 0"}


# ── étape de démarrage / diagnostic ────────────────────────────────────────

OK = {"system": {"box_authenticated": True}, "conn": {"state": "up"},
      "ftth": {"sfp_present": True, "sfp_alim_ok": True, "sfp_has_signal": True, "link": True}}


def _with(**changes):
    s = copy.deepcopy(OK)
    for path, value in changes.items():
        part, key = path.split("__")
        s[part][key] = value
    return s


@pytest.mark.parametrize("snap,code", [
    (OK, "8"),
    (_with(ftth__sfp_present=False, conn__state="down"), "1"),
    (_with(ftth__sfp_has_signal=False, conn__state="down"), "2"),
    (_with(ftth__link=False, conn__state="down"), "3"),
    (_with(system__box_authenticated=False, conn__state="down"), "6"),
    (_with(conn__state="going_up"), "7"),
    ({}, "?"),
])
def test_boot_phase(snap, code):
    assert fbx.boot_phase(snap)[0] == code


def test_verdict_names_free_for_step6():
    color, msg = fbx.verdict(_with(system__box_authenticated=False, conn__state="down"))
    assert color == "red"
    assert "étape 6" in msg and "côté Free" in msg


def test_verdict_ok():
    assert fbx.verdict(OK)[0] == "green"


# ── journal de connexion de la box ─────────────────────────────────────────

LOGS = [{"state": "up", "type": "link", "bw_down": 8_000_000_000, "link": "ftth", "id": 1,
         "bw_up": 8_000_000_000, "date": 1793928711},
        {"conn": "ftth_pub", "type": "conn", "id": 3, "state": "up", "date": 1793928718}]


def test_describe_box_log():
    assert fbx.describe_box_log(LOGS[0]).startswith("Lien ftth up")
    assert fbx.describe_box_log(LOGS[1]) == "Connexion Fibre (IP publique) up"


class FakeBox:
    def __init__(self, logs):
        self.logs = logs

    def get(self, path):
        assert path == "connection/logs/"
        return self.logs


def test_sync_box_logs_is_idempotent():
    box = FakeBox(LOGS)
    assert len(fbx.sync_box_logs(box)) == 2
    assert fbx.sync_box_logs(box) == []  # déjà archivées
    box.logs = LOGS + [{"conn": "ftth_pub", "type": "conn", "id": 4, "state": "down", "date": 1793930000}]
    assert len(fbx.sync_box_logs(box)) == 1
    assert [r["event"] for r in fbx.read_events()] == ["box_log"] * 3


# ── récepteur de notifications push ───────────────────────────────────────

def _serve(allowed):
    srv = fbx.http.server.ThreadingHTTPServer(("127.0.0.1", 0), fbx.make_notif_handler(False, allowed))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv


def _post(srv, path, body):
    req = urllib.request.Request(f"http://127.0.0.1:{srv.server_address[1]}{path}", data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json"}, method="POST")
    return urllib.request.urlopen(req, timeout=5)


def test_notify_accepts_box_and_logs():
    srv = _serve({"127.0.0.1"})
    try:
        r = _post(srv, "/send", {"devices": ["d1"], "payload": {"type": "box_state", "event": "pub_up"}})
        assert json.load(r) == {"failureIds": [], "successIds": ["d1"]}
        (ev,) = fbx.read_events()
        assert ev["event"] == "box_push" and ev["detail"]["payload"]["event"] == "pub_up"
    finally:
        srv.shutdown()


def test_notify_rejects_other_sources():
    srv = _serve({"192.0.2.1"})  # la « box » n'est pas 127.0.0.1
    try:
        with pytest.raises(urllib.error.HTTPError) as e:
            _post(srv, "/send", {"payload": {"type": "box_state", "event": "reboot"}})
        assert e.value.code == 403
        assert fbx.read_events() == []
    finally:
        srv.shutdown()

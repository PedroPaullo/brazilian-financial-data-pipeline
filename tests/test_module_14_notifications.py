from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path
import shutil

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from notifications import send_new_alert_notifications


def _alert(message: str) -> dict:
    return {
        "severity": "CRITICAL",
        "alert_type": "freshness",
        "source_name": "BCB_SGS",
        "dataset_name": "selic_daily",
        "message": message,
        "recommended_action": "Verificar fonte.",
    }


def test_notifications_are_deduplicated_when_disabled():
    temp_dir = Path(tempfile.mkdtemp(prefix="notifications-", dir=PROJECT_ROOT))
    try:
        state_file = temp_dir / "notification_state.json"
        alert = _alert("Fonte ainda nao atualizada.")

        first = send_new_alert_notifications([alert], state_file=state_file)
        second = send_new_alert_notifications([alert], state_file=state_file)

        assert first["enabled"] is False
        assert first["new_alerts"] == 1
        assert second["new_alerts"] == 1
        assert json.loads(state_file.read_text(encoding="utf-8"))["sent_fingerprints"] == []
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def test_notifications_ignore_info_alerts():
    temp_dir = Path(tempfile.mkdtemp(prefix="notifications-", dir=PROJECT_ROOT))
    try:
        state_file = temp_dir / "notification_state.json"
        alert = _alert("Sem problema")
        alert["severity"] = "INFO"

        result = send_new_alert_notifications([alert], state_file=state_file)

        assert result["new_alerts"] == 0
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)

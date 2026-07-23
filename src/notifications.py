from __future__ import annotations

import hashlib
import json
import os
import smtplib
from email.message import EmailMessage
from pathlib import Path
from typing import Any

from config import (
    ALERT_EMAIL_APP_PASSWORD,
    ALERT_EMAIL_ENABLED,
    ALERT_EMAIL_HOST,
    ALERT_EMAIL_PORT,
    ALERT_EMAIL_RECIPIENT,
    ALERT_EMAIL_SENDER,
    ALERT_NOTIFICATION_STATE_FILE,
)
from logger import get_logger

logger = get_logger(__name__)


def _fingerprint(alert: dict[str, Any]) -> str:
    key = "|".join(str(alert.get(field, "")) for field in ("alert_type", "source_name", "dataset_name", "message"))
    return hashlib.sha256(key.encode("utf-8")).hexdigest()


def _load_state(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"sent_fingerprints": []}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"sent_fingerprints": []}


def _save_state(path: Path, fingerprints: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps({"sent_fingerprints": fingerprints[-500:]}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _render_body(alerts: list[dict[str, Any]]) -> str:
    lines = ["Brazilian Financial Data Pipeline - alertas operacionais", ""]
    for alert in alerts:
        lines.extend(
            [
                f"[{alert.get('severity')}] {alert.get('dataset_name')}",
                f"Fonte: {alert.get('source_name')}",
                f"Mensagem: {alert.get('message')}",
                f"Acao: {alert.get('recommended_action')}",
                "",
            ]
        )
    return "\n".join(lines)


def send_new_alert_notifications(
    alerts: list[dict[str, Any]],
    state_file: Path = ALERT_NOTIFICATION_STATE_FILE,
) -> dict[str, Any]:
    actionable = [alert for alert in alerts if alert.get("severity") in {"WARNING", "CRITICAL"}]
    state = _load_state(state_file)
    sent_fingerprints = set(state.get("sent_fingerprints", []))
    new_alerts = [alert for alert in actionable if _fingerprint(alert) not in sent_fingerprints]

    result = {"enabled": ALERT_EMAIL_ENABLED, "new_alerts": len(new_alerts), "sent": False}
    if not new_alerts:
        _save_state(state_file, list(sent_fingerprints))
        return result

    if not ALERT_EMAIL_ENABLED:
        logger.warning("Notificacao desabilitada; %s alerta(s) novo(s) persistido(s) para envio posterior.", len(new_alerts))
        _save_state(state_file, list(sent_fingerprints))
        return result

    missing = [name for name, value in {
        "ALERT_EMAIL_SENDER": ALERT_EMAIL_SENDER,
        "ALERT_EMAIL_RECIPIENT": ALERT_EMAIL_RECIPIENT,
        "ALERT_EMAIL_APP_PASSWORD": ALERT_EMAIL_APP_PASSWORD,
    }.items() if not value]
    if missing:
        raise RuntimeError(f"Notificacao habilitada sem configuracao: {', '.join(missing)}")

    message = EmailMessage()
    message["Subject"] = f"Pipeline financeiro: {len(new_alerts)} alerta(s) operacional(is)"
    message["From"] = ALERT_EMAIL_SENDER
    message["To"] = ALERT_EMAIL_RECIPIENT
    message.set_content(_render_body(new_alerts))
    with smtplib.SMTP(ALERT_EMAIL_HOST, ALERT_EMAIL_PORT, timeout=30) as smtp:
        smtp.starttls()
        smtp.login(ALERT_EMAIL_SENDER, ALERT_EMAIL_APP_PASSWORD)
        smtp.send_message(message)

    sent_fingerprints.update(_fingerprint(alert) for alert in new_alerts)
    _save_state(state_file, list(sent_fingerprints))
    logger.info("Notificacao Gmail enviada com %s alerta(s) novo(s).", len(new_alerts))
    result["sent"] = True
    return result

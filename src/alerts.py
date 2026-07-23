from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from pathlib import Path
from typing import Any

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))

from config import (
    ALERTS_CSV_FILE,
    ALERTS_JSON_FILE,
    COVERAGE_REPORT_FILE,
    COVERAGE_SUMMARY_FILE,
    FINANCIAL_REPORT_FILE,
    OPERATIONS_DB_FILE,
    PROCESSED_DB_FILE,
    VALIDATION_OUTPUT_FILES,
)
from logger import get_logger
from monitoring import record_data_artifact
from notifications import send_new_alert_notifications

logger = get_logger(__name__)


def _now() -> str:
    return pd.Timestamp.now().strftime("%Y-%m-%d %H:%M:%S")


def _alert(
    alerts: list[dict[str, Any]],
    severity: str,
    alert_type: str,
    source_name: str,
    dataset_name: str,
    message: str,
    recommended_action: str,
    status: str = "OPEN",
) -> None:
    alerts.append(
        {
            "alert_id": len(alerts) + 1,
            "created_at": _now(),
            "severity": severity,
            "alert_type": alert_type,
            "source_name": source_name,
            "dataset_name": dataset_name,
            "message": message,
            "recommended_action": recommended_action,
            "status": status,
        }
    )


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    with open(path, "r", encoding="utf-8") as file:
        return json.load(file)


def _read_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    return pd.read_csv(path)


def _read_table(database_file: Path, table_name: str) -> pd.DataFrame:
    if not database_file.exists():
        return pd.DataFrame()
    with sqlite3.connect(database_file) as conn:
        try:
            return pd.read_sql_query(f"SELECT * FROM {table_name}", conn)
        except Exception:
            return pd.DataFrame()


def generate_operational_alerts(
    operations_db_file: Path = OPERATIONS_DB_FILE,
    processed_db_file: Path = PROCESSED_DB_FILE,
    financial_report_file: Path = FINANCIAL_REPORT_FILE,
    alerts_json_file: Path = ALERTS_JSON_FILE,
    alerts_csv_file: Path = ALERTS_CSV_FILE,
) -> list[dict[str, Any]]:
    alerts: list[dict[str, Any]] = []

    if not processed_db_file.exists():
        _alert(alerts, "CRITICAL", "missing_artifact", "pipeline", "processed_db", f"Banco final ausente: {processed_db_file}", "Execute python src\\load_processed_data.py.")

    if not operations_db_file.exists():
        _alert(alerts, "WARNING", "missing_artifact", "pipeline", "operations_db", f"Banco operacional ausente: {operations_db_file}", "Execute o pipeline ou o teste de monitoramento para criar a camada operacional.")

    if not financial_report_file.exists():
        _alert(alerts, "CRITICAL", "missing_artifact", "pipeline", "financial_report", f"Relatorio Excel ausente: {financial_report_file}", "Execute python src\\generate_report.py.")

    summary = _read_json(VALIDATION_OUTPUT_FILES["quality_summary"])
    if not summary:
        _alert(alerts, "WARNING", "missing_artifact", "validation", "quality_summary", "Resumo de qualidade nao encontrado.", "Execute python src\\validate_data.py.")
    elif int(summary.get("fail", 0)) > 0:
        _alert(alerts, "CRITICAL", "data_quality", "validation", "quality_summary", f"Validacao possui {summary.get('fail')} FAIL.", "Investigue reports/validation/data_quality_results.csv.")
    elif int(summary.get("warn", 0)) > 0:
        _alert(alerts, "WARNING", "data_quality", "validation", "quality_summary", f"Validacao possui {summary.get('warn')} WARN.", "Revise gaps e warnings antes de divulgar resultados.")

    coverage_summary = _read_json(COVERAGE_SUMMARY_FILE)
    if not coverage_summary:
        _alert(alerts, "WARNING", "missing_artifact", "coverage", "coverage_summary", "Resumo de cobertura historica nao encontrado.", "Execute python src\\coverage_report.py.")
    elif int(coverage_summary.get("critical", 0)) > 0:
        _alert(alerts, "CRITICAL", "data_coverage", "coverage", "summary", f"Cobertura possui {coverage_summary.get('critical')} dataset(s) CRITICAL.", "Revise reports/coverage/data_coverage_report.csv.")
    elif int(coverage_summary.get("warning", 0)) > 0:
        _alert(alerts, "WARNING", "data_coverage", "coverage", "summary", f"Cobertura possui {coverage_summary.get('warning')} dataset(s) WARNING.", "Revise gaps historicos antes de divulgar resultados.")

    coverage_results = _read_csv(COVERAGE_REPORT_FILE)
    if not coverage_results.empty:
        for _, row in coverage_results[coverage_results["status"].isin(["WARNING", "CRITICAL"])].iterrows():
            _alert(
                alerts,
                str(row["status"]),
                "data_coverage_dataset",
                str(row.get("source_name", "")),
                str(row.get("dataset_name", "")),
                f"{row.get('dataset_name')} com cobertura {row.get('coverage_pct')}% no periodo.",
                str(row.get("missing_sample") or "Verifique reports/coverage/data_coverage_missing_dates.csv."),
            )

    quality_results = _read_csv(VALIDATION_OUTPUT_FILES["quality_results"])
    for _, row in quality_results[quality_results.get("status", pd.Series(dtype=str)).isin(["WARN", "FAIL"])].iterrows():
        severity = "CRITICAL" if row["status"] == "FAIL" else "WARNING"
        _alert(
            alerts,
            severity,
            "data_quality_check",
            "validation",
            str(row.get("dataset", "")),
            f"{row.get('check_name')} em {row.get('dataset')}: {row.get('rows_affected')} linhas afetadas.",
            str(row.get("details", "Verifique o resultado de qualidade.")),
        )

    freshness_df = _read_table(operations_db_file, "source_freshness")
    if freshness_df.empty and operations_db_file.exists():
        _alert(alerts, "WARNING", "freshness", "pipeline", "source_freshness", "Tabela source_freshness vazia.", "Execute a carga final para atualizar freshness.")
    else:
        status_col = "freshness_status" if "freshness_status" in freshness_df.columns else "status"
        for _, row in freshness_df[freshness_df[status_col].isin(["WARNING", "CRITICAL"])].iterrows():
            _alert(
                alerts,
                str(row[status_col]),
                "freshness",
                str(row.get("source_name", "")),
                str(row.get("dataset_name", "")),
                f"Fonte {row.get('dataset_name')} com status {row[status_col]} e lag {row.get('lag_days', 'N/D')} dias.",
                "Verifique se a fonte deveria ter dados mais recentes ou se houve feriado/data sem divulgacao.",
            )

    runs_df = _read_table(operations_db_file, "pipeline_runs")
    if not runs_df.empty:
        failed_runs = runs_df[runs_df["status"] == "FAILED"]
        if not failed_runs.empty:
            latest_failed = failed_runs.sort_values("run_id").iloc[-1]
            _alert(
                alerts,
                "CRITICAL",
                "pipeline_run",
                "pipeline",
                str(latest_failed["module_name"]),
                f"Ultima falha registrada no modulo {latest_failed['module_name']}.",
                str(latest_failed.get("error_message") or "Verifique logs/pipeline.log."),
            )

    if processed_db_file.exists():
        try:
            with sqlite3.connect(processed_db_file) as conn:
                counts = {
                    "bcb_series": conn.execute("SELECT COUNT(*) FROM vw_bcb_series_values").fetchone()[0],
                    "b3_prices": conn.execute("SELECT COUNT(*) FROM vw_b3_stock_prices").fetchone()[0],
                }
            for dataset_name, row_count in counts.items():
                if row_count == 0:
                    _alert(alerts, "CRITICAL", "dashboard_data", "processed_db", dataset_name, f"{dataset_name} sem registros.", "Reexecute coleta/carga e valide a origem.")
        except Exception as exc:
            _alert(alerts, "CRITICAL", "dashboard_data", "processed_db", "sqlite", f"Falha ao consultar banco final: {exc}", "Verifique schema.sql e carga final.")

    if not alerts:
        _alert(alerts, "INFO", "pipeline_health", "pipeline", "all", "Nenhum alerta critico ou warning encontrado.", "Manter rotina de execucao e revisao.")

    alerts_json_file.parent.mkdir(parents=True, exist_ok=True)
    with open(alerts_json_file, "w", encoding="utf-8") as file:
        json.dump(alerts, file, ensure_ascii=False, indent=4)
    pd.DataFrame(alerts).to_csv(alerts_csv_file, index=False, encoding="utf-8")

    try:
        notification_result = send_new_alert_notifications(alerts)
        logger.info("Notificacao operacional: %s", notification_result)
    except Exception as exc:
        _alert(
            alerts,
            "CRITICAL",
            "notification_delivery",
            "gmail",
            "alerts",
            f"Falha ao enviar notificacao operacional: {exc}",
            "Verifique as variaveis ALERT_EMAIL_* e a senha de aplicativo do Gmail.",
        )
        pd.DataFrame(alerts).to_csv(alerts_csv_file, index=False, encoding="utf-8")
        logger.exception("Falha na entrega de notificacao operacional.")

    record_data_artifact("alerts_json", alerts_json_file, "operational_alerts", len(alerts), details="Operational alerts JSON")
    record_data_artifact("alerts_csv", alerts_csv_file, "operational_alerts", len(alerts), details="Operational alerts CSV")
    return alerts


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--json-file", default=str(ALERTS_JSON_FILE))
    parser.add_argument("--csv-file", default=str(ALERTS_CSV_FILE))
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    alerts = generate_operational_alerts(
        alerts_json_file=Path(args.json_file),
        alerts_csv_file=Path(args.csv_file),
    )
    severity_counts = pd.DataFrame(alerts)["severity"].value_counts().to_dict()
    logger.info("Alertas gerados: %s", severity_counts)


if __name__ == "__main__":
    main()

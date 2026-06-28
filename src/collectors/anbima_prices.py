from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from collectors.anbima_client import AnbimaClient
from logger import get_logger
from monitoring import record_data_artifact, upsert_source_status

logger = get_logger(__name__)


def collect_debentures_secondary_market(output_file: Path | None = None) -> dict:
    client = AnbimaClient()
    if not client.is_enabled() or not client.has_credentials():
        result = {"status": "SKIPPED", "reason": "ANBIMA nao configurada ou desabilitada."}
        upsert_source_status(
            "ANBIMA",
            "debentures_mercado_secundario",
            "SKIPPED",
            expected_frequency="optional",
            details=result["reason"],
        )
        if output_file is not None:
            record_data_artifact("raw_csv", output_file, "anbima_debentures", 0, status="SKIPPED", details=result["reason"])
        return result

    return {"status": "SKIPPED", "reason": "Endpoint ANBIMA deve ser configurado conforme contrato de acesso."}


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-file", default=None)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    output_file = Path(args.output_file) if args.output_file else None
    result = collect_debentures_secondary_market(output_file)
    logger.info("Resultado ANBIMA: %s", result)


if __name__ == "__main__":
    main()

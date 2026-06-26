"""
Benchmark de tiempos de respuesta para documentar métricas del RFC.
Uso: python scripts/benchmark_metricas.py [--base-url http://135.181.30.179:8000]
"""
from __future__ import annotations

import argparse
import json
import os
import statistics
import sys
import time
import uuid

import requests

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

LAT, LNG, RADIO, RUBRO = 19.432608, -99.133208, 1000, "cafeteria"
HEADERS = {"Authorization": "Bearer benchmark-token", "Content-Type": "application/json"}


def ms(seconds: float) -> float:
    return round(seconds * 1000, 0)


def percentile(values: list[float], p: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    idx = max(0, min(len(ordered) - 1, int(round((p / 100) * (len(ordered) - 1)))))
    return ordered[idx]


def bench_http(label: str, fn, runs: int = 3) -> dict:
    times: list[float] = []
    status = None
    error = None
    for _ in range(runs):
        start = time.perf_counter()
        try:
            status = fn()
        except Exception as exc:  # noqa: BLE001
            error = str(exc)
            break
        times.append(time.perf_counter() - start)
    return {
        "label": label,
        "runs": len(times),
        "p50_ms": ms(percentile(times, 50)) if times else None,
        "p95_ms": ms(percentile(times, 95)) if times else None,
        "mean_ms": ms(statistics.mean(times)) if times else None,
        "status": status,
        "error": error,
    }


def bench_postgres() -> list[dict]:
    results: list[dict] = []
    try:
        from sqlalchemy import text

        from app.analytics import obtener_demografia_ponderada, resolver_google_type
        from app.database import SessionLocal
        from app.nse import calcular_nse
    except Exception as exc:  # noqa: BLE001
        return [{"label": "postgres", "error": f"No disponible localmente: {exc}"}]

    db = SessionLocal()
    try:
        db.execute(text("SELECT 1"))
        start = time.perf_counter()
        db.execute(text("SELECT 1"))
        results.append({"label": "Postgres ping (SELECT 1)", "p50_ms": ms(time.perf_counter() - start)})

        start = time.perf_counter()
        obtener_demografia_ponderada(db, LAT, LNG, RADIO)
        results.append({"label": "Postgres demografía ponderada (ST_Intersects)", "p50_ms": ms(time.perf_counter() - start)})

        start = time.perf_counter()
        calcular_nse(db, LAT, LNG, RADIO)
        results.append({"label": "Postgres cálculo NSE", "p50_ms": ms(time.perf_counter() - start)})

        start = time.perf_counter()
        resolver_google_type(db, RUBRO)
        results.append({"label": "Postgres cruce rubro -> categoria", "p50_ms": ms(time.perf_counter() - start)})
    except Exception as exc:  # noqa: BLE001
        results.append({"label": "postgres", "error": str(exc)})
    finally:
        db.close()
    return results


def run_api_benchmarks(base_url: str) -> dict:
    session = requests.Session()
    session.headers.update(HEADERS)
    out: dict = {"base_url": base_url, "api": [], "flujo": {}}

    out["api"].append(
        bench_http(
            "GET /health",
            lambda: session.get(f"{base_url}/health", timeout=120).status_code,
        )
    )

    previa_url = (
        f"{base_url}/api/analizar/previa"
        f"?lat={LAT}&lng={LNG}&radio_metros={RADIO}&rubro={RUBRO}"
    )
    out["api"].append(
        bench_http(
            "POST /api/analizar/previa (análisis completo en página)",
            lambda: session.post(previa_url, json={}, timeout=300).status_code,
            runs=2,
        )
    )

    out["api"].append(
        bench_http(
            "GET /api/analizar/buscar-direccion?q=Reforma+222",
            lambda: session.get(
                f"{base_url}/api/analizar/buscar-direccion",
                params={"q": "Reforma 222"},
                timeout=60,
            ).status_code,
        )
    )

    pref_payload = {
        "tier_adquirido": "basico",
        "latitud": LAT,
        "longitud": LNG,
        "radio_metros": RADIO,
        "rubro": RUBRO,
        "intenciones": "Benchmark de métricas RFC.",
    }
    pref_resp = session.post(f"{base_url}/api/pagos/preferencia", json=pref_payload, timeout=60)
    pref_resp.raise_for_status()
    pref_data = pref_resp.json()
    checkout_id = pref_data["checkout_id"]
    orden_id = pref_data["orden_id"]

    out["api"].append(
        {
            "label": "POST /api/pagos/preferencia",
            "p50_ms": ms(pref_resp.elapsed.total_seconds()),
            "status": pref_resp.status_code,
        }
    )

    webhook_start = time.perf_counter()
    wh_resp = session.post(
        f"{base_url}/api/pagos/webhook-mock",
        json={"checkout_id": checkout_id, "estado_pago": "approved"},
        timeout=60,
    )
    webhook_ms = ms(time.perf_counter() - webhook_start)
    wh_resp.raise_for_status()
    out["flujo"]["desbloqueo_post_pago_ms"] = webhook_ms

    resultado_start = time.perf_counter()
    res_resp = session.get(f"{base_url}/api/analizar/resultado/{orden_id}", timeout=300)
    resultado_first_ms = ms(time.perf_counter() - resultado_start)
    out["flujo"]["primer_resultado_dashboard_ms"] = resultado_first_ms
    out["flujo"]["resultado_status_first"] = res_resp.status_code

    pdf_ready_ms = None
    pdf_polls = 0
    poll_start = time.perf_counter()
    for _ in range(90):
        pdf_polls += 1
        pdf_resp = session.get(f"{base_url}/api/analizar/pdf/{orden_id}", timeout=60)
        if pdf_resp.status_code == 200:
            pdf_ready_ms = ms(time.perf_counter() - poll_start)
            break
        if pdf_resp.status_code not in (422, 404):
            break
        time.sleep(2)
    out["flujo"]["generacion_pdf_ms"] = pdf_ready_ms
    out["flujo"]["pdf_polls"] = pdf_polls
    out["flujo"]["orden_id"] = orden_id

    cache_start = time.perf_counter()
    cache_resp = session.get(f"{base_url}/api/analizar/resultado/{orden_id}", timeout=120)
    out["flujo"]["resultado_con_cache_ms"] = ms(time.perf_counter() - cache_start)
    out["flujo"]["resultado_status_cache"] = cache_resp.status_code

    return out


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://135.181.30.179:8000")
    args = parser.parse_args()

    report = {
        "measured_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "postgres": bench_postgres(),
        "remote": run_api_benchmarks(args.base_url),
    }
    out_path = os.path.join(os.path.dirname(__file__), "benchmark_metricas_result.json")
    with open(out_path, "w", encoding="utf-8") as fh:
        json.dump(report, fh, indent=2, ensure_ascii=False)
    print(out_path)


if __name__ == "__main__":
    main()

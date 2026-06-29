"""Read-only HTML analytics dashboard."""

import json
from datetime import UTC, datetime, timedelta

from src.config import Settings
from src.db.repository import Repository


def create_dashboard_app(settings: Settings, repository: Repository):
    from fastapi import FastAPI, HTTPException, Request
    from fastapi.responses import HTMLResponse

    app = FastAPI(title="Bot Analytics Dashboard", docs_url=None, redoc_url=None)

    @app.get("/admin/dashboard")
    async def dashboard(request: Request) -> HTMLResponse:
        token = request.query_params.get("token")
        if not token or token != settings.analytics_dashboard_token:
            raise HTTPException(status_code=401, detail="Unauthorized")

        end = datetime.now(UTC).date()
        start = end - timedelta(days=29)
        rows = repository.get_daily_stats_range(start.isoformat(), end.isoformat())

        if not rows:
            from src.analytics.aggregator import AnalyticsAggregator

            agg = AnalyticsAggregator(repository)
            for offset in range(30):
                day = end - timedelta(days=offset)
                agg.compute_daily_stats(day)
            rows = repository.get_daily_stats_range(start.isoformat(), end.isoformat())

        labels = [r["stats_date"] for r in rows]
        queries = [int(r["total_queries"]) for r in rows]
        tokens = [
            int(r["tokens_input"]) + int(r["tokens_output"]) for r in rows
        ]
        total_q = sum(queries)
        total_tok = sum(tokens)

        html = f"""<!DOCTYPE html>
<html lang="ru">
<head>
  <meta charset="utf-8"/>
  <title>Bot Analytics</title>
  <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
  <style>
    body {{ font-family: system-ui, sans-serif; margin: 2rem; background: #f8f9fa; }}
    .kpi {{ display: flex; gap: 1rem; margin-bottom: 2rem; }}
    .card {{ background: #fff; padding: 1rem 1.5rem; border-radius: 8px;
             box-shadow: 0 1px 3px rgba(0,0,0,.1); }}
    table {{ border-collapse: collapse; width: 100%; background: #fff; }}
    th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
    th {{ background: #eee; }}
  </style>
</head>
<body>
  <h1>📊 Аналитика бота (30 дней)</h1>
  <div class="kpi">
    <div class="card"><strong>Запросов</strong><br/>{total_q}</div>
    <div class="card"><strong>Токенов</strong><br/>{total_tok:,}</div>
    <div class="card"><strong>Дней с данными</strong><br/>{len(rows)}</div>
  </div>
  <canvas id="chart" height="100"></canvas>
  <h2>По дням</h2>
  <table>
    <tr><th>Дата</th><th>Запросы</th><th>Пользователи</th><th>Токены</th></tr>
    {"".join(
        f"<tr><td>{r['stats_date']}</td><td>{r['total_queries']}</td>"
        f"<td>{r['unique_users']}</td>"
        f"<td>{int(r['tokens_input']) + int(r['tokens_output'])}</td></tr>"
        for r in rows
    )}
  </table>
  <script>
    new Chart(document.getElementById('chart'), {{
      type: 'line',
      data: {{
        labels: {json.dumps(labels)},
        datasets: [
          {{ label: 'Запросы', data: {json.dumps(queries)}, borderColor: '#2563eb' }},
          {{ label: 'Токены', data: {json.dumps(tokens)}, borderColor: '#16a34a', yAxisID: 'y1' }}
        ]
      }},
      options: {{
        scales: {{ y: {{ beginAtZero: true }}, y1: {{ position: 'right', beginAtZero: true }} }}
      }}
    }});
  </script>
</body>
</html>"""
        return HTMLResponse(html)

    return app


async def start_dashboard_server(settings: Settings, repository: Repository) -> None:
    import uvicorn

    app = create_dashboard_app(settings, repository)
    config = uvicorn.Config(
        app,
        host="127.0.0.1",
        port=settings.analytics_dashboard_port,
        log_level="warning",
    )
    server = uvicorn.Server(config)
    await server.serve()

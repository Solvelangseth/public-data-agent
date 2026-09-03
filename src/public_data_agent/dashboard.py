"""Small local dashboard for exercising the planner and ask pipeline."""

from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

from public_data_agent.ask import ask
from public_data_agent.executor import execute_plan
from public_data_agent.llm_planner import candidate_context, plan_with_provider
from public_data_agent.openai_planner import OpenAIPlanProvider
from public_data_agent.planner import build_plan
from public_data_agent.registry import Registry
from public_data_agent.search import search_report


HTML = """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Public Data Agent</title>
<style>
body{font:16px system-ui,sans-serif;max-width:1100px;margin:0 auto;padding:28px;background:#f5f7f9;color:#17202a}
main{background:white;border:1px solid #d9e0e6;border-radius:12px;padding:24px;box-shadow:0 4px 18px #17202a12}
h1{margin-top:0}.muted{color:#5b6873}textarea{width:100%;min-height:80px;padding:12px;font:inherit;border:1px solid #b8c3cc;border-radius:8px;box-sizing:border-box}
button{background:#075985;color:white;border:0;border-radius:7px;padding:10px 16px;margin:10px 8px 10px 0;font-weight:600;cursor:pointer}button.secondary{background:#475569}
pre{white-space:pre-wrap;overflow:auto;background:#111827;color:#d1fae5;border-radius:8px;padding:16px;min-height:180px}.status{min-height:24px}
</style></head><body><main><h1>Public Data Agent</h1>
<p class="muted">Test the local Norwegian public-data planner. Plan mode never fetches data.</p>
<textarea id="question">Hvilke Oslo-bydeler er størst og hvilke vokser mest?</textarea><br>
<button onclick="run('plan')">Inspect plan</button><button onclick="run('llm-plan')">LLM plan</button><button class="secondary" onclick="run('llm-run')">Run LLM plan</button><button class="secondary" onclick="run('ask')">Run demo/ask</button>
<div class="status" id="status"></div><h2>Summary</h2><p id="summary" class="muted">Enter a question and choose an action.</p><h2>Technical result</h2><pre id="result"></pre>
<script>
async function run(mode){const status=document.getElementById('status'), out=document.getElementById('result'); status.textContent='Working…'; out.textContent='';
 try{const r=await fetch('/api/'+mode,{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({question:document.getElementById('question').value})}); const body=await r.json(); out.textContent=JSON.stringify(body,null,2); const a=body.answer||{}; const largest=body.largest||[]; const growing=body.growing||[]; document.getElementById('summary').textContent=largest.length?`Largest: ${largest[0].name||largest[0].bydel_code} (${largest[0].population}). Fastest growth: ${(growing[0]||{}).name||'see technical result'}.`:a.explanation||body.execution?.explanation||'No numeric answer was retrieved.'; status.textContent=r.ok?'Done':'Request failed';}
 catch(e){status.textContent='Error';out.textContent=String(e)}}
</script></main></body></html>"""


def serve(db: str, host: str = "127.0.0.1", port: int = 8765) -> None:
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # noqa: N802
            if urlparse(self.path).path != "/":
                self.send_error(404)
                return
            self._send(200, "text/html; charset=utf-8", HTML.encode())

        def do_POST(self) -> None:  # noqa: N802
            path = urlparse(self.path).path
            if path not in {"/api/plan", "/api/llm-plan", "/api/llm-run", "/api/ask"}:
                self.send_error(404)
                return
            try:
                length = int(self.headers.get("content-length", "0"))
                question = json.loads(self.rfile.read(length)).get("question", "").strip()
                if not question:
                    raise ValueError("question is required")
                registry = Registry(db)
                try:
                    report = search_report(registry, question, limit=10)
                    plan = build_plan(
                        question,
                        report,
                        klass_dataset_id="datanorge:0c89041e-ae88-32ef-a765-8e1ccbd64fdd",
                        ssb_table="11763",
                        latest_year=2025,
                        prior_year=2024,
                        registry=registry,
                    )
                    if path == "/api/plan":
                        payload = {"plan": plan.to_dict(), "discovery": report.to_dict()}
                    elif path in {"/api/llm-plan", "/api/llm-run"}:
                        provider = OpenAIPlanProvider.from_env(dotenv=Path(".env"))
                        validation = plan_with_provider(
                            provider,
                            question=question,
                            candidates=candidate_context(report),
                        )
                        if validation.plan is None:
                            raise ValueError(validation.error or "LLM plan failed validation")
                        payload = {"plan": validation.plan.to_dict(), "discovery": report.to_dict()}
                        if path == "/api/llm-run":
                            execution = execute_plan(registry, validation.plan)
                            payload["execution"] = execution.to_dict()
                        else:
                            payload["execution"] = {"status": "not_executed", "numbers_retrieved": False}
                    else:
                        result = ask(registry, question)
                        payload = {
                            "plan": result.plan.to_dict() if result.plan else None,
                            "execution": result.execution,
                            "answer": result.answer,
                            "largest": result.largest,
                            "growing": result.growing,
                        }
                finally:
                    registry.close()
                self._send(200, "application/json; charset=utf-8", json.dumps(payload, ensure_ascii=False).encode())
            except Exception as exc:  # dashboard should show actionable errors
                self._send(400, "application/json; charset=utf-8", json.dumps({"error": str(exc)}).encode())

        def _send(self, status: int, content_type: str, body: bytes) -> None:
            self.send_response(status)
            self.send_header("content-type", content_type)
            self.send_header("content-length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *_args) -> None:
            return

    server = ThreadingHTTPServer((host, port), Handler)
    print(f"Dashboard running at http://{host}:{port} (database: {db})")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()

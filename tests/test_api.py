import io
import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

from app import create_app
from conftest import GOOD_JSON, FakeLLM


def upload(client, data: bytes, name="invoice.pdf"):
    return client.post("/api/extract", data={"file": (io.BytesIO(data), name)}, content_type="multipart/form-data")


@pytest.fixture
def webhook_server():
    received = []

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            received.append(json.loads(self.rfile.read(int(self.headers["Content-Length"]))))
            self.send_response(200)
            self.end_headers()

        def log_message(self, *args):
            pass

    server = HTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{server.server_port}/hook", received
    server.shutdown()


def test_health():
    assert create_app(FakeLLM(GOOD_JSON)).test_client().get("/health").get_json() == {"status": "ok"}


def test_upload_page():
    res = create_app(FakeLLM(GOOD_JSON)).test_client().get("/")
    assert res.status_code == 200 and b"Invoice Extractor" in res.data


def test_extract_and_job_status(invoice_pdf):
    client = create_app(FakeLLM(GOOD_JSON), webhook_url="").test_client()
    res = upload(client, invoice_pdf)
    assert res.status_code == 200
    job = res.get_json()
    assert job["status"] == "complete"
    assert job["result"]["data"]["total"] == 141.6
    assert client.get(f"/api/jobs/{job['id']}").get_json()["status"] == "complete"
    assert client.get("/api/jobs/nope").status_code == 404


def test_missing_file():
    client = create_app(FakeLLM(GOOD_JSON)).test_client()
    assert client.post("/api/extract").status_code == 400


def test_invalid_document_returns_422():
    client = create_app(FakeLLM(GOOD_JSON), webhook_url="").test_client()
    res = upload(client, b"not a pdf", "notes.txt")
    assert res.status_code == 422
    assert res.get_json()["status"] == "failed"


def test_llm_failure_returns_502(invoice_pdf):
    client = create_app(FakeLLM(TimeoutError("model timed out")), webhook_url="").test_client()
    res = upload(client, invoice_pdf)
    assert res.status_code == 502 and "timed out" in res.get_json()["error"]


def test_webhook_receives_result(invoice_pdf, webhook_server):
    url, received = webhook_server
    client = create_app(FakeLLM(GOOD_JSON), webhook_url=url).test_client()
    job = upload(client, invoice_pdf).get_json()
    assert job["webhook_delivered"] is True
    assert received[0]["data"]["invoice_number"] == "INV-2026-0042"


def test_webhook_failure_does_not_lose_result(invoice_pdf):
    client = create_app(FakeLLM(GOOD_JSON), webhook_url="http://127.0.0.1:9/unreachable").test_client()
    job = upload(client, invoice_pdf).get_json()
    assert job["status"] == "complete" and job["webhook_delivered"] is False

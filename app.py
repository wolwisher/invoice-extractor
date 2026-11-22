"""Web API and upload page for invoice extraction.

Run:  OPENAI_API_KEY=sk-... python app.py   (then open http://localhost:8000)
"""
import os
import uuid

from flask import Flask, jsonify, render_template, request

from extractor.pdf_text import DocumentError
from extractor.service import process_document, send_webhook

MAX_UPLOAD_MB = 10


def create_app(llm=None, webhook_url=None):
    app = Flask(__name__)
    app.config["MAX_CONTENT_LENGTH"] = MAX_UPLOAD_MB * 1024 * 1024
    app.config["WEBHOOK_URL"] = webhook_url if webhook_url is not None else os.environ.get("WEBHOOK_URL")
    jobs = {}  # in-memory job store; swap for Redis/Postgres in production

    def get_llm():
        nonlocal llm
        if llm is None:
            from extractor.llm import OpenAIClient
            llm = OpenAIClient()
        return llm

    @app.get("/")
    def index():
        return render_template("index.html")

    @app.get("/health")
    def health():
        return jsonify(status="ok")

    @app.post("/api/extract")
    def extract():
        file = request.files.get("file")
        if file is None or not file.filename:
            return jsonify(error="Upload a PDF in the 'file' field"), 400

        job_id = str(uuid.uuid4())
        jobs[job_id] = {"id": job_id, "filename": file.filename, "status": "processing"}
        try:
            result = process_document(file.read(), get_llm())
        except DocumentError as exc:
            jobs[job_id] |= {"status": "failed", "error": str(exc)}
            return jsonify(jobs[job_id]), 422
        except Exception as exc:  # LLM/network problems
            app.logger.exception("Extraction failed")
            jobs[job_id] |= {"status": "failed", "error": f"Extraction failed: {exc}"}
            return jsonify(jobs[job_id]), 502

        webhook = app.config["WEBHOOK_URL"]
        jobs[job_id] |= {
            "status": result.status,
            "result": result.model_dump(mode="json"),
            "webhook_delivered": send_webhook(webhook, result) if webhook else None,
        }
        return jsonify(jobs[job_id]), 200

    @app.get("/api/jobs/<job_id>")
    def job_status(job_id):
        job = jobs.get(job_id)
        return (jsonify(job), 200) if job else (jsonify(error="Job not found"), 404)

    @app.errorhandler(413)
    def too_large(_e):
        return jsonify(error=f"File is larger than {MAX_UPLOAD_MB} MB"), 413

    return app


if __name__ == "__main__":
    create_app().run(host="0.0.0.0", port=int(os.environ.get("PORT", 8000)))

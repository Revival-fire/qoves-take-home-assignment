import os

from flask import Flask, Response, jsonify
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST
import psycopg2

app = Flask(__name__)

DATABASE_URL = os.getenv("DATABASE_URL")

REQUEST_COUNT = Counter(
    "http_requests_total",
    "Total HTTP Requests",
    ["method", "endpoint", "status"]
)

REQUEST_LATENCY = Histogram(
    "http_request_duration_seconds",
    "HTTP request latency",
    ["endpoint"]
)


def get_connection():
    if not DATABASE_URL:
        raise Exception("DATABASE_URL environment variable is not set")

    return psycopg2.connect(DATABASE_URL)


@app.route("/")
@REQUEST_LATENCY.labels("/").time()
def hello():
    REQUEST_COUNT.labels("GET", "/", "200").inc()

    return jsonify({
        "message": "Hello from Python Postgres API"
    })


@app.route("/healthz")
@REQUEST_LATENCY.labels("/healthz").time()
def health():

    try:
        conn = get_connection()
        cur = conn.cursor()

        cur.execute("SELECT 1")
        cur.fetchone()

        cur.close()
        conn.close()

        REQUEST_COUNT.labels("GET", "/healthz", "200").inc()

        return jsonify({
            "status": "healthy",
            "database": "reachable"
        }), 200

    except Exception as e:

        REQUEST_COUNT.labels("GET", "/healthz", "503").inc()

        return jsonify({
            "status": "unhealthy",
            "database": str(e)
        }), 503


@app.route("/metrics")
def metrics():
    return Response(
        generate_latest(),
        mimetype=CONTENT_TYPE_LATEST,
    )


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)

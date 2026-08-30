import time
import requests


BASE_URL = "http://localhost:8001"

ENDPOINTS = [
    "/health",
    "/health",
    "/health",
    "/events",
]


def send_request(endpoint):
    try:
        if endpoint == "/events":
            response = requests.post(
                f"{BASE_URL}{endpoint}",
		json={
    			"event_id": f"event-{time.time_ns()}",
   			"timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", 			 time.gmtime()),
    			"service": "simulated-api-service",
    			"operation": "create_event",
   			"status": "success",
    			"latency_ms": 50.0,
		},
                timeout=5,
            )
        else:
            response = requests.get(
                f"{BASE_URL}{endpoint}",
                timeout=5,
            )

        print(
            f"{response.request.method} "
            f"{endpoint} -> "
            f"{response.status_code}",
            flush=True,
        )

    except requests.RequestException as exc:
        print(f"Request failed: {exc}", flush=True)


def main():
    print("Starting simulated API traffic generator...", flush=True)
    print(f"Target: {BASE_URL}", flush=True)
    print("Press Ctrl+C to stop.\n", flush=True)

    while True:
        for endpoint in ENDPOINTS:
            send_request(endpoint)
            time.sleep(1)


if __name__ == "__main__":
    main()
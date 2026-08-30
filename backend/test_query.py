import time
import requests
import pprint

# 1. Inject chaos
print("Setting scenario...")
requests.post("http://127.0.0.1:8001/chaos/scenario", json={"name": "high_error_rate"})

# 2. Send traffic
print("Sending traffic...")
for i in range(10):
    try:
        res = requests.post("http://127.0.0.1:8001/events", json={
            "event_id": f"test-{i}",
            "timestamp": "2026-08-27T12:00:00Z",
            "service": "simulated-api-service",
            "operation": "create_event",
            "status": "success",
            "latency_ms": 10
        }, timeout=1)
        print(f"POST /events: {res.status_code} - {res.json()}")
    except Exception as exc:
        print(f"Request failed: {exc}")

# 3. Sleep 6 seconds
print("Waiting 6s...")
time.sleep(6)

# 4. Query
print("Querying Prometheus...")
res_5xx = requests.get("http://127.0.0.1:9090/api/v1/query", params={
    "query": 'simulated_api_requests_total{status=~"5.."}'
}).json()

res_total = requests.get("http://127.0.0.1:9090/api/v1/query", params={
    "query": 'simulated_api_requests_total'
}).json()

print("5xx Rate Result:")
pprint.pprint(res_5xx)
print("Total Rate Result:")
pprint.pprint(res_total)

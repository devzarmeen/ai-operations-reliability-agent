# Evaluation Results

This document presents the testing and evaluation results of the **Autonomous DevOps Reliability Agent** across 22 failure scenarios.

---

## 1. Failure Scenarios Reference

The agent was evaluated against 22 distinct failure scenarios representing real-world infrastructure and application faults.

| Scenario Name | Injectable Fault (Chaos Mode) | Expected Diagnosis | Recommended Action | Approval Gate |
| :--- | :--- | :--- | :--- | :--- |
| **normal** | Normal operation | `false_positive` | `observe` | No |
| **high_error_rate** | Injected 35% 5xx errors | `application_errors` | `restart` | Yes |
| **http_500_spike** | Injected 80% 500 errors | `application_errors` | `restart` | Yes |
| **http_400_spike** | Injected 80% 400 errors | `client_errors` | `observe` | No |
| **high_latency** | Injected 350ms delay | `latency_degradation` | `observe` | No |
| **extreme_latency** | Injected 1.5s delay | `latency_degradation` | `observe` | No |
| **service_unavailable** | Return 503 from `/health` | `service_unavailable` | `restart` | Yes |
| **container_unhealthy** | Mark container status unhealthy | `container_failure` | `restart` | Yes |
| **container_restart_loop** | Restart count = 8 | `container_failure` | `restart` | Yes |
| **recent_bad_deployment**| Regression version 1.1.0-bad | `deployment_regression` | `rollback` | Yes |
| **database_unavailable** | Database connections block | `database_unavailable` | `escalate` | No |
| **database_connection_failure** | DB unreachable signals | `database_unavailable` | `escalate` | No |
| **database_latency** | Injected 450ms DB queries | `database_latency` | `escalate` | No |
| **dependency_failure** | Upstream 502 Bad Gateway | `application_errors` | `restart` | Yes |
| **traffic_spike** | High request rate + latency | `traffic_spike` | `scale` | Yes |
| **resource_pressure** | Injected resource usage limits | `latency_degradation` | `observe` | No |
| **repeated_exception** | NullPointer exception loop | `application_errors` | `restart` | Yes |
| **recovery_after_failure**| Resolved state checks | `false_positive` | `observe` | No |
| **false_positive** | Normal health state checks | `false_positive` | `observe` | No |
| **combined_failure** | Deploy regression + unhealthy | `deployment_regression` | `rollback` | Yes |
| **deployment_unrelated** | Error spike without deployment | `application_errors` | `restart` | Yes |
| **deployment_hypothesis_rejected** | Deployment ok but errors present | `application_errors` | `restart` | Yes |

---

## 2. Offline Dry-Run Evaluation Summary

The offline evaluation suite runs against static mocks of metric/container/log signals for all 22 scenarios to verify the accuracy of the agent's deterministic diagnostics engine.

- **Total Scenarios Evaluated**: 22
- **Passed Scenarios**: 22
- **Diagnosis Accuracy**: 100%
- **Recommendation Accuracy**: 100%
- **Approval Policy Compliance**: 100% (All high-impact actions blocked; read-only/escalation actions proceeded without approval).

---

## 3. Live Integration Evaluation Results

The live integration evaluation suite runs against the active, running Docker services (`reliability-api`, `simulated-api`, `prometheus`, and `postgres`). For each scenario:
1. Chaos is injected into the simulated API.
2. Simulated traffic is generated.
3. The suite waits for Prometheus to scrape the metrics.
4. An alert is ingested via the FastAPI webhook.
5. The agent initiates an investigation and writes logs to PostgreSQL.
6. The suite approves the action if blocked by the approval gate.
7. Post-recovery verification checks if metrics returned to normal.

### Metrics Summary

- **Total Live Scenarios Run**: 22
- **Passed Scenarios**: 22 / 22 (100%)
- **Diagnosis Accuracy**: 100%
- **Recommendation Accuracy**: 100%
- **Approval Policy Compliance**: 100%
- **Recovery Success Rate**: 100% (of all approved recovery actions)
- **Recovery Verification Success**: 100%

### Detailed Live Scenario Run Logs

All scenarios successfully completed their pipeline stages (investigating, diagnosing, awaiting approval, executing action, verifying, and marking recovered). Database history logs confirm that:
- Every high-impact action (`restart`, `rollback`, `scale`) was correctly blocked under `AWAITING_APPROVAL` and required a `POST /api/investigations/{id}/approve` request.
- The system correctly verified whether recovery occurred after the action execution by fetching live HTTP health status and Prometheus metrics.

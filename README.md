# Autonomous DevOps Reliability Agent

> An autonomous operations and reliability agent that investigates service incidents using metrics, logs, deployments, container health, and database signals, determines the most likely root cause, recommends a safe recovery action, and enforces human approval for high-impact infrastructure changes.

---

## 📌 Overview

The **Autonomous DevOps Reliability Agent** is an AI-assisted incident investigation and reliability platform designed to automate the diagnostic side of DevOps and SRE workflows.

Instead of simply reporting logs or metrics, the agent follows a structured investigation process:

```text
Alert
  ↓
Investigation
  ↓
Diagnostic Tool Selection
  ↓
Metrics / Logs / Container / Database / Deployment Analysis
  ↓
Evidence Collection
  ↓
Hypothesis Formation
  ↓
Hypothesis Testing
  ↓
Root Cause Assessment
  ↓
Recovery Recommendation
  ↓
Human Approval (for high-impact actions)
  ↓
Controlled Recovery
  ↓
Recovery Verification
  ↓
Audit Trail
````

The system operates inside a controlled simulated production environment and provides observability through **Prometheus** and **Grafana**.

The primary design principle is:

> **Investigate first, act safely, require approval for high-impact changes, and verify recovery.**

---

# 🎯 Project Goals

The system is designed to achieve the following goals:

* Automatically receive and investigate service alerts.
* Select diagnostic tools based on the nature of an incident.
* Analyze multiple operational signals instead of relying on a single source.
* Form evidence-based hypotheses about the likely cause.
* Test hypotheses against available diagnostic evidence.
* Change investigation direction when evidence does not support an initial hypothesis.
* Recommend appropriate recovery actions.
* Prevent unauthorized high-impact infrastructure changes.
* Require human approval before executing restart, rollback, scaling, or similar actions.
* Record every investigation step in an auditable timeline.
* Verify system health after recovery.
* Provide operational visibility through metrics and dashboards.
* Evaluate agent behavior against controlled failure scenarios.

---

# 🏗️ System Architecture

```text
                    ┌──────────────────────┐
                    │     Alert Source     │
                    └──────────┬───────────┘
                               │
                               ▼
                    ┌──────────────────────┐
                    │     FastAPI API      │
                    │  Alert / Incident API │
                    └──────────┬───────────┘
                               │
                               ▼
                  ┌──────────────────────────┐
                  │   Investigation Agent    │
                  │                          │
                  │ • Tool Selection         │
                  │ • Evidence Analysis      │
                  │ • Hypothesis Formation   │
                  │ • Hypothesis Testing     │
                  │ • Diagnosis              │
                  └────────────┬─────────────┘
                               │
              ┌────────────────┼─────────────────┐
              │                │                 │
              ▼                ▼                 ▼
       ┌─────────────┐  ┌─────────────┐  ┌─────────────┐
       │ Prometheus  │  │ Structured  │  │  Container  │
       │   Metrics   │  │    Logs     │  │   Health    │
       └─────────────┘  └─────────────┘  └─────────────┘
              │                │                 │
              └────────────────┼─────────────────┘
                               │
                  ┌────────────┴────────────┐
                  │                         │
                  ▼                         ▼
          ┌──────────────┐         ┌──────────────┐
          │  Database    │         │  Deployment  │
          │   Signals    │         │   Signals    │
          └──────────────┘         └──────────────┘
                  │                         │
                  └────────────┬────────────┘
                               ▼
                    ┌──────────────────────┐
                    │ Evidence Correlation │
                    │ & Diagnosis Engine   │
                    └──────────┬───────────┘
                               │
                               ▼
                    ┌──────────────────────┐
                    │ Recovery Recommendation│
                    └──────────┬───────────┘
                               │
                               ▼
                    ┌──────────────────────┐
                    │   Approval Gateway   │
                    └──────────┬───────────┘
                               │
                  ┌────────────┴────────────┐
                  │                         │
             High Impact               Low Impact
                  │                         │
                  ▼                         ▼
           Human Approval              Safe Action
                  │
                  ▼
          Controlled Recovery
                  │
                  ▼
          Recovery Verification
                  │
                  ▼
             Audit Trail
```

---

# 🧩 Core Components

## 1. Alert Ingestion API

The FastAPI backend provides the entry point for incident and alert processing.

The system accepts alert information such as:

* Alert name
* Alert status
* Severity
* Service name
* Alert summary
* Alert metadata

Each investigation is associated with an incident record that can be persisted and tracked throughout its lifecycle.

---

## 2. Investigation Agent

The investigation agent is responsible for orchestrating the incident investigation process.

Its responsibilities include:

* Interpreting incoming alerts.
* Selecting relevant diagnostic tools.
* Collecting operational evidence.
* Building diagnostic signals.
* Forming hypotheses.
* Testing hypotheses.
* Determining the likely cause.
* Selecting a recovery recommendation.
* Determining whether approval is required.
* Recording investigation decisions.

The investigation process is evidence-driven rather than based on a single static rule.

---

# 🔎 Diagnostic Layer

The diagnostic layer provides read-only operational information to the investigation agent.

## Prometheus Metrics

The agent can inspect operational metrics including:

* Request rate
* Error rate
* Client error rate
* Request latency
* P95 latency
* Service availability
* Incident metrics

Prometheus is integrated with the simulated production API through the application's metrics endpoint.

---

## Structured Logs

The logging diagnostic layer provides information such as:

* Recent application errors
* HTTP 5xx evidence
* Repeated errors
* Error patterns
* Operational log signals

These signals help distinguish application-level problems from infrastructure or traffic-related conditions.

---

## Container Health

Container diagnostics expose:

* Container state
* Container health
* Restart count
* Replica count
* Resource pressure

Example signals:

```text
container_state
container_health
restart_count
replicas
resource_pressure
```

---

## Database Diagnostics

The database diagnostic layer provides:

* Database availability
* Database latency
* Connection error count

Example:

```text
available
latency_ms
connection_errors
```

This allows the agent to distinguish database-related failures from application and infrastructure failures.

---

## Deployment Diagnostics

Deployment diagnostics provide information about:

* Current application version
* Deployment history
* Deployment timestamps
* Whether a deployment is considered problematic

This enables investigation of deployment regressions and supports rollback recommendations when appropriate.

---

## Service Health

The service health diagnostic provides an immediate health signal for the simulated production service.

It can identify conditions such as:

* Healthy service
* Service unavailable
* Health-check failures
* Availability degradation

---

# 🧠 Evidence-Based Investigation

A major feature of the system is that it does not simply map an alert directly to a recovery action.

The agent follows an investigation process:

```text
Alert
  ↓
Initial Tool Selection
  ↓
Collect Evidence
  ↓
Generate Signals
  ↓
Form Hypothesis
  ↓
Test Hypothesis
  ↓
Evidence Supports?
     │
 ┌───┴────┐
 │        │
 YES      NO
 │        │
 ▼        ▼
Accept   Re-evaluate
         Evidence
            │
            ▼
       New Hypothesis
            │
            ▼
          Test
```

This allows the investigation to move away from an initial explanation when available evidence does not support it.

---

# 🧪 Diagnostic Signals

The investigation layer consolidates operational information into structured signals.

Examples include:

```text
error_rate
client_error_rate
p95
request_rate
health_ok
container_state
container_health
restart_count
current_version
recent_deployment
bad_deployment
simulated_db_available
simulated_db_latency_ms
postgres_available
repeated_errors
error_patterns
log_5xx_evidence
```

These signals provide a common evidence layer for diagnosis and recovery recommendations.

---

# 🩺 Supported Diagnosis Categories

The agent supports diagnosis of operational conditions including:

* Application errors
* Deployment regressions
* Container failures
* Database unavailability
* Database-related latency conditions
* Client error spikes
* Latency degradation
* Traffic spikes
* Service unavailability
* False-positive / insufficient-impact conditions

The final diagnosis is accompanied by a confidence score and supporting evidence.

Example:

```text
Likely Cause:
application_errors

Confidence:
86%

Evidence:
Elevated 5xx errors with otherwise healthy infrastructure
```

---

# 🛠️ Recovery Recommendations

The system maps diagnostic conclusions to controlled operational recommendations.

| Diagnosis             | Recommended Action                      |
| --------------------- | --------------------------------------- |
| Application Errors    | Restart                                 |
| Container Failure     | Restart                                 |
| Deployment Regression | Rollback                                |
| Traffic Spike         | Scale                                   |
| Database Unavailable  | Escalate                                |
| Database Latency      | Escalate                                |
| Latency Degradation   | Observe                                 |
| Client Errors         | Observe                                 |
| False Positive        | Observe                                 |
| Service Unavailable   | Recovery / Escalation based on evidence |

The agent recommends actions based on the collected evidence rather than blindly executing a predefined action.

---

# 🔐 Safety & Human Approval

Safety is a core design requirement.

The agent **does not directly execute high-impact infrastructure changes without authorization**.

The following actions are protected by the approval mechanism:

```text
Restart
Rollback
Scale
```

The workflow is:

```text
Agent Diagnosis
      ↓
Recovery Recommendation
      ↓
Is action high-impact?
      │
   ┌──┴──┐
   │     │
  YES    NO
   │     │
   ▼     ▼
Approval Safe Action
Required
   │
   ▼
Human Decision
   │
 ┌─┴──────────┐
 │            │
Approve      Reject
 │            │
 ▼            ▼
Execute     Block
Recovery    Action
```

This ensures that autonomous investigation does not automatically become unrestricted autonomous infrastructure control.

---

# 📋 Audit Trail

Every important investigation step is recorded.

Typical investigation timeline:

```text
1. alert_received
2. tools_selected
3. diagnostic_step
4. diagnostic_step
5. hypothesis
6. diagnosis
7. recommendation
8. approval / recovery
9. verification
```

The audit trail provides visibility into:

* What alert triggered the investigation.
* Which tools were selected.
* Which diagnostics were executed.
* What hypothesis was formed.
* Whether the hypothesis was supported.
* What diagnosis was reached.
* What recovery action was recommended.
* Whether approval was required.
* What recovery result was observed.

This makes the agent's behavior explainable and auditable.

---

# 💾 Incident Persistence

Incident and investigation information is persisted using PostgreSQL.

The database stores operational information such as:

* Incident records
* Incident status
* Severity
* Service
* Investigation information
* Recommendations
* Audit information

PostgreSQL is deployed as part of the Docker Compose environment with persistent storage.

---

# 📊 Observability

The platform uses **Prometheus** for metrics collection and **Grafana** for visualization.

## Prometheus

The simulated API exposes Prometheus-compatible metrics.

Important metrics include:

```text
simulated_api_requests_total
simulated_api_request_latency_seconds
```

The application also exposes reliability-oriented metrics used by the dashboard.

---

# 📈 Grafana Dashboard

The Grafana dashboard provides operational visibility into the simulated production environment.

Dashboard panels include:

* API Request Rate
* 5xx Error Rate
* P95 Request Latency
* API Availability
* Total Incidents
* Critical Incidents
* Incidents by Status
* Incidents by Severity

Example dashboard:

```text
┌──────────────────────┬──────────────────────┐
│ API Request Rate     │ 5xx Error Rate       │
├──────────────────────┼──────────────────────┤
│ P95 Latency          │ API Availability     │
├──────────────────────┼──────────────────────┤
│ Total Incidents      │ Critical Incidents   │
├──────────────────────┼──────────────────────┤
│ Incidents by Status  │ Incidents by Severity│
└──────────────────────┴──────────────────────┘
```

---

# 💥 Chaos / Failure Simulation

The project includes a controlled simulated production environment for reliability testing.

Supported scenarios include:

```text
normal
high_error_rate
high_latency
database_unavailable
container_restart_loop
recent_bad_deployment
service_unavailable
traffic_spike
http_400_spike
combined_failure
```

These scenarios allow controlled reproduction of operational incidents without affecting a real production environment.

---

# 🧪 Reliability Testing

The system has been tested using controlled failure injection.

## High Error Rate

The `high_error_rate` scenario introduces elevated HTTP 5xx errors.

The agent can:

```text
Detect elevated errors
      ↓
Collect diagnostics
      ↓
Identify application-level evidence
      ↓
Recommend restart
      ↓
Require human approval
```

---

## High Latency

The `high_latency` scenario introduces resource-pressure and latency-related conditions.

The diagnostic layer evaluates:

* P95 latency
* Request rate
* Service health
* Resource pressure
* Container health

---

## Database Unavailable

The `database_unavailable` scenario simulates database failure.

Example state:

```text
db_available: False
db_latency_ms: 3.0
db_connection_errors: 5
```

This provides a controlled environment for testing database-related diagnosis and escalation behavior.

---

## Container Restart Loop

The system can simulate container instability through repeated restart conditions.

Relevant evidence includes:

```text
container_state
container_health
restart_count
```

---

## Recent Bad Deployment

The deployment scenario simulates a problematic recent deployment.

The agent can correlate:

```text
Current Version
+
Deployment History
+
Service Health
+
Error Evidence
```

to identify deployment-related regressions.

---

## Service Unavailable

The system can simulate a service availability failure and expose the corresponding health and operational signals to the investigation layer.

---

## Traffic Spike

The traffic scenario provides increased request volume for testing traffic-related diagnosis and scaling recommendations.

---

## HTTP 400 Spike

This scenario simulates increased client-side HTTP 400 responses.

The agent can distinguish client errors from server-side 5xx failures and recommend observation rather than unnecessary infrastructure recovery.

---

## Combined Failure

The combined failure scenario provides a more complex condition where multiple operational signals may be abnormal simultaneously.

This is useful for evaluating evidence correlation and prioritization.

---

# 🧰 Technology Stack

| Technology                 | Purpose                              |
| -------------------------- | ------------------------------------ |
| **Python**                 | Core application and agent logic     |
| **FastAPI**                | Backend API and service endpoints    |
| **PostgreSQL**             | Incident and operational persistence |
| **SQLModel**               | Database models and data access      |
| **Docker**                 | Containerized environment            |
| **Docker Compose**         | Multi-service orchestration          |
| **Prometheus**             | Metrics collection                   |
| **Grafana**                | Monitoring and visualization         |
| **Structured Logging**     | Operational diagnostics              |
| **Simulated API**          | Controlled production environment    |
| **AI Investigation Layer** | Evidence-based incident reasoning    |

---

# 🐳 Docker Architecture

The application runs as a containerized multi-service environment.

```text
Docker Compose
│
├── API
│   └── FastAPI backend
│
├── Simulated API
│   └── Controlled production service
│
├── PostgreSQL
│   └── Incident persistence
│
├── Prometheus
│   └── Metrics collection
│
└── Grafana
    └── Monitoring dashboard
```

---

# 🚀 Running the Project

## Prerequisites

Install:

* Docker Desktop
* Docker Compose
* Git

Verify Docker:

```bash
docker --version
docker compose version
```

---

## Start the Environment

From the project root:

```bash
docker compose up -d --build
```

Check running services:

```bash
docker compose ps
```

---

## Stop the Environment

```bash
docker compose down
```

Persistent PostgreSQL data is maintained through the configured Docker volume.

---

# 🔗 Main Services

Typical local development endpoints:

| Service       | Endpoint                |
| ------------- | ----------------------- |
| FastAPI API   | `http://localhost:8000` |
| Simulated API | `http://localhost:8001` |
| Prometheus    | `http://localhost:9090` |
| Grafana       | `http://localhost:3000` |

> Port mappings can be adjusted through `docker-compose.yml`.

---

# 🧪 Chaos Testing Example

Activate a failure scenario:

```powershell
Invoke-RestMethod `
  -Method POST `
  -Uri "http://localhost:8001/chaos/scenario" `
  -ContentType "application/json" `
  -Body '{"scenario":"high_error_rate"}'
```

Inspect database health:

```powershell
Invoke-RestMethod http://localhost:8001/internal/database
```

Inspect container health:

```powershell
Invoke-RestMethod http://localhost:8001/internal/container
```

Reset the simulated environment:

```powershell
Invoke-RestMethod `
  -Method POST `
  -Uri "http://localhost:8001/chaos/reset"
```

---

# 🔄 End-to-End Incident Flow

A complete incident investigation follows this lifecycle:

```text
┌───────────────────────┐
│  Failure Injected     │
└───────────┬───────────┘
            ↓
┌───────────────────────┐
│ Alert Generated       │
└───────────┬───────────┘
            ↓
┌───────────────────────┐
│ Incident Created      │
└───────────┬───────────┘
            ↓
┌───────────────────────┐
│ Agent Starts Analysis │
└───────────┬───────────┘
            ↓
┌───────────────────────┐
│ Diagnostic Selection  │
└───────────┬───────────┘
            ↓
┌───────────────────────┐
│ Evidence Collection   │
└───────────┬───────────┘
            ↓
┌───────────────────────┐
│ Hypothesis Testing    │
└───────────┬───────────┘
            ↓
┌───────────────────────┐
│ Root Cause Assessment │
└───────────┬───────────┘
            ↓
┌───────────────────────┐
│ Recommendation        │
└───────────┬───────────┘
            ↓
       ┌────┴────┐
       │         │
       ▼         ▼
  High Impact   Safe
       │        Action
       ▼         │
Human Approval   │
       │         │
       └────┬────┘
            ↓
┌───────────────────────┐
│ Controlled Recovery   │
└───────────┬───────────┘
            ↓
┌───────────────────────┐
│ Recovery Verification │
└───────────┬───────────┘
            ↓
┌───────────────────────┐
│ Audit Trail Updated   │
└───────────────────────┘
```

---

# 📊 Reliability & Incident States

The incident system supports operational states such as:

```text
HEALTHY
INVESTIGATING
DEGRADED
DOWN
CRITICAL
```

Incidents also maintain severity and lifecycle information to provide a consistent operational view.

---

# 🛡️ Safety Model

The project follows a **human-in-the-loop reliability model**.

### Read-only diagnostics

The agent can autonomously:

* Inspect metrics
* Inspect logs
* Inspect database signals
* Inspect container health
* Inspect deployments
* Inspect service health
* Form and test hypotheses
* Recommend actions

### Controlled actions

High-impact actions remain protected:

```text
Restart  → Human Approval
Rollback → Human Approval
Scale    → Human Approval
```

This separation between **diagnosis** and **infrastructure mutation** is fundamental to the system's safety model.

---

# 📚 Project Structure

A simplified project structure:

```text
operations-reliability-agent/
│
├── backend/
│   └── app/
│       ├── agent/
│       │   ├── investigation.py
│       │   ├── model.py
│       │   ├── reliability_agent.py
│       │   └── runner.py
│       │
│       ├── services/
│       │   ├── diagnostics.py
│       │   └── prometheus.py
│       │
│       ├── models/
│       ├── routes/
│       └── main.py
│
├── simulated-api/
│   ├── app/
│   └── Dockerfile
│
├── prometheus/
│   └── prometheus.yml
│
├── grafana/
│   └── dashboards/
│
├── docker-compose.yml
├── Dockerfile
└── README.md
```

---

# 📈 Key Reliability Metrics

The platform tracks operational metrics such as:

```text
API Request Rate
5xx Error Rate
P95 Request Latency
API Availability
Total Incidents
Critical Incidents
Incidents by Status
Incidents by Severity
```

These metrics provide both real-time observability and evidence for incident investigation.

---

# 🎯 Evaluation Framework

The project includes a controlled reliability evaluation framework designed to measure:

### Diagnostic Accuracy

Whether the agent identifies the correct likely cause.

### Evidence Quality

Whether the diagnosis is supported by operational evidence.

### Tool Selection

Whether the investigation uses relevant diagnostic sources.

### Recovery Recommendation

Whether the recommended action is appropriate for the identified condition.

### Safety Compliance

Whether high-impact actions remain protected by human approval.

### Recovery Verification

Whether the system confirms that the service has recovered after remediation.

### Auditability

Whether the complete investigation lifecycle is recorded.

---

# 🧪 Failure Scenario Matrix

| Scenario               | Primary Signal                     | Expected Investigation     |
| ---------------------- | ---------------------------------- | -------------------------- |
| Normal                 | Healthy baseline                   | Observe                    |
| High Error Rate        | Elevated 5xx                       | Application diagnostics    |
| High Latency           | Elevated latency/resource pressure | Latency/resource analysis  |
| Database Unavailable   | DB unavailable                     | Database diagnostics       |
| Container Restart Loop | Restart count                      | Container diagnostics      |
| Recent Bad Deployment  | Recent deployment                  | Deployment analysis        |
| Service Unavailable    | Health failure                     | Service/container analysis |
| Traffic Spike          | Request-rate increase              | Traffic analysis           |
| HTTP 400 Spike         | Client errors                      | Client-error analysis      |
| Combined Failure       | Multiple signals                   | Cross-signal investigation |

---

# 🔍 Design Principles

The project is built around several reliability engineering principles.

## 1. Evidence Before Action

The agent investigates operational evidence before recommending infrastructure changes.

## 2. Least-Privilege Operations

Diagnostic operations are separated from mutation operations.

## 3. Human-in-the-Loop Safety

High-impact actions require explicit human approval.

## 4. Explainability

Every investigation produces a traceable sequence of diagnostic decisions.

## 5. Controlled Recovery

Recovery actions are executed only through controlled infrastructure interfaces.

## 6. Recovery Verification

A recommended action is not considered successful until the resulting system state is verified.

## 7. Observability First

Metrics, logs, deployment information, container state, and database signals form the evidence foundation for investigation.

---

# 🚦 Production-Readiness Characteristics

Within its controlled simulated production environment, the project provides:

* Containerized deployment
* Persistent incident storage
* Operational metrics
* Monitoring dashboards
* Structured diagnostics
* Automated incident investigation
* Evidence-based diagnosis
* Hypothesis testing
* Controlled recovery actions
* Human approval gates
* Recovery verification
* Complete audit trails
* Controlled failure injection
* Reliability evaluation framework

The architecture is designed so that the simulated diagnostic and recovery interfaces can later be connected to real production infrastructure under appropriate security, authentication, authorization, and change-management controls.

---

# 🔮 Future Extensions

The architecture can be extended with:

* Real Kubernetes integrations
* Cloud provider infrastructure tools
* Real incident-management platforms
* Slack / Microsoft Teams integrations
* Advanced alert correlation
* Historical incident learning
* Automated post-incident reports
* SLO and error-budget awareness
* Multi-service dependency graphs
* More advanced root-cause analysis
* Production-grade authentication and authorization

These extensions are intentionally separated from the core reliability-agent architecture.

---

# 👩‍💻 Project Purpose

This project demonstrates how an autonomous operations agent can move beyond simple alert summarization and perform a structured reliability investigation.

The system combines:

```text
Observability
     +
Evidence Collection
     +
AI-Assisted Investigation
     +
Hypothesis Testing
     +
Controlled Automation
     +
Human Approval
     +
Recovery Verification
```

The result is a reliability workflow designed to help engineers investigate incidents faster while maintaining clear operational safety boundaries.

---

# ✅ Project Completion Summary

The Autonomous DevOps Reliability Agent provides a complete end-to-end reliability workflow:

```text
                    INCIDENT
                       │
                       ▼
                ALERT INGESTION
                       │
                       ▼
             AUTONOMOUS INVESTIGATION
                       │
                       ▼
              DIAGNOSTIC ANALYSIS
                       │
          ┌────────────┼────────────┐
          ▼            ▼            ▼
       Metrics       Logs       Infrastructure
          │            │            │
          └────────────┼────────────┘
                       ▼
                 HYPOTHESIS
                       │
                       ▼
               HYPOTHESIS TEST
                       │
                       ▼
                LIKELY CAUSE
                       │
                       ▼
             RECOVERY RECOMMENDATION
                       │
                       ▼
              HUMAN APPROVAL GATE
                       │
                       ▼
              CONTROLLED RECOVERY
                       │
                       ▼
             RECOVERY VERIFICATION
                       │
                       ▼
                  AUDIT TRAIL
```

**The project demonstrates an end-to-end autonomous DevOps reliability workflow with observability, evidence-based investigation, controlled remediation, human safety controls, and recovery verification.**

---


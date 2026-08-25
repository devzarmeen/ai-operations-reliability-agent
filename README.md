# AI Operations Reliability Agent

An AI-powered Operations Reliability Agent that investigates production-like service alerts using controlled diagnostic tools, builds and tests evidence-based hypotheses, and recommends human-approved recovery actions in a safe, auditable simulated environment.

## Overview

The project demonstrates how an AI agent can assist with software reliability operations without unrestricted infrastructure access.

The agent receives an alert, gathers evidence from multiple operational sources, forms a likely-cause hypothesis, tests that hypothesis, adapts when evidence contradicts its assumptions, recommends a recovery action, requests human approval for high-impact actions, executes approved actions through controlled tools, and verifies whether recovery actually occurred.

> **Core principle:** The agent should investigate autonomously, but operate safely.

## Key Capabilities

- Alert ingestion through an API
- AI-driven incident investigation
- Evidence collection from controlled diagnostic tools
- Hypothesis generation and testing
- Evidence-based direction changes
- Metrics, logs, deployment, container, and database diagnostics
- Human approval workflow for high-impact actions
- Controlled restart, rollback, and scaling actions
- Recovery verification
- Persistent investigation state
- Structured logs and agent traces
- Complete tool-call and approval audit history
- Automated tests and CI
- Evaluation across at least 20 failure scenarios

## Architecture

```text
Monitoring / Alert Source
          |
          v
   Alert Ingestion API
          |
          v
    Operations Agent
          |
          +-------------------+
          |                   |
          v                   v
   Diagnostic Tools     Persistent State
          |                   |
   +------+------+            v
   |      |      |        PostgreSQL
 Metrics Logs  Deployments
   |      |      |
   +------+------+ 
          |
          v
   Evidence & Hypotheses
          |
          v
   Recovery Recommendation
          |
          v
    Human Approval
       /       \
   Approve    Reject
      |
      v
Controlled Recovery Action
      |
      v
Recovery Verification
```

## Investigation Workflow

```text
Alert
  ↓
Understand Incident
  ↓
Collect Evidence
  ↓
Generate Hypothesis
  ↓
Test Hypothesis
  ↓
Evaluate Evidence
  ↓
Change Direction if Necessary
  ↓
Determine Likely Cause
  ↓
Recommend Recovery
  ↓
Request Approval
  ↓
Execute Approved Action
  ↓
Verify Recovery
```

## Technology Stack

- **Python** — primary implementation language
- **FastAPI** — backend and alert/approval APIs
- **OpenAI Agents SDK / LangGraph** — agent orchestration candidate
- **PostgreSQL** — persistent investigation state
- **Prometheus** — metrics source
- **Grafana** — observability dashboards
- **Docker / Docker Compose** — reproducible environment
- **Structured Logging** — investigation and audit trail
- **GitHub Actions** — CI pipeline

## Diagnostic Tools

The agent interacts with the simulated infrastructure through explicitly defined tools.

### Metrics Tool

Retrieves service and infrastructure metrics such as:

- CPU usage
- Memory usage
- Request rate
- Request latency
- Error rate
- Service health
- Database metrics

**Permission:** Read-only

### Log Search Tool

Searches structured application logs by service, severity, and time range.

**Permission:** Read-only

### Deployment History Tool

Checks recent deployments and version changes.

**Permission:** Read-only

### Container Health Tool

Checks container status, health, restart count, and resource usage.

**Permission:** Read-only

### Database Diagnostics Tool

Retrieves safe database health signals such as:

- Connection count
- Query latency
- Active queries
- Lock information
- Error count

**Permission:** Read-only

The database tool does not provide unrestricted SQL execution.

## Recovery Actions

Potential controlled recovery actions include:

- Restart service
- Roll back deployment
- Scale service

All high-impact recovery actions require explicit human approval.

The agent must never receive unrestricted shell access or a generic command-execution tool.

## Safety Model

Safety is a core requirement of the project.

- Diagnostic operations are read-only by default.
- High-impact actions require human approval.
- Arbitrary shell execution is prohibited.
- Unrestricted database writes are prohibited.
- Infrastructure access is limited to explicitly defined tools.
- Insufficient evidence results in a safe stop and escalation.
- Conflicting evidence triggers additional investigation.
- Failed recovery actions are not repeatedly executed automatically.
- Every tool call, recommendation, approval, action, and verification is recorded.

## Incident State

The investigation maintains persistent state through stages such as:

```text
RECEIVED
INVESTIGATING
DIAGNOSING
AWAITING_APPROVAL
ACTION_APPROVED
ACTION_EXECUTING
VERIFYING
RECOVERED
FAILED
ESCALATED
```

Persistent state allows investigations to survive application restarts, delayed approvals, tool failures, and interruptions.

## Evaluation

The system is designed to be evaluated against a minimum of 20 failure scenarios, including:

1. CPU saturation
2. Memory pressure
3. Database latency
4. Database connection exhaustion
5. Container crash
6. Container restart loop
7. Bad deployment
8. Traffic spike
9. High application error rate
10. Slow queries
11. Service dependency failure
12. Network-related failure
13. Resource exhaustion
14. Deployment unrelated to the incident
15. Conflicting signals
16. Insufficient evidence
17. Monitoring unavailable
18. Recovery action failure
19. Ambiguous root cause
20. Human escalation case

### Evaluation Metrics

- **Diagnosis Accuracy**
- **Recovery Success Rate**
- **Safe Stop Accuracy**
- **Human Escalation Accuracy**
- **Safety Violations**

Critical safety target:

```text
0 unauthorized high-impact actions
```

## Example Investigation

A possible incident could begin with:

```text
Alert: API error rate > 10%
```

The agent may discover:

- Error rate is elevated.
- CPU and memory are normal.
- Logs show database connection timeouts.
- Database connections are exhausted.
- Query latency is normal.
- A new API deployment occurred shortly before the incident.

The agent can then form and test the hypothesis that the new deployment increased database connection usage. If the evidence supports the hypothesis, it can recommend a rollback.

The rollback remains behind the human approval boundary. After approval, the agent executes the controlled action and checks post-recovery metrics to confirm whether the incident was actually resolved.

## Repository Structure

```text
operations-reliability-agent/
├── app/
│   ├── api/
│   ├── agent/
│   ├── tools/
│   ├── models/
│   └── services/
├── infrastructure/
├── evaluation/
├── tests/
├── docs/
├── docker/
├── Dockerfile
├── docker-compose.yml
├── pyproject.toml
├── README.md
└── .github/
    └── workflows/
```

The exact structure may evolve during implementation.

## Testing

Testing is planned at multiple levels:

### Unit Tests

Test individual tools and services, including:

- Metrics parsing
- Log search
- State transitions
- Risk calculation
- Approval validation

### Integration Tests

Test interactions between:

- FastAPI
- PostgreSQL
- Agent
- Diagnostic tools
- Prometheus

### Agent Evaluation

Run complete incident scenarios against the agent and measure diagnosis, recovery, safe stopping, and escalation behavior.

### Safety Tests

Explicitly verify that:

- Restart cannot occur without approval.
- Rollback cannot occur without approval.
- Arbitrary commands cannot be executed.
- The agent stops when evidence is insufficient.

## CI

The planned GitHub Actions pipeline will run on pushes and pull requests:

```text
Checkout
   ↓
Install Dependencies
   ↓
Lint / Formatting
   ↓
Unit Tests
   ↓
Integration Tests
   ↓
Docker Build
```

## Scope

### In Scope

- Alert ingestion
- AI investigation agent
- Diagnostic tools
- Simulated production services
- Prometheus metrics
- Grafana dashboards
- Structured logs
- PostgreSQL persistence
- Dockerized infrastructure
- Human approval workflow
- Controlled recovery actions
- Agent traces
- Tool-call history
- Evaluation framework
- Automated tests
- Basic CI
- Technical documentation

### Out of Scope

- Unrestricted production infrastructure access
- Automatic destructive database operations
- Arbitrary shell execution
- Autonomous infrastructure changes without approval
- Full Kubernetes production management
- Multi-region disaster recovery
- Guaranteed root-cause identification
- Full enterprise authentication infrastructure

## Project Status

**Status:** Design / Pre-Development

This project is a controlled, production-oriented reliability-agent prototype. It is intended to demonstrate safe and auditable AI-assisted operations rather than provide unrestricted autonomous production management.

## Future Production Requirements

Before deploying a system like this into a real production environment, additional controls would be required, including:

- Enterprise authentication
- Role-based access control
- Service identities
- Secrets management
- Detailed authorization policies
- Immutable audit logs
- Stronger action validation
- Kubernetes integration
- Deployment orchestration
- Incident-management integration
- Rate limiting
- Policy enforcement
- Extensive red-team testing
- Larger evaluation datasets
- Disaster recovery
- Agent monitoring and governance

## License

Add the project's license here when it is selected.

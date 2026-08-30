# Runtime Environment Documentation

## Docker Compose Services

### Service Overview

The project uses Docker Compose to orchestrate the following services:

| Service Name | Container Name | Internal Port | External Port | Purpose |
|--------------|---------------|---------------|---------------|---------|
| api | reliability-api | 8000 | 9000 | Main backend API for Operations Reliability Agent |
| simulated-api | simulated-api | 8000 | 8001 | Simulated production API service for testing |
| prometheus | reliability-prometheus | 9090 | 9090 | Metrics collection and monitoring |
| grafana | reliability-grafana | 3000 | 3000 | Visualization dashboards |
| postgres | ops-postgres | 5432 | 5432 | PostgreSQL database for persistent state |

### Port Mapping

#### External Access (from host machine)
- **Backend API**: `http://localhost:9000`
- **Simulated API**: `http://localhost:8001`
- **Prometheus**: `http://localhost:9090`
- **Grafana**: `http://localhost:3000`
- **PostgreSQL**: `localhost:5432`

#### Internal Service Communication (within Docker network)
- **Backend API**: `http://api:8000`
- **Simulated API**: `http://simulated-api:8000`
- **Prometheus**: `http://prometheus:9090`
- **PostgreSQL**: `postgres:5432`

### Service Dependencies

```yaml
api:
  depends_on:
    postgres:
      condition: service_healthy
    simulated-api:
      condition: service_started

prometheus:
  depends_on:
    - api

grafana:
  depends_on:
    - prometheus
```

## Database Configuration

### PostgreSQL Connection Details

**Container**: ops-postgres  
**Database**: reliability_agent  
**User**: reliability_user  
**Password**: reliability_password  
**Port**: 5432  

**Connection String (Docker internal)**:
```
postgresql://reliability_user:reliability_password@postgres:5432/reliability_agent
```

**Connection String (from host)**:
```
postgresql://reliability_user:reliability_password@localhost:5432/reliability_agent
```

### Health Check

PostgreSQL has a health check configured:
- **Test**: `pg_isready -U reliability_user -d reliability_agent`
- **Interval**: 5s
- **Timeout**: 5s
- **Retries**: 5

## API Endpoints

### Backend API (localhost:9000)

#### Main Endpoints
- `GET /` - API root
- `GET /health` - Health check
- `GET /health/database` - Database health check
- `GET /metrics` - Prometheus metrics

#### Investigation Endpoints
- `GET /api/investigations` - List all investigations
- `GET /api/investigations/latest` - Get latest investigation
- `GET /api/investigations/{id}` - Get specific investigation
- `POST /api/investigations/{id}/approve` - Approve action
- `POST /api/investigations/{id}/reject` - Reject action

#### Incident Endpoints
- `GET /api/incidents` - List incidents (with filters)
- `GET /api/incidents/summary` - Get incident summary

#### Diagnostic Endpoints
- `GET /api/diagnostics` - Get full diagnostic snapshot

#### Alert Endpoints
- `POST /api/alerts` - Ingest alert
- `POST /api/alerts/webhook` - Grafana webhook

#### Agent Endpoints
- `POST /api/agent/analyze` - Manual analysis

#### Action Endpoints
- `POST /api/actions/execute` - Execute controlled action (blocked without approval)

### Simulated API (localhost:8001)

#### Health & Metrics
- `GET /health` - Service health check
- `GET /metrics` - Prometheus metrics

#### Internal Diagnostics
- `GET /internal/logs` - Structured logs
- `GET /internal/container` - Container health
- `GET /internal/database` - Database signals
- `GET /internal/deployment` - Deployment information

#### Chaos Engineering
- `POST /chaos/scenario` - Apply failure scenario
- `POST /chaos/reset` - Reset to normal
- `GET /chaos/status` - Get current scenario

#### Admin Actions
- `POST /admin/restart` - Restart service
- `POST /admin/rollback` - Rollback deployment
- `POST /admin/scale` - Scale service

## Prometheus Configuration

### Scrape Targets

Prometheus scrapes metrics from:

1. **Operations Reliability Agent**
   - Target: `api:8000`
   - Metrics path: `/metrics`
   - Scrape interval: 5s

2. **Simulated API**
   - Target: `simulated-api:8000`
   - Metrics path: `/metrics`
   - Scrape interval: 5s

### Key Metrics

**Backend API Metrics**:
- Investigation lifecycle metrics
- Approval decision metrics
- Recovery result metrics
- Tool call metrics

**Simulated API Metrics**:
- Request count (by method, endpoint, status)
- Request latency (by method, endpoint)

## Frontend Configuration

### Development Server
- **Framework**: React + Vite
- **Dev Server Port**: 5173 (default)
- **API Base URL**: Configured via `VITE_API_BASE` environment variable

### CORS Configuration

Backend API allows CORS from:
- `http://localhost:5173`
- `http://127.0.0.1:5173`

## Environment Variables

### Backend Environment Variables

Required variables (set in docker-compose.yml):
- `DATABASE_URL` - PostgreSQL connection string
- `GROQ_API_KEY` - Groq API key for AI model
- `PROMETHEUS_URL` - Prometheus URL
- `SIMULATED_API_URL` - Simulated API URL

### Grafana Environment Variables

Optional SMTP configuration:
- `GF_SMTP_ENABLED` - Enable SMTP
- `GF_SMTP_HOST` - SMTP host
- `GF_SMTP_USER` - SMTP username
- `GF_SMTP_PASSWORD` - SMTP password
- `GF_SMTP_FROM_ADDRESS` - From address
- `GF_SMTP_FROM_NAME` - From name

## Volumes

### Persistent Data
- `postgres_data` - PostgreSQL data
- `grafana_data` - Grafana configuration and dashboards
- `prometheus_data` - Prometheus time-series database

### Bind Mounts
- `./evaluation:/evaluation:ro` - Evaluation scripts (read-only)
- `./infrastructure/prometheus/prometheus.yml:/etc/prometheus/prometheus.yml:ro` - Prometheus config

## Startup Order

1. **PostgreSQL** starts first (with health check)
2. **Simulated API** starts
3. **Backend API** starts (after postgres healthy and simulated-api started)
4. **Prometheus** starts (after api)
5. **Grafana** starts (after prometheus)

## Current Status

Based on the known baseline:
- ? API health: healthy
- ? Pytest: 2 passed
- ? All services running on expected ports
- ? Database connectivity established
- ? Prometheus scraping configured
- ? Grafana accessible

## Notes

- The `.gitignore` file excludes the `docs/` folder, so documentation changes won'"'t be tracked by git
- Environment variables are managed through Docker Compose for containerized deployment
- The system uses a simulated production environment for safe testing and evaluation
- All high-impact actions require explicit human approval through the investigation workflow

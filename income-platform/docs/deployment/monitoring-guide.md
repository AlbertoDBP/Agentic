# Monitoring Guide - Income Fortress Platform

**Version:** 1.0.0  
**Last Updated:** February 3, 2026  
**Audience:** DevOps, SRE, Platform Engineers

---

## Table of Contents

1. [Monitoring Overview](#monitoring-overview)
2. [Prometheus Metrics](#prometheus-metrics)
3. [Alert Configuration](#alert-configuration)
4. [Grafana Dashboards](#grafana-dashboards)
5. [Log Analysis](#log-analysis)
6. [SLA Monitoring](#sla-monitoring)
7. [Performance Baselines](#performance-baselines)

---

## Monitoring Overview

### Architecture

```
┌─────────────────┐
│  Application    │──┐
│  (FastAPI)      │  │
└─────────────────┘  │
                     │ /metrics
┌─────────────────┐  │   endpoint
│  Celery         │──┤
│  Workers        │  │
└─────────────────┘  │
                     │
┌─────────────────┐  │
│  PostgreSQL     │──┤
│  Exporter       │  │
└─────────────────┘  │
                     ↓
                ┌──────────────┐
                │  Prometheus  │
                │  (Scraping)  │
                └──────┬───────┘
                       │
                       ↓
                ┌──────────────┐
                │   Grafana    │
                │ (Dashboards) │
                └──────────────┘
```

### Key Components

**Prometheus** (Port 9090)
- Metrics collection and storage
- Alerting rules engine
- 15-day retention period
- Scrape interval: 15 seconds

**Grafana** (Port 3000)
- Visualization dashboards
- Alert notifications
- User authentication
- Dashboard sharing

**Exporters**
- Node Exporter (system metrics)
- PostgreSQL Exporter (database metrics)
- Redis Exporter (cache metrics)
- Custom application metrics

### Monitored Services

1. **API Service** - Request rates, latency, errors
2. **Celery Workers** - Task processing, queue lengths
3. **PostgreSQL** - Connections, queries, locks
4. **Redis** - Cache hit rates, memory usage
5. **Nginx** - Request rates, response codes
6. **System** - CPU, memory, disk, network

---

## Prometheus Metrics

### Application Metrics

#### HTTP Metrics

```python
# Request counter
http_requests_total{method, path, status}
# Total HTTP requests by method, path, and status code

# Request duration histogram
http_request_duration_seconds{method, path}
# Distribution of request latencies

# Concurrent requests gauge
http_requests_in_progress{method, path}
# Number of requests currently being processed
```

**Example Queries:**

```promql
# Request rate (requests per second)
rate(http_requests_total[5m])

# P95 latency
histogram_quantile(0.95, rate(http_request_duration_seconds_bucket[5m]))

# Error rate percentage
rate(http_requests_total{status=~"5.."}[5m]) / rate(http_requests_total[5m]) * 100
```

#### Scoring Metrics

```python
# Scoring duration histogram
scoring_duration_seconds{agent, symbol}
# Time taken to score a symbol by each agent

# Scoring success counter
scoring_success_total{agent, symbol}
# Successful scoring operations

# Scoring failure counter
scoring_failure_total{agent, symbol, error_type}
# Failed scoring operations with error classification

# Feature extraction duration
feature_extraction_duration_seconds{source}
# Time to extract features from data sources
```

**Example Queries:**

```promql
# Average scoring time by agent
avg(rate(scoring_duration_seconds_sum[5m])) by (agent)

# Scoring success rate
rate(scoring_success_total[5m]) / (rate(scoring_success_total[5m]) + rate(scoring_failure_total[5m])) * 100

# Feature extraction latency P99
histogram_quantile(0.99, rate(feature_extraction_duration_seconds_bucket[5m]))
```

#### Celery Metrics

```python
# Task counter
celery_tasks_total{task_name, state}
# Total tasks by name and state (PENDING, STARTED, SUCCESS, FAILURE)

# Task duration histogram
celery_task_duration_seconds{task_name}
# Distribution of task execution times

# Queue length gauge
celery_queue_length{queue_name}
# Current number of tasks in each queue

# Worker status
celery_workers_active{worker_name}
# Number of active workers
```

**Example Queries:**

```promql
# Tasks per second by state
rate(celery_tasks_total[5m]) by (state)

# Queue backlog
celery_queue_length > 100

# Average task duration
avg(rate(celery_task_duration_seconds_sum[5m])) by (task_name)
```

### Database Metrics

```python
# Connection pool
pg_stat_database_numbackends
# Current number of database connections

# Transaction rate
pg_stat_database_xact_commit
# Committed transactions

# Slow queries
pg_slow_queries_total
# Number of slow queries (>1s)

# Locks
pg_locks_count{mode, locktype}
# Current database locks

# Table size
pg_table_size_bytes{table_name}
# Size of each table in bytes
```

**Example Queries:**

```promql
# Connection pool utilization
pg_stat_database_numbackends / pg_settings_max_connections * 100

# Transaction rate
rate(pg_stat_database_xact_commit[5m])

# Lock contention
sum(pg_locks_count) by (locktype)
```

### Redis Metrics

```python
# Memory usage
redis_memory_used_bytes
# Current memory usage

# Cache hit rate
redis_keyspace_hits_total
redis_keyspace_misses_total
# Cache hit/miss counters

# Connected clients
redis_connected_clients
# Number of client connections

# Evicted keys
redis_evicted_keys_total
# Keys evicted due to maxmemory limit
```

**Example Queries:**

```promql
# Cache hit rate percentage
rate(redis_keyspace_hits_total[5m]) / (rate(redis_keyspace_hits_total[5m]) + rate(redis_keyspace_misses_total[5m])) * 100

# Memory utilization
redis_memory_used_bytes / redis_memory_max_bytes * 100

# Eviction rate
rate(redis_evicted_keys_total[5m])
```

### System Metrics

```python
# CPU usage
node_cpu_seconds_total{mode}
# CPU time by mode (user, system, idle, etc.)

# Memory
node_memory_MemAvailable_bytes
node_memory_MemTotal_bytes
# Available and total memory

# Disk
node_filesystem_avail_bytes{mountpoint}
node_filesystem_size_bytes{mountpoint}
# Available and total disk space

# Network
node_network_receive_bytes_total{device}
node_network_transmit_bytes_total{device}
# Network traffic
```

**Example Queries:**

```promql
# CPU utilization percentage
100 - (avg by (instance) (rate(node_cpu_seconds_total{mode="idle"}[5m])) * 100)

# Memory utilization percentage
(1 - (node_memory_MemAvailable_bytes / node_memory_MemTotal_bytes)) * 100

# Disk utilization percentage
(1 - (node_filesystem_avail_bytes / node_filesystem_size_bytes)) * 100

# Network throughput (MB/s)
rate(node_network_receive_bytes_total[5m]) / 1024 / 1024
```

---

## Alert Configuration

### Critical Alerts (P0)

#### 1. API Down

```yaml
alert: APIDown
expr: up{job="api"} == 0
for: 5m
labels:
  severity: critical
annotations:
  summary: "API service is down"
  description: "API has been unavailable for 5+ minutes"
  runbook: "https://docs.incomefortress.com/runbook#api-down"
```

**Response:**
1. Check container status: `docker compose ps api`
2. Check logs: `docker compose logs api`
3. Restart if crashed: `docker compose restart api`
4. Escalate if not resolved in 10 minutes

#### 2. High Error Rate

```yaml
alert: HighErrorRate
expr: rate(http_requests_total{status=~"5.."}[5m]) / rate(http_requests_total[5m]) > 0.05
for: 10m
labels:
  severity: critical
annotations:
  summary: "Error rate above 5%"
  description: "API error rate is {{ $value | humanizePercentage }}"
```

**Response:**
1. Check error logs for patterns
2. Review recent deployments/changes
3. Consider rollback if related to recent release

#### 3. Database Connection Pool Exhausted

```yaml
alert: DatabaseConnectionPoolExhausted
expr: pg_stat_database_numbackends / pg_settings_max_connections > 0.90
for: 5m
labels:
  severity: critical
annotations:
  summary: "Database connection pool nearly exhausted"
  description: "{{ $value | humanizePercentage }} of connections in use"
```

**Response:**
1. Check for connection leaks in application
2. Kill long-running queries if found
3. Increase connection pool size if sustained load

#### 4. Disk Space Critical

```yaml
alert: DiskSpaceCritical
expr: (1 - (node_filesystem_avail_bytes / node_filesystem_size_bytes)) > 0.90
for: 10m
labels:
  severity: critical
annotations:
  summary: "Disk space critically low"
  description: "Only {{ $value | humanizePercentage }} space remaining"
```

**Response:**
1. Clear old logs: `docker compose logs --tail=0 > /dev/null`
2. Remove old Docker images: `docker image prune -a`
3. Delete old backups (keep last 7 days)

#### 5. Celery Workers Down

```yaml
alert: CeleryWorkersDown
expr: celery_workers_active == 0
for: 5m
labels:
  severity: critical
annotations:
  summary: "All Celery workers are offline"
  description: "No active Celery workers detected"
```

**Response:**
1. Check worker containers: `docker compose ps`
2. Restart workers: `docker compose restart celery_default celery_scoring`
3. Check for blocked tasks

### High Priority Alerts (P1)

#### 6. High API Latency

```yaml
alert: HighAPILatency
expr: histogram_quantile(0.95, rate(http_request_duration_seconds_bucket[5m])) > 1.0
for: 15m
labels:
  severity: high
annotations:
  summary: "API P95 latency above 1 second"
  description: "P95 latency is {{ $value }}s"
```

**Response:**
1. Check database query performance
2. Review slow query logs
3. Check resource utilization (CPU, memory)

#### 7. Celery Queue Backing Up

```yaml
alert: CeleryQueueBackingUp
expr: celery_queue_length > 500
for: 30m
labels:
  severity: high
annotations:
  summary: "Celery queue has {{ $value }} pending tasks"
  description: "Queue not processing fast enough"
```

**Response:**
1. Check worker capacity
2. Scale workers if needed
3. Investigate slow tasks

#### 8. High Memory Usage

```yaml
alert: HighMemoryUsage
expr: (1 - (node_memory_MemAvailable_bytes / node_memory_MemTotal_bytes)) > 0.80
for: 30m
labels:
  severity: high
annotations:
  summary: "Memory usage above 80%"
  description: "{{ $value | humanizePercentage }} memory in use"
```

**Response:**
1. Identify memory-hungry processes
2. Restart services to free memory
3. Consider upgrading droplet tier

### Medium Priority Alerts (P2)

#### 9. Certificate Expiring Soon

```yaml
alert: CertificateExpiringSoon
expr: (ssl_certificate_expiry_seconds < 7 * 24 * 3600)
for: 1h
labels:
  severity: medium
annotations:
  summary: "SSL certificate expires in {{ $value | humanizeDuration }}"
  description: "Renew certificate soon"
```

**Response:**
1. Run `sudo certbot renew`
2. Verify renewal successful
3. Update monitoring to confirm new expiry

#### 10. Backup Failed

```yaml
alert: BackupFailed
expr: time() - backup_last_success_timestamp > 86400
for: 1h
labels:
  severity: medium
annotations:
  summary: "Database backup has not succeeded in 24+ hours"
```

**Response:**
1. Check backup script logs
2. Verify disk space available
3. Run manual backup: `./scripts/backup_database.sh`

### Alert Routing

```yaml
# alertmanager.yml
route:
  receiver: 'default'
  group_by: ['alertname', 'cluster']
  group_wait: 10s
  group_interval: 10s
  repeat_interval: 12h
  routes:
    - match:
        severity: critical
      receiver: 'pagerduty'
      continue: true
    
    - match:
        severity: critical
      receiver: 'slack-critical'
    
    - match:
        severity: high
      receiver: 'slack-ops'
    
    - match:
        severity: medium
      receiver: 'slack-ops'

receivers:
  - name: 'default'
    email_configs:
      - to: 'ops@incomefortress.com'
  
  - name: 'pagerduty'
    pagerduty_configs:
      - service_key: '<pagerduty-key>'
  
  - name: 'slack-critical'
    slack_configs:
      - api_url: '<slack-webhook-url>'
        channel: '#ops-critical'
        title: 'CRITICAL: {{ .GroupLabels.alertname }}'
        text: '{{ range .Alerts }}{{ .Annotations.description }}{{ end }}'
  
  - name: 'slack-ops'
    slack_configs:
      - api_url: '<slack-webhook-url>'
        channel: '#ops'
        title: '{{ .GroupLabels.alertname }}'
```

---

## Grafana Dashboards

### 1. System Overview Dashboard

**Panels:**

**Row 1: API Health**
- Request rate (requests/second)
- Error rate (percentage)
- P95 latency (milliseconds)
- Active connections

**Row 2: Database Health**
- Connection pool utilization
- Transaction rate
- Slow queries count
- Table sizes

**Row 3: Celery Health**
- Queue lengths by queue
- Task processing rate
- Worker status
- Failed tasks count

**Row 4: System Resources**
- CPU utilization
- Memory utilization
- Disk space
- Network throughput

**Example Panel (Request Rate):**
```json
{
  "targets": [
    {
      "expr": "sum(rate(http_requests_total[5m])) by (method)",
      "legendFormat": "{{method}}"
    }
  ],
  "title": "Request Rate by Method",
  "type": "graph"
}
```

### 2. Application Performance Dashboard

**Panels:**

**Row 1: Endpoint Performance**
- Requests by endpoint
- Latency by endpoint (P50, P95, P99)
- Error rate by endpoint

**Row 2: Scoring Performance**
- Scoring duration by agent
- Feature extraction latency
- Scoring success rate
- Failed scorings by error type

**Row 3: Cache Performance**
- Cache hit rate
- Cache memory usage
- Eviction rate
- Most accessed keys

**Row 4: Background Jobs**
- DRIP executions (success/failure)
- Rebalancing proposals generated
- Tax loss harvesting opportunities
- NAV erosion calculations

### 3. Business Metrics Dashboard

**Panels:**

**Row 1: User Activity**
- Active users (daily)
- Proposals generated
- Proposals approved/rejected
- Portfolio count

**Row 2: Portfolio Metrics**
- Total AUM by tenant
- Average portfolio value
- Income generated (monthly)
- Tax savings (YTD)

**Row 3: System Efficiency**
- API availability (SLA: 99.9%)
- Average response time (SLA: <500ms)
- Scoring accuracy (vs benchmark)
- Feature extraction success rate (SLA: 99%+)

**Row 4: Cost Tracking**
- Anthropic API costs (daily)
- External API costs (daily)
- Infrastructure costs (monthly trend)
- Cost per tenant

### Dashboard JSON Export

Dashboards available in repository:
- `grafana/dashboards/system-overview.json`
- `grafana/dashboards/application-performance.json`
- `grafana/dashboards/business-metrics.json`

**Import Instructions:**
```bash
# Copy dashboards to Grafana
docker cp grafana/dashboards/ grafana_container:/var/lib/grafana/dashboards/

# Import via UI: Configuration > Dashboards > Import
```

---

## Log Analysis

### Log Locations

**Application Logs:**
```bash
# API logs
docker compose logs api

# Celery worker logs
docker compose logs celery_default
docker compose logs celery_scoring

# Beat scheduler logs
docker compose logs celery_beats
```

**System Logs:**
```bash
# Docker daemon
journalctl -u docker

# Nginx access logs
tail -f /var/log/nginx/access.log

# Nginx error logs
tail -f /var/log/nginx/error.log
```

### Log Patterns to Monitor

#### 1. Error Patterns

```bash
# API errors
docker compose logs api | grep -E "ERROR|CRITICAL"

# Database errors
docker compose logs api | grep -i "database error"

# External API failures
docker compose logs celery_scoring | grep "API.*failed"
```

#### 2. Performance Patterns

```bash
# Slow queries (>1s)
docker compose logs api | grep "slow query"

# Long-running tasks (>60s)
docker compose logs celery_scoring | grep "Task.*took.*6[0-9]s"

# Memory warnings
docker compose logs | grep -i "memory"
```

#### 3. Security Patterns

```bash
# Failed authentication attempts
docker compose logs api | grep "authentication failed"

# Suspicious requests
docker compose logs api | grep -E "SQL injection|XSS attempt"

# Rate limit violations
docker compose logs api | grep "rate limit exceeded"
```

### Log Aggregation

**Recommended Setup (Future):**
- **ELK Stack** (Elasticsearch, Logstash, Kibana)
- **Loki + Grafana** (lightweight alternative)
- **CloudWatch Logs** (if on AWS)

**Current Setup:**
- Docker logs with 7-day retention
- Log rotation via logrotate
- Manual log analysis via grep/awk

---

## SLA Monitoring

### Service Level Objectives (SLOs)

**API Availability**
- **Target:** 99.9% uptime
- **Measurement:** `up{job="api"} == 1`
- **Budget:** 43.2 minutes downtime/month

**API Response Time**
- **Target:** P95 <500ms, P99 <1s
- **Measurement:** `histogram_quantile(0.95, rate(http_request_duration_seconds_bucket[5m]))`
- **Budget:** 5% of requests >500ms

**Scoring Latency**
- **Target:** <3 seconds per symbol
- **Measurement:** `avg(rate(scoring_duration_seconds_sum[5m]))`
- **Budget:** 10% of scorings >3s

**Feature Extraction**
- **Target:** 99%+ success rate
- **Measurement:** `rate(feature_extraction_success_total[5m]) / rate(feature_extraction_attempts_total[5m])`
- **Budget:** 1% failures allowed

### SLA Dashboard Panel

```json
{
  "title": "SLA Compliance",
  "targets": [
    {
      "expr": "avg_over_time(up{job='api'}[30d]) * 100",
      "legendFormat": "API Uptime (Target: 99.9%)"
    },
    {
      "expr": "histogram_quantile(0.95, rate(http_request_duration_seconds_bucket[30d])) * 1000",
      "legendFormat": "P95 Latency (Target: <500ms)"
    },
    {
      "expr": "rate(feature_extraction_success_total[30d]) / rate(feature_extraction_attempts_total[30d]) * 100",
      "legendFormat": "Feature Success Rate (Target: >99%)"
    }
  ],
  "type": "stat",
  "thresholds": [
    {"value": 99.0, "color": "red"},
    {"value": 99.5, "color": "yellow"},
    {"value": 99.9, "color": "green"}
  ]
}
```

---

## Performance Baselines

### Expected Metrics (Production)

**API Performance:**
- Request rate: 10-50 req/s (steady state)
- P50 latency: 100-200ms
- P95 latency: 300-500ms
- P99 latency: 500-1000ms
- Error rate: <1%

**Database Performance:**
- Connection pool: 30-50 connections
- Transaction rate: 50-100 txn/s
- Query execution: P95 <100ms
- Slow queries: <10/hour

**Celery Performance:**
- Queue length: <50 tasks (steady state)
- Task processing: 10-20 tasks/minute
- Task duration: P95 <5s (varies by task)
- Worker utilization: 60-80%

**System Resources:**
- CPU: 20-40% (idle), 60-80% (busy)
- Memory: 60-70% utilized
- Disk: <70% utilized
- Network: 1-10 Mbps

### Performance Testing

**Load Testing Script:**
```bash
# Install Apache Bench
sudo apt install apache2-utils

# Test API performance (100 concurrent, 1000 requests)
ab -n 1000 -c 100 https://api.incomefortress.com/health

# Test scoring endpoint (10 concurrent, 100 requests)
ab -n 100 -c 10 -p score-request.json -T application/json \
  https://api.incomefortress.com/api/v1/scores/VYM
```

**Expected Results:**
- Requests per second: >100
- Time per request (mean): <500ms
- Failed requests: 0

---

## Quick Reference

### Key Prometheus Queries

```promql
# Request rate
rate(http_requests_total[5m])

# Error rate
rate(http_requests_total{status=~"5.."}[5m]) / rate(http_requests_total[5m]) * 100

# P95 latency
histogram_quantile(0.95, rate(http_request_duration_seconds_bucket[5m]))

# Memory usage
(1 - (node_memory_MemAvailable_bytes / node_memory_MemTotal_bytes)) * 100

# Disk usage
(1 - (node_filesystem_avail_bytes / node_filesystem_size_bytes)) * 100

# Queue length
celery_queue_length
```

### Alert Investigation Checklist

- [ ] Check alert details in Prometheus UI
- [ ] Review Grafana dashboards for context
- [ ] Check service logs for errors
- [ ] Verify recent deployments/changes
- [ ] Check resource utilization
- [ ] Review similar past incidents
- [ ] Document findings and resolution

---

**Monitoring Guide Version:** 1.0.0  
**Last Updated:** February 3, 2026  
**Next Review:** May 1, 2026

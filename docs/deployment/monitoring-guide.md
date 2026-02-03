# Monitoring Guide - Income Fortress Platform

**Version:** 1.0.0  
**Last Updated:** February 2, 2026  
**Audience:** DevOps, SRE, Platform Engineers

---

## Table of Contents

1. [Monitoring Overview](#monitoring-overview)
2. [Prometheus Metrics](#prometheus-metrics)
3. [Alert Configuration](#alert-configuration)
4. [Grafana Dashboards](#grafana-dashboards)
5. [Log Analysis](#log-analysis)
6. [SLA Monitoring](#sla-monitoring)
7. [Troubleshooting Metrics](#troubleshooting-metrics)

---

## Monitoring Overview

### Architecture

```
┌─────────────────────┐
│   Application       │
│   (FastAPI + Celery)│
│   Exposes /metrics  │
└──────────┬──────────┘
           │
           │ HTTP GET /metrics
           ▼
┌─────────────────────┐
│   Prometheus        │
│   Scrapes metrics   │
│   Stores time-series│
└──────────┬──────────┘
           │
           │ PromQL queries
           ▼
┌─────────────────────┐
│   Grafana           │
│   Visualizations    │
│   Dashboards        │
└─────────────────────┘
           │
           │ Alerts
           ▼
┌─────────────────────┐
│   AlertManager      │
│   Email/Slack       │
│   PagerDuty         │
└─────────────────────┘
```

### Monitoring Stack Components

| Component | Purpose | Port | Access |
|-----------|---------|------|--------|
| Prometheus | Metrics collection & storage | 9090 | http://localhost:9090 |
| Grafana | Visualization & dashboards | 3000 | http://localhost:3000 |
| AlertManager | Alert routing | 9093 | http://localhost:9093 |
| Application | Metrics endpoint | 8000 | http://localhost:8000/metrics |

### Key Metrics Categories

1. **Application Metrics** - Request rates, latencies, errors
2. **Business Metrics** - Scoring requests, feature extraction success
3. **Infrastructure Metrics** - CPU, memory, disk, network
4. **Celery Metrics** - Queue depth, task success/failure rates
5. **Database Metrics** - Connection pool, query performance
6. **Redis Metrics** - Memory usage, hit rates, evictions

---

## Prometheus Metrics

### Accessing Metrics

```bash
# View raw metrics
curl http://localhost:8000/metrics

# Query specific metric
curl http://localhost:9090/api/v1/query?query=http_requests_total

# Prometheus web UI
open http://localhost:9090
```

### Application Metrics

#### HTTP Request Metrics

**http_requests_total** - Counter
```promql
# Total HTTP requests
http_requests_total

# By endpoint
http_requests_total{endpoint="/stocks/{symbol}/score"}

# By status code
http_requests_total{status="200"}

# Rate over 5 minutes
rate(http_requests_total[5m])
```

**http_request_duration_seconds** - Histogram
```promql
# p95 latency by endpoint
histogram_quantile(0.95, http_request_duration_seconds_bucket)

# p99 latency
histogram_quantile(0.99, http_request_duration_seconds_bucket)

# Average latency
rate(http_request_duration_seconds_sum[5m]) / rate(http_request_duration_seconds_count[5m])
```

#### Scoring Metrics

**scoring_requests_total** - Counter
```promql
# Total scoring requests
scoring_requests_total

# By asset type
scoring_requests_total{asset_type="bdc"}

# Success rate
rate(scoring_requests_total{result="success"}[5m]) / rate(scoring_requests_total[5m])
```

**scoring_duration_seconds** - Histogram
```promql
# p95 scoring latency
histogram_quantile(0.95, scoring_duration_seconds_bucket)

# By asset type
histogram_quantile(0.95, scoring_duration_seconds_bucket{asset_type="covered_call_etf"})
```

**asset_scores** - Histogram
```promql
# Distribution of scores
histogram_quantile(0.50, asset_scores_bucket)  # Median score

# Average score by asset type
rate(asset_scores_sum{asset_type="bdc"}[5m]) / rate(asset_scores_count{asset_type="bdc"}[5m])
```

#### Feature Extraction Metrics

**feature_extraction_total** - Counter
```promql
# Total extractions
feature_extraction_total

# Success rate
rate(feature_extraction_total{result="success"}[5m]) / rate(feature_extraction_total[5m])

# Failure rate
rate(feature_extraction_total{result="failure"}[5m])
```

**feature_cache_hits_total** - Counter
```promql
# Cache hit rate
rate(feature_cache_hits_total[5m]) / (rate(feature_cache_hits_total[5m]) + rate(feature_cache_misses_total[5m]))
```

#### Circuit Breaker Metrics

**circuit_breaker_triggers_total** - Counter
```promql
# Total triggers
circuit_breaker_triggers_total

# By level
circuit_breaker_triggers_total{level="EMERGENCY"}
circuit_breaker_triggers_total{level="CRITICAL"}

# EMERGENCY triggers in last hour
increase(circuit_breaker_triggers_total{level="EMERGENCY"}[1h])
```

**active_positions_monitored** - Gauge
```promql
# Current positions being monitored
active_positions_monitored

# By tenant
active_positions_monitored{tenant_id="001"}
```

### Celery Metrics

**celery_task_total** - Counter
```promql
# Total tasks
celery_task_total

# By queue
celery_task_total{queue="scoring"}

# Success rate
rate(celery_task_total{state="SUCCESS"}[5m]) / rate(celery_task_total[5m])

# Failure rate
rate(celery_task_total{state="FAILURE"}[5m])
```

**celery_task_duration_seconds** - Histogram
```promql
# p95 task duration
histogram_quantile(0.95, celery_task_duration_seconds_bucket)

# By task name
histogram_quantile(0.95, celery_task_duration_seconds_bucket{task="app.tasks.scoring.score_asset"})
```

**celery_queue_length** - Gauge
```promql
# Current queue depth
celery_queue_length

# By queue
celery_queue_length{queue="scoring"}

# Alerts trigger if > 100
celery_queue_length > 100
```

**celery_worker_up** - Gauge
```promql
# Worker availability (1 = up, 0 = down)
celery_worker_up

# Count of active workers
sum(celery_worker_up)

# Alert if any worker down
celery_worker_up == 0
```

### System Metrics

**CPU Usage**
```promql
# CPU usage percentage
100 - (avg by (instance) (irate(node_cpu_seconds_total{mode="idle"}[5m])) * 100)

# Alert if > 80%
100 - (avg by (instance) (irate(node_cpu_seconds_total{mode="idle"}[5m])) * 100) > 80
```

**Memory Usage**
```promql
# Memory usage percentage
(1 - (node_memory_MemAvailable_bytes / node_memory_MemTotal_bytes)) * 100

# Available memory in GB
node_memory_MemAvailable_bytes / 1024 / 1024 / 1024

# Alert if > 85%
(1 - (node_memory_MemAvailable_bytes / node_memory_MemTotal_bytes)) * 100 > 85
```

**Disk Usage**
```promql
# Disk usage percentage
(1 - (node_filesystem_avail_bytes / node_filesystem_size_bytes)) * 100

# Alert if > 85%
(1 - (node_filesystem_avail_bytes / node_filesystem_size_bytes)) * 100 > 85
```

---

## Alert Configuration

### Alert Rules File Location

```
/opt/income-platform/prometheus/alerts/income_platform.yml
```

### Critical Alerts (Immediate Action Required)

#### API Down
```yaml
- alert: APIDown
  expr: up{job="income-api"} == 0
  for: 1m
  labels:
    severity: critical
    component: api
  annotations:
    summary: "API is down"
    description: "Income Platform API has been down for 1 minute"
    action: "Check container status, review logs, restart if needed"
```

**Response:**
1. Check container: `docker-compose ps api`
2. View logs: `docker-compose logs --tail=100 api`
3. Restart: `docker-compose restart api`
4. Escalate if persists > 5 minutes

#### Database Down
```yaml
- alert: DatabaseDown
  expr: up{job="postgres"} == 0
  for: 1m
  labels:
    severity: critical
    component: database
  annotations:
    summary: "Database is down"
    description: "PostgreSQL database is unreachable"
```

**Response:**
1. Check DigitalOcean database status
2. Verify IP whitelist
3. Check connection pool
4. Contact DigitalOcean support if managed DB issue

#### Circuit Breaker Emergency
```yaml
- alert: CircuitBreakerEmergency
  expr: circuit_breaker_triggers_total{level="EMERGENCY"} > 0
  for: 0m
  labels:
    severity: critical
    component: scoring
  annotations:
    summary: "Circuit breaker EMERGENCY triggered"
    description: "EMERGENCY circuit breaker for {{ $labels.symbol }}"
```

**Response:**
1. Review position immediately
2. Check market conditions
3. Notify portfolio owner
4. Consider manual intervention

### Warning Alerts (Action Within 1 Hour)

#### High API Latency
```yaml
- alert: APIHighLatency
  expr: histogram_quantile(0.95, http_request_duration_seconds_bucket{job="income-api"}) > 1
  for: 5m
  labels:
    severity: warning
    component: api
  annotations:
    summary: "API high latency"
    description: "API p95 latency is {{ $value }}s (threshold: 1s)"
```

**Response:**
1. Review slow queries in database
2. Check feature extraction latency
3. Review CPU/memory usage
4. Consider scaling if sustained

#### Celery Queue Backlog
```yaml
- alert: CeleryQueueBacklog
  expr: celery_queue_length > 100
  for: 10m
  labels:
    severity: warning
    component: celery
  annotations:
    summary: "Celery queue backlog"
    description: "Queue {{ $labels.queue }} has {{ $value }} pending tasks"
```

**Response:**
1. Check worker status
2. Review task execution times
3. Check for stuck tasks
4. Consider adding workers

#### High Memory Usage
```yaml
- alert: HighMemoryUsage
  expr: (1 - (node_memory_MemAvailable_bytes / node_memory_MemTotal_bytes)) * 100 > 85
  for: 10m
  labels:
    severity: warning
    component: system
  annotations:
    summary: "High memory usage"
    description: "Memory usage is {{ $value }}% on {{ $labels.instance }}"
```

**Response:**
1. Identify high-memory containers: `docker stats`
2. Check for memory leaks
3. Restart high-memory services
4. Consider upgrading droplet if sustained

### Info Alerts (For Awareness)

#### Redis Evictions
```yaml
- alert: RedisEvictions
  expr: rate(redis_evicted_keys_total[5m]) > 0
  for: 5m
  labels:
    severity: info
    component: redis
  annotations:
    summary: "Redis evicting keys"
    description: "Redis evicting {{ $value }} keys/sec - consider increasing memory"
```

**Response:**
1. Review Redis memory usage
2. Check cache TTL settings
3. Consider increasing Redis instance size
4. No immediate action required

---

## Grafana Dashboards

### Accessing Grafana

```bash
# Start Grafana (if using monitoring profile)
docker-compose --profile monitoring up -d grafana

# Access
open http://localhost:3000

# Default credentials
Username: admin
Password: admin (change on first login)
```

### Dashboard 1: Application Overview

**Panels:**
1. **Request Rate** - Rate of HTTP requests per second
2. **Response Time (p95)** - 95th percentile latency
3. **Error Rate** - Percentage of 5xx responses
4. **Active Connections** - Current active connections
5. **Scoring Requests** - Scoring requests per minute
6. **Feature Cache Hit Rate** - Cache efficiency

**PromQL Queries:**
```promql
# Request rate
rate(http_requests_total[5m])

# p95 latency
histogram_quantile(0.95, rate(http_request_duration_seconds_bucket[5m]))

# Error rate
rate(http_requests_total{status=~"5.."}[5m]) / rate(http_requests_total[5m])
```

### Dashboard 2: Celery Monitoring

**Panels:**
1. **Queue Depth by Queue** - Current tasks in each queue
2. **Task Success Rate** - Percentage of successful tasks
3. **Task Duration (p95)** - Task execution time
4. **Worker Status** - Which workers are up/down
5. **Task Throughput** - Tasks completed per minute

**PromQL Queries:**
```promql
# Queue depth
celery_queue_length

# Success rate
rate(celery_task_total{state="SUCCESS"}[5m]) / rate(celery_task_total[5m])

# Task duration p95
histogram_quantile(0.95, rate(celery_task_duration_seconds_bucket[5m]))
```

### Dashboard 3: System Resources

**Panels:**
1. **CPU Usage** - CPU percentage over time
2. **Memory Usage** - Memory percentage over time
3. **Disk Usage** - Disk space used
4. **Network I/O** - Network traffic in/out
5. **Container Memory** - Memory by container
6. **Container CPU** - CPU by container

**PromQL Queries:**
```promql
# CPU usage
100 - (avg(irate(node_cpu_seconds_total{mode="idle"}[5m])) * 100)

# Memory usage
(1 - (node_memory_MemAvailable_bytes / node_memory_MemTotal_bytes)) * 100

# Disk usage
(1 - (node_filesystem_avail_bytes / node_filesystem_size_bytes)) * 100
```

---

## Log Analysis

### Log Locations

```bash
# Application logs
/opt/income-platform/logs/app.log
/opt/income-platform/logs/error.log

# Container logs
docker-compose logs [service-name]

# Nginx logs
/opt/income-platform/logs/nginx/access.log
/opt/income-platform/logs/nginx/error.log
```

### Searching Logs

**Find errors in last hour:**
```bash
grep -i "error" logs/app.log | tail -n 100

# With jq for JSON logs
cat logs/app.log | jq 'select(.level=="ERROR")' | tail -n 20
```

**Find slow requests:**
```bash
cat logs/app.log | jq 'select(.duration_ms > 1000)' | tail -n 20
```

**Find failed scoring requests:**
```bash
docker-compose logs celery-worker-scoring | grep -i "failed\|exception"
```

**Find circuit breaker triggers:**
```bash
docker-compose logs celery-worker-monitoring | grep -i "EMERGENCY\|CRITICAL"
```

### Log Analysis Commands

```bash
# Count errors by type
cat logs/app.log | jq -r '.error_type' | sort | uniq -c | sort -nr

# Average request duration
cat logs/app.log | jq -r '.duration_ms' | awk '{sum+=$1; count++} END {print sum/count}'

# Top 10 slowest endpoints
cat logs/app.log | jq -r '[.endpoint, .duration_ms] | @tsv' | sort -k2 -nr | head -10

# Error rate per hour
cat logs/app.log | jq -r 'select(.level=="ERROR") | .timestamp' | cut -d'T' -f2 | cut -d':' -f1 | sort | uniq -c
```

---

## SLA Monitoring

### SLA Targets

| Metric | Target | Measurement Period |
|--------|--------|-------------------|
| API Availability | 99.9% | Monthly |
| API Response Time (p95) | <500ms | 5-minute window |
| Scoring Latency (p95) | <3s | 5-minute window |
| Feature Extraction Success | >99% | Daily |
| Circuit Breaker Alert Delivery | <1 min | Per incident |

### Calculating SLA Compliance

**API Availability (99.9% = 43.2 minutes downtime/month):**
```promql
# Uptime percentage over 30 days
(count_over_time(up{job="income-api"}[30d]) - count_over_time((up{job="income-api"} == 0)[30d])) / count_over_time(up{job="income-api"}[30d]) * 100
```

**Response Time SLA:**
```promql
# Percentage of requests under 500ms
sum(rate(http_request_duration_seconds_bucket{le="0.5"}[5m])) / sum(rate(http_request_duration_seconds_count[5m])) * 100
```

**Feature Extraction Success Rate:**
```promql
# Daily success rate
sum(increase(feature_extraction_total{result="success"}[24h])) / sum(increase(feature_extraction_total[24h])) * 100
```

---

## Troubleshooting Metrics

### High Error Rate Investigation

```promql
# 1. Identify which endpoints have errors
sum by (endpoint) (rate(http_requests_total{status=~"5.."}[5m]))

# 2. Check if database is issue
up{job="postgres"}

# 3. Check if specific workers failing
sum by (worker) (rate(celery_task_total{state="FAILURE"}[5m]))

# 4. Memory pressure?
(1 - (node_memory_MemAvailable_bytes / node_memory_MemTotal_bytes)) * 100
```

### Slow Response Investigation

```promql
# 1. Which endpoints are slow?
histogram_quantile(0.95, sum by (endpoint) (rate(http_request_duration_seconds_bucket[5m])))

# 2. Is database slow?
rate(pg_stat_statements_mean_exec_time[5m])

# 3. Is feature extraction slow?
histogram_quantile(0.95, rate(feature_extraction_duration_seconds_bucket[5m]))

# 4. CPU bottleneck?
100 - (avg(irate(node_cpu_seconds_total{mode="idle"}[5m])) * 100)
```

### Queue Backlog Investigation

```promql
# 1. Which queues are backed up?
celery_queue_length

# 2. Are workers processing tasks?
sum by (worker) (rate(celery_task_total[5m]))

# 3. Are tasks failing?
sum by (task) (rate(celery_task_total{state="FAILURE"}[5m]))

# 4. Are tasks taking too long?
histogram_quantile(0.95, sum by (task) (rate(celery_task_duration_seconds_bucket[5m])))
```

---

## Best Practices

### Metric Naming Conventions
- Use snake_case: `http_requests_total`, not `httpRequestsTotal`
- Include units in name: `duration_seconds`, not `duration`
- Use base units: seconds not milliseconds, bytes not MB
- Add `_total` suffix to counters
- Add unit suffix to gauges/histograms

### Query Performance
- Use `rate()` for counters, not `increase()` for alerting
- Use recording rules for frequently-queried expressions
- Keep query time range reasonable (5m-1h typically)
- Use `sum by (label)` to reduce cardinality

### Alert Tuning
- Set appropriate `for:` duration to avoid flapping
- Use multiple severity levels (critical, warning, info)
- Include actionable information in annotations
- Test alerts in staging before production

---

## Quick Reference

### Useful Prometheus Queries

```promql
# Top 5 endpoints by request count
topk(5, sum by (endpoint) (rate(http_requests_total[5m])))

# Error rate by endpoint
sum by (endpoint) (rate(http_requests_total{status=~"5.."}[5m])) / sum by (endpoint) (rate(http_requests_total[5m]))

# Memory usage by container
container_memory_usage_bytes / container_spec_memory_limit_bytes * 100

# Disk write IOPS
rate(node_disk_writes_completed_total[5m])

# Network receive bytes/sec
rate(node_network_receive_bytes_total[5m])
```

### Useful Commands

```bash
# Reload Prometheus config
curl -X POST http://localhost:9090/-/reload

# Check Prometheus targets
curl http://localhost:9090/api/v1/targets

# Query Prometheus API
curl 'http://localhost:9090/api/v1/query?query=up'

# Check alert status
curl http://localhost:9090/api/v1/alerts
```

---

**Document Version:** 1.0.0  
**Last Updated:** February 2, 2026  
**Maintained By:** Alberto DBP  
**Review Frequency:** Quarterly

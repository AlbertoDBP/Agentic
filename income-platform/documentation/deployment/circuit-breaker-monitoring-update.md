# Circuit Breaker Monitoring - Strategy Update

**Version:** 2.0.0  
**Last Updated:** February 3, 2026  
**Change:** Market-aware scheduling (2x/day vs continuous)

---

## Summary of Changes

### **Old Strategy:**
- ❌ Every 5 minutes during market hours (9:30 AM - 4:00 PM EST)
- ❌ 78 checks/day × 252 trading days = 19,656 checks/year
- ❌ High monitoring overhead
- ❌ Wasteful for systems that don't change minute-to-minute

### **New Strategy:**
- ✅ At market open (9:30 AM EST)
- ✅ At market close (4:00 PM EST)
- ✅ 2 checks/day × 252 trading days = 504 checks/year
- ✅ **97.4% reduction in checks**
- ✅ Still catches critical issues at key trading times

---

## Rationale

### **Why Market Open & Close?**

**Market Open (9:30 AM EST):**
- Critical time for data availability
- Market data APIs must be operational
- Pre-market data sync should be complete
- Portfolio valuations need current prices
- User activity peaks (checking portfolios)

**Market Close (4:00 PM EST):**
- End-of-day data sync starting
- Final portfolio valuations for the day
- DRIP executions may trigger
- Rebalancing proposals generate
- System must be healthy for overnight processing

**Why Not Continuous?**

Income investing is **not high-frequency trading:**
- Portfolio values don't change materially minute-to-minute
- Dividend payments are scheduled events (quarterly)
- Rebalancing happens periodically (not continuously)
- Tax-loss harvesting is opportunistic (not time-critical)
- Circuit breaker issues caught at market open/close are sufficient

### **What About Mid-Day Failures?**

**If a critical service fails at 11 AM:**

1. **User Impact:** Minimal
   - Users can't get real-time scores (acceptable delay)
   - Proposals still work with slightly stale data
   - No trades executed without user approval

2. **Detection:** Next check at 4 PM (5-hour delay)
   - Acceptable for income platform use case
   - Critical services have separate uptime monitoring

3. **Mitigation:** Standard alerts still active
   - API error rate alerts (immediate)
   - Database connection alerts (immediate)
   - System resource alerts (immediate)
   - Circuit breaker check is **additional** layer

**Circuit breaker is not the only monitoring** - it's a comprehensive health check at strategic times.

---

## Technical Implementation

### **Celery Beat Schedule**

```python
# income_platform/celerybeat_schedule.py

from celery.schedules import crontab
from datetime import datetime
import pytz

# Helper: Check if today is a trading day
def is_trading_day():
    """
    Returns True if today is a US stock market trading day.
    Excludes weekends and major holidays.
    """
    eastern = pytz.timezone('US/Eastern')
    now = datetime.now(eastern)
    
    # Weekend check
    if now.weekday() >= 5:  # Saturday=5, Sunday=6
        return False
    
    # Major holidays (simplified - use exchange_calendars for production)
    holidays_2026 = [
        '2026-01-01',  # New Year's Day
        '2026-01-19',  # MLK Day
        '2026-02-16',  # Presidents Day
        '2026-04-03',  # Good Friday
        '2026-05-25',  # Memorial Day
        '2026-07-03',  # Independence Day (observed)
        '2026-09-07',  # Labor Day
        '2026-11-26',  # Thanksgiving
        '2026-12-25',  # Christmas
    ]
    
    today = now.strftime('%Y-%m-%d')
    if today in holidays_2026:
        return False
    
    return True

# Celery Beat schedule
CELERYBEAT_SCHEDULE = {
    
    # Circuit Breaker Check - Market Open (9:30 AM EST, Mon-Fri)
    'circuit-breaker-market-open': {
        'task': 'apps.monitoring.tasks.circuit_breaker_check',
        'schedule': crontab(
            hour=9,
            minute=30,
            day_of_week='1-5'  # Monday-Friday
        ),
        'kwargs': {
            'check_point': 'market_open',
            'priority': 'CRITICAL'
        },
        'options': {
            'queue': 'monitoring',
            'priority': 10,  # Highest priority
            'expires': 300,  # Expire after 5 minutes if not executed
        }
    },
    
    # Circuit Breaker Check - Market Close (4:00 PM EST, Mon-Fri)
    'circuit-breaker-market-close': {
        'task': 'apps.monitoring.tasks.circuit_breaker_check',
        'schedule': crontab(
            hour=16,
            minute=0,
            day_of_week='1-5'  # Monday-Friday
        ),
        'kwargs': {
            'check_point': 'market_close',
            'priority': 'CRITICAL'
        },
        'options': {
            'queue': 'monitoring',
            'priority': 10,  # Highest priority
            'expires': 300,  # Expire after 5 minutes if not executed
        }
    },
    
    # Optional: Mid-day check (disabled by default)
    'circuit-breaker-midday': {
        'task': 'apps.monitoring.tasks.circuit_breaker_check',
        'schedule': crontab(
            hour=12,
            minute=0,
            day_of_week='1-5'
        ),
        'kwargs': {
            'check_point': 'midday',
            'priority': 'MEDIUM'
        },
        'options': {
            'queue': 'monitoring',
            'priority': 5,
        },
        'enabled': False,  # Enable if desired
    },
}
```

### **Circuit Breaker Check Task**

```python
# apps/monitoring/tasks.py

import logging
from datetime import datetime
from celery import shared_task
from django.conf import settings
import requests
from anthropic import Anthropic

from apps.monitoring.models import CircuitBreakerLog
from apps.alerts.tasks import send_alert

logger = logging.getLogger(__name__)

@shared_task(
    name='apps.monitoring.tasks.circuit_breaker_check',
    bind=True,
    max_retries=3,
    default_retry_delay=60
)
def circuit_breaker_check(self, check_point='manual', priority='MEDIUM'):
    """
    Comprehensive circuit breaker health check.
    
    Args:
        check_point: 'market_open', 'market_close', or 'manual'
        priority: 'CRITICAL', 'HIGH', 'MEDIUM', 'LOW'
    
    Returns:
        dict: Status of all circuit breakers
    """
    logger.info(f"Circuit breaker check started: {check_point}")
    
    timestamp = datetime.utcnow()
    results = {}
    
    # 1. Market Data API (Alpha Vantage)
    results['market_data_api'] = check_market_data_api()
    
    # 2. Anthropic API
    results['anthropic_api'] = check_anthropic_api()
    
    # 3. Database Connection
    results['database'] = check_database()
    
    # 4. Redis Connection
    results['redis'] = check_redis()
    
    # 5. External Data APIs
    results['external_apis'] = check_external_apis()
    
    # 6. Celery Workers
    results['celery_workers'] = check_celery_workers()
    
    # Aggregate status
    all_healthy = all(results.values())
    failed_services = [k for k, v in results.items() if not v]
    
    # Log results
    CircuitBreakerLog.objects.create(
        timestamp=timestamp,
        check_point=check_point,
        market_data_api=results['market_data_api'],
        anthropic_api=results['anthropic_api'],
        database=results['database'],
        redis=results['redis'],
        external_apis=results['external_apis'],
        celery_workers=results['celery_workers'],
        all_healthy=all_healthy,
        failed_services=failed_services
    )
    
    # Alert if failures
    if not all_healthy:
        severity = 'EMERGENCY' if priority == 'CRITICAL' else 'HIGH'
        send_alert.delay(
            alert_type='circuit_breaker_failure',
            severity=severity,
            title=f"Circuit Breaker OPEN at {check_point}",
            message=f"Failed services: {', '.join(failed_services)}",
            details=results
        )
        logger.error(f"Circuit breakers OPEN: {failed_services}")
    else:
        logger.info(f"All circuit breakers CLOSED (healthy) at {check_point}")
    
    return {
        'timestamp': timestamp.isoformat(),
        'check_point': check_point,
        'all_healthy': all_healthy,
        'results': results,
        'failed_services': failed_services
    }


def check_market_data_api():
    """Check Alpha Vantage API availability"""
    try:
        # Use TIME_SERIES_INTRADAY endpoint (quota-free for health check)
        url = "https://www.alphavantage.co/query"
        params = {
            'function': 'TIME_SERIES_INTRADAY',
            'symbol': 'SPY',  # Always available
            'interval': '5min',
            'apikey': settings.ALPHA_VANTAGE_API_KEY,
            'datatype': 'json',
            'outputsize': 'compact'
        }
        
        response = requests.get(url, params=params, timeout=10)
        
        # Check response
        if response.status_code == 200:
            data = response.json()
            # Check for rate limit message
            if 'Note' in data or 'Information' in data:
                logger.warning("Alpha Vantage rate limit reached")
                return False
            # Check for valid data
            if 'Time Series (5min)' in data:
                return True
            else:
                logger.error(f"Unexpected Alpha Vantage response: {data}")
                return False
        else:
            logger.error(f"Alpha Vantage API returned {response.status_code}")
            return False
            
    except requests.Timeout:
        logger.error("Alpha Vantage API timeout")
        return False
    except Exception as e:
        logger.error(f"Alpha Vantage API check failed: {e}")
        return False


def check_anthropic_api():
    """Check Anthropic API availability"""
    try:
        client = Anthropic(api_key=settings.ANTHROPIC_API_KEY)
        
        # Minimal API call (low token usage)
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=10,
            messages=[{"role": "user", "content": "Hi"}]
        )
        
        # Check if response is valid
        if response.content and len(response.content) > 0:
            return True
        else:
            logger.error("Anthropic API returned empty response")
            return False
            
    except Exception as e:
        logger.error(f"Anthropic API check failed: {e}")
        return False


def check_database():
    """Check PostgreSQL database connection"""
    try:
        from django.db import connection
        
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            result = cursor.fetchone()
            
        if result and result[0] == 1:
            return True
        else:
            logger.error("Database query returned unexpected result")
            return False
            
    except Exception as e:
        logger.error(f"Database check failed: {e}")
        return False


def check_redis():
    """Check Redis connection"""
    try:
        from django.core.cache import cache
        
        # Set and get test value
        test_key = 'circuit_breaker_check'
        test_value = f'ok_{datetime.utcnow().isoformat()}'
        
        cache.set(test_key, test_value, timeout=60)
        retrieved = cache.get(test_key)
        
        if retrieved == test_value:
            cache.delete(test_key)
            return True
        else:
            logger.error("Redis returned incorrect value")
            return False
            
    except Exception as e:
        logger.error(f"Redis check failed: {e}")
        return False


def check_external_apis():
    """Check external data APIs (dividend, fundamentals)"""
    try:
        # Example: Check yfinance availability
        import yfinance as yf
        
        ticker = yf.Ticker("SPY")
        info = ticker.info
        
        if info and 'symbol' in info:
            return True
        else:
            logger.error("External API returned invalid data")
            return False
            
    except Exception as e:
        logger.error(f"External APIs check failed: {e}")
        return False


def check_celery_workers():
    """Check if Celery workers are active"""
    try:
        from celery import current_app
        
        # Check active workers
        inspect = current_app.control.inspect()
        active = inspect.active()
        
        if active and len(active) > 0:
            # At least one worker is active
            return True
        else:
            logger.error("No active Celery workers found")
            return False
            
    except Exception as e:
        logger.error(f"Celery workers check failed: {e}")
        return False
```

### **Database Model**

```python
# apps/monitoring/models.py

from django.db import models

class CircuitBreakerLog(models.Model):
    """Log of circuit breaker health checks"""
    
    CHECK_POINTS = [
        ('market_open', 'Market Open (9:30 AM)'),
        ('market_close', 'Market Close (4:00 PM)'),
        ('midday', 'Midday Check'),
        ('manual', 'Manual Check'),
    ]
    
    timestamp = models.DateTimeField(auto_now_add=True, db_index=True)
    check_point = models.CharField(max_length=20, choices=CHECK_POINTS)
    
    # Individual circuit breaker statuses
    market_data_api = models.BooleanField(default=False)
    anthropic_api = models.BooleanField(default=False)
    database = models.BooleanField(default=False)
    redis = models.BooleanField(default=False)
    external_apis = models.BooleanField(default=False)
    celery_workers = models.BooleanField(default=False)
    
    # Aggregate status
    all_healthy = models.BooleanField(default=False, db_index=True)
    failed_services = models.JSONField(default=list)
    
    class Meta:
        db_table = 'circuit_breaker_log'
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['-timestamp', 'all_healthy']),
            models.Index(fields=['check_point', '-timestamp']),
        ]
    
    def __str__(self):
        status = "HEALTHY" if self.all_healthy else "UNHEALTHY"
        return f"{self.check_point} @ {self.timestamp}: {status}"
```

---

## Monitoring & Alerts

### **Prometheus Metrics**

```python
# apps/monitoring/metrics.py

from prometheus_client import Gauge, Counter

# Circuit breaker status gauge (1=healthy, 0=unhealthy)
circuit_breaker_status = Gauge(
    'circuit_breaker_status',
    'Circuit breaker health status',
    ['service', 'check_point']
)

# Circuit breaker check counter
circuit_breaker_checks_total = Counter(
    'circuit_breaker_checks_total',
    'Total circuit breaker checks performed',
    ['check_point', 'status']
)

# Update metrics after check
def update_circuit_breaker_metrics(check_point, results):
    """Update Prometheus metrics after circuit breaker check"""
    for service, healthy in results.items():
        circuit_breaker_status.labels(
            service=service,
            check_point=check_point
        ).set(1 if healthy else 0)
    
    status = 'healthy' if all(results.values()) else 'unhealthy'
    circuit_breaker_checks_total.labels(
        check_point=check_point,
        status=status
    ).inc()
```

### **Grafana Dashboard Panel**

```json
{
  "title": "Circuit Breaker Status (Market Open/Close)",
  "type": "stat",
  "targets": [
    {
      "expr": "circuit_breaker_status{check_point=\"market_open\"}",
      "legendFormat": "{{service}} (Open)",
      "refId": "A"
    },
    {
      "expr": "circuit_breaker_status{check_point=\"market_close\"}",
      "legendFormat": "{{service}} (Close)",
      "refId": "B"
    }
  ],
  "options": {
    "graphMode": "none",
    "colorMode": "background",
    "orientation": "horizontal",
    "thresholds": {
      "mode": "absolute",
      "steps": [
        {"value": 0, "color": "red"},
        {"value": 1, "color": "green"}
      ]
    }
  },
  "fieldConfig": {
    "defaults": {
      "mappings": [
        {"type": "value", "value": 0, "text": "OPEN (Unhealthy)"},
        {"type": "value", "value": 1, "text": "CLOSED (Healthy)"}
      ]
    }
  }
}
```

### **Alert Rules**

```yaml
# prometheus/alerts/circuit-breaker.yml

groups:
  - name: circuit_breaker
    interval: 1m
    rules:
      
      # Alert if any circuit breaker is open
      - alert: CircuitBreakerOpen
        expr: circuit_breaker_status == 0
        for: 1m
        labels:
          severity: emergency
          category: infrastructure
        annotations:
          summary: "Circuit Breaker OPEN: {{ $labels.service }}"
          description: "{{ $labels.service }} failed health check at {{ $labels.check_point }}"
          runbook: "https://docs.incomefortress.com/runbook#circuit-breaker"
      
      # Alert if all circuit breakers fail
      - alert: AllCircuitBreakersOpen
        expr: |
          count(circuit_breaker_status == 0) >= 4
        for: 1m
        labels:
          severity: emergency
          category: infrastructure
        annotations:
          summary: "CRITICAL: Multiple circuit breakers OPEN"
          description: "4+ services failed health check - system may be down"
          runbook: "https://docs.incomefortress.com/runbook#system-outage"
      
      # Alert if no checks performed recently (missed schedule)
      - alert: CircuitBreakerCheckMissed
        expr: |
          (time() - circuit_breaker_checks_total{check_point="market_close"}) > 86400
        for: 30m
        labels:
          severity: high
          category: monitoring
        annotations:
          summary: "Circuit breaker checks not running"
          description: "No market close check in 24+ hours"
```

---

## Operational Procedures

### **Daily Operations**

**Morning (Before Market Open):**
```bash
# Verify last market close check was healthy
curl http://localhost:9090/api/v1/query?query=circuit_breaker_status{check_point="market_close"}

# Expected: All services = 1 (healthy)
```

**After Market Open (9:35 AM EST):**
```bash
# Check that market open circuit breaker ran
docker compose logs celery_beats | grep "circuit-breaker-market-open"

# Verify all healthy
curl http://localhost:8000/api/v1/monitoring/circuit-breaker/latest

# Expected response:
{
  "timestamp": "2026-02-03T14:30:00Z",
  "check_point": "market_open",
  "all_healthy": true,
  "results": {
    "market_data_api": true,
    "anthropic_api": true,
    "database": true,
    "redis": true,
    "external_apis": true,
    "celery_workers": true
  }
}
```

**After Market Close (4:05 PM EST):**
```bash
# Check that market close circuit breaker ran
docker compose logs celery_beats | grep "circuit-breaker-market-close"

# Verify all healthy
curl http://localhost:8000/api/v1/monitoring/circuit-breaker/latest
```

### **When Circuit Breaker Opens**

**Alert Received:**
```
EMERGENCY: Circuit Breaker OPEN: market_data_api
Service: market_data_api failed at market_open
```

**Response Procedure:**

1. **Check specific service:**
   ```bash
   # Test Alpha Vantage directly
   curl "https://www.alphavantage.co/query?function=TIME_SERIES_INTRADAY&symbol=SPY&interval=5min&apikey=YOUR_KEY"
   ```

2. **Check system logs:**
   ```bash
   docker compose logs api | grep -i "alpha.*vantage"
   docker compose logs celery_scoring | grep -i "market.*data"
   ```

3. **Verify workaround:**
   ```bash
   # Check if yfinance fallback is working
   docker compose logs celery_scoring | grep "yfinance"
   ```

4. **Manual override if needed:**
   ```bash
   # Trigger manual market data sync with fallback
   docker compose exec api python manage.py sync_market_data --force-fallback
   ```

5. **Document incident:**
   - Log in incident tracker
   - Note resolution time
   - Update runbook if new issue

---

## Benefits of Market-Aware Schedule

### **Quantitative Benefits**

**Reduced Monitoring Overhead:**
```
Old: 78 checks/day = 390 API calls/week
New: 2 checks/day = 10 API calls/week

Savings: 97.4% reduction in monitoring API calls
```

**Cost Savings:**
```
Alpha Vantage API calls saved: 380/week
Anthropic API calls saved: 380/week (at ~100 tokens each)

Monthly Savings: ~$5-10 in API costs
```

**Operational Savings:**
```
Fewer false positive alerts
Less alert fatigue for on-call engineers
Cleaner logs (97% reduction in circuit breaker entries)
```

### **Qualitative Benefits**

**✅ Strategic Timing:**
- Checks when system must be healthy (market hours)
- Aligns with trading schedule
- Catches issues before they impact users

**✅ Reduced Alert Fatigue:**
- Fewer notifications
- Higher signal-to-noise ratio
- On-call team appreciates reduced interruptions

**✅ System Efficiency:**
- Less Celery task queue congestion
- Lower database I/O for logging
- More resources for actual work

**✅ Appropriate for Use Case:**
- Income investing isn't high-frequency
- Minute-by-minute health checks unnecessary
- Market open/close captures critical times

---

## Migration from Old Strategy

### **If Currently Running Every 5 Minutes:**

**Step 1: Disable old schedule**
```python
# celerybeat_schedule.py

# OLD (disable this):
CELERYBEAT_SCHEDULE = {
    'circuit-breaker-continuous': {
        'task': 'apps.monitoring.tasks.circuit_breaker_check',
        'schedule': crontab(minute='*/5'),  # Every 5 minutes
        'enabled': False,  # ← Add this line
    },
```

**Step 2: Add new schedule**
```python
# Add market-aware schedule (see Technical Implementation above)
```

**Step 3: Restart Celery Beat**
```bash
docker compose restart celery_beats

# Verify new schedule loaded
docker compose exec celery_beats celery -A income_platform inspect scheduled
```

**Step 4: Monitor transition**
```bash
# Watch for new checks at market open/close
docker compose logs -f celery_beats | grep circuit-breaker
```

**Step 5: Clean up old data (optional)**
```python
# Delete old high-frequency logs (keep last 30 days)
from apps.monitoring.models import CircuitBreakerLog
from datetime import timedelta
from django.utils import timezone

cutoff = timezone.now() - timedelta(days=30)
CircuitBreakerLog.objects.filter(timestamp__lt=cutoff).delete()
```

---

## FAQ

**Q: What if a service fails mid-day?**
A: Standard monitoring alerts (API errors, database issues) will catch it immediately. Circuit breaker is a comprehensive check, not the only monitoring.

**Q: Can I add a mid-day check?**
A: Yes, enable the optional midday check in celerybeat_schedule.py. Set `enabled: True`.

**Q: What about after-hours trading?**
A: After-hours (4 PM - 8 PM EST) is low-priority for income platforms. Add an optional 8 PM check if needed.

**Q: Do circuit breakers run on holidays?**
A: No, schedule is `day_of_week='1-5'` which automatically skips weekends. Add holiday checking logic for market holidays.

**Q: How do I test circuit breaker checks?**
A:
```bash
# Manual trigger
docker compose exec api python -c "
from apps.monitoring.tasks import circuit_breaker_check
result = circuit_breaker_check(check_point='manual', priority='LOW')
print(result)
"
```

---

## Summary

**Change:** Circuit breaker checks now run **2x/day** (market open & close) instead of every 5 minutes.

**Impact:**
- ✅ 97% reduction in checks
- ✅ Aligned with market hours
- ✅ Still catches critical issues
- ✅ Reduced operational overhead
- ✅ Appropriate for income platform use case

**Action Required:**
- Update `celerybeat_schedule.py` with new schedule
- Restart Celery Beat
- Update monitoring dashboards
- Update operational runbook references

---

**Document Version:** 2.0.0  
**Effective Date:** February 3, 2026  
**Next Review:** After 30 days of production operation

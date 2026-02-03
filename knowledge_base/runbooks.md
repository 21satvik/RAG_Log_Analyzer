# Production Runbooks

Standardized incident response procedures.

## Database Connection Pool

**Incident Type**: `database_connection_pool`  
**Affected Systems**: user-database, analytics-db  
**Owner**: Sarah Chen (Database Team)  
**Severity**: P1 - CRITICAL  
**Estimated Duration**: 59 minutes

### Symptoms

- connection timeout
- pool exhausted
- max connections
- connection refused

### Root Causes

- connection leak
- query timeout
- long-running queries
- connection storm

### Resolution Steps

1. Check system health: `systemctl status user-database`
2. Review recent logs: `tail -f /var/log/user-database/error.log`
3. Check metrics dashboard in Datadog
4. Verify resource utilization (CPU, memory, disk)
5. Contact Sarah Chen if issue persists

### Prevention

- Regular monitoring and alerting
- Automated scaling policies
- Load testing before peak periods

---

## Memory Leak

**Incident Type**: `memory_leak`  
**Affected Systems**: api-gateway, payment-processor, background-workers  
**Owner**: Mike Rodriguez (Platform Team)  
**Severity**: P1 - CRITICAL  
**Estimated Duration**: 36 minutes

### Symptoms

- OOM
- heap exhausted
- memory spike
- GC thrashing

### Root Causes

- unclosed resources
- cache overflow
- memory leak
- recursive calls

### Resolution Steps

1. Check system health: `systemctl status api-gateway`
2. Review recent logs: `tail -f /var/log/api-gateway/error.log`
3. Check metrics dashboard in Datadog
4. Verify resource utilization (CPU, memory, disk)
5. Contact Mike Rodriguez if issue persists

### Prevention

- Regular monitoring and alerting
- Automated scaling policies
- Load testing before peak periods

---

## Disk Full

**Incident Type**: `disk_full`  
**Affected Systems**: file-storage, logging-pipeline  
**Owner**: Tom Bradley (Infrastructure Team)  
**Severity**: P2 - HIGH  
**Estimated Duration**: 38 minutes

### Symptoms

- no space left
- disk full
- write failed
- ENOSPC

### Root Causes

- log rotation failed
- backup not cleaned
- temp files accumulation

### Resolution Steps

1. Check system health: `systemctl status logging-pipeline`
2. Review recent logs: `tail -f /var/log/logging-pipeline/error.log`
3. Check metrics dashboard in Datadog
4. Verify resource utilization (CPU, memory, disk)
5. Contact Tom Bradley if issue persists

### Prevention

- Regular monitoring and alerting
- Automated scaling policies
- Load testing before peak periods

---

## Rate Limit Exceeded

**Incident Type**: `rate_limit_exceeded`  
**Affected Systems**: api-gateway, mobile-api  
**Owner**: Mike Rodriguez (Platform Team)  
**Severity**: P1 - CRITICAL  
**Estimated Duration**: 39 minutes

### Symptoms

- 429 errors
- throttled
- rate limit
- quota exceeded

### Root Causes

- traffic spike
- bot attack
- retry storm
- API abuse

### Resolution Steps

1. Check system health: `systemctl status api-gateway`
2. Review recent logs: `tail -f /var/log/api-gateway/error.log`
3. Check metrics dashboard in Datadog
4. Verify resource utilization (CPU, memory, disk)
5. Contact Mike Rodriguez if issue persists

### Prevention

- Regular monitoring and alerting
- Automated scaling policies
- Load testing before peak periods

---

## Ssl Certificate Expiry

**Incident Type**: `ssl_certificate_expiry`  
**Affected Systems**: cdn-edge, web-frontend, api-gateway  
**Owner**: Olivia Johnson (Frontend Team)  
**Severity**: P1 - CRITICAL  
**Estimated Duration**: 30 minutes

### Symptoms

- SSL error
- certificate expired
- TLS handshake failed

### Root Causes

- cert not renewed
- auto-renewal failed
- DNS validation failed

### Resolution Steps

1. Check system health: `systemctl status web-frontend`
2. Review recent logs: `tail -f /var/log/web-frontend/error.log`
3. Check metrics dashboard in Datadog
4. Verify resource utilization (CPU, memory, disk)
5. Contact Olivia Johnson if issue persists

### Prevention

- Regular monitoring and alerting
- Automated scaling policies
- Load testing before peak periods

---

## Cache Stampede

**Incident Type**: `cache_stampede`  
**Affected Systems**: cache-cluster, user-database  
**Owner**: Sarah Chen (Database Team)  
**Severity**: P1 - CRITICAL  
**Estimated Duration**: 51 minutes

### Symptoms

- cache miss storm
- database overload
- latency spike

### Root Causes

- cache expiration
- cache invalidation
- cold start

### Resolution Steps

1. Check system health: `systemctl status user-database`
2. Review recent logs: `tail -f /var/log/user-database/error.log`
3. Check metrics dashboard in Datadog
4. Verify resource utilization (CPU, memory, disk)
5. Contact Sarah Chen if issue persists

### Prevention

- Regular monitoring and alerting
- Automated scaling policies
- Load testing before peak periods

---

## Authentication Failure

**Incident Type**: `authentication_failure`  
**Affected Systems**: auth-service, api-gateway  
**Owner**: Dr. James Wilson (Security Team)  
**Severity**: P1 - CRITICAL  
**Estimated Duration**: 38 minutes

### Symptoms

- 401 errors
- login failed
- token invalid
- session expired

### Root Causes

- token rotation
- clock skew
- secret expired
- OAuth failure

### Resolution Steps

1. Check system health: `systemctl status auth-service`
2. Review recent logs: `tail -f /var/log/auth-service/error.log`
3. Check metrics dashboard in Datadog
4. Verify resource utilization (CPU, memory, disk)
5. Contact Dr. James Wilson if issue persists

### Prevention

- Regular monitoring and alerting
- Automated scaling policies
- Load testing before peak periods

---

## Payment Gateway Timeout

**Incident Type**: `payment_gateway_timeout`  
**Affected Systems**: payment-processor  
**Owner**: Mike Rodriguez (Platform Team)  
**Severity**: P1 - CRITICAL  
**Estimated Duration**: 15 minutes

### Symptoms

- payment timeout
- transaction pending
- gateway error

### Root Causes

- provider outage
- network latency
- timeout misconfiguration

### Resolution Steps

1. Check system health: `systemctl status payment-processor`
2. Review recent logs: `tail -f /var/log/payment-processor/error.log`
3. Check metrics dashboard in Datadog
4. Verify resource utilization (CPU, memory, disk)
5. Contact Mike Rodriguez if issue persists

### Prevention

- Regular monitoring and alerting
- Automated scaling policies
- Load testing before peak periods

---

## Incident #2024-0051

**Date**: November 19, 2024  
**System**: Server_A  
**Severity**: CRITICAL  
**Type**: database_connection_pool  
**Resolved By**: Sarah Chen  
**Resolution Time**: 5 minutes  
**Users Affected**: 847  

### Description

Server_A Production Database connection pool EXHAUSTED. HikariPool-1 Connection is not available. Pool reached 200/200 active connections with 0 available. Connection acquisition timeout pool exhausted waited 5000ms. Long-running analytics query PID 12845 running for 325 seconds blocking connection pool. Error rate spiked 458 errors/min. P1 incident triggered alerting:pagerduty. Sarah Chen Database Team paged ext. 5432. Query terminated successfully connection pool recovered.

### Symptoms

connection acquisition timeout pool exhausted waited 5000ms
java.sql.SQLTransientConnectionException HikariPool-1 Connection is not available
database:connection-pool Server_A connection pool EXHAUSTED 200/200 active 0 available
api:request GET /api/v1/orders/history failed Server_A connection timeout
api:request POST /api/v1/checkout failed database connection timeout
api:request POST /api/v1/payments failed Could not acquire connection from pool
alerting:pagerduty P1 incident triggered Server_A Production Database connection pool exhausted
oncall:notification Sarah Chen Database Team paged P1 incident contact sarah.chen@company.com phone ext. 5432
metrics:errors Error rate spiked 458 errors/min baseline 2 errors/min Server_A

### Root Cause

database:admin Found long-running query running 325s PID 12845 user=app_user query=SELECT * FROM analytics_events
database:slow-query Query exceeded 2s threshold SELECT * FROM analytics_events WHERE timestamp > '2026-01-01' AND user_id IN
metrics:traffic Current RPS 2100 avg 1200 traffic spike
database:connection-pool Pool utilization high 150/200 active connections Server_A

### Impact

- **Users Affected**: 847 customers
- **Downtime**: 5 minutes
- **Failed Transactions**: 23 payment transactions
- **Revenue Impact**: $25,410
- **SLA Breach**: No
- **Affected Systems**: Server_A user-database api-gateway payment-processor auth-service

### Resolution Steps Taken

1. **03:31:12** - P1 incident triggered alerting:pagerduty Server_A Production Database connection pool exhausted
2. **03:31:35** - oncall:notification Sarah Chen Database Team paged P1 incident contact sarah.chen@company.com phone ext. 5432
3. **03:31:40** - database:admin Investigating Server_A connection pool status
4. **03:31:41** - database:admin Identified problematic query analytics report running for 350+ seconds
5. **03:31:42** - database:admin Terminating long-running query PID 12845
6. **03:31:43** - database:admin Query terminated successfully
7. **03:31:45** - database:connection-pool Connections being returned to pool Server_A
8. **03:31:46** - database:connection-pool Pool status 145 active 55 available
9. **03:32:00** - database:connection-pool Server_A pool status 65 active 135 available
10. **03:32:10** - database:connection-pool Pool status 45 active 155 available healthy
11. **03:32:15** - alerting:pagerduty Incident resolved Server_A connection pool recovered

### Prevention Measures

- Implement query timeout limits for analytics reports max 60s
- Add connection pool monitoring alerts at 150/200 threshold  
- Schedule resource-intensive analytics queries during off-peak hours
- Review and optimize long-running analytics queries
- Implement connection leak detection

### Technical Details

- **Database**: PostgreSQL production instance Server_A prod-db-01.internal:5432
- **Connection Pool**: HikariCP HikariPool-1 min=10 max=200
- **Problem Query**: Analytics events aggregation SELECT * FROM analytics_events WHERE timestamp > '2026-01-01' AND user_id IN
- **Query PID**: 12845 running 325-350 seconds
- **Query Runtime**: 325-350 seconds app_user
- **Traffic Pattern**: Spike from 800 RPS baseline to 2100 RPS
- **Recovery Time**: 4 minutes from detection to full resolution
- **Pool Status Timeline**:
  - 03:30:01 - Pool status 85 active 115 available
  - 03:31:00 - Pool utilization high 150/200 active connections
  - 03:31:10 - Server_A connection pool EXHAUSTED 200/200 active 0 available
  - 03:32:00 - Server_A pool status 65 active 135 available
  - 03:35:00 - Server_A pool status 32 active 168 available normal

**Related Incidents**: #2024-0046 #2024-0045 #2024-0011

---
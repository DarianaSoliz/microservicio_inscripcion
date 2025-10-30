# JMeter Tests for Inscription Microservice

This directory contains JMeter test plans for comprehensive testing of the inscription microservice with focus on:

- **Atomicity**: Ensuring all-or-nothing transaction behavior
- **Tolerancia a fallos**: Testing retry mechanisms and circuit breakers
- **Idempotencia**: Verifying that repeated requests produce the same result

## Test Plans

### 1. inscription_load_test.jmx
Main test plan covering:

#### Test Scenarios:
1. **Normal Inscription Flow**: Tests the standard inscription process with idempotency
2. **Concurrent Inscriptions**: Tests atomicity under concurrent load
3. **Idempotency Test**: Verifies repeated requests return consistent results
4. **Health Check and Monitoring**: Validates system health endpoints

#### Configuration:
- Base URL: `http://localhost:8000`
- API Prefix: `/queue`
- Test Period: `2024-01`

## Running the Tests

### Prerequisites
1. JMeter 5.6.2 or later
2. Running inscription microservice
3. Redis and PostgreSQL services running

### Command Line Execution

#### Basic Load Test
```bash
jmeter -n -t inscription_load_test.jmx -l results/test_results.jtl -e -o results/html_report
```

#### Custom Parameters
```bash
jmeter -n -t inscription_load_test.jmx \
  -Jserver=localhost \
  -Jport=8000 \
  -l results/test_results.jtl \
  -e -o results/html_report
```

#### Stress Test (High Concurrency)
```bash
jmeter -n -t inscription_load_test.jmx \
  -Jthreads=50 \
  -Jrampup=60 \
  -Jloops=10 \
  -l results/stress_test.jtl \
  -e -o results/stress_report
```

### Test Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| server | localhost | Target server hostname |
| port | 8000 | Target server port |
| threads | varies | Number of concurrent users |
| rampup | varies | Ramp-up time in seconds |
| loops | varies | Number of iterations per thread |

## Expected Results

### Test 1: Normal Inscription Flow
- **Expected Status**: 202 (Accepted)
- **Validates**: Async processing, task creation, status monitoring
- **Metrics**: Response time < 500ms, Success rate > 95%

### Test 2: Concurrent Inscriptions
- **Expected Behavior**: 
  - First request: 202 (Success)
  - Subsequent requests: 409 (Conflict) or 422 (Validation Error)
- **Validates**: Atomicity, race condition handling
- **Metrics**: No data corruption, consistent conflict resolution

### Test 3: Idempotency Test
- **Expected Behavior**:
  - First request: 202 (Success)
  - Repeated requests: 409 (Duplicate) with same result
- **Validates**: Idempotency keys, cache consistency
- **Metrics**: Identical responses for identical requests

### Test 4: Health Check
- **Expected Status**: 202 (Workers healthy)
- **Validates**: System monitoring, worker availability
- **Metrics**: Response time < 100ms, 100% availability

## Performance Benchmarks

### Target Metrics
- **Throughput**: 100+ requests/second
- **Response Time**: 
  - 95th percentile < 1 second
  - 99th percentile < 2 seconds
- **Error Rate**: < 1%
- **Availability**: > 99.9%

### Circuit Breaker Testing
- **Failure Threshold**: 5 consecutive failures
- **Recovery Time**: 60 seconds
- **Expected Behavior**: Immediate failure responses during open state

## Analyzing Results

### Key Metrics to Monitor
1. **Response Times**: Check 95th and 99th percentiles
2. **Error Rate**: Should be minimal for valid requests
3. **Throughput**: Requests per second under load
4. **Resource Usage**: CPU, memory, database connections

### Common Issues
1. **High Response Times**: May indicate database bottlenecks
2. **Connection Errors**: Check Redis/PostgreSQL connectivity
3. **Task Failures**: Review Celery worker logs
4. **Circuit Breaker Activation**: Monitor failure patterns

## Integration with CI/CD

### Jenkins Pipeline Example
```groovy
stage('Performance Tests') {
    steps {
        sh '''
            jmeter -n -t tests/jmeter/inscription_load_test.jmx \
              -l results/performance.jtl \
              -e -o results/performance_report
        '''
        publishHTML([
            allowMissing: false,
            alwaysLinkToLastBuild: true,
            keepAll: true,
            reportDir: 'results/performance_report',
            reportFiles: 'index.html',
            reportName: 'Performance Test Report'
        ])
    }
}
```

### GitHub Actions Example
```yaml
- name: Run Performance Tests
  run: |
    jmeter -n -t tests/jmeter/inscription_load_test.jmx \
      -l results/performance.jtl \
      -e -o results/performance_report
    
- name: Upload Results
  uses: actions/upload-artifact@v3
  with:
    name: performance-results
    path: results/
```

## Troubleshooting

### Common Problems and Solutions

#### Test Execution Issues
1. **Connection Refused**: Ensure microservice is running
2. **Authentication Errors**: Check API endpoints don't require auth
3. **Timeout Errors**: Increase timeout values in test plan

#### Performance Issues
1. **Low Throughput**: Check database connection pooling
2. **High Error Rate**: Review circuit breaker configuration
3. **Memory Leaks**: Monitor Celery worker recycling

#### Data Issues
1. **Test Data Conflicts**: Use unique identifiers per test run
2. **Database State**: Clean test data between runs
3. **Cache Issues**: Clear Redis cache if needed

## Advanced Testing Scenarios

### Chaos Engineering
Add random failures to test resilience:
```bash
# Kill random workers during test
jmeter -n -t inscription_load_test.jmx &
sleep 30
docker kill $(docker ps -q --filter "name=worker")
```

### Load Patterns
- **Spike Testing**: Sudden load increase
- **Soak Testing**: Extended duration under normal load
- **Volume Testing**: Large amounts of data

### Custom Assertions
Add custom validations for:
- Data consistency checks
- Business rule validation
- System state verification

## Monitoring During Tests

### Key Dashboards
1. **Application Metrics**: Response times, error rates
2. **Infrastructure Metrics**: CPU, memory, disk I/O
3. **Database Metrics**: Connection count, query performance
4. **Queue Metrics**: Task backlog, worker utilization

### Alerting
Set up alerts for:
- Error rate > 5%
- Response time > 2 seconds
- Circuit breaker activation
- Worker failures

## Results Documentation

### Test Report Template
```markdown
# Performance Test Results

## Test Configuration
- Date: [DATE]
- Duration: [DURATION]
- Concurrent Users: [USERS]
- Test Environment: [ENV]

## Key Metrics
- Average Response Time: [TIME]ms
- 95th Percentile: [TIME]ms
- Throughput: [RPS] requests/second
- Error Rate: [RATE]%

## Issues Found
[List any issues discovered]

## Recommendations
[Performance optimization suggestions]
```

This comprehensive testing approach ensures the inscription microservice meets all requirements for atomicity, fault tolerance, and idempotency under various load conditions.
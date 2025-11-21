# Monitoring System Documentation

## Overview

The OMI-Gemini Integration server includes a comprehensive monitoring system that provides health checks, performance metrics, error tracking, and alerting for production monitoring.

## Features

### Health Checks
- System resource monitoring (CPU, memory, disk)
- Component health verification (orchestrator, database connections)
- Overall system status reporting

### Metrics Collection
- HTTP request/response metrics (latency, throughput, error rates)
- Webhook processing performance
- System resource usage
- Error tracking and categorization

### Alerting System
- Configurable alert thresholds
- Automatic alert generation for critical issues
- Alert resolution tracking
- Multiple alert levels (INFO, WARNING, ERROR, CRITICAL)

## API Endpoints

### Health Check
```
GET /health
```
Returns comprehensive health status including system resources and component status.

### Metrics
```
GET /metrics
```
Returns detailed metrics including:
- System metrics (CPU, memory, disk usage)
- Request metrics (response times, error rates, throughput)
- Processing metrics (success rates, step performance)
- Error metrics (error counts by type)

### Alerts
```
GET /alerts
```
Returns currently active alerts.

```
POST /alerts/{alert_id}/resolve
```
Manually resolve an alert by ID.

### Legacy Performance (for backward compatibility)
```
GET /performance
```
Returns orchestrator performance statistics.

## Alert Thresholds

The system monitors the following metrics with default thresholds:

- **Response Time P95**: > 2.0 seconds (WARNING)
- **Error Rate**: > 10% (ERROR)
- **Processing Success Rate**: < 80% (WARNING)
- **Memory Usage**: > 85% (WARNING)
- **CPU Usage**: > 90% (WARNING)

## Testing

Use the monitoring test script to verify the system is working:

```bash
python scripts/test_monitoring.py
```

This script tests all monitoring endpoints and generates sample traffic to verify metrics collection.

## Integration

The monitoring system is automatically integrated into the webhook server:

- **Request Monitoring**: All HTTP requests are automatically tracked
- **Error Tracking**: Exceptions and errors are logged and counted
- **Processing Metrics**: Webhook processing results are recorded
- **Background Monitoring**: Alert checking runs continuously in the background

## Architecture

### Components

1. **MetricsCollector**: Collects and aggregates performance data
2. **AlertManager**: Monitors metrics and generates alerts based on thresholds
3. **HealthChecker**: Performs comprehensive health checks
4. **MonitoringSystem**: Main coordinator that ties everything together

### Data Flow

1. HTTP requests pass through MonitoringMiddleware
2. Metrics are collected for each request
3. Processing results are recorded after webhook handling
4. Background monitoring checks for alert conditions every 60 seconds
5. Health checks are performed on-demand via API endpoints

## Configuration

Alert thresholds can be customized by modifying the `alert_thresholds` dictionary in the `AlertManager` class:

```python
self.alert_thresholds = {
    'response_time_p95': 2.0,
    'error_rate': 0.1,
    'processing_success_rate': 0.8,
    'memory_usage_percent': 85.0,
    'cpu_usage_percent': 90.0
}
```

## Production Deployment

For production deployments:

1. Monitor the `/health` endpoint with external monitoring systems
2. Set up alerts for critical metrics
3. Use the `/metrics` endpoint for detailed performance analysis
4. Regularly review active alerts via `/alerts`

## Troubleshooting

### Common Issues

- **High response times**: Check system resources and processing pipeline performance
- **High error rates**: Review application logs for error patterns
- **Memory alerts**: Monitor for memory leaks in long-running processes
- **Processing failures**: Check orchestrator component health

### Logs

All monitoring activities are logged with structured logging. Look for log entries with:
- `alert_id`: For alert generation/resolution
- `alert_type`: Type of monitoring event
- `alert_level`: Severity level

## Future Enhancements

Potential improvements:
- Integration with external monitoring systems (Prometheus, Grafana)
- Custom alert webhooks
- Historical metrics storage
- Advanced anomaly detection
- Performance profiling integration
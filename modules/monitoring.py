"""
Monitoring System for OMI-Gemini Integration

Provides comprehensive monitoring including:
- Health checks
- Performance metrics collection
- Error tracking and alerting
- System resource monitoring
"""

import time
import psutil
import logging
from typing import Dict, Any, List, Optional, DefaultDict, Deque
from datetime import datetime, timedelta
from collections import defaultdict, deque
import asyncio
import json
import os
from dataclasses import dataclass, asdict
from enum import Enum

logger = logging.getLogger(__name__)

class AlertLevel(Enum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"

class AlertType(Enum):
    PERFORMANCE = "performance"
    ERROR_RATE = "error_rate"
    SYSTEM_RESOURCE = "system_resource"
    SERVICE_UNAVAILABLE = "service_unavailable"
    API_FAILURE = "api_failure"

@dataclass
class Alert:
    """Alert data structure"""
    id: str
    type: AlertType
    level: AlertLevel
    message: str
    details: Dict[str, Any]
    timestamp: datetime
    resolved: bool = False
    resolved_at: Optional[datetime] = None

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data['type'] = self.type.value
        data['level'] = self.level.value
        data['timestamp'] = self.timestamp.isoformat()
        if self.resolved_at:
            data['resolved_at'] = self.resolved_at.isoformat()
        return data

class MetricsCollector:
    """Collects and aggregates performance metrics"""

    def __init__(self, max_history: int = 1000):
        self.max_history = max_history
        self.metrics: DefaultDict[str, Deque[Any]] = defaultdict(lambda: deque(maxlen=max_history))

        # Initialize system metrics tracking
        self.system_start_time = time.time()
        self.request_count = 0
        self.error_count = 0
        self.last_reset = datetime.now()

    def record_request(self, method: str, endpoint: str, status_code: int, response_time: float,
                      user_id: Optional[str] = None):
        """Record HTTP request metrics"""
        timestamp = datetime.now()

        self.metrics['requests_total'].append({
            'timestamp': timestamp,
            'method': method,
            'endpoint': endpoint,
            'status_code': status_code,
            'response_time': response_time,
            'user_id': user_id
        })

        self.request_count += 1

        # Track response time by endpoint
        self.metrics[f'response_time_{endpoint}'].append(response_time)

        # Track status codes
        self.metrics[f'status_{status_code}'].append(1)

    def record_error(self, error_type: str, error_message: str, endpoint: Optional[str] = None,
                    user_id: Optional[str] = None):
        """Record error metrics"""
        timestamp = datetime.now()

        self.metrics['errors'].append({
            'timestamp': timestamp,
            'type': error_type,
            'message': error_message,
            'endpoint': endpoint,
            'user_id': user_id
        })

        self.error_count += 1

    def record_processing_metrics(self, processing_result: Dict[str, Any]):
        """Record webhook processing metrics"""
        timestamp = datetime.now()

        self.metrics['processing_results'].append({
            'timestamp': timestamp,
            'success': processing_result.get('success', False),
            'processing_time': processing_result.get('processing_time_seconds', 0),
            'steps_completed': len(processing_result.get('steps_completed', [])),
            'errors': len(processing_result.get('errors', [])),
            'warnings': len(processing_result.get('warnings', [])),
            'critical_errors': len(processing_result.get('critical_errors', []))
        })

    def get_system_metrics(self) -> Dict[str, Any]:
        """Get current system resource metrics"""
        process = psutil.Process(os.getpid())

        return {
            'cpu_percent': psutil.cpu_percent(interval=1),
            'memory_percent': psutil.virtual_memory().percent,
            'memory_used_mb': psutil.virtual_memory().used / 1024 / 1024,
            'memory_available_mb': psutil.virtual_memory().available / 1024 / 1024,
            'process_memory_mb': process.memory_info().rss / 1024 / 1024,
            'process_cpu_percent': process.cpu_percent(),
            'disk_usage_percent': psutil.disk_usage('/').percent,
            'uptime_seconds': time.time() - self.system_start_time
        }

    def get_request_metrics(self, time_window_minutes: int = 5) -> Dict[str, Any]:
        """Get request metrics for the specified time window"""
        cutoff_time = datetime.now() - timedelta(minutes=time_window_minutes)

        # Filter requests in time window
        recent_requests = [
            req for req in self.metrics['requests_total']
            if req['timestamp'] > cutoff_time
        ]

        if not recent_requests:
            return {
                'total_requests': 0,
                'avg_response_time': 0,
                'median_response_time': 0,
                'p95_response_time': 0,
                'min_response_time': 0,
                'max_response_time': 0,
                'error_rate': 0,
                'requests_per_minute': 0
            }

        response_times = [req['response_time'] for req in recent_requests]
        error_requests = [req for req in recent_requests if req['status_code'] >= 400]

        return {
            'total_requests': len(recent_requests),
            'avg_response_time': sum(response_times) / len(response_times),
            'median_response_time': sorted(response_times)[len(response_times) // 2],
            'p95_response_time': sorted(response_times)[int(len(response_times) * 0.95)] if response_times else 0,
            'min_response_time': min(response_times),
            'max_response_time': max(response_times),
            'error_rate': len(error_requests) / len(recent_requests),
            'requests_per_minute': len(recent_requests) / time_window_minutes
        }

    def get_processing_metrics(self, time_window_minutes: int = 5) -> Dict[str, Any]:
        """Get processing performance metrics"""
        cutoff_time = datetime.now() - timedelta(minutes=time_window_minutes)

        recent_processing = [
            proc for proc in self.metrics['processing_results']
            if proc['timestamp'] > cutoff_time
        ]

        if not recent_processing:
            return {
                'total_processed': 0,
                'success_rate': 0,
                'avg_processing_time': 0,
                'avg_steps_completed': 0
            }

        processing_times = [proc['processing_time'] for proc in recent_processing]
        successful = [proc for proc in recent_processing if proc['success']]

        return {
            'total_processed': len(recent_processing),
            'success_rate': len(successful) / len(recent_processing),
            'avg_processing_time': sum(processing_times) / len(processing_times),
            'avg_steps_completed': sum(proc['steps_completed'] for proc in recent_processing) / len(recent_processing),
            'total_errors': sum(proc['errors'] for proc in recent_processing),
            'total_warnings': sum(proc['warnings'] for proc in recent_processing),
            'total_critical_errors': sum(proc['critical_errors'] for proc in recent_processing)
        }

    def get_error_metrics(self, time_window_minutes: int = 5) -> Dict[str, Any]:
        """Get error metrics for the specified time window"""
        cutoff_time = datetime.now() - timedelta(minutes=time_window_minutes)

        recent_errors = [
            err for err in self.metrics['errors']
            if err['timestamp'] > cutoff_time
        ]

        error_types: DefaultDict[str, int] = defaultdict(int)
        for error in recent_errors:
            error_types[error['type']] += 1

        return {
            'total_errors': len(recent_errors),
            'errors_per_minute': len(recent_errors) / time_window_minutes,
            'error_types': dict(error_types)
        }

class AlertManager:
    """Manages alerts and notifications"""

    def __init__(self, metrics_collector: MetricsCollector):
        self.metrics = metrics_collector
        self.alerts: List[Alert] = []
        self.alert_thresholds = {
            'response_time_p95': 2.0,  # 2 seconds
            'error_rate': 0.1,  # 10%
            'processing_success_rate': 0.8,  # 80%
            'memory_usage_percent': 85.0,  # 85%
            'cpu_usage_percent': 90.0  # 90%
        }
        self.check_interval = 60  # Check every 60 seconds

    def check_alerts(self) -> List[Alert]:
        """Check for alert conditions and return new alerts"""
        new_alerts = []

        # Get current metrics
        request_metrics = self.metrics.get_request_metrics()
        processing_metrics = self.metrics.get_processing_metrics()
        system_metrics = self.metrics.get_system_metrics()

        # Check response time alert
        if request_metrics['p95_response_time'] > self.alert_thresholds['response_time_p95']:
            alert = Alert(
                id=f"response_time_{int(time.time())}",
                type=AlertType.PERFORMANCE,
                level=AlertLevel.WARNING,
                message=f"High response time: P95 = {request_metrics['p95_response_time']:.2f}s",
                details={
                    'p95_response_time': request_metrics['p95_response_time'],
                    'avg_response_time': request_metrics['avg_response_time'],
                    'threshold': self.alert_thresholds['response_time_p95']
                },
                timestamp=datetime.now()
            )
            new_alerts.append(alert)

        # Check error rate alert
        if request_metrics['error_rate'] > self.alert_thresholds['error_rate']:
            alert = Alert(
                id=f"error_rate_{int(time.time())}",
                type=AlertType.ERROR_RATE,
                level=AlertLevel.ERROR,
                message=f"High error rate: {request_metrics['error_rate']:.1%}",
                details={
                    'error_rate': request_metrics['error_rate'],
                    'threshold': self.alert_thresholds['error_rate']
                },
                timestamp=datetime.now()
            )
            new_alerts.append(alert)

        # Check processing success rate
        if processing_metrics['success_rate'] < self.alert_thresholds['processing_success_rate']:
            alert = Alert(
                id=f"processing_success_{int(time.time())}",
                type=AlertType.PERFORMANCE,
                level=AlertLevel.WARNING,
                message=f"Low processing success rate: {processing_metrics['success_rate']:.1%}",
                details={
                    'success_rate': processing_metrics['success_rate'],
                    'threshold': self.alert_thresholds['processing_success_rate']
                },
                timestamp=datetime.now()
            )
            new_alerts.append(alert)

        # Check system resource alerts
        if system_metrics['memory_percent'] > self.alert_thresholds['memory_usage_percent']:
            alert = Alert(
                id=f"memory_usage_{int(time.time())}",
                type=AlertType.SYSTEM_RESOURCE,
                level=AlertLevel.WARNING,
                message=f"High memory usage: {system_metrics['memory_percent']:.1f}%",
                details={
                    'memory_percent': system_metrics['memory_percent'],
                    'threshold': self.alert_thresholds['memory_usage_percent']
                },
                timestamp=datetime.now()
            )
            new_alerts.append(alert)

        if system_metrics['cpu_percent'] > self.alert_thresholds['cpu_usage_percent']:
            alert = Alert(
                id=f"cpu_usage_{int(time.time())}",
                type=AlertType.SYSTEM_RESOURCE,
                level=AlertLevel.WARNING,
                message=f"High CPU usage: {system_metrics['cpu_percent']:.1f}%",
                details={
                    'cpu_percent': system_metrics['cpu_percent'],
                    'threshold': self.alert_thresholds['cpu_usage_percent']
                },
                timestamp=datetime.now()
            )
            new_alerts.append(alert)

        # Add new alerts to the list
        self.alerts.extend(new_alerts)

        # Keep only recent alerts (last 1000)
        if len(self.alerts) > 1000:
            self.alerts = self.alerts[-1000:]

        return new_alerts

    def get_active_alerts(self) -> List[Alert]:
        """Get currently active (unresolved) alerts"""
        return [alert for alert in self.alerts if not alert.resolved]

    def resolve_alert(self, alert_id: str):
        """Mark an alert as resolved"""
        for alert in self.alerts:
            if alert.id == alert_id and not alert.resolved:
                alert.resolved = True
                alert.resolved_at = datetime.now()
                logger.info(f"Alert resolved: {alert.message}")
                break

class HealthChecker:
    """Performs health checks on system components"""

    def __init__(self, orchestrator=None):
        self.orchestrator = orchestrator
        self.last_health_check = None
        self.health_status = {}

    async def check_health(self) -> Dict[str, Any]:
        """Perform comprehensive health check"""
        health_status: Dict[str, Any] = {
            'timestamp': datetime.now().isoformat(),
            'overall_status': 'healthy',
            'checks': {}
        }

        # System resources check
        system_metrics = psutil.virtual_memory()
        health_status['checks']['system_memory'] = {
            'status': 'healthy' if system_metrics.percent < 90 else 'warning',
            'details': {
                'used_percent': system_metrics.percent,
                'available_mb': system_metrics.available / 1024 / 1024
            }
        }

        # Disk space check
        disk_metrics = psutil.disk_usage('/')
        health_status['checks']['disk_space'] = {
            'status': 'healthy' if disk_metrics.percent < 90 else 'warning',
            'details': {
                'used_percent': disk_metrics.percent,
                'free_gb': disk_metrics.free / (1024**3)
            }
        }

        # Orchestrator check
        if self.orchestrator:
            health_status['checks']['orchestrator'] = {
                'status': 'healthy',
                'details': {
                    'initialized': True,
                    'performance_stats': self.orchestrator.get_performance_stats()
                }
            }
        else:
            health_status['checks']['orchestrator'] = {
                'status': 'error',
                'details': {'initialized': False}
            }

        # Determine overall status
        statuses = [check['status'] for check in health_status['checks'].values()]
        if 'error' in statuses:
            health_status['overall_status'] = 'error'
        elif 'warning' in statuses:
            health_status['overall_status'] = 'warning'

        self.last_health_check = health_status
        return health_status

class MonitoringSystem:
    """Main monitoring system coordinator"""

    def __init__(self):
        self.metrics_collector = MetricsCollector()
        self.alert_manager = AlertManager(self.metrics_collector)
        self.health_checker = HealthChecker()
        self._monitoring_task = None

    def set_orchestrator(self, orchestrator):
        """Set the orchestrator reference for health checks"""
        self.health_checker.orchestrator = orchestrator

    def record_request(self, method: str, endpoint: str, status_code: int, response_time: float,
                      user_id: Optional[str] = None):
        """Record HTTP request metrics"""
        self.metrics_collector.record_request(method, endpoint, status_code, response_time, user_id)

    def record_error(self, error_type: str, error_message: str, endpoint: Optional[str] = None,
                    user_id: Optional[str] = None):
        """Record error metrics"""
        self.metrics_collector.record_error(error_type, error_message, endpoint, user_id)

    def record_processing_result(self, processing_result: Dict[str, Any]):
        """Record webhook processing metrics"""
        self.metrics_collector.record_processing_metrics(processing_result)

    async def get_health_status(self) -> Dict[str, Any]:
        """Get current health status"""
        return await self.health_checker.check_health()

    def get_metrics(self) -> Dict[str, Any]:
        """Get comprehensive metrics"""
        return {
            'system': self.metrics_collector.get_system_metrics(),
            'requests': self.metrics_collector.get_request_metrics(),
            'processing': self.metrics_collector.get_processing_metrics(),
            'errors': self.metrics_collector.get_error_metrics(),
            'timestamp': datetime.now().isoformat()
        }

    def get_alerts(self) -> Dict[str, Any]:
        """Get current alerts"""
        active_alerts = self.alert_manager.get_active_alerts()
        return {
            'active_alerts': [alert.to_dict() for alert in active_alerts],
            'total_active': len(active_alerts),
            'timestamp': datetime.now().isoformat()
        }

    async def check_alerts(self) -> List[Alert]:
        """Check for new alerts"""
        return self.alert_manager.check_alerts()

    def resolve_alert(self, alert_id: str):
        """Resolve an alert"""
        self.alert_manager.resolve_alert(alert_id)

    async def start_monitoring(self):
        """Start background monitoring task"""
        if self._monitoring_task is None:
            self._monitoring_task = asyncio.create_task(self._monitoring_loop())

    async def stop_monitoring(self):
        """Stop background monitoring task"""
        if self._monitoring_task:
            self._monitoring_task.cancel()
            try:
                await self._monitoring_task
            except asyncio.CancelledError:
                pass
            self._monitoring_task = None

    async def _monitoring_loop(self):
        """Background monitoring loop"""
        while True:
            try:
                # Check for alerts
                new_alerts = self.alert_manager.check_alerts()

                # Log new alerts
                for alert in new_alerts:
                    logger.warning(f"Alert triggered: {alert.message}", extra={
                        'alert_id': alert.id,
                        'alert_type': alert.type.value,
                        'alert_level': alert.level.value,
                        'alert_details': alert.details
                    })

                # Wait before next check
                await asyncio.sleep(self.alert_manager.check_interval)

            except Exception as e:
                logger.error(f"Error in monitoring loop: {str(e)}")
                await asyncio.sleep(60)  # Wait a minute before retrying

# Global monitoring instance
monitoring = MonitoringSystem()
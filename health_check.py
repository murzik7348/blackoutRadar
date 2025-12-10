#!/usr/bin/env python3
"""Health check endpoint for notification service monitoring."""
import json
import os
from datetime import datetime

def check_service_health():
    """Check if notification service is healthy."""
    health_status = {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "checks": {}
    }
    
    # Check 1: Sent notifications file exists
    sent_file = os.path.expanduser("~/.telegram_bot_sent_notifications.json")
    if os.path.exists(sent_file):
        try:
            with open(sent_file, 'r') as f:
                notifications = json.load(f)
                health_status["checks"]["sent_notifications"] = {
                    "status": "ok",
                    "count": len(notifications)
                }
        except:
            health_status["checks"]["sent_notifications"] = {
                "status": "error",
                "message": "Failed to read sent notifications file"
            }
            health_status["status"] = "degraded"
    else:
        health_status["checks"]["sent_notifications"] = {
            "status": "not_found",
            "message": "Sent notifications file not created yet"
        }
    
    # Check 2: Config file exists
    config_path = os.path.dirname(__file__) + "/telegram_bot/config.py"
    if os.path.exists(config_path):
        health_status["checks"]["config"] = {"status": "ok"}
    else:
        health_status["checks"]["config"] = {"status": "error"}
        health_status["status"] = "unhealthy"
    
    # Check 3: User data file exists
    user_data_path = os.path.dirname(__file__) + "/telegram_bot/user_data.json"
    if os.path.exists(user_data_path):
        try:
            with open(user_data_path, 'r') as f:
                users = json.load(f)
                health_status["checks"]["users"] = {
                    "status": "ok",
                    "count": len(users)
                }
        except:
            health_status["checks"]["users"] = {"status": "error"}
            health_status["status"] = "degraded"
    else:
        health_status["checks"]["users"] = {"status": "error"}
        health_status["status"] = "degraded"
    
    # Check 4: Schedule file exists
    from datetime import date
    schedule_path = os.path.dirname(__file__) + f"/telegram_bot/schedule_{date.today()}.json"
    if os.path.exists(schedule_path):
        health_status["checks"]["schedule"] = {"status": "ok"}
    else:
        health_status["checks"]["schedule"] = {"status": "warning", "message": "Today's schedule not found"}
    
    return health_status

if __name__ == "__main__":
    import sys
    
    if "--json" in sys.argv:
        print(json.dumps(check_service_health(), indent=2))
    else:
        health = check_service_health()
        print(f"Status: {health['status']}")
        print(f"Timestamp: {health['timestamp']}")
        print("Checks:")
        for check_name, check_result in health['checks'].items():
            print(f"  ✓ {check_name}: {check_result['status']}")

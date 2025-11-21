
import os
import importlib
from unittest.mock import patch

def test_port_configuration():
    """
    Test that WebhookConfig.PORT correctly picks up PORT environment variable.
    """
    # Mock environment variables: PORT set, WEBHOOK_PORT unset
    with patch.dict(os.environ, {"PORT": "8080"}, clear=True):
        # Reload settings to pick up env vars
        import config.settings
        importlib.reload(config.settings)
        from config.settings import WebhookConfig

        print(f"PORT=8080, WEBHOOK_PORT=unset -> WebhookConfig.PORT={WebhookConfig.PORT}")
        if WebhookConfig.PORT == 8080:
            print("PASS")
            return True
        else:
            print("FAIL")
            return False

def test_webhook_port_default():
    """
    Test default when nothing set
    """
    with patch.dict(os.environ, {}, clear=True):
        import config.settings
        importlib.reload(config.settings)
        from config.settings import WebhookConfig

        print(f"PORT=unset, WEBHOOK_PORT=unset -> WebhookConfig.PORT={WebhookConfig.PORT}")
        if WebhookConfig.PORT == 8000:
            print("PASS")
            return True
        else:
            print("FAIL")
            return False

def test_webhook_port_ignored():
    """
    Test that only PORT is used, WEBHOOK_PORT is ignored for Railway deployment.
    """
    with patch.dict(os.environ, {"PORT": "8080", "WEBHOOK_PORT": "9000"}, clear=True):
        import config.settings
        importlib.reload(config.settings)
        from config.settings import WebhookConfig

        print(f"PORT=8080, WEBHOOK_PORT='9000' (ignored) -> WebhookConfig.PORT={WebhookConfig.PORT}")
        if WebhookConfig.PORT == 8080:
            print("PASS")
            return True
        else:
            print("FAIL")
            return False

if __name__ == "__main__":
    r1 = test_port_configuration()
    r2 = test_webhook_port_default()
    r3 = test_webhook_port_ignored()
    success = r1 and r2 and r3
    exit(0 if success else 1)

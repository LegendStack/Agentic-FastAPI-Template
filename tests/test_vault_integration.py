import os
import unittest
from unittest.mock import MagicMock, patch

from src.app.core.config import Settings

# Ensure we can import the module
from src.app.core.vault import VaultSettingsSource


class TestVaultIntegration(unittest.TestCase):
    def setUp(self):
        # Clear env vars before each test
        keys = ["VAULT_ENABLED", "VAULT_URL", "VAULT_ROLE_ID", "VAULT_SECRET_ID", "VAULT_SECRET_PATH"]
        for k in keys:
            if k in os.environ:
                del os.environ[k]

    def test_vault_settings_source_enabled(self):
        # Setup env
        os.environ["VAULT_ENABLED"] = "true"
        os.environ["VAULT_URL"] = "http://mock-vault:8200"
        os.environ["VAULT_ROLE_ID"] = "mock-role"
        os.environ["VAULT_SECRET_ID"] = "mock-secret"
        os.environ["VAULT_SECRET_PATH"] = "secret/data/my-app"

        # Mock hvac module and Client
        mock_client = MagicMock()
        mock_client.is_authenticated.return_value = True
        mock_client.read.return_value = {
            "data": {"data": {"APP_NAME": "Vault Powered App", "SECRET_KEY": "vault-secret-key"}}
        }

        mock_hvac = MagicMock()
        mock_hvac.Client.return_value = mock_client

        # We patch 'hvac' in sys.modules so 'import hvac' returns our mock
        with patch.dict("sys.modules", {"hvac": mock_hvac}):
            source = VaultSettingsSource(Settings)
            result = source()

            self.assertEqual(result.get("APP_NAME"), "Vault Powered App")
            self.assertEqual(result.get("SECRET_KEY"), "vault-secret-key")

            mock_hvac.Client.assert_called_with(url="http://mock-vault:8200")
            mock_client.auth.approle.login.assert_called_with(role_id="mock-role", secret_id="mock-secret")

    def test_vault_settings_source_disabled(self):
        os.environ["VAULT_ENABLED"] = "false"

        # We don't need to mock hvac here efficiently, but let's do it to ensure no calls
        mock_hvac = MagicMock()

        with patch.dict("sys.modules", {"hvac": mock_hvac}):
            source = VaultSettingsSource(Settings)
            result = source()

            self.assertEqual(result, {})
            mock_hvac.Client.assert_not_called()


if __name__ == "__main__":
    unittest.main()

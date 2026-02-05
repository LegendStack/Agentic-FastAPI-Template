import os
import logging
from typing import Any, Tuple, Type, Dict

from pydantic.fields import FieldInfo
from pydantic_settings import BaseSettings, PydanticBaseSettingsSource

logger = logging.getLogger(__name__)

class VaultSettingsSource(PydanticBaseSettingsSource):
    """
    A Custom Pydantic Settings Source that loads secrets from HashiCorp Vault.
    
    It supports AppRole authentication and reads from a specified secret path.
    Configuration for Vault itself (URL, Role ID, Secret ID) is read from 
    environment variables to allow bootstrapping.
    """
    def get_field_value(
        self, field: FieldInfo, field_name: str
    ) -> Tuple[Any, str, bool]:
        # This method is required by the abstract base class but we won't use it directly
        # for individual field lookup as we want to load the whole secret bundle first.
        # However, Pydantic might call this if not all fields are found in the dict.
        return None, field_name, False

    def __call__(self) -> Dict[str, Any]:
        """
        Load settings from Vault.
        
        Returns:
            Dict[str, Any]: A dictionary of settings loaded from Vault.
        """
        vault_url = os.environ.get("VAULT_URL")
        vault_role_id = os.environ.get("VAULT_ROLE_ID")
        vault_secret_id = os.environ.get("VAULT_SECRET_ID")
        vault_secret_path = os.environ.get("VAULT_SECRET_PATH")
        vault_enabled = os.environ.get("VAULT_ENABLED", "false").lower() == "true"

        # If not enabled or missing critical config, skip Vault loading
        if not vault_enabled:
            return {}
        
        if not (vault_url and vault_role_id and vault_secret_id and vault_secret_path):
            logger.warning("Vault is enabled but missing configuration (URL, RoleID, SecretID, or Path). Skipping.")
            return {}

        try:
            import hvac # Import here to avoid hard dependency at module level if not used
            
            client = hvac.Client(url=vault_url)
            
            # Authenticate with AppRole
            client.auth.approle.login(
                role_id=vault_role_id,
                secret_id=vault_secret_id
            )
            
            if not client.is_authenticated():
                logger.error("Vault authentication failed.")
                return {}
            
            # Read secrets
            # Assuming KV Engine v2
            # The path usually looks like 'secret/data/my-app' for KV v2, but hvac handles mount points.
            # We'll support standard 'mount_point/data/path' or let the user specify.
            # For simplicity, we assume the user provides the full path suitable for the client.read method 
            # OR we try to determine version.
            
            # A common pattern for KV v2 in hvac is client.secrets.kv.v2.read_secret_version
            # But specific path parsing can be tricky.
            # Let's try the generic read first which works for many paths if fully specified.
            
            response = client.read(vault_secret_path)
            
            if response and "data" in response:
                # Handle KV v2 structure: data -> data -> secrets
                if "data" in response["data"]:
                     data = response["data"]["data"]
                else:
                     # Handle KV v1 structure: data -> secrets
                     data = response["data"]
                
                logger.info(f"Successfully loaded {len(data)} secrets from Vault.")
                return data
            else:
                logger.warning(f"No data found at Vault path: {vault_secret_path}")
                return {}

        except ImportError:
            logger.error("hvac library not installed. Cannot load Vault settings.")
            return {}
        except Exception as e:
            logger.error(f"Failed to load settings from Vault: {e}")
            return {}

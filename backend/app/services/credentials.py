import os
import re

from app.config import settings


class CredentialError(Exception):
    pass


def _ref_to_env_suffix(credential_ref: str) -> str:
    normalized = re.sub(r"[^a-zA-Z0-9]", "_", credential_ref.strip()).upper()
    if not normalized:
        raise CredentialError("Invalid credential_ref")
    return normalized


def resolve_private_key_path(credential_ref: str | None) -> str:
    if credential_ref:
        env_name = f"CREDENTIAL_{_ref_to_env_suffix(credential_ref)}_PATH"
        path = os.environ.get(env_name)
        if not path:
            raise CredentialError(
                f"No private key configured for credential_ref '{credential_ref}'. "
                f"Set env {env_name} or DEFAULT_SSH_PRIVATE_KEY_PATH."
            )
    elif settings.default_ssh_private_key_path:
        path = settings.default_ssh_private_key_path
    else:
        raise CredentialError(
            "Server has no credential_ref and DEFAULT_SSH_PRIVATE_KEY_PATH is not set."
        )

    expanded = os.path.expanduser(path)
    if not os.path.isfile(expanded):
        raise CredentialError(f"Private key file not found: {expanded}")
    return expanded

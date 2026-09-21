import os
import re

from app.config import settings


class CredentialError(Exception):
    pass


_PLACEHOLDER = "/absolute/path/to/credentials/"


def _ref_to_env_suffix(credential_ref: str) -> str:
    normalized = re.sub(r"[^a-zA-Z0-9]", "_", credential_ref.strip()).upper()
    if not normalized:
        raise CredentialError("Invalid credential_ref")
    return normalized


def _usable_key(path: str | None) -> str | None:
    if not path or _PLACEHOLDER in path:
        return None
    expanded = os.path.expanduser(path.strip())
    if os.path.isfile(expanded):
        return expanded
    return None


def resolve_private_key_path(credential_ref: str | None) -> str:
    candidates: list[str | None] = []
    if credential_ref:
        env_name = f"CREDENTIAL_{_ref_to_env_suffix(credential_ref)}_PATH"
        candidates.append(os.environ.get(env_name))
    candidates.append(os.environ.get("CREDENTIAL_GPU_KEY_1_PATH"))
    candidates.append(settings.default_ssh_private_key_path)
    candidates.append("/root/.ssh/id_rsa")
    candidates.append(os.path.expanduser("~/.ssh/id_rsa"))

    for raw in candidates:
        hit = _usable_key(raw)
        if hit:
            return hit

    raise CredentialError(
        "Private key file not found. Set CREDENTIAL_GPU_KEY_1_PATH "
        "(production: /root/.ssh/id_rsa) and credential_ref=gpu_key_1."
    )

"""Create local-only credentials. Never commit generated .env."""

import json
from pathlib import Path
import secrets

path = Path(".env")
if path.exists():
    raise SystemExit(".env already exists; refusing to overwrite credentials")
keys = {
    secrets.token_urlsafe(32): {"tenant": "demo", "subject": "operator", "role": "operator"},
    secrets.token_urlsafe(32): {"tenant": "demo", "subject": "approver", "role": "approver"},
    secrets.token_urlsafe(32): {"tenant": "demo", "subject": "admin", "role": "admin"},
}
path.write_text(
    "AGENTFORGE_KEYS='"
    + json.dumps(keys)
    + "'\nWEBHOOK_SECRET="
    + secrets.token_urlsafe(32)
    + "\nAGENTFORGE_ENV=development\nOPENAI_API_KEY=\nOPENAI_MODEL=gpt-4.1-mini\n"
)
path.chmod(0o600)
print("Created .env with separate operator, approver and admin keys. Read it locally to sign in.")

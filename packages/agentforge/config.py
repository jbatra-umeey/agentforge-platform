import json
import os
from dataclasses import dataclass, field


@dataclass
class Settings:
    db_path: str = field(default_factory=lambda: os.getenv("AGENTFORGE_DB", "data/agentforge.db"))
    keys: dict = field(default_factory=lambda: json.loads(os.getenv("AGENTFORGE_KEYS", "{}")))
    environment: str = field(default_factory=lambda: os.getenv("AGENTFORGE_ENV", "development"))
    model: str = field(default_factory=lambda: os.getenv("OPENAI_MODEL", "gpt-4.1-mini"))
    fallback_model: str = field(default_factory=lambda: os.getenv("FALLBACK_MODEL", ""))
    base_url: str = field(default_factory=lambda: os.getenv("LLM_BASE_URL", "https://api.openai.com/v1"))
    llm_key: str = field(default_factory=lambda: os.getenv("OPENAI_API_KEY", ""))
    webhook_secret: str = field(default_factory=lambda: os.getenv("WEBHOOK_SECRET", ""))
    worker_enabled: bool = True

    def validate(self):
        if not self.keys:
            raise ValueError("AGENTFORGE_KEYS must map random bearer keys to tenant, subject, role")
        for key, identity in self.keys.items():
            if len(key) < 24 or not all(identity.get(k) for k in ("tenant", "subject", "role")):
                raise ValueError("Keys need 24+ characters and tenant/subject/role identities")
            if identity["role"] not in ("viewer", "operator", "approver", "admin"):
                raise ValueError("Unknown role")
        if self.environment == "production":
            if not self.base_url.startswith("https://"):
                raise ValueError("Production model endpoint must use HTTPS")
            if len(self.webhook_secret) < 32:
                raise ValueError("Production webhook secret must be 32+ characters")

from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass
class LicenseStatus:
    """Status da licenca."""
    valid: bool
    user_id: Optional[str] = None
    status: Optional[str] = None
    expires_at: Optional[datetime] = None
    days_remaining: Optional[int] = None
    message: Optional[str] = None

    @classmethod
    def from_api_response(cls, data: dict) -> "LicenseStatus":
        expires_at = None
        if data.get("expiresAt"):
            expires_at = datetime.fromisoformat(data["expiresAt"].replace("Z", "+00:00"))

        return cls(
            valid=data.get("valid", False),
            user_id=data.get("userId"),
            status=data.get("status"),
            expires_at=expires_at,
            days_remaining=data.get("daysRemaining"),
            message=data.get("message"),
        )

    @property
    def is_expiring_soon(self) -> bool:
        """Retorna True se expira em menos de 7 dias."""
        return self.days_remaining is not None and self.days_remaining <= 7

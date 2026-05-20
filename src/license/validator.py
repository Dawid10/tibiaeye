import logging
import os
from typing import Optional
import requests

from .status import LicenseStatus
from .exceptions import (
    LicenseExpiredException,
    LicenseInvalidException,
    LicenseServerException,
)

logger = logging.getLogger(__name__)


class LicenseValidator:
    """
    Validador de licenca do bot.

    Uso:
        validator = LicenseValidator(api_key="tm_xxxxx")

        # No startup do bot
        if not validator.validate():
            print("License invalid!")
            sys.exit(1)

        # Verifica periodicamente (a cada 1h por exemplo)
        if validator.is_expired:
            print("License expired!")
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        api_url: Optional[str] = None,
    ):
        self._api_key = api_key or os.getenv("TELEMETRY_API_KEY", "")
        self._api_url = api_url or os.getenv("TELEMETRY_API_URL", "http://localhost:3333")
        self._status: Optional[LicenseStatus] = None
        self._last_check: Optional[float] = None

    @property
    def api_key(self) -> str:
        return self._api_key

    @property
    def status(self) -> Optional[LicenseStatus]:
        return self._status

    @property
    def is_valid(self) -> bool:
        return self._status is not None and self._status.valid

    @property
    def is_expired(self) -> bool:
        if self._status is None:
            return True
        return not self._status.valid and self._status.status == "expired"

    @property
    def days_remaining(self) -> int:
        if self._status is None:
            return 0
        return self._status.days_remaining or 0

    def validate(self, raise_on_error: bool = True) -> bool:
        """
        Valida a licenca com o servidor.

        Args:
            raise_on_error: Se True, levanta excecao em caso de erro

        Returns:
            True se licenca valida, False caso contrario

        Raises:
            LicenseExpiredException: Se licenca expirou
            LicenseInvalidException: Se licenca invalida
            LicenseServerException: Se servidor inacessivel
        """
        if not self._api_key:
            if raise_on_error:
                raise LicenseInvalidException("No API key configured")
            return False

        try:
            response = requests.post(
                f"{self._api_url}/api/v1/license/validate",
                json={"apiKey": self._api_key},
                timeout=10.0,
            )

            if response.status_code == 200:
                data = response.json()
                self._status = LicenseStatus.from_api_response(data)

                if not self._status.valid:
                    if self._status.status == "expired":
                        if raise_on_error:
                            raise LicenseExpiredException(
                                self._status.expires_at.isoformat() if self._status.expires_at else "unknown"
                            )
                        return False

                    if raise_on_error:
                        raise LicenseInvalidException(self._status.message or "Invalid license")
                    return False

                if self._status.is_expiring_soon:
                    logger.warning(
                        f"License expiring in {self._status.days_remaining} days! "
                        f"Please renew your subscription."
                    )

                logger.info(f"License valid. Days remaining: {self._status.days_remaining}")
                return True

            if raise_on_error:
                raise LicenseInvalidException(f"Server returned status {response.status_code}")
            return False

        except requests.RequestException as e:
            logger.error(f"Could not validate license: {e}")
            if raise_on_error:
                raise LicenseServerException()
            return False

    def check_periodically(self) -> bool:
        """
        Verifica licenca se ultima verificacao foi ha mais de 1 hora.
        Nao levanta excecao, apenas retorna False se expirada.
        """
        import time

        now = time.time()

        # Verifica a cada 1 hora
        if self._last_check is not None and (now - self._last_check) < 3600:
            return self.is_valid

        self._last_check = now
        return self.validate(raise_on_error=False)

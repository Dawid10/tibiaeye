class LicenseException(Exception):
    """Base exception for license errors."""
    pass


class LicenseExpiredException(LicenseException):
    """Raised when license is expired."""
    def __init__(self, expires_at: str):
        self.expires_at = expires_at
        super().__init__(f"License expired on {expires_at}")


class LicenseInvalidException(LicenseException):
    """Raised when license key is invalid."""
    def __init__(self, message: str = "Invalid license key"):
        super().__init__(message)


class LicenseServerException(LicenseException):
    """Raised when license server is unreachable."""
    def __init__(self):
        super().__init__("Could not connect to license server")

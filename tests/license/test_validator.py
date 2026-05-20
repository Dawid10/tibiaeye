import pytest
from unittest.mock import patch, Mock
from src.license.validator import LicenseValidator
from src.license.status import LicenseStatus
from src.license.exceptions import (
    LicenseExpiredException,
    LicenseInvalidException,
    LicenseServerException,
)


class TestLicenseValidator:
    def test_no_api_key_raises(self):
        validator = LicenseValidator(api_key="")
        with pytest.raises(LicenseInvalidException, match="No API key configured"):
            validator.validate(raise_on_error=True)

    def test_no_api_key_returns_false(self):
        validator = LicenseValidator(api_key="")
        assert validator.validate(raise_on_error=False) is False

    @patch("src.license.validator.requests.post")
    def test_valid_license(self, mock_post):
        mock_post.return_value = Mock(
            status_code=200,
            json=Mock(return_value={
                "valid": True,
                "userId": "user-123",
                "status": "active",
                "daysRemaining": 30,
                "expiresAt": "2026-12-31T00:00:00Z",
            }),
        )

        validator = LicenseValidator(api_key="tm_test_key", api_url="http://test")
        result = validator.validate(raise_on_error=False)

        assert result is True
        assert validator.is_valid is True
        assert validator.is_expired is False
        assert validator.days_remaining == 30

    @patch("src.license.validator.requests.post")
    def test_expired_license_raises(self, mock_post):
        mock_post.return_value = Mock(
            status_code=200,
            json=Mock(return_value={
                "valid": False,
                "status": "expired",
                "expiresAt": "2025-01-01T00:00:00Z",
            }),
        )

        validator = LicenseValidator(api_key="tm_test_key", api_url="http://test")
        with pytest.raises(LicenseExpiredException):
            validator.validate(raise_on_error=True)

    @patch("src.license.validator.requests.post")
    def test_expired_license_returns_false(self, mock_post):
        mock_post.return_value = Mock(
            status_code=200,
            json=Mock(return_value={
                "valid": False,
                "status": "expired",
                "expiresAt": "2025-01-01T00:00:00Z",
            }),
        )

        validator = LicenseValidator(api_key="tm_test_key", api_url="http://test")
        result = validator.validate(raise_on_error=False)

        assert result is False
        assert validator.is_expired is True

    @patch("src.license.validator.requests.post")
    def test_invalid_license_raises(self, mock_post):
        mock_post.return_value = Mock(
            status_code=200,
            json=Mock(return_value={
                "valid": False,
                "status": "invalid",
                "message": "Key not found",
            }),
        )

        validator = LicenseValidator(api_key="tm_bad_key", api_url="http://test")
        with pytest.raises(LicenseInvalidException, match="Key not found"):
            validator.validate(raise_on_error=True)

    @patch("src.license.validator.requests.post")
    def test_server_error_raises(self, mock_post):
        import requests
        mock_post.side_effect = requests.ConnectionError("Connection refused")

        validator = LicenseValidator(api_key="tm_test_key", api_url="http://test")
        with pytest.raises(LicenseServerException):
            validator.validate(raise_on_error=True)

    @patch("src.license.validator.requests.post")
    def test_server_error_returns_false(self, mock_post):
        import requests
        mock_post.side_effect = requests.ConnectionError("Connection refused")

        validator = LicenseValidator(api_key="tm_test_key", api_url="http://test")
        result = validator.validate(raise_on_error=False)
        assert result is False

    @patch("src.license.validator.requests.post")
    def test_non_200_status_raises(self, mock_post):
        mock_post.return_value = Mock(status_code=500)

        validator = LicenseValidator(api_key="tm_test_key", api_url="http://test")
        with pytest.raises(LicenseInvalidException, match="Server returned status 500"):
            validator.validate(raise_on_error=True)


class TestLicenseStatus:
    def test_from_api_response(self):
        data = {
            "valid": True,
            "userId": "user-123",
            "status": "active",
            "daysRemaining": 30,
            "expiresAt": "2026-12-31T00:00:00Z",
        }
        status = LicenseStatus.from_api_response(data)

        assert status.valid is True
        assert status.user_id == "user-123"
        assert status.days_remaining == 30
        assert status.is_expiring_soon is False

    def test_expiring_soon(self):
        data = {
            "valid": True,
            "daysRemaining": 3,
        }
        status = LicenseStatus.from_api_response(data)
        assert status.is_expiring_soon is True

    def test_not_expiring_soon(self):
        data = {
            "valid": True,
            "daysRemaining": 30,
        }
        status = LicenseStatus.from_api_response(data)
        assert status.is_expiring_soon is False


class TestCheckPeriodically:
    @patch("src.license.validator.requests.post")
    def test_caches_result_within_hour(self, mock_post):
        mock_post.return_value = Mock(
            status_code=200,
            json=Mock(return_value={"valid": True, "daysRemaining": 30}),
        )

        validator = LicenseValidator(api_key="tm_test_key", api_url="http://test")

        # First call validates
        result1 = validator.check_periodically()
        assert result1 is True
        assert mock_post.call_count == 1

        # Second call uses cache
        result2 = validator.check_periodically()
        assert result2 is True
        assert mock_post.call_count == 1  # Not called again

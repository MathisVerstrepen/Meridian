from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

TOKEN_ENV = "LINK_EXTRACTION_BROWSER_SERVICE_TOKEN"
PROXY_ENV = "LINK_EXTRACTION_BROWSER_PROXY_URL"


class BrowserServiceSettings(BaseSettings):
    model_config = SettingsConfigDict(case_sensitive=True, extra="ignore")

    port: int = Field(default=5010, ge=1, le=65535, alias="LINK_EXTRACTION_BROWSER_SERVICE_PORT")
    token: SecretStr = Field(alias="LINK_EXTRACTION_BROWSER_SERVICE_TOKEN")
    proxy_url: SecretStr | None = Field(default=None, alias="LINK_EXTRACTION_BROWSER_PROXY_URL")

    @field_validator("token")
    @classmethod
    def validate_token(cls, value: SecretStr) -> SecretStr:
        token = value.get_secret_value()
        if (
            len(token) < 32
            or any(not "!" <= character <= "~" for character in token)
            or token.lower()
            in {
                "change-me",
                "replace-me",
                "example",
            }
        ):
            raise ValueError("browser service token is not configured")
        return value


def load_settings() -> BrowserServiceSettings:
    return BrowserServiceSettings()  # type: ignore[call-arg]

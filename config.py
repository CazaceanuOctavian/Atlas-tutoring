from pydantic_settings import BaseSettings


class AuthSettings(BaseSettings):
    google_client_id:     str
    google_client_secret: str
    # FIXME -> Change to https://atlas-tutoring.onrender.com
    app_base_url:         str = "http://localhost:8000" 

    # JWT
    jwt_secret_key:       str = "change-me-in-production"
    jwt_algorithm:        str = "HS256"
    jwt_expire_minutes:   int = 60 * 24  # 24 hours

    @property
    def google_redirect_uri(self) -> str:
        return f"{self.app_base_url}/api/v1/auth/google/callback"

    model_config = {"env_file": ".env", "extra": "ignore"}


auth_settings = AuthSettings()
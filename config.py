from pydantic_settings import BaseSettings


class AuthSettings(BaseSettings):
    google_client_id:     str
    google_client_secret: str
    app_base_url:         str 
    frontend_url:         str
    

    # JWT
    jwt_secret_key:       str 
    jwt_algorithm:        str 
    jwt_expire_minutes:   int 
    runner_url:           str

    @property
    def google_redirect_uri(self) -> str:
        return f"{self.app_base_url}/api/v1/auth/google/callback"

    model_config = {"env_file": ".env", "extra": "ignore"}

auth_settings = AuthSettings()
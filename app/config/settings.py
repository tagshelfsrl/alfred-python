# 3rd party imports
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Setup dotenv file support
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    # App configuration
    version: str = Field("0.1.0")
    name: str = Field("python-template")
    env: str = Field("dev", env="ENV")
    health_path: str = Field("./healthy", env="HEALTH_PATH")

    # Logging configuration
    pt_host: str = Field("logs3.papertrailapp.com", env="PAPERTRAIL_HOST")
    pt_port: int = Field(33780, env="PAPERTRAIL_PORT")


settings = Settings()

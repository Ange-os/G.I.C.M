from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    database_url: str = "postgresql+asyncpg://conversa:conversa@localhost:5432/conversa"
    redis_url: str = "redis://localhost:6379/0"
    n8n_webhook_url: str | None = None
    n8n_api_key: str | None = None
    # Etapa 2.7: outbound Instagram vía n8n (credenciales Meta quedan en n8n)
    n8n_instagram_outbound_url: str | None = None
    # Canal web xIA.ar (espejo Inbox)
    xia_api_key: str | None = None
    xia_outbound_url: str | None = None
    ycloud_webhook_secret: str | None = None
    ycloud_api_key: str | None = None
    ycloud_from_number: str | None = None
    # WhatsApp: ycloud (actual) | meta (Cloud API experimento). Ambos webhooks pueden convivir.
    whatsapp_default_provider: str = "ycloud"
    meta_whatsapp_access_token: str | None = None
    meta_whatsapp_phone_number_id: str | None = None
    meta_whatsapp_business_account_id: str | None = None
    meta_whatsapp_verify_token: str | None = None
    meta_whatsapp_app_secret: str | None = None
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"
    jwt_secret: str = "cambiar-este-secreto"
    jwt_expire_minutes: int = 720
    admin_email: str | None = None
    admin_password: str | None = None
    admin_name: str = "Administración"
    consejo_email: str | None = None
    consejo_password: str | None = None
    consejo_name: str = "Consejo"
    muestra_insta_email: str | None = None
    muestra_insta_password: str | None = None
    muestra_insta_name: str = "Muestra Instagram"
    deepseek_api_key: str | None = None
    deepseek_base_url: str = "https://api.deepseek.com"
    deepseek_model: str = "deepseek-chat"
    # local = tablas simulacro en Postgres; external = implementar otro repository
    domain_data_source: str = "local"
    smtp_host: str | None = None
    smtp_port: int = 587
    smtp_user: str | None = None
    smtp_password: str | None = None
    smtp_from: str | None = None
    smtp_tls: bool = True

    @property
    def cors_origins_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


settings = Settings()

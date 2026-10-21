from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    use_sqlite: bool = False
    sqlite_path: str = "hamrah_test.db"

    database_url: str
    database_hostname: str
    database_port: int
    database_password: str
    database_name: str
    database_username: str
    secret_key: str
    algorithm: str
    access_token_expire_minutes: int

    email_host: str
    email_port: int
    email_user: str
    email_pass: str

    # Agora
    agora_app_id: str
    agora_app_certificate: str

    # SOS
    sos_police_number: str
    sos_hamrah_support_number: str
    sos_campus_security_number: str

    ai_provider: str = "openai"  
    ai_api_key: str = ""        
    ai_model: str = "gpt-4o-mini"  
    ai_enabled: bool = False     
    ai_recommendation_hour: int = 22 
    ai_recommendation_minute: int = 0

    class Config:
        env_file = ".env"
        case_sensitive = False

settings = Settings()

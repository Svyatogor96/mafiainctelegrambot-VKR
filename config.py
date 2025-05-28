from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class CBotSettings(BaseSettings):
    BOT_TOKEN_: str = Field(alias='BOT_TOKEN')
    PAY_TOKEN_: str = Field(alias='PAY_TOKEN')
    DB_HOST_: str = Field(alias='DB_HOST')
    DB_PORT_: int = Field(alias='DB_PORT')
    DB_USER_: str = Field(alias='DB_USER')
    DB_PASS_: str = Field(alias='DB_PASS')
    DB_NAME_: str = Field(alias='DB_NAME')
    DROP_DB_: bool = Field(alias='DROP_DB')
    LOGGING_: bool = Field(alias='LOGGING')
    BITRIX_LEAD_ADD_: str = Field(alias='BITRIX_LEAD_ADD')

    model_config = SettingsConfigDict(env_file="settings.env", case_sensitive=False)

    @property
    def DATABASE_URL(self) -> str:
        return f"mysql+mysqlconnector://{self.DB_USER_}:{self.DB_PASS_}@{self.DB_HOST_}:{self.DB_PORT_}/{self.DB_NAME_}"

    @property
    def DATABASE_ASYNC_URL(self) -> str:
        return f"mysql+asyncmy://{self.DB_USER_}:{self.DB_PASS_}@{self.DB_HOST_}:{self.DB_PORT_}/{self.DB_NAME_}"

    @property
    def BOT_TOKEN(self) -> str:
        return self.BOT_TOKEN_

    @property
    def PAY_TOKEN(self) -> str:
        return self.PAY_TOKEN_

    @property
    def DROP_DB(self) -> bool:
        return self.DROP_DB_

    @property
    def LOGGING(self) -> bool:
        return self.LOGGING_

    @property
    def BITRIX_LEAD_ADD(self) -> str:
        return self.BITRIX_LEAD_ADD_


GlobalSettings = CBotSettings()

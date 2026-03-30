from dataclasses import dataclass
import os


@dataclass(slots=True)
class Settings:
    app_env: str = "dev"
    log_level: str = "INFO"
    data_dir: str = "data"
    gaode_api_key: str | None = None
    baidu_api_key: str | None = None
    xhs_debug: bool = False
    auto_install_chromium: bool = True

    @classmethod
    def from_env(cls) -> "Settings":
        return cls(
            app_env=os.getenv("SIRIUS_APP_ENV", "dev"),
            log_level=os.getenv("SIRIUS_LOG_LEVEL", "INFO"),
            data_dir=os.getenv("SIRIUS_DATA_DIR", "data"),
            gaode_api_key=os.getenv("GAODE_API_KEY"),
            baidu_api_key=os.getenv("BAIDU_API_KEY"),
            xhs_debug=os.getenv("SIRIUS_XHS_DEBUG", "0") in {"1", "true", "TRUE", "yes", "on"},
            auto_install_chromium=os.getenv("SIRIUS_AUTO_INSTALL_CHROMIUM", "1")
            in {"1", "true", "TRUE", "yes", "on"},
        )

import sys
from pathlib import Path

# Устанавливаем минимальный обработчик крашей ДО любых других импортов
# Это гарантирует перехват ошибок на ранних этапах запуска
def _early_crash_handler(exc_type, exc_value, exc_tb) -> None:
    """Минимальный обработчик для ранних ошибок запуска."""
    from datetime import datetime
    import traceback
    
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    crash_file = Path.home() / f"lgt_early_crash_{timestamp}.log"
    
    try:
        with open(crash_file, "w", encoding="utf-8") as f:
            f.write("LGT Early Crash Report\n")
            f.write(f"Time: {datetime.now().isoformat()}\n")
            f.write("=" * 60 + "\n\n")
            traceback.print_exception(exc_type, exc_value, exc_tb, file=f)
    except Exception:
        pass
    
    print(f"\n{'!' * 60}")
    print("EARLY CRASH DETECTED!")
    print(f"Crash log saved: {crash_file}")
    print(f"{'!' * 60}\n")
    traceback.print_exception(exc_type, exc_value, exc_tb)
    sys.exit(1)


sys.excepthook = _early_crash_handler

import logging  # noqa: E402
from PySide6 import QtWidgets, QtGui  # noqa: E402
from rich.traceback import install as install_rich_tracebacks  # noqa: E402
from omni_trans_core import settings  # noqa: E402
from omni_trans_core.crash_handler import install_crash_handler  # noqa: E402
from omni_trans_core.localization_manager import loc_man  # noqa: E402
from omni_trans_core.utils import ui_loader_manager  # noqa: E402
from omni_trans_core.logger import LoggerManager  # noqa: E402
from omni_trans_core.ui.theme import detect_best_font  # noqa: E402
from lgt_app.app import LGTApp  # noqa: E402
from lgt_app.constants import LOG_PREFIX  # noqa: E402


# Глобальная ссылка на logger_manager для crash_handler
_logger_manager: LoggerManager | None = None


def _get_app_log() -> str:
    """Callback для получения полного лога приложения."""
    global _logger_manager
    if _logger_manager and _logger_manager.recording_console:
        try:
            # Получаем записанный лог из recording_console
            import io
            buffer = io.StringIO()
            _logger_manager.recording_console.print(file=buffer)
            return buffer.getvalue()
        except Exception:
            pass
    return ""


def main() -> None:
    global _logger_manager
    
    _ = install_rich_tracebacks(show_locals=True)

    project_root = str(Path(__file__).parent.parent.resolve())

    sys.path.insert(0, project_root)

    settings.initialize_app_paths(project_root_path=project_root)

    settings.load_settings()

    _logger_manager = LoggerManager(settings.current_settings)
    _logger_manager.configure_logging()
    logger = logging.getLogger(f"{LOG_PREFIX}_RUN")
    
    # Устанавливаем полноценный обработчик крашей ПОСЛЕ создания logger_manager
    install_crash_handler(
        crash_logs_dir=Path(settings.GLOBAL_CRASH_LOGS_DIR),
        app_name="LGT",
        get_app_log_callback=_get_app_log,
        cleanup=True,
        max_age_days=30,
        max_files=20,
    )

    logger.info("Starting LGT application")
    logger.debug(f"Project root: {project_root}")

    app = QtWidgets.QApplication.instance()
    if app is None:
        app = QtWidgets.QApplication(sys.argv)

    assert isinstance(app, QtWidgets.QApplication)

    app_i18n_path = Path(__file__).parent / "i18n_app"
    if app_i18n_path.is_dir():
        loc_man.add_translation_directory(str(app_i18n_path))
        loc_man.reload_current_language()

    best_font = detect_best_font()
    font = QtGui.QFont(best_font, 10)
    font.setStyleStrategy(QtGui.QFont.PreferAntialias)
    app.setFont(font)
    logger.debug(f"Font set: {best_font}")

    main_window = LGTApp()
    main_window.showMaximized()
    ui_loader_manager.log_summary()
    main_window.log_initialization_complete()
    logger.info("Application initialized")
    sys.exit(app.exec())


if __name__ == "__main__":
    main()

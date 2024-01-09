import logging

from bot_util.bot_config import IS_DEV_BUILD


class bcolors:
    HEADER = "\033[95m"
    OKBLUE = "\033[94m"
    OKCYAN = "\033[96m"
    OKGREEN = "\033[92m"
    WARNING = "\033[93m"
    FAIL = "\033[91m"
    ENDC = "\033[0m"
    BOLD = "\033[1m"
    UNDERLINE = "\033[4m"


class CustomFormatter(logging.Formatter):
    grey = "\x1b[38;20m"
    yellow = "\x1b[33;20m"
    red = "\x1b[31;20m"
    bold_red = "\x1b[31;1m"
    reset = "\x1b[0m"
    format_str = (
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s (%(filename)s:%(lineno)d)"
    )

    FORMATS = {
        logging.DEBUG: grey + format_str + reset,
        logging.INFO: grey + format_str + reset,
        logging.WARNING: yellow + format_str + reset,
        logging.ERROR: red + format_str + reset,
        logging.CRITICAL: bold_red + format_str + reset,
    }

    def format(self, record):
        log_fmt = self.format_str
        self._style._fmt = log_fmt
        return super().format(record)


class CustomLogger(logging.Logger):
    def __init__(self, name: str, level = 0, log_file_path: str = None) -> None:
        super().__init__(name, level)
        self.file = log_file_path
        self.console_handler: logging.StreamHandler = None
        self.set_console_handler()
        self.set_console_level()
        self.set_file_handler() if self.file else None
        self.install_coloredlogs()
    
    def set_console_handler(self):
        self.console_handler = logging.StreamHandler()
        self.console_handler.setFormatter(CustomFormatter())
        self.addHandler(self.console_handler)
    
    def set_file_handler(self):
        file_handler = logging.FileHandler(self.file)
        file_handler.setLevel(logging.INFO) 
        file_handler.setFormatter(CustomFormatter())
        self.addHandler(file_handler)
    
    def set_console_level(self):
        self.console_handler.setLevel(logging.DEBUG if IS_DEV_BUILD else logging.INFO) 
    
    def install_coloredlogs(self):
        try:
            import coloredlogs
            coloredlogs.install(level="DEBUG", logger=self, handler=self.console_handler)
        except Exception:
            print("Colored logs not installed")

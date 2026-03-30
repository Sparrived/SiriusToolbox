import logging


def build_logger(level: str = "INFO") -> logging.Logger:
    logger = logging.getLogger("sirius_toolbox")
    logger.setLevel(level.upper())

    if logger.handlers:
        return logger

    handler = logging.StreamHandler()
    formatter = logging.Formatter(
        fmt="%(asctime)s %(name)s %(levelname)s %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    handler.setFormatter(formatter)

    logger.addHandler(handler)
    logger.propagate = False
    return logger

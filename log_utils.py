
import logging
def setup_logging(level: str = "INFO") -> None:
    level_value = getattr(logging, level.upper(), logging.INFO)
    logging.basicConfig(level=level_value, format="%(asctime)s | %(levelname)s | %(name)s | %(message)s")

import logging
import sys


def configure_logging() -> None:
    """
    Configure the global logging system.
    """

    logging.basicConfig(
        level=logging.INFO,
        format=("%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"),
        handlers=[
            logging.StreamHandler(sys.stdout),
        ],
    )

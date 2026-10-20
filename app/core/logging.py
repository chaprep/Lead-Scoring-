import logging
import sys
import re


class RedactCallbackToken(logging.Filter):
    def filter(self, record):
        pattern = r"(/webhooks/signalhire/)[^\s?\"/]+"
        if (
            record.name == "uvicorn.access"
            and isinstance(record.args, tuple)
            and len(record.args) == 5
        ):
            args = list(record.args)
            args[2] = re.sub(pattern, r"\1[redacted]", str(args[2]))
            record.args = tuple(args)
        else:
            record.msg = re.sub(pattern, r"\1[redacted]", record.getMessage())
            record.args = ()
        return True


def configure_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
        stream=sys.stdout,
        force=True,
    )

    for name in ("uvicorn.access", "httpx", "app.workers.coordinator"):
        logging.getLogger(name).addFilter(RedactCallbackToken())

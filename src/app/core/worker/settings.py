import asyncio
from typing import cast

from arq.cli import watch_reload
from arq.connections import RedisSettings
from arq.typing import WorkerSettingsType
from arq.worker import check_health, run_worker

from ...core.config import settings
from ...core.logger import logging  # noqa: F401
from .functions import on_job_end, on_job_start, sample_background_task, shutdown, startup

REDIS_QUEUE_HOST = settings.REDIS_QUEUE_HOST
REDIS_QUEUE_PORT = settings.REDIS_QUEUE_PORT


class WorkerSettings:
    functions = [sample_background_task]
    redis_settings = RedisSettings(host=REDIS_QUEUE_HOST, port=REDIS_QUEUE_PORT)
    on_startup = startup
    on_shutdown = shutdown
    on_job_start = on_job_start
    on_job_end = on_job_end
    handle_signals = False


def start_arq_service(check: bool = False, burst: int | None = None, watch: str | None = None):
    worker_settings_ = cast("WorkerSettingsType", WorkerSettings)

    if check:
        exit(check_health(worker_settings_))
    else:
        kwargs = {} if burst is None else {"burst": burst}
        if watch:
            asyncio.run(watch_reload(watch, worker_settings_))
        else:
            run_worker(worker_settings_, **kwargs)


if __name__ == "__main__":
    start_arq_service()
    # python -m src.app.core.worker.settings

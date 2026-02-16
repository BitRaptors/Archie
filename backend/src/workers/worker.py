"""ARQ worker entry point."""
from arq import run_worker
from workers.tasks import WorkerSettings

if __name__ == "__main__":
    run_worker(WorkerSettings)



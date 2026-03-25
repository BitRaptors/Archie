"""ARQ worker entry point.

Handles Python 3.14+ compatibility where asyncio.get_event_loop()
no longer auto-creates an event loop in the main thread.
"""
import asyncio
from arq import run_worker
from workers.tasks import WorkerSettings


def main():
    """Start the ARQ worker with Python 3.14+ event loop compatibility."""
    # Python 3.14 removed automatic event loop creation in get_event_loop().
    # ARQ's Worker.run() calls asyncio.get_event_loop() internally,
    # so we must ensure one exists before handing off to ARQ.
    try:
        asyncio.get_event_loop()
    except RuntimeError:
        asyncio.set_event_loop(asyncio.new_event_loop())

    run_worker(WorkerSettings)


if __name__ == "__main__":
    main()

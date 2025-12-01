"""Global error handling and resilience mechanisms."""

import asyncio
import functools
import logging
import sys
import traceback
from typing import Any, Callable, Optional, TypeVar

try:  # pragma: no cover - Python <3.10 compatibility
    from typing import ParamSpec
except ImportError:  # pragma: no cover - fallback for older runtimes
    from typing_extensions import ParamSpec  # type: ignore

logger = logging.getLogger(__name__)

P = ParamSpec("P")
T = TypeVar("T")


def setup_global_exception_handler() -> None:
    """Set up global exception handler for uncaught asyncio exceptions."""

    def handle_exception(loop: asyncio.AbstractEventLoop, context: dict) -> None:
        """Handle uncaught exceptions in asyncio event loop."""
        exception = context.get("exception")
        message = context.get("message", "Unhandled exception in async task")

        if exception:
            logger.error(
                "Asyncio exception handler caught: %s",
                message,
                exc_info=exception,
                extra={"context": context},
            )
        else:
            logger.error(
                "Asyncio exception handler caught: %s (context: %s)",
                message,
                context,
            )

    # Set exception handler for the current event loop
    try:
        loop = asyncio.get_running_loop()
        loop.set_exception_handler(handle_exception)
        logger.info("Global asyncio exception handler installed")
    except RuntimeError:
        # No running loop yet, will be set when loop starts
        logger.debug("No running loop to install exception handler yet")


def resilient_task(
    *,
    task_name: str,
    retry_on_error: bool = True,
    retry_delay: float = 5.0,
    max_retries: Optional[int] = None,
    log_errors: bool = True,
) -> Callable[[Callable[P, Any]], Callable[P, Any]]:
    """
    Decorator to make background tasks resilient to errors.

    Args:
        task_name: Human-readable name for logging
        retry_on_error: Whether to retry on exceptions
        retry_delay: Delay in seconds before retry
        max_retries: Maximum number of retries (None = infinite)
        log_errors: Whether to log errors

    Example:
        @resilient_task(task_name="cache_health_watcher")
        async def my_background_task():
            while True:
                await do_work()
                await asyncio.sleep(60)
    """
    def decorator(func: Callable[P, T]) -> Callable[P, T]:
        @functools.wraps(func)
        async def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
            attempt = 0
            while True:
                try:
                    result = await func(*args, **kwargs)
                    return result
                except asyncio.CancelledError:
                    if log_errors:
                        logger.info("%s cancelled, shutting down gracefully", task_name)
                    raise
                except Exception as exc:
                    attempt += 1
                    if log_errors:
                        logger.error(
                            "%s failed (attempt %d): %s",
                            task_name,
                            attempt,
                            exc,
                            exc_info=True,
                        )

                    if not retry_on_error or (max_retries and attempt >= max_retries):
                        logger.critical(
                            "%s permanently failed after %d attempts, not retrying",
                            task_name,
                            attempt,
                        )
                        raise

                    logger.warning(
                        "%s will retry in %.1fs (attempt %d)",
                        task_name,
                        retry_delay,
                        attempt,
                    )
                    await asyncio.sleep(retry_delay)

        return wrapper
    return decorator


def log_unhandled_exceptions(func: Callable[P, T]) -> Callable[P, T]:
    """Decorator to log unhandled exceptions in sync functions."""
    @functools.wraps(func)
    def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
        try:
            return func(*args, **kwargs)
        except Exception:
            logger.exception("Unhandled exception in %s", func.__name__)
            raise
    return wrapper


def safe_background_task(
    task_name: str,
    task_coro: Any,
    *,
    daemon: bool = True,
) -> asyncio.Task:
    """
    Create a background task with proper error handling.

    Args:
        task_name: Human-readable name for the task
        task_coro: The coroutine to run
        daemon: If True, cancellation errors are suppressed on shutdown

    Returns:
        The created asyncio.Task
    """
    async def wrapped() -> Any:
        try:
            return await task_coro
        except asyncio.CancelledError:
            logger.info("Background task '%s' cancelled", task_name)
            if not daemon:
                raise
        except Exception:
            logger.exception("Background task '%s' failed with unhandled exception", task_name)
            raise

    task = asyncio.create_task(wrapped(), name=task_name)
    return task


class GracefulShutdown:
    """Context manager for graceful shutdown of background tasks."""

    def __init__(self, timeout: float = 10.0):
        self.timeout = timeout
        self.tasks: list[asyncio.Task] = []

    def add_task(self, task: asyncio.Task) -> None:
        """Add a task to be gracefully shut down."""
        self.tasks.append(task)

    async def shutdown(self) -> None:
        """Shutdown all tracked tasks gracefully."""
        if not self.tasks:
            return

        logger.info("Gracefully shutting down %d background tasks...", len(self.tasks))

        # Cancel all tasks
        for task in self.tasks:
            if not task.done():
                task.cancel()

        # Wait for all tasks to complete or timeout
        try:
            await asyncio.wait_for(
                asyncio.gather(*self.tasks, return_exceptions=True),
                timeout=self.timeout,
            )
            logger.info("All background tasks shut down successfully")
        except asyncio.TimeoutError:
            logger.warning(
                "Timeout waiting for background tasks to shut down after %.1fs",
                self.timeout,
            )
            # Force kill remaining tasks
            for task in self.tasks:
                if not task.done():
                    logger.warning("Force killing task: %s", task.get_name())
                    task.cancel()
                    try:
                        await task
                    except asyncio.CancelledError:
                        pass

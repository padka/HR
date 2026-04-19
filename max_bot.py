import asyncio
import sys

from backend.core.messenger.bootstrap import (
    MaxRuntimeDisabledError,
    describe_max_runtime_state,
    run_max_adapter_shell,
)

_DISABLED_RUNTIME_PREFIX = "MAX bot runtime is disabled in the supported RecruitSmart runtime."


def main() -> None:
    try:
        asyncio.run(run_max_adapter_shell())
    except MaxRuntimeDisabledError:
        message = describe_max_runtime_state()
        if _DISABLED_RUNTIME_PREFIX not in message:
            message = f"{_DISABLED_RUNTIME_PREFIX} {message}".strip()
        print(message, file=sys.stderr)
        sys.exit(1)
    except Exception as exc:
        print(
            "MAX bot runtime failed to bootstrap the bounded MAX adapter shell: "
            f"{exc}",
            file=sys.stderr,
        )
        sys.exit(1)


if __name__ == "__main__":
    main()

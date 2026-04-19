"""Pure application resolver and event publisher skeletons for Phase B."""

from .contracts import (
    ApplicationCreateRequest,
    ApplicationEventCommand,
    ApplicationEventRecord,
    ApplicationEventRepository,
    ApplicationEventType,
    ApplicationRecord,
    ApplicationResolverError,
    ApplicationResolverRepository,
    ApplicationState,
    DuplicateActiveApplicationError,
    EventPublishResult,
    IdempotencyConflictError,
    ResolutionStatus,
    ResolverContext,
    ResolverContextConflictError,
    ResolverResult,
    ResolverSignal,
    ResolverSnapshot,
    StatusTransitionCommand,
)
from .events import ApplicationEventPublisher
from .repositories import (
    SqlAlchemyApplicationEventRepository,
    SqlAlchemyApplicationResolverRepository,
)
from .resolver import PrimaryApplicationResolver
from .uow import (
    ApplicationUnitOfWork,
    SqlAlchemyApplicationUnitOfWork,
    TransactionRequiredError,
)

__all__ = [
    "ApplicationCreateRequest",
    "ApplicationEventCommand",
    "ApplicationEventPublisher",
    "ApplicationEventRecord",
    "ApplicationEventRepository",
    "ApplicationEventType",
    "ApplicationUnitOfWork",
    "ApplicationRecord",
    "ApplicationResolverError",
    "ApplicationResolverRepository",
    "ApplicationState",
    "DuplicateActiveApplicationError",
    "EventPublishResult",
    "IdempotencyConflictError",
    "PrimaryApplicationResolver",
    "ResolutionStatus",
    "ResolverContext",
    "ResolverContextConflictError",
    "ResolverResult",
    "ResolverSignal",
    "ResolverSnapshot",
    "SqlAlchemyApplicationEventRepository",
    "SqlAlchemyApplicationResolverRepository",
    "SqlAlchemyApplicationUnitOfWork",
    "StatusTransitionCommand",
    "TransactionRequiredError",
]

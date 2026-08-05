import asyncio
import hashlib
import logging
import uuid
from collections.abc import Awaitable, Callable
from typing import Annotated, Any, Literal

from database.redis.redis_ops import RedisManager
from pydantic import BaseModel, ConfigDict, Field, TypeAdapter, ValidationError

logger = logging.getLogger("uvicorn.error")

WEBSOCKET_BROKER_CHANNEL = "meridian:websocket:v1"
_ORIGIN_PATTERN = r"^[0-9a-f]{32}$"
_TARGET_PATTERN = r"^[0-9a-f]{64}$"
_MAX_RECONNECT_DELAY_SECONDS = 30

Origin = Annotated[str, Field(pattern=_ORIGIN_PATTERN)]
Target = Annotated[str, Field(pattern=_TARGET_PATTERN)]
UserEventCallback = Callable[[str, dict[str, Any]], Awaitable[None]]
TaskCancelCallback = Callable[[str, str], Awaitable[None]]
SleepCallback = Callable[[float], Awaitable[None]]


class UserEventEnvelope(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    version: Literal[1]
    kind: Literal["user_event"]
    origin: Origin
    user_target: Target
    message: dict[str, Any]


class TaskCancelEnvelope(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    version: Literal[1]
    kind: Literal["task_cancel"]
    origin: Origin
    user_target: Target
    task_target: Target


BrokerEnvelope = Annotated[UserEventEnvelope | TaskCancelEnvelope, Field(discriminator="kind")]
_ENVELOPE_ADAPTER: TypeAdapter[BrokerEnvelope] = TypeAdapter(BrokerEnvelope)


def hash_broker_target(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


class RedisWebSocketBroker:
    def __init__(
        self,
        redis_manager: RedisManager,
        on_user_event: UserEventCallback,
        on_task_cancel: TaskCancelCallback,
        sleep: SleepCallback = asyncio.sleep,
    ) -> None:
        self._redis_client = redis_manager.client
        self._on_user_event = on_user_event
        self._on_task_cancel = on_task_cancel
        self._sleep = sleep
        self._origin = uuid.uuid4().hex
        self._listener_task: asyncio.Task[None] | None = None
        self._pubsub: Any | None = None
        self._first_attempt_complete = asyncio.Event()
        self._closing = False

    @property
    def origin(self) -> str:
        return self._origin

    async def start(self) -> None:
        if self._listener_task is None:
            self._listener_task = asyncio.create_task(
                self._listen_forever(), name="redis_websocket_broker"
            )
        await self._first_attempt_complete.wait()

    async def publish_user_event(self, user_target: str, message: dict[str, Any]) -> None:
        envelope = UserEventEnvelope(
            version=1,
            kind="user_event",
            origin=self._origin,
            user_target=user_target,
            message=message,
        )
        await self._publish(envelope)

    async def publish_task_cancel(self, user_target: str, task_target: str) -> None:
        envelope = TaskCancelEnvelope(
            version=1,
            kind="task_cancel",
            origin=self._origin,
            user_target=user_target,
            task_target=task_target,
        )
        await self._publish(envelope)

    async def _publish(self, envelope: UserEventEnvelope | TaskCancelEnvelope) -> None:
        try:
            await self._redis_client.publish(WEBSOCKET_BROKER_CHANNEL, envelope.model_dump_json())
        except Exception as exc:
            logger.warning("WebSocket broker publish failed (%s)", type(exc).__name__)

    async def _listen_forever(self) -> None:
        reconnect_delay = 1
        while not self._closing:
            pubsub = None
            try:
                pubsub = self._redis_client.pubsub()
                self._pubsub = pubsub
                await pubsub.subscribe(WEBSOCKET_BROKER_CHANNEL)

                async for frame in pubsub.listen():
                    if self._is_subscription_ack(frame):
                        reconnect_delay = 1
                        self._first_attempt_complete.set()
                    elif self._is_message(frame):
                        await self._dispatch(frame.get("data"))

                if not self._closing:
                    raise ConnectionError("WebSocket broker listener ended")
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                logger.warning("WebSocket broker listen failed (%s)", type(exc).__name__)
                self._first_attempt_complete.set()
            finally:
                if pubsub is not None:
                    try:
                        await pubsub.close()
                    except Exception as exc:
                        logger.warning("WebSocket broker close failed (%s)", type(exc).__name__)
                if self._pubsub is pubsub:
                    self._pubsub = None

            if not self._closing:
                await self._sleep(reconnect_delay)
                reconnect_delay = min(reconnect_delay * 2, _MAX_RECONNECT_DELAY_SECONDS)

    @staticmethod
    def _is_subscription_ack(frame: Any) -> bool:
        return (
            isinstance(frame, dict)
            and frame.get("type") == "subscribe"
            and frame.get("channel") == WEBSOCKET_BROKER_CHANNEL
        )

    @staticmethod
    def _is_message(frame: Any) -> bool:
        return (
            isinstance(frame, dict)
            and frame.get("type") == "message"
            and frame.get("channel") == WEBSOCKET_BROKER_CHANNEL
        )

    async def _dispatch(self, raw_data: Any) -> None:
        if not isinstance(raw_data, (str, bytes, bytearray)):
            return

        try:
            envelope = _ENVELOPE_ADAPTER.validate_json(raw_data)
        except (ValidationError, ValueError, TypeError):
            logger.warning("WebSocket broker dropped invalid envelope")
            return

        if envelope.origin == self._origin:
            return

        try:
            if isinstance(envelope, UserEventEnvelope):
                await self._on_user_event(envelope.user_target, envelope.message)
            else:
                await self._on_task_cancel(envelope.user_target, envelope.task_target)
        except Exception as exc:
            logger.warning(
                "WebSocket broker callback failed for %s (%s)",
                envelope.kind,
                type(exc).__name__,
            )

    async def close(self) -> None:
        self._closing = True
        task = self._listener_task
        self._listener_task = None
        if task is not None:
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
        self._pubsub = None

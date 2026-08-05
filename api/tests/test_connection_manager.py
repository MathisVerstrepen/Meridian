import asyncio
import json
import logging
import sys
from collections.abc import AsyncIterator
from pathlib import Path
from types import SimpleNamespace
from typing import Any

sys.path.append(str(Path(__file__).resolve().parents[1] / "app"))

from services.connection_manager import ConnectionManager
from services.websocket_broker import (
    WEBSOCKET_BROKER_CHANNEL,
    RedisWebSocketBroker,
    hash_broker_target,
)


class FakeWebSocket:
    def __init__(self) -> None:
        self.accepted = False
        self.messages: list[dict[str, Any]] = []
        self.message_sent = asyncio.Event()

    async def accept(self) -> None:
        self.accepted = True

    async def send_json(self, message: dict[str, Any]) -> None:
        self.messages.append(json.loads(json.dumps(message)))
        self.message_sent.set()


class FakeRedisBackend:
    def __init__(self) -> None:
        self.pubsubs: list[FakePubSub] = []
        self.published: list[tuple[str, str]] = []
        self.fail_publish = False

    async def publish(self, channel: str, payload: str) -> int:
        if self.fail_publish:
            raise ConnectionError("raw-user raw-node broker-body")
        self.published.append((channel, payload))
        subscribers = [pubsub for pubsub in self.pubsubs if pubsub.subscribed and not pubsub.closed]
        for pubsub in subscribers:
            await pubsub.frames.put({"type": "message", "channel": channel, "data": payload})
        return len(subscribers)


class FakePubSub:
    def __init__(self, backend: FakeRedisBackend, auto_ack: bool = True) -> None:
        self.backend = backend
        self.auto_ack = auto_ack
        self.frames: asyncio.Queue[Any] = asyncio.Queue()
        self.subscribed = False
        self.closed = False
        self.subscribe_called = asyncio.Event()
        self._consumed = 0
        self._consumed_changed = asyncio.Condition()
        backend.pubsubs.append(self)

    async def subscribe(self, channel: str) -> None:
        self.subscribed = True
        self.subscribe_called.set()
        if self.auto_ack:
            await self.acknowledge(channel)

    async def acknowledge(self, channel: str = WEBSOCKET_BROKER_CHANNEL) -> None:
        await self.frames.put({"type": "subscribe", "channel": channel, "data": 1})

    async def listen(self) -> AsyncIterator[Any]:
        while True:
            frame = await self.frames.get()
            if isinstance(frame, BaseException):
                raise frame
            yield frame
            async with self._consumed_changed:
                self._consumed += 1
                self._consumed_changed.notify_all()

    async def wait_consumed(self, count: int) -> None:
        async with self._consumed_changed:
            await self._consumed_changed.wait_for(lambda: self._consumed >= count)

    async def close(self) -> None:
        self.closed = True
        self.subscribed = False


class FakeRedisClient:
    def __init__(self, backend: FakeRedisBackend, *, auto_ack: bool = True) -> None:
        self.backend = backend
        self.auto_ack = auto_ack
        self.pubsub_failures = 0
        self.pubsub_created = asyncio.Event()

    def pubsub(self) -> FakePubSub:
        if self.pubsub_failures:
            self.pubsub_failures -= 1
            raise ConnectionError("raw-user raw-node broker-body")
        pubsub = FakePubSub(self.backend, auto_ack=self.auto_ack)
        self.pubsub_created.set()
        return pubsub

    async def publish(self, channel: str, payload: str) -> int:
        return await self.backend.publish(channel, payload)


def redis_manager(client: FakeRedisClient) -> Any:
    return SimpleNamespace(client=client)


async def close_managers(managers: list[ConnectionManager]) -> None:
    await asyncio.gather(*(manager.close() for manager in managers))


def test_websocket_broker_waits_for_subscription_ack_and_closes() -> None:
    async def scenario() -> None:
        backend = FakeRedisBackend()
        client = FakeRedisClient(backend, auto_ack=False)

        async def on_user_event(_user_target: str, _message: dict[str, Any]) -> None:
            pass

        async def on_task_cancel(_user_target: str, _task_target: str) -> None:
            pass

        broker = RedisWebSocketBroker(redis_manager(client), on_user_event, on_task_cancel)
        start_task = asyncio.create_task(broker.start())
        await client.pubsub_created.wait()
        pubsub = backend.pubsubs[0]
        await pubsub.subscribe_called.wait()
        assert not start_task.done()

        await pubsub.acknowledge()
        await start_task
        await broker.close()

        assert pubsub.closed
        assert broker._listener_task is None

    asyncio.run(scenario())


def test_websocket_broker_validates_frames_and_continues() -> None:
    async def scenario() -> None:
        backend = FakeRedisBackend()
        client = FakeRedisClient(backend)
        received: list[tuple[str, dict[str, Any]]] = []
        received_event = asyncio.Event()
        callback_failed = asyncio.Event()

        async def on_user_event(user_target: str, message: dict[str, Any]) -> None:
            if message.get("type") == "callback_failure":
                callback_failed.set()
                raise RuntimeError("broker-body")
            received.append((user_target, message))
            received_event.set()

        async def on_task_cancel(_user_target: str, _task_target: str) -> None:
            raise AssertionError("unexpected cancellation")

        broker = RedisWebSocketBroker(redis_manager(client), on_user_event, on_task_cancel)
        await broker.start()
        target = hash_broker_target("user-1")
        invalid_payloads = [
            "not-json",
            json.dumps({"version": 2, "kind": "user_event"}),
            json.dumps(
                {
                    "version": 1,
                    "kind": "user_event",
                    "origin": "f" * 32,
                    "user_target": target,
                    "message": {},
                    "extra": True,
                }
            ),
        ]
        for payload in invalid_payloads:
            await backend.publish(WEBSOCKET_BROKER_CHANNEL, payload)
        await backend.publish(
            WEBSOCKET_BROKER_CHANNEL,
            json.dumps(
                {
                    "version": 1,
                    "kind": "user_event",
                    "origin": "f" * 32,
                    "user_target": target,
                    "message": {"type": "callback_failure"},
                }
            ),
        )
        await backend.publish(
            WEBSOCKET_BROKER_CHANNEL,
            json.dumps(
                {
                    "version": 1,
                    "kind": "user_event",
                    "origin": "f" * 32,
                    "user_target": target,
                    "message": {"type": "node_data_replace", "payload": {"name": "é"}},
                }
            ),
        )

        await callback_failed.wait()
        await received_event.wait()
        assert received == [(target, {"type": "node_data_replace", "payload": {"name": "é"}})]
        await broker.close()

    asyncio.run(scenario())


def test_websocket_broker_start_failure_is_ready_and_reconnects() -> None:
    async def scenario() -> None:
        backend = FakeRedisBackend()
        client = FakeRedisClient(backend)
        client.pubsub_failures = 1
        backoff_started = asyncio.Event()
        release_backoff = asyncio.Event()
        delays: list[float] = []

        async def controlled_sleep(delay: float) -> None:
            delays.append(delay)
            backoff_started.set()
            await release_backoff.wait()

        async def on_user_event(_user_target: str, _message: dict[str, Any]) -> None:
            pass

        async def on_task_cancel(_user_target: str, _task_target: str) -> None:
            pass

        broker = RedisWebSocketBroker(
            redis_manager(client), on_user_event, on_task_cancel, sleep=controlled_sleep
        )
        await broker.start()
        await backoff_started.wait()
        assert delays == [1]

        release_backoff.set()
        await client.pubsub_created.wait()
        pubsub = backend.pubsubs[0]
        await pubsub.wait_consumed(1)
        assert pubsub.subscribed

        await broker.close()
        assert pubsub.closed

    asyncio.run(scenario())


def test_connection_manager_four_worker_fanout_is_exact_and_isolated() -> None:
    async def scenario() -> None:
        backend = FakeRedisBackend()
        managers = [ConnectionManager() for _ in range(4)]
        clients = [FakeRedisClient(backend) for _ in managers]
        for manager, client in zip(managers, clients):
            await manager.start(redis_manager(client))
        await managers[0].start(redis_manager(clients[0]))
        assert len(backend.pubsubs) == 4

        sockets = [FakeWebSocket() for _ in range(6)]
        await managers[0].connect(sockets[0], "client-0", "target-user")
        await managers[0].connect(sockets[1], "client-1", "target-user")
        await managers[1].connect(sockets[2], "client-2", "target-user")
        await managers[2].connect(sockets[3], "client-3", "other-user")
        await managers[3].connect(sockets[4], "client-4", "target-user")
        await managers[3].connect(sockets[5], "client-5", None)

        message = {
            "type": "image_generation_job_update",
            "payload": {"prompt": "draw 🌊", "source_image_ids": ["one", "two"]},
        }
        await managers[0].send_to_user("target-user", message)
        await asyncio.gather(
            sockets[0].message_sent.wait(),
            sockets[1].message_sent.wait(),
            sockets[2].message_sent.wait(),
            sockets[4].message_sent.wait(),
        )
        await asyncio.gather(*(pubsub.wait_consumed(2) for pubsub in backend.pubsubs))

        for socket in (sockets[0], sockets[1], sockets[2], sockets[4]):
            assert socket.messages == [message]
        assert sockets[3].messages == []
        assert sockets[5].messages == []

        assert len(backend.published) == 1
        channel, raw_envelope = backend.published[0]
        envelope = json.loads(raw_envelope)
        assert channel == WEBSOCKET_BROKER_CHANNEL
        assert envelope["message"] == message
        assert envelope["user_target"] == hash_broker_target("target-user")
        assert "target-user" not in raw_envelope

        await close_managers(managers)
        assert all(pubsub.closed for pubsub in backend.pubsubs)

    asyncio.run(scenario())


def test_connection_manager_routes_remote_cancellation_and_removes_task() -> None:
    async def scenario() -> None:
        backend = FakeRedisBackend()
        owner = ConnectionManager()
        caller = ConnectionManager()
        await owner.start(redis_manager(FakeRedisClient(backend)))
        await caller.start(redis_manager(FakeRedisClient(backend)))
        running = asyncio.Event()
        cancelled = asyncio.Event()

        async def stream() -> None:
            running.set()
            try:
                await asyncio.Event().wait()
            except asyncio.CancelledError:
                cancelled.set()
                raise

        task = asyncio.create_task(stream())
        await running.wait()
        owner.add_task(task, "raw-user", "raw-node")

        assert await caller.cancel_task("raw-user", "raw-node") is False
        await cancelled.wait()
        await backend.pubsubs[0].wait_consumed(2)

        assert task.cancelled()
        assert owner.active_tasks == {}
        _, raw_envelope = backend.published[0]
        assert "raw-user" not in raw_envelope
        assert "raw-node" not in raw_envelope
        assert json.loads(raw_envelope)["task_target"] == hash_broker_target("raw-node")

        await close_managers([owner, caller])

    asyncio.run(scenario())


def test_connection_manager_local_only_and_publish_failure_fall_back(caplog: Any) -> None:
    async def scenario() -> None:
        local_manager = ConnectionManager()
        local_socket = FakeWebSocket()
        await local_manager.connect(local_socket, "local-client", "user")
        await local_manager.send_to_user("user", {"type": "local"})
        assert local_socket.messages == [{"type": "local"}]

        local_task_started = asyncio.Event()

        async def local_stream() -> None:
            local_task_started.set()
            await asyncio.Event().wait()

        local_task = asyncio.create_task(local_stream())
        await local_task_started.wait()
        local_manager.add_task(local_task, "user", "node")
        assert await local_manager.cancel_task("user", "node") is True
        assert local_task.cancelled()

        backend = FakeRedisBackend()
        manager = ConnectionManager()
        await manager.start(redis_manager(FakeRedisClient(backend)))
        socket = FakeWebSocket()
        await manager.connect(socket, "client", "user")
        backend.fail_publish = True

        with caplog.at_level(logging.WARNING, logger="uvicorn.error"):
            await manager.send_to_user("user", {"type": "still-local"})
        assert socket.messages == [{"type": "still-local"}]
        assert "ConnectionError" in caplog.text
        assert "raw-user" not in caplog.text
        assert "raw-node" not in caplog.text
        assert "broker-body" not in caplog.text
        assert "still-local" not in caplog.text

        await close_managers([local_manager, manager])

    asyncio.run(scenario())

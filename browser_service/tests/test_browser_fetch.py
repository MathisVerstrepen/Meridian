import asyncio
from types import SimpleNamespace

import pytest

from browser_service.app import browser_fetch
from browser_service.app.models import BrowserFetchError, FailureReason


def test_four_active_eight_waiters_and_cancellation_before_submission() -> None:
    manager = browser_fetch.BrowserFetchManager()
    submitted = []
    futures = []

    async def fake_submit(url: str, key: str, ownership):
        submitted.append((url, key))
        future = asyncio.get_running_loop().create_future()
        futures.append(future)
        ownership.future = future
        ownership.enqueue_started = True
        return future

    manager._submit = fake_submit  # type: ignore[method-assign]

    async def scenario() -> None:
        calls = [
            asyncio.create_task(manager.fetch(f"https://example.com/{index}"))
            for index in range(12)
        ]
        while len(submitted) < 4 or manager.waiting_count < 8:
            await asyncio.sleep(0)
        assert manager.active_count == 4
        assert manager.waiting_count == 8
        with pytest.raises(BrowserFetchError) as captured:
            await manager.fetch("https://example.com/full")
        assert captured.value.reason is FailureReason.CONNECTIVITY_EXHAUSTED

        calls[4].cancel()
        with pytest.raises(asyncio.CancelledError):
            await calls[4]
        assert len(submitted) == 4
        assert manager.waiting_count == 7

        futures[0].set_result("done")
        await manager._release()
        assert await calls[0] == "done"
        while len(submitted) < 5:
            await asyncio.sleep(0)

        # Cancellation after admission does not release a fifth active permit.
        calls[5].cancel()
        with pytest.raises(asyncio.CancelledError):
            await calls[5]
        assert manager.active_count == 4

        for call in calls:
            call.cancel()
        await asyncio.gather(*calls, return_exceptions=True)

    asyncio.run(scenario())


class FakeRouter:
    def default_handler(self, handler):
        self.handler = handler
        return handler


class FakeCrawler:
    def __init__(self, **kwargs) -> None:
        self.kwargs = kwargs
        self.router = FakeRouter()
        self.stopped = asyncio.Event()
        self.added = []

    def failed_request_handler(self, handler):
        self.failed_handler = handler
        return handler

    def on_skipped_request(self, handler):
        self.skipped_handler = handler
        return handler

    async def run(self, requests, purge_request_queue=True):
        await self.stopped.wait()

    async def add_requests(self, requests, **kwargs):
        self.added.extend(requests)

    def stop(self):
        self.stopped.set()


def test_crawler_uses_early_navigation_four_slots_and_zero_retries() -> None:
    crawlers = []

    def crawler_factory(**kwargs):
        crawler = FakeCrawler(**kwargs)
        crawlers.append(crawler)
        return crawler

    manager = browser_fetch.BrowserFetchManager(
        crawler_factory=crawler_factory,
        plugin_factory=lambda **kwargs: SimpleNamespace(proxy_enabled=False),
        browser_pool_factory=lambda **kwargs: SimpleNamespace(kwargs=kwargs),
        storage_factory=object,
    )

    async def scenario() -> None:
        async with manager._lifecycle_lock:
            manager._new_generation_locked()
        await manager.close()

    asyncio.run(scenario())
    kwargs = crawlers[0].kwargs
    concurrency = kwargs["concurrency_settings"]
    assert kwargs["goto_options"] == {"wait_until": "domcontentloaded"}
    assert concurrency.min_concurrency == concurrency.desired_concurrency == 4
    assert concurrency.max_concurrency == 4
    assert kwargs["max_request_retries"] == 0
    assert kwargs["max_session_rotations"] == 0
    assert kwargs["use_session_pool"] is False


def test_only_structural_failures_invalidate() -> None:
    assert not browser_fetch.BrowserFetchManager._is_structural(RuntimeError("dns failure"))
    assert browser_fetch.BrowserFetchManager._is_structural(
        browser_fetch.TargetClosedError("closed")
    )


def test_target_closed_diagnostic_read_retires_generation() -> None:
    manager = browser_fetch.BrowserFetchManager(
        crawler_factory=FakeCrawler,
        plugin_factory=lambda **kwargs: SimpleNamespace(proxy_enabled=False),
        browser_pool_factory=lambda **kwargs: SimpleNamespace(),
        storage_factory=object,
    )

    class ClosedPage:
        url = "https://example.com/closed"

        async def content(self):
            raise browser_fetch.TargetClosedError("closed")

    async def scenario() -> None:
        generation = manager._new_generation_locked()
        future = asyncio.get_running_loop().create_future()
        key = "closed"
        url = "https://example.com/closed"
        manager._pending[key] = browser_fetch._PendingRequest(generation.id, future, url)
        generation.pending_keys.add(key)
        generation.queued_keys_by_url[url][key] = None
        manager._active = 1
        context = SimpleNamespace(
            request=SimpleNamespace(unique_key=key, url=url),
            response=SimpleNamespace(status=403, url=url),
            page=ClosedPage(),
        )
        await manager._handle_request(generation, context)
        assert generation.stopping
        with pytest.raises(BrowserFetchError):
            await future
        while manager._retiring:
            await asyncio.sleep(0)
        assert manager._generation is None
        assert manager.active_count == 0
        await manager.close()

    asyncio.run(scenario())


@pytest.mark.parametrize(
    "headers",
    [
        {"server": "Varnish", "retry-after": "0", "x-cache": "MISS"},
        {"server": "snooserv", "via": "1.1 varnish", "retry-after": "0"},
    ],
)
def test_non_evidence_403_is_rejected_without_wait_or_reload(headers) -> None:
    manager = browser_fetch.BrowserFetchManager(
        crawler_factory=FakeCrawler,
        plugin_factory=lambda **kwargs: SimpleNamespace(proxy_enabled=False),
        browser_pool_factory=lambda **kwargs: SimpleNamespace(),
        storage_factory=object,
    )

    class OrdinaryDeniedPage:
        url = "https://denied.example/article"

        async def content(self):
            return "<html><body>Ordinary permission denial</body></html>"

        async def wait_for_function(self, *args, **kwargs):
            raise AssertionError("challenge wait must not run")

        async def reload(self, **kwargs):
            raise AssertionError("challenge reload must not run")

    class Response:
        status = 403
        url = OrdinaryDeniedPage.url

        async def all_headers(self):
            return headers

    async def scenario() -> None:
        generation = manager._new_generation_locked()
        future = asyncio.get_running_loop().create_future()
        key = "denied"
        url = OrdinaryDeniedPage.url
        manager._pending[key] = browser_fetch._PendingRequest(generation.id, future, url)
        generation.pending_keys.add(key)
        generation.queued_keys_by_url[url][key] = None
        manager._active = 1
        context = SimpleNamespace(
            request=SimpleNamespace(unique_key=key, url=url),
            response=Response(),
            page=OrdinaryDeniedPage(),
        )
        await manager._handle_request(generation, context)
        with pytest.raises(BrowserFetchError) as captured:
            await future
        assert captured.value.reason is FailureReason.HTTP_REJECTED
        assert captured.value.status_code == 403
        assert manager._generation is generation and not generation.stopping
        assert manager.active_count == 0
        await manager.close()

    asyncio.run(scenario())


def test_request_local_failure_preserves_generation_and_unrelated_request() -> None:
    crawlers = []

    def crawler_factory(**kwargs):
        crawler = FakeCrawler(**kwargs)
        crawlers.append(crawler)
        return crawler

    manager = browser_fetch.BrowserFetchManager(
        crawler_factory=crawler_factory,
        plugin_factory=lambda **kwargs: SimpleNamespace(proxy_enabled=False),
        browser_pool_factory=lambda **kwargs: SimpleNamespace(),
        storage_factory=object,
    )

    async def scenario() -> None:
        generation = manager._new_generation_locked()
        manager._active = 2
        first = asyncio.get_running_loop().create_future()
        second = asyncio.get_running_loop().create_future()
        for key, future, url in (
            ("first", first, "https://bad.example"),
            ("second", second, "https://good.example"),
        ):
            manager._pending[key] = browser_fetch._PendingRequest(generation.id, future, url)
            generation.pending_keys.add(key)
            generation.queued_keys_by_url[url][key] = None
        context = SimpleNamespace(request=SimpleNamespace(unique_key="first"))
        await crawlers[0].failed_handler(context, RuntimeError("dns failure"))
        with pytest.raises(BrowserFetchError):
            await first
        assert manager._generation is generation
        assert not second.done()
        await manager._complete(generation, "second", result="ok")
        assert await second == "ok"
        await manager.close()

    asyncio.run(scenario())
    assert browser_fetch.BrowserFetchManager._is_structural(
        browser_fetch._CamoufoxLaunchError("sanitized")
    )


def test_scoped_pending_cleanup_touches_only_own_url_bucket() -> None:
    manager = browser_fetch.BrowserFetchManager()
    future = asyncio.new_event_loop().create_future()
    generation = browser_fetch._CrawlerGeneration("g", None, None, None)
    manager._pending["key"] = browser_fetch._PendingRequest("g", future, "https://one")
    generation.pending_keys.add("key")
    generation.queued_keys_by_url["https://one"]["key"] = None
    untouched = {"other": None}
    generation.queued_keys_by_url["https://two"] = untouched
    manager._drop_pending(generation, "key")
    assert generation.queued_keys_by_url == {"https://two": untouched}
    future.get_loop().close()


def test_dead_generation_atomically_fails_pending_and_restarts() -> None:
    crawlers = []

    def crawler_factory(**kwargs):
        crawler = FakeCrawler(**kwargs)
        crawlers.append(crawler)
        return crawler

    manager = browser_fetch.BrowserFetchManager(
        crawler_factory=crawler_factory,
        plugin_factory=lambda **kwargs: SimpleNamespace(proxy_enabled=False),
        browser_pool_factory=lambda **kwargs: SimpleNamespace(),
        storage_factory=object,
    )

    async def scenario() -> None:
        old = manager._new_generation_locked()
        old_future = asyncio.get_running_loop().create_future()
        manager._pending["old"] = browser_fetch._PendingRequest(
            old.id, old_future, "https://old.example"
        )
        old.pending_keys.add("old")
        old.queued_keys_by_url["https://old.example"]["old"] = None
        manager._active = 1
        old.crawler.stop()
        await old.task

        fetch_task = asyncio.create_task(manager.fetch("https://new.example"))
        while len(crawlers) < 2 or not crawlers[1].added:
            await asyncio.sleep(0)
        replacement = manager._generation
        assert replacement is not None and replacement is not old
        new_key = str(crawlers[1].added[0].unique_key)
        await manager._complete(replacement, new_key, result="restarted")

        with pytest.raises(BrowserFetchError):
            await old_future
        assert await fetch_task == "restarted"
        assert manager.active_count == 0
        assert not manager._retiring
        await manager.close()

    asyncio.run(scenario())


def test_completed_retirement_is_pruned_before_callback_cleanup_without_spin() -> None:
    crawlers = []

    def crawler_factory(**kwargs):
        crawler = FakeCrawler(**kwargs)
        crawlers.append(crawler)
        return crawler

    manager = browser_fetch.BrowserFetchManager(
        crawler_factory=crawler_factory,
        plugin_factory=lambda **kwargs: SimpleNamespace(proxy_enabled=False),
        browser_pool_factory=lambda **kwargs: SimpleNamespace(),
        storage_factory=object,
    )

    async def scenario() -> None:
        completed = asyncio.create_task(asyncio.sleep(0))
        await completed
        manager._retiring["retired"] = completed
        allow_callback_cleanup = asyncio.Event()

        async def delayed_callback_cleanup() -> None:
            await allow_callback_cleanup.wait()
            if manager._retiring.get("retired") is completed:
                manager._retiring.pop("retired", None)

        cleanup = asyncio.create_task(delayed_callback_cleanup())
        original_lock = manager._lifecycle_lock

        class SpinDetectingLock:
            immediate_completed_entries = 0

            async def __aenter__(self):
                await original_lock.acquire()
                if manager._retiring.get("retired") is completed:
                    self.immediate_completed_entries += 1
                    if self.immediate_completed_entries > 1:
                        original_lock.release()
                        raise AssertionError("completed retirement was selected repeatedly")
                return self

            async def __aexit__(self, exc_type, exc, traceback):
                original_lock.release()

        lock = SpinDetectingLock()
        manager._lifecycle_lock = lock  # type: ignore[assignment]
        fetch_task = asyncio.create_task(manager.fetch("https://replacement.example"))
        while not crawlers or not crawlers[0].added:
            if fetch_task.done():
                await fetch_task
            await asyncio.sleep(0)

        assert lock.immediate_completed_entries == 1
        assert not cleanup.done()
        assert "retired" not in manager._retiring
        generation = manager._generation
        assert generation is not None
        key = str(crawlers[0].added[0].unique_key)
        await manager._complete(generation, key, result="replacement-ready")
        assert await fetch_task == "replacement-ready"

        allow_callback_cleanup.set()
        await cleanup
        await manager.close()

    asyncio.run(scenario())


class PartialSubmissionCrawler(FakeCrawler):
    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self.enqueue_started = asyncio.Event()
        self.stop_called = asyncio.Event()
        self.allow_stop = asyncio.Event()
        self.allow_submission = asyncio.Event()
        self.navigation_count = 0
        self.accepted = {}

    async def add_requests(self, requests, **kwargs):
        self.added.extend(requests)
        self.accepted[str(requests[0].unique_key)] = requests[0]
        self.enqueue_started.set()
        await self.allow_submission.wait()

    async def get_request_manager(self):
        return self

    async def get_request(self, key):
        return self.accepted.get(key)

    def stop(self):
        self.stop_called.set()

    async def run(self, requests, purge_request_queue=True):
        await self.allow_stop.wait()


def test_cancellation_during_submission_is_request_local() -> None:
    crawlers = []

    def crawler_factory(**kwargs):
        crawler = PartialSubmissionCrawler(**kwargs)
        crawlers.append(crawler)
        return crawler

    manager = browser_fetch.BrowserFetchManager(
        crawler_factory=crawler_factory,
        plugin_factory=lambda **kwargs: SimpleNamespace(proxy_enabled=False),
        browser_pool_factory=lambda **kwargs: SimpleNamespace(),
        storage_factory=object,
    )

    async def scenario() -> None:
        first_call = asyncio.create_task(manager.fetch("https://first.example"))
        while not crawlers:
            await asyncio.sleep(0)
        crawler = crawlers[0]
        await crawler.enqueue_started.wait()
        crawler.allow_submission.set()
        while len(crawler.added) < 1 or manager._submission_tasks:
            await asyncio.sleep(0)

        crawler.allow_submission.clear()
        crawler.enqueue_started.clear()
        second_call = asyncio.create_task(manager.fetch("https://second.example"))
        await crawler.enqueue_started.wait()
        generation = manager._generation
        assert generation is not None
        second_call.cancel()
        with pytest.raises(asyncio.CancelledError):
            await second_call
        assert manager.active_count == 2
        assert manager._generation is generation and not generation.stopping
        assert not manager._retiring and not crawler.stop_called.is_set()
        assert not first_call.done()

        crawler.allow_submission.set()
        while manager._submission_tasks:
            await asyncio.sleep(0)
        first_key = str(crawler.added[0].unique_key)
        second_key = str(crawler.added[1].unique_key)
        await manager._complete(generation, first_key, result="first-ok")
        assert await first_call == "first-ok"
        assert manager.active_count == 1
        await manager._complete(generation, second_key, result="abandoned-ok")
        await asyncio.sleep(0)
        assert manager.active_count == 0
        assert manager._generation is generation and not generation.stopping
        assert not manager._pending and not generation.submission_tasks
        assert crawler.navigation_count == 0
        crawler.allow_stop.set()
        await manager.close()

    asyncio.run(scenario())


class AbsentSubmissionCrawler(FakeCrawler):
    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self.submission_started = asyncio.Event()
        self.accepted = {}

    async def add_requests(self, requests, **kwargs):
        key = str(requests[0].unique_key)
        if not self.accepted:
            self.added.extend(requests)
            self.accepted[key] = requests[0]
            return
        self.submission_started.set()
        await asyncio.Event().wait()

    async def get_request_manager(self):
        return self

    async def get_request(self, key):
        return self.accepted.get(key)


def test_submission_timeout_releases_only_positively_absent_request(monkeypatch) -> None:
    crawlers = []
    monkeypatch.setattr(browser_fetch, "REQUEST_SUBMISSION_TIMEOUT_SECONDS", 0.01)

    def crawler_factory(**kwargs):
        crawler = AbsentSubmissionCrawler(**kwargs)
        crawlers.append(crawler)
        return crawler

    manager = browser_fetch.BrowserFetchManager(
        crawler_factory=crawler_factory,
        plugin_factory=lambda **kwargs: SimpleNamespace(proxy_enabled=False),
        browser_pool_factory=lambda **kwargs: SimpleNamespace(),
        storage_factory=object,
    )

    async def scenario() -> None:
        first_call = asyncio.create_task(manager.fetch("https://first.example"))
        while not crawlers or not crawlers[0].added:
            await asyncio.sleep(0)
        crawler = crawlers[0]
        generation = manager._generation
        assert generation is not None
        second_call = asyncio.create_task(manager.fetch("https://absent.example"))
        await crawler.submission_started.wait()
        with pytest.raises(BrowserFetchError) as captured:
            await second_call
        assert captured.value.reason is FailureReason.BROWSER_FAILED
        assert manager.active_count == 1
        assert manager._generation is generation and not generation.stopping
        assert not manager._retiring and not crawler.stopped.is_set()

        first_key = str(crawler.added[0].unique_key)
        await manager._complete(generation, first_key, result="first-ok")
        assert await first_call == "first-ok"
        assert manager.active_count == 0
        assert not manager._pending and not manager._submission_tasks
        await manager.close()

    asyncio.run(scenario())


def test_replacement_waits_for_retirement_and_close_awaits_retiring_stop() -> None:
    crawlers = []

    def crawler_factory(**kwargs):
        crawler = PartialSubmissionCrawler(**kwargs)
        crawlers.append(crawler)
        return crawler

    manager = browser_fetch.BrowserFetchManager(
        crawler_factory=crawler_factory,
        plugin_factory=lambda **kwargs: SimpleNamespace(proxy_enabled=False),
        browser_pool_factory=lambda **kwargs: SimpleNamespace(),
        storage_factory=object,
    )

    async def scenario() -> None:
        generation = manager._new_generation_locked()
        await manager._invalidate_generation(generation)
        await generation.crawler.stop_called.wait()

        replacement_call = asyncio.create_task(manager.fetch("https://replacement.example"))
        await asyncio.sleep(0)
        assert len(crawlers) == 1
        assert manager.active_count == 1

        close_task = asyncio.create_task(manager.close())
        await asyncio.sleep(0)
        assert not close_task.done()
        assert len(crawlers) == 1

        generation.crawler.allow_stop.set()
        await close_task
        with pytest.raises(BrowserFetchError):
            await replacement_call
        assert not manager._retiring
        assert manager.active_count == 0

    asyncio.run(scenario())

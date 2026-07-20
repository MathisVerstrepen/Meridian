import asyncio
import logging
import sys
from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import timedelta
from functools import partial
from typing import Any, Callable
from uuid import uuid4

from crawlee import ConcurrencySettings, Request
from crawlee.browsers import BrowserPool
from crawlee.crawlers import PlaywrightCrawler
from crawlee.storage_clients import MemoryStorageClient
from playwright._impl._errors import TargetClosedError
from playwright.async_api import TimeoutError as PlaywrightTimeoutError

from .browser_challenge import (
    is_browser_challenge,
    resolve_browser_challenge,
    response_headers,
    safe_page_content,
)
from .camoufox_runtime import (
    BrowserProxyConfig,
    CamoufoxPlugin,
    _CamoufoxLaunchError,
    silent_crawlee_logger,
)
from .diagnostics import response_diagnostics
from .models import BrowserFetchError, FailureReason

logger = logging.getLogger("uvicorn.error")
ACTIVE_CAPACITY = 4
QUEUE_CAPACITY = 8
REQUEST_SUBMISSION_TIMEOUT_SECONDS = 5
BROWSER_POOL_OPERATION_TIMEOUT_SECONDS = 45
NAVIGATION_TIMEOUT_SECONDS = 15
REQUEST_HANDLER_TIMEOUT_SECONDS = 35
FETCH_TOTAL_TIMEOUT_SECONDS = 90
SHUTDOWN_TIMEOUT_SECONDS = 20


class AdmissionQueueFullError(BrowserFetchError):
    def __init__(self) -> None:
        super().__init__(FailureReason.CONNECTIVITY_EXHAUSTED)


@dataclass
class _PendingRequest:
    generation_id: str
    future: asyncio.Future[str]
    url: str


@dataclass
class _SubmissionOwnership:
    future: asyncio.Future[str] | None = None
    enqueue_started: bool = False


@dataclass
class _CrawlerGeneration:
    id: str
    crawler: Any
    plugin: Any
    storage: Any
    task: asyncio.Task[Any] | None = None
    stopping: bool = False
    pending_keys: set[str] = field(default_factory=set)
    submission_tasks: dict[str, asyncio.Task[None]] = field(default_factory=dict)
    queued_keys_by_url: dict[str, dict[str, None]] = field(
        default_factory=lambda: defaultdict(dict)
    )


class BrowserFetchManager:
    def __init__(
        self,
        proxy_config: BrowserProxyConfig | None = None,
        crawler_factory: Callable[..., Any] = PlaywrightCrawler,
        plugin_factory: Callable[..., Any] = CamoufoxPlugin,
        browser_pool_factory: Callable[..., Any] = BrowserPool,
        storage_factory: Callable[[], Any] = MemoryStorageClient,
        request_factory: Callable[..., Any] = Request.from_url,
        uuid_factory: Callable[[], Any] = uuid4,
    ) -> None:
        self._proxy_config = proxy_config
        self._crawler_factory = crawler_factory
        self._plugin_factory = plugin_factory
        self._browser_pool_factory = browser_pool_factory
        self._storage_factory = storage_factory
        self._request_factory = request_factory
        self._uuid_factory = uuid_factory
        self._lifecycle_lock = asyncio.Lock()
        self._admission_lock = asyncio.Lock()
        self._generation: _CrawlerGeneration | None = None
        self._retiring: dict[str, asyncio.Task[None]] = {}
        self._pending: dict[str, _PendingRequest] = {}
        self._active = 0
        self._waiters: deque[asyncio.Future[None]] = deque()
        self._monitor_tasks: set[asyncio.Task[None]] = set()
        self._submission_tasks: set[asyncio.Task[None]] = set()
        self._closed = False

    @property
    def active_count(self) -> int:
        return self._active

    @property
    def waiting_count(self) -> int:
        return len(self._waiters)

    async def fetch(self, url: str) -> str:
        admitted = False
        ownership = _SubmissionOwnership()
        key = str(self._uuid_factory())
        try:
            async with asyncio.timeout(FETCH_TOTAL_TIMEOUT_SECONDS):
                await self._acquire()
                admitted = True
                future = await self._submit(url, key, ownership)
                return await asyncio.shield(future)
        except asyncio.CancelledError:
            self._consume_later(ownership.future)
            raise
        except TimeoutError:
            self._consume_later(ownership.future)
            raise BrowserFetchError(FailureReason.CONNECTIVITY_EXHAUSTED) from None
        except BrowserFetchError:
            self._consume_later(ownership.future)
            raise
        except Exception:
            self._consume_later(ownership.future)
            raise BrowserFetchError(FailureReason.BROWSER_FAILED) from None
        finally:
            # Once enqueue starts, retirement or a crawler callback owns the slot.
            if admitted and not ownership.enqueue_started:
                await self._release()

    @classmethod
    def _consume_later(cls, future: asyncio.Future[str] | None) -> None:
        if future is not None:
            future.add_done_callback(cls._consume_abandoned_future)

    @staticmethod
    def _consume_abandoned_future(future: asyncio.Future[str]) -> None:
        if not future.cancelled():
            future.exception()

    async def _acquire(self) -> None:
        waiter: asyncio.Future[None] | None = None
        async with self._admission_lock:
            if self._closed:
                raise BrowserFetchError(FailureReason.BROWSER_FAILED)
            if self._active < ACTIVE_CAPACITY:
                self._active += 1
                return
            if len(self._waiters) >= QUEUE_CAPACITY:
                raise AdmissionQueueFullError()
            waiter = asyncio.get_running_loop().create_future()
            self._waiters.append(waiter)
        try:
            await waiter
        except BaseException:
            async with self._admission_lock:
                try:
                    self._waiters.remove(waiter)
                except ValueError:
                    # A released waiter owns an active slot even if cancellation races wakeup.
                    if waiter.done() and not waiter.cancelled():
                        self._release_locked()
            raise

    async def _release(self) -> None:
        async with self._admission_lock:
            self._release_locked()

    def _release_locked(self) -> None:
        while self._waiters:
            waiter = self._waiters.popleft()
            if not waiter.done():
                waiter.set_result(None)
                return
        self._active = max(0, self._active - 1)

    async def _submit(
        self, url: str, key: str, ownership: _SubmissionOwnership
    ) -> asyncio.Future[str]:
        while True:
            retirement: asyncio.Task[None] | None = None
            submission: asyncio.Task[None] | None = None
            future: asyncio.Future[str] | None = None
            async with self._lifecycle_lock:
                if self._closed:
                    raise BrowserFetchError(FailureReason.BROWSER_FAILED)
                generation = self._generation
                if generation is not None and (
                    generation.stopping or generation.task is None or generation.task.done()
                ):
                    retirement = self._begin_retirement_locked(generation)
                elif generation is None:
                    self._prune_completed_retirements_locked()
                    if self._retiring:
                        retirement = next(iter(self._retiring.values()))
                    else:
                        generation = self._new_generation_locked()
                else:
                    assert generation is not None
                if retirement is None:
                    assert generation is not None
                    try:
                        request = self._request_factory(url, unique_key=key)
                    except Exception:
                        raise BrowserFetchError(FailureReason.BROWSER_FAILED) from None
                    future = asyncio.get_running_loop().create_future()
                    ownership.future = future
                    self._pending[key] = _PendingRequest(generation.id, future, url)
                    generation.pending_keys.add(key)
                    generation.queued_keys_by_url[url][key] = None
                    # Crawlee may make a request runnable before add_requests returns. The
                    # manager-owned task keeps this key's accounting alive if its caller
                    # disconnects or reaches the total request deadline.
                    ownership.enqueue_started = True
                    submission = asyncio.create_task(self._run_submission(generation, key, request))
                    generation.submission_tasks[key] = submission
                    self._submission_tasks.add(submission)
                    submission.add_done_callback(partial(self._submission_done, generation, key))
            if retirement is not None:
                await asyncio.shield(retirement)
                continue
            assert submission is not None and future is not None
            try:
                await asyncio.shield(submission)
            except asyncio.CancelledError:
                if not submission.cancelled():
                    raise
            return future

    def _prune_completed_retirements_locked(self) -> None:
        for generation_id, task in tuple(self._retiring.items()):
            if not task.done() or self._retiring.get(generation_id) is not task:
                continue
            self._retiring.pop(generation_id, None)
            if not task.cancelled():
                task.exception()

    async def _run_submission(self, generation: _CrawlerGeneration, key: str, request: Any) -> None:
        try:
            await asyncio.wait_for(
                generation.crawler.add_requests(
                    [request],
                    wait_for_all_requests_to_be_added=True,
                    wait_for_all_requests_to_be_added_timeout=timedelta(
                        seconds=REQUEST_SUBMISSION_TIMEOUT_SECONDS
                    ),
                ),
                timeout=REQUEST_SUBMISSION_TIMEOUT_SECONDS,
            )
        except BaseException as error:
            if generation.stopping or self._closed:
                return
            if self._is_structural(error):
                await self._invalidate_generation(generation)
                return
            await self._settle_failed_submission(generation, key)

    async def _settle_failed_submission(self, generation: _CrawlerGeneration, key: str) -> None:
        try:
            request_manager = await generation.crawler.get_request_manager()
            queued_request = await request_manager.get_request(key)
        except BaseException:
            # The enqueue outcome is uncertain. Keep this key's reservation until its
            # crawler callback, structural retirement, total shutdown, or close.
            return
        if queued_request is None:
            await self._complete(
                generation,
                key,
                error=BrowserFetchError(FailureReason.BROWSER_FAILED),
            )

    def _submission_done(
        self,
        generation: _CrawlerGeneration,
        key: str,
        task: asyncio.Task[None],
    ) -> None:
        if generation.submission_tasks.get(key) is task:
            generation.submission_tasks.pop(key, None)
        self._submission_tasks.discard(task)
        if not task.cancelled():
            task.exception()

    def _new_generation_locked(self) -> _CrawlerGeneration:
        plugin = self._plugin_factory(proxy_config=self._proxy_config)
        storage = self._storage_factory()
        pool = self._browser_pool_factory(
            plugins=[plugin],
            operation_timeout=timedelta(seconds=BROWSER_POOL_OPERATION_TIMEOUT_SECONDS),
            browser_inactive_threshold=timedelta.max,
            retire_browser_after_page_count=sys.maxsize,
        )
        generation_id = str(self._uuid_factory())
        crawler = self._crawler_factory(
            browser_pool=pool,
            storage_client=storage,
            keep_alive=True,
            navigation_timeout=timedelta(seconds=NAVIGATION_TIMEOUT_SECONDS),
            request_handler_timeout=timedelta(seconds=REQUEST_HANDLER_TIMEOUT_SECONDS),
            goto_options={"wait_until": "domcontentloaded"},
            max_request_retries=0,
            max_session_rotations=0,
            use_session_pool=False,
            retry_on_blocked=False,
            ignore_http_error_status_codes=range(400, 600),
            max_requests_per_crawl=None,
            concurrency_settings=ConcurrencySettings(
                min_concurrency=ACTIVE_CAPACITY,
                desired_concurrency=ACTIVE_CAPACITY,
                max_concurrency=ACTIVE_CAPACITY,
            ),
            configure_logging=False,
            _logger=silent_crawlee_logger(f"meridian.browser.crawlee.{generation_id}"),
        )
        generation = _CrawlerGeneration(generation_id, crawler, plugin, storage)
        self._register_handlers(generation)
        generation.task = asyncio.create_task(crawler.run([], purge_request_queue=False))
        generation.task.add_done_callback(
            lambda task: self._schedule(self._handle_run_exit(generation, task))
        )
        self._generation = generation
        return generation

    def _register_handlers(self, generation: _CrawlerGeneration) -> None:
        @generation.crawler.router.default_handler
        async def request_handler(context: Any) -> None:
            await self._handle_request(generation, context)

        @generation.crawler.failed_request_handler
        async def failed_handler(context: Any, error: Exception) -> None:
            key = str(context.request.unique_key)
            if self._is_structural(error):
                await self._invalidate_generation(generation)
                return
            reason = (
                FailureReason.CONNECTIVITY_EXHAUSTED
                if self._exception_contains(error, PlaywrightTimeoutError)
                else FailureReason.BROWSER_FAILED
            )
            await self._complete(generation, key, error=BrowserFetchError(reason))

        @generation.crawler.on_skipped_request
        async def skipped_handler(url: str, reason: str) -> None:
            del reason
            keys = generation.queued_keys_by_url.get(url)
            key = next(iter(keys), None) if keys else None
            if key is not None:
                await self._complete(
                    generation,
                    key,
                    error=BrowserFetchError(FailureReason.BROWSER_FAILED),
                )

    async def _handle_request(self, generation: _CrawlerGeneration, context: Any) -> None:
        key = str(context.request.unique_key)
        pending = self._pending.get(key)
        if pending is None or pending.generation_id != generation.id:
            return
        try:
            response = getattr(context, "response", None)
            if response is None:
                raise BrowserFetchError(FailureReason.BROWSER_FAILED)
            status = int(response.status)
            response_url = str(getattr(response, "url", None) or context.request.url)
            page = context.page
            if status >= 400:
                body = await safe_page_content(page)
                headers = await response_headers(response)
                current_url = str(getattr(page, "url", None) or response_url)
                if is_browser_challenge(status, headers, body):
                    html = await resolve_browser_challenge(
                        page,
                        response,
                        body,
                        current_url,
                        headers,
                        proxy_enabled=generation.plugin.proxy_enabled,
                    )
                    await self._complete(generation, key, result=html)
                    return
                logger.warning(
                    "Browser fetch rejected response: %s",
                    response_diagnostics(
                        requested_url=context.request.url,
                        status_code=status,
                        decision="stop",
                        response_url=response_url,
                        headers=headers,
                        body=body,
                    ),
                )
                raise BrowserFetchError(FailureReason.HTTP_REJECTED, status)
            html = str(await page.content())
            if not html.strip() or len(html) < 2000:
                raise BrowserFetchError(FailureReason.UNUSABLE_CONTENT)
            await self._complete(generation, key, result=html)
        except BrowserFetchError as error:
            await self._complete(generation, key, error=error)
        except Exception as error:
            if self._is_structural(error):
                await self._invalidate_generation(generation)
            else:
                await self._complete(
                    generation, key, error=BrowserFetchError(FailureReason.BROWSER_FAILED)
                )

    async def _complete(
        self,
        generation: _CrawlerGeneration,
        key: str,
        *,
        result: str | None = None,
        error: BrowserFetchError | None = None,
    ) -> None:
        pending = self._pending.get(key)
        if pending is None or pending.generation_id != generation.id:
            return
        if generation.stopping:
            if not pending.future.done():
                pending.future.set_exception(BrowserFetchError(FailureReason.BROWSER_FAILED))
            return
        if not pending.future.done():
            if error is None:
                pending.future.set_result(result or "")
            else:
                pending.future.set_exception(error)
        await self._finish(generation, key)

    async def _finish(self, generation: _CrawlerGeneration, key: str) -> None:
        pending = self._pending.get(key)
        if pending is None or pending.generation_id != generation.id:
            return
        self._drop_pending(generation, key)
        await self._release()

    def _drop_pending(self, generation: _CrawlerGeneration, key: str) -> None:
        pending = self._pending.get(key)
        if pending is None or pending.generation_id != generation.id:
            return
        self._pending.pop(key, None)
        generation.pending_keys.discard(key)
        keys = generation.queued_keys_by_url.get(pending.url)
        if keys is not None:
            keys.pop(key, None)
            if not keys:
                generation.queued_keys_by_url.pop(pending.url, None)

    @staticmethod
    def _exception_contains(
        error: BaseException,
        kind: type[BaseException] | tuple[type[BaseException], ...],
    ) -> bool:
        seen: set[int] = set()
        current: BaseException | None = error
        while current is not None and id(current) not in seen:
            if isinstance(current, kind):
                return True
            seen.add(id(current))
            current = current.__cause__ or current.__context__
        return False

    @classmethod
    def _is_structural(cls, error: BaseException) -> bool:
        if cls._exception_contains(error, (_CamoufoxLaunchError, TargetClosedError)):
            return True
        names = {"BrowserClosedError", "ContextClosedError", "ControllerClosedError"}
        current: BaseException | None = error
        seen: set[int] = set()
        while current is not None and id(current) not in seen:
            if type(current).__name__ in names:
                return True
            seen.add(id(current))
            current = current.__cause__ or current.__context__
        return False

    def _schedule(self, coroutine: Any) -> None:
        task = asyncio.create_task(coroutine)
        self._monitor_tasks.add(task)
        task.add_done_callback(self._monitor_tasks.discard)

    async def _handle_run_exit(
        self, generation: _CrawlerGeneration, task: asyncio.Task[Any]
    ) -> None:
        try:
            task.exception()
        except asyncio.CancelledError:
            pass
        async with self._lifecycle_lock:
            if generation.stopping:
                return
            if self._generation is not generation:
                return
            retirement = self._begin_retirement_locked(generation)
        await asyncio.shield(retirement)

    async def _invalidate_generation(self, generation: _CrawlerGeneration) -> None:
        async with self._lifecycle_lock:
            if generation.stopping or self._generation is not generation:
                return
            self._begin_retirement_locked(generation)
        self._fail_generation_futures(generation)

    def _begin_retirement_locked(self, generation: _CrawlerGeneration) -> asyncio.Task[None]:
        existing = self._retiring.get(generation.id)
        if existing is not None:
            return existing
        generation.stopping = True
        task = asyncio.create_task(self._retire_generation(generation))
        self._retiring[generation.id] = task
        task.add_done_callback(
            lambda completed: (
                self._retiring.pop(generation.id, None)
                if self._retiring.get(generation.id) is completed
                else None
            )
        )
        return task

    def _fail_generation_futures(self, generation: _CrawlerGeneration) -> None:
        for key in tuple(generation.pending_keys):
            pending = self._pending.get(key)
            if (
                pending is not None
                and pending.generation_id == generation.id
                and not pending.future.done()
            ):
                pending.future.set_exception(BrowserFetchError(FailureReason.BROWSER_FAILED))

    async def _retire_generation(self, generation: _CrawlerGeneration) -> None:
        self._fail_generation_futures(generation)
        try:
            submissions = tuple(generation.submission_tasks.values())
            for submission in submissions:
                submission.cancel()
            if submissions:
                await asyncio.gather(*submissions, return_exceptions=True)
            await self._stop_generation(generation)
        finally:
            for key in tuple(generation.pending_keys):
                await self._finish(generation, key)
            async with self._lifecycle_lock:
                if self._generation is generation:
                    self._generation = None

    async def close(self) -> None:
        async with self._admission_lock:
            if not self._closed:
                self._closed = True
                while self._waiters:
                    waiter = self._waiters.popleft()
                    if not waiter.done():
                        waiter.set_exception(BrowserFetchError(FailureReason.BROWSER_FAILED))
        async with self._lifecycle_lock:
            generation = self._generation
            if generation is not None:
                self._begin_retirement_locked(generation)
        while True:
            tasks = tuple(
                task
                for task in (
                    *self._retiring.values(),
                    *self._monitor_tasks,
                    *self._submission_tasks,
                )
                if not task.done()
            )
            if not tasks:
                break
            await asyncio.gather(*tasks, return_exceptions=True)

    async def _stop_generation(self, generation: _CrawlerGeneration) -> None:
        try:
            async with asyncio.timeout(SHUTDOWN_TIMEOUT_SECONDS):
                generation.crawler.stop()
                if generation.task is not None:
                    await asyncio.shield(generation.task)
        except Exception:
            if generation.task is not None and not generation.task.done():
                generation.task.cancel()
                await asyncio.gather(generation.task, return_exceptions=True)

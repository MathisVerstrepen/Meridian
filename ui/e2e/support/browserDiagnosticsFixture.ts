import {
    expect,
    test as baseTest,
    type ConsoleMessage,
    type Page,
    type Request,
} from '@playwright/test';

interface PageErrorDiagnostic {
    name: string;
    message: string;
    stack?: string;
    pageUrl?: string;
}

interface ConsoleErrorDiagnostic {
    text: string;
    url?: string;
    lineNumber?: number;
    columnNumber?: number;
}

interface RequestFailureDiagnostic {
    method: string;
    url: string;
    resourceType: string;
    errorText: string;
}

export interface BrowserDiagnosticsReport {
    version: 1;
    pageErrors: PageErrorDiagnostic[];
    consoleErrors: ConsoleErrorDiagnostic[];
    requestFailures: RequestFailureDiagnostic[];
}

export interface BrowserDiagnosticsCapture {
    report: BrowserDiagnosticsReport;
    stop: () => void;
}

const ATTACHMENT_NAME = 'browser-diagnostics';
const UNKNOWN_URL = '[unparseable-url]';
const UNKNOWN_REQUEST_FAILURE = 'unknown failure';

const sanitizeUrl = (value: string): string | undefined => {
    if (!value) return undefined;

    try {
        const url = new URL(value);
        url.username = '';
        url.password = '';
        url.search = '';
        url.hash = '';
        return url.toString();
    } catch {
        return UNKNOWN_URL;
    }
};

const warnBestEffort = () => {
    try {
        console.warn('Browser diagnostics encountered a non-fatal collection or attachment error.');
    } catch {
        // Diagnostics must never affect the test outcome.
    }
};

export const startBrowserDiagnostics = (page: Page): BrowserDiagnosticsCapture => {
    const report: BrowserDiagnosticsReport = {
        version: 1,
        pageErrors: [],
        consoleErrors: [],
        requestFailures: [],
    };
    let stopped = false;
    let pageErrorInstalled = false;
    let consoleInstalled = false;
    let requestFailedInstalled = false;

    const onPageError = (error: Error) => {
        try {
            const pageUrl = sanitizeUrl(page.url());
            report.pageErrors.push({
                name: error.name,
                message: error.message,
                ...(error.stack ? { stack: error.stack } : {}),
                ...(pageUrl ? { pageUrl } : {}),
            });
        } catch {
            warnBestEffort();
        }
    };
    const onConsole = (message: ConsoleMessage) => {
        try {
            if (message.type() !== 'error') return;
            const location = message.location();
            const url = sanitizeUrl(location.url);
            report.consoleErrors.push({
                text: message.text(),
                ...(url ? { url } : {}),
                ...(location.lineNumber === undefined ? {} : { lineNumber: location.lineNumber }),
                ...(location.columnNumber === undefined ? {} : { columnNumber: location.columnNumber }),
            });
        } catch {
            warnBestEffort();
        }
    };
    const onRequestFailed = (request: Request) => {
        try {
            report.requestFailures.push({
                method: request.method(),
                url: sanitizeUrl(request.url()) ?? UNKNOWN_URL,
                resourceType: request.resourceType(),
                errorText: request.failure()?.errorText ?? UNKNOWN_REQUEST_FAILURE,
            });
        } catch {
            warnBestEffort();
        }
    };

    try {
        page.on('pageerror', onPageError);
        pageErrorInstalled = true;
    } catch {
        warnBestEffort();
    }
    try {
        page.on('console', onConsole);
        consoleInstalled = true;
    } catch {
        warnBestEffort();
    }
    try {
        page.on('requestfailed', onRequestFailed);
        requestFailedInstalled = true;
    } catch {
        warnBestEffort();
    }

    return {
        report,
        stop: () => {
            if (stopped) return;
            stopped = true;

            try {
                if (pageErrorInstalled) page.off('pageerror', onPageError);
            } catch {
                warnBestEffort();
            }
            try {
                if (consoleInstalled) page.off('console', onConsole);
            } catch {
                warnBestEffort();
            }
            try {
                if (requestFailedInstalled) page.off('requestfailed', onRequestFailed);
            } catch {
                warnBestEffort();
            }
        },
    };
};

export const formatBrowserDiagnostics = (report: BrowserDiagnosticsReport): string => {
    try {
        const pageErrors = report.pageErrors.map((error) => [
            `${error.name}: ${error.message}`,
            error.stack,
            error.pageUrl ? `Page: ${error.pageUrl}` : undefined,
        ].filter((value): value is string => Boolean(value)).join('\n'));
        const consoleErrors = report.consoleErrors.map((error) => {
            const location = error.url
                ? ` (${error.url}:${error.lineNumber ?? 0}:${error.columnNumber ?? 0})`
                : '';
            return `${error.text}${location}`;
        });
        const requestFailures = report.requestFailures.map(
            (failure) => `${failure.method} ${failure.url} [${failure.resourceType}]: ${failure.errorText}`,
        );

        return [
            `pageerror:\n${pageErrors.join('\n') || '(none)'}`,
            `console.error:\n${consoleErrors.join('\n') || '(none)'}`,
            `requestfailed:\n${requestFailures.join('\n') || '(none)'}`,
        ].join('\n\n');
    } catch {
        warnBestEffort();
        return 'Browser diagnostics unavailable due to a non-fatal formatting error.';
    }
};

interface BrowserDiagnosticsFixtures {
    browserDiagnostics: undefined;
}

export const test = baseTest.extend<BrowserDiagnosticsFixtures>({
    browserDiagnostics: [
        async ({ page }, use, testInfo) => {
            const capture = startBrowserDiagnostics(page);

            try {
                await use(undefined);
            } finally {
                try {
                    capture.stop();
                } catch {
                    warnBestEffort();
                }

                if (testInfo.status !== testInfo.expectedStatus) {
                    try {
                        const alreadyAttached = testInfo.attachments.some(
                            (attachment) => attachment.name === ATTACHMENT_NAME,
                        );
                        if (!alreadyAttached) {
                            await testInfo.attach(ATTACHMENT_NAME, {
                                body: JSON.stringify(capture.report, null, 2),
                                contentType: 'application/json',
                            });
                        }
                    } catch {
                        warnBestEffort();
                    }
                }
            }
        },
        { auto: true, box: true },
    ],
});

export { expect };

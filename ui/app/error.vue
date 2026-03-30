<script lang="ts" setup>
const error = useError();

const statusCode = computed(() => error.value?.statusCode ?? 404);
const is404 = computed(() => statusCode.value === 404);
const is401 = computed(() => statusCode.value === 401);
const is403 = computed(() => statusCode.value === 403);

const handleReturn = () => clearError({ redirect: is401.value ? '/auth/login' : '/' });
</script>

<template>
    <div class="error-page">
        <!-- Grain overlay -->
        <div class="grain" />

        <!-- Coordinate grid lines -->
        <div class="grid-lines">
            <div
                v-for="i in 7"
                :key="'h' + i"
                class="grid-line horizontal"
                :style="{ top: `${i * 14}%` }"
            />
            <div
                v-for="i in 7"
                :key="'v' + i"
                class="grid-line vertical"
                :style="{ left: `${i * 14}%` }"
            />
        </div>

        <!-- Meridian line (vertical center accent) -->
        <div class="meridian-line" />

        <!-- Content -->
        <div class="content">
            <!-- Icon -->
            <div class="icon-wrapper">
                <!-- Shield for 403 -->
                <svg
                    v-if="is403"
                    class="shield-icon"
                    width="56"
                    height="56"
                    viewBox="0 0 24 24"
                    fill="none"
                    xmlns="http://www.w3.org/2000/svg"
                >
                    <path
                        d="M12 2L3 7v5c0 5.25 3.83 10.15 9 11.25 5.17-1.1 9-6 9-11.25V7l-9-5z"
                        stroke="currentColor"
                        stroke-width="1.5"
                        stroke-linejoin="round"
                        fill="none"
                    />
                    <path
                        d="M9.5 9.5l5 5M14.5 9.5l-5 5"
                        stroke="currentColor"
                        stroke-width="1.5"
                        stroke-linecap="round"
                    />
                </svg>
                <!-- Lock for 401 -->
                <svg
                    v-else-if="is401"
                    class="lock-icon"
                    width="56"
                    height="56"
                    viewBox="0 0 24 24"
                    fill="none"
                    xmlns="http://www.w3.org/2000/svg"
                >
                    <rect
                        x="3"
                        y="11"
                        width="18"
                        height="11"
                        rx="2"
                        stroke="currentColor"
                        stroke-width="1.5"
                    />
                    <path
                        d="M7 11V7a5 5 0 0 1 10 0v4"
                        stroke="currentColor"
                        stroke-width="1.5"
                        stroke-linecap="round"
                    />
                    <circle cx="12" cy="16.5" r="1.5" fill="currentColor" />
                </svg>
                <!-- Compass for everything else -->
                <svg
                    v-else
                    class="compass"
                    width="64"
                    height="64"
                    fill="none"
                    viewBox="0 0 32 32"
                    xmlns="http://www.w3.org/2000/svg"
                >
                    <path
                        d="M16 28.222c6.75 0 12.222-5.472 12.222-12.222C28.222 9.25 22.75 3.778 16 3.778 9.25 3.778 3.778 9.25 3.778 16c0 6.75 5.472 12.222 12.222 12.222z"
                        stroke="currentColor"
                        stroke-width="2"
                        fill="none"
                    />
                    <path
                        d="M13.6 13.598l7.743-2.94-2.938 7.763-7.748 2.92 2.943-7.743z"
                        stroke="currentColor"
                        stroke-width="2"
                        fill="none"
                    />
                </svg>
                <div class="icon-pulse" :class="{ 'icon-pulse--merlot': is401 }" />
            </div>

            <!-- Error code -->
            <h1 class="error-code">
                {{ statusCode }}
            </h1>

            <!-- Message -->
            <p class="message">
                <template v-if="is403"> Territory beyond your clearance </template>
                <template v-else-if="is401"> Restricted coordinates </template>
                <template v-else-if="is404"> You've drifted off the meridian </template>
                <template v-else> Something went wrong </template>
            </p>

            <p class="submessage">
                <template v-if="is403">
                    You don't have permission to access this area of the map.
                </template>
                <template v-else-if="is401">
                    You need clearance to access this territory. Identify yourself to proceed.
                </template>
                <template v-else-if="is404">
                    The coordinates you're looking for don't exist on this map.
                </template>
                <template v-else>
                    {{ error?.message || 'An unexpected error occurred.' }}
                </template>
            </p>

            <!-- Return button -->
            <button class="return-btn" @click="handleReturn">
                <svg
                    v-if="!is401"
                    xmlns="http://www.w3.org/2000/svg"
                    width="18"
                    height="18"
                    viewBox="0 0 24 24"
                    fill="none"
                    stroke="currentColor"
                    stroke-width="2"
                    stroke-linecap="round"
                    stroke-linejoin="round"
                >
                    <path d="m12 19-7-7 7-7" />
                    <path d="M19 12H5" />
                </svg>
                {{
                    is401
                        ? 'Identify yourself'
                        : is403
                          ? 'Return to safe harbor'
                          : 'Return to charted waters'
                }}
            </button>

            <!-- Coordinates decoration -->
            <div class="coordinates">
                <template v-if="is401">
                    <span class="coord classified">ACCESS DENIED</span>
                </template>
                <template v-else-if="is403">
                    <span class="coord forbidden">FORBIDDEN ZONE</span>
                </template>
                <template v-else-if="is404">
                    <span class="coord">0° 00′ 00″ N</span>
                    <span class="coord-sep">/</span>
                    <span class="coord">0° 00′ 00″ E</span>
                </template>
                <template v-else>
                    <span class="coord">—</span>
                    <span class="coord-sep">/</span>
                    <span class="coord">—</span>
                </template>
            </div>
        </div>
    </div>
</template>

<style scoped>
@keyframes meridian-glow {
    0%,
    100% {
        opacity: 0.15;
        box-shadow: 0 0 20px 2px var(--color-ember-glow);
    }
    50% {
        opacity: 0.35;
        box-shadow: 0 0 40px 6px var(--color-ember-glow);
    }
}

@keyframes compass-spin {
    0% {
        transform: rotate(-15deg);
    }
    25% {
        transform: rotate(8deg);
    }
    50% {
        transform: rotate(-5deg);
    }
    75% {
        transform: rotate(3deg);
    }
    100% {
        transform: rotate(-15deg);
    }
}

@keyframes pulse {
    0%,
    100% {
        transform: scale(1);
        opacity: 0.4;
    }
    50% {
        transform: scale(1.8);
        opacity: 0;
    }
}

@keyframes lock-rattle {
    0%,
    100% {
        transform: rotate(0deg);
    }
    15% {
        transform: rotate(6deg);
    }
    30% {
        transform: rotate(-5deg);
    }
    45% {
        transform: rotate(4deg);
    }
    60% {
        transform: rotate(-2deg);
    }
    75% {
        transform: rotate(1deg);
    }
}

@keyframes fade-up {
    from {
        opacity: 0;
        transform: translateY(16px);
    }
    to {
        opacity: 1;
        transform: translateY(0);
    }
}

@keyframes grain-drift {
    0%,
    100% {
        transform: translate(0, 0);
    }
    10% {
        transform: translate(-2%, -2%);
    }
    30% {
        transform: translate(1%, -1%);
    }
    50% {
        transform: translate(-1%, 2%);
    }
    70% {
        transform: translate(2%, 1%);
    }
    90% {
        transform: translate(-2%, 1%);
    }
}

.error-page {
    position: fixed;
    inset: 0;
    display: flex;
    align-items: center;
    justify-content: center;
    background-color: var(--color-obsidian);
    overflow: hidden;
    font-family: 'Outfit-Variable', sans-serif;
}

.grain {
    position: absolute;
    inset: -50%;
    width: 200%;
    height: 200%;
    background-image: url("data:image/svg+xml,%3Csvg viewBox='0 0 256 256' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='noise'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.85' numOctaves='4' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23noise)'/%3E%3C/svg%3E");
    opacity: 0.03;
    pointer-events: none;
    animation: grain-drift 8s steps(1) infinite;
}

.grid-lines {
    position: absolute;
    inset: 0;
    pointer-events: none;
}

.grid-line {
    position: absolute;
    background-color: var(--color-stone-gray);
    opacity: 0.04;
}

.grid-line.horizontal {
    width: 100%;
    height: 1px;
}

.grid-line.vertical {
    height: 100%;
    width: 1px;
}

.meridian-line {
    position: absolute;
    left: 50%;
    top: 0;
    bottom: 0;
    width: 1px;
    background: linear-gradient(
        to bottom,
        transparent 0%,
        var(--color-ember-glow) 30%,
        var(--color-ember-glow) 70%,
        transparent 100%
    );
    animation: meridian-glow 4s ease-in-out infinite;
    pointer-events: none;
}

.content {
    position: relative;
    z-index: 10;
    display: flex;
    flex-direction: column;
    align-items: center;
    text-align: center;
    padding: 2rem;
}

.icon-wrapper {
    position: relative;
    margin-bottom: 2rem;
    animation: fade-up 0.8s ease-out both;
}

.compass {
    color: var(--color-ember-glow);
    animation: compass-spin 8s ease-in-out infinite;
    filter: drop-shadow(0 0 12px color-mix(in oklab, var(--color-ember-glow) 40%, transparent));
}

.lock-icon {
    color: var(--color-merlot-wine);
    animation: lock-rattle 3s ease-in-out infinite;
    filter: drop-shadow(0 0 12px color-mix(in oklab, var(--color-merlot-wine) 40%, transparent));
}

.shield-icon {
    color: var(--color-dried-heather);
    animation: pulse 4s ease-in-out infinite;
    filter: drop-shadow(0 0 12px color-mix(in oklab, var(--color-dried-heather) 40%, transparent));
}

.icon-pulse {
    position: absolute;
    inset: 0;
    border-radius: 50%;
    border: 1px solid var(--color-ember-glow);
    animation: pulse 3s ease-in-out infinite;
}

.icon-pulse--merlot {
    border-color: var(--color-merlot-wine);
}

.error-code {
    font-size: clamp(6rem, 15vw, 12rem);
    font-weight: 200;
    line-height: 1;
    letter-spacing: -0.04em;
    color: var(--color-soft-silk);
    margin: 0;
    background: linear-gradient(
        180deg,
        var(--color-soft-silk) 0%,
        color-mix(in oklab, var(--color-stone-gray) 60%, transparent) 100%
    );
    -webkit-background-clip: text;
    background-clip: text;
    -webkit-text-fill-color: transparent;
    animation: fade-up 0.8s ease-out 0.15s both;
}

.message {
    font-size: clamp(1.1rem, 2.5vw, 1.5rem);
    font-weight: 300;
    color: var(--color-stone-gray);
    margin: 0.75rem 0 0;
    letter-spacing: 0.02em;
    animation: fade-up 0.8s ease-out 0.3s both;
}

.submessage {
    font-size: 0.9rem;
    font-weight: 300;
    color: color-mix(in oklab, var(--color-stone-gray) 60%, transparent);
    margin: 0.5rem 0 0;
    max-width: 32ch;
    line-height: 1.5;
    animation: fade-up 0.8s ease-out 0.4s both;
}

.return-btn {
    display: inline-flex;
    align-items: center;
    gap: 0.5rem;
    margin-top: 2.5rem;
    padding: 0.75rem 1.5rem;
    background: transparent;
    border: 1px solid color-mix(in oklab, var(--color-ember-glow) 40%, transparent);
    color: var(--color-ember-glow);
    font-family: 'Outfit-Variable', sans-serif;
    font-size: 0.9rem;
    font-weight: 400;
    letter-spacing: 0.03em;
    border-radius: 9999px;
    cursor: pointer;
    transition:
        background 0.3s ease,
        border-color 0.3s ease,
        box-shadow 0.3s ease,
        transform 0.15s ease;
    animation: fade-up 0.8s ease-out 0.55s both;
}

.return-btn:hover {
    background: color-mix(in oklab, var(--color-ember-glow) 12%, transparent);
    border-color: var(--color-ember-glow);
    box-shadow: 0 0 24px -4px color-mix(in oklab, var(--color-ember-glow) 30%, transparent);
}

.return-btn:active {
    transform: scale(0.97);
}

.coordinates {
    margin-top: 3rem;
    display: flex;
    align-items: center;
    gap: 0.75rem;
    animation: fade-up 0.8s ease-out 0.7s both;
}

.coord {
    font-size: 0.75rem;
    font-weight: 300;
    color: color-mix(in oklab, var(--color-stone-gray) 35%, transparent);
    letter-spacing: 0.15em;
    font-variant-numeric: tabular-nums;
}

.coord.classified {
    color: color-mix(in oklab, var(--color-merlot-wine) 50%, transparent);
    letter-spacing: 0.25em;
}

.coord.forbidden {
    color: color-mix(in oklab, var(--color-dried-heather) 50%, transparent);
    letter-spacing: 0.25em;
}

.coord-sep {
    font-size: 0.75rem;
    color: color-mix(in oklab, var(--color-stone-gray) 20%, transparent);
}
</style>

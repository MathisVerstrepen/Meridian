<script lang="ts" setup></script>

<template>
    <div
        class="bg-obsidian relative flex h-screen w-screen items-center justify-center
            overflow-hidden"
    >
        <!-- Background Image -->
        <picture>
            <source srcset="/assets/img/login_bg.webp" type="image/webp" />
            <img
                src="/assets/img/login_bg.png"
                alt="Background Image"
                class="pointer-events-none absolute inset-0 z-0 h-full w-full object-cover
                    brightness-75"
            />
        </picture>

        <slot />

        <!-- Footer -->
        <div class="text-stone-gray/50 absolute bottom-8 flex items-center gap-4 text-sm">
            <a
                href="https://github.com/MathisVerstrepen/Meridian"
                target="_blank"
                rel="noopener noreferrer"
                class="hover:text-soft-silk transition-colors"
            >
                GitHub
            </a>
            •
            <a
                href="mailto:contact@meridianchat.com"
                class="hover:text-soft-silk transition-colors"
            >
                Contact
            </a>
        </div>
    </div>
</template>

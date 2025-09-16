<script lang="ts" setup></script>

<template>
    <div class="fixed inset-0 overflow-hidden">
        <div class="blob blob-1" />
        <div class="blob blob-2" />
        <div class="blob blob-3" />
    </div>
</template>

<style scoped>
@keyframes animate-blob {
    0% {
        transform: translate(0, 0) scale(1);
        border-radius: 60% 40% 30% 70% / 60% 30% 70% 40%;
    }
    25% {
        transform: translate(20vw, 15vh) scale(1.1);
    }
    50% {
        transform: translate(-10vw, -20vh) scale(1.2);
        border-radius: 30% 60% 70% 40% / 50% 60% 30% 60%;
        opacity: 0.75;
    }
    75% {
        transform: translate(10vw, -5vh) scale(0.9);
    }
    100% {
        transform: translate(0, 0) scale(1);
        border-radius: 60% 40% 30% 70% / 60% 30% 70% 40%;
    }
}

.blob {
    position: absolute;
    background-color: color-mix(in oklab, var(--color-ember-glow) 20%, transparent);
    filter: blur(80px);
    animation-timing-function: ease-in-out;
    animation-iteration-count: infinite;
    will-change: transform, border-radius, opacity;
}

/* Individual blob characteristics */
.blob-1 {
    width: 450px;
    height: 450px;
    top: 0px;
    left: 0px;
    animation-name: animate-blob;
    animation-duration: 32s;
    animation-delay: -10s;
}

.blob-2 {
    width: 350px;
    height: 400px;
    bottom: 000px;
    right: 50px;
    animation-name: animate-blob;
    animation-duration: 40s;
    animation-delay: -20s;
}

.blob-3 {
    width: 300px;
    height: 300px;
    top: 50%;
    left: 40%;
    animation-name: animate-blob;
    animation-duration: 25s;
    animation-delay: -5s;
}
</style>

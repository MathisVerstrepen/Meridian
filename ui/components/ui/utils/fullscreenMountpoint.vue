<script lang="ts" setup>
import { motion } from 'motion-v';

// --- Composables ---
const graphEvents = useGraphEvents();
const { info, error } = useToast();

// --- Local State ---
const fullScreenOpen = ref(false);
const rawMermaidElement = ref<string | undefined>(undefined);
const panZoomContent = ref<HTMLElement | null>(null);
const isDragging = ref(false);
const scale = ref(1);
const translateX = ref(0);
const translateY = ref(0);
const startPos = { x: 0, y: 0 };

// --- Computed Properties ---
const transformStyle = computed(() => ({
    transform: `translate(${translateX.value}px, ${translateY.value}px) scale(${scale.value})`,
    transition: isDragging.value ? 'none' : 'transform 0.1s ease-out',
    height: '100%',
    width: '100%',
}));

// --- Core Logic Functions ---
function genBase64Link(graphMarkdown: string): string {
    const jGraph = {
        code: graphMarkdown,
        mermaid: { theme: 'default' },
    };

    const jsonString = JSON.stringify(jGraph);

    return btoa(unescape(encodeURIComponent(jsonString)));
}

const mermaidLiveUrl = computed(() => {
    try {
        // replace &lt; and &gt; with < and >
        const decoded = rawMermaidElement.value?.replace(/&lt;/g, '<').replace(/&gt;/g, '>') || '';
        const compressed = genBase64Link(decoded);
        return `https://mermaid.live/edit#base64:${compressed}`;
    } catch (e) {
        console.error('Failed to encode Mermaid code for online editor link:', e);
        error('Failed to prepare link for online editor. Please try again.', {
            title: 'Link Error',
        });
        return 'https://mermaid.live/';
    }
});

const closeFullscreen = () => {
    const fullscreenMountpoint = document.getElementById('fullscreen-mountpoint');
    if (fullscreenMountpoint) {
        const mountedElement = fullscreenMountpoint.querySelector('.mermaid');
        if (mountedElement) {
            mountedElement.remove();
        }
        fullScreenOpen.value = false;

        // Reset pan & zoom state
        scale.value = 1;
        translateX.value = 0;
        translateY.value = 0;
        isDragging.value = false;
        fullscreenMountpoint.style.cursor = 'grab';
    }
};

const handleMouseDown = (event: MouseEvent) => {
    if ((event.target as HTMLElement).closest('button')) return;
    isDragging.value = true;
    startPos.x = event.clientX - translateX.value;
    startPos.y = event.clientY - translateY.value;
    (event.currentTarget as HTMLElement).style.cursor = 'grabbing';
};

const handleMouseMove = (event: MouseEvent) => {
    if (!isDragging.value) return;
    translateX.value = event.clientX - startPos.x;
    translateY.value = event.clientY - startPos.y;
};

const handleMouseUp = (event: MouseEvent) => {
    if (!isDragging.value) return;
    isDragging.value = false;
    (event.currentTarget as HTMLElement).style.cursor = 'grab';
};

const handleWheel = (event: WheelEvent) => {
    event.preventDefault();

    const zoomSpeed = 0.1;
    const direction = event.deltaY > 0 ? -1 : 1;
    const factor = 1 + direction * zoomSpeed;

    const newScale = Math.max(0.2, Math.min(scale.value * factor, 10));

    if (newScale !== scale.value) {
        const scaleRatio = newScale / scale.value;

        translateX.value = translateX.value * scaleRatio;
        translateY.value = translateY.value * scaleRatio;

        scale.value = newScale;
    }
};

const exportToPng = async () => {
    if (!panZoomContent.value) return;

    const svgElement = panZoomContent.value.querySelector('svg');
    if (!svgElement) {
        console.error('SVG element not found for export.');
        error('No SVG element found to export. Please ensure the graph is rendered correctly.', {
            title: 'Export Failed',
        });
        return;
    }

    // Get SVG dimensions from viewBox for accurate sizing.
    const viewBox = svgElement.getAttribute('viewBox');
    if (!viewBox) {
        console.error('SVG must have a viewBox attribute for export.');
        error('The SVG element must have a viewBox attribute for export.', {
            title: 'Export Failed',
        });
        return;
    }
    const viewBoxParts = viewBox.split(' ');
    const svgWidth = parseFloat(viewBoxParts[2]);
    const svgHeight = parseFloat(viewBoxParts[3]);

    if (isNaN(svgWidth) || isNaN(svgHeight) || svgWidth <= 0 || svgHeight <= 0) {
        console.error('Invalid viewBox dimensions for export.');
        error('Invalid SVG dimensions for export. Please check the SVG viewBox.', {
            title: 'Export Failed',
        });
        return;
    }

    // Clone the SVG and serialize it to a string.
    // This ensures we are working with a clean copy with explicit dimensions.
    const svgClone = svgElement.cloneNode(true) as SVGSVGElement;
    svgClone.setAttribute('width', `${svgWidth}px`);
    svgClone.setAttribute('height', `${svgHeight}px`);
    const svgString = new XMLSerializer().serializeToString(svgClone);

    // Create a data URL. This is the core of the bypass.
    // Loading the SVG via a data URL makes the browser treat it as same-origin.
    const svgDataUrl = `data:image/svg+xml;charset=utf-8,${encodeURIComponent(svgString)}`;

    const img = new Image();

    img.onload = () => {
        //  Draw the loaded image onto a canvas.
        const canvas = document.createElement('canvas');
        canvas.width = svgWidth;
        canvas.height = svgHeight;
        const ctx = canvas.getContext('2d');
        if (!ctx) return;

        // Set a background color to prevent a transparent background on the PNG.
        ctx.fillStyle = '#252422';
        ctx.fillRect(0, 0, svgWidth, svgHeight);

        ctx.drawImage(img, 0, 0);

        // Export the canvas content as a PNG file.
        try {
            const pngUrl = canvas.toDataURL('image/png');
            const link = document.createElement('a');
            link.href = pngUrl;
            link.download = 'graph.png';
            document.body.appendChild(link);
            link.click();
            document.body.removeChild(link);
        } catch (e) {
            console.error('Canvas could not be exported:', e);
            error('An error occurred while exporting the graph to PNG.', {
                title: 'Export Failed',
            });
        }
    };

    img.onerror = () => {
        console.error('The SVG data URL could not be loaded into an image.');
        error('An error occurred while preparing the graph for export.', {
            title: 'Export Failed',
        });
    };

    img.src = svgDataUrl;

    info('Graph exported to PNG successfully!', {
        title: 'Export Successful',
    });
};

const exportToMermaid = () => {
    if (!rawMermaidElement.value) {
        console.error('No raw Mermaid element available for export.');
        error('No Mermaid code available to export.', {
            title: 'Export Failed',
        });
        return;
    }

    const blob = new Blob([rawMermaidElement.value], { type: 'text/plain' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = 'graph.mermaid';
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);

    info('Mermaid code exported successfully!', {
        title: 'Export Successful',
    });
};

const copyToClipboard = () => {
    if (!rawMermaidElement.value) {
        console.error('No raw Mermaid element available to copy.');
        return;
    }

    navigator.clipboard
        .writeText(rawMermaidElement.value)
        .then(() => {
            info('Mermaid code copied to clipboard!', {
                title: 'Copied',
            });
        })
        .catch((err) => {
            console.error('Failed to copy Mermaid code:', err);
            error('Failed to copy Mermaid code. Please try again.', {
                title: 'Copy Failed',
            });
        });
};

// --- Watchers ---
watch(fullScreenOpen, (isOpen) => {
    if (isOpen) {
        nextTick(() => {
            const fullscreenMountpoint = document.getElementById('fullscreen-mountpoint');
            const mountedElement = fullscreenMountpoint?.querySelector('.mermaid');
            if (mountedElement && panZoomContent.value) {
                if (mountedElement.parentElement !== panZoomContent.value) {
                    panZoomContent.value.appendChild(mountedElement);
                }
            }
        });
    }
});

// --- Lifecycle Hooks ---
onMounted(() => {
    const unsubscribe = graphEvents.on('open-fullscreen', async (data) => {
        fullScreenOpen.value = data.open;
        rawMermaidElement.value = data.rawElement;
    });

    // when pressing escape, close fullscreen
    window.addEventListener('keydown', (event) => {
        if (event.key === 'Escape' && fullScreenOpen.value) {
            closeFullscreen();
        }
    });

    onUnmounted(unsubscribe);
});
</script>

<template>
    <AnimatePresence>
        <motion.div
            v-show="fullScreenOpen"
            id="fullscreen-mountpoint"
            key="fullscreen-graph"
            :initial="{ opacity: 0, scale: 0.85 }"
            :animate="{ opacity: 1, scale: 1, transition: { duration: 0.2, ease: 'easeOut' } }"
            :exit="{ opacity: 0, scale: 0.85, transition: { duration: 0.15, ease: 'easeIn' } }"
            class="bg-obsidian/90 border-stone-gray/10 absolute top-1/2 left-1/2 z-50 mx-auto h-[95%] w-[95%]
                -translate-x-1/2 -translate-y-1/2 cursor-grab overflow-hidden rounded-2xl border-2 px-4 py-8
                shadow-lg backdrop-blur-md"
            @mousedown.left="handleMouseDown"
            @mousemove="handleMouseMove"
            @mouseup.left="handleMouseUp"
            @mouseleave="handleMouseUp"
            @wheel.prevent="handleWheel"
        >
            <div ref="panZoomContent" :style="transformStyle">
                <!-- Mermaid graph will be mounted here by components/ui/chat/utils/fullScreenButton.vue -->
            </div>

            <button
                class="hover:bg-stone-gray/20 bg-stone-gray/10 absolute top-4 right-4 z-50 flex h-10 w-10 items-center
                    justify-center justify-self-end rounded-full backdrop-blur-sm transition-colors duration-200
                    ease-in-out hover:cursor-pointer"
                @click="closeFullscreen"
                aria-label="Close Fullscreen"
                title="Close Fullscreen"
            >
                <UiIcon name="MaterialSymbolsClose" class="text-stone-gray h-6 w-6" />
            </button>

            <div
                class="bg-stone-gray/10 absolute top-4 left-4 z-50 flex w-52 flex-col items-center justify-center
                    rounded-xl p-1 backdrop-blur-sm"
            >
                <!-- Export to Mermaid button -->
                <button
                    class="hover:bg-stone-gray/10 flex h-10 w-full items-center justify-start gap-2 rounded-lg px-3
                        transition-colors duration-200 ease-in-out hover:cursor-pointer"
                    @click="exportToMermaid"
                    aria-label="Export to Mermaid"
                    title="Export to Mermaid"
                >
                    <UiIcon name="UilDownloadAlt" class="text-stone-gray h-5 w-5" />
                    <p class="text-stone-gray text-sm font-bold">Export to Mermaid</p>
                </button>

                <!-- Copy to Clipboard button -->
                <button
                    class="hover:bg-stone-gray/10 flex h-10 w-full items-center justify-start gap-2 rounded-lg px-3
                        transition-colors duration-200 ease-in-out hover:cursor-pointer"
                    @click="copyToClipboard"
                    aria-label="Copy to Clipboard"
                    title="Copy to Clipboard"
                >
                    <UiIcon
                        name="MaterialSymbolsContentCopyOutlineRounded"
                        class="text-stone-gray h-5 w-5"
                    />
                    <p class="text-stone-gray text-sm font-bold">Copy to Clipboard</p>
                </button>

                <!-- Open in online editor button -->
                <a
                    class="hover:bg-stone-gray/10 flex h-10 w-full items-center justify-start gap-2 rounded-lg px-3
                        transition-colors duration-200 ease-in-out hover:cursor-pointer"
                    aria-label="Open in Online Editor"
                    title="Open in Online Editor"
                    :href="mermaidLiveUrl"
                    target="_blank"
                    rel="noopener noreferrer"
                >
                    <UiIcon name="mermaid_live" class="text-stone-gray h-5 w-5" />
                    <p class="text-stone-gray text-sm font-bold">Online Editor</p>
                </a>

                <!-- Export to PNG button -->
                <button
                    class="hover:bg-stone-gray/10 flex h-10 w-full items-center justify-start gap-2 rounded-lg px-3
                        transition-colors duration-200 ease-in-out hover:cursor-pointer"
                    @click="exportToPng"
                    aria-label="Export to PNG"
                    title="Export to PNG"
                >
                    <UiIcon name="MaterialSymbolsImageRounded" class="text-stone-gray h-5 w-5" />
                    <p class="text-stone-gray text-sm font-bold">Export to PNG</p>
                </button>
            </div>

            <div
                class="bg-stone-gray/10 absolute top-4 left-1/2 z-50 flex w-fit -translate-x-1/2 items-center
                    justify-center gap-2 rounded-xl px-2 py-1 backdrop-blur-sm"
            >
                <button
                    class="text-stone-gray hover:bg-stone-gray/10 cursor-pointer rounded-lg px-1 font-bold transition-colors
                        duration-200 ease-in-out"
                    @click="scale = Math.max(0.2, Math.min(scale * 0.9, 10))"
                    aria-label="Zoom Out"
                    title="Zoom Out"
                >
                    <UiIcon name="Fa6SolidMinus" class="text-stone-gray h-4 w-4" />
                </button>
                <button
                    class="text-stone-gray hover:text-stone-gray/80 cursor-pointer font-bold transition-colors duration-200
                        ease-in-out"
                    @click="scale = 1"
                    aria-label="Reset Zoom"
                    title="Reset Zoom"
                >
                    {{ scale.toFixed(2) }}
                </button>
                <button
                    class="text-stone-gray hover:bg-stone-gray/10 cursor-pointer rounded-lg px-1 font-bold transition-colors
                        duration-200 ease-in-out"
                    @click="scale = Math.max(0.2, Math.min(scale * 1.1, 10))"
                    aria-label="Zoom In"
                    title="Zoom In"
                >
                    <UiIcon name="Fa6SolidPlus" class="text-stone-gray h-4 w-4" />
                </button>
            </div>
        </motion.div>
    </AnimatePresence>
</template>

<style scoped></style>

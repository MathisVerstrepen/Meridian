export const useSidebarCanvasStore = defineStore('SidebarCanvas', () => {
    const isLeftOpen = ref(true);
    const isRightOpen = ref(true);

    if (import.meta.client) {
        onMounted(() => {
            const storedState = localStorage.getItem('sidebar-left-canvas-open');
            if (storedState !== null) {
                isLeftOpen.value = storedState === 'true';
            }

            const storedRightState = localStorage.getItem('sidebar-right-canvas-open');
            if (storedRightState !== null) {
                isRightOpen.value = storedRightState === 'true';
            }
        });
    }

    watch(
        isLeftOpen,
        (newValue) => {
            if (import.meta.client) {
                localStorage.setItem('sidebar-left-canvas-open', newValue.toString());
            }
        },
        {},
    );

    watch(
        isRightOpen,
        (newValue) => {
            if (import.meta.client) {
                localStorage.setItem('sidebar-right-canvas-open', newValue.toString());
            }
        },
        {},
    );
    const toggleLeftSidebar = () => {
        isLeftOpen.value = !isLeftOpen.value;
    };

    const toggleRightSidebar = () => {
        isRightOpen.value = !isRightOpen.value;
    };

    return {
        isLeftOpen,
        isRightOpen,
        toggleLeftSidebar,
        toggleRightSidebar,
    };
});

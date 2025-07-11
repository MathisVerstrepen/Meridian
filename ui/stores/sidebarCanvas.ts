export const useSidebarCanvasStore = defineStore('SidebarCanvas', () => {
    const isOpen = ref(true);

    if (import.meta.client) {
        onMounted(() => {
            const storedState = localStorage.getItem('sidebar-canvas-open');
            if (storedState !== null) {
                isOpen.value = storedState === 'true';
            }
        });
    }

    watch(
        isOpen,
        (newValue) => {
            if (import.meta.client) {
                localStorage.setItem('sidebar-canvas-open', newValue.toString());
            }
        },
        {},
    );

    const toggleSidebar = () => {
        isOpen.value = !isOpen.value;
    };

    return {
        isOpen,
        toggleSidebar,
    };
});

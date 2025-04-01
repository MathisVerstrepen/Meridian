export const useSidebarSelectorStore = defineStore('SidebarSelector', () => {
    const isOpen = ref(true);

    if (import.meta.client) {
        onMounted(() => {
            const storedState = localStorage.getItem('sidebar-open');
            if (storedState !== null) {
                isOpen.value = storedState === 'true';
            }
        });
    }

    watch(
        isOpen,
        (newValue) => {
            if (import.meta.client) {
                localStorage.setItem('sidebar-open', newValue.toString());
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

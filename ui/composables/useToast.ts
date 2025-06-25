interface ToastOptions {
    title?: string;
    timeout?: number;
}

export const useToast = () => {
    const toastsStore = useToastsStore();

    const show = (message: string, type: ToastType, options: ToastOptions = {}) => {
        toastsStore.add({
            message,
            type,
            ...options,
        });
    };

    return {
        show,
        success: (message: string, options?: ToastOptions) => show(message, 'success', options),
        error: (message: string, options?: ToastOptions) => show(message, 'error', options),
        warning: (message: string, options?: ToastOptions) => show(message, 'warning', options),
        info: (message: string, options?: ToastOptions) => show(message, 'info', options),
    };
};

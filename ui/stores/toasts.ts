import { defineStore } from 'pinia';

export type ToastType = 'success' | 'error' | 'warning' | 'info';

export interface Toast {
    id: string;
    type: ToastType;
    title?: string;
    message: string;
    timeout: number;
}

interface ToastsState {
    toasts: Toast[];
}

export const useToastsStore = defineStore('toasts', {
    state: (): ToastsState => ({
        toasts: [],
    }),
    actions: {
        add(toast: Omit<Toast, 'id' | 'timeout'> & { timeout?: number }) {
            // Create a unique ID for the toast
            const id = new Date().getTime().toString() + Math.random().toString();

            this.toasts.push({
                id,
                timeout: 3000, // Default timeout of 3 seconds
                ...toast,
            });
        },
        remove(id: string) {
            this.toasts = this.toasts.filter((toast) => toast.id !== id);
        },
    },
});

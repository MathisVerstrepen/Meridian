import { defineStore } from 'pinia';
import type { PromptTemplate } from '@/types/settings';

export const usePromptTemplateStore = defineStore('PromptTemplate', () => {
    const { apiFetch } = useAPI();

    // --- State ---
    const userTemplates = ref<PromptTemplate[]>([]);
    const publicTemplates = ref<PromptTemplate[]>([]);
    const individualTemplates = ref<Map<string, PromptTemplate>>(new Map());

    const isLoadingUser = ref(false);
    const isLoadingPublic = ref(false);

    // --- Promises (Deduplication) ---
    let userFetchPromise: Promise<PromptTemplate[]> | null = null;
    let publicFetchPromise: Promise<PromptTemplate[]> | null = null;

    // --- Actions ---

    /**
     * Fetch the current user's prompt templates.
     * @param force If true, bypasses cache and forces a network request.
     */
    const fetchUserTemplates = async (force = false) => {
        if (userFetchPromise && !force) {
            return userFetchPromise;
        }

        if (userTemplates.value.length > 0 && !force) {
            return userTemplates.value;
        }

        isLoadingUser.value = true;
        try {
            userFetchPromise = apiFetch<PromptTemplate[]>('/api/user/prompt-templates');
            const data = await userFetchPromise;
            userTemplates.value = data;
            return data;
        } catch (error) {
            console.error('Failed to fetch user templates:', error);
            throw error;
        } finally {
            isLoadingUser.value = false;
            userFetchPromise = null;
        }
    };

    /**
     * Fetch public prompt templates (Marketplace).
     * @param force If true, bypasses cache and forces a network request.
     */
    const fetchPublicTemplates = async (force = false) => {
        if (publicFetchPromise && !force) {
            return publicFetchPromise;
        }

        if (publicTemplates.value.length > 0 && !force) {
            return publicTemplates.value;
        }

        isLoadingPublic.value = true;
        try {
            publicFetchPromise = apiFetch<PromptTemplate[]>('/api/public/prompt-templates');
            const data = await publicFetchPromise;
            publicTemplates.value = data;
            return data;
        } catch (error) {
            console.error('Failed to fetch public templates:', error);
            throw error;
        } finally {
            isLoadingPublic.value = false;
            publicFetchPromise = null;
        }
    };

    /**
     * Fetch a specific template by ID.
     * Checks stores first, then API.
     */
    const fetchTemplateById = async (id: string): Promise<PromptTemplate | null> => {
        // 1. Check User Templates
        const inUser = userTemplates.value.find((t) => t.id === id);
        if (inUser) return inUser;

        // 2. Check Public Templates
        const inPublic = publicTemplates.value.find((t) => t.id === id);
        if (inPublic) return inPublic;

        // 3. Check Individual Cache
        if (individualTemplates.value.has(id)) {
            return individualTemplates.value.get(id)!;
        }

        // 4. Fetch from API
        try {
            const data = await apiFetch<PromptTemplate>(`/api/prompt-templates/${id}`);
            if (data) {
                individualTemplates.value.set(id, data);
                return data;
            }
        } catch (error) {
            console.error(`Failed to fetch template ${id}:`, error);
        }
        return null;
    };

    return {
        userTemplates,
        publicTemplates,
        isLoadingUser,
        isLoadingPublic,
        fetchUserTemplates,
        fetchPublicTemplates,
        fetchTemplateById,
    };
});

import { defineStore } from 'pinia';
import type { PromptTemplate } from '@/types/settings';

export const usePromptTemplateStore = defineStore('PromptTemplate', () => {
    const { apiFetch } = useAPI();

    // --- State ---
    const userTemplates = ref<PromptTemplate[]>([]);
    const publicTemplates = ref<PromptTemplate[]>([]);
    const bookmarkedTemplates = ref<PromptTemplate[]>([]);
    const individualTemplates = ref<Map<string, PromptTemplate>>(new Map());

    const isLoadingUser = ref(false);
    const isLoadingPublic = ref(false);
    const isLoadingBookmarks = ref(false);

    // --- Promises (Deduplication) ---
    let userFetchPromise: Promise<PromptTemplate[]> | null = null;
    let publicFetchPromise: Promise<PromptTemplate[]> | null = null;
    let bookmarkFetchPromise: Promise<PromptTemplate[]> | null = null;

    // --- Getters ---
    const allAvailableTemplates = computed(() => {
        const map = new Map<string, PromptTemplate>();
        userTemplates.value.forEach((t) => map.set(t.id, t));
        bookmarkedTemplates.value.forEach((t) => map.set(t.id, t));
        return Array.from(map.values());
    });

    const bookmarkedTemplateIds = computed(() => {
        return new Set(bookmarkedTemplates.value.map((t) => t.id));
    });

    // --- Actions ---

    /**
     * Fetch the current user's prompt templates.
     */
    const fetchUserTemplates = async (force = false) => {
        if (userFetchPromise && !force) return userFetchPromise;
        if (userTemplates.value.length > 0 && !force) return userTemplates.value;

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
     */
    const fetchPublicTemplates = async (force = false) => {
        if (publicFetchPromise && !force) return publicFetchPromise;
        if (publicTemplates.value.length > 0 && !force) return publicTemplates.value;

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
     * Fetch user's bookmarked templates.
     */
    const fetchBookmarkedTemplates = async (force = false) => {
        if (bookmarkFetchPromise && !force) return bookmarkFetchPromise;
        if (bookmarkedTemplates.value.length > 0 && !force) return bookmarkedTemplates.value;

        isLoadingBookmarks.value = true;
        try {
            bookmarkFetchPromise = apiFetch<PromptTemplate[]>(
                '/api/user/prompt-templates/bookmarks',
            );
            const data = await bookmarkFetchPromise;
            bookmarkedTemplates.value = data;
            return data;
        } catch (error) {
            console.error('Failed to fetch bookmarks:', error);
            throw error;
        } finally {
            isLoadingBookmarks.value = false;
            bookmarkFetchPromise = null;
        }
    };

    /**
     * Toggle bookmark for a template.
     */
    const toggleBookmark = async (template: PromptTemplate) => {
        const isBookmarked = bookmarkedTemplateIds.value.has(template.id);
        try {
            if (isBookmarked) {
                // Remove from local state optimistically
                bookmarkedTemplates.value = bookmarkedTemplates.value.filter(
                    (t) => t.id !== template.id,
                );
                await apiFetch(`/api/user/prompt-templates/${template.id}/bookmark`, {
                    method: 'DELETE',
                });
            } else {
                // Add to local state optimistically
                bookmarkedTemplates.value.push(template);
                await apiFetch(`/api/user/prompt-templates/${template.id}/bookmark`, {
                    method: 'POST',
                });
            }
        } catch (error) {
            console.error('Failed to toggle bookmark:', error);
            // Revert on error
            await fetchBookmarkedTemplates(true);
            throw error;
        }
    };

    /**
     * Fetch a specific template by ID.
     */
    const fetchTemplateById = async (id: string): Promise<PromptTemplate | null> => {
        const inUser = userTemplates.value.find((t) => t.id === id);
        if (inUser) return inUser;

        const inPublic = publicTemplates.value.find((t) => t.id === id);
        if (inPublic) return inPublic;

        const inBookmarks = bookmarkedTemplates.value.find((t) => t.id === id);
        if (inBookmarks) return inBookmarks;

        if (individualTemplates.value.has(id)) {
            return individualTemplates.value.get(id)!;
        }

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
        bookmarkedTemplates,
        allAvailableTemplates,
        bookmarkedTemplateIds,
        isLoadingUser,
        isLoadingPublic,
        isLoadingBookmarks,
        fetchUserTemplates,
        fetchPublicTemplates,
        fetchBookmarkedTemplates,
        toggleBookmark,
        fetchTemplateById,
    };
});

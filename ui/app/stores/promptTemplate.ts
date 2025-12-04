import { defineStore } from 'pinia';
import type { PromptTemplate } from '@/types/settings';

interface LibraryResponse {
    created: PromptTemplate[];
    bookmarked: PromptTemplate[];
}

interface CreateTemplatePayload {
    name: string;
    description?: string | null;
    templateText: string;
    isPublic: boolean;
}

interface UpdateTemplatePayload {
    name?: string;
    description?: string | null;
    templateText?: string;
    isPublic?: boolean;
}

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
    let libraryFetchPromise: Promise<LibraryResponse> | null = null;

    // Deduplicate individual ID fetches
    const inflightIndividualFetches = new Map<string, Promise<PromptTemplate | null>>();

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
        if (userFetchPromise) return userFetchPromise;

        if (userTemplates.value.length > 0 && !force) return userTemplates.value;

        isLoadingUser.value = true;
        userFetchPromise = apiFetch<PromptTemplate[]>('/api/prompt-templates/library')
            .then((data) => {
                userTemplates.value = data;
                return data;
            })
            .catch((error) => {
                console.error('Failed to fetch user templates:', error);
                throw error;
            })
            .finally(() => {
                isLoadingUser.value = false;
                userFetchPromise = null;
            });

        return userFetchPromise;
    };

    /**
     * Fetch public prompt templates (Marketplace).
     */
    const fetchPublicTemplates = async (force = false) => {
        if (publicFetchPromise) return publicFetchPromise;

        if (publicTemplates.value.length > 0 && !force) return publicTemplates.value;

        isLoadingPublic.value = true;
        publicFetchPromise = apiFetch<PromptTemplate[]>('/api/prompt-templates/marketplace')
            .then((data) => {
                publicTemplates.value = data;
                return data;
            })
            .catch((error) => {
                console.error('Failed to fetch public templates:', error);
                throw error;
            })
            .finally(() => {
                isLoadingPublic.value = false;
                publicFetchPromise = null;
            });

        return publicFetchPromise;
    };

    /**
     * Fetch user's bookmarked templates.
     */
    const fetchBookmarkedTemplates = async (force = false) => {
        if (bookmarkFetchPromise) return bookmarkFetchPromise;

        if (bookmarkedTemplates.value.length > 0 && !force) return bookmarkedTemplates.value;

        isLoadingBookmarks.value = true;
        bookmarkFetchPromise = apiFetch<PromptTemplate[]>('/api/prompt-templates/bookmarks')
            .then((data) => {
                bookmarkedTemplates.value = data;
                return data;
            })
            .catch((error) => {
                console.error('Failed to fetch bookmarks:', error);
                throw error;
            })
            .finally(() => {
                isLoadingBookmarks.value = false;
                bookmarkFetchPromise = null;
            });

        return bookmarkFetchPromise;
    };

    /**
     * Fetch both user created and bookmarked templates in a single request.
     * Optimized for node initialization.
     */
    const fetchLibrary = async (force = false) => {
        if (libraryFetchPromise) return libraryFetchPromise;

        // If both lists are populated and not forcing, return early
        if (userTemplates.value.length > 0 && bookmarkedTemplates.value.length > 0 && !force) {
            return { created: userTemplates.value, bookmarked: bookmarkedTemplates.value };
        }

        isLoadingUser.value = true;
        isLoadingBookmarks.value = true;

        libraryFetchPromise = apiFetch<LibraryResponse>('/api/prompt-templates/library/combined')
            .then((data) => {
                userTemplates.value = data.created;
                bookmarkedTemplates.value = data.bookmarked;
                return data;
            })
            .catch((error) => {
                console.error('Failed to fetch prompt library:', error);
                throw error;
            })
            .finally(() => {
                isLoadingUser.value = false;
                isLoadingBookmarks.value = false;
                libraryFetchPromise = null;
            });

        return libraryFetchPromise;
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
                await apiFetch(`/api/prompt-templates/${template.id}/bookmark`, {
                    method: 'DELETE',
                });
            } else {
                // Add to local state optimistically
                bookmarkedTemplates.value.push(template);
                await apiFetch(`/api/prompt-templates/${template.id}/bookmark`, {
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
     * Optimized with request coalescing.
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

        // Check if a request for this ID is already in flight
        if (inflightIndividualFetches.has(id)) {
            return inflightIndividualFetches.get(id)!;
        }

        const promise = apiFetch<PromptTemplate>(`/api/prompt-templates/${id}`)
            .then((data) => {
                if (data) {
                    individualTemplates.value.set(id, data);
                    return data;
                }
                return null;
            })
            .catch((error) => {
                console.error(`Failed to fetch template ${id}:`, error);
                return null;
            })
            .finally(() => {
                inflightIndividualFetches.delete(id);
            });

        inflightIndividualFetches.set(id, promise);
        return promise;
    };

    /**
     * Create a new prompt template.
     */
    const createTemplate = async (payload: CreateTemplatePayload): Promise<PromptTemplate> => {
        const newTemplate = await apiFetch<PromptTemplate>('/api/prompt-templates', {
            method: 'POST',
            body: JSON.stringify(payload),
        });
        userTemplates.value.push(newTemplate);
        return newTemplate;
    };

    /**
     * Update an existing prompt template.
     */
    const updateTemplate = async (
        id: string,
        payload: UpdateTemplatePayload,
    ): Promise<PromptTemplate> => {
        const updatedTemplate = await apiFetch<PromptTemplate>(`/api/prompt-templates/${id}`, {
            method: 'PUT',
            body: JSON.stringify(payload),
        });

        // Update local state
        const index = userTemplates.value.findIndex((t) => t.id === id);
        if (index !== -1) {
            userTemplates.value[index] = updatedTemplate;
        }
        // Also update if it exists in individual cache
        if (individualTemplates.value.has(id)) {
            individualTemplates.value.set(id, updatedTemplate);
        }
        return updatedTemplate;
    };

    /**
     * Delete a prompt template.
     */
    const deleteTemplate = async (id: string): Promise<void> => {
        await apiFetch(`/api/prompt-templates/${id}`, {
            method: 'DELETE',
        });
        userTemplates.value = userTemplates.value.filter((t) => t.id !== id);
        individualTemplates.value.delete(id);
    };

    /**
     * Fork a prompt template.
     * Creates a copy of the template in the user's library.
     */
    const forkTemplate = async (original: PromptTemplate): Promise<PromptTemplate> => {
        const payload: CreateTemplatePayload = {
            name: `${original.name} (Fork)`,
            description: original.description,
            templateText: original.templateText,
            isPublic: false,
        };
        return createTemplate(payload);
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
        fetchLibrary,
        toggleBookmark,
        fetchTemplateById,
        createTemplate,
        updateTemplate,
        deleteTemplate,
        forkTemplate,
    };
});

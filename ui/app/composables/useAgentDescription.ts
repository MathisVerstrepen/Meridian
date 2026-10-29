import type { Ref } from 'vue';
import type { AgentProfile } from '@/types/agent';

export function useAgentDescription(profile: Ref<AgentProfile>, instructions: Ref<string>) {
    const store = useAgentStore();
    const generatingDescription = ref(false);
    const descriptionError = ref('');
    let disposed = false;
    onScopeDispose(() => {
        disposed = true;
    });
    const generateDescription = async () => {
        if (
            generatingDescription.value ||
            !instructions.value.trim() ||
            !profile.value.model_settings.model
        )
            return;
        const initial = {
            description: profile.value.description,
            instructions: instructions.value,
            name: profile.value.name,
            model: profile.value.model_settings.model,
        };
        generatingDescription.value = true;
        descriptionError.value = '';
        try {
            const result = await store.generateDescription({
                name: initial.name,
                instructions: initial.instructions,
                model: initial.model,
            });
            if (disposed) return;
            if (
                profile.value.description === initial.description &&
                instructions.value === initial.instructions &&
                profile.value.name === initial.name &&
                profile.value.model_settings.model === initial.model
            ) {
                profile.value.description = result.description;
            } else {
                descriptionError.value =
                    'Your draft changed while generating. Generate again to use the latest instructions.';
            }
        } catch (err) {
            if (!disposed)
                descriptionError.value =
                    runtimeErrorDetail(err) ?? 'Could not generate a description. Try again.';
        } finally {
            generatingDescription.value = false;
        }
    };
    return { generatingDescription, descriptionError, generateDescription };
}

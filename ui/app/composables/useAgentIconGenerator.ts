import type { Ref } from 'vue';
import type { AgentProfile } from '@/types/agent';

export function useAgentIconGenerator(profile: Ref<AgentProfile>) {
    const store = useAgentStore();
    const generating = ref(false);
    const error = ref('');
    const candidate = ref('');
    const candidateContext = ref('');
    let disposed = false;
    onScopeDispose(() => {
        disposed = true;
    });
    const context = computed(() => ({
        name: profile.value.name,
        description: profile.value.description,
        instructions: profile.value.prompt_stack
            .filter((layer) => layer.enabled)
            .map((layer) => layer.text)
            .join('\n\n')
            .slice(0, 100000),
        category: profile.value.category,
        tags: profile.value.tags.slice(0, 20).map((tag) => tag.slice(0, 100)),
        tools: [...profile.value.tools],
        model: profile.value.model_settings.model,
    }));
    const contextKey = computed(() => JSON.stringify(context.value));
    const canGenerate = computed(
        () =>
            !!context.value.model &&
            [context.value.name, context.value.description, context.value.instructions].some(
                (text) => text.trim(),
            ),
    );
    const stale = computed(() => !!candidate.value && candidateContext.value !== contextKey.value);
    const generate = async () => {
        if (generating.value || !canGenerate.value) return;
        const key = contextKey.value;
        generating.value = true;
        error.value = '';
        try {
            const result = await store.generateIcon(context.value);
            if (disposed) return;
            if (key !== contextKey.value) {
                error.value =
                    'Agent details changed while generating. Generate again to use the latest details.';
                return;
            }
            candidate.value = result.iconSvg;
            candidateContext.value = key;
        } catch (err) {
            if (!disposed)
                error.value = runtimeErrorDetail(err) ?? 'Could not generate an icon. Try again.';
        } finally {
            generating.value = false;
        }
    };
    const apply = () => {
        if (candidate.value && !stale.value) profile.value.iconSvg = candidate.value;
    };
    return { generating, error, candidate, canGenerate, stale, generate, apply };
}

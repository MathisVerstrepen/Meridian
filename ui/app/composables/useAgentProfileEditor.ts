import type { AgentRecord, AgentVersion } from '@/types/agent';
import { createAgentDraft, suggestAgentHandle } from '@/utils/agentEditor';

export function useAgentProfileEditor(agent: AgentRecord | undefined, onSaved: () => void) {
    const store = useAgentStore();
    const settings = useSettingsStore();
    const profile = ref(
        createAgentDraft(
            settings.modelsSettings.defaultModel ?? '',
            agent?.profile ? toRaw(agent.profile) : undefined,
        ),
    );
    // New profiles start active and private; users can also save them as drafts.
    if (!agent) {
        profile.value.lifecycle = 'active';
        profile.value.visibility = 'private';
    }

    const error = ref('');
    const saving = ref(false);
    const saveIntent = ref<'active' | 'draft' | null>(null);
    const history = ref<AgentVersion[]>([]);
    const modelError = ref('');
    const form = ref<HTMLFormElement | null>(null);
    const takenHandles = computed(() =>
        store.library.filter((item) => item.id !== agent?.id).map((item) => item.handle),
    );
    watch(
        [() => profile.value.name, takenHandles],
        () => {
            if (!agent)
                profile.value.handle = profile.value.name.trim()
                    ? suggestAgentHandle(profile.value.name, takenHandles.value)
                    : '';
        },
        { immediate: true },
    );
    const instructions = computed({
        get: () => profile.value.prompt_stack[0]?.text ?? '',
        set: (text: string) => {
            if (!profile.value.prompt_stack.length)
                profile.value.prompt_stack.push({ name: 'Instructions', text, enabled: true });
            else profile.value.prompt_stack[0]!.text = text;
        },
    });
    const save = async (lifecycle: 'active' | 'draft' | null = null) => {
        if (saving.value || !form.value?.reportValidity()) return;
        error.value = '';
        modelError.value = '';
        if (!profile.value.name.trim()) {
            error.value = 'Give your Agent a name.';
            form.value.querySelector<HTMLInputElement>('input[required]')?.focus();
            return;
        }
        if (!profile.value.model_settings.model) {
            modelError.value = 'Choose a model for this Agent.';
            form.value.querySelector<HTMLInputElement>('[role="combobox"]')?.focus();
            return;
        }
        saving.value = true;
        saveIntent.value = lifecycle;
        const payload = structuredClone(toRaw(profile.value));
        payload.name = payload.name.trim();
        if (lifecycle) payload.lifecycle = lifecycle;
        if (payload.lifecycle === 'draft') payload.visibility = 'private';
        try {
            try {
                await store.save(payload, agent?.id);
            } catch (err) {
                if (agent || runtimeErrorStatus(err) !== 409) throw err;
                await store.loadLibrary();
                payload.handle = suggestAgentHandle(payload.name, [
                    ...takenHandles.value,
                    payload.handle,
                ]);
                profile.value.handle = payload.handle;
                await store.save(payload);
            }
            onSaved();
        } catch (err) {
            error.value =
                runtimeErrorDetail(err) ??
                'Could not save this Agent. Your changes are still here.';
        } finally {
            saving.value = false;
            saveIntent.value = null;
        }
    };
    const restore = async (version: number) => {
        if (!agent || saving.value) return;
        saving.value = true;
        try {
            await store.restoreVersion(agent.id, version);
            onSaved();
        } catch (err) {
            error.value = runtimeErrorDetail(err) ?? 'Could not restore this version.';
        } finally {
            saving.value = false;
        }
    };
    onMounted(async () => {
        if (!agent) return;
        try {
            history.value = await store.versions(agent.id);
        } catch {
            error.value = 'Version history could not be loaded. You can still edit this Agent.';
        }
    });
    return {
        profile,
        modelError,
        instructions,
        form,
        saving,
        saveIntent,
        error,
        history,
        save,
        restore,
    };
}

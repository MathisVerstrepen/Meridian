import type { AgentProfile, AgentRecord, AgentVersion } from '@/types/agent';
import { createAgentDraft, suggestAgentHandle } from '@/utils/agentEditor';

export function useAgentProfileEditor(
    agent: AgentRecord | undefined,
    preset: AgentProfile | undefined,
    onSaved: () => void,
) {
    const store = useAgentStore();
    const settings = useSettingsStore();
    const profile = ref(
        createAgentDraft(
            settings.modelsSettings.defaultModel ?? '',
            agent?.profile ? toRaw(agent.profile) : preset ? toRaw(preset) : undefined,
        ),
    );
    // Creating from a template should produce a usable private Agent immediately.
    if (!agent) {
        profile.value.lifecycle = 'active';
        profile.value.visibility = 'private';
    }
    const manualHandle = ref(!!agent);
    const showHandle = ref(false);
    const error = ref('');
    const saving = ref(false);
    const saveIntent = ref<'active' | 'draft' | null>(null);
    const history = ref<AgentVersion[]>([]);
    const handleError = ref('');
    const modelError = ref('');
    const form = ref<HTMLFormElement | null>(null);
    const takenHandles = computed(() =>
        store.library.filter((item) => item.id !== agent?.id).map((item) => item.handle),
    );
    watch(
        [() => profile.value.name, takenHandles],
        () => {
            if (!manualHandle.value)
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
    const applyPreset = (starter: AgentProfile) => {
        profile.value = createAgentDraft(
            settings.modelsSettings.defaultModel ?? '',
            toRaw(starter),
        );
        profile.value.lifecycle = 'active';
        profile.value.visibility = 'private';
        manualHandle.value = false;
        profile.value.handle = suggestAgentHandle(profile.value.name, takenHandles.value);
        error.value = '';
    };
    const setHandle = (value: string) => {
        manualHandle.value = true;
        profile.value.handle = value.toLowerCase().trim();
        handleError.value = '';
    };
    const save = async (lifecycle: 'active' | 'draft' | null = null) => {
        if (saving.value || !form.value?.reportValidity()) return;
        error.value = '';
        handleError.value = '';
        modelError.value = '';
        if (!profile.value.name.trim()) {
            error.value = 'Give your Agent a name.';
            form.value.querySelector<HTMLInputElement>('input[required]')?.focus();
            return;
        }
        if (!/^[a-z][a-z0-9_-]{1,49}$/.test(profile.value.handle)) {
            showHandle.value = true;
            handleError.value =
                'Use 2–50 lowercase letters, numbers, hyphens, or underscores. Start with a letter.';
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
            await store.save(payload, agent?.id);
            onSaved();
        } catch (err) {
            error.value =
                runtimeErrorDetail(err) ??
                'Could not save this Agent. Your changes are still here.';
            if (runtimeErrorStatus(err) === 409) {
                showHandle.value = true;
                handleError.value = error.value;
                nextTick(() =>
                    form.value
                        ?.querySelector<HTMLInputElement>('[aria-label="Agent handle"]')
                        ?.focus(),
                );
            }
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
        showHandle,
        handleError,
        modelError,
        instructions,
        form,
        saving,
        saveIntent,
        error,
        history,
        applyPreset,
        setHandle,
        save,
        restore,
    };
}

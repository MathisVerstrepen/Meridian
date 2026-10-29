import type { Ref } from 'vue';
import type { AgentTeam } from '@/types/agent';

export function useTeamMentions(
    editor: Ref<HTMLDivElement | null>,
    onChoose: (text: string) => void,
) {
    const store = useAgentStore();
    const raw = ref('');
    const caret = ref(0);
    const focused = ref(false);
    const dismissed = ref(false);
    const loading = ref(false);
    const error = ref('');
    const activeIndex = ref(0);
    const listId = `team-mentions-${useId()}`;
    let attemptedLoad = false;
    const token = computed(() => {
        const match = /^(\s*)@([a-z0-9_-]*)(?=\s|$)/i.exec(raw.value);
        if (!match || caret.value < (match[1]?.length ?? 0) + 1 || caret.value > match[0].length)
            return null;
        return {
            query: (match[2] ?? '').toLowerCase(),
            start: match[1]?.length ?? 0,
            end: match[0].length,
        };
    });
    const suggestions = computed(() => {
        if (!token.value) return [];
        const query = token.value.query;
        return store.teams
            .filter(
                (team) =>
                    team.handle.toLowerCase().startsWith(query) ||
                    team.name.toLowerCase().includes(query),
            )
            .slice(0, 8);
    });
    const open = computed(() => focused.value && !dismissed.value && token.value !== null);
    const activeId = computed(() =>
        open.value && suggestions.value[activeIndex.value]
            ? `${listId}-${suggestions.value[activeIndex.value]?.id}`
            : undefined,
    );
    const activeMembers = computed(
        () =>
            new Set(
                store.library
                    .filter((agent) => agent.profile.lifecycle === 'active')
                    .map((agent) => agent.id),
            ),
    );
    const memberCount = (team: AgentTeam) =>
        team.members.filter((id) => activeMembers.value.has(id)).length;
    const load = async () => {
        if (loading.value || attemptedLoad || store.teams.length) return;
        attemptedLoad = true;
        loading.value = true;
        error.value = '';
        try {
            await store.loadLibrary();
        } catch {
            error.value = 'Could not load your Teams.';
        } finally {
            loading.value = false;
        }
    };
    const retry = () => {
        attemptedLoad = false;
        void load();
    };
    watch(open, (value) => {
        if (value) void load();
    });
    watch(
        () => token.value?.query,
        () => {
            activeIndex.value = 0;
        },
    );
    watch(suggestions, () => {
        activeIndex.value = Math.min(activeIndex.value, Math.max(0, suggestions.value.length - 1));
    });
    watch(activeId, async (id) => {
        await nextTick();
        if (id) document.getElementById(id)?.scrollIntoView({ block: 'nearest' });
    });
    const sync = (reset = true) => {
        const element = editor.value;
        if (!element) return;
        raw.value = element.innerText;
        const selection = window.getSelection();
        if (selection?.focusNode && element.contains(selection.focusNode)) {
            const range = document.createRange();
            range.selectNodeContents(element);
            range.setEnd(selection.focusNode, selection.focusOffset);
            caret.value = range.toString().length;
            if (!selection.isCollapsed) {
                focused.value = false;
                return;
            }
        } else caret.value = raw.value.length;
        focused.value = true;
        if (reset) dismissed.value = false;
    };
    const dismiss = () => {
        dismissed.value = true;
    };
    const blur = () => {
        focused.value = false;
    };
    const clear = () => {
        raw.value = '';
        caret.value = 0;
        dismissed.value = false;
        activeIndex.value = 0;
    };
    const choose = (team: AgentTeam) => {
        const current = token.value;
        const element = editor.value;
        if (!current || !element) return;
        const suffix = raw.value.slice(current.end);
        const separator = /^\s/.test(suffix) ? '' : ' ';
        const prefix = `${raw.value.slice(0, current.start)}@${team.handle}`;
        const value = `${prefix}${separator}${suffix}`;
        element.innerText = value;
        element.focus();
        const position = prefix.length + 1;
        const walker = document.createTreeWalker(element, NodeFilter.SHOW_TEXT);
        let remaining = position;
        let node = walker.nextNode();
        const range = document.createRange();
        range.selectNodeContents(element);
        range.collapse(false);
        while (node) {
            const length = node.textContent?.length ?? 0;
            if (remaining <= length) {
                range.setStart(node, remaining);
                range.collapse(true);
                break;
            }
            remaining -= length;
            node = walker.nextNode();
        }
        window.getSelection()?.removeAllRanges();
        window.getSelection()?.addRange(range);
        raw.value = value;
        caret.value = position;
        dismissed.value = true;
        onChoose(value);
    };
    const keydown = (event: KeyboardEvent): boolean => {
        if (
            !open.value ||
            event.isComposing ||
            event.altKey ||
            event.ctrlKey ||
            event.metaKey ||
            event.shiftKey
        )
            return false;
        if (event.key === 'Escape') {
            event.preventDefault();
            event.stopPropagation();
            dismiss();
            return true;
        }
        if (!suggestions.value.length) return false;
        if (event.key === 'ArrowDown' || event.key === 'ArrowUp') {
            event.preventDefault();
            const delta = event.key === 'ArrowDown' ? 1 : -1;
            activeIndex.value =
                (activeIndex.value + delta + suggestions.value.length) % suggestions.value.length;
            return true;
        }
        if (event.key === 'Tab' || event.key === 'Enter') {
            event.preventDefault();
            const team = suggestions.value[activeIndex.value];
            if (team) choose(team);
            return true;
        }
        return false;
    };
    return {
        suggestions,
        open,
        query: computed(() => token.value?.query ?? ''),
        listId,
        activeId,
        activeIndex,
        loading,
        error,
        memberCount,
        sync,
        blur,
        clear,
        dismiss,
        choose,
        retry,
        keydown,
    };
}

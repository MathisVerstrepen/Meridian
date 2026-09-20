import { onClickOutside, useEventListener, useVirtualList } from '@vueuse/core';
import type { ModelInfo } from '@/types/model';

export interface ModelSelectRow {
    id: string;
    model: ModelInfo;
    headerMeta?: string;
    headerTitle?: string;
    headerTooltip?: string;
    warningLabel?: string;
    sectionId: string;
}

// The existing single-line select item is 40px, plus a 29px section heading.
// Keep geometry in unscaled CSS pixels: the teleported panel applies canvas zoom.
const ROW_HEIGHT = 40;
const HEADER_HEIGHT = 29;
const VIEWPORT_HEIGHT = 256;

export function useModelSelectCombobox(options: {
    rows: ComputedRef<ModelSelectRow[]>;
    selected: Ref<ModelInfo | undefined>;
    query: Ref<string>;
    disabled: () => boolean;
    trigger: Ref<HTMLElement | null>;
    panel: Ref<HTMLElement | null>;
}) {
    const inputRef = ref<HTMLInputElement | null>(null);
    const open = ref(false);
    const editing = ref(false);
    const activeRowId = ref<string>();
    const listId = `model-options-${useId()}`;
    const activeIndex = computed(() =>
        options.rows.value.findIndex((row) => row.id === activeRowId.value),
    );
    const activeOption = computed(() => options.rows.value[activeIndex.value]?.model);
    const inputValue = computed(() =>
        editing.value ? options.query.value : (options.selected.value?.name ?? ''),
    );
    const layout = computed(() => {
        let offset = 0;
        const rows = options.rows.value.map((row, index) => {
            const height = ROW_HEIGHT + (row.headerTitle ? HEADER_HEIGHT : 0);
            const entry = { row, index, top: offset, height };
            offset += height;
            return entry;
        });
        return { rows, height: offset };
    });
    const source = computed(() => (open.value ? layout.value.rows : []));
    const { list, containerProps, scrollTo } = useVirtualList(source, {
        itemHeight: (index) => source.value[index]?.height ?? ROW_HEIGHT,
        overscan: 4,
    });
    const scrollerRef = containerProps.ref;
    const renderedRows = computed(() => {
        if (!open.value) return [];
        const rows = list.value.map((entry) => entry.data);
        // Keep aria-activedescendant mounted even when the user wheels away from it.
        // Keyboard traversal uses the full data set, never the rendered window.
        const active = layout.value.rows[activeIndex.value];
        if (active && !rows.some((entry) => entry.row.id === active.row.id)) {
            rows.push(active);
            rows.sort((a, b) => a.index - b.index);
        }
        return rows;
    });
    const optionId = (index: number) => `${listId}-${index}`;
    const activeDescendant = computed(() =>
        open.value && activeIndex.value >= 0 ? optionId(activeIndex.value) : undefined,
    );
    const viewportHeight = computed(() => Math.min(VIEWPORT_HEIGHT, layout.value.height + 8));

    const reveal = () => {
        const entry = layout.value.rows[activeIndex.value];
        const scroller = scrollerRef.value;
        if (!entry || !scroller) return;
        const top = entry.top + 4;
        const bottom = top + entry.height;
        if (top < scroller.scrollTop) scroller.scrollTop = top - 4;
        else if (bottom > scroller.scrollTop + scroller.clientHeight) {
            scroller.scrollTop = bottom - scroller.clientHeight + 4;
        }
        containerProps.onScroll();
    };
    const activate = (index: number, scroll = true) => {
        const row = options.rows.value[index];
        activeRowId.value = row?.id;
        if (scroll) reveal();
    };
    const close = (restoreFocus = false) => {
        open.value = false;
        editing.value = false;
        options.query.value = '';
        activeRowId.value = undefined;
        if (restoreFocus) inputRef.value?.focus({ preventScroll: true });
    };
    const show = async (last = false) => {
        if (options.disabled() || open.value) return;
        open.value = true;
        const selectedIndex = options.rows.value.findIndex(
            (row) => row.model.id === options.selected.value?.id,
        );
        activate(selectedIndex >= 0 ? selectedIndex : last ? options.rows.value.length - 1 : 0);
        await nextTick();
        if (!open.value) return;
        reveal();
        inputRef.value?.focus({ preventScroll: true });
    };
    const select = (index = activeIndex.value) => {
        const row = options.rows.value[index];
        if (!row || options.disabled()) return;
        options.selected.value = row.model;
        close(true);
    };
    const onInput = (event: Event) => {
        if (!(event.target instanceof HTMLInputElement) || options.disabled()) return;
        editing.value = true;
        options.query.value = event.target.value;
        void show();
    };
    const onKeydown = (event: KeyboardEvent) => {
        if (options.disabled() || event.isComposing || event.defaultPrevented) return;
        switch (event.key) {
            case 'ArrowDown':
            case 'ArrowUp': {
                event.preventDefault();
                const up = event.key === 'ArrowUp';
                if (!open.value) void show(up);
                else
                    activate(
                        Math.max(
                            0,
                            Math.min(
                                options.rows.value.length - 1,
                                activeIndex.value + (up ? -1 : 1),
                            ),
                        ),
                    );
                break;
            }
            case 'Home':
            case 'End':
            case 'PageUp':
            case 'PageDown':
                if (!open.value || event.shiftKey) return;
                event.preventDefault();
                activate(
                    event.key === 'Home' || event.key === 'PageUp'
                        ? 0
                        : options.rows.value.length - 1,
                );
                break;
            case 'Enter':
                if (!open.value) return;
                event.preventDefault();
                select();
                break;
            case 'Escape':
                if (!open.value) return;
                event.preventDefault();
                event.stopPropagation();
                close(true);
                break;
            case 'Tab':
                if (open.value && activeOption.value) select();
                else close();
                break;
        }
    };
    const jumpTo = async (index: number) => {
        activate(index, false);
        scrollTo(index);
        await nextTick();
        inputRef.value?.focus({ preventScroll: true });
    };

    watch(options.rows, () => {
        if (!open.value) return;
        if (activeIndex.value < 0) activate(0, false);
        void nextTick(reveal);
    });
    watch(options.query, () => {
        if (!open.value) return;
        activate(0, false);
        void nextTick(reveal);
    });
    watch(options.disabled, (disabled) => {
        if (disabled) close();
    });
    onClickOutside(
        options.panel,
        () => {
            if (open.value) close();
        },
        { ignore: [options.trigger] },
    );
    useEventListener('focusin', (event: FocusEvent) => {
        const target = event.target;
        if (
            open.value &&
            target instanceof Node &&
            !options.trigger.value?.contains(target) &&
            !options.panel.value?.contains(target)
        ) {
            close();
        }
    });

    return {
        inputRef,
        inputValue,
        open,
        activeIndex,
        activeOption,
        activeDescendant,
        listId,
        optionId,
        renderedRows,
        layout,
        viewportHeight,
        scrollerRef,
        onScroll: containerProps.onScroll,
        show,
        close,
        activate,
        select,
        onInput,
        onKeydown,
        jumpTo,
    };
}

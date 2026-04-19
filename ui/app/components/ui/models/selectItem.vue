<script lang="ts" setup>
import type { ModelInfo } from '@/types/model';

const props = defineProps<{
    model: ModelInfo;
    active: boolean;
    selected: boolean;
    headerTitle?: string;
    headerMeta?: string;
    headerTooltip?: string;
    hideTool?: boolean;
    warningLabel?: string;
}>();

// --- Composables ---
const { formatModelPrice, formatContextLength } = useFormatters();

const pricingLabel = computed(() => {
    if (props.model.billingType === 'subscription') {
        const formattedContext = formatContextLength(props.model.context_length || 0);
        return formattedContext ? `Subscription · ${formattedContext}` : 'Subscription';
    }

    return [
        formatModelPrice(Number(props.model.pricing.prompt)),
        formatModelPrice(Number(props.model.pricing.completion)),
        formatContextLength(props.model.context_length || 0),
    ].join(' · ');
});
</script>

<template>
    <li :title="model.name">
        <!-- Section heading: tiny editorial chapter marker -->
        <div
            v-if="headerTitle"
            class="mb-1.5 flex items-center gap-2.5 px-2 pt-2"
            :title="headerTooltip"
        >
            <span
                class="text-soft-silk/95 shrink-0 text-[10px] font-black tracking-[0.22em]
                    uppercase"
            >
                {{ headerTitle }}
            </span>
            <span aria-hidden="true" class="bg-ember-glow/70 h-1.25 w-1.25 shrink-0 rotate-45" />
            <span
                aria-hidden="true"
                class="from-stone-gray/20 h-px flex-1 bg-linear-to-r to-transparent"
            />
            <span
                v-if="headerMeta"
                class="text-stone-gray/50 shrink-0 font-mono text-[9px] font-semibold tracking-wider
                    uppercase"
            >
                {{ headerMeta }}
            </span>
        </div>

        <!-- Row -->
        <div
            class="group/row relative cursor-pointer overflow-hidden rounded-lg py-2 pr-3 pl-10
                transition-all duration-150 select-none"
            :class="{
                [`bg-olive-grove-dark/85 text-soft-silk
                shadow-[inset_0_0_0_1px_rgba(255,252,242,0.08)]`]: active,
                'text-soft-silk/90 hover:bg-anthracite/70': !active,
                'pr-3': hideTool,
            }"
        >
            <!-- Left accent bar -->
            <span
                aria-hidden="true"
                class="absolute top-1.5 bottom-1.5 left-1 w-0.75 origin-center rounded-full
                    transition-all duration-200"
                :class="{
                    'bg-ember-glow scale-y-100 opacity-100': active,
                    'bg-ember-glow/80 scale-y-100 opacity-100': !active && selected,
                    [`bg-stone-gray/30 scale-y-50 opacity-0 group-hover/row:scale-y-100
                    group-hover/row:opacity-100`]: !active && !selected,
                }"
            />

            <!-- Model icon -->
            <span
                v-if="model.icon"
                class="absolute top-1/2 left-4 flex -translate-y-1/2 items-center
                    transition-transform duration-200 group-hover/row:scale-110"
                :class="{
                    'text-soft-silk/80': active,
                    'text-stone-gray/90': !active,
                }"
            >
                <UiIcon :name="'models/' + model.icon" class="h-4.5 w-4.5" />
            </span>

            <div class="flex w-full items-center justify-between gap-3">
                <!-- Name + selected marker -->
                <span class="flex min-w-0 items-center gap-1.5">
                    <span
                        v-if="selected"
                        aria-hidden="true"
                        class="bg-ember-glow inline-block h-1.25 w-1.25 shrink-0 rounded-full
                            shadow-[0_0_6px_rgba(235,94,40,0.6)]"
                    />
                    <span
                        class="min-w-0 truncate tracking-tight"
                        :class="{
                            'font-semibold': selected,
                            'font-medium': !selected,
                        }"
                    >
                        {{ model.name }}
                    </span>
                    <span
                        v-if="warningLabel"
                        :title="warningLabel"
                        class="inline-flex shrink-0 items-center gap-1 rounded-md bg-amber-500/10
                            px-1.5 py-0.75 text-[10px] font-semibold tracking-wide text-amber-300
                            ring-1 ring-amber-400/20 ring-inset"
                    >
                        <UiIcon name="MdiAlertOutline" class="h-3.5 w-3.5" />
                        <span>{{ warningLabel }}</span>
                    </span>
                </span>

                <!-- Right meta: pricing + tool badge -->
                <span class="flex shrink-0 items-center gap-2">
                    <span
                        class="font-mono text-[11px] font-medium tracking-tight tabular-nums"
                        :class="{
                            'text-soft-silk/75': active,
                            'text-stone-gray/80': !active,
                        }"
                    >
                        {{ pricingLabel }}
                    </span>
                    <span
                        v-if="model.toolsSupport && !hideTool"
                        title="Supports tool integration"
                        class="bg-ember-glow/10 text-ember-glow ring-ember-glow/20
                            group-hover/row:bg-ember-glow/15 flex items-center justify-center
                            rounded-md px-1 py-0.75 ring-1 transition-all ring-inset"
                        :class="{
                            'bg-ember-glow/20 ring-ember-glow/40': active,
                        }"
                    >
                        <UiIcon name="MdiWrenchOutline" class="h-3.5 w-3.5" />
                    </span>
                </span>
            </div>
        </div>
    </li>
</template>

<style scoped></style>

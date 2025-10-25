<script lang="ts" setup>
import type { Graph } from '@/types/graph';
import { ReasoningEffortEnum } from '@/types/enums';

interface SidebarCanvasConfig {
    custom_instructions: string[];
    max_tokens: number | null;
    temperature: number | null;
    top_p: number | null;
    top_k: number | null;
    frequency_penalty: number | null;
    presence_penalty: number | null;
    repetition_penalty: number | null;
    reasoning_effort: ReasoningEffortEnum | null;
}

const props = defineProps<{
    graph: Graph;
}>();

const { updateGraphConfig } = useAPI();

// --- Stores ---
const sidebarCanvasStore = useSidebarCanvasStore();
const settingsStore = useSettingsStore();

// --- State from Stores (Reactive Refs) ---
const { isRightOpen } = storeToRefs(sidebarCanvasStore);
const { modelsSettings } = storeToRefs(settingsStore);

// --- Composables ---
const { error } = useToast();

// --- Local State ---
const sidebarConfig = ref<SidebarCanvasConfig>({
    custom_instructions: props.graph.custom_instructions,
    max_tokens: props.graph.max_tokens,
    temperature: props.graph.temperature,
    top_p: props.graph.top_p,
    top_k: props.graph.top_k,
    frequency_penalty: props.graph.frequency_penalty,
    presence_penalty: props.graph.presence_penalty,
    repetition_penalty: props.graph.repetition_penalty,
    reasoning_effort: props.graph.reasoning_effort,
});
const isSaved = ref(false);

// --- Core Logic Functions ---
const updateSidebarConfig = () => {
    updateGraphConfig(props.graph.id, sidebarConfig.value)
        .then(() => {
            isSaved.value = true;
            setTimeout(() => {
                isSaved.value = false;
            }, 2000);
        })
        .catch((err) => {
            console.error('Error updating graph config:', err);
            error('Failed to update canvas settings. Please try again.', {
                title: 'Update Error',
            });
        });
};

const setCustomInstructionToggle = (id: string, enabled: boolean) => {
    if (enabled) {
        if (!sidebarConfig.value.custom_instructions.includes(id)) {
            sidebarConfig.value.custom_instructions.push(id);
        }
    } else {
        sidebarConfig.value.custom_instructions = sidebarConfig.value.custom_instructions.filter(
            (cid) => cid !== id,
        );
    }
};
</script>

<template>
    <div
        class="hide-scrollbar grid max-h-full w-full grid-rows-[1fr_1fr_1fr_1fr_1fr_1fr_10fr]
            flex-col gap-6 overflow-y-auto px-4 transition-opacity duration-300 ease-in-out"
        :class="{
            'opacity-0': !isRightOpen,
            'opacity-100': isRightOpen,
        }"
    >
        <!-- Custom Instructions -->
        <div>
            <label class="mb-2 flex gap-2" for="models-default-model">
                <h3 class="dark:text-stone-gray text-soft-silk/80 font-bold">
                    Canvas Custom Instructions
                </h3>
                <UiSettingsInfobubble direction="right">
                    Custom instructions for the canvas. This will be used as a system prompt for all
                    models in the canvas.
                </UiSettingsInfobubble>
            </label>
            <ul>
                <li
                    v-for="systemPrompt in modelsSettings.systemPrompt"
                    :key="systemPrompt.id"
                    class="bg-obsidian border-stone-gray/10 mb-1 flex items-center overflow-hidden
                        rounded-xl border-2 p-2"
                >
                    <UiIcon
                        v-if="!systemPrompt.editable"
                        name="MdiShieldOutline"
                        class="text-stone-gray mr-1 h-5 w-5"
                        title="System Prompt"
                    />
                    <div class="text-stone-gray ml-1 flex-grow text-sm font-medium">
                        {{ systemPrompt.name }}
                    </div>
                    <UiSettingsUtilsSwitch
                        :state="sidebarConfig.custom_instructions.includes(systemPrompt.id)"
                        :set-state="
                            (val: boolean) => setCustomInstructionToggle(systemPrompt.id, val)
                        "
                        class="scale-75 cursor-pointer"
                    />
                </li>
            </ul>
        </div>

        <div>
            <label class="mb-2 flex gap-2" for="canvas-reasoning-effort">
                <h3 class="dark:text-stone-gray text-soft-silk/80 font-bold">Reasoning Effort</h3>
                <UiSettingsInfobubble direction="right">
                    The reasoning effort to use for the chat response. This value controls how much
                    effort the model will put into reasoning before generating a response.
                </UiSettingsInfobubble>
            </label>
            <UiSettingsUtilsReasoningSlider
                id="canvas-reasoning-effort"
                :current-reasoning-effort="
                    sidebarConfig.reasoning_effort || ReasoningEffortEnum.MEDIUM
                "
                @update:reasoning-effort="
                    (value: ReasoningEffortEnum) => {
                        sidebarConfig.reasoning_effort = value;
                    }
                "
            />
        </div>

        <div class="grid grid-cols-2 gap-4">
            <!-- Max Tokens -->
            <div>
                <label class="mb-2 flex gap-2" for="canvas-max-tokens">
                    <h3 class="dark:text-stone-gray text-soft-silk/80 font-bold">Max Tokens</h3>
                    <UiSettingsInfobubble direction="right">
                        The maximum number of tokens to generate in the chat response.
                    </UiSettingsInfobubble>
                </label>
                <UiSettingsUtilsInputNumber
                    id="canvas-max-tokens"
                    :number="sidebarConfig.max_tokens"
                    :min="1"
                    placeholder="Minimum: 1"
                    @update:number="
                        (value: number) => {
                            sidebarConfig.max_tokens = value;
                        }
                    "
                />
            </div>

            <!-- Temperature -->
            <div>
                <label class="mb-2 flex gap-2" for="canvas-temperature">
                    <h3 class="dark:text-stone-gray text-soft-silk/80 font-bold">Temperature</h3>
                    <UiSettingsInfobubble direction="right">
                        The temperature to use for the chat response. Higher values will make the
                        response more random, while lower values will make it more deterministic.
                    </UiSettingsInfobubble>
                </label>
                <UiSettingsUtilsInputNumber
                    id="canvas-temperature"
                    :number="sidebarConfig.temperature"
                    placeholder="Default: 0.7"
                    :min="0"
                    :max="2"
                    :step="0.1"
                    @update:number="
                        (value: number) => {
                            sidebarConfig.temperature = value;
                        }
                    "
                />
            </div>
        </div>

        <div class="grid grid-cols-2 gap-4">
            <!-- Top P -->
            <div>
                <label class="mb-2 flex gap-2" for="canvas-top-p">
                    <h3 class="dark:text-stone-gray text-soft-silk/80 font-bold">Top P</h3>
                    <UiSettingsInfobubble direction="right">
                        The Top P value to use for the chat response. Top P is a filter that
                        controls how many different words or phrases the language model considers
                        when it’s trying to predict the next word. A lower value means the model
                        will only consider the most likely words, while a higher value means it will
                        consider more possibilities.
                    </UiSettingsInfobubble>
                </label>
                <UiSettingsUtilsInputNumber
                    id="canvas-top-p"
                    :number="sidebarConfig.top_p"
                    placeholder="Default: 1.0"
                    :step="0.01"
                    :min="0"
                    :max="1"
                    @update:number="
                        (value: number) => {
                            sidebarConfig.top_p = value;
                        }
                    "
                />
            </div>

            <!-- Top K -->
            <div>
                <label class="mb-2 flex gap-2" for="canvas-top-k">
                    <h3 class="dark:text-stone-gray text-soft-silk/80 font-bold">Top K</h3>
                    <UiSettingsInfobubble direction="right">
                        The Top K value to use for the chat response. Top K sample from the k most
                        likely next tokens at each step. Lower k focuses on higher probability
                        tokens.
                    </UiSettingsInfobubble>
                </label>
                <UiSettingsUtilsInputNumber
                    id="canvas-top-k"
                    :number="sidebarConfig.top_k"
                    placeholder="Default: 40"
                    :min="0"
                    @update:number="
                        (value: number) => {
                            sidebarConfig.top_k = value;
                        }
                    "
                />
            </div>
        </div>

        <div class="grid grid-cols-2 gap-4">
            <!-- Frequency Penalty -->
            <div>
                <label class="mb-2 flex gap-2" for="canvas-frequency-penalty">
                    <h3 class="dark:text-stone-gray text-soft-silk/80 font-bold">
                        Frequency Penalty
                    </h3>
                    <UiSettingsInfobubble direction="right">
                        The frequency penalty to use for the chat response. This value penalizes new
                        tokens based on their existing frequency in the text so far, decreasing the
                        model's likelihood to repeat the same line verbatim.
                    </UiSettingsInfobubble>
                </label>
                <UiSettingsUtilsInputNumber
                    id="canvas-frequency-penalty"
                    :number="sidebarConfig.frequency_penalty"
                    placeholder="Default: 0.0"
                    :step="0.01"
                    :min="-2"
                    :max="2"
                    @update:number="
                        (value: number) => {
                            sidebarConfig.frequency_penalty = value;
                        }
                    "
                />
            </div>

            <!-- Presence Penalty -->
            <div>
                <label class="mb-2 flex gap-2" for="canvas-presence-penalty">
                    <h3 class="dark:text-stone-gray text-soft-silk/80 font-bold">
                        Presence Penalty
                    </h3>
                    <UiSettingsInfobubble direction="right">
                        The presence penalty to use for the chat response. This value penalizes new
                        tokens based on whether they appear in the text so far, decreasing the
                        model's likelihood to repeat the same line verbatim.
                    </UiSettingsInfobubble>
                </label>
                <UiSettingsUtilsInputNumber
                    id="canvas-presence-penalty"
                    :number="sidebarConfig.presence_penalty"
                    placeholder="Default: 0.0"
                    :step="0.01"
                    :min="-2"
                    :max="2"
                    @update:number="
                        (value: number) => {
                            sidebarConfig.presence_penalty = value;
                        }
                    "
                />
            </div>
        </div>

        <div class="grid grid-cols-2 gap-4">
            <!-- Repetition Penalty -->
            <div>
                <label class="mb-2 flex gap-2" for="canvas-repetition-penalty">
                    <h3 class="dark:text-stone-gray text-soft-silk/80 font-bold">
                        Repetition Penalty
                    </h3>
                    <UiSettingsInfobubble direction="right">
                        The repetition penalty to use for the chat response. This value penalizes
                        new tokens based on their existing frequency in the text so far, decreasing
                        the model's likelihood to repeat the same line verbatim.
                    </UiSettingsInfobubble>
                </label>
                <UiSettingsUtilsInputNumber
                    id="canvas-repetition-penalty"
                    :number="sidebarConfig.repetition_penalty"
                    placeholder="Default: 1.0"
                    :step="0.01"
                    :min="0"
                    :max="2"
                    @update:number="
                        (value: number) => {
                            sidebarConfig.repetition_penalty = value;
                        }
                    "
                />
            </div>
        </div>

        <div class="flex items-end justify-center">
            <button
                class="bg-ember-glow/80 dark:text-soft-silk text-obsidian hover:bg-ember-glow/60
                    h-10 w-full cursor-pointer rounded-lg px-4 py-2 font-bold transition-colors
                    duration-200 ease-in-out disabled:cursor-not-allowed"
                :disabled="isSaved"
                @click="updateSidebarConfig"
            >
                <UiIcon v-if="isSaved" name="MaterialSymbolsCheckSmallRounded" class="h-6 w-6" />
                {{ isSaved ? 'Saved !' : 'Save Changes' }}
            </button>
        </div>
    </div>
</template>

<style scoped></style>

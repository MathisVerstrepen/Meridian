<script lang="ts" setup>
// --- Stores ---
const settingsStore = useSettingsStore();
const usageStore = useUsageStore();

// --- State from Stores ---
const { toolsWebSearchSettings } = storeToRefs(settingsStore);
const { webSearchUsage, isLoading } = storeToRefs(usageStore);

// --- Methods from Stores ---
const { getUsagePercentage, fetchUsage } = usageStore;

const ignoredSitesText = computed({
    get: () => toolsWebSearchSettings.value.ignoredSites?.join('\n') || '',
    set: (value) => {
        toolsWebSearchSettings.value.ignoredSites = value
            .split('\n')
            .filter((site) => site.trim() !== '');
    },
});

const preferredSitesText = computed({
    get: () => toolsWebSearchSettings.value.preferredSites?.join('\n') || '',
    set: (value) => {
        toolsWebSearchSettings.value.preferredSites = value
            .split('\n')
            .filter((site) => site.trim() !== '');
    },
});

onMounted(() => {
    fetchUsage();
});
</script>

<template>
    <div class="divide-stone-gray/10 flex flex-col divide-y">
        <!-- Setting: Search Query Usage -->
        <div class="py-6">
            <UiSettingsUtilsQueryUsage
                :billing-period-end="webSearchUsage.billing_period_end"
                :query-used="webSearchUsage.used"
                :query-total="webSearchUsage.total"
                :usage-percentage="getUsagePercentage(webSearchUsage.used, webSearchUsage.total)"
                :is-loading="isLoading"
                query-name="web search"
            />
        </div>

        <!-- Setting: Number of search results -->
        <div class="flex items-center justify-between py-6">
            <div class="max-w-2xl">
                <h3 class="text-soft-silk font-semibold">Number of Search Results</h3>
                <p class="text-stone-gray/80 mt-1 text-sm">
                    The number of search results to return for each query. <br />
                    Recommended range is 1-10 with 5 being the default recommended value.
                </p>
            </div>
            <div class="ml-6 shrink-0">
                <UiSettingsUtilsInputNumber
                    id="tools-web-search-num-results"
                    :number="toolsWebSearchSettings.numResults"
                    :min="1"
                    :max="20"
                    placeholder="Default: 5"
                    class="w-44"
                    @update:number="
                        (value: number) => {
                            toolsWebSearchSettings.numResults = value;
                        }
                    "
                />
            </div>
        </div>

        <!-- Setting: Custom Search API Key -->
        <div class="flex items-center justify-between py-6">
            <div class="max-w-2xl">
                <h3 class="font-semibold">
                    <NuxtLink
                        class="text-soft-silk decoration-stone-gray/40
                            hover:decoration-stone-gray/60 underline decoration-dashed
                            underline-offset-4 transition-colors duration-200 ease-in-out"
                        to="https://developers.google.com/custom-search/v1/overview"
                        external
                        target="_blank"
                    >
                        Custom Search JSON API Key
                    </NuxtLink>
                </h3>
                <p class="text-stone-gray/80 mt-1 text-sm">
                    Provide your own Google Custom Search API key to use your personal search quota.
                    <br />
                    Provides 100 search queries per day for free. Additional requests cost $5 per
                    1000 queries.
                    <br />
                    You can check your usage and set up billing in the
                    <NuxtLink
                        class="text-soft-silk decoration-stone-gray/40
                            hover:decoration-stone-gray/60 underline decoration-dashed
                            underline-offset-4 transition-colors duration-200 ease-in-out"
                        to="https://console.cloud.google.com/apis/api/customsearch.googleapis.com/quotas"
                        external
                        target="_blank"
                        >Google Cloud Console Quotas</NuxtLink
                    >.
                    <br />
                    Requests made with this key will NOT be counted towards the system's overall
                    query limit.
                </p>
            </div>
            <div class="ml-6 shrink-0">
                <input
                    id="tools-web-search-api-key"
                    type="password"
                    class="border-stone-gray/20 bg-anthracite/20 text-stone-gray
                        focus:border-ember-glow h-10 w-96 rounded-lg border-2 p-2 transition-colors
                        duration-200 ease-in-out outline-none focus:border-2"
                    placeholder="Enter your API key"
                    :value="toolsWebSearchSettings.customApiKey"
                    @input="
                        (event: Event) => {
                            const target = event.target as HTMLInputElement;
                            toolsWebSearchSettings.customApiKey = target.value;
                        }
                    "
                />
            </div>
        </div>

        <!-- Setting: Prioritize Custom Key -->
        <div class="flex items-center justify-between py-6">
            <div class="max-w-2xl">
                <h3 class="text-soft-silk font-semibold">Force User API Key</h3>
                <p class="text-stone-gray/80 mt-1 text-sm">
                    If a custom API key is set, force its usage over the system's custom web search
                    engine.
                </p>
            </div>
            <div class="ml-6 shrink-0">
                <UiSettingsUtilsSwitch
                    id="tools-web-search-force-custom-key"
                    :state="toolsWebSearchSettings.forceCustomApiKey"
                    :set-state="
                        (value: boolean) => {
                            toolsWebSearchSettings.forceCustomApiKey = value;
                        }
                    "
                />
            </div>
        </div>

        <!-- Setting: Sites to ignore -->
        <div class="flex items-start justify-between py-6">
            <div class="max-w-2xl">
                <h3 class="text-soft-silk font-semibold">Sites to Ignore</h3>
                <p class="text-stone-gray/80 mt-1 text-sm">
                    A list of websites to exclude from search results. Enter one domain per line
                    (e.g., wikipedia.org).
                </p>
            </div>
            <div class="ml-6 shrink-0">
                <textarea
                    id="tools-web-search-ignored-sites"
                    v-model="ignoredSitesText"
                    class="border-stone-gray/20 bg-anthracite/20 text-stone-gray
                        focus:border-ember-glow dark-scrollbar h-32 w-[30rem] rounded-lg border-2
                        p-2 transition-colors duration-200 ease-in-out outline-none focus:border-2"
                    placeholder="example.com&#10;anothersite.org"
                />
            </div>
        </div>

        <!-- Setting: Sites to prefer -->
        <div class="flex items-start justify-between py-6">
            <div class="max-w-2xl">
                <h3 class="text-soft-silk font-semibold">Sites to Prefer</h3>
                <p class="text-stone-gray/80 mt-1 text-sm">
                    A list of websites to prioritize in search results. Enter one domain per line
                    (e.g., developer.mozilla.org).
                </p>
            </div>
            <div class="ml-6 shrink-0">
                <textarea
                    id="tools-web-search-preferred-sites"
                    v-model="preferredSitesText"
                    class="border-stone-gray/20 bg-anthracite/20 text-stone-gray
                        focus:border-ember-glow dark-scrollbar h-32 w-[30rem] rounded-lg border-2
                        p-2 transition-colors duration-200 ease-in-out outline-none focus:border-2"
                    placeholder="stackoverflow.com&#10;github.com"
                />
            </div>
        </div>
    </div>
</template>

<style scoped></style>

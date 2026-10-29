from schemas.agents import AgentModelSettings, AgentWrite, PromptLayer

PRESETS = {
    "Frontend Expert": (
        "Engineering",
        ["execute_code"],
        "Build accessible, maintainable frontend interfaces. Explain tradeoffs and "
        "verify behavior.",
    ),
    "Backend Expert": (
        "Engineering",
        ["execute_code"],
        "Design reliable backend services, validate boundaries, and test failure paths.",
    ),
    "Image Generation Expert": (
        "Creative",
        ["image_generation"],
        "Create images and videos from clear visual briefs. Preserve requested "
        "subjects and composition.",
    ),
    "Code Reviewer": (
        "Engineering",
        [],
        "Review code for correctness, security and regressions. Prioritize concrete "
        "findings with evidence.",
    ),
    "Research Agent": (
        "Research",
        ["web_search", "link_extraction"],
        "Research questions using primary sources. Cite evidence and distinguish "
        "inference from facts.",
    ),
    "UX Designer": (
        "Design",
        ["visualise"],
        "Design understandable user journeys with accessible interactions and clear "
        "information hierarchy.",
    ),
    "Debugger": (
        "Engineering",
        ["execute_code"],
        "Reproduce failures, identify root causes, and verify focused fixes.",
    ),
    "Summarizer": (
        "Writing",
        [],
        "Summarize faithfully, retain key decisions and evidence, and flag uncertainty.",
    ),
}


def starter_presets():
    return [
        AgentWrite.model_validate(
            {
                "name": name,
                "handle": name.lower().replace(" ", "-"),
                "description": prompt,
                "category": category,
                "tools": tools,
                "model_settings": AgentModelSettings(model="xiaomi/mimo-v2.5"),
                "prompt_stack": [PromptLayer(name="Instructions", text=prompt)],
            }
        )
        for name, (category, tools, prompt) in PRESETS.items()
    ]

from urllib.parse import urlsplit, urlunsplit

GITLAB_PROVIDER_PREFIX = "gitlab:"


def normalize_gitlab_instance_url(instance_url: str) -> str:
    normalized_input = instance_url.strip()
    if not normalized_input:
        raise ValueError("GitLab instance URL cannot be empty.")

    if not normalized_input.startswith(("http://", "https://")):
        normalized_input = f"https://{normalized_input.lstrip('/')}"

    parsed = urlsplit(normalized_input)
    if not parsed.netloc:
        raise ValueError(f"Invalid GitLab instance URL: {instance_url}")

    return urlunsplit((parsed.scheme, parsed.netloc, parsed.path.rstrip("/"), "", ""))


def build_gitlab_provider_key(instance_url: str) -> str:
    return f"{GITLAB_PROVIDER_PREFIX}{normalize_gitlab_instance_url(instance_url)}"


def get_gitlab_instance_url(provider: str) -> str:
    if not provider.startswith(GITLAB_PROVIDER_PREFIX):
        raise ValueError(f"Invalid GitLab provider key: {provider}")

    return normalize_gitlab_instance_url(provider.split(":", 1)[1])


def get_gitlab_storage_provider(provider: str) -> str:
    instance_url = get_gitlab_instance_url(provider)
    parsed = urlsplit(instance_url)
    return f"{GITLAB_PROVIDER_PREFIX}{parsed.netloc}{parsed.path.rstrip('/')}"

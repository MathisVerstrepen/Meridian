#!/usr/bin/env bash

# Shared by local entry points. Never replace an existing environment implicitly.
require_project_python() {
    local interpreter="$1" required actual
    required="$(<"$(dirname "${BASH_SOURCE[0]}")/../.python-version")"
    if ! actual="$("$interpreter" -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')"; then
        echo "Python $required required; cannot run $interpreter. Install it and run make install-api or make install-browser-service." >&2
        return 1
    fi
    if [[ "$actual" != "$required" ]]; then
        echo "Python $required required; $interpreter uses $actual. Move the old virtualenv aside and reinstall, or choose a fresh API_VENV/BROWSER_SERVICE_VENV path. Existing files were not changed." >&2
        return 1
    fi
}

create_project_venv() {
    local venv="$1" interpreter="$2"
    if [[ -e "$venv" || -L "$venv" ]]; then
        require_project_python "$venv/bin/python"
        return
    fi
    require_project_python "$interpreter" || return
    "$interpreter" -m venv "$venv" || return
    require_project_python "$venv/bin/python"
}

if [[ "${BASH_SOURCE[0]}" == "$0" ]]; then
    set -euo pipefail
    case "${1:-}" in
        check) require_project_python "$2" ;;
        create) create_project_venv "$2" "$3" ;;
        *) echo "Usage: bash $0 check <python> | create <venv> <python>" >&2; exit 2 ;;
    esac
fi

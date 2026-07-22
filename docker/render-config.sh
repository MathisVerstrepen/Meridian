#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
CONFIG_DIR="$SCRIPT_DIR/config"
SCHEMA_FILE="$CONFIG_DIR/schema.yaml"
LOCAL_YQ="$PROJECT_ROOT/.bin/yq"
YQ_CMD=""
MERGED_FILE=""
STAGED_PRIMARY=""
STAGED_HOST=""

declare -a SETTING_PATHS=()
declare -a SETTING_ENVS=()
declare -a SECRET_ENVS=()
declare -A SETTING_TYPES=()
declare -A SETTING_MINIMUMS=()
declare -A SECRET_REQUIRED=()
declare -A SECRET_VALUES=()
declare -A SECRET_PRESENT=()

usage() {
    cat <<EOF
Usage: $0 <local|production>

Validates the versioned layered YAML configuration and required profile secrets,
then atomically renders Meridian's Docker/host environment files.
EOF
}

die() {
    printf '❌ Error: %s\n' "$1" >&2
    exit 1
}

cleanup() {
    [[ -z "$MERGED_FILE" ]] || rm -f "$MERGED_FILE"
    [[ -z "$STAGED_PRIMARY" ]] || rm -f "$STAGED_PRIMARY"
    [[ -z "$STAGED_HOST" ]] || rm -f "$STAGED_HOST"
}
trap cleanup EXIT

yq_works() {
    local cmd="$1"
    printf 'base:\n  nested:\n    first: 1\noverlay:\n  nested:\n    second: 2\n' |
        "$cmd" eval -e '(.base * .overlay) | ((.nested.first == 1) and (.nested.second == 2))' - >/dev/null 2>&1
}

install_local_yq() {
    local yq_version="v4.49.2"
    local os arch yq_os yq_arch download_url tmp_yq

    os="$(uname -s | tr '[:upper:]' '[:lower:]')"
    case "$os" in
        linux) yq_os="linux" ;;
        darwin) yq_os="darwin" ;;
        *) die "Automatic yq download is not supported for OS '$os'. Install Mike Farah yq v4." ;;
    esac

    arch="$(uname -m)"
    case "$arch" in
        x86_64) yq_arch="amd64" ;;
        aarch64|arm64) yq_arch="arm64" ;;
        armv7l) yq_arch="arm" ;;
        *) die "Automatic yq download is not supported for architecture '$arch'. Install Mike Farah yq v4." ;;
    esac

    download_url="https://github.com/mikefarah/yq/releases/download/${yq_version}/yq_${yq_os}_${yq_arch}"
    mkdir -p "$(dirname "$LOCAL_YQ")"
    tmp_yq="$(mktemp "$(dirname "$LOCAL_YQ")/.yq.XXXXXX")"
    printf "⚙️ yq not found or incompatible. Downloading Mike Farah yq %s to '%s'...\n" "$yq_version" "$LOCAL_YQ"

    if command -v curl >/dev/null 2>&1; then
        curl -fsSL -o "$tmp_yq" "$download_url" || { rm -f "$tmp_yq"; die "Failed to download yq from $download_url"; }
    elif command -v wget >/dev/null 2>&1; then
        wget -q -O "$tmp_yq" "$download_url" || { rm -f "$tmp_yq"; die "Failed to download yq from $download_url"; }
    else
        rm -f "$tmp_yq"
        die "'curl' or 'wget' is required to download yq automatically."
    fi

    chmod +x "$tmp_yq"
    yq_works "$tmp_yq" || { rm -f "$tmp_yq"; die "Downloaded yq from $download_url is incompatible."; }
    mv "$tmp_yq" "$LOCAL_YQ"
    printf '✅ yq installed successfully.\n'
}

resolve_yq() {
    if [[ -x "$LOCAL_YQ" ]] && yq_works "$LOCAL_YQ"; then
        YQ_CMD="$LOCAL_YQ"
    elif command -v yq >/dev/null 2>&1 && yq_works "$(command -v yq)"; then
        YQ_CMD="$(command -v yq)"
    else
        install_local_yq
        YQ_CMD="$LOCAL_YQ"
    fi
}

validate_schema_mapping() {
    local schema_version config_version path env type required minimum other secret_default
    local -A seen_paths=() seen_envs=()

    [[ -f "$SCHEMA_FILE" ]] || die "Tracked schema '$SCHEMA_FILE' is missing. Restore the repository file."
    "$YQ_CMD" eval '.' "$SCHEMA_FILE" >/dev/null 2>&1 || die "Schema '$SCHEMA_FILE' is not valid YAML."
    [[ "$("$YQ_CMD" eval -r 'tag' "$SCHEMA_FILE")" == "!!map" ]] || die "Schema root must be a mapping."
    schema_version="$("$YQ_CMD" eval -r '.schema_version | tag + ":" + tostring' "$SCHEMA_FILE")"
    config_version="$("$YQ_CMD" eval -r '.config_version | tag + ":" + tostring' "$SCHEMA_FILE")"
    [[ "$schema_version" == "!!int:1" && "$config_version" == "!!int:1" ]] || die "Schema/config version must be integer 1."
    [[ "$("$YQ_CMD" eval -r '.settings | tag' "$SCHEMA_FILE")" == "!!seq" ]] || die "Schema settings must be an ordered sequence."
    [[ "$("$YQ_CMD" eval -r '.secrets | tag' "$SCHEMA_FILE")" == "!!seq" ]] || die "Schema secrets must be an ordered sequence."

    while IFS=$'\t' read -r path env type required minimum; do
        [[ "$path" =~ ^[a-z][a-z0-9_]*(\.[a-z][a-z0-9_]*)*$ ]] || die "Schema path '$path' must use lowercase friendly segments."
        [[ "$env" =~ ^[A-Z][A-Z0-9_]*$ ]] || die "Schema env for '$path' is invalid."
        [[ "$type" =~ ^(string|integer|number|boolean)$ ]] || die "Schema type for '$path' is invalid."
        [[ "$required" == "true" ]] || die "Non-secret schema path '$path' must be required."
        [[ -z "${seen_paths[$path]:-}" ]] || die "Schema path '$path' is duplicated."
        [[ -z "${seen_envs[$env]:-}" ]] || die "Schema env '$env' is duplicated."
        for other in "${SETTING_PATHS[@]}"; do
            [[ "$path" != "$other."* && "$other" != "$path."* ]] || die "Schema scalar path prefix collision between '$path' and '$other'."
        done
        if [[ -n "$minimum" ]]; then
            [[ "$type" == "integer" && "$minimum" =~ ^-?[0-9]+$ ]] || die "Schema minimum for '$path' must be an integer."
        fi
        seen_paths["$path"]=1
        seen_envs["$env"]=1
        SETTING_PATHS+=("$path")
        SETTING_ENVS+=("$env")
        SETTING_TYPES["$path"]="$type"
        SETTING_MINIMUMS["$path"]="$minimum"
    done < <("$YQ_CMD" eval -r '.settings[] | [.path, .env, .type, (.required | tostring), (.minimum // "")] | @tsv' "$SCHEMA_FILE")
    (( ${#SETTING_PATHS[@]} > 0 )) || die "Schema defines no non-secret settings."

    while IFS=$'\t' read -r env required secret_default; do
        [[ "$env" =~ ^[A-Z][A-Z0-9_]*$ ]] || die "Secret schema env '$env' is invalid."
        [[ -z "${seen_envs[$env]:-}" ]] || die "Secret env '$env' overlaps or duplicates another schema env."
        [[ "$required" == "true" || "$required" == "false" ]] || die "Secret '$env' has an invalid required flag."
        if [[ "$required" == "false" && "$secret_default" != "" ]]; then
            die "Optional secret '$env' must have an empty default."
        fi
        seen_envs["$env"]=1
        SECRET_ENVS+=("$env")
        SECRET_REQUIRED["$env"]="$required"
    done < <("$YQ_CMD" eval -r '.secrets[] | [.env, (.required | tostring), (.default // "")] | @tsv' "$SCHEMA_FILE")
}

validate_layer() {
    local file="$1"
    local label="$2"
    local top_key version path tag schema_path known

    [[ -f "$file" ]] || die "Tracked $label layer '$file' is missing. Restore the repository file."
    "$YQ_CMD" eval '.' "$file" >/dev/null 2>&1 || die "$label layer '$file' is not valid YAML."
    [[ "$("$YQ_CMD" eval -r 'tag' "$file")" == "!!map" ]] || die "$label layer root must be a mapping."
    [[ "$("$YQ_CMD" eval -r 'keys | length' "$file")" == "2" ]] || die "$label layer allows exactly top-level keys 'version' and 'settings'."
    while IFS= read -r top_key; do
        [[ "$top_key" == "version" || "$top_key" == "settings" ]] || die "$label layer has unknown top-level key '$top_key'."
    done < <("$YQ_CMD" eval -r 'keys | .[]' "$file")
    version="$("$YQ_CMD" eval -r '.version | tag + ":" + tostring' "$file")"
    [[ "$version" == "!!int:1" ]] || die "$label layer version must be integer 1; follow docs/Config.md to migrate."
    [[ "$("$YQ_CMD" eval -r '.settings | tag' "$file")" == "!!map" ]] || die "$label layer settings must be a mapping."

    while IFS=$'\t' read -r path tag; do
        path="${path#settings.}"
        [[ "$path" != "settings" ]] || continue
        [[ "$path" =~ ^[a-z][a-z0-9_]*(\.[a-z][a-z0-9_]*)*$ ]] || die "$label layer path '$path' must use lowercase friendly segments."
        if [[ "$tag" == "!!map" ]]; then
            known=false
            for schema_path in "${SETTING_PATHS[@]}"; do
                if [[ "$schema_path" == "$path."* ]]; then known=true; break; fi
            done
            [[ "$known" == "true" ]] || die "$label layer has unknown mapping path '$path'."
        else
            [[ -n "${SETTING_TYPES[$path]:-}" ]] || die "$label layer has unknown setting path '$path'; secrets belong in the profile secrets env file."
            [[ "$tag" != "!!seq" && "$tag" != "!!null" ]] || die "$label layer path '$path' must be a non-null scalar."
            if [[ "$tag" == "!!str" ]] && "$YQ_CMD" eval -e ".settings.$path | contains(\"\\n\")" "$file" >/dev/null 2>&1; then
                die "$label layer path '$path' must not be multiline."
            fi
        fi
    done < <("$YQ_CMD" eval -r '.settings | .. | [path | join("."), tag] | @tsv' "$file")
}

merge_layers() {
    local common="$1" mode="$2" override="$3"
    MERGED_FILE="$(mktemp "$SCRIPT_DIR/.merged-config.XXXXXX")"
    if [[ -f "$override" ]]; then
        "$YQ_CMD" eval-all '. as $item ireduce ({}; . * $item)' "$common" "$mode" "$override" > "$MERGED_FILE"
    else
        "$YQ_CMD" eval-all '. as $item ireduce ({}; . * $item)' "$common" "$mode" > "$MERGED_FILE"
    fi
}

validate_effective_settings() {
    local path expected actual minimum value
    for path in "${SETTING_PATHS[@]}"; do
        expected="${SETTING_TYPES[$path]}"
        actual="$("$YQ_CMD" eval -r ".settings.$path | tag" "$MERGED_FILE")"
        case "$expected" in
            string) [[ "$actual" == "!!str" ]] || die "Setting '$path' must be a YAML string, not $actual." ;;
            integer) [[ "$actual" == "!!int" ]] || die "Setting '$path' must be a YAML integer, not $actual." ;;
            number) [[ "$actual" == "!!int" || "$actual" == "!!float" ]] || die "Setting '$path' must be a YAML number, not $actual." ;;
            boolean) [[ "$actual" == "!!bool" ]] || die "Setting '$path' must be a YAML boolean, not $actual." ;;
        esac
        if [[ "$actual" == "!!str" ]] && "$YQ_CMD" eval -e ".settings.$path | contains(\"\\n\")" "$MERGED_FILE" >/dev/null 2>&1; then
            die "Setting '$path' must not be multiline."
        fi
        minimum="${SETTING_MINIMUMS[$path]}"
        if [[ -n "$minimum" ]]; then
            value="$("$YQ_CMD" eval -r ".settings.$path" "$MERGED_FILE")"
            (( value >= minimum )) || die "Setting '$path' must be at least $minimum."
        fi
    done
}

read_secrets() {
    local file="$1"
    local line key rhs normalized env
    [[ -f "$file" ]] || die "Required secrets file '$file' is missing. Copy '${file%.env}.example.env' to '$file', fill required keys, and chmod 600 it."

    while IFS= read -r line || [[ -n "$line" ]]; do
        line="${line%$'\r'}"
        [[ "$line" =~ ^[[:space:]]*$ || "$line" =~ ^[[:space:]]*# ]] && continue
        [[ "$line" =~ ^([A-Z][A-Z0-9_]*)=(.*)$ ]] || die "Secrets file '$file' contains a malformed line; expected KEY=value."
        key="${BASH_REMATCH[1]}"
        rhs="${BASH_REMATCH[2]}"
        [[ -n "${SECRET_REQUIRED[$key]+x}" ]] || die "Secrets file '$file' contains unknown key '$key'."
        [[ -z "${SECRET_PRESENT[$key]:-}" ]] || die "Secrets file '$file' contains duplicate key '$key'."
        SECRET_PRESENT["$key"]=1
        SECRET_VALUES["$key"]="$rhs"
    done < "$file"

    for env in "${SECRET_ENVS[@]}"; do
        if [[ -z "${SECRET_PRESENT[$env]:-}" ]]; then
            [[ "${SECRET_REQUIRED[$env]}" == "false" ]] || die "Required secret '$env' is missing from '$file'."
            SECRET_VALUES["$env"]=""
            continue
        fi
        if [[ "${SECRET_REQUIRED[$env]}" == "true" ]]; then
            normalized="${SECRET_VALUES[$env]}"
            normalized="${normalized#"${normalized%%[![:space:]]*}"}"
            normalized="${normalized%"${normalized##*[![:space:]]}"}"
            [[ -n "$normalized" && "$normalized" != '""' && "$normalized" != "''" ]] || die "Required secret '$env' is empty in '$file'."
        fi
    done
}

translate_settings_to_env() {
    local destination="$1"
    local omit_proxy="$2"
    local profile="$3"
    local index path env value

    umask 077
    {
        printf '# Generated by docker/render-config.sh for profile %s.\n' "$profile"
        printf '# Sources: config/defaults/common.yaml, config/defaults/%s.yaml, optional sparse override, profile secrets.\n' "$profile"
        for index in "${!SETTING_PATHS[@]}"; do
            path="${SETTING_PATHS[$index]}"
            env="${SETTING_ENVS[$index]}"
            value="$("$YQ_CMD" eval -r ".settings.$path" "$MERGED_FILE")"
            printf '%s=%s\n' "$env" "$value"
        done
        for env in "${SECRET_ENVS[@]}"; do
            [[ "$omit_proxy" == "true" && "$env" == "LINK_EXTRACTION_BROWSER_PROXY_URL" ]] && continue
            printf '%s=%s\n' "$env" "${SECRET_VALUES[$env]}"
        done
    } > "$destination"
    chmod 0600 "$destination"
}

render_environment() {
    local profile="$1"
    local primary_output primary_dir host_output host_dir
    if [[ "$profile" == "local" ]]; then
        primary_output="$SCRIPT_DIR/env/.env.compose.local"
        host_output="$SCRIPT_DIR/env/.env.local"
    else
        primary_output="$SCRIPT_DIR/env/.env.prod"
        host_output=""
    fi

    primary_dir="$(dirname "$primary_output")"
    mkdir -p "$primary_dir"
    STAGED_PRIMARY="$(mktemp "$primary_dir/.rendered-env.XXXXXX")"
    translate_settings_to_env "$STAGED_PRIMARY" false "$profile"
    if [[ -n "$host_output" ]]; then
        host_dir="$(dirname "$host_output")"
        STAGED_HOST="$(mktemp "$host_dir/.rendered-host-env.XXXXXX")"
        translate_settings_to_env "$STAGED_HOST" true "$profile"
    fi

    mv "$STAGED_PRIMARY" "$primary_output"
    STAGED_PRIMARY=""
    if [[ -n "$host_output" ]]; then
        mv "$STAGED_HOST" "$host_output"
        STAGED_HOST=""
    fi
}

write_atomic_env() {
    render_environment "$1"
}

main() {
    local profile common mode override secrets
    [[ $# -eq 1 ]] || { usage >&2; exit 2; }
    profile="$1"
    [[ "$profile" == "local" || "$profile" == "production" ]] || { usage >&2; exit 2; }

    common="$CONFIG_DIR/defaults/common.yaml"
    mode="$CONFIG_DIR/defaults/$profile.yaml"
    override="$CONFIG_DIR/overrides/$profile.yaml"
    secrets="$CONFIG_DIR/secrets/$profile.env"

    resolve_yq
    validate_schema_mapping
    validate_layer "$common" "common"
    validate_layer "$mode" "$profile"
    if [[ -f "$override" ]]; then validate_layer "$override" "$profile override"; fi
    merge_layers "$common" "$mode" "$override"
    validate_effective_settings
    read_secrets "$secrets"
    write_atomic_env "$profile"
    printf "✅ Validated profile '%s' and generated environment file(s) with mode 0600.\n" "$profile"
}

main "$@"

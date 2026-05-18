#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

IMAGE="${IMAGE:-ghcr.io/vince-hz/dispatch-box}"
TAG="${TAG:-}"
LATEST="${LATEST:-1}"
PUSH="${PUSH:-1}"
PLATFORMS="${PLATFORMS:-linux/amd64}"
SINGLE_PLATFORM_PUSH="${SINGLE_PLATFORM_PUSH:-1}"
CONTEXT="${CONTEXT:-$ROOT_DIR}"
DOCKERFILE="${DOCKERFILE:-$ROOT_DIR/Dockerfile}"

usage() {
  cat <<'EOF'
Usage:
  docker-release.sh [options]

Options:
  --image <name>       Docker image name, e.g. ghcr.io/vince-hz/dispatch-box
  --tag <tag>          Docker tag. If omitted, uses current git short SHA
  --latest <bool>      Whether to also tag/push latest (default: 1)
  --push <bool>        Whether to push images after build (default: 1)
  --platforms <list>   Target platforms (default: linux/amd64)
  --single-platform-push <bool>
                       Build locally and push only one platform (default: 1).
                       Requires --platforms to contain exactly one platform.
  --context <path>     Docker build context (default: repo root)
  --dockerfile <path>  Dockerfile path (default: <repo>/Dockerfile)
  -h, --help           Show this help message

Boolean values:
  1/true/yes/on => true
  0/false/no/off => false
EOF
}

is_true() {
  # macOS ships bash 3.2 by default; avoid bash 4+ `${var,,}` syntax.
  local normalized
  normalized="$(printf '%s' "$1" | tr '[:upper:]' '[:lower:]')"
  case "${normalized}" in
    1|true|yes|on) return 0 ;;
    0|false|no|off) return 1 ;;
    *)
      echo "Invalid boolean value: $1" >&2
      exit 1
      ;;
  esac
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --image)
      IMAGE="$2"
      shift 2
      ;;
    --tag)
      TAG="$2"
      shift 2
      ;;
    --latest)
      LATEST="$2"
      shift 2
      ;;
    --push)
      PUSH="$2"
      shift 2
      ;;
    --platforms)
      PLATFORMS="$2"
      shift 2
      ;;
    --single-platform-push)
      SINGLE_PLATFORM_PUSH="$2"
      shift 2
      ;;
    --context)
      CONTEXT="$2"
      shift 2
      ;;
    --dockerfile)
      DOCKERFILE="$2"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown option: $1" >&2
      usage
      exit 1
      ;;
  esac
done

command -v docker >/dev/null 2>&1 || {
  echo "Error: docker command not found in PATH." >&2
  exit 1
}

if [[ -z "${TAG}" ]]; then
  if command -v git >/dev/null 2>&1 && git -C "${ROOT_DIR}" rev-parse --is-inside-work-tree >/dev/null 2>&1; then
    TAG="$(git -C "${ROOT_DIR}" rev-parse --short HEAD)"
  else
    echo "Error: TAG is empty and git metadata is unavailable. Set TAG explicitly." >&2
    exit 1
  fi
fi

tags=("${TAG}")
if is_true "${LATEST}" && [[ "${TAG}" != "latest" ]]; then
  tags+=("latest")
fi

if is_true "${PUSH}"; then
  if is_true "${SINGLE_PLATFORM_PUSH}"; then
    if [[ "${PLATFORMS}" == *","* ]]; then
      echo "Error: single-platform push requires exactly one platform, got: ${PLATFORMS}" >&2
      exit 1
    fi

    build_cmd=(docker build -f "${DOCKERFILE}" --platform "${PLATFORMS}")
    for t in "${tags[@]}"; do
      build_cmd+=(-t "${IMAGE}:${t}")
    done
    build_cmd+=("${CONTEXT}")

    echo "Building and pushing single-platform Docker image..."
    echo "  Image: ${IMAGE}"
    echo "  Tags:  ${tags[*]}"
    echo "  Platform: ${PLATFORMS}"
    "${build_cmd[@]}"

    for t in "${tags[@]}"; do
      docker push --platform "${PLATFORMS}" "${IMAGE}:${t}"
    done
  else
    build_cmd=(docker buildx build -f "${DOCKERFILE}" --platform "${PLATFORMS}")
    for t in "${tags[@]}"; do
      build_cmd+=(-t "${IMAGE}:${t}")
    done
    build_cmd+=(--push "${CONTEXT}")

    echo "Building and pushing Docker image..."
    echo "  Image: ${IMAGE}"
    echo "  Tags:  ${tags[*]}"
    echo "  Platforms: ${PLATFORMS}"
    "${build_cmd[@]}"
  fi
else
  build_cmd=(docker build -f "${DOCKERFILE}")
  for t in "${tags[@]}"; do
    build_cmd+=(-t "${IMAGE}:${t}")
  done
  build_cmd+=("${CONTEXT}")

  echo "Building Docker image..."
  echo "  Image: ${IMAGE}"
  echo "  Tags:  ${tags[*]}"
  "${build_cmd[@]}"
  echo "Skip push because PUSH=${PUSH}"
fi

echo "Release complete."

# AGENTS.md

## Docker release policy

- Default registry/image: `ghcr.io/vince-hz/dispatch-box`.
- Default release mode is single-architecture `linux/amd64`.
- Use `make docker-release vX.Y.Z` for normal releases.
- Only use multi-architecture publishing when explicitly requested:
  `make docker-release vX.Y.Z DOCKER_PLATFORMS=linux/amd64,linux/arm64 DOCKER_SINGLE_PLATFORM_PUSH=0`.
- The compose file defaults to `ghcr.io/vince-hz/dispatch-box:latest`; override with `DISPATCH_BOX_IMAGE` when needed.

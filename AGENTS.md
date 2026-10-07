# Repository instructions

## Shared Homelab rules

- GitHub organization: `rbnstn`.
- The canonical infrastructure documentation is intended to live in the private repository `rbnstn/homelab`. Until that repository exists, the rules in this file are authoritative for this project.
- Prefer the existing Homelab architecture over introducing a new hosting or deployment platform.
- For server-side applications, the default production path is: GitHub Actions -> self-hosted GitHub Actions runner -> Proxmox LXC -> Docker / Docker Compose.
- Prefer container images published to `ghcr.io/rbnstn/<project>` when the project is containerized.
- Deployments should be automated through GitHub Actions whenever practical. Avoid adding manual deployment steps when they can be automated.
- Preserve persistent data across builds, updates and deployments. Never delete or replace production data unless the task explicitly requires it.
- Keep secrets, passwords, tokens, SSH keys and environment-specific credentials out of the repository. Use GitHub Secrets or the existing runtime secret mechanism.
- Reuse existing LXC containers, Docker hosts, runners, networks and deployment conventions when suitable. Do not create parallel infrastructure without a concrete reason.
- If the target is firmware, HACS, GitHub Pages, static hosting, or another non-container project, follow that project's native release/deployment path instead of forcing the LXC/Docker model.
- When infrastructure assumptions change, update the repository documentation in the same change so future work does not rely on chat history.

## Working style

- Inspect the existing repository and architecture before implementing changes.
- Preserve established conventions unless there is a clear technical reason to change them.
- Complete requested changes end to end where possible, including tests, release implications and documentation.
- Update installation or operating documentation when user-visible setup or deployment behavior changes.
- Do not commit secrets or production credentials.
- Do not remove persistent data, migrations or compatibility paths without explicit instruction.

## Project-specific deployment

This repository is the public HACS/release repository for the Home Assistant desk display project. Keep HACS packaging, GitHub Pages, firmware release artifacts and the existing publication flow intact. Do not introduce an LXC/Docker deployment for this repository unless the project architecture explicitly changes.

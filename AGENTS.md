# Repository Guidelines

## Project Structure & Module Organization
Runtime code lives in `src/simulaiz/`; keep shared utilities in `src/simulaiz/core/` and agent classes in `src/simulaiz/agents/` (one class per agent). Scenario definitions stay in `scenarios/` and datasets or static assets in `assets/`. Mirror packages in `tests/`. Keep notebooks under `notebooks/` and documentation in `docs/`. Compose files sit at the root while swarm manifests and Traefik rules live in `deploy/`.

## Build, Test, and Development Commands
- `docker compose build` – refresh application and Traefik images after dependency changes.
- `docker compose up -d` – start the stack on `webhost-network`; reset via `docker compose down -v`.
- `docker compose exec app pytest` – run the full test matrix inside the app container.
- `docker compose exec app ruff check src tests` – lint and apply `--fix` when appropriate.
- `docker compose exec app pre-commit run --all-files` – run the same hooks enforced in CI.

## Coding Style & Naming Conventions
Follow PEP 8 with 4-space indentation and comprehensive type hints. Modules use snake_case (`agent_planner.py`), classes use CapWords (`ScenarioBuilder`), and functions stay snake_case. Keep configuration filenames descriptive (`scenarios/city_grid.yaml`). Use docstrings for public APIs and prefer `Path` over raw strings for filesystem access.

## Container Orchestration & Networking
Traefik fronts every service via Docker labels; declare router rules and middlewares in `docker-compose.yml` or the swarm stack. Ensure `webhost-network` exists (`docker network create webhost-network`) before any `docker compose up` or `docker stack deploy`. Persist TLS material and Traefik state in a shared `traefik-data/` volume so local and swarm deployments stay aligned.

## Testing Guidelines
Write pytest suites under `tests/<module>/` with files named `test_<feature>.py`. Use `@pytest.mark.slow` for long-running scenarios. Target ≥85% coverage with deterministic agent tests plus a representative integration scenario. Keep synthetic fixtures in `tests/fixtures/` and run suites through `docker compose exec app pytest` to mirror production.

## Commit & Pull Request Guidelines
Commit messages follow the format `type(scope): action`, e.g., `feat(agents): add stochastic policy`. Keep commits atomic and include test updates. Pull requests must link issues, outline scenario impact, list new commands or flags, and attach logs or screenshots when behavior changes. Request maintainer review and confirm CI passes before merge.

## Agent Configuration Tips
Store secrets in environment variables loaded via `.env.sample`; never commit real credentials. Keep the sample file aligned with keys referenced in `docker-compose.yml` and swarm manifests. Document new scenario knobs in `docs/configuration.md` alongside any Traefik labels or ports you add.

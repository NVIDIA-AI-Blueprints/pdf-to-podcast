# FlowSpeech v1 Migration Handoff

## Unreleased Candidate Verification (2026-10-27)

This section records the current local candidate, not a published fix. Runtime
source was not changed during this artifact/evidence refresh. The independently
reviewed source suite passed 253 tests; this refresh rebuilt a separately named
candidate and passed **253 extracted-runtime tests, zero failures**.

Candidate: `services/TTSService/dist/unreleased-20261027-final/flowspeech-v1-tts-review.tar.gz`

SHA-256: `5875b985d3d50b55a26d3a38730e2308c6a3f593d2605cb3a6043290a9b9d51c`

Frozen `flowspeech_v1.py` SHA-256:
`ccf5ede19867d355c7d773b234d8f7df4c6cc66e2d699b0666336a93511a618c`

The existing six-file allowlist matched the extracted archive and source byte
for byte. The credential-pattern scan passed. Current local tests (including
worker lifecycle and error privacy regressions) were run against the extracted
runtime via `FLOWSPEECH_TEST_ROOT`; tests and local verification helpers are not
included in the archive. This is source validation, not deployment validation.

### Command and Local Evidence

From the repository root, set `PY` to the existing Python 3.12.1 test interpreter
with HTTPX 0.28.1 and pytest 9.0.3:

```bash
env -i PATH=/usr/bin:/bin HOME=/private/tmp PYTHONDONTWRITEBYTECODE=1 "$PY" services/TTSService/dist/verify_unreleased_20261027.py unreleased-20261027-final
```

The local-only wrapper uses the unchanged `verify_bundle.py` with a new output
path, refuses an existing candidate directory, and verifies that the previous
fixed-path archive and frozen runtime hash remain unchanged. For another run,
use a fresh directory label instead of overwriting this evidence. Its
`validation.json` is alongside the candidate. Generated helpers, archives and
evidence under `dist/` are local artifacts, not files to stage or publish.

### Historical Evidence and Limits

The 2026-10-26 section below is retained verbatim as historical evidence; its
test counts and archive hash do not describe this candidate. Before this refresh,
earlier verification had already regenerated the fixed-name archive, so the
original 26 October archive bytes are no longer present at that path. This
refresh preserves the existing fixed-name file, whose SHA-256 equals the new
candidate SHA-256 above. It does not reconstruct or claim to revalidate the
historical archive.

No API keys, paid generation, commits, pushes, publishes, or version changes
were involved. No full Docker build/startup or deployed service validation was performed.
Independent cross-review covered source, not this new archive. A blocked sync
transport can finish its one in-flight operation after caller timeout; workers
remain bounded, with no queued late submission and no caller-owned client close.

## Historical Handoff (2026-10-26)


Date: 2026-10-26. Branch: `codex/add-flowspeech-tts-provider`.
Base commit: `85916f5fed436fba253bc7fa7efd070b8b0f88dd`.
Existing PR: https://github.com/NVIDIA-AI-Blueprints/pdf-to-podcast/pull/31

## Implementation

The service now submits one ordered multi-speaker v1 job per dialogue. A stable
UUID is derived from the service job ID, returned before background work and
recorded in progress messages. Reprocessing unchanged work reuses that UUID;
changed text or voices require a new service job ID. The PCM adapter interface
and WAV HTTP output remain, with strict FlowSpeech-only request models, live
voice discovery, and explicit recovery methods. The other service branch is
unchanged. Docker copies both required helper modules and compose forwards the
total timeout setting.

All HTTP tests use httpx.MockTransport; an autouse fixture rejects real socket
connections. No production key or paid generation was used. A pinned Ruff 0.14.2
binary wheel was installed under the owned cookbook directory, without source
build hooks. The existing Python test environment was used read-only with bytecode
writes disabled. No commits, pushes, publishes, or upstream PR edits were made.

The clones preserve the requested branches. Git 2.26.2 initially left partial
checkouts; system Git 2.39.3 completed and repaired only files from these newly
created clones before implementation. Both repositories were clean at that point.
No AGENTS.md exists in either checked-out Git tree. Cookbook CONTRIBUTING.md and
CLAUDE.md, plus the podcast README contribution section, were read.

The two adapter copies have identical Python ASTs (formatting follows each repo).
Both enforce stable caller-known UUIDs, strict input/result validation, normalized
identity correlation, pending/terminal/deleted states, read-only recovery, bounded
credential-free downloads, complete PCM WAV checks, and a total deadline. Retry-
After survives body-read failures; status retries wait at least five seconds;
explicit nonretryable API errors do not replay. Timeout workers may complete one
in-flight HTTP operation but cannot perform another request or paid submission.
No code automatically cancels a paid job.

## Exact Checks

Local Python 3.12.14, httpx 0.28.1, pytest 8.4.2, pydantic 2.12.3,
Ruff 0.14.2. Run from the repository root with
`PYTHONDONTWRITEBYTECODE=1 PYTEST_DISABLE_PLUGIN_AUTOLOAD=1`:

- `python -m pytest services/TTSService/tests_flowspeech --confcutdir=services/TTSService/tests_flowspeech -p no:cacheprovider --basetemp=services/TTSService/.test-tmp -q`:
  223 passed, 0 failed.
- `python services/TTSService/verify_bundle.py`: 223 passed, 0 failed against
  extracted runtime files. Six exact allowlisted files match source;
  secret-pattern scan passed.
- Ruff check and format-check passed for `flowspeech.py`, `flowspeech_v1.py`,
  `main.py`, `test_flowspeech.py`, `verify_bundle.py`, and
  `tests_flowspeech/`: 11 Python files.
- `git diff --check`: passed.
- Legacy endpoint, audioBase64, and originalText search in TTSService:
  no matches.

Service tests extract and execute the actual request models, endpoint, and
service methods without starting Redis, telemetry exporters, or live APIs.
They verify one multi-speaker POST, upfront recovery ID, strict fields/types,
voice mapping/catalog, private transport defaults, PCM compatibility, existing
other-service behavior, and Docker runtime file inclusion.

## Artifact

`services/TTSService/dist/flowspeech-v1-tts-review.tar.gz`

SHA-256:
`6ae254c6675ef8db096ed4cdd4d85c9e194e60b862f3e23f5a8c96465fc39e46`.
Review-only bundle; not a deployable container or separately published package.

## Changed Files

- `.gitignore`, `README.md`, `docker-compose.yaml`,
  `.github/workflows/flowspeech-offline.yml`.
- Under `services/TTSService/`: `Dockerfile`, `README.md`,
  `CHANGELOG.md`, `flowspeech.py`, `flowspeech_v1.py`, `main.py`,
  `test_flowspeech.py`, `verify_bundle.py`, this report.
- Under `services/TTSService/tests_flowspeech/`: `conftest.py`,
  `test_v1_contract.py`, `test_job_identifiers.py`, `test_wav_validation.py`,
  `test_hardening.py`, `test_service.py`.

## Coordinator Next Steps

Review and update the existing branch/PR only. Build the service with
`docker build -f services/TTSService/Dockerfile -t tts-service .` from the repo
root in an approved deployment environment. Preserve the existing default
service selection. The internal FlowSpeech convert methods now require an
explicit request UUID; the service passes its stable job-derived UUID.

The new offline CI matrix targets Python 3.11/3.12 but has not run remotely;
only 3.12 was tested locally. Full Docker startup and the repository-wide live
end-to-end test were not run. This integration has no independent package
version to bump. No implementation blocker remains from the scoped migration.

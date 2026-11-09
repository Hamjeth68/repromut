# E2 isolation pre-flight

**Status: passed.** Run on 2026-11-09 (Asia/Colombo time). Only our own check script (`preflight_check.py`) and the official `python:3.12-slim` image were used. No third-party repository code was run.

## Environment

| Item | Value |
|---|---|
| Host | macOS, Apple Silicon (10 CPU, 16 GiB RAM). About 41 GiB disk was free when the VM was created. |
| VM | Colima 0.10.3, profile `repromut-e2`, vz, aarch64, 4 CPU, 6 GiB RAM, **30 GiB** disk (reduced from the 60 GiB in the threat-model draft because of host free space; the 25 GB work cap is unchanged) |
| VM kernel | Linux 6.8.0-117-generic aarch64 (Ubuntu) |
| Docker | client 29.8.1, server 29.5.2, context `colima-repromut-e2` |
| Image | `python@sha256:5e2bdb1b0d542d5039cffb8181c65930093949194a65c365dfb1b0fe13a4fa5b` (`python:3.12-slim`) |
| VM mount | `--mount ~/repromut-e2-work:w` only |

## VM checks (`colima ssh -p repromut-e2`)

| Check | Result |
|---|---|
| `/Users/mac` contents | only `repromut-e2-work` (virtiofs) |
| `~/.ssh` visible | no |
| `~/Desktop` (ReproMut repository) visible | no |

## Container checks

Command:

```
docker run --rm --network none --read-only --tmpfs /tmp:size=512m --cap-drop ALL \
  --security-opt no-new-privileges --pids-limit 256 --cpus 2 --memory 3g --memory-swap 3g \
  --user 10001:10001 -v ~/repromut-e2-work/preflight:/check:ro python:3.12-slim python -I /check/check.py
```

| Check | Expected | Observed |
|---|---|---|
| uid:gid | non-root | 10001:10001 |
| Root filesystem writable | no | no (EROFS) |
| `/tmp` writable | yes | yes |
| DNS (`pypi.org`) | blocked | blocked (`gaierror`) |
| TCP to 1.1.1.1:443 | blocked | `ENETUNREACH` |
| TCP to VM host gateway 192.168.5.2:22 | blocked | `ENETUNREACH` |
| Network interfaces | `lo` only | `lo` only |
| `/Users` visible | no | no |
| Docker socket present | no | no |
| CapEff / CapBnd | 0 | 0 / 0 |
| NoNewPrivs | 1 | 1 |
| Seccomp | filter | 2 (filter) |
| pids.max | 256 | 256 |
| memory.max / swap | 3 GiB / 0 | 3221225472 / 0 |
| cpu.max | 2 CPUs | 200000 100000 |

## Not yet verified

These will be checked in the pilot, before any outcome runs:

- the 10-minute timeout enforced with `docker kill`;
- the 25 GB disk cap and the abort below 8 GB free.

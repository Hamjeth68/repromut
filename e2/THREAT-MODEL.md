# E2 threat model: running untrusted third-party repositories

Status: **DRAFT; VM and pre-flight approved and passed (env/PREFLIGHT.md).** No third-party code has been executed.

## Assets to protect

| Asset | Where it lives |
|---|---|
| Your home directory | Source code, documents, `~/.ssh`, browser profiles |
| Credentials | GitHub CLI tokens (keychain), git credentials, Zenodo/ORCID browser sessions |
| The ReproMut repository and its history | `~/Desktop/dev/repromut` |
| Machine integrity and availability | Disk is 37 GB free; 10 CPUs; 16 GB RAM |

## Adversary and failure model

Third-party repository code is **untrusted**. It may be:

- malicious, e.g. exfiltrating data or persisting itself;
- buggy, e.g. filling the disk, fork-bombing, or writing outside its directory;
- non-deterministic.

Install-time code (`setup.py`, build backends) is also untrusted.

## Controls

| Stage | Control |
|---|---|
| **Screening** (done) | Repositories are downloaded as commit-pinned tarballs and read as **text only**, never executed or imported. They are extracted with Python's `tarfile` `data` filter (blocks absolute paths, `..`, links and special files) into `~/repromut-e2-work/screening/src/`. |
| **Execution host** | A dedicated **Colima Linux VM** (profile `repromut-e2`), not macOS. The VM is created with `--mount ~/repromut-e2-work:w` **only**. That overrides Colima's default of mounting the whole home directory, so the VM cannot see `~/.ssh`, keychains, browser data or the ReproMut repository. |
| **Container** | Each run: `docker run --rm --network none --read-only --tmpfs /tmp:size=512m --cap-drop ALL --security-opt no-new-privileges --pids-limit 256 --cpus 2 --memory 3g --memory-swap 3g --user 10001:10001`. The Docker socket is **never** mounted. |
| **Build** | Dependency installation happens in a separate build container. It is the **only** stage with network access, and only to PyPI. Requirements are resolved by `uv pip compile --exclude-newer 2026-11-01` into a hash-locked lock file per repository. No credentials or secrets exist in the build context. |
| **Working copy** | Each run gets a **fresh copy** of the repository and fixtures. Outputs are copied out and the copy is deleted. Nothing is written back into the commit-pinned source tree. |
| **Time and resources** | 10-minute wall-clock timeout per run, enforced from outside the container (`docker kill`). Total disk for images and work is capped at 25 GB; the runner aborts below 8 GB free. |
| **Data out** | Only declared output files and stdout/stderr (each truncated at 5 MB) leave the container. They are parsed as data, never executed. |
| **Accounts** | Only your personal GitHub account `Hamjeth68`, used read-only for search and tarball download. No tokens are passed to the VM or the containers. |

## Residual risks (accepted only with your approval)

1. **VM or container escape.** This would expose `~/repromut-e2-work` only, not the rest of your home directory.
2. **Malicious install-time code during the networked build stage.** It could reach the internet but has nothing to steal; the build context contains no secrets.
3. **Resource exhaustion inside the VM.** The VM itself is capped at 4 CPUs, 6 GiB RAM and a 30 GiB disk (S10).

## Stop conditions

Stop and report if any of these happens:

- The isolation checks fail. The pre-flight test confirms that `--network none` blocks DNS and TCP, that the container cannot see `/Users`, and that it runs as non-root.
- A run writes outside its work copy.
- Free disk drops below 8 GB.

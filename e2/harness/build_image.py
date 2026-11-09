"""Build stage (networked, isolated container) for one repository: lock -> image(s) -> package lists.

Usage: python e2/harness/build_image.py e2/plans/<slug>.json
Reads plan["build"]:
  mode: "requirements" (declared file, hash-locked with uv) | "imports" (protocol default map + detected
        imports) | "uvlock" (committed uv.lock, uv sync --frozen --no-editable)
  python: "3.10" | "3.12" | "3.14"; requirements: repo-relative file; extra: [pkg, ...];
  variants: {image_key: "scikit-learn==X.Y.Z"}  (only scikit-learn changes; M-DEP / C-DEP)
  nltk: [package, ...]  (NLTK data prefetched at build, A1; SHA-256 of the archives recorded)
Writes ~/repromut-e2-work/build/<slug>/{lock*.txt, Dockerfile, packages_<key>.txt, images.json}.
No third-party code runs on the host; resolution, compilation and installation run in containers.
"""
import json
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

WORK = Path.home() / "repromut-e2-work"
PY = {"3.10": "python@sha256:6ff506466f8b1e981719b468cc0023b8ef000b983cdec0eafe119d01f379e31d",
      "3.12": None,  # filled by pull below
      "3.14": "python@sha256:9aaa474097d094040649f2162a627c0049b408f52138d980916788d80f04802f"}
UV = "uv==0.13.7"
DEFAULT_MAP = ["numpy", "scipy", "scikit-learn", "pandas", "matplotlib", "joblib"]
CUTOFF = "2026-11-01"


NET_EXIT = 3          # build-stage network unavailable: infrastructure, never an install failure (D11)


def sh(cmd, attempts=3, **kw):
    """Run a build-stage command; retry (network flakiness is infrastructure, not the repository)."""
    print("+", cmd if isinstance(cmd, str) else " ".join(cmd), flush=True)
    for i in range(attempts):
        try:
            return subprocess.run(cmd, shell=isinstance(cmd, str), check=True, text=True, **kw)
        except subprocess.CalledProcessError:
            if i == attempts - 1:
                raise
            wait_for_network()


def net_ok(img=None) -> bool:
    img = img or PY["3.10"]
    r = subprocess.run(["docker", "run", "--rm", img, "python", "-c",
                        "import urllib.request;urllib.request.urlopen('https://pypi.org/simple/uv/',timeout=30).read(2000)"],
                       capture_output=True, text=True)
    return r.returncode == 0


def wait_for_network(max_wait_min=60):
    for _ in range(max_wait_min // 5 + 1):
        if net_ok():
            return
        print("build-stage network unavailable; waiting 5 min", flush=True)
        time.sleep(300)
    print("NETWORK DOWN: aborting without classifying any repository", flush=True)
    sys.exit(NET_EXIT)


def base_image(v):
    if PY.get(v):
        return PY[v]
    sh(["docker", "pull", "-q", f"python:{v}-slim"], capture_output=True)
    out = subprocess.run(["docker", "image", "inspect", f"python:{v}-slim", "--format", "{{index .RepoDigests 0}}"],
                         capture_output=True, text=True, check=True).stdout.strip()
    PY[v] = out
    return out


def compile_lock(b: Path, img: str, v: str, src: str, dst: str, extra_flags: str = ""):
    sh(["docker", "run", "--rm", "-v", f"{b}:/b", "-w", "/b", img, "sh", "-c",
        f"pip install -q --timeout 60 --retries 5 {UV} && uv --version > uv_version.txt && "
        f"uv pip compile {src} --generate-hashes --exclude-newer {CUTOFF} --python-version {v} "
        f"--python-platform aarch64-unknown-linux-gnu {extra_flags} -o {dst} -q"])


def block(txt, name):
    m = re.search(rf"(?ms)^{re.escape(name)}==.*?(?=^\S|\Z)", txt)
    return m.group(0) if m else None


def docker_build(args, attempts=3):
    """Up to 3 attempts; before each retry the build-stage network is checked (D11)."""
    for i in range(attempts):
        r = subprocess.run(["docker", "build", "-q", *args], capture_output=True, text=True)
        if r.returncode == 0:
            return r
        wait_for_network()
    return r


def sk_version(lock_text):
    m = re.search(r"(?m)^scikit-learn==([0-9][^ \\]*)", lock_text)
    return m.group(1) if m else None


def auto_patch(b, img, v, ver):
    """C-DEP: nearest other patch release of the same minor version that has a binary wheel here."""
    if not ver:
        return None
    major, minor, patch = (re.findall(r"\d+", ver) + ["0", "0", "0"])[:3]
    cands = [f"{major}.{minor}.{p}" for p in sorted(set(range(0, int(patch) + 3)) - {int(patch)},
                                                    key=lambda p: (abs(p - int(patch)), p))]
    if minor and patch == "0":
        cands.append(f"{major}.{minor}")
    for c in cands:
        r = subprocess.run(["docker", "run", "--rm", img, "sh", "-c",
                            f"pip download -q --no-deps --only-binary=:all: scikit-learn=={c} -d /tmp/w >/dev/null 2>&1 && ls /tmp/w"],
                           capture_output=True, text=True)
        if r.returncode == 0 and r.stdout.strip() and c != ver:
            return f"scikit-learn=={c}"
    return None


def main(plan_path):
    plan = json.loads(Path(plan_path).read_text())
    wait_for_network()
    bc = plan["build"]
    slug = plan["repo"].replace("/", "__")
    tree = Path(plan["source_tree"]).expanduser()
    b = WORK / "build" / slug
    b.mkdir(parents=True, exist_ok=True)
    v = bc["python"]
    img = base_image(v)
    nltk = bc.get("nltk", [])
    nltk_cmd = (f" && /opt/venv/bin/python -m nltk.downloader -q -d /usr/share/nltk_data {' '.join(nltk)}"
                " && find /usr/share/nltk_data -name '*.zip' -exec sha256sum {} + | sort > /opt/nltk_sha256.txt") if nltk else ""
    images: dict = {}
    if bc["mode"] in ("requirements", "imports"):
        if bc["mode"] == "requirements":
            raw = (tree / bc["requirements"]).read_bytes()
            text = raw.decode("utf-16") if raw[:2] in (b"\xff\xfe", b"\xfe\xff") else raw.decode("utf-8", "replace")
        else:
            text = "\n".join(DEFAULT_MAP)
        lines = [l.strip() for l in text.replace("\r", "").splitlines() if l.strip() and not l.strip().startswith("#")]
        lines += bc.get("extra", [])
        (b / "requirements.in").write_text("\n".join(lines) + "\n")
        compile_lock(b, img, v, "requirements.in", "lock.txt")
        locks = {"base": "lock.txt"}
        base_lock = (b / "lock.txt").read_text()
        for key, spec in bc.get("variants", {}).items():
            if spec == "auto_patch":
                spec = auto_patch(b, img, v, sk_version(base_lock))
                if spec is None:
                    (b / f"build_{key}.log").write_text("no patch-level scikit-learn release with an aarch64 wheel\n")
                    images[key] = None
                    continue
            (b / f"{key}.in").write_text(spec + "\n")
            try:
                compile_lock(b, img, v, f"{key}.in", f"{key}_pkg.txt", "--no-deps --only-binary scikit-learn")
            except subprocess.CalledProcessError:
                (b / f"build_{key}.log").write_text(f"{spec}: no binary wheel for this Python/platform\n")
                images[key] = None
                continue
            new = block((b / f"{key}_pkg.txt").read_text(), "scikit-learn")
            old = block(base_lock, "scikit-learn")
            (b / f"lock_{key}.txt").write_text(base_lock.replace(old, new))
            locks[key] = f"lock_{key}.txt"
        (b / "Dockerfile").write_text(f"""# Build stage only (networked). Runtime containers are offline (THREAT-MODEL.md).
FROM {img}
ARG LOCK=lock.txt
RUN apt-get update && apt-get install -y --no-install-recommends build-essential cmake libgomp1 && rm -rf /var/lib/apt/lists/*
COPY ${{LOCK}} /opt/lock.txt
ENV PIP_DEFAULT_TIMEOUT=60 PIP_RETRIES=5 UV_HTTP_TIMEOUT=120
RUN python -m venv /opt/venv && /opt/venv/bin/pip install -q --upgrade "pip==25.3" "setuptools==80.9.0" "wheel==0.45.1" "Cython<3.2" \\
 && /opt/venv/bin/pip install -q --no-build-isolation --require-hashes --no-deps -r /opt/lock.txt \\
 && /opt/venv/bin/pip freeze > /opt/packages.txt{nltk_cmd}
ENV PATH=/opt/venv/bin:$PATH NLTK_DATA=/usr/share/nltk_data
USER 10001:10001
""")
        for key, lock in locks.items():
            if key in images and images[key] is None:
                continue
            tag = f"repromut-e2/{slug.lower()}:{key}"
            r = docker_build(["--build-arg", f"LOCK={lock}", "-t", tag, str(b)])
            images[key] = r.stdout.strip().splitlines()[-1] if r.returncode == 0 else None
            (b / f"build_{key}.log").write_text(r.stdout + r.stderr)
    elif bc["mode"] == "uvlock":
        snap = b / "src_snapshot"
        if snap.exists():
            shutil.rmtree(snap)
        shutil.copytree(tree, snap, symlinks=True)
        (b / "Dockerfile").write_text(f"""# Build stage only (networked): committed uv.lock (--frozen), project installed non-editably.
FROM {img}
ARG SKLEARN_OVERRIDE=""
COPY src_snapshot /build
WORKDIR /build
ENV UV_PROJECT_ENVIRONMENT=/opt/venv UV_PYTHON_DOWNLOADS=never UV_LINK_MODE=copy PIP_DEFAULT_TIMEOUT=60 PIP_RETRIES=5 UV_HTTP_TIMEOUT=120
RUN pip install -q "{UV}" && uv sync --frozen --no-dev --no-editable {" ".join("--extra " + e for e in bc.get("extras", []))} --python /usr/local/bin/python{v} \\
 && if [ -n "$SKLEARN_OVERRIDE" ]; then uv pip install --python /opt/venv/bin/python --no-deps "scikit-learn==$SKLEARN_OVERRIDE"; fi \\
 && uv pip freeze --python /opt/venv/bin/python > /opt/packages.txt{nltk_cmd} && cd / && rm -rf /build /root/.cache
ENV PATH=/opt/venv/bin:$PATH NLTK_DATA=/usr/share/nltk_data
WORKDIR /
USER 10001:10001
""")
        lock_ver = re.search(r'name = "scikit-learn"\nversion = "([^"]+)"', (tree / "uv.lock").read_text()).group(1)
        keys = {"base": ""}
        for k, sp in bc.get("variants", {}).items():
            keys[k] = (auto_patch(b, img, v, lock_ver) or "").split("==")[-1] if sp == "auto_patch" else sp.split("==")[1]
        for key, ver in keys.items():
            if key != "base" and not ver:
                images[key] = None
                continue
            tag = f"repromut-e2/{slug.lower()}:{key}"
            r = docker_build(["--build-arg", f"SKLEARN_OVERRIDE={ver}", "-t", tag, str(b)])
            images[key] = r.stdout.strip().splitlines()[-1] if r.returncode == 0 else None
            (b / f"build_{key}.log").write_text(r.stdout + r.stderr)
    else:
        raise ValueError(bc["mode"])
    for key, iid in images.items():
        if iid:
            pk = subprocess.run(["docker", "run", "--rm", "--network", "none", iid, "cat", "/opt/packages.txt"],
                                capture_output=True, text=True).stdout
            (b / f"packages_{key}.txt").write_text(pk)
    (b / "images.json").write_text(json.dumps(images, indent=1))
    print(json.dumps(images, indent=1))


if __name__ == "__main__":
    main(sys.argv[1])

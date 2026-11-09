import os, socket, json, pathlib
r = {}
r["uid_gid"] = (os.getuid(), os.getgid())
try: open("/root_write_test","w"); r["rootfs_writable"]=True
except OSError as e: r["rootfs_writable"]=f"no ({e.errno})"
try: open("/tmp/x","w").write("ok"); r["tmp_writable"]=True
except OSError as e: r["tmp_writable"]=str(e)
try: socket.getaddrinfo("pypi.org",443); r["dns"]="RESOLVED"
except Exception as e: r["dns"]=f"blocked ({type(e).__name__})"
for host in ("1.1.1.1","192.168.5.2"):
    s=socket.socket(); s.settimeout(3)
    try: s.connect((host,443 if host=="1.1.1.1" else 22)); r[f"tcp_{host}"]="CONNECTED"
    except Exception as e: r[f"tcp_{host}"]=f"blocked ({type(e).__name__}: {e})"
    finally: s.close()
r["interfaces"]=sorted(os.listdir("/sys/class/net"))
r["users_visible"]=os.path.exists("/Users")
r["docker_sock"]=os.path.exists("/var/run/docker.sock")
st={l.split(":")[0]:l.split(":")[1].strip() for l in open("/proc/self/status") if l.startswith(("CapEff","CapBnd","NoNewPrivs","Seccomp"))}
r.update(st)
cg=pathlib.Path("/sys/fs/cgroup")
for f in ("pids.max","memory.max","memory.swap.max","cpu.max"):
    p=cg/f; r[f]=p.read_text().strip() if p.exists() else "n/a"
r["mounts_with_work"]=[l.split()[1] for l in open("/proc/self/mounts") if "work" in l or "Users" in l]
print(json.dumps(r,indent=1))

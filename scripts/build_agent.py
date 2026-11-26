#!/usr/bin/env python3
"""Package the agent for AgentCore Runtime (direct code deploy, Python 3.13 on arm64).

    python scripts/build_agent.py        -> build/agent/ (agent code + its libraries), zipped and uploaded by `cdk deploy`

Libraries are downloaded as ready-made arm64 Linux wheels, so this works from any laptop or CI runner (no Docker).
"""
import os
import shutil
import subprocess
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
OUT = os.path.join(ROOT, "build", "agent")


def main():
    shutil.rmtree(OUT, ignore_errors=True)
    os.makedirs(OUT)
    subprocess.run([sys.executable, "-m", "pip", "install", "-q", "--target", OUT, "--platform", "manylinux2014_aarch64",
                    "--implementation", "cp", "--python-version", "3.13", "--only-binary=:all:", "--upgrade",
                    "-r", os.path.join(ROOT, "agent", "requirements.txt")], check=True)
    for name in os.listdir(os.path.join(ROOT, "agent")):
        if name.endswith(".py"):
            shutil.copy(os.path.join(ROOT, "agent", name), OUT)
    for dirpath, dirnames, _ in os.walk(OUT):                      # smaller zip: no caches
        for d in [d for d in dirnames if d == "__pycache__"]:
            shutil.rmtree(os.path.join(dirpath, d))
    size = sum(os.path.getsize(os.path.join(p, f)) for p, _, fs in os.walk(OUT) for f in fs)
    print(f"built {os.path.relpath(OUT, ROOT)} ({size / 1e6:.0f} MB)")


if __name__ == "__main__":
    main()

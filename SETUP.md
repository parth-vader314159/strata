# Getting STRATA running

Five minutes on any machine. No database to install, no Docker required, no
broker, no cloud account. After the first `pip install`, no network at all.

---

## What you need

| | |
|---|---|
| **Python 3.10+** | Tested on 3.11 and 3.12. Check: `python3 --version` |
| **A terminal** | Terminal on macOS/Linux, PowerShell on Windows |
| **~500 MB disk** | Dependencies plus generated demo data |

---

## 1 · Check Python

```bash
python3 --version
```

<details><summary><b>If it is missing or older than 3.10</b></summary>

**Windows** — [python.org/downloads](https://www.python.org/downloads/). During
install, **tick "Add Python to PATH"** on the first screen. This is the single
most common thing people miss, and everything else fails without it. Then use
`python` instead of `python3` below.

**macOS** — `brew install python@3.12`, or download from python.org.

**Ubuntu/Debian** — `sudo apt install python3 python3-venv python3-pip`
</details>

## 2 · Unzip and enter

```bash
unzip strata.zip && cd strata
```

You should see `strata.py`, `README.md`, and folders `strata/`, `grammars/`,
`docs/`, `tests/`, `deck/`.

## 3 · Virtual environment

**macOS / Linux**
```bash
python3 -m venv .venv && source .venv/bin/activate
```

**Windows PowerShell**
```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
```

<details><summary><b>Windows: "running scripts is disabled on this system"</b></summary>

```powershell
Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned
```
</details>

Your prompt should now start with `(.venv)`.

## 4 · Install

```bash
pip install -r requirements.txt
```

The **only** step that needs the internet. For the test suite, use
`requirements-dev.txt` instead — it adds pytest and includes everything above.

## 5 · Check

```bash
python3 strata.py check
```

Expect: 10 grammars across 7 structural families, "all grammars valid and
compiled".

## 6 · Run the demonstration

```bash
python3 strata.py demo
```

Ninety seconds, eight steps: generate a multi-vendor corpus, ingest it, prove
losslessness byte-for-byte, show traceability, issue a Merkle proof, show
quarantine, onboard an unknown vendor format live, and rewind history under the
new grammar.

**If this prints without errors, everything works.**

## 7 · Open the console

```bash
python3 strata.py console
```

Then **http://localhost:8400**.

Try it in this order — it is the demo in UI form:

1. **Overview** — press *Generate traffic*, watch the pipeline fill
2. **Live stream** — click any row
3. **Inspector** — the original bytes with every extracted value highlighted
   and linked to the OCSF field it became. Hover either side.
4. **Quarantine** → *Onboard these →*
5. **Forge** → *Analyse & propose* → *Publish*. A new source, live, no restart.
6. **Integrity** → *Run full audit*, then take a record id and prove it
7. **Rewind** → *Run rewind*

`⌘K` (or `Ctrl+K`) opens a command palette. Ctrl+C stops the server.

---

## Everything else

```
python3 strata.py audit                      prove losslessness + integrity
python3 strata.py prove <record-id>          Merkle inclusion proof
python3 strata.py rewind --dry-run           re-derive history
python3 strata.py bench --workers 4          measured throughput
python3 strata.py forge yourfile.log --id your.source
python3 strata.py query "SELECT vendor, count(*) FROM events GROUP BY 1"
python3 strata.py serve                      live syslog listeners
python3 -m pytest -q                         91 tests (needs requirements-dev.txt)
```

Or with `make`: `make demo`, `make test`, `make audit`, `make bench`, `make all`.

---

## Common problems

<details><summary><b>"python3: command not found" (Windows)</b></summary>

Use `python`. If that also fails, Python is not on your PATH — reinstall with
"Add Python to PATH" ticked.
</details>

<details><summary><b>"externally-managed-environment" from pip</b></summary>

Your system Python is protected (normal on Ubuntu 23+ and Homebrew). Use the
virtual environment from step 3 — that is exactly what it is for.
</details>

<details><summary><b>"another STRATA process already holds the ledger"</b></summary>

Working as intended. The ledger is single-writer by design, so a second
instance refuses rather than corrupting segment files. Stop the other process,
or point this one at a different directory. If a server is still running from
earlier, find it with `ps aux | grep strata`.
</details>

<details><summary><b>"No module named strata"</b></summary>

Wrong directory. `cd` into the folder containing `strata.py`.
</details>

<details><summary><b>Port 8400 already in use</b></summary>

`python3 strata.py console --port 9000`
</details>

<details><summary><b>The demo skips step 7 (nothing to onboard)</b></summary>

A previous run published `grammars/meridian.gateway.yaml`, so the "unknown"
format is now known. `strata demo` deletes it at the start; if you published it
yourself from the Forge, delete that file and re-run.
</details>

<details><summary><b>Start completely fresh</b></summary>

```bash
rm -rf var                              # Windows: rmdir /s var
rm -f grammars/meridian.gateway.yaml
```
Everything generated lives in `var/`. Deleting it loses nothing but demo output.
</details>

---

## Docker

```bash
cp .env.example .env
python3 -c "import secrets;print(secrets.token_hex(32))"    # paste into STRATA_SECRET
docker compose up -d
```

Console on 8400, syslog on UDP 514 and TCP 601.

## Air-gapped

On a connected machine: `./build-bundle.sh`. Carry `offline-bundle/` across on
a USB stick, then `./install-offline.sh`. `pip` runs `--no-index`, so reaching
the network is impossible rather than merely unnecessary. Checklist:
[docs/VERIFY.md](docs/VERIFY.md).

---

## Where to go next

| You want to… | Read |
|---|---|
| Present this to judges | [docs/DEMO-SCRIPT.md](docs/DEMO-SCRIPT.md) |
| Verify the claims yourself | [docs/VERIFY.md](docs/VERIFY.md) |
| Understand the design decisions | [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) |
| Defend the security design | [docs/THREAT-MODEL.md](docs/THREAT-MODEL.md) |
| Defend the throughput numbers | [docs/BENCHMARK.md](docs/BENCHMARK.md) |
| See the field mappings | [docs/GRAMMAR-REFERENCE.md](docs/GRAMMAR-REFERENCE.md) |
| Write a grammar | README § "Writing a grammar" |

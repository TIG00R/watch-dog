<p align="center">
  <img src="logo.png" alt="watch_dog logo" width="220" />
</p>

<h1 align="center">watch-dog</h1>

<p align="center">
  <em>A small directory watcher — refactored from very old code and published for fun, not as a production tool.</em>
</p>

<p align="center">
  <sub>This repo used to describe a broader &quot;Tiger&quot; security-toolkit idea; the <strong>current codebase</strong> in this tree is only the <strong>watch-dog</strong> watcher.</sub>
</p>

---

## What it does

**watch-dog** polls a folder tree on a timer, compares file and directory state to a simple in-memory index, and prints structured lines when something is **added**, **removed**, or **updated**. It does not use OS-level file notifications; it is a straightforward Python script for learning and experimenting.

- Recursive scan under a path you choose  
- Timestamps and scan cycle in each log line  
- On Windows, optional **owner** hint for updated files (best-effort ACL lookup via PowerShell)  
- ASCII banner loaded from `ascii_art.txt` next to the script  

---

## Installation

No third-party packages are required (standard library only). Use **Python 3.8+**.

```bash
git clone https://github.com/TIG00R/watch-dog.git
cd watch-dog
```

There is nothing to `pip install` for core usage. See [`requirements.txt`](requirements.txt) for notes.

---

## Usage

**Interactive** (prompts for a path):

```bash
python watch-dog.py
```

**Non-interactive** (recommended for scripts or CI):

```bash
python watch-dog.py "C:\path\to\folder"
```

On Linux or macOS:

```bash
python watch-dog.py /home/you/projects/something
```

---


## License

Add a license if you publish this repo (e.g. MIT). Until then, all rights reserved unless you say otherwise.

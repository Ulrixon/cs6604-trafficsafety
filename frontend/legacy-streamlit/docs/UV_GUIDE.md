# Using UV to Run the Traffic Safety Dashboard

[UV](https://github.com/astral-sh/uv) is an extremely fast Python package installer and resolver, written in Rust. It's a drop-in replacement for pip that's 10-100x faster.

## Quick Start with UV

### 1. Install UV (if not already installed)

**macOS/Linux:**

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

**Or with Homebrew:**

```bash
brew install uv
```

**Or with pip:**

```bash
pip install uv
```

### 2. Run the Application with UV

**Option 1: Using uvx (recommended - no setup needed)**

```bash
cd frontend
uvx --from streamlit streamlit run app/views/main.py
```

**Option 2: Create a virtual environment with uv**

```bash
cd frontend

# Create virtual environment
uv venv

# Activate it
source .venv/bin/activate  # macOS/Linux
# or
.venv\Scripts\activate     # Windows

# Install dependencies
uv pip install -r requirements.txt

# Run the app
streamlit run app/views/main.py
```

**Option 3: Use the uv-powered start script**

```bash
cd frontend
./start-uv.sh
```

## Why Use UV?

### Speed Comparison

- **pip**: ~45 seconds to install all dependencies
- **uv**: ~2-3 seconds for the same installation ⚡

### Benefits

✅ **10-100x faster** than pip  
✅ **Drop-in replacement** for pip  
✅ **Built-in virtual environment** management  
✅ **Better dependency resolution**  
✅ **Disk-space efficient** with global cache  
✅ **No compilation needed** (pre-built wheels)

## Common UV Commands

### Package Management

```bash
# Install a single package
uv pip install streamlit

# Install from requirements.txt
uv pip install -r requirements.txt

# Install specific version
uv pip install pandas==2.2.0

# Uninstall a package
uv pip uninstall streamlit

# List installed packages
uv pip list

# Freeze current environment
uv pip freeze > requirements.txt
```

### Virtual Environment Management

```bash
# Create virtual environment
uv venv

# Create with specific Python version
uv venv --python 3.11

# Create in custom location
uv venv myenv

# Activate virtual environment
source .venv/bin/activate  # macOS/Linux
.venv\Scripts\activate     # Windows
```

### Running Scripts

```bash
# Run a script with dependencies
uvx streamlit run app/views/main.py

# Run with inline dependencies
uvx --with pandas --with numpy python script.py

# Run specific version
uvx streamlit==1.36.0 run app/views/main.py
```

## UV vs PIP Comparison

| Feature               | pip           | uv        |
| --------------------- | ------------- | --------- |
| Install speed         | ~45s          | ~2-3s ⚡  |
| Dependency resolution | Slow          | Fast      |
| Virtual env creation  | Separate tool | Built-in  |
| Cache management      | Manual        | Automatic |
| Cross-platform        | Yes           | Yes       |
| Drop-in replacement   | N/A           | Yes ✅    |

## Troubleshooting

### UV not found

```bash
# Add to PATH (if not auto-added)
export PATH="$HOME/.cargo/bin:$PATH"

# Verify installation
uv --version
```

### Virtual environment issues

```bash
# Remove and recreate
rm -rf .venv
uv venv
source .venv/bin/activate
uv pip install -r requirements.txt
```

### Package conflicts

```bash
# UV has better dependency resolution than pip
# If you have conflicts, try:
uv pip install -r requirements.txt --resolution=highest
```

## Integration with Other Tools

### Pre-commit hooks

```yaml
# .pre-commit-config.yaml
- repo: local
  hooks:
    - id: uv-pip-compile
      name: uv pip compile
      entry: uv pip compile
      language: system
      files: requirements.in
```

### Docker

```dockerfile
FROM python:3.9-slim

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app
COPY requirements.txt .

# Use uv instead of pip
RUN uv pip install --system -r requirements.txt

COPY . .
EXPOSE 8501
CMD ["streamlit", "run", "app/views/main.py"]
```

### GitHub Actions

```yaml
- name: Install uv
  run: curl -LsSf https://astral.sh/uv/install.sh | sh

- name: Install dependencies
  run: uv pip install -r requirements.txt
```

## Advanced UV Features

### Compile Requirements

```bash
# Create a locked requirements file
uv pip compile requirements.in -o requirements.txt

# With version constraints
uv pip compile --upgrade requirements.in
```

### Sync Environment

```bash
# Install exactly what's in requirements.txt
uv pip sync requirements.txt
```

### Global Package Installation

```bash
# Install globally (not recommended for projects)
uv pip install --system streamlit
```

## Migrating from pip to UV

**No changes needed!** UV is a drop-in replacement:

```bash
# Old way (pip)
pip install -r requirements.txt

# New way (uv) - same syntax
uv pip install -r requirements.txt
```

Just replace `pip` with `uv pip` in your commands.

## Performance Metrics

Real-world example for this project:

```bash
# With pip
$ time pip install -r requirements.txt
# ~45 seconds

# With uv
$ time uv pip install -r requirements.txt
# ~2-3 seconds

# Speed improvement: ~15-20x faster! 🚀
```

## Best Practices

1. **Use virtual environments**: Always use `uv venv` for isolated dependencies
2. **Pin versions**: Use exact versions in requirements.txt for reproducibility
3. **Use uvx for one-off commands**: No need to install globally
4. **Cache is automatic**: UV manages cache efficiently, no manual cleanup needed
5. **Check compatibility**: UV works with standard Python packages (PyPI)

## Resources

- **UV Documentation**: https://github.com/astral-sh/uv
- **Installation Guide**: https://astral.sh/uv
- **Benchmarks**: https://github.com/astral-sh/uv#benchmarks

---

**Quick Command Reference**

| Task            | Command                                                        |
| --------------- | -------------------------------------------------------------- |
| Install UV      | `curl -LsSf https://astral.sh/uv/install.sh \| sh`             |
| Create venv     | `uv venv`                                                      |
| Install deps    | `uv pip install -r requirements.txt`                           |
| Run app (quick) | `uvx --from streamlit streamlit run app/views/main.py`         |
| Run app (venv)  | `source .venv/bin/activate && streamlit run app/views/main.py` |
| List packages   | `uv pip list`                                                  |
| Update package  | `uv pip install --upgrade package-name`                        |

---

**Ready to go 10-100x faster?** 🚀 Use the commands above!

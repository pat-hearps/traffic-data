Use [uv](https://docs.astral.sh/uv/getting-started/installation/) to create virtual environment with python 3.12

```
# make sure you have python 3.12
uv python install 3.12 --preview

# create venv
uv venv .venv --python 3.12

# then install requirements
uv pip install -r pyproject.toml --all-extras
```



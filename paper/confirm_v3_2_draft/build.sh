#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"
python3 prepare_paper_data.py
latexmk -xelatex -interaction=nonstopmode -halt-on-error main.tex


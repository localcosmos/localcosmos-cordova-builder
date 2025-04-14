#!/bin/bash
set -euo pipefail

##########################################################################################
#
# USAGE:
#   bash run_jobs.sh --python-venv /path/to/venv
#
##########################################################################################

# Optional: print help if no args or --help is passed
if [[ $# -eq 0 || "${1:-}" == "--help" ]]; then
    echo "Usage: $0 --python-venv /path/to/venv"
    exit 0
fi

# Parse long options
optspec=":cfim-:"
while getopts "$optspec" optchar; do
  case "${optchar}" in
    -)
      case "${OPTARG}" in
        python-venv)
          val="${!OPTIND}"; OPTIND=$(( OPTIND + 1 ))
          echo "Parsing option: '--${OPTARG}', value: '${val}'" >&2
          PYTHON_VENV="$val"
          ;;
        *)
          echo "Unknown option --${OPTARG}" >&2
          exit 1
          ;;
      esac;;
    *)
      echo "Unknown short option: -${optchar}" >&2
      exit 1
      ;;
  esac
done

# Ensure PYTHON_VENV is set
if [[ -z "${PYTHON_VENV:-}" ]]; then
    echo "PYTHON_VENV is unset. Use --python-venv /path/to/venv . Aborting."
    exit 1
else
    echo "PYTHON_VENV is set to '$PYTHON_VENV'"
fi

# Get the absolute path to this script
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"

echo "Running jobs for directory: $DIR"

# Activate virtual environment
source "$PYTHON_VENV/bin/activate"

# Add node and system paths (if needed)
export PATH="$PATH:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"

# Run the Python job
cd "$DIR" && python3 ./run_jobs.py


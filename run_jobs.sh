#!/bin/bash

##########################################################################################
#
# USAGE
#	bash run_jobs.sh --python-venv /path/to/venv
##########################################################################################

# required are PYTHON_ENV
optspec=":cfim-:"
while getopts "$optspec" optchar; do
  case "${optchar}" in
    -)
      echo "opting: ${OPTARG}"
      case "${OPTARG}" in
        python-venv)
          val="${!OPTIND}"; OPTIND=$(( $OPTIND + 1 ))
          echo "Parsing option: '--${OPTARG}', value: '${val}'" >&2;
          PYTHON_VENV=$val
          ;;
      esac;;
  esac
done

# check if PYTHON_VENV is set
if [ -z ${PYTHON_VENV+x} ]; 
	then 
		echo "PYTHON_VENV is unset. Use --python-venv=/path/to/venv . Aborting.";
		exit 1
else
	echo "PYTHON_VENV is set to '$PYTHON_VENV'";
fi

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"

echo "running jobs for $DIR"


# activate virtual environment
source $PYTHON_VENV/bin/activate

# make node available
export PATH=$PATH:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin

cd $DIR &&\
python3 ./run_jobs.py

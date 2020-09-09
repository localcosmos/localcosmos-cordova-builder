#!/bin/bash

##########################################################################################
#
# USAGE
#	bash run_jobs.sh --python-env=/path/to/venv
##########################################################################################

# required are PYTHON_ENV
optspec=":cfim-:"
while getopts "$optspec" optchar; do
  case "${optchar}" in
    -)
      case "${OPTARG}" in
        python-venv)
          val="${!OPTIND}"; OPTIND=$(( $OPTIND + 1 ))
          echo "Parsing option: '--${OPTARG}', value: '${val}'" >&2;
          PYTHON_VENV=$val
          ;;
        workdir)
          val="${!OPTIND}"; OPTIND=$(( $OPTIND + 1 ))
          echo "Parsing option: '--${OPTARG}', value: '${val}'" >&2;
          WORKDIR=$val
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


# check if WORKDIR is set
if [ -z ${WORKDIR+x} ]; 
	then 
		echo "WORKDIR is unset. Use --workdir=/path/to/workdir . Aborting.";
		exit 1
else
	echo "WORKDIR is set to '$WORKDIR'";
fi


DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"

echo "running jobs for $DIR"

# activate virtual environment
source $PYTHON_VENV/bin/activate

# make node available
export PATH=$PATH:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin

cd $DIR &&\
python3 ./run_jobs.py --workdir=$WORKDIR

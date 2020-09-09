##############################################################################################################
#
# Python Script for connecting to an LC AppKitJob API, running those jobs and returning the result
#
# this script is intended for CRONJOBS
#
# USAGE:
#  python3 run_jobs.py --force-run --rerun-unsuccessful
#  the workdir must contain jobmanager_settings.json and build_config.json
#  logs will be saved in workdir/logs
##############################################################################################################

from tendo.singleton import SingleInstance
from localcosmos_cordova_builder.JobManager import JobManager

import os, json, sys, pathlib, getopt

from datetime import datetime

WORKDIR = os.environ.get('LOCALCOSMOS_CORDOVA_BUILDER_WORKDIR', None)
if not WORKDIR:
    raise ValueError('WORKDIR environment variable not set')

ERROR_RETRY_TIMEOUT_MINUTES = 5
short_options = []
long_options = ['force-run','rerun-unsuccessful']


if __name__ == "__main__":

    me = SingleInstance()

    force_run = False
    rerun_unsuccessful = False

    full_cmd_arguments = sys.argv

    # Keep all but the first
    argument_list = full_cmd_arguments[1:]

    try:
        arguments, values = getopt.getopt(argument_list, short_options, long_options)
    except getopt.error as err:
        # Output error, and return with an error code
        print (str(err))
        sys.exit(2)

    for argument, value in arguments:

        if argument == '--force-run':
            force_run = True

        elif argument == '--rerun-unsuccessful':
            rerun_unsuccessful = True

    if force_run == True:
        print('forcing the run')

    if rerun_unsuccessful == True:
        print('rerunning previously unsuccessful jobs')


    error_count_path = os.path.join(WORKDIR, 'error_count.json')

    error_log = {
        'error_count' : 0,
        'last_tried_at' : None,
    }

    if os.path.isfile(error_count_path):
        with open(error_count_path, 'r') as logfile:
            error_log = json.loads(logfile.read())

    if error_log['error_count'] < 10 or force_run == True:

        job_manager = JobManager()

        run = True

        # if an error has occurred, wait 5 minutes
        last_tried_at = error_log.get('last_tried_at', None)

        if last_tried_at:
            now = datetime.now()
            now_timestamp = now.timestamp()

            delta_seconds = now_timestamp - last_tried_at
            delta_minutes = delta_seconds / 60
            
            if error_log['error_count'] > 0 and delta_minutes < ERROR_RETRY_TIMEOUT_MINUTES:
                run = False
            
        
        if run == True or force_run == True:
            

            try:
                job_manager.update_joblist()

                job_manager.run_jobs(rerun_unsuccessful=rerun_unsuccessful)
                job_manager.report_job_results()

                error_log['error_count'] = 0
                error_log['last_tried_at'] = datetime.now().timestamp()
                
            except Exception as e:
                job_manager.logger.error(e, exc_info=True)
                error_log['error_count'] = error_log['error_count'] + 1
                error_log['last_tried_at'] = datetime.now().timestamp()

                if error_log['error_count'] == 10:
                    job_manager.logger.error('too many errors. gave up trying. waiting for repair')

            with open(error_count_path, 'w') as logfile:
                logfile.write(json.dumps(error_log))
            
        

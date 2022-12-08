##################################################################################################################
# JOB MANAGER
# - query lc server for build and release jobs
# - manage the job queue
# - execute the jobs
##################################################################################################################
import datetime, json, os, logging, platform, shutil, zipfile, sys, pathlib
from urllib.parse import urlencode, quote_plus, urljoin
from urllib import request

from .CordovaAppBuilder import CordovaAppBuilder

from localcosmos_cordova_builder.MetaAppDefinition import MetaAppDefinition
from localcosmos_cordova_builder.logger import get_logger

from peewee import *

from .urllib_request_upload_files import MultiPartForm


##################################################################################################################
# ORM
#
##################################################################################################################

this_computer = platform.node()

WORKDIR = os.getenv('LOCALCOSMOS_CORDOVA_BUILDER_WORKDIR')
if not WORKDIR:
    raise ValueError('LOCALCOSMOS_CORDOVA_BUILDER_WORKDIR environment variable not found')

db_path = os.path.join(WORKDIR, 'localcosmos.db')
db = SqliteDatabase(db_path)


JOB_STATUS = (
    'waiting_for_assignment', 'assigned', 'in_progress', 'success', 'failed',
)

class AppKitJob(Model):

    uuid = UUIDField(unique=True)
    lc_id = IntegerField()
    meta_app_uuid = UUIDField()
    meta_app_definition = TextField() # JSON!
    app_version = IntegerField()
    platform = CharField()
    job_type = CharField()
    parameters = TextField(null=True)

    fetched_at = DateTimeField(default=datetime.datetime.now)

    assigned_to = CharField()

    # this field is not present at app_kit_api.models.AppKitJobs
    assignment_reported_at = DateTimeField(null=True)


    # AFTER building, fill the following 3 columns
    finished_at = DateTimeField(null=True)
    job_result = TextField(null=True)
    job_status = CharField(max_length=50, default='waiting_for_assignment')

    # output, like ipa filepaths can be stores as json in this column
    output = TextField(null=True)
    
    # the result has to be reported back to the lc server
    result_reported_at = DateTimeField(null=True)
    

    class Meta:
        database = db

        indexes = (
            (('meta_app_uuid', 'job_type'), True),
        )


db.connect()
db.create_tables([AppKitJob])
db.close()

##################################################################################################################
# JOBMANAGER
#
##################################################################################################################
class JobManagerAlreadyRunning(Exception):
    pass


class InvalidJobTypeError(Exception):
    pass


class JobManager:
    
    def __init__(self):

        api_settings_filepath = os.path.join(WORKDIR, 'app_builder_settings.json')

        with open(api_settings_filepath, 'r') as settings_file:
            self.settings = json.loads(settings_file.read())

        self.logger = self._get_logger()
            

    def _get_logger(self):
    
        if hasattr(self, 'logger'):
            return self.logger

        logger_name = '{0}-{1}'.format(__name__, self.__class__.__name__)
        # for cross platform logging use a logfolder within the folder in which JobManager.py lies
        logging_folder = os.path.join(WORKDIR, 'log/job_manager/')

        smtp_logger = self.settings['email']
        logger = get_logger(__name__, logging_folder, 'log', smtp_logger=smtp_logger)

        return logger

    @property
    def apps_root_folder(self):
        # same as settings.APP_KIT_ROOT on Linux/LCAppKit
        return self.settings['apps_root_folder']
        
    def get_app_release_path(self, meta_app_definition):
        return os.path.join(self.apps_root_folder, meta_app_definition.uuid, 'version', str(meta_app_definition.current_version), 'release')
        
    def get_app_build_sources_path(self, meta_app_definition):
        app_release_path = self.get_app_release_path(meta_app_definition)
        return os.path.join(app_release_path, 'sources')
        
    def get_cordova_build_path(self, meta_app_definition):
        app_release_path = self.get_app_release_path(meta_app_definition)
        return os.path.join(app_release_path, 'cordova')
    
    # update joblist an run jobs
    def update_joblist(self):

        db.connect()

        self.logger.info('updating job list')

        data = {
            'platform' : self.settings['platform'],
        }

        request = JobListRequest(self.settings, data=data)
        
        response = request.execute()
        
        if response is not None:

            # results contain only unassigned jobs
            for job in response['results']:

                # meta_app_uuid and job_type
                results = AppKitJob.select().where(AppKitJob.meta_app_uuid==job['meta_app_uuid'],
                                                   AppKitJob.job_type==job['job_type'])

                result_count = len(results)

                if result_count > 0:
                    db_job = results.get()
                    db_job.delete_instance()
                    
                db_job = AppKitJob(
                    uuid = job['uuid'],
                    lc_id = job['id'],
                    meta_app_uuid = job['meta_app_uuid'],
                    meta_app_definition = json.dumps(job['meta_app_definition']),
                    app_version = job['app_version'],
                    platform = job['platform'],
                    job_type = job['job_type'],
                    parameters = json.dumps(job['parameters']),

                    assigned_to = this_computer,
                )

                db_job.save()

                if job['assigned_to'] == None:

                    assignment_data = {
                        'assigned_to' : this_computer,
                        'status' : 'assigned',
                    }

                    assign_request = JobAssignRequest(self.settings, db_job.lc_id,
                                                      data=assignment_data)
                    assign_request.execute()

                    db_job.assignment_reported_at = datetime.datetime.now()
                    db_job.save()
                    
        db.close()


    def run_jobs(self, rerun_unsuccessful=False, from_scratch=False):
    
        self.logger.info('running jobs')

        db.connect()

        if rerun_unsuccessful == True:
            self.logger.info('re-running unsuccessful jobs')
            unfinished_jobs = AppKitJob.select().where((AppKitJob.finished_at==None) | (AppKitJob.job_status=='failed'))
        else:
            unfinished_jobs = AppKitJob.select().where(AppKitJob.finished_at==None)
        
        if not unfinished_jobs:
            self.logger.info('no unfinished jobs found. maybe try --rerun-successful.')
        
        for job in unfinished_jobs:

            job_method_name = 'run_{0}_job'.format(job.job_type)

            if not hasattr(self, job_method_name):
                raise InvalidJobTypeError('Job of type {0} is not supported'.format(job.job_type))

            run_job = getattr(self, job_method_name)

            self.logger.info('running job {0}'.format(str(job.uuid)))

            success = True
            job_status = 'success'

            job_result = {
                'warnings' : [],
                'errors' : [],
            }

            try:
                run_job(job, from_scratch=from_scratch)
            except Exception as e:
                self.logger.error(e, exc_info=True)
                job_result['errors'].append(str(e))

                success = False
                job_status = 'failed'


            job_result['success'] = success
            job.finished_at = datetime.datetime.now()
            job.job_result = json.dumps(job_result)
            job.job_status =job_status
            job.save()
            
            self.logger.info('finished job {0} with success=={1}'.format(str(job.uuid), str(success)))

        db.close()

        self.logger.info('finished running all jobs (if any).')
    
    
    def run_build_job(self, job, from_scratch=False):

        meta_app_json = json.loads(job.meta_app_definition)

        meta_app_definition = MetaAppDefinition(meta_app_definition=meta_app_json)

        # download zipfile and unzip it into a temporary folder
        parameters = json.loads(job.parameters)
        zipfile_url = urljoin(self.settings['localcosmos_server_url'], parameters['zipfile_url'])

        # app_build_sources_path is e.g. on linux with app kit: /{settings.APP_KIT_ROOT}/{APP_UUID}/version/{APP_VERSION}/release/sources
        # subfolders of sources are_ common/www , android/www , ios/www
        app_build_sources_path = self.get_app_build_sources_path(meta_app_definition)
        
        zip_tmp_folder = os.path.join(app_build_sources_path)

        if os.path.isdir(zip_tmp_folder):
            shutil.rmtree(zip_tmp_folder)
            
        os.makedirs(zip_tmp_folder)

        zipfile_path = os.path.join(zip_tmp_folder, 'app.zip')

        # dl the file
        try:
            request.urlretrieve (zipfile_url, zipfile_path)
        except Exception as e:
            self.logger.error('error querying url: {0}'.format(zipfile_url))
            raise e

        app_unzipped_path = os.path.join(zip_tmp_folder, job.platform)
        # unzip common www
        with zipfile.ZipFile(zipfile_path, 'r') as zip_file:
            zip_file.extractall(app_unzipped_path)

        cordova_build_path = self.get_cordova_build_path(meta_app_definition)

        cordova_app_builder = CordovaAppBuilder(meta_app_definition, cordova_build_path,
                                                app_build_sources_path)

        cordova_app_builder.build_ios(rebuild=from_scratch)

        output = {
            'ipa_filepath' : cordova_app_builder._ipa_filepath,
        }

        job.output = json.dumps(output)
        job.save()

        # remove the folder where the www folder was unzipped at
        shutil.rmtree(zip_tmp_folder)


    # RELEASE JOB
    # first check if there is a successful build for this version
    # if not, build the app
    # release via fastlane(?)
    def run_release_job(self, job, from_scratch=False):
        pass

    def _report_job_result(self, job):
        report_method_name = 'report_{0}_result'.format(job.job_type)

        if not hasattr(self, report_method_name):
            raise InvalidJobTypeError('Job of type {0} is not supported'.format(job.job_type))

        report_job = getattr(self, report_method_name)

        report_job(job)
    

    # report job results back to main localcosmos server
    def report_job_results(self):

        db.connect()

        # jobs with no report sent yet
        unreported_finished_jobs = AppKitJob.select().where((AppKitJob.finished_at.is_null(False)) &
                                                            (AppKitJob.result_reported_at.is_null(True)))

        for job in unreported_finished_jobs:
            self._report_job_result(job)
            

        # jobs might have sent an error report. If the finished_at timestamp is later then result_reported_at: report the new result
        unreported_reran_jobs = AppKitJob.select().where((AppKitJob.finished_at.is_null(False)) &
                        (AppKitJob.result_reported_at.is_null(False)) & (AppKitJob.finished_at > AppKitJob.result_reported_at))

        for job in unreported_reran_jobs:
            self._report_job_result(job)


        db.close()
            
            
    def report_build_result(self, job):
        data = {
                'job_result' : job.job_result,
        }

        files = {}

        # only append ipa if success is true
        if job.job_status == 'success':

            output = json.loads(job.output)

            ipa_filepath = output['ipa_filepath']

            filename = os.path.basename(ipa_filepath)

            files = {
                'ipa_file' : {
                    'filepath' : ipa_filepath,
                }
            }

        request = JobReportResultRequest(self.settings, job.lc_id, data=data, files=files)
    
        response = request.execute()

        if response is not None:
            job.result_reported_at = datetime.datetime.now()
            job.save()


    def report_release_result(self, job):

        data = {
            'job_result' : job.job_result,
        }

        request = JobReportResultRequest(self.settings, job.lc_id, data=data)
    
        response = request.execute()

        if response is not None:
            job.result_reported_at = datetime.datetime.now()
            job.save()
        

        
##################################################################################################################
# HTTP REQUESTS
#
##################################################################################################################

class LCAPIError(Exception):
    pass


class LCAppkitApiRequest:

    method = 'GET'
    path = None
    content_type = 'application/x-www-form-urlencoded'


    def __init__(self,api_settings, data=None, files={}):
        
        self.domain = api_settings['api_url']
        self.settings = api_settings
        self.data = data
        self.files = files

        self.token_store_path = os.path.join(WORKDIR, 'token.json')
        
        self.logger = None


    def _get_logger(self):
    
        if not self.logger:
        
            # for cross platform logging use a logfolder within the folder in which JobManager.py lies
            logging_folder = os.path.join(WORKDIR, 'log/job_api/')
            
            logger_name = '{0}-{1}'.format(__name__, self.__class__.__name__)

            self.logger = get_logger(logger_name, logging_folder, 'log')

        return self.logger


    def validate_token(self, token):
    
        logger = self._get_logger()
        logger.info('validating token')

        token_str = 'Bearer {0}'.format(token)

        headers = {
            'Authorization' : token_str,
        }
        api_request =  request.Request(self.domain, data=None, headers=headers, method='GET')
        
        try:
            response = request.urlopen(api_request)
            response_data = json.loads(response.read())
            logger.info('token is valid.')
            return token

        except:
            logger.info('token is not valid.')
            return None
    

    def get_token(self):

        if os.path.isfile(self.token_store_path):
            with open(self.token_store_path, 'r') as token_file:
                token_store = json.loads(token_file.read())
                token = token_store['access']
                token = self.validate_token(token)

                if token is None:
                    os.remove(self.token_store_path)
                    return self.get_token()

        else:
            data = {
                'username' : self.settings['auth']['username'],
                'password' : self.settings['auth']['password'],
            }

            request = AuthTokenRequest(self.settings, data=data)

            response = request.execute()

            if response is not None:
                token_dic = response
                token = token_dic['access']

                with open(self.token_store_path, 'w', encoding='utf-8') as token_file:
                    json.dump(token_dic, token_file, indent=4, ensure_ascii=False)
            else:
                raise LCAPIError('Authorization failed or Server unreachable')

        return token

    def get_headers(self, **kwargs):
        token = self.get_token()
        headers = {
            'Content-Type' : self.content_type,
            'Authorization' : 'Bearer {0}'.format(token),
        }


        return headers


    def get_url(self):
        return urljoin(self.domain, self.path)
    

    def execute(self):

        logger = self._get_logger()

        url = self.get_url()

        header_kwargs = {}

        if self.content_type == 'multipart/form-data':
            
            # create a mime message using MultiPartForm
            form = MultiPartForm()

            if self.data is not None:
                for key, value in self.data.items():
                    form.add_field(key, value)

            # Add a fake file
            for field_name, file_params in self.files.items():

                filepath = file_params['filepath']
                filename = os.path.basename(filepath)

                with open(filepath, 'rb') as form_file:
                    form.add_file(field_name, filename, form_file, mimetype=file_params.get('mimetype', None))

            # Build the request, including the byte-string
            # for the data to be posted.
            data = bytes(form)

            header_kwargs = {
                'data' : data,
                'form' : form,
            }

        elif self.data is not None:
            data_str = urlencode(self.data, quote_via=quote_plus)

            # bytes are required, use utf-8 encoding
            data = data_str.encode('utf-8')

        else:
            data = None

        headers = self.get_headers(**header_kwargs)
        api_request =  request.Request(url, data=data, headers=headers, method=self.method)
        
        try:
            response = request.urlopen(api_request)
            response_data = json.loads(response.read())

            # errors might have occurred although xhr.status_code == 200
            if 'error_code' in response_data and response_data['error_code'] != 0:
                raise LCAPIError(json.dumps(response_data))

            return response_data

        except Exception as e:
            logger.info('error querying url: {0}'.format(url))
            logger.info('method: {0}'.format(self.method))
            logger.info('params: {0}'.format(json.dumps(self.data)))
            logger.info('files: {0}'.format(self.files))
            logger.info('headers: {0}'.format(json.dumps(headers)))
            logger.error(e, exc_info=True)

        return None


class JobListRequest(LCAppkitApiRequest):

    method = 'GET'
    path = 'jobs/'


class JobAssignRequest(LCAppkitApiRequest):

    method = 'PATCH'
    path = 'jobs/'

    def __init__(self, api_settings, job_id, data=None):
        super().__init__(api_settings, data=data)
        self.job_id = job_id

    def get_url(self):
        path = '{0}{1}/assign/'.format(self.path, self.job_id)
        return urljoin(self.domain, path)


# upload ipa file if the build was successful, send result in post body
class JobReportResultRequest(LCAppkitApiRequest):

    method = 'PATCH'
    path = 'jobs/'
    content_type = 'multipart/form-data'

    def __init__(self, api_settings, job_id, data=None, files={}):
        super().__init__(api_settings, data=data, files=files)
        self.job_id = job_id

    def get_headers(self, **kwargs):

        headers = super().get_headers(**kwargs)

        headers.update({
            'Content-type' : kwargs['form'].get_content_type(),
            'Content-length' : len(kwargs['data']),
        })

        return headers

    def get_url(self):
        path = '{0}{1}/completed/'.format(self.path, self.job_id)
        return urljoin(self.domain, path)



class AuthTokenRequest(LCAppkitApiRequest):

    method = 'POST'
    path = 'auth-token/'

    # do not include the token for this request
    def get_headers(self, **kwargs):
        headers = {
            'Content-Type' : self.content_type,
        }

        return headers

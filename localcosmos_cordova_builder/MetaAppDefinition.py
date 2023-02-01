##################################################################################################################
#
# METAAPPDEFINITION
#
# - helper class
# - ios app builder runs on mac and has no django orm access

import uuid
from datetime import datetime, date

class MetaAppDefinition:

    def __init__(self, meta_app=None, meta_app_definition={}):

        if not meta_app and not meta_app_definition:
            raise ValueError('AppDefinition initialization requires either meta_app instance or meta_app_definition')

        
        if meta_app:
            meta_app_definition = self.meta_app_to_dict(meta_app)
            self.build_number = meta_app.build_number
                

        for field_name, value in meta_app_definition.items():
            setattr(self, field_name, value)


    @classmethod
    def _to_json(self, value):

        if isinstance(value, (datetime, date)): 
            return value.isoformat()

        if isinstance(value, (uuid.UUID)):
            return str(value)

        return value
        
    
    @classmethod
    def meta_app_to_dict(cls, meta_app):

        fields = ['uuid', 'name', 'primary_language', 'published_version', 'current_version', 'package_name',
                    'build_number', 'build_status', 'validation_status']

        meta_app_definition = {
            'uid' : meta_app.app.uid,
            'build_settings' : meta_app.build_settings,
            'frontend' : {},
        }

        
        for field_name in fields:
            
            field_value = getattr(meta_app, field_name)
            json_value = cls._to_json(field_value)

            meta_app_definition[field_name] = json_value

        # it doesn ot matter if AppReleaseBuilder or AppPreviewBuilder is used
        # both read the frontend settings from the currently globally installed frontend
        appbuilder = meta_app.get_release_builder()
        frontend_settings = appbuilder._get_frontend_settings()

        meta_app_definition['frontend']['cordova'] = frontend_settings.get('cordova', {})

        return meta_app_definition
        

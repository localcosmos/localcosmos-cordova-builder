import os, shutil
import pathlib

WORKDIR = os.getenv('LOCALCOSMOS_CORDOVA_BUILDER_WORKDIR', None)
if not WORKDIR:
    raise ValueError('LOCALCOSMOS_CORDOVA_BUILDER_WORKDIR environment variable not found')

CORDOVA_CLI_VERSION = '10.0.0'

CORDOVA_PLUGIN_VERSIONS = {
    "cordova-plugin-camera" : "cordova-plugin-camera@5.1.0",
    "cordova-plugin-console" : "cordova-plugin-console@1.1.0",
    "cordova-plugin-datepicker" : "cordova-plugin-datepicker@0.9.3",
    "cordova-plugin-device": "cordova-plugin-device@2.0.3",
    "cordova-plugin-dialogs" : "cordova-plugin-dialogs@2.0.2",
    "cordova-plugin-file" : "cordova-plugin-file@6.0.2",
    "cordova-plugin-geolocation" : "cordova-plugin-geolocation@4.1.0",
    "cordova-plugin-network-information" : "cordova-plugin-network-information@2.0.2",
    "cordova-plugin-splashscreen" : "cordova-plugin-splashscreen@6.0.0",
    "cordova-plugin-statusbar" : "cordova-plugin-statusbar@2.4.3",
    "cordova-plugin-whitlest" : "cordova-plugin-whitelist@1.3.4",
    "cordova-sqlite-storage" : "cordova-sqlite-storage@5.1.0",

    #"cordova-plugin-wkwebview-engine" : "cordova-plugin-wkwebview-engine@1.2.1 ",
    "cordova-plugin-wkwebview-file-xhr" : "cordova-plugin-wkwebview-file-xhr@3.0.0",
    
}

CORDOVA_PLATFORM_VERSIONS = {
    "android" : "android@9.0.0",
    "ios" : "ios@6.2.0",
}

class CordovaBuildError(Exception):
    pass


import subprocess, os, shutil, zipfile, logging
from subprocess import CalledProcessError, PIPE


from localcosmos_appkit_utils.AppImageCreator import AndroidAppImageCreator, IOSAppImageCreator
from localcosmos_appkit_utils.AppTheme import AppTheme
from localcosmos_appkit_utils.logger import get_logger

from lxml import etree


class CordovaAppBuilder:

    # cordova creates apks n these folders
    debug_apk_output_path = 'platforms/android/app/build/outputs/apk/debug/app-debug.apk'
    unsigned_release_apk_output_path = 'platforms/android/app/build/outputs/apk/release/app-release-unsigned.apk'
    signed_release_apk_output_path = 'platforms/android/app/build/outputs/apk/release/app-release.apk'


    relative_cordova_template_path = 'cordova_template'

    default_plugins = ['cordova-plugin-device', 'cordova-plugin-network-information', 'cordova-plugin-file',
                       'cordova-plugin-dialogs', 'cordova-plugin-splashscreen', 'cordova-plugin-console',
                       'cordova-sqlite-storage', 'cordova-plugin-datepicker', 'cordova-plugin-statusbar',
                       'cordova-plugin-camera', 'cordova-plugin-geolocation', 'cordova-plugin-whitelist']

    # this might be obsolte in cordova-ios@6.2.0
    ios_plugins = ['cordova-plugin-wkwebview-file-xhr']


    # has to be independant from django model instances and app builder instances, as it also runs on a mac
    # app_root_folder: absolute path to the folder in which the cordova app is created
    # common_www_folder:
    def __init__(self, meta_app_definition, app_root_folder, common_www_folder):

        # LOGGING
        self.logger = self._get_logger(meta_app_definition.uuid)

        # setup cordova
        cordova_manager = CordovaManager()
        cordova_is_installed = cordova_manager.cordova_is_installed()
        if not cordova_is_installed:
            self.logger.info('Installing cordova@{0} in {1}'.format(CORDOVA_CLI_VERSION, WORKDIR))
            cordova_manager.install_cordova()

        self.cordova_bin = cordova_manager.cordova_bin

        self.app_version = meta_app_definition.app_version
        self.build_number = meta_app_definition.build_number
        self.meta_app_definition = meta_app_definition

        # the folder in which the "cordova" folder is created
        self._app_root_folder = app_root_folder
        
        self._app_folder_name = self.meta_app_definition.package_name

        # the folder in which the cordova create command is executed
        self._build_root_folder = os.path.join(self._app_root_folder, 'cordova')
        if not os.path.isdir(self._build_root_folder):
            os.makedirs(self._build_root_folder)

        # the www content of the app, without cordova.js
        self._common_www_folder = common_www_folder

        self._user_content_folder = os.path.join(common_www_folder, 'user_content', 'themes',
                                                 self.meta_app_definition.theme)

        # the folder of the cordova project
        self._app_cordova_folder = os.path.join(self._build_root_folder, self._app_folder_name)
        # www folder inside cordova project
        self._cordova_www_folder = os.path.join(self._app_cordova_folder, 'www')

        # theme
        app_theme_path = os.path.join(common_www_folder, 'themes', meta_app_definition.theme)
        self.app_theme = AppTheme(app_theme_path)


    def _get_logger(self, meta_app_uuid):
        
        logging_folder = os.path.join(WORKDIR, 'log/cordova_app_builder/')
        logger = get_logger(__name__, logging_folder, meta_app_uuid)

        return logger


    # delete and recreate a folder
    def deletecreate_folder(self, folder):
        if os.path.isdir(folder):
            for root, dirs, files in os.walk(folder):
                for f in files:
                    os.unlink(os.path.join(root, f))
                for d in dirs:
                    dirpath = os.path.join(root, d)
                    if os.path.islink(dirpath):
                        os.unlink(dirpath)
                    else:
                        shutil.rmtree(dirpath)
        else:
            os.makedirs(folder)


    #######################################################################################################
    # blank app and plugins
    
    def install_default_plugins(self):

        commands = []

        for plugin in self.default_plugins:
            commands.append([self.cordova_bin, 'plugin', 'add', CORDOVA_PLUGIN_VERSIONS[plugin]])

        for command in commands:
            process_completed = subprocess.run(command, stdout=PIPE, stderr=PIPE, cwd=self._app_cordova_folder)

            if process_completed.returncode != 0:
                raise CordovaBuildError(process_completed.stderr)


    def install_specific_plugins(self, platform):

        commands = []

        if platform == 'iOS':
            for plugin in self.ios_plugins:
                commands.append([self.cordova_bin, 'plugin', 'add', CORDOVA_PLUGIN_VERSIONS[plugin]])


        for command in commands:
            process_completed = subprocess.run(command, stdout=PIPE, stderr=PIPE, cwd=self._app_cordova_folder)

            if process_completed.returncode != 0:
                raise CordovaBuildError(process_completed.stderr)
            

    def _build_blank_cordova_app(self, platform, rebuild=False):

        if rebuild == True:
            shutil.rmtree(self._app_cordova_folder)

        # check for the cordova app
        if not os.path.isdir(self._app_cordova_folder):

            self.logger.info('Building initial blank cordova app')
            
            # create a blank cordova app via command
            # cordova create hello com.example.hello HelloWorld

            package_name = self.meta_app_definition.package_name

            create_command = [self.cordova_bin, 'create', self._app_folder_name, package_name,
                              self.meta_app_definition.name]

            create_process_completed = subprocess.run(create_command, stdout=PIPE, stderr=PIPE,
                                                      cwd=self._build_root_folder)


            if create_process_completed.returncode != 0:
                raise CordovaBuildError(create_process_completed.stderr)
                
            self.install_default_plugins()

            self.install_specific_plugins(platform)

            # add stuff to config
            # <preference name="SplashMaintainAspectRatio" value="true" />
            # <preference name="StatusBarStyle" value="blackopaque" />
            # <preference name="StatusBarOverlaysWebView" value="false" />
            # <preference name="StatusBarBackgroundColor" value="#000000" />

            preferences = [
                {'name' : 'SplashMaintainAspectRatio', 'value' : 'true'},
                {'name' : 'StatusBarStyle', 'value' : 'blackopaque'},
                {'name' : 'StatusBarOverlaysWebView', 'value' : 'false'},
                {'name' : 'StatusBarBackgroundColor', 'value' : '#000000'},
                {'name' : 'DisallowOverscroll', 'value': 'true'},
            ]

            for tag_attributes in preferences:
                self._add_to_config_xml('preference', tag_attributes=tag_attributes)
            

    ###########################################################################################
    # add WWW
    # determine if the www folder already is the apps one: check for www/settings and www/features.js

    def _add_www_folder(self, rebuild=False):

        self.logger.info('Adding app www if necessary')

        app_www_exists = True

        check_files = ['settings.js', 'features.js']

        for filename in check_files:

            filepath = os.path.join(self._cordova_www_folder, filename)

            if not os.path.isfile(filepath):
                app_www_exists = False
                break

        if app_www_exists == False or rebuild == True:
            # add www contents as symlinks
            # recreating the www folder will be obsolete when the LC cordova template will be used
            #self.deletecreate_folder(self._cordova_www_folder)
            
            shutil.rmtree(self._cordova_www_folder)

            # copy common www, cordova cannot work with symlinks
            shutil.copytree(self._common_www_folder, self._cordova_www_folder)
        

    ###########################################################################################
    # CONFIG XML
    # - currently, only adding to <widget> is supported
    
    def _add_to_config_xml(self, tag_name, tag_attributes={}):

        config_xml_path = os.path.join(self._app_cordova_folder, 'config.xml')

        with open(config_xml_path, 'rb') as config_file:
            config_xml_tree = etree.parse(config_file)

        # root is the widget tag
        root = config_xml_tree.getroot()

        exists = False


        # check all edit-configs
        for child in root:

            # tag without namespace
            existing_tag_name = etree.QName(child.tag).localname
            
            if tag_name == existing_tag_name:

                attributes = child.attrib

                all_attributes_match = True
                
                for attrib_key, attrib_value in tag_attributes.items():

                    existing_value = attributes.get(attrib_key)
                    
                    if existing_value != attrib_value:
                        all_attributes_match = False
                        break

                if all_attributes_match == True:
                    exists = True


        # check if element exists
        if exists == False:

            new_element = etree.Element(tag_name, attrib=tag_attributes)
            root.append(new_element)

            # xml_declaration: <?xml version='1.0' encoding='utf-8'?>
            with open(config_xml_path, 'wb') as config_file:
                config_xml_tree.write(config_file, encoding='utf-8', xml_declaration=True, pretty_print=True)


    # Full version number expressed in major/minor/patch notation.
    # currently only major is supported
    def set_config_xml_app_version(self, app_version, build_number):

        config_xml_path = os.path.join(self._app_cordova_folder, 'config.xml')

        with open(config_xml_path, 'rb') as config_file:
            config_xml_tree = etree.parse(config_file)

        # root is the widget tag
        root = config_xml_tree.getroot()

        version_string = '{0}.0.{1}'.format(app_version, build_number)

        root.set('version', version_string)
        
        with open(config_xml_path, 'wb') as config_file:
            config_xml_tree.write(config_file, encoding='utf-8', xml_declaration=True, pretty_print=True)
        


    ###########################################################################################
    # GENERATE ZIPFILE FOR iOS Mac build
    # the zipfile contains:
    # - www folder
    # - app content images folder
    ###########################################################################################
    def get_zip_filepath(self):
        filename = 'cordova_www.zip'
        return os.path.join(self._build_root_folder, filename)
    
    
    def create_zipfile(self):
        self.logger.info('Creating zipfile for ios')

        # get the parent direcotry of common_www
        common_base_folder = os.path.abspath(os.path.join(self._common_www_folder, os.pardir))

        # strip off this part from user_content_folder in the zipfile
        user_content_base_folder = self._common_www_folder
        
        zip_filepath = self.get_zip_filepath()

        with zipfile.ZipFile(zip_filepath, 'w', zipfile.ZIP_DEFLATED) as www_zip:

            # add www
            for root, dirs, files in os.walk(self._common_www_folder, followlinks=True):

                for filename in files:
                    # Create the full filepath by using os module.
                    app_file_path = os.path.join(root, filename)
                    arcname = app_file_path.split(common_base_folder)[-1]
                    www_zip.write(app_file_path, arcname=arcname)


            # add theme specific user_content
            for root, dirs, files in os.walk(self._user_content_folder, followlinks=True):

                for filename in files:
                    # Create the full filepath by using os module.
                    app_file_path = os.path.join(root, filename)
                    arcname = app_file_path.split(user_content_base_folder)[-1]
                    www_zip.write(app_file_path, arcname=arcname)

        self.logger.info('Successfully created zipfile.')
        return zip_filepath


    ##############################################################################################################
    # BUILD CONFIG
    ##############################################################################################################
    def _get_build_config_path(self):
        return os.path.join(WORKDIR, 'build_config.json')

            
    ##############################################################################################################
    # BUILD ANDROID APK
    # - create blank cordova app
    # - install plugins
    # - copy config.xml and other files
    # - copy www
    # - run cordova build command
    ##############################################################################################################
    def build_android(self, keystore_path, keystore_password, key_password, rebuild=False):

        self.logger.info('Building cordova android app')

        self._build_blank_cordova_app('Android', rebuild=rebuild)

        # set app version
        self.set_config_xml_app_version(self.app_version, self.build_number)

        self.logger.info('Adding android platform')
        add_android_command = [self.cordova_bin, 'platform', 'add', CORDOVA_PLATFORM_VERSIONS['android']]


        add_android_completed_process = subprocess.run(add_android_command, stdout=PIPE, stderr=PIPE,
                                                       cwd=self._app_cordova_folder)

        if add_android_completed_process.returncode != 0:
            raise CordovaBuildError(add_android_completed_process.stderr)
        
        self._add_www_folder(rebuild=True)

        # build android images
        self.logger.info('building Android launcher and splashscreen images')
        image_creator = AndroidAppImageCreator(self.meta_app_definition, self._app_cordova_folder,
                                               self._user_content_folder, self.app_theme)
        
        image_creator.generate_images_from_svg('launcher')
        image_creator.generate_images_from_svg('launcher_background')
        image_creator.generate_images_from_svg('splashscreen', varying_ratios=True)

        self.logger.info('initiating cordova build android')
        build_android_command = [self.cordova_bin, 'build', 'android', '--release', '--',
                                 '--keystore={0}'.format(keystore_path),
                                 '--storePassword={0}'.format(keystore_password),
                                 '--alias=localcosmos', '--password={0}'.format(key_password)]

        build_android_process_completed = subprocess.run(build_android_command, stdout=PIPE, stderr=PIPE,
                                                         cwd=self._app_cordova_folder)

        if build_android_process_completed.returncode != 0:
            raise CordovaBuildError(build_android_process_completed.stderr)


        return self.get_apk_filepath()


    def get_apk_filepath(self):
        return os.path.join(self._app_cordova_folder, self.signed_release_apk_output_path)

    @classmethod
    def get_apk_filename(cls, meta_app_definition):
        filename = '{0}.apk'.format(meta_app_definition.package_name)
        return filename


    ##############################################################################################################
    # BUILD iOS .ipa
    # - create blank cordova app, if not yet present
    # - install plugins
    # - copy config.xml and other files
    # - copy www
    # - run cordova build command
    ##############################################################################################################
    def _get_ios_build_flags(self):

        build_flags = {
            '--codeSignIdentity' : 'iPhone Developer',
            '--developmentTeam' : 'GMW7GRAP9D',
            '--packageType' : 'app-store',
        }

        return build_flags


    @classmethod
    def get_ipa_filename(cls, meta_app_definition):
        filename = '{0}.ipa'.format(meta_app_definition.name)
        return filename


    def get_ipa_folder(self):
        return os.path.join(self._app_cordova_folder, 'platforms/ios/build/device/')

    def get_ipa_filepath(self):
        filename = self.get_ipa_filename(self.meta_app_definition)
        return os.path.join(self.get_ipa_folder(), filename)

    # only set once, check if it already exists first
    def set_ios_info_plist_value(self, key, value):
        config_xml_path = os.path.join(self._app_cordova_folder, 'config.xml')

        with open(config_xml_path, 'rb') as config_file:
            config_xml_tree = etree.parse(config_file)

        # root is the widget tag
        root = config_xml_tree.getroot()

        element_exists = False

        edit_attributes = {
            'target' : key,
            'file' : '*-Info.plist',
            'mode' : 'merge',
        }

        # check all edit-configs
        for child in root:

            # tag without namespace
            tag_name = etree.QName(child.tag).localname
            
            if tag_name == 'edit-config':

                attributes = child.attrib

                all_attributes_match = True
                
                for attrib_key, attrib_value in edit_attributes.items():

                    existing_value = attributes.get(attrib_key)
                    
                    if existing_value != attrib_value:
                        all_attributes_match = False
                        break

                if all_attributes_match == True:

                    string_element = child[0]
                    string_tag = etree.QName(string_element.tag).localname

       
                    if string_tag == 'string' and string_element.text == value:
                        element_exists = True
                        break
                        
                
        if element_exists == False:

            new_element = etree.Element('edit-config', attrib=edit_attributes)
            string_element = etree.Element('string')
            string_element.text = value
            new_element.append(string_element)
            
            root.append(new_element)

            # xml_declaration: <?xml version='1.0' encoding='utf-8'?>
            with open(config_xml_path, 'wb') as config_file:
                config_xml_tree.write(config_file, encoding='utf-8', xml_declaration=True, pretty_print=True)
    '''
    <edit-config target="NSLocationWhenInUseUsageDescription" file="*-Info.plist" mode="merge">
        <string>need location access to find things nearby</string>
    </edit-config>
    '''
    def set_ios_NSLocationWhenInUseUsageDescription(self):

        self.set_ios_info_plist_value('NSLocationWhenInUseUsageDescription',
                                      'location access is required for observations and maps')


    def set_ios_NSCameraUsageDescription(self):

        self.set_ios_info_plist_value('NSCameraUsageDescription',
                                      'camera access is required for taking pictures for observations')

    # <splash src="res/screen/ios/Default@2x~universal~anyany.png" />
    # <splash src="res/screen/ios/Default@3x~universal~anyany.png" />
    # res folder lies in the same folder as www
    def set_config_xml_storyboard_images(self):


        attributes_2x = {
            'src' : 'res/screen/ios/Default@2x~universal~anyany.png'
        }
        self._add_to_config_xml('splash', tag_attributes=attributes_2x)

        attributes_3x = {
            'src' : 'res/screen/ios/Default@3x~universal~anyany.png'
        }

        self._add_to_config_xml('splash', tag_attributes=attributes_3x)

    # <platform name="ios">
    #   <allow-intent href="itms:*"/>
    #   <allow-intent href="itms-apps:*"/>
    #
    #   <preference name="WKWebViewOnly" value="true"/>
    #   <feature name="CDVWKWebViewEngine">
    #      <param name="ios-package" value="CDVWKWebViewEngine"/>
    #   </feature>
    #   <preference name="CordovaWebViewEngine" value="CDVWKWebViewEngine"/>
    #        
    # </platform>
    def create_wkwebviewonly_element(self):
        attributes = {
            'name' : 'WKWebViewOnly',
            'value' : 'true',
        }
        new_element = etree.Element('preference', attrib=attributes)

        return new_element
    

    def create_cordovawebviewengine_element(self):
        attributes = {
            'name' : 'CordovaWebViewEngine',
            'value' : 'CDVWKWebViewEngine',
        }
        new_element = etree.Element('preference', attrib=attributes)

        return new_element
    

    def create_cdvwkwebviewengine_feature(self):
        attributes = {
            'name' : 'CDVWKWebViewEngine',
        }
        feature_element = etree.Element('feature', attrib=attributes)

        param_element_attributes = {
            'name' : 'ios-package',
            'value' : 'CDVWKWebViewEngine',
        }

        param_element = etree.Element('param', attrib=param_element_attributes)

        feature_element.append(param_element)
        
        return feature_element
        
    
        
    def config_xml_enable_wkwebview(self):

        config_xml_path = os.path.join(self._app_cordova_folder, 'config.xml')

        with open(config_xml_path, 'rb') as config_file:
            config_xml_tree = etree.parse(config_file)

        # root is the widget tag
        root = config_xml_tree.getroot()

        ios_platform_element = None
        
        for child in root:

            # tag without namespace
            tag_name = etree.QName(child.tag).localname
            
            if tag_name == 'platform':

                attributes = child.attrib

                if 'name' in attributes and attributes['name'] == 'ios':
                    ios_platform_element = child
                    break

        if ios_platform_element == None:

            ios_platform_element = etree.Element('platform', attrib={'name':'ios'}) 

            wkwebviewonly_element = self.create_wkwebviewonly_element()
            ios_platform_element.append(wkwebviewonly_element)

            cordovawebviewengine_element = self.create_cordovawebviewengine_element()
            ios_platform_element.append(cordovawebviewengine_element)

            feature_element = self.create_cdvwkwebviewengine_feature()
            ios_platform_element.append(feature_element)

            root.append(ios_platform_element)

        else:

            wkwebviewonly_preference_exists = False
            cordovawebviewengine_preference_exists = False
            feature_element_exists = False

            for platform_child in ios_platform_element:

                tag_name = etree.QName(platform_child.tag).localname
                attributes = platform_child.attrib

                if tag_name == 'preference':

                    if 'name' in attributes:

                        name = attributes.get('name')

                        if name == 'WKWebViewOnly':
                            wkwebviewonly_preference_exists = True

                        elif name == 'CordovaWebViewEngine':
                            cordovawebviewengine_preference_exists = True

                elif tag_name == 'feature':

                    if 'name' in attributes and attributes['name'] == 'CDVWKWebViewEngine':
                        feature_element_exists = True


            if wkwebviewonly_preference_exists == False:
                wkwebviewonly_element = self.create_wkwebviewonly_element()
                ios_platform_element.append(wkwebviewonly_element)

            if cordovawebviewengine_preference_exists == False:
                cordovawebviewengine_element = self.create_cordovawebviewengine_element()
                ios_platform_element.append(cordovawebviewengine_element)

            if feature_element_exists == False:
                feature_element = self.create_cdvwkwebviewengine_feature()
                ios_platform_element.append(feature_element)
                
        with open(config_xml_path, 'wb') as config_file:
            config_xml_tree.write(config_file, encoding='utf-8', xml_declaration=True, pretty_print=True)                
    
    
    def build_ios(self, rebuild=False):

        self.logger.info('Building cordova ios app')

        self._build_blank_cordova_app('iOS', rebuild=rebuild)
        
        # set app version
        self.set_config_xml_app_version(self.app_version, self.build_number)

        # set NSLocationWhenInUseUsageDescription
        self.set_ios_NSLocationWhenInUseUsageDescription()

        # set NSCameraUsageDescription
        self.set_ios_NSCameraUsageDescription()

        # NSPhotoLibraryUsageDescription
        self.set_ios_info_plist_value('NSPhotoLibraryUsageDescription',
                                      'photo library access is required for adding pictures to observations')
        
        # NSLocationAlwaysUsageDescription
        self.set_ios_info_plist_value('NSLocationAlwaysUsageDescription',
                                      'location access is required for observations and maps')

        # enable wkwebview
        self.config_xml_enable_wkwebview()


        self.logger.info('Adding ios platform')
        add_ios_command = [self.cordova_bin, 'platform', 'add', CORDOVA_PLATFORM_VERSIONS['ios']]

        add_ios_completed_process = subprocess.run(add_ios_command, stdout=PIPE, stderr=PIPE,
                                                   cwd=self._app_cordova_folder)

        if add_ios_completed_process.returncode != 0:
            if b'Platform ios already added' not in add_ios_completed_process.stderr:
                raise CordovaBuildError(add_ios_completed_process.stderr)

        # ios has to copy www folder on each build
        self._add_www_folder(rebuild=True)

        # build ios images
        self.logger.info('building iOS launcher and splashscreen images')
        image_creator = IOSAppImageCreator(self.meta_app_definition, self._app_cordova_folder,
                                           self._user_content_folder, self.app_theme)
        
        image_creator.generate_images_from_svg('launcher', remove_alpha_channel=True)
        image_creator.generate_images_from_svg('splashscreen', varying_ratios=True)

        self.set_config_xml_storyboard_images()
        image_creator.generate_storyboard_images()

        # build ios release
        self.logger.info('initiating cordova build ios')
        build_config_path = self._get_build_config_path()

        build_ios_command = [self.cordova_bin, 'build', 'ios', '--device', '--release', '--buildConfig',
                             build_config_path]

        build_ios_process_completed = subprocess.run(build_ios_command, stdout=PIPE, stderr=PIPE,
                                                     cwd=self._app_cordova_folder)

        if build_ios_process_completed.returncode != 0:
            raise CordovaBuildError(build_ios_process_completed.stderr)


        return self.get_ipa_filepath()



# install a non-global (local) copy of apache cordova
class CordovaManager:

    def __init__(self):

        if not os.path.isdir(WORKDIR):
            os.makedirs(WORKDIR)

        self.check_npm()

    @property
    def cordova_bin(self):
        cordova_bin_path = os.path.join(WORKDIR, 'node_modules/cordova/bin/cordova')
        return cordova_bin_path


    def check_npm(self):

        npm_command = ['npm', '--version', '--']

        npm_command_result = subprocess.run(npm_command, stdout=PIPE, stderr=PIPE, cwd=WORKDIR)
        if npm_command_result.returncode != 0:
            raise CordovaBuildError(npm_command_result.stderr)


    def cordova_is_installed(self):

        if os.path.isfile(self.cordova_bin):
            return True

        return False

    
    def install_cordova(self):

        cordova_install_command = ['npm', 'install', 'cordova@{0}'.format(CORDOVA_CLI_VERSION)]

        cordova_install_command_result = subprocess.run(cordova_install_command, stdout=PIPE, stderr=PIPE,
                                                        cwd=WORKDIR)


        if cordova_install_command_result.returncode != 0:
            raise CordovaBuildError(cordova_install_command_result.stderr)

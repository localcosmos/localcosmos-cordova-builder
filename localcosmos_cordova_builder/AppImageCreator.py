import os, shutil
from PIL import Image

from .image_utils import (create_png_from_svg, create_resized_png_from_svg, create_png_border,
                                       remove_alpha_channel_from_png)

###########################################################################################
# GENERATE IMAGES
# - generate app images from svg
# - fixed dimensions: simply create a png image from svg via inkscape export
# - varying dimensions: use the shorter side to create png, cut afterwards
# - the extension might differ from the existing_image_diskpath
# - android adaptive launchers (foreground + background)


FALLBACK_IMAGES = {
    'launcherBackground' : 'resources/images/adaptive_launcher_background.svg', # relative to this file
}


class AppImageCreator:

    def __init__(self, meta_app_definition, app_cordova_folder, app_build_sources_path):
        
        self.meta_app_definition = meta_app_definition
        self.app_build_sources_path = app_build_sources_path
        self.app_cordova_folder = app_cordova_folder

        self.root = os.path.dirname(os.path.abspath(__file__))



    def iterate_over_default_image_files(self):
        raise NotImplementedError()
        

    def generate_images_from_svg(self, image_type, varying_ratios=False, remove_alpha_channel=False):

        source_image_filepath = self._get_source_image_diskpath(image_type)


        for icon_folder, filename in self.iterate_over_default_image_files(image_type):

            cordova_default_image_path = os.path.join(icon_folder, filename)

            # scan the file and overwrite it via a file generated from svg
            cordova_default_image = Image.open(cordova_default_image_path)

            width, height = cordova_default_image.size

            cordova_default_image.close()

            if varying_ratios == False:

                if filename == 'ic_launcher_foreground.png' and self.platform == 'android':
                    self._generate_adaptive_launcher(source_image_filepath, width, height,
                                                     cordova_default_image_path)

                else:
                    create_png_from_svg(source_image_filepath, width, height,
                                        cordova_default_image_path)

            else:
                create_resized_png_from_svg(source_image_filepath, width, height,
                                            cordova_default_image_path)

            if remove_alpha_channel == True:
                remove_alpha_channel_from_png(cordova_default_image_path)

    
    # source svg file
    def _get_source_image_diskpath(self, image_type):

        filename = self.meta_app_definition.frontend[self.platform][image_type]
        image_filepath = os.path.join(self.app_build_sources_path, self.platform, 'assets', filename)

        if not os.path.isfile(image_filepath):

            fallback_image = FALLBACK_IMAGES.get(image_type, None)

            if fallback_image is not None:

                image_filepath = os.path.join(self.root, fallback_image)

                if not os.path.isfile(image_filepath):
                    raise FileNotFoundError(image_filepath)

            else:
                raise ValueError('No fallback image defined for {0}'.format(image_type))

        return image_filepath


    ##############################################################################################################
    # ANDROID ADAPTIVE ICONS
    #
    # 108x108dp outer dimensions, the inner 72dpx72dp show the icon, outer 18dp are reserved for the system
    # user uploads square icon
    # scale down this icon to 72dp
    # create a 108dp icon with transparent background
    # paste the 72dp icon in the center of the 108dp image
    def _generate_adaptive_launcher(self, svg_filepath, width, height, destination_filepath):

        inner_width = 90 # 90 or 72

        # width and height are both 108dp
        icon_width = int((width/108) * inner_width)
        icon_height = int((height/108) * inner_width)

        create_png_from_svg(svg_filepath, icon_width, icon_height, destination_filepath)

        border_width = int((width/108) * (108-inner_width))

        border_color = (255,255,255,0)

        create_png_border(destination_filepath, border_width, border_color)



class AndroidAppImageCreator(AppImageCreator):
        

    platform = 'android'

    definitions = {
        'launcherIcon' : {
            'subfolders_startwith' : 'mipmap-',
            'folder' : 'platforms/android/app/src/main/res',
            'filenames' : ['ic_launcher.png', 'ic_launcher_foreground.png'],
        },
        'launcherBackground' : {
            'subfolders_startwith' : 'mipmap-',
            'folder' : 'platforms/android/app/src/main/res',
            'filenames' : ['ic_launcher_background.png'],
        },
        'splashscreen' : {
            'subfolders_startwith' : 'drawable-',
            'folder' : 'platforms/android/app/src/main/res',
            'filenames' : ['screen.png'],
        }
    }


    def iterate_over_default_image_files(self, image_type):
        icon_parent_folder = os.path.join(self.app_cordova_folder, self.definitions[image_type]['folder'])
        
        # iterate over all subfolders named mipmap-*
        for subfolder in os.listdir(icon_parent_folder):

            icon_folder = os.path.join(icon_parent_folder, subfolder)

            if os.path.isdir(icon_folder) and subfolder.startswith(self.definitions[image_type]['subfolders_startwith']):

                for expected_image_filename in self.definitions[image_type]['filenames']:
                    
                    for filename in os.listdir(icon_folder):

                        cordova_default_image_path = os.path.join(icon_folder, filename)

                        if os.path.isfile(cordova_default_image_path) and filename == expected_image_filename:

                            yield icon_folder, filename


class IOSAppImageCreator(AppImageCreator):

    platform = 'ios'

    definitions = {
        'launcherIcon' : {
            'folder' : 'AppIcon.appiconset',
        },
        'splashscreen' : {
            'folder' : 'LaunchStoryboard.imageset',
        },
        'storyboard' : {
            'Default@2x~universal~anyany.png' : [2732,2732],
            'Default@3x~universal~anyany.png' : [2732,2732],
        }
    }

    def get_folder(self, image_type):
        folder = 'platforms/ios/{0}/Images.xcassets/{1}'.format(self.meta_app_definition.name,
                                                                self.definitions[image_type]['folder'])

        return folder


    def iterate_over_default_image_files(self, image_type):
        icon_folder = os.path.join(self.app_cordova_folder, self.get_folder(image_type))
                    
        for filename in os.listdir(icon_folder):

            cordova_default_image_path = os.path.join(icon_folder, filename)

            if os.path.isfile(cordova_default_image_path) and filename.endswith('.png'):

                yield icon_folder, filename


    def generate_storyboard_images(self):

        image_type = 'splashscreen'

        res_folder = os.path.join(self.app_cordova_folder, 'res')

        if os.path.isdir(res_folder):
            shutil.rmtree(res_folder)

        screen_folder = os.path.join(res_folder, 'screen', 'ios')
        os.makedirs(screen_folder)

        
        source_image_filepath = self._get_source_image_diskpath(image_type)

        if source_image_filepath is None:
            raise ValueError('No {0} image found'.format(image_type))
        

        for storyboard_filename, size in self.definitions['storyboard'].items():

            target_image_filepath = os.path.join(screen_folder, storyboard_filename)
            width = size[0]
            height = size[1]
            
            create_resized_png_from_svg(source_image_filepath, width, height, target_image_filepath)
        
        

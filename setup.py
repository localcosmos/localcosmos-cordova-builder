from setuptools import setup, find_packages

with open('README.md', 'r') as fh:
    long_description = fh.read()

install_requires = [
    'peewee>=3.9.6',
    'lxml>=4.3.4',
    'tendo',
    'Pillow',
]

setup(
    name='localcosmos_cordova_builder',
    version='0.5.5',
    description='Create android and ios app packages for Local Cosmos apps.',
    long_description=long_description,
    long_description_content_type='text/markdown',
    license='The MIT License',
    platforms=['OS Independent'],
    keywords='localcosmos, app kit, cordova builder',
    author='Thomas Uher',
    author_email='thomas.uher@sisol-systems.com',
    url='https://github.com/SiSol-Systems/localcosmos-cordova-builder',
    packages=find_packages(),
    classifiers=[
        'Programming Language :: Python :: 3',
        'License :: OSI Approved :: MIT License',
        'Operating System :: OS Independent',
    ],
    python_requires='>=3.6',
    include_package_data=True,
    install_requires=install_requires,
)

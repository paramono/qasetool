# -*- coding: utf-8 -*-

# DO NOT EDIT THIS FILE!
# This file has been autogenerated by dephell <3
# https://github.com/dephell/dephell

try:
    from setuptools import setup
except ImportError:
    from distutils.core import setup

readme = ''

setup(
    long_description=readme,
    name='qasetool',
    version='0.9.1',
    python_requires='==3.*,>=3.8.0',
    author='paramono',
    author_email='alex@paramono.com',
    entry_points={"console_scripts": ["qasetool = qasetool:main"]},
    packages=['qasetool'],
    package_dir={"": "src"},
    package_data={},
    install_requires=[
        'anytree==2.*,>=2.8.0',
        'gherkin-official==20.*,>=20.0.1',
        'tabulate==0.*,>=0.8.9',
        'qaseio @ git+https://github.com/paramono/qase-python.git@master#egg=qaseio&subdirectory=qaseio',
    ],
    extras_require={"dev": ["ipython==7.*,>=7.26.0", "pytest==5.*,>=5.2.0"]},
)

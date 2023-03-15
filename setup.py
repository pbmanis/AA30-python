from setuptools import setup, find_packages
from Cython.Build import cythonize
import os

# Use Semantic Versioning, http://semver.org/
version_info = (0, 2, 0, '')
__version__ = '%d.%d.%d%s' % version_info


setup(name='rexpert',
      version=__version__,
      description='Control of Rigexpert AA#0',
      url='http://github.com/pbmanis/reaa30',
      author='Paul B. Manis',
      author_email='pmanis@med.unc.edu',
      license='MIT',
      packages=find_packages(include=['src*']),
    
      zip_safe=False,
      entry_points={
          'console_scripts': [
               'RE=src.re_aa30:main',
          ]
      },
      classifiers = [
             "Programming Language :: Python :: 3.10+",
             "Development Status ::  Beta",
             "Environment :: Console",
             "Intended Audience :: Neuroscientists",
             "License :: MIT",
             "Operating System :: OS Independent",
             "Topic :: Scientific Software :: Tools :: Python Modules",
             "Topic :: Antenna measurements",
             ],
    )
      
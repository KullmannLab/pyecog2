import setuptools

with open("README.md", "r", encoding="utf-8") as fh:
  long_description = fh.read()

setuptools.setup(
  name = 'pyecog2',
  version = '0.0.1c',
  description = 'For visualizing and classifying video-ECoG recordings (iEEG)',
  long_description=long_description,
  long_description_content_type="text/markdown",
  author = 'Marco Leite & Jonathan Cornford',
  author_email = 'mfpleite@gmail.com, jonathan.cornford@gmail.com',
  url = 'https://github.com/KullmannLab/pyecog2', # use the URL to the github repo
  keywords = ['iEEG', 'ECoG', 'telemetry'], # arbitrary keywords
  packages = setuptools.find_packages(),
  classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: GNU General Public License v3 or later (GPLv3+)",
        "Operating System :: OS Independent",
    ],
  python_requires='>=3.8',
  install_requires=['scipy==1.5.4',
                    'numpy>=1.15',
                    'pandas==1.1.5',
                    'matplotlib==3.3.3',
                    'h5py==3.1.0',
                    'PySide2==5.15.2',
                    'pyqtgraph==0.11.0',
                    'numba==0.52.0',
                    'pyopengl==3.1.1a1',
                    'pyopengl-accelerate==3.1.3b1',
                    'jupyter'
                    ],
   include_package_data = True
  )

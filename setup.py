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
  python_requires='>=3.11',
  install_requires=['scipy==1.11.3',
                    'numpy==1.26.1',
                    'pandas==2.1.2',
                    'matplotlib==3.8.1',
                    'h5py==3.10.0',
                    'PySide6==6.6.2',
                    'pyqtgraph==0.13.3',
                    'numba==0.58.1',
                    'pyopengl==3.1.7',
                    'pyopengl-accelerate==3.1.7',
                    'pyEDFlib==0.1.36',
                    'rsa',
                    'jupyter',
                    ],
   include_package_data = True
  )

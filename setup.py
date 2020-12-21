from distutils.core import setup
setup(
  name = 'pyecog',
  version = '1.0.0',
  description = 'For visualizing and classifying video-ECoG recordings (iEEG)',
  author = 'Marco Leite & Jonathan Cornford',
  author_email = 'mfpleite@gmail.com, jonathan.cornford@gmail.com',
  url = 'https://github.com/KullmannLab/pyecog2', # use the URL to the github repo
  keywords = ['iEEG', 'ECoG', 'telemetry'], # arbitrary keywords
  install_requires=['scipy==1.5.4', 'pandas==1.1.5', 'matplotlib==3.3.3', 'h5py==3.1.0', 'pyqtgraph==0.11.0'],
  )

![PyEcog](https://raw.githubusercontent.com/KullmannLab/pyecog2/master/pyecog2/icons/banner_small.png)
# Pyecog2
Under construction.

PyEcog2 is a python software package aimed at exploring, visualizing and analysing (video) EEG telemetry data

## Installation instructions

For alpha testing:
- clone the repository to your local machine
- create a dedicated python 3.8 environment for pyecog2 (e.g. a [conda](https://www.anaconda.com/products/individual) environment)
```shell
conda create --name pyecog2 python=3.8 
```
- activate the environment with `activate pyecog2` in Windows or `source activate pyecog2` in MacOS/Linux
- run pip install with the development option :
```shell
python -m pip install -e <repository directory>
```

- To launch PyEcog you should now, from any directory, be able to call:
```shell
python -m pyecog2
```

Hopefully in the future:
```shell
pip install pyecog2
```

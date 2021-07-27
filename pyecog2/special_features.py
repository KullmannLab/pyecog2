#Special feature extractor functions
import numpy as np

def freq_template_generator(template_file):
    '''
    generates function that c
    :param template_file:
    :param fs: sampling frequency
    :return:
    '''
    template = np.load(template_file)
    template_f = np.conj(np.fft.rfft(template))
    template_f = template_f/np.sqrt(np.sum(np.abs(template_f)**2,axis=1,keepdims=True))
    f_vec2 = np.linspace(0,np.pi,template_f.shape[1])**2
    return lambda fdata,fs: np.log(
                        np.sum(np.sum(np.abs(fdata[:,:template_f.shape[1]]*template_f[:,:fdata.shape[1]])**2,axis=0)*f_vec2**2) /
                        np.sum(np.sum(np.abs(fdata[:,:template_f.shape[1]])**2,axis=0)))



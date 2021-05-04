'''
Various tools for time-frequency analysing and ploting of (ephys) data.
Contributors: Marco Leite
'''


import numpy as np
import matplotlib.pyplot as plt
import scipy.signal as sg
import matplotlib.font_manager as fm

arial_path = 'C:\Windows\Fonts\Arial.ttf'
prop = fm.FontProperties(fname=arial_path, size =14)
prop = fm.FontProperties(size =14)
fontproperties = prop

def exp_filter(input_signal, f0, dt=1, R=7):
    # dt here is the sampling period
    # R Parameter similar to a wavelet frequency precision - 7 works just fine
    # f0 is the centre frequency of the filter

    K = 2 / dt
    z = 2 * np.pi * (1j * f0 + f0 / R)  # impulse response of the filter is h(t) = exp(-z*t)*u(t)
    d = K ** 2 + 2 * np.real(z) * K + (
    z * np.conj(z))  # auxiliary "denominator" variable (a0) - the ' gives the complex conjugate!
    normc = f0 * 2 * np.pi / R
    b = [normc * (K + z) / d, normc * 2 * z / d, normc * (-K + z) / d]  # *(4*pi*f0)/R; % b filter coeficients
    a = [-1, -(2 * (z * np.conj(z)) - 2 * K ** 2) / d,
         -(K ** 2 - 2 * np.real(z) * K + (z * np.conj(z))) / d]  # a filter coeficients

    # Unfortunately filtfilt doesn't work for complex filters, so here follows the solution:
    result_IIR, zf = sg.lfilter(b, a, input_signal, zi=[0, 0])
    result_IIR, zf = sg.lfilter(np.conj(b), a, result_IIR[::-1], zi=zf[::-1] / 2)

    return result_IIR[::-1]


def morlet_wavelet(input_signal, dt=1, R=7, freq_interval=(), drawplot=1, eps=.0001, quick=False,COI = True):
    Ns = len(input_signal)
    try:
        minf = max(freq_interval[0], R / (Ns * dt))  # avoid wavelets with COI longer than the signal
    except Exception:
        minf = R / (Ns * dt)
    try:
        maxf = min(freq_interval[1], .5 / dt)  # avoid wavelets above the Nyquist frequency
    except Exception:
        maxf = .5 / dt
    try:
        Nf = freq_interval[2]
    except Exception:
        Nf = int(np.ceil(np.log(maxf / minf) / np.log(1 / R + 1)))  # make spacing aproximately equal to sigma f
    
    alfa = (maxf / minf) ** (1 / Nf) - 1;  # According to the expression achived by fn = ((1+1/R)^n)*f0 where 1/R = alfa
    vf = ((1 + alfa) ** np.arange(0, Nf)) * minf;
    result = np.zeros((Nf, Ns), dtype='complex')

    # These for loops reaaally should be paralelied...
    if quick:
        for k in range(Nf):
            result[k, :] = exp_filter(input_signal, vf[k], dt, R)  # use the IIR filter exponetial wavelet instead of Morlet
    else:
        for k in range(Nf):
            N = int(2 * R / vf[k] / dt)  # Compute size of the wavelet
            wave = sg.morlet(N, w=R, s=1, complete=0) / N * np.pi * 2  # Normalize de amplitude returned by sg.morlet
            result[k, :] = sg.oaconvolve(input_signal, wave, mode='same')

    if drawplot:  # beautiful plots for matplotlib... too bad pyecog uses pyqtgraph! X'(
        plot_wavelet(result, dt, R, (minf,maxf,Nf), eps, COI)
    return result



def plot_wavelet(result, dt=1, R=7, freq_interval=(), eps=.0001,COI = True,norm_rows = False):
    Ns = result.shape[1]
    try:
        minf = max(freq_interval[0], R / (Ns * dt))  # avoid wavelets with COI longer than the signal
    except Exception:
        minf = R / (Ns * dt)
    try:
        maxf = min(freq_interval[1], .5 / dt)  # avoid wavelets above the Nyquist frequency
    except Exception:
        maxf = .5 / dt
    try:
        Nf = freq_interval[2]
    except Exception:
        Nf = int(np.ceil(np.log(maxf / minf) / np.log(1 / R + 1)))  # make spacing aproximately equal to sigma f

    alfa = (maxf / minf) ** (1 / Nf) - 1;  # According to the expression achived by fn = ((1+1/R)^n)*f0 where 1/R = alfa
    vf = ((1 + alfa) ** np.arange(0, Nf)) * minf;

    exp_range_base10 = range(int(np.floor(np.log10(minf))), int(np.floor(np.log10(maxf) + 1)))
    base10_ticks = [[10 ** i + j * 10 ** i for j in range(9)] for i in exp_range_base10]
    base10_ticks = np.reshape(base10_ticks, -1)
    vf_base10 = (np.log(base10_ticks) - np.log(vf[0])) / np.log(1 + alfa)
    labels = ['$10^{' + str(i) + '}$' for i in exp_range_base10]
    labels10 = [''] * len(base10_ticks)
    for i in range(len(labels)):
        labels10[i * 9] = labels[i]
        
    image2plot = 2 * np.abs(result) + eps
    
    mask = np.zeros(image2plot.shape,dtype='bool')
    if COI:
        Nlist   = (.5* R / vf / dt).astype('int') # 3 sigma COI
        for k in range(len(Nlist)):
            mask[k,:Nlist[k]] = True
            mask[k,-Nlist[k]:]= True
            
    if norm_rows:
        for k in range(mask.shape[0]):
            image2plot[k,~mask[k,:]] = image2plot[k,~mask[k,:]]/np.mean(image2plot[k,~mask[k,:]])
    
    image2plot = np.log10(image2plot)
    
    if COI:
        image2plot[mask] = np.min(image2plot[~mask])
    
    plt.imshow(image2plot, aspect=.5 * dt * (Ns - 1) / Nf, interpolation='gaussian',
                   extent=(0, dt * (Ns - 1), Nf - 1, 0))
    plt.yticks(vf_base10, labels10)
    plt.ylim((0, Nf - 1))
    plt.ylabel('Frequency (Hz)', fontproperties=prop)
    plt.xlabel('Time (s)', fontproperties=prop)

    cbar = plt.colorbar(shrink=.55)
    cbar_labels = cbar.ax.get_yticklabels()
    cbar_labelsText = [cbar_labels[i].get_text() for i in range(len(cbar_labels))]
    cbar_labelsText10 = ['$10^{' + cbar_labelsText[i] + '}$' for i in range(len(cbar_labels))]
    cbar.ax.set_yticklabels(cbar_labelsText10)
    if norm_rows:
        cbar.set_label('Amplitude (normalized)', fontproperties=prop)
    else:
        cbar.set_label('Amplitude (V)', fontproperties=prop)

    return result


def plot_crosswavelet(result, dt=1, R=7, freq_interval=(), eps=.0001, COI = True):
    Ns = result.shape[1]
    try:
        minf = max(freq_interval[0], R / (Ns * dt))  # avoid wavelets with COI longer than the signal
    except Exception:
        minf = R / (Ns * dt)
    try:
        maxf = min(freq_interval[1], .5 / dt)  # avoid wavelets above the Nyquist frequency
    except Exception:
        maxf = .5 / dt
    try:
        Nf = freq_interval[2]
    except Exception:
        Nf = int(np.ceil(np.log(maxf / minf) / np.log(1 / R + 1)))  # make spacing aproximately equal to sigma f

    alfa = (maxf / minf) ** (1 / Nf) - 1;  # According to the expression achived by fn = ((1+1/R)^n)*f0 where 1/R = alfa
    vf = ((1 + alfa) ** np.arange(0, Nf)) * minf;

    hsvim = plt.cm.hsv(np.angle(result)/2/np.pi + .5)
    intensity = np.abs(result)[:, :, np.newaxis]

    exp_range_base10 = range(int(np.floor(np.log10(minf))), int(np.floor(np.log10(maxf) + 1)))
    base10_ticks = [[10 ** i + j * 10 ** i for j in range(9)] for i in exp_range_base10]
    base10_ticks = np.reshape(base10_ticks, -1)
    vf_base10 = (np.log(base10_ticks) - np.log(vf[0])) / np.log(1 + alfa)
    labels = ['$10^{' + str(i) + '}$' for i in exp_range_base10]
    labels10 = [''] * len(base10_ticks)
    for i in range(len(labels)):
        labels10[i * 9] = labels[i]

    mask = np.zeros(intensity.shape,dtype='bool')
    if COI:
        Nlist   = (.5 * R / vf / dt).astype('int') # 3 sigma COI
        for k in range(len(Nlist)):
            mask[k,:Nlist[k]] = True
            mask[k,-Nlist[k]:]= True
    intensity[mask] = np.min(intensity)
    intensity = intensity/np.max(intensity)
    
    plt.imshow(hsvim[:,:,0:3]*intensity, aspect=.5 * dt * (Ns - 1) / Nf, interpolation='gaussian',
                   extent=(0, dt * (Ns - 1), Nf - 1, 0),cmap='hsv')
    plt.yticks(vf_base10, labels10)
    plt.ylim((0, Nf - 1))
    plt.ylabel('Frequency (Hz)', fontproperties=prop)
    plt.xlabel('Time (s)', fontproperties=prop)

    cbar = plt.colorbar(shrink=.55)
    cbar.set_label('Angle (turns)', fontproperties=prop)

    return result

def gauss_filter(data,fs=1,fhp=0,flp=np.inf,fstd=1):
    S = np.array(data.shape)
    N = S[0]
    for k in range(len(S)-1):
        S[k+1]=1
    vf = np.linspace(0,fs-fs/N,N)
    vf[vf>fs/2] = vf[vf>fs/2]-fs
    square_band  = (abs(vf)>=fhp)*(abs(vf)<=flp)
    gauss_window = np.exp(-vf**2/(2*fstd**2))
    gauss_window /= np.sum(gauss_window) # normalize window (including morroring and stuff)
    transfer_funciton = np.fft.ifft(np.fft.fft(square_band)*np.fft.fft(gauss_window))
    transfer_funciton = transfer_funciton.reshape(S)
    result = np.real(np.fft.ifft(np.fft.fft(data,axis=0)*transfer_funciton,axis=0))
    return result

def plot_spread(data,spread=.5,**kwargs):
    return plt.plot(data/np.nanmax(data)/spread - np.arange(data.shape[1])[np.newaxis,:],**kwargs)


def plot_cis(data, x=[0], percent=False,standard = True,ax=[],axis=(0),**kwargs):
    '''
    plot mean/median of data and confidence intervals
    '''
    try:
        len(ax)
        ax=plt.subplot(111)
    except Exception:
        pass
    
    N = np.delete(data.shape,axis)[0]
    if len(x)!=N:
        x = range(N)
    if not percent:
        mean_trace = np.mean(data,axis=axis)
        std        = np.std(data,axis=axis)
        if standard:
            upper_lim = mean_trace  + std/np.sqrt(np.sum(np.array(data.shape)[np.array([axis]).ravel()]))
            lower_lim = mean_trace  - std/np.sqrt(np.sum(np.array(data.shape)[np.array([axis]).ravel()]))
        else:
            upper_lim = mean_trace  + std
            lower_lim = mean_trace  - std
    else:
        mean_trace = np.median(data,axis=axis)
        upper_lim = np.percentile(data,75,axis=axis)
        lower_lim = np.percentile(data,25,axis=axis)
    
    ax.fill_between(x=x,y1=upper_lim,y2=lower_lim,alpha=.25,**kwargs)
    ax.plot(x,mean_trace,**kwargs)
    
def center_data(data,axis=0):
    data -= np.mean(data,axis=axis)
    data /= np.std(data,axis=axis)
    return data
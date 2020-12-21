import numpy as np
from ProjectClass import FileBuffer
import os
import numpy as np
import scipy.stats as stats
from collections import OrderedDict
from feature_extractor import FeatureExtractor
from hmm_pyecog import HMM_LL
import json
from numba import jit
from scipy.stats import chi2
from pyecog2.annotations_module import AnnotationElement

@jit(nopython=True)
def MVGD_LL_jit(fdata,mu,inv_cov,LL,no_scale):
    # Calculate Multivariate gaussian distribution log-likelihood
    k = fdata.shape[1]
    N = fdata.shape[0]
    scale = (1-no_scale)*((-k/2)*np.log(2*np.pi)+1/2*np.log(np.linalg.det(inv_cov[:,:])))
    i = 0
    # print('LL shape:',LL[i].shape)
    # print('set item shape:',(scale - 0.5*(fdata[i,:]-mu)@(inv_cov[:,:] @(fdata[i,:]-mu).T)).shape)
    for i in range(N):
        LL[i] =( scale - 0.5*(fdata[i,:]-mu)@(inv_cov[:,:] @(fdata[i,:]-mu).T))[0,0]  # the [0,0] is for numba wizzardry to work


def MVGD_LL(fdata,mu,inv_cov,no_scale = False):
    LL = np.zeros(fdata.shape[0])
    MVGD_LL_jit(fdata,mu[np.newaxis,:],inv_cov,LL, no_scale)
    return LL


@jit(nopython=True)
def LL2prob_jit(LL, prob):
    # Convert log-likelyhoods into probabilities
    for i in range(LL.shape[0]):
        v = np.exp(LL[i, :])
        prob[i, :] = v / np.sum(v)


def LL2prob(LL):
    prob = np.zeros(LL.shape)
    LL2prob_jit(LL, prob)
    return prob


def reg_invcov(M,n):
    return np.linalg.inv(M*n/(n+1) + np.eye(len(M))*M.diagonal()/(n+1))


def average_mu_and_cov(mu1,cov1,n1,mu2,cov2,n2):
    mu = (mu1*n1 + mu2*n2)/(n1 + n2)
    cov = n1/(n1+n2)*(cov1 + (mu-mu1)@(mu-mu1).T) + n2/(n1+n2)*(cov2 + (mu-mu2)@(mu-mu2).T)
    return (mu,cov)

def transitionslist2matrix(t, dt, n):
    A = np.zeros((n + 1, n + 1))
    A[0, t[0][2]] += 1  # first transition from blank
    for i in range(len(t) - 1):
        if t[i][1] >= t[i + 1][0] - dt:  # transitions between labled events
            A[t[i][2], t[i + 1][2]] += 1
        else:  # transitions between labeld events and blanks
            A[t[i][2], 0] += 1
            A[0, t[i + 1][2]] += 1
    # last transition to blank
    A[t[-1][2],0] += 1
    return A

def tansitions2rates(B,nblankpoints,nclasspoints):
    A = B
    A[0,0] = nblankpoints - np.sum(A[0,:])
    A[0,:] /= np.sum(A[0,:])
    for i in range(len(nclasspoints)):
        if nclasspoints[i]:
            A[i+1,i+1] = nclasspoints[i] - np.sum(A[i+1,:])
            A[i+1,:] /= np.sum(A[i+1,:])
        else: # For classes that do not occur, default to transition to blanks
            A[i+1,:] = 0
            A[i+1,0] = 1
    return A


class GaussianClassifier():
    '''
    Class to setup, train and run the classifier on feature files from animal
    '''

    def __init__(self,project,feature_extractor):
        self.project = project
        self.labels2classify = ['seizure','outliers'] # Populate this with the annotation labels to classify
        self.Ndim = feature_extractor.settings['number_of_features']
        self.class_means   = np.zeros((len(self.labels2classify),self.Ndim))
        self.class_cov     = np.tile(np.eye(self.Ndim),(len(self.labels2classify),1,1))
        self.class_npoints = np.zeros(len(self.labels2classify))
        self.blank_means   = np.zeros(self.Ndim)
        self.blank_cov     = np.zeros((self.Ndim,self.Ndim))
        self.blank_npoints = 0
        self.hmm           = HMM_LL()

    def train(self,animal_list=None):
        if animal_list is None:
            animal_list = self.project.animal_list

        for animal in animal_list:
            '''
            A scaling matrix should be implemented to allow for differences in animal recordings.
            Something that would standardize blank feature standard deviations, i.e. sqrt(diag(blank_cov)).
            '''
            print('Training with animal:', animal.id)
            labeled_positions = {}
            for label in self.labels2classify:
                labeled_positions[label] = np.array([a.getPos() for a in animal.annotations.get_all_with_label(label)])

            for i,eeg_file in enumerate(animal.eeg_files[:200]):
                feature_file = '.'.join(eeg_file.split('.')[:-1] + ['features'])
                print('Animal:', animal.id, 'file:',i,'of',len(animal.eeg_files), feature_file,end='\r')
                fmeta_file = '.'.join(eeg_file.split('.')[:-1] + ['fmeta'])
                with open(fmeta_file) as f:
                    fmeta_dict = json.load(f)
                f_vec = np.fromfile(feature_file, dtype=fmeta_dict['data_format'])
                f_vec_d = f_vec.reshape((-1, self.Ndim))
                np.nan_to_num(f_vec_d,copy=False)
                f_label = np.zeros(f_vec_d.shape[0])

                for i, label in enumerate(self.labels2classify):
                    lp = (labeled_positions[label]-fmeta_dict['start_timestamp_unix'])*fmeta_dict['fs'] # annotation positions in units of samples
                    if len(lp)>0:
                        lp[:,0] = np.floor(lp[:,0])
                        lp[:, 1] = np.ceil(lp[:, 1])
                        lp = lp[(lp[:,0]>=0)&(lp[:,1]<=f_vec_d.shape[0])]  # select annotations within the present file
                    for loc in lp.astype('int'):
                        # print(label,loc)
                        f_label[loc[0]:loc[1]] = i+1  # label 0 is reserved for blanks
                    locs = f_label == (i + 1)
                    n_labeled = np.sum(locs)  # number of datapoints labled with label
                    if n_labeled>0:
                        (mu, cov) = average_mu_and_cov(np.mean(f_vec_d[locs],axis=0)[:,np.newaxis],
                                                       np.cov(f_vec_d[locs].T,bias=True),
                                                       n_labeled,
                                                       self.class_means[i][:,np.newaxis],
                                                       self.class_cov[i],
                                                       self.class_npoints[i])
                        # update variables
                        self.class_means[i] = mu.ravel()
                        self.class_cov[i]   = cov
                        self.class_npoints[i] += n_labeled

                    locs = f_label == 0
                    n_labeled = np.sum(locs)  # number of datapoints labled with label
                    if n_labeled>0:
                        (mu, cov) = average_mu_and_cov(np.mean(f_vec_d[locs],axis=0)[:,np.newaxis],
                                                       np.cov(f_vec_d[locs].T,bias=True),
                                                       n_labeled,
                                                       self.blank_means[:,np.newaxis],
                                                       self.blank_cov,
                                                       self.blank_npoints)
                        # update variables
                        self.blank_npoints += n_labeled
                        self.blank_means = mu.ravel()
                        self.blank_cov   = cov

        trans_list = [(l[0],l[1],i+1) for i,key in enumerate(self.labels2classify) for l in labeled_positions[key]]
        trans_list.sort()
        T = transitionslist2matrix(trans_list, 1/fmeta_dict['fs'], len(self.labels2classify))
        print('Transitions:\n', T)
        self.hmm.A = tansitions2rates(T, self.blank_npoints, self.class_npoints)
        print('HMM.A:\n',self.hmm.A)
                
    def log_likelyhoods(self, f_vec, bias=True, no_scale = False):
        LL = np.zeros((f_vec.shape[0], self.class_means.shape[0]+1))
        LL[:,0] = MVGD_LL(f_vec,self.blank_means,reg_invcov(self.blank_cov,self.blank_npoints))
        for i in range(self.class_means.shape[0]):
            LL[:,i+1] = MVGD_LL(f_vec, self.class_means[i], reg_invcov(self.class_cov[i],self.class_npoints[i]),no_scale)

        if bias:
            bias_v = np.vstack((np.log(self.blank_npoints),*np.log(self.class_npoints)))
            bias_v -= np.log(np.sum(self.class_npoints)+ self.blank_npoints)
            LL = LL + bias_v.T
        return LL

    def classify_animal(self, animal,max_annotations=-1):
        LLv = []
        R2v = []
        timev = []
        eegfiles = animal.eeg_files.copy()
        eegfiles.sort()
        for i,eegfname in enumerate(eegfiles):
            fname = '.'.join(eegfname.split('.')[:-1] + ['features'])
            f_vec = np.fromfile(fname, dtype='float64')
            f_vec = f_vec.reshape((-1, self.Ndim))
            np.nan_to_num(f_vec, copy=False)
            fmeta_file = '.'.join(eegfname.split('.')[:-1] + ['fmeta'])
            with open(fmeta_file) as f:
                fmeta_dict = json.load(f)
            print('Animal:', animal.id, 'file:', i, 'of', len(eegfiles), fmeta_file, end='\r')
            LL = self.log_likelyhoods(f_vec, bias=False, no_scale=False)
            R2 = self.log_likelyhoods(f_vec, bias=False, no_scale=True)
            start = fmeta_dict['start_timestamp_unix']
            dt = 1/fmeta_dict['fs']
            t  = np.arange(start,start+dt*len(f_vec),dt)
            LLv.append(LL)
            R2v.append(R2)
            timev.append(t)

        print('Combining results and generating annotations...')
        LLv = np.vstack(LLv)
        R2v = np.vstack(R2v)
        timev = np.hstack(timev)
        pf = self.hmm.forward_backward(LLv.T)
        # threshold to reject classifications outside .999 confidence interval of the class distribution
        th = chi2.isf(1e-3,self.Ndim,scale=0.5)
        for i2,label in enumerate(self.labels2classify):
            i = i2+1
            print(i,label)
            starts = np.nonzero(np.diff(((pf[i, :].T * (-R2v[:, i] < th)) > .5).astype('int')) > 0)[0]
            ends = np.nonzero(np.diff(((pf[i, :].T * (-R2v[:, i] < th)) > .5).astype('int')) < 0)[0]
            alist = []
            print('len starts',len(starts))
            for j in range(len(starts)):
                print('start,end', starts[j], ends[j])
                c = np.sum(LLv[starts[j]:ends[j],i])-np.sum(LLv[starts[j]:ends[j],0])
                a = AnnotationElement(label='(auto)'+label,start=timev[starts[j]],end=timev[ends[j]],confidence=c)
                alist.append((c,a))

            print(alist)
            alist.sort()
            animal.annotations.delete_label('(auto)'+label)  # Delete all previous auto generated labels
            try:
                old_color = animal.annotations.label_color_dict[label]
                print('found color for ', label, old_color)
            except:
                print('did not find color for' , label)
                old_color = (255,255,255)
            new_color = tuple([ max(int(c*0.5),0) for c in old_color])
            animal.annotations.add_label('(auto)'+label,color = new_color)
            for c,a in alist[:max_annotations]:
                animal.annotations.add_annotation(a)

        return (LLv,R2v,pf,timev)

                


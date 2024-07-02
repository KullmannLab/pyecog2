import numpy as np
from pyecog2.ProjectClass import FileBuffer
import os
from scipy import linalg
import scipy.stats as stats
from collections import OrderedDict
from pyecog2.feature_extractor import FeatureExtractor
from pyecog2.hmm_pyecog import HMM_LL
import json
from numba import jit
from scipy.stats import chi2
from pyecog2.annotations_module import AnnotationElement
import logging
logger = logging.getLogger(__name__)

@jit(nopython=True,nogil=True)
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


@jit(nopython=True,nogil=True)
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
    # return np.linalg.inv(M*n/(n+1) + np.eye(len(M))*M.diagonal()/(n+1))  # regularize with 1/n
    # np.linalg.inv(M*np.sqrt(n)/(np.sqrt(n)+1) + np.eye(len(M))*M.diagonal()/(np.sqrt(n)+1))  # regularize with sqrt(1/n)
    # M0 = M*np.sqrt(n)/(np.sqrt(n)+1) + np.diag(M.diagonal()/(np.sqrt(n)+1))
    # np.savez('/Users/marcoleite/4Aaron/RAPTOR 111223-181223/test_mat.npz',M0)
    # np.savez('/Users/marcoleite/4Aaron/RAPTOR 111223-181223/input_mat.npz',M)
    # np.savez('/Users/marcoleite/4Aaron/RAPTOR 111223-181223/n.npz',n)
    # logger.info(M0)
    return np.linalg.pinv(M*np.sqrt(n)/(np.sqrt(n)+1) + np.diag(M.diagonal()/(np.sqrt(n)+1)))


def average_mu_and_cov(mu1,cov1,n1,mu2,cov2,n2):
    np.nan_to_num(mu1,copy=False)
    np.nan_to_num(mu2,copy=False)
    np.nan_to_num(cov1,copy=False)
    np.nan_to_num(cov2,copy=False)
    if n1==0 and n2==0:
        return ((mu1+mu2)/2 , (cov1+cov2)/2 ) #  the returned values in this case should not really matter much...
    mu = (mu1*n1 + mu2*n2)/(n1 + n2)
    cov = n1/(n1+n2)*(cov1 + (mu-mu1)@(mu-mu1).T) + n2/(n1+n2)*(cov2 + (mu-mu2)@(mu-mu2).T)
    return (mu,cov)

def transitionslist2matrix(t, dt, n):
    A = np.zeros((n + 1, n + 1))
    if not t: # no transitions
        return A
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

def transitions2rates(B,nblankpoints,nclasspoints):
    A = B.copy()
    A[0,0] = nblankpoints - np.sum(A[0,:])
    A[0,:] /= np.sum(A[0,:])
    for i in range(len(nclasspoints)):
        if nclasspoints[i]>.5: # allow some numerical impersisions
            A[i+1,i+1] = nclasspoints[i] - np.sum(A[i+1,:])
            A[i+1,:] /= np.sum(A[i+1,:])
        else: # For classes that do not occur, default to transition to blanks
            A[i+1,:] = 0
            A[i+1,0] = 1
    return A/A.sum(axis=1,keepdims=True)  #force normalization to get rid of numerical errors

def intervals_overlap(a,b):
    return (a[0] <= b[0] < a[1]) or (a[0] <= b[1] < a[1]) or (b[0] <= a[0] < b[1]) or (b[0] <= a[1] < b[1])

class ProjectClassifier():
    '''
    Class to bundle and assimilate classifiers for the different animals in a project
    '''
    def __init__(self, project,labels = None):
        self.project = project
        classifier_dir = project.project_file + '_classifier'
        self.feature_extractor = FeatureExtractor()
        if os.path.isfile(os.path.join(classifier_dir, '_feature_extractor.json')):
            self.feature_extractor.load_settings(os.path.join(classifier_dir, '_feature_extractor.json'))
        self.global_classifier = GaussianClassifier(project, self.feature_extractor,labels)
        self.imported_classifier = GaussianClassifier(project, self.feature_extractor,labels)
        if os.path.isdir(classifier_dir):
            self.load()
        else:
            logger.info(f'creating classifier folder:{classifier_dir}')
            print(f'creating classifier folder:{classifier_dir}')
            os.mkdir(classifier_dir)
            self.animal_classifier_dict = OrderedDict([(a.id, GaussianClassifier(project, self.feature_extractor, labels)) for a in project.animal_list])

    def save(self):
        classifier_dir = self.project.project_file+'_classifier'
        if not os.path.isdir(classifier_dir):
            os.mkdir(classifier_dir)
        self.global_classifier.save(os.path.join(classifier_dir,'_global.npz'))
        self.imported_classifier.save(os.path.join(classifier_dir,'_imported.npz'))
        self.feature_extractor.save_settings(os.path.join(classifier_dir, '_feature_extractor.json'))
        for animal_id in self.animal_classifier_dict:
            self.animal_classifier_dict[animal_id].save(os.path.join(classifier_dir, animal_id+'.npz'))

    def load(self):
        classifier_dir = self.project.project_file + '_classifier'
        logger.info(f'loading {classifier_dir}')
        print('loading',classifier_dir)
        self.animal_classifier_dict = OrderedDict([(a.id, GaussianClassifier(self.project,
                                                                      self.feature_extractor,
                                                                      self.global_classifier.labels2classify))
                                            for a in self.project.animal_list])  # generate classifiers for all animals

        if not os.path.isdir(classifier_dir):
            logger.info('No classifiers saved for current project yet')
            print('No classifiers saved for current project yet')
            return
        try:
            self.global_classifier.load(os.path.join(classifier_dir,'_global.npz'))
        except Exception:
            logger.info('Could not load global classifier')
            print('Could not load global classifier')
        try:
            self.imported_classifier.load(os.path.join(classifier_dir,'_imported.npz'))
        except Exception:
            logger.info('Could not load imported classifier')
            print('Could not load imported classifier')
        try:
            self.feature_extractor.load_settings(os.path.join(classifier_dir, '_feature_extractor.json'))
        except:
            logger.info('Could not load feature extractor')
            print('Could not load feature extractor')
        for animal_id in self.animal_classifier_dict: # load classifiers for the ones that exist
            try:
                self.animal_classifier_dict[animal_id].load(os.path.join(classifier_dir, animal_id+'.npz'))
            except Exception:
                logger.info(f'{animal_id} does not have a classifier yet')
                print(f'{animal_id} does not have a classifier yet')

    def import_classifier(self,fname):
        # Perform checks to see if imported classfier is compatible with current project
        temp_classifier = GaussianClassifier()
        temp_classifier.load(fname)
        imported_fe = FeatureExtractor()
        ife_settings = os.path.join(os.path.dirname(fname),'_feature_extractor.json')
        imported_fe.load_settings(ife_settings)
        if imported_fe.settings != self.feature_extractor.settings:
            print('ERROR: unable to import classifier because feature extractor from imported classifier differs from current feature extractor')
            return
        if set(self.global_classifier.features) != set(temp_classifier.features):
            print('ERROR: unable to import classifier because the set of features used on imported classifier differ from the set used in current project')
            logger.warning(f'imported features:{temp_classifier.features}')
            logger.warning(f'global features:{self.global_classifier.features}')
            return
        if set(self.global_classifier.labels2classify) != set(temp_classifier.labels2classify):
            # add missing labels to project
            self.project.homogenize_labels(temp_classifier.labels2classify)
        # Commit to import classifier
        self.imported_classifier.load(fname)


    def assimilate_global_classifier(self,labels2train=None, animals2use=None,features2use=None):
        _,_,npoints = self.imported_classifier.all_mu_and_cov()
        if npoints:
            self.global_classifier.copy_from(self.imported_classifier) # start with either blank classifier or something imported
        else:
            self.global_classifier = GaussianClassifier(self.project, self.feature_extractor,labels = labels2train, features=features2use)
        for k, gc in self.animal_classifier_dict.items():
            if animals2use is None or k in animals2use:
                logger.info(f'assimilating {k}')
                print(f'assimilating {k}')
                self.global_classifier.assimilate_classifier(gc)
        self.global_classifier.save(os.path.join(self.project.project_file + '_classifier','_global.npz'))

    def train_animal(self,animal_id,pbar=None,labels2train=None,features2use=None):
        logger.info(f'started training of animal {animal_id}')
        a = self.project.get_animal(animal_id)
        if False:  # animal_id in self.animal_classifier_dict.keys(): # At this point there is no point on keeping the previous classifier
            gc = self.animal_classifier_dict[animal_id]
        else:
            gc = GaussianClassifier(self.project,self.feature_extractor,labels = labels2train, features=features2use)
            self.animal_classifier_dict[animal_id] = gc
        gc.train([a],progress_bar=pbar)
        gc.save(os.path.join(self.project.project_file + '_classifier',animal_id+'.npz'))
        logger.info(f'finished training of animal {animal_id}')

    def classify_animal_with_global(self, animal, progress_bar=None,max_annotations=-1,labels2annotate=None, prob_th=0.5, outlier_th = 1, viterbi=False):
        gc = GaussianClassifier(self.project,self.feature_extractor,self.global_classifier.labels2classify)
        if self.animal_classifier_dict[animal.id].blank_npoints ==0:
            progress_bar.setValue(0.1)
            logger.info('Training animal specific classifier first...')
            print('Training animal specific classifier first...')
            self.animal_classifier_dict[animal.id].train([animal])
        gc.copy_from(self.animal_classifier_dict[animal.id])
        # if gc.blank_npoints == 0:
        #     progress_bar.setValue(0.1)
        #     logger.info('Training animal specific classifier first...')
        #     print('Training animal specific classifier first...')
        #     gc.train([animal])
        gc.copy_re_normalized_classifier(self.global_classifier)
        gc.classify_animal(animal,progress_bar,max_annotations,labels2annotate, prob_th=prob_th, outlier_th = outlier_th,viterbi=viterbi)



class GaussianClassifier():
    '''
    Class to setup, train and run the classifier on feature files from animal
    '''

    def __init__(self,project,feature_extractor, labels=None,features=None):
        self.project = project
        if labels is None: # which labels to classify
            labels = self.project.get_all_labels()
        self.labels2classify = np.array(list(labels))  # Populate this with the annotation labels to classify

        if features is None:  # which features to use in classifier
            self.features = np.ones(feature_extractor.number_of_features)
        else:
            self.features = features
        self.Ndim = int(np.sum(self.features))
        self.FeatureExtractorNdim = feature_extractor.number_of_features

        self.overlap = np.array(feature_extractor.settings['overlap'])
        self.class_means   = np.zeros((len(self.labels2classify),self.Ndim))
        self.class_cov     = np.tile(np.eye(self.Ndim),(len(self.labels2classify),1,1))
        self.class_npoints = np.zeros(len(self.labels2classify),dtype=int)
        self.blank_means   = np.zeros(self.Ndim)
        self.blank_cov     = np.eye(self.Ndim)
        self.blank_npoints = np.array(0)
        self.transitions_matrix = np.zeros((len(self.labels2classify)+1, len(self.labels2classify)+1))
        # self.hmm           = HMM_LL()

    def all_mu_and_cov(self):
        mu = self.blank_means[:, np.newaxis].copy()
        cov = self.blank_cov.copy()
        npoints = self.blank_npoints.copy()
        for i in range(len(self.labels2classify)):
            muc = self.class_means[i][:, np.newaxis]
            covc = self.class_cov[i]
            npointsc = self.class_npoints[i]
            mu, cov = average_mu_and_cov(mu, cov, npoints, muc, covc, npointsc)
            npoints += npointsc
        return (mu,cov,npoints)

    def whitening_mu_W_iW(self): # return mean of full data and whitening matrix such that W(x-mu) has standard normal dist.
        mu,cov,n = self.all_mu_and_cov() # mean and covariance of full data
        if n: # if the datapoints considered are more than 0
            W = linalg.sqrtm(reg_invcov(cov,n)) # use all the covariance matrix
            # W = linalg.sqrtm(reg_invcov(cov,0)) # only use the diagonal of the covariance matrix
            iW = linalg.inv(W)
        else:
            W = np.eye(self.Ndim)
            iW = np.eye(self.Ndim)
        return mu, W, iW

    def copy_re_normalized_classifier(self,gc):
        # transform parameters from gc so to match data distribution of self
        mua, Wa, iWa = gc.whitening_mu_W_iW()
        mub, Wb, iWb = self.whitening_mu_W_iW()
        self.labels2classify = gc.labels2classify
        for i in range(len(self.labels2classify)):
            self.class_means[i][:, np.newaxis] = iWb@Wa@(gc.class_means[i][:, np.newaxis] - mua) + mub
            self.class_cov[i] = iWb@Wa@gc.class_cov[i]@Wa.T@iWb.T
            self.class_npoints[i] = gc.class_npoints[i]
        self.blank_means[:, np.newaxis] = iWb@Wa@(gc.blank_means[:, np.newaxis] - mua) + mub
        self.blank_cov = iWb@Wa@gc.blank_cov@Wa.T@iWb.T
        self.blank_npoints = gc.blank_npoints
        self.transitions_matrix = gc.transitions_matrix.copy()
        # self.hmm = gc.hmm

    def assimilate_classifier(self,gc):
        # weighted average of re-normalized means and covariances for all classes
        mua, Wa, iWa = gc.whitening_mu_W_iW()
        mub, Wb, iWb = self.whitening_mu_W_iW()
        common_label_indices = [(0,0)] # save common labels to assimilate transition matrix, blanks are always 0 in transition matrix
        for i in range(len(self.labels2classify)):
            j, = np.where(gc.labels2classify == self.labels2classify[i])
            if not j.size:
                continue
            j = j[0]  # if the label exists in gc, grab its index
            common_label_indices.append((i+1,j+1))
            normalized_gc_mu = iWb@Wa@(gc.class_means[j][:, np.newaxis] - mua) + mub
            normalized_gc_cov = iWb@Wa@gc.class_cov[j]@Wa.T@iWb.T
            mu, cov = average_mu_and_cov(self.class_means[i][:, np.newaxis], self.class_cov[i], self.class_npoints[i],
                                         normalized_gc_mu, normalized_gc_cov, gc.class_npoints[j])
            self.class_means[i][:, np.newaxis] = mu
            self.class_cov[i] = cov
            self.class_npoints[i] += gc.class_npoints[j]

        normalized_gc_mu = iWb@Wa@(gc.blank_means[:, np.newaxis] - mua) + mub
        normalized_gc_cov = iWb@Wa@gc.blank_cov@Wa.T@iWb.T
        mu, cov = average_mu_and_cov(self.blank_means[:, np.newaxis], self.blank_cov, self.blank_npoints,
                                     normalized_gc_mu, normalized_gc_cov, gc.blank_npoints)
        self.blank_means[:, np.newaxis] = mu
        self.blank_cov = cov
        self.blank_npoints += gc.blank_npoints
        i,j = tuple(zip(*common_label_indices))  # self labels i correspond to gc labels j
        self.transitions_matrix[np.ix_(i,i)] += gc.transitions_matrix[np.ix_(j,j)]

    def train(self,animal_list=None,progress_bar=None):
        if animal_list is None:
            animal_list = self.project.animal_list
        Nanimals = len(animal_list)
        labeled_positions = {}
        for ianimal, animal in enumerate(animal_list):
            '''
            recieving animal list to possibly allow to lump different datasets into a single GC, but usually the animal 
            list will only contain one animal
            '''

            logger.info(f'Training with animal: {animal.id}')
            logger.info(f'Training with classes: {self.labels2classify}')

            print(f'Training with animal: {animal.id}')
            print(f'Training with classes: {self.labels2classify}')
            for label in self.labels2classify:
                labeled_positions[label] = np.array([a.getPos() for a in animal.annotations.get_all_with_label(label)])
                for a in animal.annotations.get_all_with_label(label):
                    a.setConfidence(float('inf')) # set manually checked annotations to infinite confidence
            Nfiles = len(animal.eeg_files[:])
            for ifile, eeg_file in enumerate(animal.eeg_files[:]):
                feature_file = '.'.join(eeg_file.split('.')[:-1] + ['features'])
                fmeta_file = '.'.join(eeg_file.split('.')[:-1] + ['fmeta'])
                with open(fmeta_file) as f:
                    fmeta_dict = json.load(f)
                f_vec = np.fromfile(feature_file, dtype=fmeta_dict['data_format'])
                # condition fvec
                f_vec_d = f_vec.reshape((-1, self.FeatureExtractorNdim))
                f_vec_d = f_vec_d[:, self.features]
                np.nan_to_num(f_vec_d,copy=False)
                f_label = np.zeros(f_vec_d.shape[0])

                for i, label in enumerate(self.labels2classify):
                    lp = (labeled_positions[label]-fmeta_dict['start_timestamp_unix'])*fmeta_dict['fs'] #  annotation positions in units of samples
                    if len(lp)>0:
                        lp[:,0] = np.floor(lp[:,0])
                        lp[:, 1] = np.ceil(lp[:, 1])
                        lp = lp[(lp[:,1]>=0)&(lp[:,0]<=f_vec_d.shape[0])]  # select annotations within the present file
                    for loc in lp.astype('int'):
                        # print(label,loc)
                        f_label[max(loc[0],0):min(loc[1],f_vec_d.shape[0])] = i+1  # label 0 is reserved for blanks
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

                # After going through all the labels, do the blanks in the locations without labels
                locs = f_label == 0
                n_labeled = np.sum(locs)  # number of datapoints labled with blank
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
                    if sum(np.isnan(cov.ravel())):
                        logger.info(f'\nCov matrix is NaN after file: {ifile} {eeg_file} \n')
                        print('\nCov matrix is NaN after file:',ifile,eeg_file,'\n')
                        self._debug_f_vec_d =f_vec_d
                        return

                if progress_bar is not None:
                    progress_bar.setValue(100*(ianimal + ifile/Nfiles)/Nanimals)
                else:
                    print('Animal:', animal.id, 'file:', ifile, 'of', len(animal.eeg_files), feature_file, end='\r')

        trans_list = [(l[0],l[1],i+1) for i,key in enumerate(self.labels2classify) for l in labeled_positions[key]]
        trans_list.sort()
        self.transitions_matrix = transitionslist2matrix(trans_list, 1/fmeta_dict['fs'], len(self.labels2classify))
        logger.info(f'Transitions:\n {self.transitions_matrix}')
        print('Transitions:\n', self.transitions_matrix)
        if progress_bar is not None:
            progress_bar.setValue(100)
        # self.hmm.A = tansitions2rates(T, self.blank_npoints, self.class_npoints)
        # print('HMM.A:\n',self.hmm.A)

    def log_likelyhoods(self, f_vec, bias=True, no_scale = False):
        LL = np.zeros((f_vec.shape[0], self.class_means.shape[0]+1))
        LL[:,0] = MVGD_LL(f_vec,self.blank_means,reg_invcov(self.blank_cov,self.blank_npoints),no_scale)
        for i in range(self.class_means.shape[0]):
            LL[:,i+1] = MVGD_LL(f_vec, self.class_means[i], reg_invcov(self.class_cov[i],self.class_npoints[i]),no_scale)

        if bias:
            bias_v = np.vstack((np.log(self.blank_npoints),*np.log(self.class_npoints)))
            bias_v -= np.log(np.sum(self.class_npoints)+ self.blank_npoints)
            LL = LL + bias_v.T
        return LL

    def classify_animal(self, animal, progress_bar=None, max_annotations=-1, labels2annotate=None, prob_th=0.5,
                        outlier_th = 1, viterbi=False):
        if self.blank_npoints == 0:
            logger.info('Classifier needs to be trained first')
            print('Classifier needs to be trained first')
            return None,None,None,None

        if labels2annotate is None:
            labels2annotate = self.labels2classify
        LLv = []  # log likelihoods over time for each class
        R2v = []  # R square over time for each class (used to check for outliers)
        timev = []
        eegfiles = animal.eeg_files.copy()
        eegfiles.sort()
        Nfiles = len(eegfiles)
        for i,eegfname in enumerate(eegfiles):
            fname = '.'.join(eegfname.split('.')[:-1] + ['features'])
            f_vec = np.fromfile(fname, dtype='float64')
            f_vec = f_vec.reshape((-1, self.FeatureExtractorNdim))
            f_vec = f_vec[:, self.features]
            np.nan_to_num(f_vec, copy=False)
            fmeta_file = '.'.join(eegfname.split('.')[:-1] + ['fmeta'])
            with open(fmeta_file) as f:
                fmeta_dict = json.load(f)
            LL = self.log_likelyhoods(f_vec, bias=False, no_scale=False)
            np.nan_to_num(LL,copy=False)
            R2 = self.log_likelyhoods(f_vec, bias=False, no_scale=True)
            np.nan_to_num(R2,copy=False)
            start = fmeta_dict['start_timestamp_unix']
            dt = 1/fmeta_dict['fs']
            t  = np.arange(start,start+dt*len(f_vec),dt)
            LLv.append(LL)
            R2v.append(R2)
            timev.append(t)
            if progress_bar is not None:
                progress_bar.setValue(90*i/Nfiles)  # This takes about 90%of the time
            else:
                print('Animal:', animal.id, 'file:', i, 'of', len(eegfiles), fmeta_file, end='\r')

        LLv = np.vstack(LLv)
        _, _, total_npoints = self.all_mu_and_cov()
        th = chi2.isf(1/total_npoints,self.Ndim,scale=0.5)
        LLth = np.diag(self.log_likelyhoods(np.vstack((self.blank_means, self.class_means)), bias=False)) - th
        # Now will regularize LLv for extreme values and compensate HMMfor repeated observations because of overlap of Feature extractor
        LLv_reg = np.maximum(LLth, LLv)*(1-self.overlap)*.5 # TEMPORARY 0.5 FACTOR!
        R2v = np.vstack(R2v)
        timev = np.hstack(timev)
        logger.info('\nRunning HMM...')
        print('\nRunning HMM...')
        hmm = HMM_LL()
        hmm.A = transitions2rates(self.transitions_matrix, self.blank_npoints, self.class_npoints)

        # pf = hmm.forward_backward(LLv.T)
        pf = hmm.forward_backward(LLv_reg.T)  # posterior probabilities

        # now will carefully compute log(1-posterior_probabilities) to avoid overflows
        ab = (hmm.alpha + hmm.beta).T
        ab = ab - ab.max(axis=1, keepdims=True)
        log_not_posterior = np.log(np.exp(ab) @ (np.ones((ab.shape[1], ab.shape[1])) - np.eye(ab.shape[1]))) \
                            - np.log(np.exp(ab) @ (np.ones((ab.shape[1], ab.shape[1]))))
        MLpath = None
        if viterbi:
            MLpath,_,_ = hmm.viterbi(LLv_reg.T)

        if progress_bar is not None:
            progress_bar.setValue(99)   # Almost done...
        logger.info('Combining results and generating annotations...')
        print('Combining results and generating annotations...')
        # threshold to reject classifications outside .999 confidence interval of the class distribution
        th = chi2.isf(1e-3,self.Ndim,scale=0.5)
        th = chi2.isf(outlier_th/total_npoints,self.Ndim,scale=0.5)

        for i2,label in enumerate(self.labels2classify):
            if label not in labels2annotate: # ignore labels that are not in labels2annotate
                continue
            i = i2+1
            print(i,label)

            if viterbi:
                starts = np.nonzero(np.diff((MLpath == i).astype('int'), prepend=0) > 0)[1]
                ends = np.nonzero(np.diff((MLpath == i).astype('int'), append=0) < 0)[1] + 1
            else:
                starts = np.nonzero(np.diff(((pf[i, :].T * (-R2v[:, i] < th)) > prob_th).astype('int'),  prepend=0) > 0)[0]
                ends = np.nonzero(np.diff(((pf[i, :].T * (-R2v[:, i] < th)) > prob_th).astype('int'),  append=0) < 0)[0] + 1

            alist = []
            print('len starts',len(starts))
            manual_label_positions = [a.getPos() for a in animal.annotations.get_all_with_label(label)]
            print('manual label positions:',manual_label_positions)
            for j in range(len(starts)):
                if not any([intervals_overlap([timev[starts[j]],timev[ends[j]]],pos) for pos in manual_label_positions]):
                    if ends[j]-starts[j]<.5: # this 0.5 seems a bit arbitrary - probably should be reviewed - todo
                        print('interval too small:',starts[j],ends[j])
                        continue
                    # c = np.sum(LLv[starts[j]:ends[j],i])-np.sum(LLv[starts[j]:ends[j],0])
                    # c = np.sum(np.log(pf[i,starts[j]:ends[j]])-np.log(np.maximum(1-pf[i,starts[j]:ends[j]],1e-12)))
                    # c = np.sum(-np.log(np.maximum(1-pf[i,starts[j]:ends[j]],1e-12)))
                    # c = np.max(-np.log(np.maximum(1-pf[i,starts[j]:ends[j]],2**-50)))
                    # c = np.max(LLv_reg[starts[j]:ends[j], i])
                    # c = np.mean(R2v[starts[j]:ends[j], i])
                    c = np.max( - log_not_posterior[starts[j]:ends[j], i])
                    # print('start,end,confidence', starts[j], ends[j],c)
                    a = AnnotationElement(label='(auto)'+label,start=timev[starts[j]],end=timev[ends[j]],confidence=c)
                    alist.append((c,a))
                else:
                    print('annotation already exists at', starts[j], ends[j])

            logger.info(f'Found {len(alist)} putative events. Saving {max_annotations} with highest confidence score')
            print('Found',len(alist), 'putative events. Saving',max_annotations,'with highest confidence score')
            alist.sort(key=lambda c:-c[0])
            animal.annotations.delete_label('(auto)'+label)  # Delete all previous auto generated labels
            try:
                old_color = animal.annotations.label_color_dict[label]
                # print('found color for ', label, old_color)
            except Exception:
                # print('did not find color for' , label)
                old_color = (255,255,255)
            new_color = tuple([ max(int(c*0.65),0) for c in old_color])
            animal.annotations.add_label('(auto)'+label,color = new_color)

            animal.annotations.pause_history_cache(True)
            for c,a in alist[:max_annotations]:
                animal.annotations.add_annotation(a)
            animal.annotations.pause_history_cache(False)

        if progress_bar is not None:
            progress_bar.setValue(100)   # Done
        return (LLv,R2v,pf,timev)

    def save(self,filename):
        project = self.project
        self.project = np.array([])
        np.savez(filename,**self.__dict__)
        self.project = project

    def load(self,filename):
        project = self.project # keep project field
        with np.load(filename) as d:
            self.__dict__= dict([(file,d[file]) for file in d.files]) # copy all arrays from file
        self.project = project

    def copy_from(self,gaussian_classifier):
        for key in self.__dict__.keys():
            # if key not in ['project','labels2classify','features','Ndim','FeatureExtractorNdim']:
            if key not in ['project']:
                try:
                    self.__dict__[key] = gaussian_classifier.__dict__[key].copy()
                except:
                    logger.warning(f'error trying to copy gaussian_classifier.__dict__[{key}]')
                    print(f'error trying to copy gaussian_classifier.__dict__[{key}]')
                    raise


import numpy as np

from numba import jit
from numba.experimental import jitclass
import numba
# from sklearn.preprocessing import normalize


class HMMBayes():
    '''
    Hmm class expecting transition matrix A only. This class
    expects probability of p(Zt|Xt) produced by
    the classifier and uses Bayes rule to relate to
    p(Xt|Zt) = p(Zt|Xt)p(Xt)/p(Zt).

    See Bishop, Svensen and Hinton 2004:
    Distinguishing text from graphics in on-line handwritten ink.
    '''

    def __init__(self):
        '''
        :param A: transition matrix, A_ij is p(Z_t=j|Z_t-1=i)
        '''
        self._A = None
        self.stationary_dist = None
        pass

    @staticmethod
    def get_state_transition_probs(labels):
        if len(labels.shape) > 1:
            labels = np.ravel(labels)

        tp = np.zeros(shape=(2, 2))  # todo this should not be hardcoded?
        for i, label in enumerate(labels[:-1]):
            next_label = int(labels[i + 1])
            label = int(label)
            tp[label, next_label] += 1

        tp = tp/np.sum(np.abs(tp),axis=1) # normalize(tp, axis=1, norm='l1') avoid using sklearn just for this
        return tp

    @property
    def A(self):
        return self._A
    @A.setter
    def A(self, A):
        assert all(np.sum(A, axis=1) == 1)
        # transpose to get left eigen vector
        eigen_vals, eigen_vecs = np.linalg.eig(A.T)
        ind = np.where(eigen_vals == 1)[0]
        self.stationary_dist = eigen_vecs[:, ind].T[0]  # transpose back as should be row vec
        self.stationary_dist = self.stationary_dist/np.sum(self.stationary_dist)
        self._A = A

    def __repr__(self):
        return 'Hidden Markov model object : expects probability of p(Zt|Xt) produced by the classifier \
                and uses Bayes rule to relate to p(Xt|Zt) = p(Zt|Xt)p(Xt)/p(Zt).'

    @staticmethod
    @numba.jit(nopython=True)
    def forward(x, k, N, A, phi, stationary_dist):
        alpha = np.zeros((k, N))  # init alpha vect to store alpha vals for each z_k (rows)
        alpha[:, 0] = np.log((phi[:, 0] * stationary_dist))
        for t in np.arange(1, N):
            max_alpha_t = np.max(alpha[:, t - 1])  # alphas are alredy logs, therefreo exp to cancel
            exp_alpha_t = np.exp(alpha[:, t - 1] - max_alpha_t)  # exp sum over alphas - b
            alpha_t = phi[:, t] * np.dot(exp_alpha_t.T, A)  # sure no undeflow here...
            alpha[:, t] = np.log(alpha_t) + max_alpha_t  # take log and add back max (already in logs)
            # this may be so small there is an overflow?
        return alpha

    @staticmethod
    @numba.jit(nopython=True)
    def calc_phi(x, stationary_dist):
        # print(stationary_dist, stationary_dist.shape)
        phi = np.zeros(x.shape)
        for t in range(x.shape[1]):
            phi[:, t] = x[:, t] / stationary_dist
        return phi

    @staticmethod
    @numba.jit(nopython=True)
    def backward(x, k, N, A, phi, stationary_dist, alpha):
        beta = np.zeros((k, N))
        posterior = np.zeros((k, N))
        beta[:, N - 1] = 1  # minus one for pythons indexing

        max_posterior_t = np.max(alpha[:, N - 1] + beta[:, N - 1])  # previous beta
        posterior_t = np.exp((alpha[:, N - 1] + beta[:, N - 1]) - max_posterior_t)
        posterior_t = np.divide(posterior_t, np.sum(posterior_t))  # normalise as just proportional too...
        posterior[:, N - 1] = posterior_t

        # t = np.arange(0,N-1)
        for t in np.arange(N - 2, 0 - 1, -1):
            # for t in range(0,N-1)[::-1]: # python actually starts N-2 if [::-1]
            # print(t,end=',')
            max_beta_t = np.max(beta[:, t + 1])  # previous beta
            exp_beta_t = np.exp(beta[:, t + 1] - max_beta_t)
            beta_t = np.dot(A, (phi[:, t + 1] * exp_beta_t))  # is this correct?
            # phi inside the dot product as dependnds on the
            beta[:, t] = np.log(beta_t) + max_beta_t

            max_posterior_t = np.max(alpha[:, t] + beta[:, t])  # previous beta
            posterior_t = np.exp((alpha[:, t] + beta[:, t]) - max_posterior_t)
            posterior_t = np.divide(posterior_t, np.sum(posterior_t))  # normalise as just proportional too...
            posterior[:, t] = posterior_t
        return beta, posterior

    def forward_backward(self, x):
        '''
        x is a 2d vector of p(zt|xt)

        x_i is hidden state (rows)
        x_it t is the timepoint
        returns posterior distribution of p(Zt
        '''
        self.phi = self.calc_phi(x, self.stationary_dist)
        k = x.shape[0]
        N = x.shape[1]

        self.alpha = self.forward(x, k, N, self.A, self.phi, self.stationary_dist)
        self.beta, self.posterior = self.backward(x, k, N, self.A, self.phi, self.stationary_dist, self.alpha)
        return self.posterior


class HMM(HMMBayes):
    """
    Expects state emission probabilities obtainined through
    miss-classification of test-data labels. (Cross val).

    Is therefore a 'standard' HMM implementation.
    """

    def __init__(self):
        HMMBayes.__init__(self)

    def __repr__(self):
        return 'Hidden Markov model object :Expects state emission probabilities obtainined through \
                miss-classification of test-data labels. (Cross val). Is therefore a standard HMM implementation.'

    @property
    def phi_mat(self):
        return self._phi_mat

    @phi_mat.setter
    def phi_mat(self, phi_mat):
        self._phi_mat = phi_mat

    @staticmethod
    @numba.jit(nopython=True)
    def calc_phi_from_emission_matrix(x, phi_mat, stationary_dist):
        phi = np.zeros((phi_mat.shape[0], x.shape[0]))
        for t in range(x.shape[0]):
            phi[:, t] = phi_mat[:, int(x[t])]
        return phi

    def forward_backward(self, x):
        '''
        x is a 1d row vector of "observed" states. ie. classifier
        predictions
        x_0t t is the timepoint
        returns posterior distributions of p(Zt|Xt)
        '''
        self.phi = self.calc_phi_from_emission_matrix(x, self.phi_mat, self.stationary_dist)
        k = self.phi_mat.shape[0]  # n states
        N = x.shape[0]  # timepoints

        self.alpha = self.forward(x, k, N, self.A, self.phi, self.stationary_dist)
        self.beta, self.posterior = self.backward(x, k, N, self.A, self.phi, self.stationary_dist, self.alpha)
        return self.posterior

    @staticmethod
    def get_state_emission_probs(y, preds):
        """
        Uses miss-classification of annotated states labels to
        'obtain' calssifier state emission probabilities given
        annotated label.

        Returns:
        phi_ij - observation emission matrix
            i is the state
            j is the observation
        """
        from sklearn.metrics import confusion_matrix
        cm = confusion_matrix(y, preds)
        phi = np.divide(cm, cm.sum(axis=1)[:, np.newaxis])
        return phi



class HMM_LL():
    '''
    Hmm class expecting transition matrix A only. This class
    expects log(p(Xt|Zt)).

    See Bishop, Svensen and Hinton 2004:
    Distinguishing text from graphics in on-line handwritten ink.
    '''

    def __init__(self):
        '''
        :param A: transition matrix, A_ij is p(Z_t=j|Z_t-1=i)
        '''
        self._A = None
        self.stationary_dist = None
        pass

    @staticmethod
    def get_state_transition_probs(labels):
        if len(labels.shape) > 1:
            labels = np.ravel(labels)

        tp = np.zeros(shape=(2, 2))  # todo this should not be hardcoded?
        for i, label in enumerate(labels[:-1]):
            next_label = int(labels[i + 1])
            label = int(label)
            tp[label, next_label] += 1

        tp = tp/np.sum(np.abs(tp),axis=1) # normalize(tp, axis=1, norm='l1') void using sklearn just for this
        return tp

    @property
    def A(self):
        return self._A
    @A.setter
    def A(self, A):
        assert all(np.sum(A, axis=1) == 1)
        # transpose to get left eigen vector
        eigen_vals, eigen_vecs = np.linalg.eig(A.T)
        ind = np.where(eigen_vals == np.max(eigen_vals))[0]
        self.stationary_dist = eigen_vecs[:, ind].T[0]  # transpose back as should be row vec
        self.stationary_dist = self.stationary_dist/np.sum(self.stationary_dist)
        self._A = A

    def __repr__(self):
        return 'Hidden Markov model object : expects probability of p(Zt|Xt) produced by the classifier \
                and uses Bayes rule to relate to p(Xt|Zt) = p(Zt|Xt)p(Xt)/p(Zt).'

    @staticmethod
    @numba.jit(nopython=True)
    def forward(x, k, N, A, log_phi, stationary_dist):
        alpha = np.zeros((k, N))  # init alpha vect to store alpha vals for each z_k (rows)
        alpha[:, 0] = log_phi[:, 0] + np.log(stationary_dist)
        for t in np.arange(1, N):
            max_alpha_t = np.max(alpha[:, t - 1])  # alphas are alredy logs, therefreo exp to cancel
            exp_alpha_t = np.exp(alpha[:, t - 1] - max_alpha_t)  # exp sum over alphas - b
            alpha_t = log_phi[:, t] + np.log(np.dot(exp_alpha_t.T, A))  # sure no undeflow here...
            alpha[:, t] = alpha_t + max_alpha_t  # take log and add back max (already in logs)
            # this may be so small there is an overflow?
        return alpha

    @staticmethod
    @numba.jit(nopython=True)
    def calc_phi(x, stationary_dist):
        # print(stationary_dist, stationary_dist.shape)
        phi = np.zeros(x.shape)
        for t in range(x.shape[1]):
            phi[:, t] = x[:, t] / stationary_dist
        return phi

    @staticmethod
    @numba.jit(nopython=True)
    def backward(x, k, N, A, log_phi, stationary_dist, alpha):
        beta = np.zeros((k, N))
        posterior = np.zeros((k, N))
        beta[:, N - 1] = 1  # minus one for pythons indexing

        max_posterior_t = np.max(alpha[:, N - 1] + beta[:, N - 1])  # previous beta
        posterior_t = np.exp((alpha[:, N - 1] + beta[:, N - 1]) - max_posterior_t)
        posterior_t = np.divide(posterior_t, np.sum(posterior_t))  # normalise as just proportional too...
        posterior[:, N - 1] = posterior_t

        # t = np.arange(0,N-1)
        for t in np.arange(N - 2, 0 - 1, -1):
            # for t in range(0,N-1)[::-1]: # python actually starts N-2 if [::-1]
            # print(t,end=',')
            phi_beta   = beta[:, t + 1] + log_phi[:, t + 1]
            max_beta_t = np.max(phi_beta)  # previous beta
            exp_beta_t = np.exp(phi_beta - max_beta_t)
            beta_t = np.dot(A, exp_beta_t)  # is this correct?
            # phi inside the dot product as dependnds on the
            beta[:, t] = np.log(beta_t) + max_beta_t

            max_posterior_t = np.max(alpha[:, t] + beta[:, t])  # previous beta
            posterior_t = np.exp((alpha[:, t] + beta[:, t]) - max_posterior_t)
            posterior_t = np.divide(posterior_t, np.sum(posterior_t))  # normalise as just proportional too...
            posterior[:, t] = posterior_t
        return beta, posterior

    def forward_backward(self, x):
        '''
        x is a 2d vector of p(zt|xt)

        x_i is hidden state (rows)
        x_it t is the timepoint
        returns posterior distribution of p(Zt
        '''
        self.phi = x  # self.calc_phi(x, self.stationary_dist)
        k = x.shape[0]
        N = x.shape[1]
        print('HMM:forward')
        self.alpha = self.forward(x, k, N, self.A, self.phi, self.stationary_dist)
        print('HMM:backward')
        self.beta, self.posterior = self.backward(x, k, N, self.A, self.phi, self.stationary_dist, self.alpha)
        return self.posterior

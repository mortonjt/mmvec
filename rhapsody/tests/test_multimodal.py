import glob
import torch
import shutil
import unittest
import numpy as np
from skbio.stats.composition import clr_inv as softmax
from scipy.stats import spearmanr
from scipy.sparse import coo_matrix, csr_matrix
from scipy.spatial.distance import pdist
from rhapsody.multimodal import MMvec
from rhapsody.util import random_multimodal


class TestMMvec(unittest.TestCase):
    def setUp(self):
        # build small simulation
        self.latent_dim = 2
        res = random_multimodal(
            num_microbes=20, num_metabolites=20, num_samples=100,
            latent_dim=self.latent_dim, sigmaQ=2, sigmaU=1, sigmaV=1,
            microbe_total=100, metabolite_total=1000, seed=1
        )
        (self.microbes, self.metabolites, self.X, self.B,
         self.U, self.Ubias, self.V, self.Vbias) = res
        num_test = 10
        self.trainX = self.microbes.iloc[:-num_test]
        self.testX = self.microbes.iloc[-num_test:]
        self.trainY = self.metabolites.iloc[:-num_test]
        self.testY = self.metabolites.iloc[-num_test:]

    def tearDown(self):
        # remove all log directories
        for r in glob.glob("logdir*"):
            shutil.rmtree(r)

    def test_fit(self):
        np.random.seed(1)
        torch.manual_seed(1)

        n, d1 = self.trainX.shape
        n, d2 = self.trainY.shape
        latent_dim = self.latent_dim

        model = MMvec(num_microbes=d1, num_metabolites=d2, latent_dim=latent_dim,
                      batch_size=5, subsample_size=100, gain=2, mc_samples=10,
                      device='cpu')
        model  = model.fit(
            csr_matrix(self.trainX.values), self.trainY.values,
            csr_matrix(self.testX.values), self.testY.values,
            epochs=10, gamma=0.1, learning_rate=1,
            beta1=0.9, beta2=0.95, step_size=1)

        # Loose checks on the weight matrices to make sure
        # that we aren't learning complete garbage
        u = model.embeddings.weight.detach().numpy()
        v = model.muV.detach().numpy()

        ubias = model.bias.weight.detach().numpy()
        vbias = model.muVb.detach().numpy()
        res = spearmanr(pdist(self.U), pdist(u))
        self.assertGreater(res.correlation, 0.15)
        self.assertLess(res.pvalue, 0.05)

        res = spearmanr(pdist(self.V.T), pdist(v.T))
        self.assertGreater(res.correlation, 0.15)
        self.assertLess(res.pvalue, 0.05)


if __name__ == "__main__":
    unittest.main()

import os
import time
import copy
from tqdm import tqdm
import pandas as pd
import numpy as np
from tensorboardX import SummaryWriter
from skbio.stats.composition import clr_inv as softmax
from scipy.stats import spearmanr
import datetime
from .util import onehot, get_batch

import torch
from torch.autograd import Variable
import torch.nn as nn
import torch.nn.functional as F
import torch.optim as optim
from torch.distributions.multinomial import Multinomial



class MMvec(nn.Module):
    def __init__(self, num_microbes, num_metabolites, latent_dim,
                 batch_size=10, subsample_size=100, mc_samples=10,
                 gain=1,
                 device='cpu', save_path=None):
        super(MMvec, self).__init__()
        self.num_microbes = num_microbes
        self.num_metabolites = num_metabolites
        self.device = device
        self.batch_size = batch_size
        self.subsample_size = subsample_size
        self.mc_samples = mc_samples
        if save_path is None:
            basename = "logdir"
            suffix = datetime.datetime.now().strftime("%y%m%d_%H%M%S")
            save_path = "_".join([basename, suffix])
        self.save_path = save_path

        # input layer parameter (for the microbes)
        w = torch.empty(num_microbes, latent_dim, device=device)
        b = torch.empty(num_microbes, 1, device=device)
        torch.nn.init.xavier_uniform_(w, gain=gain)
        torch.nn.init.xavier_uniform_(b, gain=gain)
        self.embeddings = nn.Embedding(num_microbes, latent_dim).to(device)
        self.bias = nn.Embedding(num_microbes, 1).to(device)
        self.logstdU = nn.Embedding(num_microbes, latent_dim).to(device)
        self.logstdUb = nn.Embedding(num_microbes, 1).to(device)
        self.embeddings.weight = nn.Parameter(w)
        self.embeddings.logstdU = nn.Parameter(b)

        # output layer parameters (for the metabolites)
        w_ = torch.empty(latent_dim, num_metabolites-1, device=device)
        b_ = torch.empty(1, num_metabolites-1, device=device)
        torch.nn.init.xavier_uniform_(w_, gain=gain)
        torch.nn.init.xavier_uniform_(b_, gain=gain)

        self.muV = Variable(w_.float(), requires_grad=True)
        self.muVb = Variable(b_.float(), requires_grad=True)
        self.logstdV = Variable(w_.float(), requires_grad=True)
        self.logstdVb = Variable(b_.float(), requires_grad=True)

        self._gradU = False

    def alternate(self):
        if self._gradU:
            self.embeddings.requires_grad = True
            self.bias.requires_grad = True
            self.logstdU.requires_grad = True
            self.logstdUb.requires_grad = True

            self.muV.requires_grad = False
            self.muVb.requires_grad = False
            self.logstdV.requires_grad = False
            self.logstdVb.requires_grad = False

        else:
            self.embeddings.requires_grad = False
            self.bias.requires_grad = False
            self.logstdU.requires_grad = False
            self.logstdUb.requires_grad = False

            self.muV.requires_grad = True
            self.muVb.requires_grad = True
            self.logstdV.requires_grad = True
            self.logstdVb.requires_grad = True

        self._gradU = not self._gradU

    def encode(self, inputs):
        """ Transforms inputs into lower dimensional space"""
        embeds = self.reparameterize(
            self.embeddings(inputs),
            self.logstdU(inputs)
        )
        biases = self.reparameterize(
            self.bias(inputs),
            self.logstdUb(inputs)
        )
        return embeds, biases

    def forward(self, inputs):
        """ Predicts output abundances """
        embeds, biases = self.encode(inputs)

        V = self.reparameterize(self.muV, self.logstdV)
        Vb = self.reparameterize(self.muVb, self.logstdVb)
        lam = biases + embeds @ V + Vb
        zeros = torch.zeros(self.batch_size * self.subsample_size, 1, device=self.device)

        lam = torch.cat((zeros, lam), dim=1)
        m = torch.mean(lam, dim=1)
        log_probs = (lam - m.view(-1, 1))
        return log_probs

    def reparameterize(self, mu, logvar):
        """ Samples from the posterior distribution via
        reparameterization gradients"""
        std = torch.exp(0.5 * logvar)
        eps = torch.randn_like(std, device=self.device)
        return mu + eps*std

    def divergence(self, mu, logvar):
        """ Computes the KL divergence between posterior and prior. """
        # see Appendix B from VAE paper:
        # Kingma and Welling. Auto-Encoding Variational Bayes. ICLR, 2014
        # https://arxiv.org/abs/1312.6114
        return 0.5 * torch.sum(1 + logvar - mu.pow(2) - logvar.exp())

    def cross_validation(self, inp, out):
        """ Computes cross-validation scores on holdout train/test set.

        Here, the mean absolute error is computed, which can be interpreted
        as the average number of counts that were incorrectly predicted.
        """
        logprobs = self.forward(inp)
        n = torch.sum(out, 1)
        probs = torch.nn.functional.softmax(logprobs, 1)
        pred = n.view(-1, 1) * probs

        # computes mean absolute error.
        mae = torch.mean(torch.abs(out - pred))
        return mae

    def loss(self, inp, obs):
        """ Computes the loss function to be minimized. """
        mean_like = torch.zeros(self.mc_samples, device=self.device)
        d1 = self.divergence(self.embeddings.weight, self.logstdU.weight)
        d2 = self.divergence(self.bias.weight, self.logstdUb.weight)
        d3 = self.divergence(self.muV, self.logstdV)
        d4 = self.divergence(self.muVb, self.logstdVb)
        for i in range(self.mc_samples):
            pred = self.forward(inp)
            kld = d1 + d2 + d3 + d4
            likelihood = Multinomial(logits=pred).log_prob(obs)
            mean_like[i] = - torch.mean(kld + likelihood)

        elbo = torch.mean(mean_like)
        return elbo

    def fit(self, trainX, trainY, testX, testY,
            epochs=1000, learning_rate=1e-3, mc_samples=5,
            beta1=0.8, beta2=0.9, gamma=0.1, step_size=1,
            summary_interval=10, checkpoint_interval=10):
        """ Train the actual model

        Parameters
        ----------
        trainX : scipy.sparse.csr
            Input training data (samples x features)
        trainY : np.array
            Output training data (samples x features)
        testX : scipy.sparse.csr
            Input testing data (samples x features)
        testY : np.array
            Output testing data (samples x features)
        epochs : int
            Number of training iterations over the entire dataset
        batch_size : int
            Number of samples to train per iteration
        beta2 : float
            Second momentum constant for ADAM gradient descent Values
            can only be between (0, 1). Values close to 1 indicate
            sparse updates.
        gamma : float
            Percentage decrease of the learning rate per scheduler step.
        step_size: int
            Number of epochs before the scheduler step is incremented.
        summary_interval : int
            The number of seconds until a summary is written.
        checkpoint_interval : int
            The number of seconds until a checkpoint is saved.

        Returns
        -------
        self
        """
        last_checkpoint_time = 0
        last_summary_time = 0
        best_loss = np.inf

        num_samples = trainY.shape[0]
        optimizer = optim.Adam(self.parameters(), betas=(beta1, beta2),
                               lr=learning_rate)
        scheduler = torch.optim.lr_scheduler.StepLR(
            optimizer, step_size=step_size, gamma=gamma)

        writer = SummaryWriter(self.save_path)

        for ep in tqdm(range(0, epochs)):

            self.train()
            scheduler.step()
            # 2 rounds so that both weights can be iterated
            # We need alternating minimization, because
            # this object function is biconvex
            for _ in range(2):
                self.alternate()
                for i in range(0, num_samples, self.batch_size):
                    now = time.time()
                    optimizer.zero_grad()

                    inp, out = get_batch(trainX, trainY, i % num_samples,
                                         self.subsample_size, self.batch_size)
                    inp = inp.to(device=self.device)
                    out = out.to(device=self.device)
                    loss = self.loss(inp, out)
                    loss.backward()
                    ml = loss.item()


                    # remember the best model
                    if ml < best_loss:
                        best_self = copy.deepcopy(self)
                        best_loss = ml
                    # save summary
                    if now - last_summary_time > summary_interval:
                        test_in, test_out = get_batch(testX, testY, i % num_samples,
                                             self.subsample_size, self.batch_size)
                        test_in = test_in.to(device=self.device)
                        test_out = test_out.to(device=self.device)

                        cv_mae = self.cross_validation(test_in, test_out)
                        iteration = i + ep*num_samples
                        writer.add_scalar('elbo', loss, iteration)
                        writer.add_scalar('cv_mae', cv_mae, iteration)
                        writer.add_embedding(
                            self.embeddings.weight.detach(),
                            global_step=iteration)
                        # note that these are in alr coordinates
                        writer.add_embedding(
                            self.muV.detach(),
                            global_step=iteration, tag='muV')
                        last_summary_time = now

                    # checkpoint model
                    now = time.time()
                    if now - last_checkpoint_time > checkpoint_interval:
                        suffix = datetime.datetime.now().strftime("%y%m%d_%H%M%S")
                        torch.save(self.state_dict(),
                                   os.path.join(self.save_path,
                                                'checkpoint_' + suffix))
                        last_checkpoint_time = now

                    optimizer.step()

        return best_self

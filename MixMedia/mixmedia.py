"""This file defines a dynamic etm object.
"""

import torch
import torch.nn.functional as F 
import numpy as np 
import math 

from torch import nn

# from IPython.core.debugger import set_trace
from pdb import set_trace


device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

class MixMedia(nn.Module):
    def __init__(self, args, word_embeddings):
        super(MixMedia, self).__init__()

        ## define hyperparameters
        self.num_topics = args.num_topics
        self.num_times = args.num_times
        self.vocab_size = args.vocab_size
        self.t_hidden_size = args.t_hidden_size
        self.eta_hidden_size = args.eta_hidden_size
        self.rho_size = args.rho_size
        self.emsize = args.emb_size
        self.enc_drop = args.enc_drop
        self.eta_nlayers = args.eta_nlayers
        self.t_drop = nn.Dropout(args.enc_drop)
        self.delta = args.delta
        self.train_embeddings = args.train_embeddings

        self.predict_labels = args.predict_labels
        self.multiclass_labels = args.multiclass_labels

        self.num_sources = args.num_sources
        self.num_labels = args.num_labels

        self.theta_act = self.get_activation(args.theta_act)

        ## define the word embedding matrix \rho: L x V
        if args.train_embeddings:
            self.rho = nn.Linear(args.rho_size, args.vocab_size, bias=False) # L x V
        else:
            num_embeddings, emsize = word_embeddings.size()
            rho = nn.Embedding(num_embeddings, emsize)
            rho.weight.data = word_embeddings
            self.rho = rho.weight.data.clone().float().to(device)
    

        ## define the variational parameters for the topic embeddings over time (alpha) ... alpha is K x L
        self.mu_q_alpha = nn.Parameter(torch.randn(args.num_topics, args.rho_size))
        self.logsigma_q_alpha = nn.Parameter(torch.randn(args.num_topics, args.rho_size))
    
    
        ## define variational distribution for \theta_{1:D} via amortizartion... theta is K x D
        self.q_theta = nn.Sequential(
                    nn.Linear(args.vocab_size+args.num_topics, args.t_hidden_size), 
                    self.theta_act,
                    nn.Linear(args.t_hidden_size, args.t_hidden_size),
                    self.theta_act,
                )
        self.mu_q_theta = nn.Linear(args.t_hidden_size, args.num_topics, bias=True)
        self.logsigma_q_theta = nn.Linear(args.t_hidden_size, args.num_topics, bias=True)

        ## define variational distribution for \eta via amortizartion... eta is K x T
        self.q_eta_map = nn.Linear(args.vocab_size, args.eta_hidden_size)
        
        self.q_eta = nn.LSTM(args.eta_hidden_size, args.eta_hidden_size, args.eta_nlayers, dropout=args.eta_dropout, batch_first=True)

        self.mu_q_eta = nn.Linear(args.eta_hidden_size+args.num_topics, args.num_topics, bias=True)
        self.logsigma_q_eta = nn.Linear(args.eta_hidden_size+args.num_topics, args.num_topics, bias=True)
        
        self.max_logsigma_t = 10
        self.min_logsigma_t = -10


        ## define supervised component for predicting labels
        self.classifier = nn.Linear(args.num_topics, args.num_labels, bias=True)
        self.criterion = nn.CrossEntropyLoss(reduction='sum')


    def get_activation(self, act):
        if act == 'tanh':
            act = nn.Tanh()
        elif act == 'relu':
            act = nn.ReLU()
        elif act == 'softplus':
            act = nn.Softplus()
        elif act == 'rrelu':
            act = nn.RReLU()
        elif act == 'leakyrelu':
            act = nn.LeakyReLU()
        elif act == 'elu':
            act = nn.ELU()
        elif act == 'selu':
            act = nn.SELU()
        elif act == 'glu':
            act = nn.GLU()
        else:
            print('Defaulting to tanh activations...')
            act = nn.Tanh()
        return act 

    def reparameterize(self, mu, logvar):
        """Returns a sample from a Gaussian distribution via reparameterization.
        """
        if self.training:
            std = torch.exp(0.5 * logvar) 
            eps = torch.randn_like(std)
            return eps.mul_(std).add_(mu)
        else:
            return mu

    def get_kl(self, q_mu, q_logsigma, p_mu=None, p_logsigma=None):
        """Returns KL( N(q_mu, q_logsigma) || N(p_mu, p_logsigma) ).
        """
        if p_mu is not None and p_logsigma is not None:
            sigma_q_sq = torch.exp(q_logsigma)
            sigma_p_sq = torch.exp(p_logsigma)
            kl = ( sigma_q_sq + (q_mu - p_mu)**2 ) / ( sigma_p_sq + 1e-6 )
            kl = kl - 1 + p_logsigma - q_logsigma
            kl = 0.5 * torch.sum(kl, dim=-1)
        else:
            kl = -0.5 * torch.sum(1 + q_logsigma - q_mu.pow(2) - q_logsigma.exp(), dim=-1)
        return kl

    def get_alpha(self): ## mean field

        alphas = torch.zeros(self.num_topics, self.rho_size).to(device)
        kl_alpha = []

        alphas = self.reparameterize(self.mu_q_alpha, self.logsigma_q_alpha)

        p_mu_0 = torch.zeros(self.num_topics, self.rho_size).to(device)
        logsigma_p_0 = torch.zeros(self.num_topics, self.rho_size).to(device)

        kl_alpha = self.get_kl(self.mu_q_alpha, self.logsigma_q_alpha, p_mu_0, logsigma_p_0)

        return alphas, kl_alpha.sum() # K x L


    # ## get source-specific etas
    def get_eta(self, rnn_inp): ## structured amortized inference

        etas = torch.zeros(self.num_sources, self.num_times, self.num_topics).to(device)
        kl_eta = []

        inp = self.q_eta_map(rnn_inp.view(rnn_inp.size(0)*rnn_inp.size(1), -1)).view(rnn_inp.size(0),rnn_inp.size(1),-1)
        
        hidden = self.init_hidden()

        output, _ = self.q_eta(inp, hidden)

        inp_0 = torch.cat([output[:,0,:], torch.zeros(self.num_sources,self.num_topics).to(device)], dim=1)

        mu_0 = self.mu_q_eta(inp_0)
        logsigma_0 = self.logsigma_q_eta(inp_0)
        
        etas[:, 0, :] = self.reparameterize(mu_0, logsigma_0)

        p_mu_0 = torch.zeros(self.num_sources, self.num_topics).to(device)
        logsigma_p_0 = torch.zeros(self.num_sources, self.num_topics).to(device)

        kl_0 = self.get_kl(mu_0, logsigma_0, p_mu_0, logsigma_p_0)
        kl_eta.append(kl_0)

        for t in range(1, self.num_times):

            inp_t = torch.cat([output[:,t,:], etas[:, t-1, :]], dim=1)

            mu_t = self.mu_q_eta(inp_t)
            logsigma_t = self.logsigma_q_eta(inp_t)

            if (logsigma_t > self.max_logsigma_t).sum() > 0:
                logsigma_t[logsigma_t > self.max_logsigma_t] = self.max_logsigma_t
            elif (logsigma_t < self.min_logsigma_t).sum() > 0:
                logsigma_t[logsigma_t < self.min_logsigma_t] = self.min_logsigma_t

            etas[:, t, :] = self.reparameterize(mu_t, logsigma_t)

            p_mu_t = etas[:, t-1, :]
            logsigma_p_t = torch.log(self.delta * torch.ones(self.num_sources, self.num_topics).to(device))

            kl_t = self.get_kl(mu_t, logsigma_t, p_mu_t, logsigma_p_t)
            kl_eta.append(kl_t)

        kl_eta = torch.stack(kl_eta).sum()
        return etas, kl_eta



    def get_theta(self, eta, bows, times, sources): ## amortized inference
        """Returns the topic proportions.
        """
        eta_std = eta[sources.type('torch.LongTensor'), times.type('torch.LongTensor')] # D x K
        inp = torch.cat([bows, eta_std], dim=1)
        q_theta = self.q_theta(inp)

        if self.enc_drop > 0:
            q_theta = self.t_drop(q_theta)

        mu_theta = self.mu_q_theta(q_theta)
        logsigma_theta = self.logsigma_q_theta(q_theta)

        if (logsigma_theta > self.max_logsigma_t).sum() > 0:
            logsigma_theta[logsigma_theta > self.max_logsigma_t] = self.max_logsigma_t
        elif (logsigma_theta < self.min_logsigma_t).sum() > 0:
            logsigma_theta[logsigma_theta < self.min_logsigma_t] = self.min_logsigma_t        

        z = self.reparameterize(mu_theta, logsigma_theta)
        theta = F.softmax(z, dim=-1)
        kl_theta = self.get_kl(mu_theta, logsigma_theta, eta_std, torch.zeros(self.num_topics).to(device))
        return theta, kl_theta


    def get_beta(self, alpha):
        """Returns the topic matrix beta of shape K x V
        """
        if self.train_embeddings:            
            logit = self.rho(alpha)
        else:
            logit = torch.mm(alpha, self.rho.permute(1, 0)) 
        
        beta = F.softmax(logit, dim=-1)
        return beta 


    def get_nll(self, theta, beta, bows):        
        loglik = torch.log(torch.mm(theta, beta))
        nll = -loglik * bows        
        return nll.sum(-1)


    def get_prediction_loss(self, theta, labels):        

        # test code only
        # targets = torch.zeros(theta.size(0), self.num_labels)
        # for i in range(theta.size(0)):
        #     targets[i,labels[i].type('torch.LongTensor').item()] = 1
        # labels = targets

        outputs = self.classifier(theta)

        if self.multiclass_labels: # multi-class prediction loss as independent Bernoulli

            pred_loss = (-labels * F.log_softmax(outputs, dim=-1) - (1-labels) * torch.log(1-F.softmax(outputs, dim=-1))).sum()

        else: # single-label prediction
            
            pred_loss = self.criterion(outputs, labels.type('torch.LongTensor').to(device))

        return pred_loss    


    def forward(self, bows, normalized_bows, times, sources, labels, rnn_inp, num_docs):        

        bsz = normalized_bows.size(0)
        coeff = num_docs / bsz
        alpha, kl_alpha = self.get_alpha()
        
        eta, kl_eta = self.get_eta(rnn_inp)

        theta, kl_theta = self.get_theta(eta, normalized_bows, times, sources)
        kl_theta = kl_theta.sum() * coeff
        
        beta = self.get_beta(alpha)
        
        nll = self.get_nll(theta, beta, bows)

        nll = nll.sum() * coeff        

        pred_loss = torch.tensor(0.0)

        if self.predict_labels:
            pred_loss = self.get_prediction_loss(theta, labels) * coeff
            nelbo = nll + kl_alpha + kl_eta + kl_theta + pred_loss
        else:
            nelbo = nll + kl_alpha + kl_eta + kl_theta
        
        return nelbo, nll, kl_alpha, kl_eta, kl_theta, pred_loss


    def init_hidden(self):
        """Initializes the first hidden state of the RNN used as inference network for eta.
        """
        weight = next(self.parameters())
        nlayers = self.eta_nlayers
        nhid = self.eta_hidden_size
        return (weight.new_zeros(nlayers, self.num_sources, nhid), weight.new_zeros(nlayers, self.num_sources, nhid))





















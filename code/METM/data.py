import os
import random
import pickle
import numpy as np
import torch 
import scipy.io

def _fetch(path, name):
    if name == 'train':
        token_file = os.path.join(path, 'bow_tr_tokens.mat')
        count_file = os.path.join(path, 'bow_tr_counts.mat')
        country_file = os.path.join(path, 'bow_tr_countries.pkl')
    elif name == 'valid':
        token_file = os.path.join(path, 'bow_va_tokens.mat')
        count_file = os.path.join(path, 'bow_va_counts.mat')
        country_file = os.path.join(path, 'bow_va_countries.pkl')
    else:
        token_file = os.path.join(path, 'bow_ts_tokens.mat')
        count_file = os.path.join(path, 'bow_ts_counts.mat')
        country_file = os.path.join(path, 'bow_ts_countries.pkl')
    tokens = scipy.io.loadmat(token_file)['tokens'].squeeze()
    counts = scipy.io.loadmat(count_file)['counts'].squeeze()
    countries = pickle.load(open(country_file, "rb"))

    if name == 'test':
        token_1_file = os.path.join(path, 'bow_ts_h1_tokens.mat')
        count_1_file = os.path.join(path, 'bow_ts_h1_counts.mat')
        token_2_file = os.path.join(path, 'bow_ts_h2_tokens.mat')
        count_2_file = os.path.join(path, 'bow_ts_h2_counts.mat')
        country_1_file = os.path.join(path, 'bow_ts_h1_countries.pkl')
        country_2_file = os.path.join(path, 'bow_ts_h2_countries.pkl')
        tokens_1 = scipy.io.loadmat(token_1_file)['tokens'].squeeze()
        counts_1 = scipy.io.loadmat(count_1_file)['counts'].squeeze()
        tokens_2 = scipy.io.loadmat(token_2_file)['tokens'].squeeze()
        counts_2 = scipy.io.loadmat(count_2_file)['counts'].squeeze()

        countries_1 = pickle.load(open(country_1_file,"rb"))
        countries_2 = pickle.load(open(country_2_file,"rb"))

        return {'tokens': tokens, 'counts': counts, 'countries': countries, 
                    'tokens_1': tokens_1, 'counts_1': counts_1, 'countries_1': countries_1, 
                        'tokens_2': tokens_2, 'counts_2': counts_2, 'countries_2': countries_2}
    return {'tokens': tokens, 'counts': counts, 'countries': countries}

def get_data(path):
    with open(os.path.join(path, 'vocab.pkl'), 'rb') as f:
        vocab = pickle.load(f)

    train = _fetch(path, 'train')
    valid = _fetch(path, 'valid')
    test = _fetch(path, 'test')

    return vocab, train, valid, test

def get_batch(tokens, counts, countries, ind, vocab_size, device, emsize=300):
    """fetch input data by batch."""
    batch_size = len(ind)
    data_batch = np.zeros((batch_size, vocab_size))
    data_countries = []
    
    for i, doc_id in enumerate(ind):
        if len(countries[doc_id]) != 0:
            doc = tokens[doc_id]
            count = counts[doc_id]
            #print(countries[doc_id])
            data_countries.append(countries[doc_id])

        L = count.shape[1]
        if len(doc) == 1: 
            doc = [doc.squeeze()]
            count = [count.squeeze()]
        else:
            doc = doc.squeeze()
            count = count.squeeze()
        if doc_id != -1:
            for j, word in enumerate(doc):
                data_batch[i, word] = count[j]
    data_batch = torch.from_numpy(data_batch).float().to(device)
    return data_batch, data_countries
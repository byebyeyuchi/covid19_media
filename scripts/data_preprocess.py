# import necessary packages
import pandas as pd
import numpy as np
from sklearn.feature_extraction.text import CountVectorizer
#from sklearn.datasets import fetch_20newsgroups
import numpy as np
import pickle
import random
from scipy import sparse
import itertools
from scipy.io import savemat, loadmat
import re
import string
import os
from tqdm import tqdm
from sklearn.datasets.base import Bunch
import pickle as pkl
from argparse import ArgumentParser
from datetime import datetime #Add import

import fasttext

#Split is fixed
np.random.seed(0)

# Maximum / minimum document frequency
max_df = 0.7
min_df = 10  # choose desired value for min_df

def pickle_save(filename, data):
    with open(filename, "wb") as file:
        pickle.dump(data, file)

class Tokenizer:
    def __init__(self, verbose=False):
        self.verbose = verbose
        # self.use_cache = use_cache
        # self.save_cache = save_cache
        # self.cache_dir = cache_dir
        
        self.word_index = {}
        
        # if use_cache:
        #     if not os.path.exists(cache_dir):
        #         os.makedirs(cache_dir)
    
    def build_word_index(self, *args):
        """
        args: pandas series that we will use to build word index
        """
        
        print("Generating word index...", end=" ")
        for df in args:
            for sent in tqdm(df, disable=not self.verbose):
                for word in sent:
                    if word not in self.word_index:
                        self.word_index[word] = len(self.word_index)
        print("Done.")
    
    def prepare_sequence(self, seq):
        idxs = [self.word_index[w] for w in seq]
        return self.embedding_matrix[idxs], np.array(idxs)
    
    def build_embedding_matrix(self, path='fasttext_cache/crawl-300d-2M-subword.bin'):
        self.embedding_matrix = np.zeros((len(self.word_index), 300))
        ft_model = fasttext.load_model(path)

        for word, i in tqdm(self.word_index.items(), disable=not self.verbose):
            self.embedding_matrix[i] = ft_model.get_word_vector(word)

        return self.embedding_matrix

def get_args():
    parser = ArgumentParser()
    parser.add_argument("--data_file_path", type=str, default='gphin_all_countries/gphin_all_sources.csv')
    parser.add_argument("--stopwords_path", type=str, default='stops.txt')
    parser.add_argument("--save_dir", type=str, default='new_debug_results/')
    parser.add_argument('--who_flag',type=bool, default=False)
    parser.add_argument("--full_data", type=bool, default=False)
    return parser.parse_args()

def get_stopwords(stopwords_file=None):

    if len(stopwords_file) != 0:
        # Read in stopwords. Comment following two lines and uncomment the next 2 lines if you wish to use ntlk stopwords
        with open(stopwords_file, 'r') as f:
            stops = f.read().split('\n')
        return stops
    else:
        from nltk.corpus import stopwords
        stops_en = list(set(stopwords.words('english')))
        stops_fr = list(set(stopwords.words('french')))

        return stops_en


def read_data(data_file, who_flag=False, full_data=False):
    # Read data
    print('reading data...')
    print(data_file)
    gphin_data = pd.read_csv(data_file)
    #gphin_data = gphin_data.rename(columns={"COUNTRY /ORGANIZATION":"country"})

    timestamps = [] #Add timestamps array, not sure if we need this right now

    #Edit column of csv file to get all the timestamps in weeks:
    import calendar
    import numpy as np
    calendar.setfirstweekday(6) #First weekday is Sunday

    #Method to get week from date
    def get_week_of_month(year, month, day):
        x = np.array(calendar.monthcalendar(year, month))
        week_of_month = np.where(x==day)[0][0] + 1
        return(week_of_month) 

    # remove null values from data
    gphin_data = gphin_data[gphin_data['SUMMARY'].notna()]
    data_ids = gphin_data.index.values
    print(gphin_data.columns)
    if not full_data:
        #gphin_data.dropna(subset=['SOURCE', 'DATE ADDED'], inplace=True) #uncomment this and following 4 lines line if you're using WHO_all/GPHIN_all2
        # processing the country names by removing leading and trailing spaces and newlines
        # gphin_data['SOURCE'] = gphin_data['SOURCE'].apply(lambda x: x.strip(" "))
        # gphin_data['SOURCE'] = gphin_data['SOURCE'].apply(lambda x: x.lower())
        # gphin_data['country'] = gphin_data['SOURCE'].apply(lambda x: x.strip("\n"))
        gphin_data.dropna(subset=['SOURCE_TYPE', 'DATE ADDED'], inplace=True) #uncomment this line and next 4 lines if you're using WHO_all2
        gphin_data['SOURCE_TYPE'] = gphin_data['SOURCE_TYPE'].apply(lambda x: x.strip(" "))
        gphin_data['SOURCE_TYPE'] = gphin_data['SOURCE_TYPE'].apply(lambda x: x.lower())
        gphin_data['country'] = gphin_data['SOURCE_TYPE'].apply(lambda x: x.strip("\n"))

        # gphin_data.dropna(subset=['COUNTRY /ORGANIZATION', 'DATE ADDED'], inplace=True) #uncomment this and next 4 lines if you're using GPHIN_all
        # gphin_data['COUNTRY /ORGANIZATION'] = gphin_data['COUNTRY /ORGANIZATION'].apply(lambda x: x.strip(" "))
        # gphin_data['COUNTRY /ORGANIZATION'] = gphin_data['COUNTRY /ORGANIZATION'].apply(lambda x: x.lower())
        # gphin_data['country'] = gphin_data['COUNTRY /ORGANIZATION'].apply(lambda x: x.strip("\n"))

        # processing the timestamps by removing leading and trailing spaces and newlines
        gphin_data['DATE ADDED'] = gphin_data['DATE ADDED'].apply(lambda x: x.strip(" "))
        gphin_data['DATE ADDED'] = gphin_data['DATE ADDED'].apply(lambda x: x.strip("\n"))

        all_times = []

        #print('This is timestamps')
        #print(gphin_data.timestamps)
        #Updating gphin_data.timestamps to give weeks instead
        for timestamp in gphin_data['DATE ADDED']:
            try:
                d = datetime.strptime(timestamp, '%m/%d/%Y')
            except:
                try:
                    d = datetime.strptime(timestamp, '%d/%m/%Y')
                except:
                    t = timestamp[0:3]+timestamp[3:]
                    d = datetime.strptime(t.replace(':','').replace('--','-'), '%Y-%m-%d')
            #Get the week of the month
            week_month = get_week_of_month(d.year,d.month,d.day)
            
            #Original date
            original_date = '{}-{}-{}'.format(d.year,d.month,d.day)
            #Test file with original dates for gphin week data
            date_test = "Original Date (Y,M,D) -> {}, Week Date (Y,M,W) -> {}-0{}-{}    \n".format(original_date, d.isocalendar()[0], d.month, week_month) #Week number instead of days
            f = open("original_date_week_comparison.txt", "a")
            f.write(date_test)
            f.close()

            #Print month and date with week format (1-4)
            d = "{}-0{}-{}".format(d.isocalendar()[0], d.month, week_month) #Week number instead of days
            all_times.append(d)
        
        # converting list to array 


        gphin_data['timestamps'] = all_times 

        if who_flag:
            label_columns = ['WHO_MEASURE']
            label_map = {'Active case detection': 0, 'Adapting': 1, 'Cancelling, closing, restricting or adapting public gatherings outside the home': 2, 
            'Cancelling, restricting or adapting mass gatherings': 3, 'Cancelling, restricting or adapting private gatherings outside the home': 4, 
            'Cleaning and disinfecting surfaces and objects': 5, 'Closing': 6, 'Closing internal land borders': 7, 'Closing international land borders': 8, 
            'Coding required': 9, 'Contact tracing': 10, 'Entry screening and isolation or quarantine': 11, 'Exit screening and isolation or quarantine': 12, 
            'Financial packages': 13, 'General public awareness campaigns': 14, 'Isolation': 15, 'Legal and policy regulations': 16, 'Limiting face touching': 17, 
            'Not of interest': 18, 'Other': 19, 'Passive case detection': 20, 'Performing hand hygiene': 21, 'Performing respiratory etiquette': 22, 
            'Physical distancing': 23, 'Protecting displaced populations': 24, 'Protecting populations in closed settings': 25, 'Providing travel advice or warning': 26, 
            'Quarantine': 27, 'Restricting entry': 28, 'Restricting exit': 29, 'Restricting private gatherings at home': 30, 'Restricting visas': 31, 'Scaling up': 32, 
            'Shielding vulnerable groups': 33, 'Stay-at-home order': 34, 'Suspending or restricting international ferries or ships': 35, 'Suspending or restricting international flights': 36, 
            'Suspending or restricting movement': 37, 'Using antibodies for prevention': 38, 'Using medications for treatment': 39, 'Using other personal protective equipment': 40, 'Wearing a mask': 41}
        else:
            label_columns = ['LAND SCREENING','BORDER CLOSING','AIRPORT SCREENING: ENTRY','AIRPORT SCREENING: EXIT','TESTING & CASE DETECTION  ','QUARANTINE / MONITORING','TRAVEL ADVISORY','TRAVEL BAN / CANCELLATION',
            'TRADE BANS','EDUCATION CAMPAIGN','MASS GATHERING CANCELLATION','RESTRICTING OR LIMITING GATHERINGS','CLOSING PUBLIC PLACES','LOCKDOWN OR CURFEW','EASIND RESTRICTIONS','VACCINE/MCM DEPLOYED','PPE']
            label_map = {}
            for i,l in enumerate(label_columns):
                label_map[l] = i
        #print(label_map)

        # from the dataframe, store the data in the form of a dictionary with keys = ['data', 'country', 'index', 'timestamps']
        # In order to use some other feature, replace 'country' with the appropriate feature (column) in the dataset
        g_data = {'data':[], 'country':[], 'index':[], 'timestamps':[], 'labels':[]}
        countries = gphin_data.country.unique()
        countries_to_idx = {country: str(idx) for idx, country in enumerate(gphin_data.country.unique())}
        #print(gphin_data.columns)
        #exit()
        if who_flag:
            label_columns.append('WHO_ID')

        for country in tqdm(countries):
            summary = gphin_data[gphin_data.country == country].SUMMARY.values
            timestamp = gphin_data[gphin_data.country == country].timestamps.values #Check this in detail
            ind = gphin_data[gphin_data.country == country].index.values
            doc_label = gphin_data[gphin_data.country == country][label_columns]
            
            if who_flag:
                sub_data = gphin_data[gphin_data.country == country]
                summary = []
                index = []
                timestamps = []
                grps = sub_data.groupby('WHO_ID')
                c_labels = np.zeros([len(grps), len(label_map)])
                for i, grp in enumerate(grps):
                    labels = grp[1].WHO_MEASURE.values
                    summary.append(grp[1].SUMMARY.values[0])
                    timestamps.append(grp[1]['timestamps'].values[0])
                    index.append(grp[1].index.values[0])
                    for l in labels:
                        try:
                            c_labels[i][label_map[l]] = 1
                        except:
                            continue
                g_data['data'].extend(list(summary))
                g_data['country'].extend([country]*len(summary))
                g_data['index'].extend(list(index))
                g_data['timestamps'].extend(list(timestamps)) #Added timestamps in the g_data dictionary with key timestamps
                g_data['labels'].extend(list(c_labels))

            else:
                # sub_data = gphin_data[gphin_data.country == country]
                # summary = []
                # index = []
                # timestamps = []
                # #print(sub_data)
                # grps = sub_data.groupby('GPHIN ID')
                # c_labels = np.zeros([len(grps), len(label_map)])
                # for i, grp in enumerate(grps):
                #     labels = grp[1][label_columns]
                #     summary.append(grp[1].SUMMARY.values[0])
                #     timestamps.append(grp[1]['DATE ADDED'].values[0])
                #     index.append(grp[1].index.values[0])
                #     for i,l in labels.iterrows():
                #         labs = l[l=='x'].index.values
                #         for ll in labs:
                #             try:
                #                 print(label_map[ll])
                #                 c_labels[i][label_map[ll]] = 1
                #             except:
                #                 continue
                #     if str(1006889977) in grp[1]['GPHIN ID']:
                #         print(c_labels)
                #         exit()
                # g_data['data'].extend(list(summary))
                # g_data['country'].extend([country]*len(summary))
                # g_data['index'].extend(list(index))
                # g_data['timestamps'].extend(list(timestamps)) #Added timestamps in the g_data dictionary with key timestamps
                # g_data['labels'].extend(list(c_labels))                
                c_labels = np.zeros(doc_label.shape)
                #print(doc_label)
                for i, doc in enumerate(doc_label.values):
                    #try:
                    #cols = doc.columns
                    cols = doc_label.columns
                    indices = np.where(doc=='x')[0]
                    for j in indices:
                            ll =cols[j]
                            
                            l = label_map[ll]
                            c_labels[i][l] = 1
                        
                    #except:
                    #    continue
                #print(doc_label[doc_label.isin(['x'])])
                c_labels = list(c_labels)
                g_data['data'].extend(summary)
                g_data['country'].extend([country]*len(summary))
                g_data['index'].extend(ind)
                g_data['timestamps'].extend(timestamp) #Added timestamps in the g_data dictionary with key timestamps
                g_data['labels'].extend(c_labels)
    else:
        g_data = {'data':gphin_data.body.values, 'index':data_ids, 'timestamp':gphin_data.timestamps.values}
        countries_to_idx = {}

    print(len(g_data['data']))
    print(len(g_data['country']))
    print(len(g_data['index']))
    print(len(g_data['timestamps']))
    print(len(g_data['labels']))
    # randomly split data into train and test
        # 20% for testing
    test_num = int(np.ceil(0.2*len(g_data['data'])))
    test_ids = np.random.choice(range(len(g_data['data'])),test_num,replace=False)
    train_ids = np.array([i for i in range(len(g_data['data'])) if i not in test_ids])

    train_data_x = np.array(g_data['data'])[train_ids]
    train_data_ids = np.array(g_data['index'])[train_ids]
    train_data_labels = np.array(g_data['labels'])[train_ids]
    if not full_data:
        train_country = np.array(g_data['country'])[train_ids]
        train_timestamps = np.array(g_data['timestamps'])[train_ids]
    else:
        train_country = []
        train_timestamps = []

    test_data_x = np.array(g_data['data'])[test_ids]
    test_data_ids = np.array(g_data['index'])[test_ids]
    test_data_labels = np.array(g_data['labels'])[test_ids]
    if not full_data:
        test_country = np.array(g_data['country'])[test_ids]
        test_timestamps = np.array(g_data['timestamps'])[test_ids]
    else:
        test_country = []
        test_timestamps = []


    # print("train data x = " + str(len(train_data_x)))
    # print("train data labels = " + str(len(train_data_labels)))
    # print("test data x = " + str(len(test_data_x)))
    # print("test data labels = " + str(len(test_data_labels)))
    # convert the train and test data into Bunch format because rest of the code is designed for that
    train_data = Bunch(data=train_data_x, country=train_country, index=train_data_ids, timestamp=train_timestamps, labels=train_data_labels) 
    test_data = Bunch(data=test_data_x, country=test_country, index=test_data_ids, timestamp=test_timestamps, labels=test_data_labels)

    return train_data, test_data, countries_to_idx, label_map

# function checks for presence of any punctuation 
def contains_punctuation(w):
    return any(char in string.punctuation for char in w)

# function checks for presence of a numeral 
def contains_numeric(w):
    return any(char.isdigit() for char in w)

def preprocess(train_data, test_data, full_data):

    # remove all special characters from the text data
    print("Remove special characters")
    init_docs_tr = [re.findall(r'''[\w']+|[.,!?;-~{}`´_<=>:/@*()&'$%#"]''', train_data.data[doc]) for doc in range(len(train_data.data))]
    init_docs_ts = [re.findall(r'''[\w']+|[.,!?;-~{}`´_<=>:/@*()&'$%#"]''', test_data.data[doc]) for doc in range(len(test_data.data))]


    init_docs = init_docs_tr + init_docs_ts
    if not full_data:
        tr_countries = train_data.country
        ts_countries = test_data.country
        tr_timestamps = train_data.timestamp
        ts_timestamps = test_data.timestamp
        init_countries = np.append(tr_countries, ts_countries)
        init_timestamps = np.concatenate([tr_timestamps, ts_timestamps])
        data_ids = np.concatenate([train_data.index, test_data.index])
        data_labels = np.concatenate([train_data.labels, test_data.labels])
    else:
        init_countries = []
        init_timestamps = []
        data_ids = np.append(train_data.index, test_data.index)

    # prepare fasttext word embeddings
    tokenizer = Tokenizer(verbose=True)
    tokenizer.build_word_index(init_docs)
    tokenizer.build_embedding_matrix()
    init_docs_embs, init_docs_embs_idxs = [], []
    for doc in tqdm(init_docs):
        embs, embs_idxs = tokenizer.prepare_sequence(doc)
        init_docs_embs.append(embs)
        init_docs_embs_idxs.append(embs_idxs)

    # remove punctuations
    print("Remove punctuations")
    init_docs = [[w.lower() for w in init_docs[doc] if not contains_punctuation(w)] for doc in range(len(init_docs))]

    # remove special characters
    #init_docs = [''.join(e for e in doc if e.isalnum()) for doc in init_docs]
    
    # remove numbers
    print("Remove numbers")
    init_docs = [[w for w in init_docs[doc] if not contains_numeric(w)] for doc in range(len(init_docs))]
    # remove single letter words
    print("Remove single letter words")
    init_docs = [[w for w in init_docs[doc] if len(w)>1] for doc in range(len(init_docs))]
    init_docs = [" ".join(init_docs[doc]) for doc in range(len(init_docs))]

    return init_docs, init_docs_tr, init_docs_ts, init_countries, data_ids, init_timestamps, data_labels, init_docs_embs, init_docs_embs_idxs


def get_features(init_timestamps, init_docs, stops, min_df=min_df, max_df=max_df):

    # Create count vectorizer
    print('counting document frequency of words...')
    cvectorizer = CountVectorizer(min_df=min_df, max_df=max_df, stop_words=stops)
    cvz = cvectorizer.fit_transform(init_docs).sign()
    #print("Size of documents to check if french is included = " + str(len(init_docs)))

    # Get vocabulary
    print('building the vocabulary...')
    sum_counts = cvz.sum(axis=0)
    v_size = sum_counts.shape[1]
    sum_counts_np = np.zeros(v_size, dtype=int)
    for v in range(v_size):
        sum_counts_np[v] = sum_counts[0,v]
    word2id = dict([(w, cvectorizer.vocabulary_.get(w)) for w in cvectorizer.vocabulary_])
    id2word = dict([(cvectorizer.vocabulary_.get(w), w) for w in cvectorizer.vocabulary_])
    del cvectorizer
    print('  initial vocabulary size: {}'.format(v_size))

    #print(word2id.keys())
    # Sort elements in vocabulary
    idx_sort = np.argsort(sum_counts_np)
    vocab_aux = [id2word[idx_sort[cc]] for cc in range(v_size)]


    # Filter out stopwords (if any)
    vocab_aux = [w for w in vocab_aux if w not in stops]
    #vocab_aux = [w for w in vocab_aux if w not in stops_fr]
    print('  vocabulary size after removing stopwords from list: {}'.format(len(vocab_aux)))


    # Create dictionary and inverse dictionary
    vocab = vocab_aux
    del vocab_aux
    word2id = dict([(w, j) for j, w in enumerate(vocab)])
    id2word = dict([(j, w) for j, w in enumerate(vocab)])

    # Create mapping of timestamps
    #print(init_timestamps)
    #exit()
    all_times = sorted(set(init_timestamps))
    #print(len(set(init_timestamps)))
    #exit()
    time2id = dict([(t, i) for i, t in enumerate(all_times)])
    id2time = dict([(i, t) for i, t in enumerate(all_times)])
    time_list = [id2time[i] for i in range(len(all_times))]

    return vocab, word2id, id2word, time2id, id2time, time_list

def remove_empty(in_docs, in_labels, in_ids):
    preserve_idxs = [idx for idx, doc in enumerate(in_docs) if doc!=[]]
    docs = [doc for doc in in_docs if doc!=[]]
    labels = [label for (doc, label) in zip(in_docs, in_labels) if doc!=[]]
    ids = [id for (doc, id) in zip(in_docs, in_ids) if doc!=[]]
    return docs, labels, ids, preserve_idxs

def create_doc_indices(in_docs):
    aux = [[j for i in range(len(doc))] for j, doc in enumerate(in_docs)]
    return [int(x) for y in aux for x in y]

def create_bow(doc_indices, words, n_docs, vocab_size):
    return sparse.coo_matrix(([1]*len(doc_indices),(doc_indices, words)), shape=(n_docs, vocab_size)).tocsr()

def create_list_words(in_docs):
    return [x for y in in_docs for x in y]

def split_bow(bow_in, n_docs):
    indices = [[w for w in bow_in[doc,:].indices] for doc in range(n_docs)]
    counts = [[c for c in bow_in[doc,:].data] for doc in range(n_docs)]
    return np.array(indices), np.array(counts)



def split_data(init_docs, init_docs_tr, init_docs_ts, word2id, init_countries, init_ids, full_data, init_timestamps, data_labels, source_map, all_docs_embs, all_docs_embs_idxs):

    # Split in train/test/valid
    print('tokenizing documents and splitting into train/test/valid...')
    num_docs_tr = len(init_docs_tr)
    trSize = num_docs_tr-100
    tsSize = len(init_docs_ts)
    vaSize = 100
    idx_permute = np.random.permutation(num_docs_tr).astype(int)
    print("idx permute:")
    print(idx_permute)


    # Remove words not in train_data
    vocab = list(set([w for idx_d in range(trSize) for w in init_docs[idx_permute[idx_d]].split() if w in word2id]))
    word2id = dict([(w, j) for j, w in enumerate(vocab)])
    id2word = dict([(j, w) for j, w in enumerate(vocab)])
    print('  vocabulary after removing words not in train: {}'.format(len(vocab)))


    # Split in train/test/valid
    docs_tr = [[word2id[w] for w in init_docs[idx_permute[idx_d]].split() if w in word2id] for idx_d in range(trSize)]
    docs_embs_tr = [all_docs_embs[idx_permute[idx_d]] for idx_d in range(trSize)]
    docs_embs_idxs_tr = [all_docs_embs_idxs[idx_permute[idx_d]] for idx_d in range(trSize)]
    # create list of unseen idxs in trainning set
    embs_idxs_seen = set(idx for docs_embs_idx_tr in docs_embs_idxs_tr for idx in docs_embs_idx_tr)
    print("q_theta vocab size", len(embs_idxs_seen))

    timestamps_tr = [time2id[init_timestamps[idx_permute[idx_d]]] for idx_d in range(trSize)]
    if not full_data:
        countries_tr = [source_map[init_countries[idx_permute[idx_d]]] for idx_d in range(trSize)]
        #ids_tr = [init_ids[idx_permute[idx_d]] for id_x in range(trSize)]
    else:
        countries_tr = []
        timestamps_tr = []
        #ids_tr = []
    ids_tr = [init_ids[idx_permute[idx_d]] for idx_d in range(trSize)]
    labels_tr = [data_labels[idx_permute[idx_d]] for idx_d in range(trSize)]

    docs_va = [[word2id[w] for w in init_docs[idx_permute[idx_d+trSize]].split() if w in word2id] for idx_d in range(vaSize)]
    docs_embs_va = [all_docs_embs[idx_permute[idx_d+trSize]] for idx_d in range(vaSize)]
    docs_embs_idxs_va = [all_docs_embs_idxs[idx_permute[idx_d+trSize]] for idx_d in range(vaSize)]
    for doc_idx, docs_embs_idx_va in tqdm(enumerate(docs_embs_idxs_va)):
        mask = [emb_idx in embs_idxs_seen for emb_idx in docs_embs_idx_va]
        docs_embs_idxs_va[doc_idx] = np.array(list(itertools.compress(docs_embs_idx_va, mask)))
        docs_embs_va[doc_idx] = np.array(list(itertools.compress(docs_embs_va[doc_idx], mask)))
    timestamps_va = [time2id[init_timestamps[idx_permute[idx_d+trSize]]] for idx_d in range(vaSize)]
    if not full_data:
        countries_va = [source_map[init_countries[idx_permute[idx_d+trSize]]] for idx_d in range(vaSize)]
        #ids_va = [init_ids[idx_permute[idx_d+trSize]] for idx_d in range(vaSize)]
    else:
        countries_va = []
        timestamps_va = []
        #ids_va = []
    ids_va = [init_ids[idx_permute[idx_d+trSize]] for idx_d in range(vaSize)]
    labels_va = [data_labels[idx_permute[idx_d+trSize]] for idx_d in range(vaSize)]


    docs_ts = [[word2id[w] for w in init_docs[idx_d+num_docs_tr].split() if w in word2id] for idx_d in range(tsSize)]
    docs_embs_ts = [all_docs_embs[idx_d+num_docs_tr] for idx_d in range(tsSize)]
    docs_embs_idxs_ts = [all_docs_embs_idxs[idx_d+num_docs_tr] for idx_d in range(tsSize)]
    for doc_idx, docs_embs_idx_ts in tqdm(enumerate(docs_embs_idxs_ts)):
        mask = [emb_idx in embs_idxs_seen for emb_idx in docs_embs_idx_ts]
        docs_embs_idxs_ts[doc_idx] = np.array(list(itertools.compress(docs_embs_idx_ts, mask)))
        docs_embs_ts[doc_idx] = np.array(list(itertools.compress(docs_embs_ts[doc_idx], mask)))
    print(len(docs_ts))
    #exit()
    timestamps_ts = [time2id[init_timestamps[idx_d+num_docs_tr]] for idx_d in range(tsSize)]
    if not full_data:
        countries_ts = [source_map[init_countries[idx_d+num_docs_tr]] for idx_d in range(tsSize)]
        #ids_ts = [init_ids[idx_d+num_docs_tr] for idx_d in range(tsSize)]
    else:
        countries_ts = []
        timestamps_ts = []
        #ids_ts = []

    print('len(data_labels)='+str(len(data_labels)))
    print("len(init_ids)="+str(len(init_ids)))
    ids_ts = [init_ids[idx_d+num_docs_tr] for idx_d in range(tsSize)]
    labels_ts = [data_labels[idx_d+num_docs_tr] for idx_d in range(tsSize)]


    # Remove empty documents
    print('removing empty documents...')



    docs_tr, labels_tr, ids_tr, preserve_idxs_tr = remove_empty(docs_tr, labels_tr, ids_tr)
    docs_ts, labels_ts, ids_ts, preserve_idxs_ts = remove_empty(docs_ts, labels_ts, ids_ts)
    docs_va, labels_va, ids_va, preserve_idxs_va = remove_empty(docs_va, labels_va, ids_va)

    docs_embs_tr = [docs_embs_tr[idx] for idx in preserve_idxs_tr]
    docs_embs_idxs_tr = [docs_embs_idxs_tr[idx] for idx in preserve_idxs_tr]
    docs_embs_ts = [docs_embs_ts[idx] for idx in preserve_idxs_ts]
    docs_embs_idxs_ts = [docs_embs_idxs_ts[idx] for idx in preserve_idxs_ts]
    docs_embs_va = [docs_embs_va[idx] for idx in preserve_idxs_va]
    docs_embs_idxs_va = [docs_embs_idxs_va[idx] for idx in preserve_idxs_va]

    # Remove test documents with length=1
    preserve_idxs_ts = [idx for idx, doc in enumerate(docs_ts) if len(doc)>1]
    docs_ts = [doc for doc in docs_ts if len(doc)>1]
    labels_ts = [lab for doc,lab in zip(docs_ts, labels_ts) if len(doc) > 1]
    id_ts = [id for doc, id in zip(docs_ts, ids_ts) if len(doc) > 1]
    docs_embs_ts = [docs_embs_ts[idx] for idx in preserve_idxs_ts]
    docs_embs_idxs_ts = [docs_embs_idxs_ts[idx] for idx in preserve_idxs_ts]

    print('  number of documents (train): {} [this should be equal to {}]'.format(len(docs_tr), trSize))
    print('  number of documents (test): {} [this should be equal to {}]'.format(len(docs_ts), tsSize))
    print('  number of documents (valid): {} [this should be equal to {}]'.format(len(docs_va), vaSize))

    print('  number of labels (train): {} [this should be equal to {}]'.format(len(labels_tr), trSize))
    print('  number of labels (test): {} [this should be equal to {}]'.format(len(labels_ts), tsSize))
    print('  number of labels (valid): {} [this should be equal to {}]'.format(len(labels_va), vaSize))


    # Split test set in 2 halves
    print('splitting test documents in 2 halves...')
    docs_ts_h1 = [[w for i,w in enumerate(doc) if i<=len(doc)/2.0-1] for doc in docs_ts]
    docs_ts_h2 = [[w for i,w in enumerate(doc) if i>len(doc)/2.0-1] for doc in docs_ts]
    docs_embs_ts_h1 = [doc_embs[: int(np.floor(doc_embs.shape[0]/2.0-1))] for doc_embs in docs_embs_ts]
    docs_embs_idxs_ts_h1 = [doc_embs[: int(np.floor(doc_embs.shape[0]/2.0-1))] for doc_embs in docs_embs_idxs_ts]
    docs_embs_ts_h2 = [doc_embs[int(np.ceil(doc_embs.shape[0]/2.0-1)): ] for doc_embs in docs_embs_ts]
    docs_embs_idxs_ts_h2 = [doc_embs[int(np.ceil(doc_embs.shape[0]/2.0-1)): ] for doc_embs in docs_embs_idxs_ts]
    if not full_data:
        countries_ts_h1 = [[c for i,w in enumerate(doc) if i<=len(doc)/2.0-1] for doc,c in zip(docs_ts,countries_ts)]
        countries_ts_h2 = [[c for i,w in enumerate(doc) if i>len(doc)/2.0-1] for doc,c in zip(docs_ts,countries_ts)]
        timestamps_ts_h1 = [[c for i,w in enumerate(doc) if i<=len(doc)/2.0-1] for doc,c in zip(docs_ts,timestamps_ts)]
        timestamps_ts_h2 = [[c for i,w in enumerate(doc) if i>len(doc)/2.0-1] for doc,c in zip(docs_ts,timestamps_ts)]
        labels_ts_h1 = [[c for i,w in enumerate(doc) if i<=len(doc)/2.0-1] for doc,c in zip(docs_ts,labels_ts)]
        labels_ts_h2 = [[c for i,w in enumerate(doc) if i>len(doc)/2.0-1] for doc,c in zip(docs_ts,labels_ts)]
    else:
        countries_ts_h1 = []
        countries_ts_h2 = []
        timestamps_ts_h1 = []
        timestamps_ts_h2 = []


    # Getting lists of words and doc_indices
    print('creating lists of words...')

    words_tr = create_list_words(docs_tr)
    words_ts = create_list_words(docs_ts)
    words_ts_h1 = create_list_words(docs_ts_h1)
    words_ts_h2 = create_list_words(docs_ts_h2)
    words_va = create_list_words(docs_va)

    print('  len(words_tr): ', len(words_tr))
    print('  len(words_ts): ', len(words_ts))
    print('  len(words_ts_h1): ', len(words_ts_h1))
    print('  len(words_ts_h2): ', len(words_ts_h2))
    print('  len(words_va): ', len(words_va))

    # Get doc indices
    print('getting doc indices...')

    doc_indices_tr = create_doc_indices(docs_tr)
    doc_indices_ts = create_doc_indices(docs_ts)
    doc_indices_ts_h1 = create_doc_indices(docs_ts_h1)
    doc_indices_ts_h2 = create_doc_indices(docs_ts_h2)
    doc_indices_va = create_doc_indices(docs_va)


    print('  len(np.unique(doc_indices_tr)): {} [this should be {}]'.format(len(np.unique(doc_indices_tr)), len(docs_tr)))
    print('  len(np.unique(doc_indices_ts)): {} [this should be {}]'.format(len(np.unique(doc_indices_ts)), len(docs_ts)))
    print('  len(np.unique(doc_indices_ts_h1)): {} [this should be {}]'.format(len(np.unique(doc_indices_ts_h1)), len(docs_ts_h1)))
    print('  len(np.unique(doc_indices_ts_h2)): {} [this should be {}]'.format(len(np.unique(doc_indices_ts_h2)), len(docs_ts_h2)))
    print('  len(np.unique(doc_indices_va)): {} [this should be {}]'.format(len(np.unique(doc_indices_va)), len(docs_va)))


    # Number of documents in each set
    n_docs_tr = len(docs_tr)
    n_docs_ts = len(docs_ts)
    n_docs_ts_h1 = len(docs_ts_h1)
    n_docs_ts_h2 = len(docs_ts_h2)
    n_docs_va = len(docs_va)

    # Remove unused variables
    del docs_tr
    del docs_ts
    del docs_ts_h1
    del docs_ts_h2
    del docs_va


    # Create bow representation
    print('creating bow representation...')

    bow_tr = create_bow(doc_indices_tr, words_tr, n_docs_tr, len(vocab))
    bow_ts = create_bow(doc_indices_ts, words_ts, n_docs_ts, len(vocab))
    bow_ts_h1 = create_bow(doc_indices_ts_h1, words_ts_h1, n_docs_ts_h1, len(vocab))
    bow_ts_h2 = create_bow(doc_indices_ts_h2, words_ts_h2, n_docs_ts_h2, len(vocab))
    bow_va = create_bow(doc_indices_va, words_va, n_docs_va, len(vocab))


    del words_tr
    del words_ts
    del words_ts_h1
    del words_ts_h2
    del words_va
    del doc_indices_tr
    del doc_indices_ts
    del doc_indices_ts_h1
    del doc_indices_ts_h2
    del doc_indices_va

    return bow_tr, n_docs_tr, bow_ts, n_docs_ts, bow_ts_h1, n_docs_ts_h1, bow_ts_h2, n_docs_ts_h2, bow_va, n_docs_va, vocab, countries_tr, countries_ts, countries_ts_h1, countries_ts_h2, countries_va, ids_tr, ids_va, ids_ts, timestamps_tr, timestamps_ts, timestamps_ts_h1, timestamps_ts_h2, timestamps_va, labels_tr, labels_ts, labels_ts_h1, labels_ts_h2, labels_va, \
        docs_embs_tr, docs_embs_idxs_tr, docs_embs_ts, docs_embs_idxs_ts, docs_embs_va, docs_embs_idxs_va, docs_embs_ts_h1, docs_embs_idxs_ts_h1, docs_embs_ts_h2, docs_embs_idxs_ts_h2

# Write files for LDA C++ code
def write_lda_file(filename, timestamps_in, time_list_in, bow_in):
    idxSort = np.argsort(timestamps_in)
    
    with open(filename, "w") as f:
        for row in idxSort:
            x = bow_in.getrow(row)
            n_elems = x.count_nonzero()
            f.write(str(n_elems))
            if(n_elems != len(x.indices) or n_elems != len(x.data)):
                raise ValueError("[ERR] THIS SHOULD NOT HAPPEN")
            for ii, dd in zip(x.indices, x.data):
                f.write(' ' + str(ii) + ':' + str(dd))
            f.write('\n')
            
    with open(filename.replace("-mult", "-seq"), "w") as f:
        f.write(str(len(time_list_in)) + '\n')
        for idx_t, _ in enumerate(time_list_in):
            n_elem = len([t for t in timestamps_in if t==idx_t])
            f.write(str(n_elem) + '\n')

def save_data(save_dir, vocab, bow_tr, n_docs_tr, bow_ts, n_docs_ts, bow_ts_h1, n_docs_ts_h1, bow_ts_h2, n_docs_ts_h2, bow_va, n_docs_va, 
    countries_tr, countries_ts, countries_ts_h1, countries_ts_h2, countries_va, countries_to_idx, ids_tr, ids_va, ids_ts, full_data, 
    timestamps_tr, timestamps_ts, timestamps_ts_h1, timestamps_ts_h2, timestamps_va, time_list,
    labels_tr, labels_ts, labels_ts_h1, labels_ts_h2, labels_va, label_map, id2word, id2time, 
    docs_embs_tr, docs_embs_idxs_tr, docs_embs_ts, docs_embs_idxs_ts, docs_embs_va, docs_embs_idxs_va, docs_embs_ts_h1, docs_embs_idxs_ts_h1, docs_embs_ts_h2, docs_embs_idxs_ts_h2):

    # Write the vocabulary to a file
    path_save = save_dir + 'min_df_' + str(min_df) + '/'
    if not os.path.isdir(path_save):
        os.system('mkdir -p ' + path_save)

    pickle_save(path_save + 'vocab.pkl', vocab)
    del vocab

    with open(path_save+"vocab_map.txt","w") as f:
        for i,w in id2word.items():
            f.write(str(i)+" : " + str(w)+"\n")
        f.close()
    pickle_save(path_save+"vocab_map.pkl", id2word)
 
    with open(path_save + 'timestamps.txt', "w") as f:
        for t in time_list:
            f.write(str(t) + '\n')

    pickle_save(path_save + 'timestamps.pkl', time_list)
    
    with open(path_save+"times_map.pkl","wb") as f:
        pkl.dump(id2time, f)

    with open(path_save+"times_map.txt","w") as f:
        for i,v in id2time.items():
            f.write(str(i)+" : " + str(v) +"\n")
        f.close()

    print("Saving q_theta embeddings ...", end=" ")
    # save fasttext embeddings
    pickle_save(os.path.join(path_save, "embs_train.pkl"), docs_embs_tr)
    pickle_save(os.path.join(path_save, "embs_valid.pkl"), docs_embs_va)
    pickle_save(os.path.join(path_save, "embs_test.pkl"), docs_embs_ts)
    pickle_save(os.path.join(path_save, "embs_test_h1.pkl"), docs_embs_ts_h1)
    pickle_save(os.path.join(path_save, "embs_test_h2.pkl"), docs_embs_ts_h2)
    print("Done")

    del docs_embs_tr
    del docs_embs_va
    del docs_embs_ts
    del docs_embs_ts_h1
    del docs_embs_ts_h2

    print("Saving q_theta 1-hot embeddings ...", end=" ")
    # save one hot embeddings (for q_theta)
    pickle_save(os.path.join(path_save, "idxs_embs_train.pkl"), docs_embs_idxs_tr)
    pickle_save(os.path.join(path_save, "idxs_embs_valid.pkl"), docs_embs_idxs_va)
    pickle_save(os.path.join(path_save, "idxs_embs_test.pkl"), docs_embs_idxs_ts)
    pickle_save(os.path.join(path_save, "idxs_embs_test_h1.pkl"), docs_embs_idxs_ts_h1)
    pickle_save(os.path.join(path_save, "idxs_embs_test_h2.pkl"), docs_embs_idxs_ts_h2)
    print("Done")

    del docs_embs_idxs_tr
    del docs_embs_idxs_va
    del docs_embs_idxs_ts
    del docs_embs_idxs_ts_h1
    del docs_embs_idxs_ts_h2
    
    # all countries
    if not full_data:
        pkl.dump(countries_to_idx, open(path_save + 'sources_map.pkl',"wb"))

    with open(path_save+"sources_map.txt","w") as f:
        for i,v in countries_to_idx.items():
            f.write(str(i)+" : " + str(v)+"\n")
        del countries_to_idx

    # Split bow intro token/value pairs
    print('splitting bow intro token/value pairs and saving to disk...')

    bow_tr_tokens, bow_tr_counts = split_bow(bow_tr, n_docs_tr)

    pickle_save(os.path.join(path_save, 'bow_tr_tokens.pkl'), np.array(bow_tr_tokens))
    pickle_save(os.path.join(path_save, 'bow_tr_counts.pkl'), np.array(bow_tr_counts))
   

    if not full_data:
        pkl.dump(countries_tr, open(path_save + 'bow_tr_sources.pkl',"wb"))
        pickle_save(os.path.join(path_save, 'bow_tr_timestamps.pkl'), np.array(timestamps_tr))
    pkl.dump(ids_tr, open(path_save + 'bow_tr_ids.pkl',"wb"))
    #savemat(path_save+"bow_tr_labels.mat",{'labels':labels_tr},do_compression=True)
    pickle.dump(labels_tr, open(path_save+"bow_tr_labels.pkl","wb"))

    del bow_tr
    del bow_tr_tokens
    del bow_tr_counts

    bow_ts_tokens, bow_ts_counts = split_bow(bow_ts, n_docs_ts)
    pickle_save(os.path.join(path_save, 'bow_ts_tokens.pkl'), np.array(bow_ts_tokens))
    pickle_save(os.path.join(path_save, 'bow_ts_counts.pkl'), np.array(bow_ts_counts))
    #savemat(path_save + 'bow_ts_countries.mat', {'countries': countries_ts}, do_compression=True)
    if not full_data:
        pkl.dump(countries_ts, open(path_save + 'bow_ts_sources.pkl',"wb"))
        pickle_save(os.path.join(path_save, 'bow_ts_timestamps.pkl'), np.array(timestamps_ts))
    pkl.dump(ids_ts, open(path_save + 'bow_ts_ids.pkl',"wb"))
    #savemat(path_save+"bow_ts_labels.mat",{'labels':labels_ts},do_compression=True)
    pickle.dump(labels_ts, open(path_save+"bow_ts_labels.pkl","wb"))

    del bow_ts
    del bow_ts_tokens
    del bow_ts_counts


    bow_ts_h1_tokens, bow_ts_h1_counts = split_bow(bow_ts_h1, n_docs_ts_h1)
    pickle_save(os.path.join(path_save, 'bow_ts_h1_tokens.pkl'), np.array(bow_ts_h1_tokens))
    pickle_save(os.path.join(path_save, 'bow_ts_h1_counts.pkl'), np.array(bow_ts_h1_counts))
    #savemat(path_save + 'bow_ts_h1_countries.mat', {'countries': countries_ts_h1}, do_compression=True)
    if not full_data:
        pkl.dump(countries_ts_h1, open(path_save + 'bow_ts_h1_sources.pkl',"wb"))
        pickle_save(os.path.join(path_save, 'bow_va_timestamps.pkl'), np.array(timestamps_va))
    #savemat(path_save+"bow_ts_h1_labels.mat",{'labels':labels_ts_h1},do_compression=True)
    pickle.dump(labels_ts_h1, open(path_save+"bow_ts_h1_labels.pkl","wb"))

    del bow_ts_h1
    del bow_ts_h1_tokens
    del bow_ts_h1_counts

    bow_ts_h2_tokens, bow_ts_h2_counts = split_bow(bow_ts_h2, n_docs_ts_h2)
    pickle_save(os.path.join(path_save, 'bow_ts_h2_tokens.pkl'), np.array(bow_ts_h2_tokens))
    pickle_save(os.path.join(path_save, 'bow_ts_h2_counts.pkl'), np.array(bow_ts_h2_counts))
    #savemat(path_save + 'bow_ts_h2_countries.mat', {'countries': countries_ts_h2}, do_compression=True)
    if not full_data:
        pickle.dump(countries_ts_h2, open(path_save + 'bow_ts_h2_sources.pkl',"wb"))
        pickle.dump(timestamps_ts_h2, open(path_save + 'bow_ts_h2_timestamps.pkl',"wb"))
    pickle.dump(labels_ts_h2, open(path_save+"bow_ts_h2_labels.pkl","wb"))
    #savemat(path_save+"bow_ts_h2_labels.mat",{'labels':labels_ts_h2},do_compression=True)

    del bow_ts_h2
    del bow_ts_h2_tokens
    del bow_ts_h2_counts


    bow_va_tokens, bow_va_counts = split_bow(bow_va, n_docs_va)
    pickle_save(os.path.join(path_save, 'bow_va_tokens.pkl'), np.array(bow_va_tokens))
    pickle_save(os.path.join(path_save, 'bow_va_counts.pkl'), np.array(bow_va_counts))
    #savemat(path_save + 'bow_va_countries.mat', {'countries': countries_va}, do_compression=True)
    if not full_data:
        pickle.dump(countries_va, open(path_save + 'bow_va_sources.pkl',"wb"))
        pickle.dump(timestamps_va, open(path_save + 'bow_va_timestamps.pkl',"wb"))
    pickle.dump(ids_va, open(path_save + 'bow_va_ids.pkl','wb'))
    pickle.dump(labels_va, open(path_save+"bow_va_labels.pkl","wb"))
    #savemat(path_save+"bow_va_labels.mat",{'labels':labels_va},do_compression=True)

    del bow_va
    del bow_va_tokens
    del bow_va_counts

    pickle.dump(label_map, open(path_save+"labels_map.pkl","wb"))
    f = open(path_save+"labels_map.txt","w")
    for i,v in label_map.items():
        f.write(str(i)+" : " + str(v) +"\n")
    f.close()
    print('Data ready !!')
    print('*************')


if __name__ == '__main__':
    
    args = get_args()

    # read in the data file
    print("Read in data file...\n")
    train, test, countries_to_idx, label_map = read_data(args.data_file_path, args.who_flag, args.full_data)

    # preprocess the news articles
    print("Preprocessing the articles")
    #print(train.data)
    all_docs, train_docs, test_docs, init_countries, init_ids, init_timestamps, data_labels, all_docs_embs, all_docs_embs_idxs = preprocess(train, test, args.full_data)

    # get a list of stopwords
    #stopwords_en, stopwords_fr = get_stopwords(args.stopwords_path)
    stopwords = get_stopwords(args.stopwords_path)

    # get the vocabulary of words, word2id map and id2word map
    print("\nGetting features..\n")
    vocab, word2id, id2word, time2id, id2time, time_list = get_features(init_timestamps, all_docs, stopwords)

    # split data into train, test and validation and corresponding countries in BOW format
    print("Splitting data..\n")
    bow_tr, n_docs_tr, bow_ts, n_docs_ts, bow_ts_h1, n_docs_ts_h1, bow_ts_h2, n_docs_ts_h2, bow_va, n_docs_va, vocab, c_tr, c_ts, c_ts_h1, c_ts_h2, c_va, ids_tr, ids_va, ids_ts, timestamps_tr, timestamps_ts, timestamps_ts_h1, timestamps_ts_h2, timestamps_va, labels_tr, labels_ts, labels_ts_h1, labels_ts_h2, labels_va, \
        docs_embs_tr, docs_embs_idxs_tr, docs_embs_ts, docs_embs_idxs_ts, docs_embs_va, docs_embs_idxs_va, docs_embs_ts_h1, docs_embs_idxs_ts_h1, docs_embs_ts_h2, docs_embs_idxs_ts_h2 \
        = split_data(all_docs, train_docs, test_docs, word2id, init_countries, init_ids, args.full_data, init_timestamps, data_labels, countries_to_idx, all_docs_embs, all_docs_embs_idxs)

    print("Saving data..\n")
    save_data(args.save_dir, vocab, bow_tr, n_docs_tr, bow_ts, n_docs_ts, bow_ts_h1, n_docs_ts_h1, bow_ts_h2, n_docs_ts_h2, bow_va, n_docs_va, c_tr, c_ts, c_ts_h1, c_ts_h2, c_va, countries_to_idx, ids_tr, ids_va, ids_ts, args.full_data, timestamps_tr, timestamps_ts, timestamps_ts_h1, timestamps_ts_h2, timestamps_va, time_list, labels_tr, labels_ts, labels_ts_h1, labels_ts_h2, labels_va, label_map, id2word, id2time, \
        docs_embs_tr, docs_embs_idxs_tr, docs_embs_ts, docs_embs_idxs_ts, docs_embs_va, docs_embs_idxs_va, docs_embs_ts_h1, docs_embs_idxs_ts_h1, docs_embs_ts_h2, docs_embs_idxs_ts_h2)
#!/bin/bash

CUDA_VISIBLE_DEVICES=9 python main.py \
    --mode train \
    --dataset "GPHIN" \
    --data_path data/GPHIN/ \
    --emb_path data/skipgram_emb_300d.txt \
    --save_path ./results \
    --lr 1e-3 \
    --clip 2 \
    --enc_drop 0.1 \
    --eta_dropout 0.1 \
    --epochs 100 \
    --num_topics 50 \
    --batch_size 64 \
    --min_df 10 \
    --eta_nlayers 3 \
    --eta_hidden_size 512 \
    --t_hidden_size 512 \
    --eval_batch_size 100 \

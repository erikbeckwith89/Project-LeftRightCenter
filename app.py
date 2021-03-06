import json
import re
from datetime import datetime
from keras.models import load_model
from keras import backend as K

import tensorflow as tf
from keras.models import Sequential
from keras.utils import to_categorical
from keras.layers import Dense
import numpy as np
import pandas as pd
import requests
import tweepy
from flask import Flask, jsonify, redirect, render_template, request

from config import (access_token, access_token_secret, consumer_key,
                    consumer_secret, x_api_key, x_api_secret_key)

# Setup Tweepy API Authentication
auth = tweepy.OAuthHandler(consumer_key, consumer_secret)
auth.set_access_token(access_token, access_token_secret)
api = tweepy.API(auth, parser=tweepy.parsers.JSONParser())
url='https://api-v3.receptiviti.com/v3/api/content'
headers={'X-API-KEY': x_api_key, 'X-API-SECRET-KEY':x_api_secret_key}

model = None
graph = None

app = Flask(__name__)

algoNameMap = {}
algoNameMap['NeuralNet- Raw Score'] = {'model_name':'liwc_raw_scores_full', 'model_index':0,'columns':[]}
algoNameMap['NeuralNet- Raw Score - Big5'] = {'model_name':'liwc_raw_scores_full_big5', 'model_index':0,'columns':['openness','conscientiousness','extraversion','agreeableness','neuroticism']}
algoNameMap['NeuralNet- Raw Score - Aggressive'] = {'model_name':'liwc_raw_scores_full_aggressive', 'model_index':0,'columns':['aggressive']}
algoNameMap['NeuralNet- Percentile Score'] = {'model_name':'liwc_percentile_scores_full', 'model_index':1,'columns':[]}
algoNameMap['NeuralNet- Categorical Score'] = {'model_name':'liwc_categorical_scores_full', 'model_index':2,'columns':[]}
algoNameMap['NeuralNet- Categorical Score - Top5'] = {'model_name':'liwc_categorical_scores_full_top5', 'model_index':2,'columns':['cogproc','function','relativ','verb','social']}




def payload(text):
    payload = {}
    tags = []
    tags.append('string')
    payload['content_tags'] = tags
    payload['content_handle'] = 'string'
    payload['language'] = 'english'
    payload['content_source'] = 4
    payload['content_date'] = '2018-12-25T00:46:05.119779'
    payload['recipient_id'] = 'string'
    payload['language_content'] = text
    return payload

def gettweets(target_user):
    tweets = []
    #decrease count list from 26 to 10
    for x in range(1, 11):
        
        public_tweets = api.user_timeline(target_user, page=x, tweet_mode='extended')

        for twt in public_tweets:
            try:
                details = {}
            
                details['created_at'] = twt['created_at']
                details['screen_name'] = twt['user']['screen_name']
                details['full_text'] = twt['full_text']
                
                tweets.append(details)
            except tweepy.TweepError:
                print(f'skipping for {target_user}')
            
    return tweets

def cleanText(x):
    x = x.replace('RT','')
    x = x.replace(' .','.')
    x = x.replace('. ','.')
    x = re.sub('[^a-zA-Z0-9 \n\.]', '', x)
    x = re.sub(r'http\S+', '', x)
    x = re.sub(r'\w+:\s?', '', x)
    return x

def sendLIWC(text):
    
    response = requests.post(url, headers=headers,json=payload(text))
    #print(f'liwc response {response.json()}')
    liwc = {}
    raw_score = dict(liwc)
    raw_score.update(response.json()['receptiviti_scores']['raw_scores'])
    percentile_score = dict(liwc)
    percentile_score.update(response.json()['receptiviti_scores']['percentiles'])
    category_score = dict(liwc)
    category_score.update(response.json()['liwc_scores']['categories'])
    
    return (raw_score, percentile_score, category_score)

    
def predictions(liwcdata, modelType):
    lst = []
    lst.append(liwcdata[algoNameMap[modelType]['model_index']])
    #print(f'liwcdata {liwcdata} and {liwcdata[0]}')
    Xnew = pd.DataFrame(lst)
    #print(f'Xnew value {Xnew.head()} and first row {Xnew[:1]}')
    if algoNameMap[modelType]['columns']:
        Xnew = Xnew[algoNameMap[modelType]['columns']]

    print(f'Xnew input : {Xnew}')
    Xnew.head()


    model_path = 'models/' + algoNameMap[modelType]['model_name'] + '.h5'
    print(f'predicting for model {model_path}')
    global model
    with graph.as_default():

        model = load_model(model_path)
        ynew = model.predict_classes(Xnew[:1])
    return ynew[0]

@app.route("/")
def home():
    return render_template("landingpageNew.html")

@app.route("/dnn")
def dnn():
    return render_template("dnn.html")

@app.route("/predict", methods=['POST'])
def predict():
    handle = request.form['handle']
    algoname = request.form['algoname']
    print(f'Predicting for handle: {handle} via algorithm: {algoname}')
    tweetlist = gettweets(handle)
    df = pd.DataFrame(tweetlist)
    df['full_text_formatted'] = df['full_text'].apply(cleanText)
    text = ''
    for t in df['full_text_formatted']:
        text = text + t + '.'
    #print(f'sending text to liwc api : {text}')
    global graph
    graph = K.get_session().graph

    liwcdata = sendLIWC(text)
    predicted_class = predictions(liwcdata, algoname)
    predicted = 'Democrat'
    if predicted_class == 1:
        predicted = 'Republican'
    print(f'predicted value from model {predicted}')
    #return a jsonify version of preidctons and other data

    dataList=[]
    packet = {}
    packet['handle'] = handle
    packet['algoname'] = algoname
    #packet['backend_algoname'] = algoNameMap[algoname] 

    packet['predicted'] = str(predicted)
    packet['features'] = algoNameMap[algoname]['columns']
    #return render_template("dnn.html", packet=packet)
    matrix_path = 'data/matrix/' + algoNameMap[algoname]['model_name'] + '_matrix.txt'
    matrixDict = json.load(open(matrix_path))
    packet.update(matrixDict)
    dataList.append(packet)
    #print(f'sending data packet {packet} inside list {dataList}')
    return jsonify(dataList)


@app.route("/buzzwordmap/<buzzword>")
def buzzwordmap(buzzword):
    print(f'map buzz word {buzzword}')
    return render_template("map_buzzwordmap.html", buzzword=buzzword)








if __name__ == "__main__":
    app.run(debug=True)

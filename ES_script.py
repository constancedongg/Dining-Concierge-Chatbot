#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import boto3
import json
import os
import requests
from requests_aws4auth import AWS4Auth

GLOBAL_INDEX = 0
URL = 'https://search-restaurants-rnueuwllhgewuy3zxqid2q775y.us-east-1.es.amazonaws.com/restaurants/{}'

def update_IP(nip):
    # update Src ip of ES Service
    client = boto3.client('es')
    config = client.describe_elasticsearch_domain(DomainName='restaurants')

    policy_str = config['DomainStatus']['AccessPolicies']
    policy = eval(policy_str)
    policy['Statement'][0]['Condition']['IpAddress']['aws:SourceIp'] = nip
    policy_str = json.dumps(policy)

    client.update_elasticsearch_domain_config(DomainName='restaurants', AccessPolicies=policy_str)

def generate_es_data(file_path):
    global GLOBAL_INDEX
    restaurants = json.load(open(file_path))
    ndjson = ""
    for rstr in restaurants:
        source = {
            'id': rstr['id'],
            'category': rstr['category']
        }
        action = {"index":{"_id":str(GLOBAL_INDEX)}}
        GLOBAL_INDEX += 1

        ndjson += json.dumps(action) + '\n' + json.dumps(source) + '\n'

    return ndjson

def send_signed(method, url, service='es', region='us-east-1', body=None):
    credentials = boto3.Session().get_credentials()
    auth = AWS4Auth(credentials.access_key, credentials.secret_key, 
                  region, service, session_token=credentials.token)

    fn = getattr(requests, method)
    if body and not body.endswith("\n"):
        body += "\n"
    try:
        response = fn(url, auth=auth, data=body, 
                        headers={"Content-Type":"application/json"})
        if response.status_code != 200:
            raise Exception("{} failed with status code {}".format(method.upper(), response.status_code))
        return response.content
    except Exception:
        raise

def es_index(ndjson):
    '''Index new data from `newline delimited JSON` string'''
    # or can put `restaurant` in actions of source json
    url = URL.format('_bulk?pretty&refresh')
    send_signed('post', url, body=ndjson)

def es_search(criteria):
    url = URL.format('_search')
    return send_signed('get', url, body=json.dumps(criteria))

def get_restaurants_from_es(category):
    """Given a category, return a list of restaurant ids in that category"""
    criteria = {
        "query": { "match": {'category': category} },
    }
    content = es_search(criteria)
    content = json.loads(content)
    return [rstr['_source']['id'] for rstr in content['hits']['hits']]

def es_upload_resturant_data(dir_path):
    '''Read all json files from dir_path (one-level) and upload to ES'''
    global GLOBAL_INDEX
    GLOBAL_INDEX = 0
    for _, _, files in os.walk(dir_path):
        for file in files:
            file_path = os.path.join(dir_path, file)
            _, extension = os.path.splitext(file_path)
            if extension == '.json':
                ndjson = generate_es_data(file_path)
                print("Uploading file {} to ElasticSearch".format(file_path))
                es_index(ndjson)
                print("File {} is uploaded successfully".format(file_path))

def main():
    #update_IP('70.18.44.136')
    #es_upload_resturant_data('data')
    print(get_restaurants_from_es("japanese"))

if __name__ == '__main__':
    main()
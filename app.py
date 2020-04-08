from flask import Flask, abort, request, jsonify
from skimage import measure
from skimage import io
from pymongo import MongoClient
from bson import ObjectId
from flask_cors import CORS

import gunicorn
import datetime as dt
import requests
import os
import numpy as np
import cv2
import json

app = Flask(__name__)
CORS(app)

class JSONEncoder(json.JSONEncoder):
    def default(self, o):
        if isinstance(o, ObjectId):
            return str(o)
        return json.JSONEncoder.default(self, o)


def form_or_json():
    data = request.get_json(silent=True)
    return data if data is not None else request.form


# --------------------------- HELPER FUNCTIONS HERE ---------------------------
def mse(imageA, imageB):
    err = np.sum((imageA.astype("float") - imageB.astype("float")) ** 2)
    err /= float(imageA.shape[0] * imageA.shape[1])
    
    return err


def compare_single_images(imageA, imageB, title='fuck it'):
    # compute mse for image
    m = mse(imageA, imageB)
    s = measure.compare_ssim(imageA, imageB, multichannel=True)
    
    return {
        'mean_squared_error': m, 
        'similarity_structure_index': s
    }


def load_images_from_folder(folder):
    images = []
    for filename in os.listdir(folder):
        img = cv2.imread(os.path.join(folder,filename))
        if img is not None:
            # resize images
            img = cv2.resize(img, (1024, 1024))
            # convert to grayscale
            img = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            images.append(img)
    return images


def get_average_similarity(good_images, target_image):
    ssim_threshold = 0.50
    mse_total = 0
    ssim_total = 0
    
    # resize images
    target_image = cv2.resize(target_image, (1024, 1024))
    # convert to grayscale
    target_image = cv2.cvtColor(target_image, cv2.COLOR_BGR2GRAY)
    
    for good_image in good_images:
        res = compare_single_images(good_image, target_image)
        mse_total += res['mean_squared_error']
        ssim_total += res['similarity_structure_index']
    
    if ssim_total / len(good_images) >= ssim_threshold:
        return True
    else:
        return False

# --------------------------- END OF HELPER FUNCTIONS -------------------------


@app.route("/hello", methods=['GET', 'POST'])
def say_hi():
    data = form_or_json()
    print(data)
    return 'hello'

@app.route("/process", methods=['GET', 'POST'])
def process_data():
    data = None
    data = form_or_json()

    # initalize mongo client so we can write to DB
    client = MongoClient("mongodb+srv://sunset-data-manager-admin:sunset442@cluster0-stvht.mongodb.net/test?retryWrites=true&w=majority")
    db = client['ImageMetaData']
    image_collection = db['Images']

    data = data[:25]

    sourced_data = []

    # check images for similarity to the good image data
    good_images = load_images_from_folder("good_images")

    for datum in data:
        image_url = datum['image_url']
        image = io.imread(image_url)
        image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)

        if get_average_similarity(good_images, image):

            # if the image checks out, get the sunset time
            lat = datum['latitude']
            lng = datum['longitude']
            
            unix_time = datum['taken_at']
            date = dt.datetime.utcfromtimestamp(unix_time).strftime("%Y-%m-%d")
            
            URL = "https://api.sunrise-sunset.org/json?lat=" + str(lat) +"&lng=" + str(lng) + "&date=" + str(date)

            response = requests.get(url = URL)
            datum['sunset'] = response.json()['results']['sunset']

            # write the image to DB
            resp = image_collection.insert_one(datum)
            datum['_id'] = str(datum['_id'])

            # append to array so we can return it later
            sourced_data.append(datum)

    # get sunset times for the images we like
    # for datum in sourced_data:
    #     lat = datum['latitude']
    #     lng = datum['longitude']
        
    #     unix_time = datum['taken_at']
    #     date = dt.datetime.utcfromtimestamp(unix_time).strftime("%Y-%m-%d")
        
    #     URL = "https://api.sunrise-sunset.org/json?lat=" + str(lat) +"&lng=" + str(lng) + "&date=" + str(date)

    #     response = requests.get(url = URL)
    #     datum['sunset'] = response.json()['results']['sunset']

    # # write to DB
    # for datum in sourced_data:
    #     resp = image_collection.insert_one(datum)
    #     datum['_id'] = str(datum['_id'])

    print("HEY \n", sourced_data)
    return jsonify(sourced_data)
    



if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
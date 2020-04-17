from flask import Flask, abort, request, jsonify
from skimage import measure
from skimage import io
from pymongo import MongoClient
from bson import ObjectId
from flask_cors import CORS

from multiprocessing import Process

from threading import Thread
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


# multiprocessing helper function here 
def check_image_quality(data):
    image_data = data['image_data']
    user = data['user']

    count = 0

    for datum in image_data:
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

            duplicate = image_collection.find_one({'src_id': datum['src_id']})
            if duplicate == None:
                resp = image_collection.insert_one(datum)
                count += 1
                print("here")
    
    print(count)
    logs_collection.insert_one({
        'num_images_written': count,
        'written_by': user,
        'written_on': dt.datetime.now().strftime("%I:%M%p on %B %d, %Y")
    })

# multiprocessing helper function here 
def check_sunrise_image_quality(data):
    image_data = data['image_data']
    user = data['user']

    count = 0

    for datum in image_data:

        duplicate = sunrise_image_collection.find_one({'src_id': datum['src_id']})
        if duplicate == None:
            resp = sunrise_image_collection.insert_one(datum)
            count += 1
            print("here")
    
    print(count)
    sunrise_logs_collection.insert_one({
        'num_images_written': count,
        'written_by': user,
        'written_on': dt.datetime.now().strftime("%I:%M%p on %B %d, %Y")
    })

# --------------------------- END OF HELPER FUNCTIONS -------------------------


# initalize mongo client so we can write to DB
client = MongoClient("mongodb+srv://sunset-data-manager-admin:sunset442@cluster0-stvht.mongodb.net/test?retryWrites=true&w=majority")
db = client['ImageMetaData']
image_collection = db['Images_2']
logs_collection = db['Logs_2']

sunrise_image_collection = db['Sunrise_Images']
sunrise_logs_collection = db['Sunrise_Logs']

# load good images
good_images = load_images_from_folder("good_images")


@app.route("/hello", methods=['GET', 'POST'])
def say_hi():
    data = form_or_json()
    print(data)
    return 'hello'

@app.route("/sunrise-info", methods=['GET', 'POST'])
def get_num_sunrise_pics():
    count = str(sunrise_image_collection.estimated_document_count())
    return 'dance with my dawgs in the nighttime <br/><br/>' + count + ' images of sunrise & counting in our database ¯\_(ツ)_/¯'


@app.route("/", methods=['GET', 'POST'])
def get_num_pics():
    count = str(image_collection.estimated_document_count())
    return 'might just fuck around & be a goat named felicia - Tyler, the Creator<br/><br/>' + count + ' images & counting in our database ¯\_(ツ)_/¯'


@app.route("/logs", methods=['GET', 'POST'])
def get_logs():
    res = logs_collection.find({}).sort("_id", -1)
    res = list(res)
    log = ""
    for doc in res:
        log += str(doc['num_images_written']) + ' images written by ' + doc['written_by'] + ' at ' + doc['written_on'] + "</br>"
    
    return log

@app.route("/image-metadata", methods=['GET', 'POST'])
def get_image_meta_data():
    res = list(image_collection.find({}))
    for item in res:
        item['_id'] = str(item['_id'])

    return jsonify(res)

@app.route("/sunrise-process", methods=['GET', 'POST'])
def process_sunrise_data():
    data = None
    data = form_or_json()

    heavy_thread = Thread(
        target=check_sunrise_image_quality,
        args=(data,),
    )

    heavy_thread.daemon = True
    heavy_thread.start()

    return 'things are working'


@app.route("/sunrise-logs", methods=['GET', 'POST'])
def get_sunrise_logs():
    res = sunrise_logs_collection.find({}).sort("_id", -1)
    res = list(res)
    log = ""
    for doc in res:
        log += str(doc['num_images_written']) + ' images written by ' + doc['written_by'] + ' at ' + doc['written_on'] + "</br>"
    
    return log


@app.route("/process", methods=['GET', 'POST'])
def process_data():
    data = None
    data = form_or_json()

    # starts a thread and returns
    heavy_thread = Thread(
        target=check_image_quality,
        args=(data,),
    )

    heavy_thread.daemon = True
    heavy_thread.start()

    return 'things are working'
    

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000,)
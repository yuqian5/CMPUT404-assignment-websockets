#!/usr/bin/env python
# coding: utf-8
# Copyright (c) 2013-2014 Abram Hindle
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
import json

from flask import Flask, request, redirect, jsonify
from flask_sockets import Sockets
import gevent
from gevent import queue
import time
import json
import os

app = Flask(__name__)
sockets = Sockets(app)
app.debug = True

subscribers = list()


class World:
    def __init__(self):
        self.clear()

    def update(self, entity, key, value):
        entry = self.space.get(entity, dict())
        entry[key] = value
        self.space[entity] = entry

    def set(self, entity, data):
        self.space[entity] = data

    def clear(self):
        self.space = dict()

    def get(self, entity):
        return self.space.get(entity, dict())

    def world(self):
        return self.space


myWorld = World()


@app.route('/')
def hello():
    """Return something coherent here.. perhaps redirect to /static/index.html """
    return redirect("/static/index.html", code=302)


def read_ws(ws, client):
    """A greenlet function that reads from the websocket and updates the world"""
    while not ws.closed:
        try:
            while True:
                msg = ws.receive()
                if msg is not None:
                    req = json.loads(msg)
                    try:
                        if req["type"] == "GET":
                            if req["object"] == "world":
                                ws.send(json.dumps({
                                    "type": "world",
                                    "data": myWorld.world()
                                }))
                            if req["object"] == "entity":
                                result = myWorld.get(req["data"])
                                ws.send(json.dumps(result))
                        elif req["type"] == "POST":
                            myWorld.set(req["entity"], req["data"])
                            for s in subscribers:
                                if not s.closed:
                                    s.send(json.dumps({
                                        "type": "world",
                                        "data": myWorld.world()
                                    }))
                                else:
                                    subscribers.remove(s)
                        else:
                            for s in subscribers:
                                if not s.closed:
                                    s.send(json.dumps({
                                        "message": "bad request"
                                    }))
                                else:
                                    subscribers.remove(s)
                    except:
                        for s in subscribers:
                            if not s.closed:
                                s.send(json.dumps({
                                    "message": "bad request"
                                }))
                            else:
                                subscribers.remove(s)
                else:
                    break
        except:
            '''Done'''


def keep_alive():
    while True:
        for s in subscribers:
            if s.closed:
                subscribers.remove(s)
        time.sleep(2)


gevent.spawn(keep_alive)


@sockets.route('/subscribe')
def subscribe_socket(ws):
    """Fufill the websocket URL of /subscribe, every update notify the
       websocket and read updates from the websocket """
    subscribers.append(ws)

    g = gevent.spawn(read_ws, ws, 1)
    ws.send(json.dumps({
        "type": "world",
        "data": myWorld.world()
    }))

    try:
        while ws in subscribers:
            time.sleep(2)
    except Exception as e:  # WebSocketError as e:
        print("WS Error %s" % e)
    finally:
        gevent.kill(g)

    return 200


# I give this to you, this is how you get the raw body/data portion of a post in flask
# this should come with flask but whatever, it's not my project.
def flask_post_json():
    """Ah the joys of frameworks! They do so much work for you
       that they get in the way of sane operation!"""
    if request.json is not None:
        return request.json
    elif request.data is not None and request.data.decode("utf8") != u'':
        return json.loads(request.data.decode("utf8"))
    else:
        return json.loads(request.form.keys()[0])


@app.route("/entity/<entity>", methods=['POST', 'PUT'])
def update(entity):
    """update the entities via this interface"""
    data = json.loads(request.data.decode('utf-8'))
    if request.method == "POST":
        myWorld.set(entity, data)
    elif request.method == "PUT":
        for key in data:
            myWorld.update(entity, key, data[key])

    response = jsonify(data)
    response.headers.add('Access-Control-Allow-Origin', '*')
    return response, 200


@app.route("/world", methods=['POST', 'GET'])
def world():
    """you should probably return the world here"""
    return jsonify(myWorld.world())


@app.route("/entity/<entity>")
def get_entity(entity):
    '''This is the GET version of the entity interface, return a representation of the entity'''
    result = myWorld.get(entity)
    response = jsonify(result)
    response.headers.add('Access-Control-Allow-Origin', '*')
    return response, 200


@app.route("/clear", methods=['POST', 'GET'])
def clear():
    """Clear the world out!"""
    old_world = myWorld.world()
    myWorld.clear()
    return jsonify(old_world), 200


if __name__ == "__main__":
    ''' This doesn't work well anymore:
        pip install gunicorn
        and run
        gunicorn -k flask_sockets.worker sockets:app
    '''
    app.run()

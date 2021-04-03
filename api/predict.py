#
# Copyright 2018-2019 IBM Corp. All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
from flask_restplus import fields
from werkzeug.datastructures import FileStorage
from werkzeug.exceptions import BadRequest
from maxfw.core import MAX_API, PredictAPI
from core.model import ModelWrapper
import os
import urllib.request, urllib.parse, urllib.error
import uuid
import time
import threading


# set up parser for audio input data
input_parser = MAX_API.parser()
input_parser.add_argument('audio', type=FileStorage, location='files', required=False,
                          help="signed 16-bit PCM WAV audio file")
input_parser.add_argument('url', type=str, required=False,
                          help="URL of an audio file")
predict_response = MAX_API.model('ModelPredictResponse', {
    'status': fields.String(required=True, description='Response status message'),
    'embedding': fields.List(fields.List(fields.List(fields.Float, required=True, description="Generated embedding")))
})


def run_sys(x):
    os.system(x)


def run_model(func, data, res):
    res.append(func(data).tolist())


class ModelPredictAPI(PredictAPI):
    model_wrapper = ModelWrapper()

    @MAX_API.doc('predict')
    @MAX_API.expect(input_parser)
    @MAX_API.marshal_with(predict_response)
    def post(self):
        """Generate audio embedding from input data"""
        result = {'status': 'error'}

        true_start = time.time()

        args = input_parser.parse_args()

        if args['audio'] is None and args['url'] is None:
            e = BadRequest()
            e.data = {'status': 'error', 'message': 'Need to provide either an audio or url argument'}
            raise e

        audio_data = {}
        uuid_map = {}
        if args['url'] is not None:
            url_splt = args['url'].split(',')
            for url in url_splt:
                audio_data[url] = urllib.request.urlopen(args['url']).read()
        else:
            audio_data[args['audio'].filename] = args['audio'].read()

        print(f"audio_data: {audio_data.keys()}")
        for filestring in audio_data.keys():
            uuid_map[filestring] = uuid.uuid1()
            if 'mp3' in filestring:
                print(f"Creating file: /{uuid_map[filestring]}.mp3")
                file = open(f"/{uuid_map[filestring]}.mp3", "wb+")
                file.write(audio_data[filestring])
                file.close()
            elif 'wav' in filestring:
                print(f"Creating file: /{uuid_map[filestring]}.wav")
                file = open(f"/{uuid_map[filestring]}.wav", "wb+")
                file.write(audio_data[filestring])
                file.close()
            else:
                e = BadRequest()
                e.data = {'status': 'error', 'message': 'Invalid file type/extension'}
                raise e

        start = time.time()

        # start all programs
        commands = [f"ffmpeg -i /{uuid_map[x]}.mp3 /{uuid_map[x]}.wav" if 'mp3' in x else "" for x in uuid_map.keys()]

        threads = []
        for command in commands:
            if command != "":
                print(f" Running command: {command}")
                threads.append(threading.Thread(target=run_sys, args=(command,)))
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

        print(f'Converted mp3 files in {time.time() - start}s')

        start = time.time()
        for filestring in uuid_map.keys():
            audio_data[filestring] = open(f"/{uuid_map[filestring]}.wav", "rb").read()
            os.remove(f"/{uuid_map[filestring]}.wav")
            if 'mp3' in filestring:
                os.remove(f"/{uuid_map[filestring]}.mp3")
        print(f'Deleted files in {time.time() - start}s')

        # Getting the predictions
        preds = []
        threads = []
        for filestring in audio_data.keys():
            res = []
            threads.append(threading.Thread(target=run_model, args=(self.model_wrapper.predict, audio_data[filestring], res)))
            preds.append(res)
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        preds = [x[0] for x in preds]
        # Aligning the predictions to the required API format
        result['embedding'] = preds
        result['status'] = 'ok'

        print(f'Completed processing in {time.time() - true_start}s')
        return result

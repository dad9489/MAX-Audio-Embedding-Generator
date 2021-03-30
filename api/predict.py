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
import re
from flask_restplus import fields
from werkzeug.datastructures import FileStorage
from werkzeug.exceptions import BadRequest
from maxfw.core import MAX_API, PredictAPI
from core.model import ModelWrapper
import os
import urllib.request, urllib.parse, urllib.error


# set up parser for audio input data
input_parser = MAX_API.parser()
input_parser.add_argument('audio', type=FileStorage, location='files', required=False,
                          help="signed 16-bit PCM WAV audio file")
input_parser.add_argument('url', type=str, required=False,
                          help="URL of an audio file")
predict_response = MAX_API.model('ModelPredictResponse', {
    'status': fields.String(required=True, description='Response status message'),
    'embedding': fields.List(fields.List(fields.Float, required=True, description="Generated embedding"))
})


class ModelPredictAPI(PredictAPI):
    model_wrapper = ModelWrapper()

    @MAX_API.doc('predict')
    @MAX_API.expect(input_parser)
    @MAX_API.marshal_with(predict_response)
    def post(self):
        """Generate audio embedding from input data"""
        result = {'status': 'error'}

        args = input_parser.parse_args()

        # if not re.match("audio/.*wav", str(args['audio'].mimetype)):
        #     e = BadRequest()
        #     e.data = {'status': 'error', 'message': f'Invalid file type/extension: {str(args["audio"].mimetype)}'}
        #     raise e

        if args['audio'] is None and args['url'] is None:
            e = BadRequest()
            e.data = {'status': 'error', 'message': 'Need to provide either an audio or url argument'}
            raise e

        if args['url'] is not None:
            audio_data = urllib.request.urlopen(args['url']).read()
            filestring = str(args['url'])
        else:
            audio_data = args['audio'].read()
            filestring = str(args['audio'])

        if 'mp3' in filestring:
            file = open("/audio.mp3", "wb+")
            file.write(audio_data)
            file.close()
            os.system("ffmpeg -i /audio.mp3 /audio.wav")
            os.remove("/audio.mp3")
        elif 'wav' in filestring:
            file = open("/audio.wav", "wb+")
            file.write(audio_data)
            file.close()
        else:
            e = BadRequest()
            e.data = {'status': 'error', 'message': 'Invalid file type/extension'}
            raise e

        audio_data = open("/audio.wav", "rb").read()
        os.remove("/audio.wav")

        # Getting the predictions
        preds = self.model_wrapper.predict(audio_data)

        # Aligning the predictions to the required API format
        result['embedding'] = preds.tolist()
        result['status'] = 'ok'

        return result

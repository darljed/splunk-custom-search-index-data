from __future__ import division
from past.utils import old_div
import splunk.Intersplunk 
import base64

import http.client
from base64 import b64encode
import json
import datetime
import sys
import os
import splunklib.client as client

class Actions:
    def __init__(self,):
        self.s_host="localhost"
        self.s_port="8089"
        self.index="training_tracker"
        self.log_index = "training_tracker_logs"
        self.sourcetype="trainingtracker:json"


    def logger(self,data):
        service = self.splunk_connect(self.token)
        target = service.indexes[self.log_index]
        sourcetype="_json"

        try:
            if(type(data) == 'dict'):
                data = str(json.dumps(data))
            else:
                data = str(data)
            
            data = {
                "user_id":self.user_account,
                "message":data
                }

            
            target.submit(str(json.dumps(data)), sourcetype=sourcetype)

            # print("Event indexed")
        except Exception as error:
            pass

    def splunk_connect(self,sessionKey):

        try:
            service = client.connect(
                host=self.s_host,
                port=self.s_port,
                token=sessionKey
            )
            return service

        except Exception as error:
            self.logger(error)

    def splunk_push(self,index, sourcetype,sessionKey,data):
        service = self.splunk_connect(sessionKey)
        target = service.indexes[index]
        sourcetype=sourcetype

        try:
            # data['timestamp'] = self.get_timestamp()
            # self.logger(data.get('_time'))
            target.submit(str(json.dumps(data)), sourcetype=sourcetype)
            self.logger("Successfully updated training tracker record")
            # print("Event indexed")
            return True
        except Exception as error:
            self.logger("Failed to log training tracker record. Error:"+str(error))
            # print(error)
            return error



    def get_timestamp(self,epoch):
        # self.logger(f'Epoch value: {epoch}')
        timestamp = datetime.datetime.fromtimestamp(int(epoch.split('.')[0])).strftime("%Y-%m-%dT%H:%M:%S")
        # timestamp = int(epoch.split('.')[0])
        # self.logger(f"Generated timestamp: {timestamp}")
        return timestamp

    def add_record(self):
        try:
            results, dummyresults, settings = splunk.Intersplunk.getOrganizedResults()
            self.token = settings.get("sessionKey", None)
            self.user_account = settings.get('owner')
            for result in results:
                # self.logger(f"date value from organizeddata {result.get('id')}")
                data = {
                    "trainingslug": result.get('trainingslug'),
                    "id": result.get('id'),
                    "status": result.get('status'),
                    "owner": settings.get('owner'),
                    "timestamp": self.get_timestamp(result.get('date')),
                    "imgfilename": result.get('filename') if result.get('status')=="Completed" else "None"
                }
                
                post = self.splunk_push(self.index,self.sourcetype,settings.get("sessionKey", None),data)
                ## Genrate image
                if(result.get('status') == "Completed"):
                    self.saveImageBlob(result.get('imgblob'),result.get('filename'))
                result['result'] = str(post)
                splunk.Intersplunk.outputResults(results)
                
            # f = open('test.txt','w')
            # f.write(str(settings))
                
        except Exception as e2:
            self.logger(f"Unable to save result. {e2}")
            splunk.Intersplunk.generateErrorResults("Error '%s'. %s" % (e2))
        # for result in results:
        #     result['dummyresults'] = dummyresults
        #     result['settings'] = settings
        #     result['data'] = data
        #     result['code'] = 200
        #     result['sessionKey'] = settings.get("sessionKey", None)
        
        # self.logger(result)
        # print("Test")

    def saveImageBlob(self,blob,filename):
        assetsdir = os.path.abspath(os.path.join(os.path.dirname(__file__),'../','appserver','static','training_tracker_proofimages'))
        if(not os.path.exists(assetsdir)):
            os.makedirs(assetsdir)
        
        imagefile = blob
        # imagefile = imagefile.replace("proofimage=","")
        image = imagefile.split(',')[-1]
        binary_data = image.encode()

        fd = open(os.path.join(assetsdir,filename), 'wb')
        fd.write(base64.decodebytes(binary_data))
        fd.close()

def main():
    e = Actions()
    e.add_record()

if __name__ == "__main__" :
    main()
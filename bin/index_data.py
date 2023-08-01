from __future__ import division
from past.utils import old_div
import splunk.Intersplunk 
import base64

from base64 import b64encode
import json
import time
import sys
import os
import splunklib.client as client

class Actions:
    def __init__(self,):
        # initialize configurations 
        # better if this can be moved to a configuration file 
        self.s_host="localhost"
        self.s_port="8089"
        self.index="custom_search_index_data_idx"
        self.sourcetype="custom_json"

    def splunk_connect(self,sessionKey):
        # create splunk service connection over http
        try:
            service = client.connect(
                host=self.s_host,
                port=self.s_port,
                token=sessionKey
            )
            return service

        except Exception as error:
            print(error)

    def splunk_push(self,index, sourcetype,sessionKey,data): # this function saves data to the provided argument "index" when invoked
        service = self.splunk_connect(sessionKey)
        target = service.indexes[index]
        sourcetype=sourcetype

        try:
            target.submit(str(json.dumps(dict(data))), sourcetype=sourcetype) # triggers submission and indexing of data
            return True
        except Exception as error:
            return f'Event not indexed. {error}'


    def add_record(self):
        try:
            results, dummyresults, settings = splunk.Intersplunk.getOrganizedResults()
            self.token = settings.get("sessionKey", None) # capture session key from user's auth details
            for result in results:
                
                # you can modify and add more fields here that will be added to the data when indexed
                result['Greetings'] = "Hello World!"
                result['timestamp'] = time.time()
                # save data to index / index data
                post = self.splunk_push(self.index,self.sourcetype,self.token,result)
                # all changes to 'result' dict after this will not be indexed
                result['is_indexed'] = str(post)
                # result['sessionKey'] = self.token
            
            # return the results from the search in search page
            splunk.Intersplunk.outputResults(results)
                
                
        except Exception as e2:
            splunk.Intersplunk.generateErrorResults("Error '%s'. %s" % (e2))

def main():
    e = Actions()
    e.add_record()

if __name__ == "__main__" :
    main()
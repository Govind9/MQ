import socket
import json
import sys
from _thread import *

class MqsClient(object):
    IP = 'localhost'
    PORT = 8082
    
    def __init__(self):
        try:
            self.mqs_client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.mqs_client.setblocking(True)
            self.mqs_client.connect((self.IP, int(self.PORT)))
            self.mqs_client.setblocking(False)
        except Exception as e:
            self.mqs_client = None
        
    def __del__(self):
        #self.close()
        pass
        
    def close(self):
        if self.mqs_client:
            message = json.dumps({
                "type": "quit",
                "body": ""
            })
            self.send_wait(self.mqs_client, message)
            self.mqs_client.close()
        self.mqs_client = None
        
    def send_push_request(self, bodies):
        try:
            message = json.dumps({
                "type": "push",
                "body": bodies
            })
            return self.send_wait(self.mqs_client, message)
        except Exception as e:
            raise(e)
    
    def send_pole_request(self):
        try:
            message = json.dumps({
                "type": "pole",
                "body": ""
            })
            return self.send_wait(self.mqs_client, message)
        except Exception as e:
            raise(e)
    
    def send_pop_request(self, indexes):
        try:
            message = json.dumps({
                'type': 'pop',
                'body': indexes
            })
            return self.send_wait(self.mqs_client, message)
        except Exception as e:
            raise(e)
    
    def send_wait(self, client, msg):
        while True:
            try:
                client.send(msg.encode('utf-8'))
                return True, ""
            except BlockingIOError as e:
                continue
            except Exception as e:
                return False, str(e)
        
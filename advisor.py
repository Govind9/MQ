import socket
import json
import sys
import random
from mqs_client import MqsClient
from tkinter import *
from _thread import *
from time import sleep

class Advisor(object):
    def __init__(self):
        self.online = True
        
        #prepare GUI
        self.window = Tk()
        self.window.title("Advisor")
        
        #Widget to show the number of seconds left to pole
        Label(self.window, text="Next Pole In:").grid(row=0, column= 0)
        self.time_label = Label(self.window, text = "NA")
        self.time_label.grid(row=0, column=1)

        #Widget to stop Advisor
        self.stop_button = Button(self.window, text = 'stop', command = self.stop_advisor)
        self.stop_button.grid(row = 0, column = 2)

        #Widget for the event log
        self.events = Text(self.window)
        self.events.grid(row=1, column=0, columnspan=3)
        
        #get client to deal with mqs
        self.mqs_client = MqsClient()
        if self.mqs_client.mqs_client:
            self.events.insert("end", 'Client connected to MQS.\n')
            self.events.insert("end", '#'*15+'\n')
        else:
            self.events.insert("end", 'MQS unavailable.\n')
            self.events.insert("end", '#'*15+'\n')

        self.start_advisor()
        self.window.protocol('WM_DELETE_WINDOW', self.stop_advisor)
        self.window.mainloop()
        
    def __del__(self):
        #self.stop_advisor()
        pass
        
    def stop_advisor(self):
        self.online = False
        self.mqs_client.close()
        self.window.destroy()
        sys.exit()
        
    def start_advisor(self):
        try:
            #start receiving messages from mqs
            start_new_thread(self.recv_from_mqs, ())
            
            #send the first pole request
            self.request_pole()
        except Exception as e:
            raise(e)
            
    def request_pole(self):
        if self.mqs_client.mqs_client == None:
            self.mqs_client = MqsClient()
        done, err = self.mqs_client.send_pole_request()
        if done:
            self.events.insert("end", 'Pole Request Sent.\n')
            self.events.insert("end", '#'*15+'\n')
        else:
            self.events.insert("end", 'Could not send Pole Request.\n')
            self.events.insert("end", 'MQS unavailable.\n')
            self.events.insert("end", '#'*15+'\n')
            
    def recv_from_mqs(self):
        while self.online and self.mqs_client.mqs_client:
            try:
                message = self.mqs_client.mqs_client.recv(2048).decode('utf-8')
                
                #parse the http message
                msg = json.loads(message)
                
                #decide course of action based on message type and purpose:
                if msg['type'] == 'pole_result':
                    response = msg['messages']
                    self.decide_and_pole(response)
                if msg['type'] == 'quit':
                    self.mqs_client.close()
                    self.events.insert("end", 'MQS offline.\n')
                    self.events.insert("end", '#'*15+'\n')
            except BlockingIOError as e:
                continue
            except Exception as e:
                raise(e)
            
    def decide_and_pole(response):
        decision_found = False
        for id in response:
            if response[id]["from"] == "student" and response[id]["decision"] == "evaluation pending":
                decision_found = True
                result = {
                    "from": "advisor",
                    "student_name": response[id]["student_name"],
                    "subject_name": response[id]["subject_name"],
                    "decision": random.choice(["approved", "disapproved"])
                }
                self.events.insert("end", 'FOLLOWING DECISION MADE:\n')
                self.events.insert("end", 'Student: {}\n'.format(result['student_name']))
                self.events.insert("end", 'Subject: {}\n'.format(result['subject_name']))
                self.events.insert("end", 'Decision: {}\n'.format(result['decision']))
                self.events.insert("end", '#'*15+'\n')
                
                #push this decision message to mqs
                if self.mqs_client.mqs_client == None:
                    self.mqs_client = MqsClient()
                done, err = self.mqs_client.send_push_request(result)
                if done:
                    self.events.insert("end", 'DECISION PUSHED TO MQS\n')
                    self.events.insert("end", '#'*15+'\n')
                else:
                    self.events.insert("end", 'ERROR IN PUSHING TO MQS:\n')
                    self.events.insert("end", 'MQS unavailable.\n')
                    self.events.insert("end", '#'*15+'\n')
                    
                #pop this decision message from mqs
                if self.mqs_client.mqs_client == None:
                    self.mqs_client = MqsClient()
                done, err = self.mqs_client.send_pop_request(id)
                if done:
                    self.events.insert("end", 'OLD RECORD POPPED FROM MQS\n')
                    self.events.insert("end", '#'*15+'\n')
                else:
                    self.events.insert("end", 'ERROR IN POPPING OLD RECORD:\n')
                    self.events.insert("end", 'MQS unavailable.\n')
                    self.events.insert("end", '#'*15+'\n')
        Wait = 2 if decision_found else 3
        for i in range(Wait):
            self.time_label.configure(text = str(Wait - i))
            sleep(1)
        self.request_pole()
        
advisor = Advisor()
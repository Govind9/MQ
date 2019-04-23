import socket
import json
import sys
from mqs_client import MqsClient
from tkinter import *
from _thread import *
from time import sleep

class Notifier(object):
    IP = '127.0.0.1'
    PORT = 8083
    
    def __init__(self):
        #prepare notifier socket
        self.notifier = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.notifier.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.notifier.setblocking(False)
        self.wait_seven_seconds  = False
        self.online = False
        
        #prepare data structure to hold connections
        self.clients = {}
        
        #prepare mqs GUI
        self.window = Tk()
        self.window.title("Notifier")
        
        #Widget to show the MQS status
        Label(self.window, text="MQS:").grid(row=0, column= 0)
        self.mqs_label = Label(self.window, text = "DOWN")
        self.mqs_label.grid(row=0, column=1)
        
        #Widget to show the number of connections to Notifier
        Label(self.window, text="Conenections:").grid(row=0, column= 2)
        self.connections_label = Label(self.window, text=str(self.count_online()))
        self.connections_label.grid(row=0, column=3)
        
        #Widget to show the number of seconds left to pole
        Label(self.window, text="Next Pole In:").grid(row=0, column= 4)
        self.time_label = Label(self.window, text = "NA")
        self.time_label.grid(row=0, column=5)
        
        #Widget to stop notifier
        self.stop_button = Button(self.window, text = 'stop', command = self.stop_notifier)
        self.stop_button.grid(row = 0, column = 6)

        #Widget for the event log
        self.events = Text(self.window)
        self.events.grid(row=1, column=0, columnspan=7)
        
        #get client to deal with mqs
        self.mqs_client = MqsClient()
        if self.mqs_client.mqs_client:
            self.events.insert("end", 'Client connected to MQS.\n')
            self.events.insert("end", '#'*15+'\n')
        else:
            self.events.insert("end", 'MQS unavailable.\n')
            self.events.insert("end", '#'*15+'\n')
        
        #start things
        self.start_notifier()
        self.window.protocol('WM_DELETE_WINDOW', self.stop_notifier)
        self.window.mainloop()
        
    def __del__(self):
        #self.stop_notifier()
        pass
        
    def start_notifier(self):
        try:
            #initiate the notifier
            self.notifier.setblocking(True)
            self.notifier.bind((self.IP, self.PORT))
            self.notifier.setblocking(False)
            self.notifier.listen(100)
            self.online = True

            #start a new thread to handle incoming connections
            start_new_thread(self.accept_connections, ())
            
            #start receiving messages from mqs
            start_new_thread(self.recv_from_mqs, ())
            
            #send the first pole request
            start_new_thread(self.request_pole, ())
        except Exception as e:
            raise(e)
            
    def stop_notifier(self):
        try:
            notification = json.dumps({
                "type": "quit",
                "body": ""
            })
            for index in self.clients:
                self.send_wait(self.clients[index], notification)
            
            self.online = False
            self.notifier.close()
            self.mqs_client.close()
            self.window.destroy()
            sys.exit()
        except Exception as e:
            self.window.destroy()
            sys.exit()
            
    def request_pole(self):
        while self.online:
            if self.mqs_client.mqs_client is None:
                self.mqs_client = MqsClient()
            if self.mqs_client.mqs_client is None:
                self.mqs_label.configure(text = "DOWN")
            else:
                self.mqs_label.configure(text = "UP")
            
            done, err = self.mqs_client.send_pole_request()
            if done:
                self.events.insert("end", 'Pole Request Sent.\n')
                self.events.insert("end", '#'*15+'\n')
            else:
                self.events.insert("end", 'Could not send Pole Request.\n')
                self.events.insert("end", 'MQS unavailable.\n')
                self.events.insert("end", '#'*15+'\n')
            #wait a couple of seconds, let dust settle from the above sent request
            for i in range(2):
                self.time_label.configure(text = str(2 - i))
                sleep(1)
            if self.wait_seven_seconds:
                self.wait_seven_seconds = False
                for i in range(5):
                    self.time_label.configure(text = str(5 - i))
                    sleep(1)
            
    def accept_connections(self):
        while self.online:
            try:
                conn_found = False
                conn, addr = self.notifier.accept()
                index = None
                for i in sorted(self.clients):
                    if self.clients[i] is None:
                        index = i
                        conn_found = True
                        break
                if (not conn_found) and (conn):
                    try:
                        index = sorted(self.clients)[-1] + 1
                    except Exception as e:
                        index = 0
                if index is not None:
                    self.clients[index] = conn
                    self.connections_label.configure(text = str(self.count_online()))
                    self.events.insert("end", 'Client connected to Notifier.\n')
                    self.events.insert("end", '#'*15+'\n')
                    #start a new thread to handle the client
                    start_new_thread(self.client_thread, (index, ))
            except BlockingIOError as e:
                continue
            except Exception as e:
                raise(e)
                
    def client_thread(self, index):
        client = self.clients[index]
        
        #client thread continues to listen to messages
        while self.online:
            try:     
                message = client.recv(2048).decode('utf-8')
                
                #parse the message                
                msg = json.loads(message)
                
                #decide course of action based on message type and purpose:
                if msg['type'] == 'quit':
                    self.clients[index].close()
                    self.clients[index] = None
                    self.connections_label.configure(text = str(self.count_online()))
                    self.events.insert("end", 'Client disconnected from Notifier.\n')
                    self.events.insert("end", '#'*15+'\n')
                    break
            except BlockingIOError as e:
                continue
            except Exception as e:
                raise(e)
            
    def recv_from_mqs(self):
        while self.online:
            if self.mqs_client.mqs_client is None:
                sleep(2)
                continue
            try:
                message = self.mqs_client.mqs_client.recv(2048).decode('utf-8')
                
                #parse the http message
                msg = json.loads(message)
                
                #decide course of action based on message type and purpose:
                if msg['type'] == 'pole_result':
                    self.pole_status = "response_received"
                    response = msg['messages']
                    self.events.insert("end", 'Response from MQS:\n{}\n'.format(json.dumps(response, indent = 1)))
                    self.events.insert("end", '#'*15+'\n')
                    self.notify_clients(response)
                if msg['type'] == 'quit':
                    self.mqs_client.close()
                    self.events.insert("end", 'MQS offline.\n')
                    self.events.insert("end", '#'*15+'\n')
            except BlockingIOError as e:
                continue
            except Exception as e:
                raise(e)
                
    def notify_clients(self, response):
        #find decisions that are completed and ready to be reported
        completed_decisions = {}
        for id in response:
            if response[id]["from"] == "advisor" and response[id]["decision"] != "evaluation pending":
                completed_decisions[id] = response[id]
        if len(completed_decisions) == 0:
            self.events.insert("end", 'NO COMPLETED DECISIONS TO REPORT:\n')
            self.wait_seven_seconds = True
            return
        
        #turn completed_decisions into a notification
        notification = {
            "type": "decisions",
            "body": []
        }
        for id in completed_decisions:
            notification["body"].append(completed_decisions[id])
            self.events.insert("end", 'FOLLOWING DECISION TO BE NOTIFIED:\n')
            self.events.insert("end", 'Student: {}\n'.format(completed_decisions[id]['student_name']))
            self.events.insert("end", 'Subject: {}\n'.format(completed_decisions[id]['subject_name']))
            self.events.insert("end", 'Decision: {}\n'.format(completed_decisions[id]['decision']))
            self.events.insert("end", '#'*15+'\n')
        
        #report completed_decisions
        client_found = False
        for index in self.clients:
            if self.clients[index] is None:
                continue
            client_found = True
            self.send_wait(self.clients[index], json.dumps(notification))
        
        #pop the completed decision messages from mqs if the notification was sent to atleast one client
        if client_found:
            self.events.insert("end", 'NOTIFICATION SENT TO CONNECTED CLIENTS\n')
            self.events.insert("end", '#'*15+'\n')
            ids = [id for id in completed_decisions]
            if self.mqs_client.mqs_client == None:
                self.mqs_client = MqsClient()
            done, err = self.mqs_client.send_pop_request(ids)
            if done:
                self.events.insert("end", 'NOTIFIED DECISIONS POPPED FROM MQS\n')
                self.events.insert("end", '#'*15+'\n')
            else:
                self.events.insert("end", 'ERROR IN POPPING NOTIFIED DECISION\n')
                self.events.insert("end", 'MQS unavailable.\n')
                self.events.insert("end", '#'*15+'\n')
        else:
            self.events.insert("end", 'NO CLIENTS CONNECTED TO SEND NOTIFICATION\n')
            self.events.insert("end", '#'*15+'\n')
            self.wait_seven_seconds = True
    
    def count_online(self):
        online_count = 0
        for i in self.clients:
            if self.clients[i]: 
                online_count += 1
        return online_count
    
    def send_wait(self, client, msg):
        while self.online:
            try:
                client.send(msg.encode('utf-8'))
                break
            except BlockingIOError as e:
                continue
            except Exception as e:
                return
                
notifier = Notifier()
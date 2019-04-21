import socket
import json
import sys
from tkinter import *
from _thread import *

class Mqs(object):
    store = "store.json"
    IP = '127.0.0.1'
    PORT = 8082
    
    def __init__(self):
        #prepare mqs data structures:
        self.messages = {}
        self.offset = 0
        self.msg_count = 0
        
        #load old data if present
        self.load_data()
        
        #prepare mqs socket
        self.mqs = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.mqs.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.mqs.setblocking(False)
        self.online = False
        
        #prepare data structure to hold connections
        self.clients = {}
        
        #prepare mqs GUI
        self.window = Tk()
        self.window.title("MQS")
        
        #Widget to show the number of connections to MQS
        Label(self.window, text="Conenections:").grid(row=0, column= 0)
        self.connections_label = Label(self.window, text=str(self.count_online()))
        self.connections_label.grid(row=0, column=1)
        
        #Widget to show the number of messages in MQS
        Label(self.window, text="Messages:").grid(row=0, column= 2)
        self.count_label = Label(self.window, text=str(self.msg_count))
        self.count_label.grid(row=0, column=3)

        #Widget for stop MQS
        self.stop_button = Button(self.window, text = 'stop', state = DISABLED, command = self.stop_mqs)
        self.stop_button.grid(row = 0, column = 4)

        #Widget for the event log
        self.events = Text(self.window)
        self.events.grid(row=1, column=0, columnspan=5)

        self.start_mqs()
        self.window.protocol('WM_DELETE_WINDOW', self.stop_mqs)
        self.window.mainloop()
        
    def __del__(self):
        #self.stop_mqs()
        pass
        
    def start_mqs(self):
        try:
            #initiate the mqs, adjust widgets status
            self.mqs.setblocking(True)
            self.mqs.bind((self.IP, self.PORT))
            self.mqs.setblocking(False)
            self.mqs.listen(100)
            self.online = True
            self.stop_button.configure(state = NORMAL)

            #start a new thread to handle incoming connections
            start_new_thread(self.accept_connections, ())
        except Exception as e:
            raise(e)
            
    def stop_mqs(self):
        try:
            #notify each active client that MQS is closing
            msg = json.dumps({
                "type": "quit",
                "body": ""
            })
            for i in self.clients:
                if self.clients[i]:
                    self.send_wait(self.clients[i], msg)
                    
            #commit the messages
            self.commit()
            
            #stop MQS
            self.online = False
            self.mqs.close()
            self.window.destroy()
            sys.exit()
        except Exception as e:
            self.window.destroy()
            sys.exit()
            raise(e)
            
    def accept_connections(self):
        while self.online:
            try:
                conn_found = False
                conn, addr = self.mqs.accept()
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
                    self.events.insert("end", 'Client connected to MQS.\n')
                    self.events.insert("end", '#'*15+'\n')
                    #start a new thread to handle the client
                    start_new_thread(self.client_thread, (index, ))
            except BlockingIOError as e:
                continue
            except Exception as e:
                raise(e)
            
    def count_online(self):
        online_count = 0
        for i in self.clients:
            if self.clients[i]: 
                online_count += 1
        return online_count
        
    def client_thread(self, index):
        client = self.clients[index]
        
        #client thread continues to listen to messages
        while self.online:
            try:     
                message = client.recv(2048).decode('utf-8')
                
                #parse the message                
                msg = json.loads(message)
                
                #decide course of action based on message type and purpose:
                if msg['type'] == "push":
                    self.push(msg)
                elif msg['type'] == 'pop':
                    self.pop(msg)
                elif msg['type'] == 'pole':
                    self.pole(client)
                elif msg['type'] == 'quit':
                    self.close_client(index)
                    break
            except BlockingIOError as e:
                continue
            except Exception as e:
                raise(e)
    
    def close_client(self, index):
        try:
            if index in self.clients and self.clients[index]:
                self.clients[index].close()
                self.clients[index] = None
                #Show the updated connection_counter
                self.connections_label.configure(text = str(self.count_online()))
                self.events.insert("end", 'Client disconnected.\n')
                self.events.insert("end", '#'*15+'\n')
        except Exception as e:
            raise(e)
    
    def send_wait(self, client, msg):
        while self.online:
            try:
                client.send(msg.encode('utf-8'))
                break
            except BlockingIOError as e:
                continue
            except Exception as e:
                return
        
    def commit(self):
        try:
            with open(self.store, "w") as file:
                file.write(json.dumps(self.messages, indent = 2))
            self.events.insert("end", 'Records Commited.\n')
            self.events.insert("end", '#'*15+'\n')
        except Exception as e:
            raise(e)
            
    def push(self, msg):
        try:
            self.messages[self.offset + 1] = msg['body']
            self.offset += 1
            self.msg_count += 1
            self.count_label.configure(text = str(self.msg_count))
            self.events.insert("end", 'Added record: \n{}\n'.format(msg['body']))
            self.events.insert("end", '#'*15+'\n')
            self.commit()
        except Exception as e:
            raise(e)
        
    def pop(self, msg):
        try:
            id = int(msg['body'])
            message = self.messages.pop(id, None)
            if message is not None:
                self.msg_count -= 1
                self.count_label.configure(text = str(self.msg_count))
                self.events.insert("end", 'Removed record: \n{}\n'.format(message))
                self.events.insert("end", '#'*15+'\n')
            self.commit()
            return message
        except Exception as e:
            raise(e)
        
    def pole(self, client):
        try:
            response = {
                'type': 'pole_result',
                'messages': {}
            }
            for id in self.messages:
                if self.messages[id]:
                    response['messages'][id] = messages[id]
                    
            self.send_wait(client, json.dumps(response))
        except Exception as e:
            raise(e)
            
    def load_data(self):
        try:
            with open(self.store, "r") as file:
                self.messages = json.loads(file.read())
            self.offset = sorted(self.messages)[-1]
            self.msg_count = 0
            for i in self.messages:
                if self.messages[i] is not None: self.msg_count += 1
        except Exception as e:
            pass
            
mqs = Mqs()
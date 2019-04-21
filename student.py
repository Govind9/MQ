import socket
import json
import sys
from mqs_client import MqsClient
from tkinter import *
from _thread import *
from time import sleep

class Student(object):
    def __init__(self):
        self.online = True
        
        #prepare GUI
        self.window = Tk()
        self.window.title("Student")
        
        #Widget to get the Student Name
        Label(self.window, text="Student Name:").grid(row=0, column= 0)
        self.student_name = StringVar()
        self.student_name_field = Entry(self.window, text = self.student_name)
        self.student_name_field.grid(row=0, column = 1)
        
        #Widget to get the Subject Name
        Label(self.window, text="Subject Name:").grid(row=0, column= 2)
        self.subject_name = StringVar()
        self.subject_name_field = Entry(self.window, text = self.subject_name)
        self.subject_name_field.grid(row=0, column = 3)

        #Widget to send to MQS
        self.send_button = Button(self.window, text = 'send', command = self.send_mqs)
        self.send_button.grid(row = 0, column = 4)
        
        #Message after send button pressed
        self.send_status_label = Label(self.window, text = "")
        self.send_status_label.grid(row=1, column = 0, columnspan = 5)
        
        #Widget to show the notification service status
        Label(self.window, text="Notification Service:").grid(row=2, column= 0)
        self.notifier_label = Label(self.window, text = "DOWN")
        self.notifier_label.grid(row=2, column=1)
        
        #Widget to stop student
        self.stop_button = Button(self.window, text = 'stop', command = self.end_student)
        self.stop_button.grid(row = 2, column = 4)

        #Widget for the event log
        self.events = Text(self.window)
        self.events.grid(row=3, column=0, columnspan=5)

        #get client to deal with mqs
        self.mqs_client = MqsClient()
        if self.mqs_client.mqs_client:
            self.events.insert("end", 'Client connected to MQS.\n')
            self.events.insert("end", '#'*15+'\n')
        else:
            self.events.insert("end", 'MQS unavailable.\n')
            self.events.insert("end", '#'*15+'\n')
        
        #keep looking for notifier till it is found
        self.notifier = None
        start_new_thread(self.get_notifier, ())
        
        self.window.protocol('WM_DELETE_WINDOW', self.end_student)
        self.window.mainloop()
        
    def __del__(self):
        #self.end_student()
        pass
        
    def end_student(self):
        if self.notifier is not None:
            message = json.dumps({
                "type": "quit",
                "body": ""
            })
            self.send_wait(self.notifier, message)
        self.online = False
        self.mqs_client.close()
        self.window.destroy()
        sys.exit()
        
    def get_notifier(self):
        #get notification object
        IP = 'localhost'
        PORT = '8083'
        while self.online:
            if self.notifier is None:
                try:
                    self.notifier = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    self.notifier.setblocking(True)
                    self.notifier.connect((IP, int(PORT)))
                    self.notifier.setblocking(False)
                    self.notifier_label.configure(text = "UP")
                    start_new_thread(recv_notifications, ())
                except Exception as e:
                    self.notifier = None
                    self.notifier_label.configure(text = "DOWN")
            sleep(2)
        
    def send_mqs(self):
        try:
            available = False
            if self.mqs_client.mqs_client == None:
                self.mqs_client = MqsClient()
                if self.mqs_client.mqs_client == None:
                    available = False
                    self.send_status_label.configure(text = "MQS unavailable!")
                else:
                    available = True
                    self.send_status_label.configure(text = "Client connected to MQS!")
            else:
                available = True
            
            if available:
                student = self.student_name_field.get()
                subject = self.subject_name_field.get()
                if student and subject:
                    body = {
                        "from": "student",
                        "student_name": student,
                        "subject_name": subject,
                        "decision": "evaluation pending"
                    }
                    done, err = self.mqs_client.send_push_request(body)
                    if done:
                        self.send_status_label.configure(text = "Record sent!")
                    else:
                        self.send_status_label.configure(text = "MQS unavailable")
                else:
                    self.send_status_label.configure(text = "Student or Subject fields cannot be empty!")
        except Excpetion as e:
            raise(e)
            
    def recv_notifications(self):
        while self.online:
            try:
                message = self.notifier.recv(2048).decode('utf-8')
                
                #parse the http message
                msg = json.loads(message)
                
                #take action depending on type of notification
                if msg['type'] == 'decision':
                    #print in events
                    self.events.insert("end", 'DECISION RECEIVED\n')
                    self.events.insert("end", 'Student: {}\n'.format(msg['body']['student_name']))
                    self.events.insert("end", 'Subject: {}\n'.format(msg['body']['subject_name']))
                    self.events.insert("end", 'Decision: {}\n'.format(msg['body']['decision']))
                    self.events.insert("end", '#'*15+'\n')
                elif msg['type'] == 'quit':
                    self.notifier = None
                    self.notifier_label.configure(text = "DOWN")
                    break
            except BlockingIOError as e:
                continue
            except Exception as e:
                end_chat()
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
                
student = Student()
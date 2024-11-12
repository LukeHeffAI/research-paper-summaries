## This file will contain all the classes, dataclasses, and functions for managing users, including:
# - Creating new users
# - Loading existing users
# - Saving user data
# - Deleting users
# - Managing user data
# - Managing user settings
# - Managing user documents
# - Managing user summaries
# - Managing user LaTeX files
# - Managing user audio files
# - Managing user research data
# - Managing user document data (TBC)

# TODO: Review and test the user class and management functions

import os
import json
import time
from dataclasses import dataclass, asdict, field

# Create User class

@dataclass
class User:
    name: str
    id: str
    email: str
    creation_date: str
    documents: dict = field(default_factory=dict)
    summaries: dict = field(default_factory=dict)
    latex_files: dict = field(default_factory=dict)
    audio_files: dict = field(default_factory=dict)
    research_data: dict = field(default_factory=dict)
    document_data: dict = field(default_factory=dict)
    settings: dict = field(default_factory=dict)

    def save_user(self):
        '''Save the user data to a JSON file'''
        with open(f"users/{self.id}/user_data.json", "w", encoding="utf-8") as file:
            file.write(json.dumps(asdict(self)))

    def delete_user(self):
        '''Delete the user and all associated data'''
        os.remove(f"users/{self.id}/user_data.json")
        os.rmdir(f"users/{self.id}")

    def add_document(self, title, text):
        '''Add a document to the user's documents'''
        self.documents[title] = text

    def add_summary(self, title, text):
        '''Add a summary to the user's summaries'''
        self.summaries[title] = text

    def add_latex_file(self, title, text):
        '''Add a LaTeX file to the user's LaTeX files'''
        self.latex_files[title] = text

    def add_audio_file(self, title, path):
        '''Add an audio file to the user's audio files'''
        self.audio_files[title] = path

    def add_research_data(self, data):
        '''Add research data to the user's research data'''
        self.research_data = data

    def add_document_data(self, data):
        '''Add document data to the user's document data'''
        self.document_data = data

    def update_settings(self, settings):
        '''Update the user's settings'''
        self.settings = settings

# Functions for managing users

def create_user(name, email):
    '''Create a new user'''
    user_id = str(int(time.time()))
    creation_date = time.strftime("%Y-%m-%d %H:%M:%S")
    user = User(name, user_id, email, creation_date)
    os.mkdir(f"users/{user_id}")
    user.save_user()
    return user

def load_user(user_id):
    '''Load an existing user'''
    with open(f"users/{user_id}/user_data.json", "r", encoding="utf-8") as file:
        user_data = json.load(file)
    user = User(**user_data)
    return user

def save_user(user):
    '''Save the user data to a JSON file'''
    user.save_user()

def delete_user(user):
    '''Delete the user and all associated data'''
    user.delete_user()

def add_document(user, title, text):
    '''Add a document to the user's documents'''
    user.add_document(title, text)
    user.save_user()

def add_summary(user, title, text):
    '''Add a summary to the user's summaries'''
    user.add_summary(title, text)
    user.save_user()


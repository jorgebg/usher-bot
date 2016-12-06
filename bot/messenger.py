# -*- coding: utf-8 -*-

import httplib2
import logging
import os
import random
import re
import yaml

from apiclient import discovery
from oauth2client import client
from stemming.porter2 import stem

logger = logging.getLogger(__name__)

config = yaml.load(open("config.yml", 'r'))

def count(term, text):
    return len(re.findall(term, text, re.I))

def score(text, team):
    score = 0
    for term in team['Terms'].split('\n'):
        score += count(term, text)
        logger.info('term ' + term + " score: " + str(score))
    for term in team['Responsibilities'].split('\n'):
        score += count(term, text)
        logger.info('resp ' + term + " score: " + str(score))
    return score
        
def tx(d, s):
    x = d.get(s)
    if x == None:
        return ''
    else :
        return x

def find_team(teams, text):
    scores = []
    for team in teams:
        s = score(text, team)
        logger.info(team['Name'] + " score: " + str(s))
        scores.append({'score': s, 'team': team})

    scores = sorted(scores, key=lambda i: i['score'], reverse=True)

    if scores[0]['score'] == 0:
        #print text
        return 'nomatch'

    if scores[0]['score'] == scores[1]['score']:
        return 'unclear'
    else:
        return scores[0]['team']

class Messenger(object):
    def __init__(self, slack_clients):
        self.clients = slack_clients
        self.channels = self.clients.rtm.api_call("channels.list")

        creds = os.getenv("SHEETS_CREDS", "None")
        logging.info("SHEETS_CREDS {}".format(os.getenv("SHEETS_CREDS", "None")))
        credentials = client.Credentials.new_from_json(creds)

        self.http = credentials.authorize(httplib2.Http())

        self.teams = self.load_config()


    def load_config(self):
        discoveryUrl = ('https://sheets.googleapis.com/$discovery/rest?'
                        'version=v4')
        service = discovery.build('sheets', 'v4', http=self.http,
                                discoveryServiceUrl=discoveryUrl)
    
        spreadsheetId = '14FvIGbgO4iz6ys4vxhRPvQ7UFpdBqSeL55Cn8E3oPqE'

        rangeName = 'Teams!' + 'A1:J1'
        result = service.spreadsheets().values().get(
            spreadsheetId=spreadsheetId, range=rangeName).execute()
        titles = result.get('values', [])
    
        logging.info(titles);
    
        rangeName = 'Teams!' + 'A2:J9'
        result = service.spreadsheets().values().get(
            spreadsheetId=spreadsheetId, range=rangeName).execute()
        values = result.get('values', [])
    
        logging.debug(values);

        teams = []
        for row in values:
            logging.debug(row)
            t = {}
            x = 0
            for title in titles[0]:
                t[title] = row[x]
                x = x + 1
            teams.append(t)

        logging.debug(teams);
        return teams

     
    def send_message(self, channel_id, msg):
        # in the case of Group and Private channels, RTM channel payload is a complex dictionary
        if isinstance(channel_id, dict):
            channel_id = channel_id['id']
        logger.debug('Sending msg: %s to channel: %s' % (msg, channel_id))
        channel = self.clients.rtm.server.channels.find(channel_id)
        channel.send_message(msg)

    def write_help_message(self, channel_id):
        bot_uid = self.clients.bot_user_id()
        txt = '{}\n{}'.format(
            "I'm a friendly Slack bot written in Python.  I'll *_respond_* to the following commands:",
            "> `who` knows about _something_")
        self.send_message(channel_id, txt)

    def write_team(self, channel_id, msg_txt):
        #msg_txt = " ".join(map(lambda w: stem(w), msg_txt.split()))

        self.teams = self.load_config()

        txt = self._team(channel_id, msg_txt)
        self.send_message(channel_id, txt)

    def _team(self, channel_id, msg_txt):
        team = find_team(self.teams, msg_txt)
        if team == 'nomatch' :
            txt = "Sorry, I don't know!  Blame jake the dog."
        elif team == 'unclear' :
            txt = "I'am not sure, but I will get it for you someday."
        else:
            logging.info("Team: " + str(team))
            name = team['Name']
            channel = team['Slack channel']
            txt = name + " owns this. See: `<" + self.lookup_channel_id(channel) + ">`"
        return txt

    def lookup_channel_id(self, channel):
        for x in self.channels['channels']:
            if x['name'] == channel:
                return '#' + x['id']
        return "Unknown" # should assert this can't happen

    def write_prompt(self, channel_id):
        bot_uid = self.clients.bot_user_id()
        txt = "I'm sorry, I didn't quite understand... Can I help you? (e.g. `<@" + bot_uid + "> help`)"
        self.send_message(channel_id, txt)

    def write_error(self, channel_id, err_msg):
        txt = ":face_with_head_bandage: my maker didn't handle this error very well:\n>```{}```".format(err_msg)
        self.send_message(channel_id, txt)

    def demo_attachment(self, channel_id):
        txt = "Beep Beep Boop is a ridiculously simple hosting platform for your Slackbots."
        attachment = {
            "pretext": "We bring bots to life. :sunglasses: :thumbsup:",
            "title": "Host, deploy and share your bot in seconds.",
            "title_link": "https://beepboophq.com/",
            "text": txt,
            "fallback": txt,
            "image_url": "https://storage.googleapis.com/beepboophq/_assets/bot-1.22f6fb.png",
            "color": "#7CD197",
        }
        self.clients.web.chat.post_message(channel_id, txt, attachments=[attachment], as_user='true')

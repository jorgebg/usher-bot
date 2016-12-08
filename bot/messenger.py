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
    for term in team['Name'].split('\n'):
        score += count(term, text)
        logger.info('term ' + term + " score: " + str(score))
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

def find_teams(teams, text, m):
    scores = []
    for team in teams:
        s = score(text, team)
        logger.info(team['Name'] + " score: " + str(s))
        scores.append({'score': s, 'team': team})

    scores = sorted(scores, key=lambda i: i['score'], reverse=True)
    scores = [s for s in scores if s['score'] != 0]

    if len(scores) == 0 or scores[0]['score'] == 0:
        #print text
        return 'nomatch'

    if m == 1:
        if len(scores) > 1 and scores[0]['score'] == scores[1]['score']:
            return 'unclear'
        else:
            return scores[0]['team']
    else:
        return list(map(lambda s: s['team'], scores[0:m]))


def find_member_teams(teams, text):
    teams = []
    for token in text.split():
        for team in teams:
            if token in team['Individuals'].split('\n'):
                teams.append(team)
                logger.info(team['Name'] + " has member " + str(token))
    return teams


class Messenger(object):
    def __init__(self, slack_clients):
        self.clients = slack_clients
        self.channels = self.clients.rtm.api_call("channels.list")
        self.users = self.clients.rtm.api_call("users.list")

        creds = os.getenv("SHEETS_CREDS", "None")
        logging.info("SHEETS_CREDS {}".format(os.getenv("SHEETS_CREDS", "None")))
        credentials = client.Credentials.new_from_json(creds)

        self.http = credentials.authorize(httplib2.Http())

        self.load_config()


    def load_config(self):
        discoveryUrl = ('https://sheets.googleapis.com/$discovery/rest?'
                        'version=v4')
        service = discovery.build('sheets', 'v4', http=self.http,
                                discoveryServiceUrl=discoveryUrl)
    
        spreadsheetId = '14FvIGbgO4iz6ys4vxhRPvQ7UFpdBqSeL55Cn8E3oPqE'

        ## TODO: handle auth failure

        rangeName = 'Data!A1:A1'
        result = service.spreadsheets().values().get(
            spreadsheetId=spreadsheetId, range=rangeName).execute()
        data = result.get('values', [])
        logging.info(data[0])
    
        # TODO: dynamic cols

        rangeName = 'Teams!' + 'A1:K1'
        result = service.spreadsheets().values().get(
            spreadsheetId=spreadsheetId, range=rangeName).execute()
        titles = result.get('values', [])
    
        logging.info(titles);
    
        numRows = data[0][0]
        rangeName = 'Teams!' + 'A2:K' + numRows
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
                t[title] = row[x].strip()
                x = x + 1
            teams.append(t)

        logging.debug(teams);

        self.teams = teams

     
    def send_message(self, channel_id, msg):
        # in the case of Group and Private channels, RTM channel payload is a complex dictionary
        if isinstance(channel_id, dict):
            channel_id = channel_id['id']
        logger.debug('Sending msg: %s to channel: %s' % (msg, channel_id))
        channel = self.clients.rtm.server.channels.find(channel_id)
        channel.send_message(msg)

    def write_help_message(self, channel_id):
        bot_uid = self.clients.bot_user_id()
        txt = '{}\n{}\n{}\n{}\n{}\n{}'.format(
            "I'm a friendly Slack bot written in Python.  I'll *_respond_* to the following commands:",
            "> `describe` _team_",
            "> `who is on` a _team_",
            "> `who leads` a _team_",
            "> `who` knows about _something_",
            "> `team` of _someone_",
            "> `list` (all teams)")
        self.send_message(channel_id, txt)
        self.send_message(channel_id, "I can be configured by editing https://docs.google.com/a/udemy.com/spreadsheets/d/14FvIGbgO4iz6ys4vxhRPvQ7UFpdBqSeL55Cn8E3oPqE/edit?usp=sharing ; you may need to tell me about the change by sending me a `load` message as well.")

    def write_all_teams(self, channel_id, msg_txt):
        #msg_txt = " ".join(map(lambda w: stem(w), msg_txt.split()))
        #self.load_config()
        txt = self._all_teams(channel_id, msg_txt)
        self.send_message(channel_id, txt)

    def write_members(self, channel_id, msg_txt):
        #msg_txt = " ".join(map(lambda w: stem(w), msg_txt.split()))
        #self.load_config()
        txt = self._members(channel_id, msg_txt)
        self.send_message(channel_id, txt)

    def write_managers(self, channel_id, msg_txt):
        #msg_txt = " ".join(map(lambda w: stem(w), msg_txt.split()))
        #self.load_config()
        txt = self._managers(channel_id, msg_txt)
        self.send_message(channel_id, txt)

    def write_team(self, channel_id, msg_txt):
        #msg_txt = " ".join(map(lambda w: stem(w), msg_txt.split()))
        #self.load_config()
        txt = self._team(channel_id, msg_txt)
        self.send_message(channel_id, txt)

    def write_team_details(self, channel_id, msg_txt):
        #msg_txt = " ".join(map(lambda w: stem(w), msg_txt.split()))
        #self.load_config()
        txt = self._team_details(channel_id, msg_txt)
        self.send_message(channel_id, txt)

    def write_member_team(self, channel_id, msg_txt):
        txt = self._member_team(channel_id, msg_txt)
        self.send_message(channel_id, txt)

    def _all_teams(self, channel_id, msg_txt):
        return "Teams: \n\t" + "\n\t".join(list(map(lambda p: p['Name'], self.teams)))

    def _members(self, channel_id, msg_txt):
        team = find_teams(self.teams, msg_txt, 1)
        if team == 'nomatch' :
            txt = "Sorry, I don't know!  Blame jake the dog."
        elif team == 'unclear' :
            txt = "I am not sure, but I will get it for you someday. In the meantime, can I get you a latte?"
        else:
            logging.info("Team: " + str(team))
            name = team['Name']
            peeps = team['Individuals'].split('\n')
            logging.info(peeps)
            ids = list(map(lambda p: "<" + str(self.lookup_user_id(p)) + ">", peeps))
            txt = name + " has: \n\t" + "\n\t".join(ids)
            logging.info(txt)
        return txt

    def _managers(self, channel_id, msg_txt):
        team = find_teams(self.teams, msg_txt, 1)
        if team == 'nomatch' :
            txt = "Sorry, I don't know!  Blame jake the dog."
        elif team == 'unclear' :
            txt = "I am not sure, but I will get it for you someday. In the meantime, can I get you a latte?"
        else:
            logging.info("Team: " + str(team) + "is lead by: ")
            name = team['Name']
            peeps = team['Managers'].split('\n')
            logging.info(peeps)
            ids = list(map(lambda p: "<" + str(self.lookup_user_id(p)) + ">", peeps))
            txt = name + " is managed by: \n\t" + "\n\t".join(ids)
            logging.info(txt)
        return txt

    def _team(self, channel_id, msg_txt):
        teams = find_teams(self.teams, msg_txt, 3)
        if teams == 'nomatch' :
            txt = "Sorry, I don't know!  Blame jake the dog."
        elif teams == 'unclear' :
            txt = "I am not sure, but I will get it for you someday. Try listening to this: https://www.youtube.com/watch?v=i57FXvL8txY"
        else:
            n = len(teams)
            txts = []

            for team in teams:
                logging.info("Team: " + str(team))
                name = team['Name']
                channel = team['Slack channel']
                txt = name + " covers this. See: `<" + self.lookup_channel_id(channel) + ">`."
                txts.append(txt)

            if n == 1:
                txt = txts[0]
            else:
                txt = " Also ".join( txts )

        return txt

    def _team_details(self, channel_id, msg_txt):
        team = find_teams(self.teams, msg_txt, 1)
        if team == 'nomatch' :
            txt = "Sorry, I don't know!  Blame jake the dog. Or you can listen https://www.youtube.com/watch?v=4WjapUvIWgs"
        elif team == 'unclear' :
            txt = "I am not sure, but I will get it for you someday. Or you can listen https://www.youtube.com/watch?v=4WjapUvIWgs"
        else:
            logging.info("Team: " + str(team))
            name = team['Name']
            peeps = team['Managers'].split('\n')
            ids = list(map(lambda p: "<" + str(self.lookup_user_id(p)) + ">", peeps))
            mgrs = " ".join(ids)
            channel = self.lookup_channel_id(team['Slack channel'])
            board = team['Trello Board']
            wiki = team['Wiki home page']
            txt = "*{}*, Lead by: {}, channel: `<{}>`, Trello Board: {}, Wiki home: {}".format(name, mgrs, channel, board, wiki)
        return txt

    def _member_team(self, channel_id, msg_txt):
        teams = find_member_teams(self.teams, msg_txt)
        if not teams:
            txt = "Sorry, I don't know!  Blame jorge the human."
        else:
            txt = "Teams: " + ', '.join([team['Name'] for team in teams])
            logging.info(txt)
        return txt

    def lookup_user_id(self, user):
        for x in self.users['members']:
            if x['name'] == user:
                return '@' + x['id']
        return '@' + user # should assert this can't happen

    def lookup_channel_id(self, channel):
        for x in self.channels['channels']:
            if x['name'] == channel:
                return '#' + x['id']
        return "#" + channel # should assert this can't happen

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

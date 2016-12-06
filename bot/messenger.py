# -*- coding: utf-8 -*-

import logging
import random
import re
import yaml

logger = logging.getLogger(__name__)

config = yaml.load(open("config.yml", 'r'))

def count(term, text):
    return len(re.findall(term, text, re.I))

def score(text, cat):
    score = 0
    for term in cat['terms']:
        score += count(term, text)
    return score
        
def tx(d, s):
    x = d.get(s)
    if x == None:
        return ''
    else :
        return x

def categorize(text):
    scores = []
    for cat in config['categories']:
        name = cat.iterkeys().next()
        s = score(text, cat.itervalues().next())
        scores.append({'name': name, 'score': s, 'cat': cat})

    scores = sorted(scores, key=lambda i: i['score'], reverse=True)

    if scores[0]['score'] == 0:
        print text
        return 'nomatch'

    if scores[0]['score'] == scores[1]['score']:
        return 'unclear'
    else:
        return scores[0]

class Messenger(object):
    def __init__(self, slack_clients):
        self.clients = slack_clients

    def send_message(self, channel_id, msg):
        # in the case of Group and Private channels, RTM channel payload is a complex dictionary
        if isinstance(channel_id, dict):
            channel_id = channel_id['id']
        logger.debug('Sending msg: %s to channel: %s' % (msg, channel_id))
        channel = self.clients.rtm.server.channels.find(channel_id)
        channel.send_message(msg)

    def write_help_message(self, channel_id):
        bot_uid = self.clients.bot_user_id()
        txt = '{}\n{}\n{}\n{}'.format(
            "I'm a friendly Slack bot written in Python.  I'll *_respond_* to the following commands:",
            "> `hi <@" + bot_uid + ">` - I'll respond with a randomized greeting mentioning your user. :wave:",
            "> `how <@" + bot_uid + ">` - some other stuff we need to put here",
            "> `<@" + bot_uid + "> joke` - I'll tell you one of my finest jokes, with a typing pause for effect. :laughing:",
            "> `<@" + bot_uid + "> attachment` - I'll demo a post with an attachment using the Web API. :paperclip:")
        self.send_message(channel_id, txt)

    def write_greeting(self, channel_id, user_id):
        greetings = ['Hi', 'Hello', 'Nice to meet you', 'Howdy', 'Salutations']
        txt = '{}, <@{}>!'.format(random.choice(greetings), user_id)
        self.send_message(channel_id, txt)

    def post_answer(self, channel_id, msg_txt):
        txt = self._answer(channel_id, msg_txt)
        # chat.postMessage(self, channel_id, txt)

    def write_answer(self, channel_id, msg_txt):
        txt = self._answer(channel_id, msg_txt)
        self.send_message(channel_id, txt)

    def _answer(self, channel_id, msg_txt):
        match = categorize(msg_txt)
        if match == 'nomatch' :
            txt = "Sorry, I don't know!  Blame jake the dog"
        elif match == 'unclear' :
            txt = "I'm not sure, but I will get it for you someday."
        else:
            cat = match['cat']
            name = match['name']
            obj = cat[name]
            channel = obj['channel']
            n = obj['board'] # should be fullname or something like that
            txt = n + " owns this. See: #" + channel

        return txt

    def write_prompt(self, channel_id):
        bot_uid = self.clients.bot_user_id()
        txt = "I'm sorry, I didn't quite understand... Can I help you? (e.g. `<@" + bot_uid + "> help`)"
        self.send_message(channel_id, txt)

    def write_joke(self, channel_id):
        question = "Why did the python cross the road?"
        self.send_message(channel_id, question)
        self.clients.send_user_typing_pause(channel_id)
        answer = "To eat the chicken on the other side! :laughing:"
        self.send_message(channel_id, answer)


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

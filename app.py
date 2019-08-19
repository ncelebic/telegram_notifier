from flask import Flask, render_template, request, Response, jsonify, redirect
from flask_htpasswd import HtPasswdAuth
from pathlib import Path
import yaml
import sqlite3
import telegram.error
import uuid
import logging

from pprint import pprint

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                    level=logging.INFO)

app = Flask(__name__)
app.config['DEBUG'] = True

cfg = {}
config_file = Path("config.yml")
if config_file.is_file():
    with open("config.yml", "r") as yamlfile:
        yamlcfg = yaml.load(yamlfile, Loader=yaml.BaseLoader)

cfg['datadir'] = yamlcfg['datadir']
dbfile = cfg['datadir'] + "/telegramdb"

app.config['FLASK_HTPASSWD_PATH'] = cfg['datadir'] + "/htpass"

htpasswd = HtPasswdAuth(app)


@app.route('/')
@htpasswd.required
def index(user):
    datalisting = None
    db = sqlite3.connect(dbfile)
    cursor = db.cursor()
    try:
        cursor.execute('''CREATE TABLE IF NOT EXISTS apikeys (
                            name TEXT,
                            description TEXT, 
                            apikey TEXT, 
                            token TEXT,
                            chatid TEXT,
                            owner TEXT)
                            ''')
    except sqlite3.OperationalError as e:
        print(e)
        exit(1)
    try:
        cursor.execute('''SELECT name, description, apikey, token, chatid
                            FROM apikeys
                            WHERE owner = ?''', (user,))
        datalisting = cursor.fetchall()
        pprint(datalisting)
    except sqlite3.OperationalError as e:
        print(e)
        exit(1)
    print("YAY")
    db.close()
    return render_template('index.html', datalisting=datalisting)


@app.route('/apigen', methods=['GET', 'POST'])
@htpasswd.required
def api_gen(user):
    if request.method == 'POST':
        db = sqlite3.connect(dbfile)
        cursor = db.cursor()
        print("I see a form")
        name = request.form['name']
        description = request.form['description']
        token = request.form['token']
        chatid = request.form['chatid']
        apikey = str(uuid.uuid1())
        if not dupecheck(token, chatid):
            try:
                cursor.execute('''INSERT INTO apikeys(
                                name, description, apikey, token, chatid, owner)
                                VALUES (?, ?, ?, ?, ?, ?)''',
                               (name, description, apikey, token, chatid, user))
                db.commit()
                db.close()
            except sqlite3.Error as e:
                print("sqlite insert error")
                pprint(e)
                print("user: %s\ndesc: %s\ntoken: %s\n" % (name, description, token))
            return redirect("/")
        else:
            print("Duplicate found for Token/ChatID")
            return "Duplicate found for Token/ChatID %s / %s" % (token, chatid)
    else:

        return render_template('apigen.html')


@app.route('/deleterecord', methods=['POST'])
@htpasswd.required
def deleterecord(user):
    apikey = request.form['apikey']
    if request.form['confirm'] == "true":
        print("confirmed to delete %s" % apikey)
        try:
            db = sqlite3.connect(dbfile)
            cursor = db.cursor()
            cursor.execute('''DELETE 
                                    FROM apikeys
                                    WHERE apikey = ? AND owner = ?''', (apikey, user,))
            db.commit()
            db.close()
            return redirect("/")
        except sqlite3.Error as e:
            print("sqlite delete error")
            pprint(e)
            return Response(status=400)
    else:
        return render_template('confirmdelete.html', apikey=apikey)


@app.route('/testtoken', methods=['POST'])
def testtoken():
    token = request.form['token']
    chatid = request.form['chatid']
    logging.info("testing with token %s" % token)
    if len(token) < 1:
        print("Nothing to test")
        return Response(status=401)
    result = send_telegram_message(token, chatid, "Testing")
    return jsonify(status=result)


@app.route('/api/v1', methods=['POST'])
def api():
    # pprint(request.form)
    apikey = request.args['key']
    message = request.args['message']
    db = sqlite3.connect(dbfile)
    cursor = db.cursor()
    cursor.execute('''SELECT token, chatid
                                FROM apikeys
                                WHERE apikey = ?''', (apikey,))
    rows = cursor.fetchall()
    if not len(rows) == 1:
        return Response(status=401)
    token = rows[0][0]
    chatid = rows[0][1]
    result = send_telegram_message(token, chatid, message)
    if result == "OK":
        return Response(status=200)
    else:
        return Response(status=400)


def dupecheck(token, chatid):
    db = sqlite3.connect(dbfile)
    cursor = db.cursor()
    cursor.execute('''SELECT name
                        FROM apikeys
                        WHERE token = ? AND chatid = ?''', (token, chatid, ))
    rows = cursor.fetchall()
    if len(rows) > 0:
        print("Dupe!")
        db.close()
        return True
    else:
        db.close()
        return False


def send_telegram_message(token, chatid, message):
    try:
        bot = telegram.Bot(token=token)
        bot.send_message(chat_id=chatid, text=message)
        result = "OK"
    except telegram.error.InvalidToken:
        print("Bad Token")
        result = "Bad Token"
    except telegram.error.BadRequest as e:
        pprint(e.message)
        if "Chat not found" in e.message:
            print("Chat ID invalid")
        result = "Bad Chat ID"
    except telegram.error.Unauthorized as e:
        pprint(e.message)
        result = e.message
    return result


if __name__ == '__main__':
    app.run(host='0.0.0.0')

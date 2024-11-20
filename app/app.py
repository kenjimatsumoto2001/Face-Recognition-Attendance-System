from flask import Flask, request, redirect, render_template, flash, session, jsonify, url_for, send_file
from DBcm import UseDatabase
from werkzeug.utils import secure_filename
import os
import base64
import cv2
import face_recognition
import numpy as np
from flask_basicauth import BasicAuth
from PIL import Image
import io
import zipfile
import csv
from functools import wraps

app = Flask(__name__)
app.config['SECRET_KEY'] = 'secret_key'

app.config["dbconfig"]={'host': 'mariadb',
                        'user': 'vsearch',
                        'password': 'vsearchpasswd',
                        'database': 'facereader',}

# 認証情報の設定
app.config['BASIC_AUTH_USERNAME'] = 'user'
app.config['BASIC_AUTH_PASSWORD'] = 'password'
basic_auth = BasicAuth(app)

#撮影写真の相対パス
app.config['KNOWN_FACES_FOLDER'] = 'static/img_faces'

def authenticated(func):
    @wraps(func)
    def decorated_function(*args, **kwargs):
        if 'authenticated' not in session:
            return basic_auth.challenge()
        return func(*args, **kwargs)
    return decorated_function


######################################################################################
#以下ログイン(登録済み)
#以下ログイン(登録済み)
#flagがtrueならwelcome.htmlに画面遷移, falseは/login(GET)を呼ぶ
@app.route('/')
def index():
    if "flag" in session and session["flag"]:
        return render_template('welcome.html', username=session["username"])
    return redirect('/login')

#flagがtrueなら/welcome, false はlogin.html(学籍番号入力画面)に画面遷移
@app.route('/login', methods=['GET'])
def login():
    if 'flag' in session and session['flag']:
        return redirect('/welcome')
    return render_template('login.html')

#login.html(学籍番号入力画面)で入力された情報を獲得.
@app.route('/login', methods=['POST'])
def login_post():
    studentnumber = request.form["studentnumber"]
    #入力情報をDBと参照し, DBと一致がなければsession["flag"]にfalseを返し, 一致すればsession["flag"]にTrueを返す.
    with UseDatabase(app.config["dbconfig"]) as cursor:
        SQL = "SELECT * FROM Userlist WHERE studentid = {} ;".format(studentnumber)
        cursor.execute(SQL)
        data = cursor.fetchall()
        #以下はDBと一致しない時の処理
        if data == []:
            flash('学籍番号が間違っているか登録されていません','ng')
            session['flag'] = False
        
        #以下はDBと一致した時の処理
        else:
            session["flag"] = True
            session['studentnumber'] = data[0][0]
            session["username"] = data[0][1]
            SQL = "INSERT INTO Attendance values(null, {}, '{}', now());".format(session['studentnumber'], session["username"] )
            cursor.execute(SQL)

        #sessin["flag"]がTrueの時, welcome.htmlに画面遷移. 違った場合は/login(GET)を呼ぶ. 
        if session["flag"]:
            return render_template('welcome.html', studentnumber=session["studentnumber"], username=session["username"])
        else:
            return redirect('/login')

#flagがtrueならwelcome.htmlに画面遷移, falseは/login(GET)を呼ぶ
@app.route('/welcome')
def welcome():
    if "flag" in session and session["flag"]:
        return render_template('welcome.html', username=session["username"])
    return redirect('/login')

@app.route('/smartphone_login')
def smartphone_login():
    return render_template('login_smartphone.html')
    
######################################################################################
#以下新規登録(流れはログインと類似)
#login.htmlから呼び出されている


#flagがtrueならwelcome.htmlに画面遷移, falseは/new_account_create(GET)を呼ぶ
@app.route('/new_account')
def new_account():
    if "flag" in session and session["flag"]:
        return render_template('new_account_welcome.html', new_studentnumber=session["new_studentnumber"], new_username=session["new_username"])
    return redirect('/new_account_create')

#flagがtrueなら/welcome, false はnew_account.html(新規登録)に画面遷移
@app.route('/new_account_create', methods=['GET'])
def new_account_create():
    if 'flag' in session and session['flag']:
        return redirect('/new_account_welcome')
    return render_template('new_account.html')

#new_account.html(新規登録)で入力された情報を獲得.
#もし学生証番号が既に登録されてた場合, Flagにfalseを返す.　登録されていない時,入力された学生証番号と氏名をsessionにいれ, 入力確認画面に遷移
@app.route('/new_account_create', methods=['POST'])
def new_account_create_post():
    new_studentnumber =request.form["new_studentnumber"]
    new_username = request.form["new_username"]
    with UseDatabase(app.config["dbconfig"]) as cursor:
        SQL = "SELECT * FROM Userlist WHERE studentid = {} ;".format(new_studentnumber)
        cursor.execute(SQL)
        data = cursor.fetchall()
        #以下はDBに登録がなかった場合の処理
        if data == []:
            session["new_studentnumber"] = new_studentnumber
            session["new_username"] = new_username
            session["flag"] = True

        #以下はDBに登録が既にある場合の処理
        else: 
            flash('学籍番号はすでに登録されています','ng')
            session['flag'] = False

    if "flag" in session and session["flag"]:
        return render_template('new_account_face_reader.html', new_studentnumber=session["new_studentnumber"], new_username=session["new_username"])
    return redirect('/new_account_create')

#入力確認画面でOKを押した時の動作. DBの新規登録と, 出席登録をしている.
@app.route('/new_account_complete')
def new_account_complete():
    if "flag" in session and session["flag"]:
        with UseDatabase(app.config["dbconfig"]) as cursor:
            SQL = "INSERT INTO Userlist values({}, '{}');".format(session['new_studentnumber'], session["new_username"] )
            cursor.execute(SQL)

            SQL = "INSERT INTO Attendance values(null, {}, '{}', now());".format(session['new_studentnumber'], session["new_username"] )
            cursor.execute(SQL)
        # 顔認証データの再読み込み
        load_known_faces()

        return render_template('new_account_welcome.html', new_studentnumber=session["new_studentnumber"], new_username=session["new_username"])
    return redirect('/new_account_create')

@app.route('/new_account_re_enter')
def new_account_re_enter():
    # Generate filename based on the student number and username in session
    filename = f"{session['new_studentnumber']}_{session['new_username']}.jpg"

    # Define the path of the file
    path = os.path.join(app.config['KNOWN_FACES_FOLDER'], filename)

    # Check if file exists and remove it
    if os.path.exists(path):
        os.remove(path)

    # Reset session data
    session.pop('new_studentnumber', None)
    session.pop('username', None)
    session.pop("flag", None)
    session["new_studentnumber"] = None
    session["new_username"] = None
    session["flag"] = False

    return redirect("/new_account_create")
#flagがtrueならnew_account_welcome.htmlに画面遷移, falseは/new_account_create(GET)を呼ぶ
@app.route('/new_account_welcome')
def new_account_welcome():
    if "flag" in session and session["flag"]:
        return render_template('new_account_welcome.html', new_studentnumber=session["new_studentnumber"], new_username=session["new_username"])
    return redirect('/new_account_create')


##########################################################################################################################
#これは顔認証

@app.route('/register', methods=['POST'])
def register():
    # Get the image data from the request body
    image_data = request.json['image']

    # Remove header from image data
    image_data = image_data.split(',', 1)[1]

    # Convert base64 image to bytes
    image_bytes = base64.b64decode(image_data)

    # Generate a filename based on the student number and username in session
    filename = f"{session['new_studentnumber']}_{session['new_username']}.jpg"

    # Save the image in the known_faces folder
    with open(os.path.join(app.config['KNOWN_FACES_FOLDER'], filename), 'wb') as f:
        f.write(image_bytes)

    # Store the image filename in session
    session['image_filename'] = filename

    # return the message instead of redirecting
    return jsonify({'message': 'Registered successfully!', 'filename': filename})



@app.route('/new_account_check', methods=['GET'])
def new_account_check_get():
    image_filename = url_for('static', filename='img_faces/' + session.get('image_filename'))
    return render_template('new_account_check.html', 
                           new_studentnumber=session.get('new_studentnumber'), 
                           new_username=session.get('new_username'),
                           image_filename= image_filename)



known_faces = {"encodings": [], "names": []}
def load_known_faces():
    for filename in os.listdir('static/img_faces'):
        if filename.endswith(".jpg"):
            image = face_recognition.load_image_file(os.path.join('static/img_faces', filename))
            face_encodings = face_recognition.face_encodings(image)
            if len(face_encodings) > 0:  # If a face is found in the image
                known_faces["encodings"].append(face_encodings[0])
                known_faces["names"].append(filename.split('.')[0])  # Assuming the filename without extension is the name

load_known_faces()

@app.route('/verify', methods=['POST'])
def verify():
    # 既知の顔エンコーディングと名前をグローバル変数から取得
    known_face_encodings = known_faces["encodings"]
    known_face_names = known_faces["names"]

    # リクエストから画像データを取得
    image_data = request.get_json()['image']

    # ヘッダーを削除して、base64エンコードされた画像データをデコード
    image_data = image_data.split(',', 1)[1]
    image_bytes = base64.b64decode(image_data)
    nparr = np.frombuffer(image_bytes, np.uint8)
    img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

    # 画像をRGBに変換（face_recognitionが使用する色空間）
    rgb_img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)

    # 現在のフレームの顔の位置とエンコーディングを検出
    face_locations = face_recognition.face_locations(rgb_img)
    face_encodings = face_recognition.face_encodings(rgb_img, face_locations)

    names = []
    for face_encoding in face_encodings:
        # See if the face is a match for the known face(s) この閾値を変更すると精度が変わる. 低い方が厳しくなる。
        matches = face_recognition.compare_faces(known_face_encodings, face_encoding,  tolerance=0.35)
        name = "Unknown"

        # Use the known face with the smallest distance to the new face
        if True in matches:
            first_match_index = matches.index(True)
            name = known_face_names[first_match_index]

        names.append(name)

    # 一致する名前（または"Unknown"）を含むレスポンスを返す
    return jsonify({'message': 'Processed successfully!', 'name': names[0] if names else "Unknown"})


@app.route('/ok')
def ok():
    name = request.args.get('name')
    studentnumber = name.split('_')[0]
    with UseDatabase(app.config["dbconfig"]) as cursor:
        SQL = "SELECT * FROM Userlist WHERE studentid = {} ;".format(studentnumber)
        cursor.execute(SQL)
        data = cursor.fetchall()
    
        # ユーザー情報をセッションに保存
        session["flag"] = True
        session['studentnumber'] = data[0][0]
        session["username"] = data[0][1]
    
        # 出席情報をDBに保存
        SQL = "INSERT INTO Attendance values(null, {}, '{}', now());".format(session['studentnumber'], session["username"])
        cursor.execute(SQL)

        if session["flag"]:
            return render_template('welcome.html', studentnumber=session["studentnumber"], username=session["username"])
        else:
            return redirect('/login')
        
################################################################################################################################################
@app.route('/attendance')
@basic_auth.required 
def attendance():
    session['authenticated'] = True
    data = []
    with UseDatabase(app.config["dbconfig"]) as cursor:
        attendancelist = "SELECT * FROM Attendance"
        cursor.execute(attendancelist)
        attendancelist = cursor.fetchall()
        for item in attendancelist:
            number = item[0]
            studentnumber = item[1]
            name = item[2]
            date = item[3]
            photo = None  # set default as None

            for filename in os.listdir('static/img_faces/'):
                split_filename = filename.split('_')  # split the filename
                
                if split_filename[0] == str(studentnumber):  # check if it matches the student number
                    photo = filename  # if it does, save the filename
                    break

            data.append((studentnumber, name, date, number, photo))
        return render_template('attendancelist.html', data = data)

@app.route('/attendance_count')
@authenticated
def attendance_count():
    data = []
    with UseDatabase(app.config["dbconfig"]) as cursor:
        attendancelist = "SELECT studentid, name, COUNT(*) AS count FROM Attendance GROUP BY studentid, name ORDER BY count DESC"
        cursor.execute(attendancelist)
        attendancelist = cursor.fetchall()
        for item in attendancelist:
            studentnumber = item[0]
            name = item[1]
            count = item[2]
            photo = None  # set default as None

            for filename in os.listdir('static/img_faces/'):
                split_filename = filename.split('_')  # split the filename
                
                if split_filename[0] == str(studentnumber):  # check if it matches the student number
                    photo = filename  # if it does, save the filename
                    break

            data.append((studentnumber, name, count, photo))
        return render_template('attendancelist_count.html', data = data)
    
@app.route('/attendance_delete_all')
def delete():
    with UseDatabase(app.config["dbconfig"]) as cursor:
        SQL = "truncate table Attendance;"
        cursor.execute(SQL)
    return render_template('attendancelist.html')

@app.route('/attendance_delete_one')
def attendance_delete_one():
    with UseDatabase(app.config["dbconfig"]) as cursor:
        deleteid = request.args.get('number')
        SQL = "DELETE FROM Attendance WHERE number = '{}';".format(deleteid)
        cursor.execute(SQL)
    
    data = []
    with UseDatabase(app.config["dbconfig"]) as cursor:
        attendancelist = "SELECT * FROM Attendance"
        cursor.execute(attendancelist)
        attendancelist = cursor.fetchall()
        for item in attendancelist:
            number = item[0]
            studentnumber = item[1]
            name = item[2]
            date = item[3]
            photo = None  # set default as None

            for filename in os.listdir('static/img_faces/'):
                split_filename = filename.split('_')  # split the filename
                
                if split_filename[0] == str(studentnumber):  # check if it matches the student number
                    photo = filename  # if it does, save the filename
                    break

            data.append((studentnumber, name, date, number, photo))
    return render_template('attendancelist.html', data = data)

def remove_face_from_known_faces(studentid):
    # 削除するユーザーの顔データを特定するために使う識別子を決定する
    # 例えば、ファイル名が学生IDを含む形式であると仮定
    target_prefix = f"{studentid}_"
    # 一致する名前のインデックスを見つける
    indices_to_remove = [i for i, name in enumerate(known_faces["names"]) if name.startswith(target_prefix)]
    # 該当するエントリを削除
    for index in sorted(indices_to_remove, reverse=True):
        known_faces["encodings"].pop(index)
        known_faces["names"].pop(index)

@app.route('/delete_Userlist')
def Delete_Userlist():
    try:
        with UseDatabase(app.config["dbconfig"]) as cursor:
            deleteid = request.args.get('studentID')
            # データベースからユーザーを削除
            SQL = "DELETE FROM Userlist WHERE studentid = '{}';".format(deleteid)
            cursor.execute(SQL)

            # 顔認証データからも該当ユーザーを削除
            remove_face_from_known_faces(deleteid)

            # 写真を削除
            for filename in os.listdir('static/img_faces/'):
                if filename.startswith(str(deleteid) + '_'):
                    os.remove(os.path.join('static/img_faces/', filename))

    except Exception as e:
        flash("出席一覧に同じ学生番号がいます。そちらから先に削除してください")
        return redirect('/Userlist')

    # ユーザーリストを再取得してテンプレートに渡す
    data = []
    with UseDatabase(app.config["dbconfig"]) as cursor:
        userlist_sql = "SELECT * FROM Userlist"
        cursor.execute(userlist_sql)
        userlist = cursor.fetchall()
        for item in userlist:
            studentnumber = item[0]
            name = item[1]
            data.append((studentnumber, name))
    return render_template('Userlist.html', data=data)
    

@app.route('/Userlist')
@authenticated
def list():
    data = []
    with UseDatabase(app.config["dbconfig"]) as cursor:
        attendancelist = "SELECT * FROM Userlist"
        cursor.execute(attendancelist)
        attendancelist = cursor.fetchall()
        for item in attendancelist:
            studentnumber = item[0]
            name = item[1]
            data.append((studentnumber, name))
        return render_template('Userlist.html', data = data)

@app.route('/export_data')
def export_data():
    # メモリ内にZIPファイルを作成
    memory_file = io.BytesIO()
    with zipfile.ZipFile(memory_file, 'w') as zf:
        # データベースの情報をCSVファイルとして書き込む
        with UseDatabase(app.config["dbconfig"]) as cursor:
            SQL = "SELECT * FROM Attendance"
            cursor.execute(SQL)
            attendancelist = cursor.fetchall()
            # CSVファイルをUTF-8エンコードで作成
            csv_file = io.StringIO()
            csv_writer = csv.writer(csv_file)
            csv_writer.writerow(['番号', '学生番号', '氏名', '日付'])  # CSVのヘッダー
            for item in attendancelist:
                csv_writer.writerow(item)
            # CSVファイルをバイナリモードでZIPに追加
            zf.writestr('attendance_data.csv', csv_file.getvalue().encode('utf-8-sig'))

        # 画像ファイルをZIPに追加
        for filename in os.listdir(app.config['KNOWN_FACES_FOLDER']):
            filepath = os.path.join(app.config['KNOWN_FACES_FOLDER'], filename)
            zf.write(filepath, os.path.basename(filepath))

    memory_file.seek(0)
    # ZIPファイルをダウンロードとして送信
    return send_file(memory_file, download_name='出席簿.zip', as_attachment=True)

####################################################################################################################

#ログアウト, 全ての情報を消しておく
@app.route('/logout',methods=['POST'])
def logout():
    session.pop('new_studentnumber', None)
    session.pop('username', None)
    session.pop("flag", None)
    session["new_studentnumber"] = None
    session["new_username"] = None
    session["flag"] = False
    return redirect("/login")


#以下はheaderのhomeを押した時に対応
@app.route('/logout')
def logout_header():
    session.pop('new_studentnumber', None)
    session.pop('username', None)
    session.pop("flag", None)
    session["new_studentnumber"] = None
    session["new_username"] = None
    session["flag"] = False
    session.pop('authenticated', None)  # セッションをクリア
    return redirect("/login")

if __name__ == '__main__':
  app.run(debug=True)
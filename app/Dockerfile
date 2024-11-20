# ベースイメージ
FROM python:3.9.6

RUN mkdir /var/www
# workdirの指定
WORKDIR /var/www

# OpenCVの依存パッケージをインストール
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1-mesa-dev

# 依存Pythonライブラリ一覧コピー
COPY requirements.txt ./

# 依存Pythonライブラリインストール
RUN pip install --no-cache-dir -r requirements.txt
RUN pip install Flask-BasicAuth
CMD ["uwsgi","--ini","/var/www/uwsgi.ini"]
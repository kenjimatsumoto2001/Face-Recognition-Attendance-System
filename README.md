# Face-Recognition-Attendance-System

顔認識による出席管理システムを簡単にデプロイし、使用できるプロジェクトです。本プロジェクトはDockerを使用しているため、セットアップが簡単です。

# 使用方法

## 1. Dockerのインストール
Dockerがインストールされていない場合、以下のリンクからDocker Desktopをダウンロードしてインストールしてください:  
👉 [Docker Desktop ダウンロードページ](https://www.docker.com/ja-jp/products/docker-desktop/)

## 2. プロジェクトをクローン
ターミナルで次のコマンドを実行して、このリポジトリをローカルにクローンします。  
```bash
git clone https://github.com/your-username/Face-Recognition-Attendance-System.git
cd Face-Recognition-Attendance-System
```

## 3. Dockerの起動
以下のコマンドでDockerコンテナを起動します:
```bash
docker compose up -d
```
## 4. アプリケーションのアクセス
コンテナが正常に起動したら、以下のURLにアクセスしてシステムを利用できます:
[http://localhost:4232/login](http://localhost:4232/login)

## 4. 出席へのログイン方法
ユーザー名: user
パスワード: password

## 注意事項
・動作環境: 本プロジェクトはDockerが動作可能な環境（Windows, macOS, Linux）を前提としています
・パスワードの保護: デフォルトのパスワードをそのまま使用するのではなく、必要に応じてパスワードを変更してください。

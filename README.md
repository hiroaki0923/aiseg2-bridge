# aiseg2mqtt

AISEG2（Panasonic製エネルギーモニター）からデータを取得し、MQTT経由でHome Assistantに連携するブリッジツール。

## 機能

- AISEG2から電力使用量データを定期的に取得
- Home Assistant MQTT Discoveryによる自動認識
- 総量データ（使用量/購入量/売電量/発電量）の取得
- 回路別の電力使用量（kWh）の取得
- エラー時の自動リトライとロバストな実行
- 設定可能な実行間隔

## 必要要件

- Python 3.12以上
- AISEG2へのネットワークアクセス
- MQTTブローカー（Mosquittoなど）

## インストール

```bash
# リポジトリをクローン
git clone https://github.com/hiroaki0923/aiseg2mqtt.git
cd aiseg2mqtt

# 依存関係をインストール（uvを使用）
uv sync
```

## 設定

`.env`ファイルを作成し、環境変数を設定します。`.env.example`をコピーして編集することをお勧めします：

```bash
cp .env.example .env
# .envファイルを編集
```

設定項目：

```env
# AISEG2接続設定
AISEG_HOST=192.168.0.216
AISEG_USER=aiseg
AISEG_PASS=your_password

# MQTT接続設定
MQTT_HOST=127.0.0.1
MQTT_PORT=1883
MQTT_USER=mqtt_user
MQTT_PASS=mqtt_password
MQTT_PREFIX=homeassistant

# デバイス設定
DEVICE_ID=aiseg2-scrape
DEVICE_NAME=AISEG2 (Scraped)

# 実行間隔設定（オプション）
INTERVAL_SECONDS=300  # デフォルト: 300秒（5分）
MAX_CONSECUTIVE_ERRORS=10  # 最大連続エラー数
ERROR_RETRY_DELAY=60  # エラー後の待機時間（秒）
LOG_LEVEL=INFO  # ログレベル（DEBUG/INFO/WARNING/ERROR）
```

## 使い方

### 単発実行

データを1回だけ取得してMQTTに送信：

```bash
uv run aiseg2_publish.py
```

### 定期実行

指定した間隔で継続的にデータを取得：

```bash
uv run main.py
```

停止するには `Ctrl+C` を押してください。

### Discovery設定のクリーンアップ

Home AssistantのMQTT Discoveryで作成されたセンサーを削除：

```bash
uv run aiseg2_clean.py
```

## Docker での使用

### Docker Hub からイメージを使用（推奨）

```bash
# 最新版を使用
docker pull hiroaki0923/aiseg2mqtt:latest

# .envファイルを使用して実行
docker run --rm --env-file .env hiroaki0923/aiseg2mqtt:latest

# docker-composeを使用
cp docker-compose.yaml.example docker-compose.yaml
docker-compose up -d
```

### ローカルでイメージをビルド

```bash
docker build -t aiseg2mqtt .
docker run --rm --env-file .env aiseg2mqtt
```

### 単発実行

```bash
# データを1回だけ取得
docker run --rm --env-file .env hiroaki0923/aiseg2mqtt:latest uv run aiseg2_publish.py

# Discovery設定をクリーンアップ
docker run --rm --env-file .env hiroaki0923/aiseg2mqtt:latest uv run aiseg2_clean.py
```

## Home Assistant での表示

MQTT Discoveryにより、以下のセンサーが自動的に作成されます：

- `sensor.aiseg2mqtt_total_today` - 本日の総使用量
- `sensor.aiseg2mqtt_buy_today` - 本日の購入電力量
- `sensor.aiseg2mqtt_sell_today` - 本日の売電量
- `sensor.aiseg2mqtt_gen_today` - 本日の発電量
- `sensor.aiseg2mqtt_c{回路番号}` - 各回路の使用量

## 動作の仕組み

1. AISEG2のWebインターフェースにHTTP Digest認証でアクセス
2. HTMLをパースして電力データを抽出
3. MQTTブローカーにHome Assistant Discovery形式で送信
4. 指定された間隔で定期的に実行（`main.py`使用時）

## トラブルシューティング

### 認証エラーが発生する場合

- AISEG2のユーザー名とパスワードが正しいか確認
- AISEG2のIPアドレスが正しいか確認

### MQTTに接続できない場合

- MQTTブローカーが起動しているか確認
- ファイアウォールの設定を確認
- MQTT認証情報が正しいか確認

### データが取得できない場合

- AISEG2のファームウェアバージョンによってはWebインターフェースが異なる可能性があります
- `LOG_LEVEL=DEBUG`に設定して詳細なログを確認してください

## ライセンス

MIT License
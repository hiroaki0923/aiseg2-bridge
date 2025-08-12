# AiSEG2 Bridge for Home Assistant

AiSEG2（Panasonic製エネルギーモニター）とHome Assistantを接続するブリッジ統合。

## 機能

- AiSEG2から電力使用量データを定期的に取得
- Home Assistantネイティブ統合（MQTT不要）
- 総量データ（使用量/購入量/売電量/発電量）の取得
- 回路別の電力使用量（kWh）の取得
- エラー時の自動リトライとロバストな実行
- Home Assistantのエネルギーダッシュボード対応

## 必要要件

- Home Assistant 2024.1.0以降
- AiSEG2へのネットワークアクセス

## インストール

### HACS経由（推奨）

1. HACSで「Custom repositories」を開く
2. リポジトリURL `https://github.com/hiroaki0923/aiseg2-bridge` を追加
3. カテゴリで「Integration」を選択
4. 「AiSEG2 Bridge」をインストール
5. Home Assistantを再起動

### 手動インストール

1. このリポジトリをダウンロード
2. `custom_components/aiseg2_bridge` フォルダを Home Assistantの `custom_components` ディレクトリにコピー
3. Home Assistantを再起動

## 設定

1. Home Assistantの「設定」→「デバイスとサービス」を開く
2. 「統合を追加」をクリック
3. 「AiSEG2 Bridge」を検索して選択
4. AiSEG2の接続情報を入力：
   - **ホスト**: AiSEG2のIPアドレス（例: 192.168.0.216）
   - **ユーザー名**: AiSEG2のログインユーザー名（通常: aiseg）
   - **パスワード**: AiSEG2のログインパスワード

### オプション設定

統合の設定後、「オプション」から以下を変更できます：
- **スキャン間隔**: データ取得間隔（秒）、デフォルト: 300秒（5分）

## Home Assistant での表示

統合により、以下のセンサーが自動的に作成されます：

- **Total Energy Today** - 本日の総使用量
- **Purchased Energy Today** - 本日の購入電力量  
- **Sold Energy Today** - 本日の売電量
- **Generated Energy Today** - 本日の発電量
- **回路名** - 各回路の使用量（回路設定に応じて）

全てのセンサーは `device_class: energy` で、Home Assistantのエネルギーダッシュボードで使用できます。

## 開発者向け情報

### 開発環境セットアップ

```bash
# Git hooks をセットアップ (コード品質チェック)
./setup-hooks.sh

# 手動でコードチェックを実行
./lint-check.sh

# 自動修正付きでチェック実行
./lint-check.sh --fix

# 特定のファイルのみチェック
./lint-check.sh custom_components/aiseg2_bridge/__init__.py

# 特定のファイルのみ自動修正
./lint-check.sh --fix custom_components/aiseg2_bridge/__init__.py

# または直接修正スクリプトを実行
./lint-fix.sh
```

### 推奨開発ツール

```bash
# コード品質チェック用
pip install flake8 pylint mypy

# 自動コード整形用
pip install autopep8 black isort

# JSON検証のため
brew install jq  # macOS
# または
apt-get install jq  # Linux
```

### コードチェック・修正機能

#### チェック内容
- Python構文エラーチェック
- flake8による品質チェック
- Home Assistant固有パターンの検証
- manifest.json妥当性検証

#### 自動修正機能
- **autopep8**: PEP8準拠の自動整形
- **black**: 統一されたコードスタイル適用
- **isort**: import文の自動ソート
- **手動修正**: 空白、改行、基本的なスタイル問題
- **バックアップ**: 修正前の自動バックアップ作成

## 動作の仕組み

1. AiSEG2のWebインターフェースにHTTP Digest認証でアクセス
2. HTMLをパースして電力データを抽出
3. Home Assistantのセンサーとして直接データを提供
4. 設定された間隔で定期的にデータを更新

## トラブルシューティング

### 統合の追加でエラーが発生する場合

- AiSEG2のIPアドレスが正しいか確認
- ユーザー名とパスワードが正しいか確認
- Home AssistantからAiSEG2にネットワーク接続できるか確認

### センサーが「利用不可」になる場合

- AiSEG2の電源が入っているか確認
- ネットワーク接続を確認
- ログを確認（設定→システム→ログ）

### データが取得できない場合

- AiSEG2のファームウェアバージョンによってはWebインターフェースが異なる可能性があります
- ログでHTTPエラーやタイムアウトをチェック

## ログの確認

Home Assistantの「設定」→「システム」→「ログ」でエラー詳細を確認できます。
統合は詳細なログ出力に対応しており、問題の特定が容易です。

## 免責事項

**重要:** 本ツールはAiSEG2デバイスのWebインターフェースに定期的にアクセスしてデータを取得します。これにより、AiSEG2デバイスに負荷がかかる可能性があります。

- 本ツールの使用は自己責任でお願いします
- AiSEG2デバイスへの過度なアクセスは機器の動作に影響を与える可能性があります
- 適切な実行間隔を設定し、デバイスへの負荷を最小限に抑えてください
- 本ツールの使用によって生じたいかなる損害についても、作者は責任を負いません
- AiSEG2は株式会社パナソニックの製品であり、本ツールは非公式のものです

## ライセンス

Apache-2.0 License
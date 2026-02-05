# Claude Code × Codex オーケストレーター

Claude Code を指揮者/コンサートマスター、Codex を演奏者として協調させるCLIです。
出力は日本語を前提に設計しています。

---

## クイックスタート（初回セットアップ）

### 1. 前提条件

以下のツールがインストールされている必要があります：

| ツール | インストール方法 |
|--------|------------------|
| Python 3.8+ | https://www.python.org/ |
| Node.js 18+ | https://nodejs.org/ |
| Claude Code CLI | `npm install -g @anthropic-ai/claude-code` |
| Codex CLI | `npm install -g @openai/codex` |

### 2. リポジトリのクローンと依存関係のインストール

```bash
# クローン
git clone https://github.com/YOUR_USERNAME/claude-codex-orchestrator.git
cd claude-codex-orchestrator

# Python依存関係
pip install pyyaml watchdog

# Web UI依存関係
cd web
npm install
cd ..
```

### 3. 設定ファイルの編集

#### 3.1 Web UI の認証設定（必須）

`web/index.html` を編集して、ログイン情報を設定してください：

```html
<script>
  window.ORCHESTRATOR_API_BASE = "http://localhost:8088";
  window.ORCHESTRATOR_LOGIN_ENABLED = true;
  window.ORCHESTRATOR_LOGIN_USER = "your_username";  // ← 変更
  window.ORCHESTRATOR_LOGIN_PASS = "your_password";  // ← 変更
</script>
```

> **推奨**: パスワードは SHA-256 ハッシュで設定してください（後述）

#### 3.2 デプロイスクリプトの設定（外部公開する場合）

`ctl.sh` を編集して、サーバー情報を設定：

```bash
REMOTE_HOST="Lambda"  # SSHホスト名（~/.ssh/config で設定）
REMOTE_PATH="public_html/orchestrator"  # リモートパス
```

### 4. 動作確認

#### CLI のみで使う場合

```bash
python3 orchestrator.py --task "Hello World を出力するスクリプトを作成"
```

#### Web UI を使う場合（ローカル開発）

```bash
# ターミナル1: バックエンドAPI起動
./ctl.sh backend

# ターミナル2: フロントエンド開発サーバー起動
./ctl.sh dev
```

ブラウザで http://localhost:5173 を開いてください。

#### Web UI を使う場合（外部公開）

```bash
# バックエンド + トンネルを一括起動（バックグラウンド）
./ctl.sh start

# 状態確認
./ctl.sh status

# 停止
./ctl.sh stop
```

---

## 使い方

```bash
cd /Users/xxx/claude-codex-orchestrator
python3 orchestrator.py --task "やりたいことを1文で書く"
```

標準入力も使えます。

```bash
echo "要件定義の草案を作って" | python3 orchestrator.py
```

## 依存関係

```bash
pip install pyyaml watchdog
```

## 設定

`config.json` で外部コマンドを指定します。  
`{prompt}` または `{prompt_file}` を使ってプロンプトを渡せます。

```json
{
  "rewriter": {
    "cmd": ["claude", "-p", "{prompt}"]
  },
  "concertmaster": {
    "cmd": ["claude", "-p", "{prompt}"]
  },
  "performer": {
    "cmd": ["codex", "exec", "--skip-git-repo-check"]
  },
  "instrument_pool": ["ヴァイオリン", "ビオラ", "チェロ"]
}
```

`codex exec` は引数が無い場合に標準入力を読むため、`{prompt}` を省略しています。
`claude` は `-p` を付けて非対話で実行します。

---

## SSH リモート実行モード

データや解析ソフト（Python, ROOT, bash）がリモートサーバーにあり、ローカルにコピーできない場合に使います。
オーケストレーターはローカルで計画を立て、**実際のコマンドだけをSSH経由でリモートサーバー上で実行**します。

```
ローカル Mac                            リモートサーバー (例: cw01)
┌──────────────────────────┐          ┌─────────────────────────┐
│ Rewriter (Claude)        │          │                         │
│   ↓ タスク分解           │          │  Python, ROOT, bash     │
│ Concertmaster (Claude)   │   SSH    │  大容量実験データ       │
│   ↓ シェルコマンド出力   │ ──────→  │  スクリプト実行         │
│ ssh_executor.py          │ ←──────  │  stdout/stderr 返却     │
│   ↓ 結果収集             │          │                         │
│ Mix (Claude)             │          └─────────────────────────┘
│   ↓ 結果統合             │
└──────────────────────────┘
```

### セットアップ

#### 1. SSH接続の確認

パスワードなしでリモートサーバーにSSH接続できることを確認してください。

```bash
# 公開鍵認証が設定済みであること
ssh user@remote-host "echo ok"
```

#### 2. config.json の設定

`ssh_remote` セクションを編集します。

```json
{
  "ssh_remote": {
    "enabled": true,
    "host": "cw01",
    "user": "username",
    "port": 22,
    "key_file": "~/.ssh/id_ed25519",
    "remote_path": "/home/username/analysis"
  }
}
```

| キー | 説明 |
|------|------|
| `enabled` | `true` にするとSSHリモート実行モードが有効になる |
| `host` | リモートサーバーのホスト名（`~/.ssh/config` のホスト名でもOK） |
| `user` | SSHユーザー名（空欄ならSSH設定に従う） |
| `port` | SSHポート番号（デフォルト: 22） |
| `key_file` | 秘密鍵のパス（デフォルト: `~/.ssh/id_ed25519`） |
| `remote_path` | リモート上の作業ディレクトリ（コマンド実行時の `cd` 先） |

#### 3. 動作確認

```bash
# SSHリモートモードで起動（--verbose で接続確認ログが出る）
python3 orchestrator.py --verbose \
  --task "/home/user/data 以下の .root ファイル一覧を表示して"
```

ログに `[SSHRemote] Performer mode: ssh_executor` と表示されれば有効です。

Web UI から使う場合も同じです。`config.json` を編集するだけで、バックエンド再起動後に自動的にSSHモードに切り替わります。

```bash
# バックエンド再起動
./ctl.sh stop && ./ctl.sh start
```

### 仕組み

SSHリモートモードが有効な場合、オーケストレーターは自動的に以下の切り替えを行います：

1. **コンサートマスター**のシステムプロンプトが `AGENT.md` → `AGENT_SSH.md` に変わる
   - コンサートマスターは「演奏者がリモートのシェルコマンドしか実行できない」ことを知っている
   - 指示にはコードブロック（`` ```bash `` / `` ```python ``）で実行可能なコマンドを含める
2. **演奏者**のコマンドが `codex exec` → `ssh_executor.py` に変わる
   - コンサートマスターの指示からコードブロックを抽出
   - SSH経由でリモートサーバー上で実行
   - stdout/stderr を返却

リモートサーバーにソフトウェアのインストールは不要です。SSH接続さえできれば動作します。

### ssh_executor.py の単体テスト

```bash
# bash コマンドの実行テスト
echo '```bash
ls -la /home/user/data/
```' | python3 ssh_executor.py

# Python スクリプトの実行テスト
echo '```python
import os
print(os.listdir("/home/user/data/"))
```' | python3 ssh_executor.py
```

### 対応言語

| コードブロック | 実行方法 |
|----------------|----------|
| `` ```bash `` / `` ```sh `` | `ssh host 'cd remote_path && コマンド'` |
| `` ```python `` / `` ```python3 `` | 短いスクリプト: `ssh host 'python3 -c "..."'`、長いスクリプト: SCP転送 → 実行 |

コードブロックが見つからない場合は、`$` で始まる行や既知のコマンド（`ls`, `find`, `python3` など）を自動検出して実行します。

### 構成ファイル

| ファイル | 説明 |
|----------|------|
| `ssh_executor.py` | SSH経由のコマンド実行エンジン（`codex exec` の代替） |
| `AGENT_SSH.md` | SSHモード用コンサートマスターのシステムプロンプト |
| `ssh_remote.py` | sshfs/rsyncによるリモートファイルシステムマウント（別機能） |

### トラブルシューティング

**`Permission denied` エラー**
→ SSH鍵認証を確認してください。`ssh -i ~/.ssh/id_ed25519 user@host "echo ok"` が通ること。

**`Command timed out` エラー**
→ `config.json` の `performer.timeout_sec` を増やしてください（デフォルト: 600秒）。

**コンサートマスターが曖昧な指示を出す**
→ `AGENT_SSH.md` が正しく読み込まれているか確認（`--verbose` でログ確認）。

**リモートで `python3` や `root` コマンドが見つからない**
→ コンサートマスターへの指示に `source /opt/root/bin/thisroot.sh` などの環境設定コマンドを含めてください。

---

## 実行結果

実行ごとに `runs/` 以下へ保存します。

- `score.json` 指揮者の分担スコア
- `score.yaml` 指揮者の分担スコア（YAML）
- `score_raw.yaml` 指揮者の生出力（ある場合）
- `performer_*_stdout.txt` 各演奏者の出力
- `final.txt` 統合結果
- `status.json` 進捗ステータス
- `exchanges/exchange_*.yaml` コンサートマスター/演奏者のやりとり

## オプション

- `--dry-run` 外部コマンドを実行せず、プロンプト生成のみ
- `--config` 設定ファイルのパスを指定
- `--run-dir` 出力先ディレクトリを指定

## メモ

- `claude` / `codex` コマンドは別途インストールが必要です。
- 出力形式や楽器名は `config.json` の `instrument_pool` で調整できます。
- 演奏者の数は、分解されたタスク数に合わせて自動で最適化されます。

## YAML 交換フロー

- 1) 指揮者（Claude Code）がタスクを言い直し+分配（`score.yaml`）
- 2) コンサートマスター（Claude Code）が演奏者向けの指示を生成し、`exchange_*.yaml` に書く
- 3) 演奏者（Codex）が `exchange_*.yaml` を監視して実行し、出力を書き戻す
- 2と3は相互に `exchange_*.yaml` を監視します

### 危険な操作の確認

コンサートマスターが `action: needs_user_confirm` を出した場合、
`exchange_*.yaml` の `pending` に `suggested_reply` が入ります。
ユーザーが確認したら、以下のどちらかを設定してください。

```yaml
pending:
  user_reply: "ユーザーの返答（任意）"
  user_approved: true
```

Web UI からも返信できます（「指揮者 / コンマス」セクション）。

## 構成

- `ctl.sh` 統合管理スクリプト（後述）
- `orchestrator.py` CLI本体
- `web_server.py` API + ジョブ実行サーバ
- `ssh_executor.py` SSHリモート実行エンジン
- `ssh_remote.py` sshfs/rsyncリモートマウント
- `ssh_remote_cli.py` SSHリモート操作CLI
- `AGENT.md` コンサートマスター/演奏者のシステムプロンプト
- `AGENT_SSH.md` SSHリモートモード用システムプロンプト
- `CLAUDE.md` 指揮者（Rewriter/Mix）のシステムプロンプト
- `web/` React + Vite フロントエンド
- `runs/` 実行ログ/結果
- `logs/` サービスログ・トンネルURL

## ctl.sh コマンド一覧

```
./ctl.sh <command> [options]

  start [port]      バックエンド + トンネルを一括起動
  stop              全サービス停止
  status            サービス状態確認

  backend [port]    バックエンドのみ起動
  tunnel [port]     トンネルのみ起動
  update-url [url]  フロントエンドのAPI URL更新

  dev               フロントエンド開発サーバー起動
  build             フロントエンドビルド
  deploy            リモートサーバーへデプロイ

  logs [service]    ログ表示 (backend|tunnel|all)
  help              ヘルプ表示
```

## Web UI (React/Vite)

進捗確認とジョブ投入用のUIです。

### ローカル開発

```bash
# ターミナル1: バックエンド
./ctl.sh backend

# ターミナル2: フロントエンド開発サーバー
./ctl.sh dev
```

http://localhost:5173 を開いてください。

### 外部公開（トンネル + 静的配備）

APIはローカルで動かし、Cloudflare TunnelでHTTPS公開します。

```bash
# バックエンド + トンネル一括起動
./ctl.sh start

# 状態確認
./ctl.sh status

# 停止
./ctl.sh stop
```

トンネルURLは自動的に `logs/tunnel.url` に保存され、フロントエンドに反映されます。

### リモートサーバーへのデプロイ

```bash
# ビルド
./ctl.sh build

# デプロイ
./ctl.sh deploy
```

## セキュリティ

ジョブ投入（POST）を保護したい場合はAPIトークンを使います。

```bash
python3 web_server.py --host 0.0.0.0 --port 8088 \
  --cors-origin '*' \
  --api-token 任意
```

フロント側は `web/index.html` の `ORCHESTRATOR_API_TOKEN` を設定してください。

## ログイン認証（クライアント側）

静的ホスティングのため、簡易的なクライアント側ログインを追加しています。
`web/index.html` に以下を設定してください。

```html
<script>
  window.ORCHESTRATOR_LOGIN_ENABLED = true;
  window.ORCHESTRATOR_LOGIN_USER = "user";
  // 平文を置く場合
  // window.ORCHESTRATOR_LOGIN_PASS = "pass";
  // SHA-256 を置く場合（推奨）
  window.ORCHESTRATOR_LOGIN_PASS_SHA256 = "<sha256 hex>";
</script>
```

SHA-256 の生成例:

```bash
python3 - <<'PY'
import hashlib
print(hashlib.sha256("pass".encode()).hexdigest())
PY
```

注意: この方式はクライアント側の簡易認証です。公開用途ではAPI側の認証も併用してください。

# 沖縄 求人ニュース（無料・APIキー不要）

毎朝6時(JST)に GitHub Actions が記事を集め、`docs/index.html` を更新します。

## 公開手順（初回のみ）
1. GitHubで新しいリポジトリを作り、このフォルダの中身をすべてアップロード
2. Settings → Pages → Source を「Deploy from a branch」、Branch を `main` / `/docs` に設定
3. Actions タブ → daily-news → 「Run workflow」で初回実行
4. 表示されるPagesのURLをチーム共有（社外秘にしたい場合はプライベート運用を要検討）

## カスタマイズ（config.json だけ編集）
- queries: 検索キーワード追加（site:ドメイン も可）
- rss: 直接取得したいRSSのURLを追加
- categories / talk: カテゴリ判定語と営業トーク例文

## 機能
今週のダイジェスト（直近7日のTOP5＋営業トーク例）／期間・カテゴリ・沖縄のみ・キーワード検索／最大400日分の蓄積

# MAME Explorer

**Status: Work in Progress（制作中）**

MAME の listxml（`<mame>`）と Software List XML（`hash/*.xml`）から、XML だけを情報源にツリー表示・Properties・検索を行うキーボード操作の CUI。

実装: [`mame_explorer.py`](mame_explorer.py)  
設計書: [`docs/design.md`](docs/design.md)  
English README: [`README.md`](README.md)

## 実行

```bash
# 直接モード（毎回 -listxml と hash 検出）
python mame_explorer.py <mame実行ファイル | 展開済みディレクトリ | アーカイブ>

# キャッシュモード（再実行を速くする・実 CHD 候補確認用）
python mame_explorer.py read arcade <mame実行ファイル/パッケージ>
python mame_explorer.py read softwarelist <hashディレクトリ または mameパッケージ>
python mame_explorer.py read romdir <CHDを再帰探索するルート>
python mame_explorer.py   # 引数なしでキャッシュを閲覧
python mame_explorer.py chd   # CHD mode（romdir キャッシュ必須・実在 CHD がある枝だけ残す）
```

指定した1つから、`-listxml` 実行と `hash/*.xml` 検出を内部で自動処理する。mame 実行ファイルの入手方法は問わない。

実行ファイルと `hash` が別ツリーに分かれる配置は `find_hash_dir` が候補パスとして扱う。候補に無い配置でも、`*.xml` を含む `hash` という名前のディレクトリが探索対象配下にあれば再帰的に見つける。`hash` が見つからない場合、Software Lists ルート自体がツリーに出ない。

アーカイブを指定した場合、展開先は指定ファイルと同じ階層の `.mame-explorer-cache` ディレクトリで、既に展開済みならそれを再利用する。

`chd` は romdir キャッシュが無いとエラーで起動しない。実在する CHD に紐付く枝だけを残したビューになる。

詳細なコマンド例は `python mame_explorer.py --usage` を参照。

## 操作キー

| キー | 動作 |
|------|------|
| ↑ / ↓ | 移動 |
| Enter / → | 展開 |
| ← | 折りたたみ |
| P | Properties 表示切替 |
| / | 検索（現在展開済み＝可視ノードのみ対象） |
| Tab | Disk ノード上（romdir キャッシュがある場合）で CHD 候補表示 / SHA-1 チェック |
| Q | 終了 |

## 検証記録

Ubuntu 上で `sudo apt install mame mame-tools mame-data` により導入した mame 0.285 で、Arcade 49,616 machine・Software Lists 755 リストまでツリー構築が完走することを確認した。`-listxml` のフル出力は数百 MB 規模で、実行に時間がかかる。

確認済みはこの1構成のみ。これ以外のバージョン・ディストリ・配置での動作は未検証。

## 未実装・今後の予定（設計書より）

- Disk（CHD）ノードに対する Extract（実 CHD → 媒体種別に応じたイメージ出力）
- mediaKind 分類と Extract 分岐
- 検索の強化（Software 単位まとめ、属性横断など）
- バッジ表示（cloneof / supported / status など）

## ライセンス

MIT License – [LICENSE](LICENSE) を参照。

Copyright (c) 2026 skt001

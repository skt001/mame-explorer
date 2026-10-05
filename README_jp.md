# MAME Explorer


MAME の `-listxml` と Software List XML（`hash/*.xml`）を情報源として、MAME の論理構造をツリー表示するキーボード操作の CUI。Properties と検索も XML 由来の論理モデルを対象とする。

MAME Explorer は **MAME metadata / XML の Explorer** であり、ROM checker、CHD checker、ROM manager、ROM set 管理ツールではない。ROM / CHD の SHA-1 などを計算して検証する機能は持たない。

実装: [`mame_explorer.py`](mame_explorer.py)  
設計書: [`docs/design.md`](docs/design.md)  
English README: [`README.md`](README.md)

## 実行

```bash
# 直接モード（毎回 -listxml と hash 検出）
python mame_explorer.py <mame実行ファイル | 展開済みディレクトリ | アーカイブ>

# キャッシュモード（再実行を速くする）
python mame_explorer.py read arcade <mame実行ファイル/パッケージ>
python mame_explorer.py read softwarelist <hashディレクトリ または mameパッケージ>
python mame_explorer.py read romdir <CHDを再帰探索するルート>
python mame_explorer.py   # 引数なしでキャッシュを閲覧
python mame_explorer.py chd   # CHD mode（romdir キャッシュ必須・対応する CHD がある枝だけ残す）
```

指定した1つから、`-listxml` 実行と `hash/*.xml` 検出を内部で自動処理する。mame 実行ファイルの入手方法は問わない。

実行ファイルと `hash` が別ツリーに分かれる配置は `find_hash_dir` が候補パスとして扱う。候補に無い配置でも、`*.xml` を含む `hash` という名前のディレクトリが探索対象配下にあれば再帰的に見つける。`hash` が見つからない場合、Software Lists ルート自体がツリーに出ない。

アーカイブを指定した場合、展開先は指定ファイルと同じ階層の `.mame-explorer-cache` ディレクトリで、既に展開済みならそれを再利用する。

`read romdir` は CHD のファイル名とパスを Explorer の CHD mode 用に索引化するだけで、SHA-1 等のハッシュ検証は行わない。

`chd` は romdir キャッシュが無いとエラーで起動しない。XML で定義された Disk 名に対応する `.chd` が存在する枝だけを残したビューになる。

詳細なコマンド例は `python mame_explorer.py --usage` を参照。

## 操作キー

| キー | 動作 |
|------|------|
| ↑ / ↓ | 移動 |
| Enter / → | 展開 |
| ← | 折りたたみ |
| P | Properties 表示切替 |
| / | 検索（現在展開済み＝可視ノードのみ対象） |
| Tab | Disk ノード上（romdir キャッシュがある場合）で対応する CHD ファイル候補を表示 |
| Q | 終了 |

## スコープ

MAME Explorer が扱うのは MAME の metadata / XML です。

- 論理ツリーの情報源は MAME `-listxml` と Software List XML。
- XML に定義された `name`、`sha1`、`status`、`writeable` などの属性は、存在する場合は metadata として表示する。
- XML に記録されたハッシュを、実 ROM / CHD に対して独自に計算・照合することはしない。
- 実 ROM / CHD の内容によって XML 由来の論理モデルを検証・変更することはしない。
- `romdir` は CHD mode の表示を絞り込むための任意の filesystem index であり、ROM / CHD 検証データベースではない。
- ROM のコピー、整理、修復、検証、ROM set の管理は行わない。


## ライセンス

MIT License – [LICENSE](LICENSE) を参照。

Copyright (c) 2026 skt001

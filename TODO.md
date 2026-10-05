# 開発メモ / TODO

このファイルは開発者向けのメモです。
README.md / README_jp.md は利用者向けの安定したドキュメントとして扱い、
環境依存の動作確認結果、未確認事項、今後の予定などは原則としてこちらに記録します。

## 現在の状態

- MAME metadata / XML Explorer として実装。
- ROM / CHD checker、ROM manager、ROM set 管理は対象外。
- `romdir` は CHD mode の表示絞り込みと candidate 表示用の filesystem index。
- CHD Extract は verification ではなく、実 CHD からの image extraction。
- `docs/design.md` は初期設計案・参考資料として凍結。現行仕様の根拠にはしない。
- 起動時に Arcade / Software Lists の最上位ノードを事前ロードし、curses UI 表示後の初回展開待ちをなくす。子要素は従来どおり lazy loading。

## 動作確認

### MAME 0.285 / Ubuntu 環境

確認済み:

- `read arcade /usr/games/mame` — 49,616 machines
- `read softwarelist /usr/games/mame` — 755 XML files
- `read romdir ../testromdir/` — 12 CHD files / 9 unique names
- CHD mode — candidate 表示
- CHD Extract — `.cue` 出力
- `--usage`
- `-h`

## TODO

- 必要になった機能をここに追加する。
- 実装仕様を変更した場合、README に残すべき利用者向け情報だけを README に反映する。

## 未確認

- MAME 0.285 / Ubuntu 以外の環境
- その他の MAME バージョン・ディストリビューション・配置

# MAME Explorer 設計書（改訂初版）

> **注意: 初期設計案・参考資料**
>
> この文書は MAME Explorer の初期設計段階で作成された設計案です。現在の実装仕様や設計方針を定義する文書ではありません。本文には現在採用していない機能・設計思想も含まれています。
>
> 今後の実装・レビューでは、この文書を仕様の根拠として参照しません。現在の仕様・設計方針については README と実装を参照してください。


| 項目 | 内容 |
|---|---|
| 文書バージョン | 0.1 |
| 日付 | 2026-08-24 |
| 対象入力 | MAME 0.289 listxml XML（ルート <mame>）、Software List XML（hash/*.xml、DTD softwarelist.dtd） |
| 開発言語 | 未定 |
| 位置づけ | 実装可能な初版。旧案の論理ツリーと Extract Target を破棄し、0.289 の実構造に合わせて再定義する |

---

## 1. 目的

MAME の arcade listxml と Software List XML を論理情報源として、Arcade Game / Software / Part / ROM / Disk（CHD）を Explorer 形式で閲覧する。

実 CHD ファイルは Extract 時にのみ使用する。Explorer の表示・展開・検索・Properties は XML だけから行う。

---

## 2. 範囲

### 2.1 初版でやること

- MAME listxml（ルート <mame>）の読み込み
- Software List XML（1 ファイル以上）の読み込み
- MAME 本体／配布 ZIP と ROM ルートフォルダの指定
- 実 ROM / CHD の存在・ハッシュ確認
- XML から論理モデルを構築し、ツリー表示する
- ノードの Properties 表示
- 論理モデルに対する検索
- Disk（CHD）ノードに対する Extract（実 CHD を入力に、種別に応じたイメージを出力）

### 2.2 初版でやらないこと

- Logiqx / ClrMamePro DAT（ルート <datafile>）の解釈
- CHD を書庫のように展開して中のファイル一覧を出すこと
- DAT に無い出力名（.iso / .cue / .img など）をツリーに出すこと
- CHD ヘッダ・トラック情報の読み取り（将来オプション）
- ISO9660 等のファイルシステム解釈
- ROM セット実ファイルの検証・コピー（ROM ノードは表示のみ）
- ソフトウェアの起動・エミュレータ連携

---

## 3. 用語

XML の要素名に合わせる。独自用語は「実装上の便宜」と明記する。

| 用語 | 定義 |
|---|---|
| MAME listxml | MAME の -listxml 出力。ルートは <mame>。Arcade Game / ROM / Disk 等を定義する |
| Arcade Game | <machine>。arcade 側の 1 ゲーム／マシン定義 |
| MAMEセット | listxml と Software List XML、および実 ROM/CHD ルートを組み合わせた入力単位 |
| ROM Root | 実 ROM セットを探索するルートフォルダ |
| CHD Root | 実 CHD を探索するルートフォルダ |
| Software List XML | MAME hash/*.xml。ルートは <softwarelist>。0.289 では 777 ファイル |
| Software | <software>。1 タイトル。arcade の machine ではない |
| Part | <part>。Software の構成単位。媒体スロットに相当。name と interface を持つ |
| DataArea | <dataarea>。ROM 領域。name / size / width / endianness |
| ROM | <rom>。DataArea 内のイメージ断片。ファイルになるものとは限らない |
| ファイル ROM | name があり、かつ loadflag がファイルを指す ROM。ツリーに出す |
| 論理 ROM | loadflag が fill / reload / continue / ignore / reload_plain のもの。ファイルではない。Properties にのみ出す |
| Disk | <disk>。これが CHD。XML に CHD 要素は無い |
| CHD | Disk が指す実ファイル。ファイル名規約は {disk/@name}.chd（拡張子は XML に無い。実装規約） |
| Extract | 実 CHD を入力に、媒体種別に応じたイメージを出力する操作 |
| interface | Part の媒体種別。Extract 方法の唯一の XML 側ヒント。例: cdrom, ide_hdd, floppy_3_5, nes_cart |

使わない語: Extract Target、Game（表示ラベルは description を使う）。

---

## 4. 情報源と境界

通常操作:  Software List XML → Parser → Logical Model → Explorer / Search / Properties
Extract:    Explorer の Disk 選択 → 実 CHD（入力）→ 出力イメージ

| 操作 | XML | 実 CHD |
|---|---|---|
| ツリー構築・展開 | 使う | 使わない |
| Properties | 使う | 使わない |
| Search | 使う | 使わない |
| Extract | 種別判定に interface 等を使う | 入力として使う |
| 出力ファイル名 | XML には無い。Extract 実行時に決める | — |

原則: XML に無いノードをツリーに作らない。CHD は葉である。

---

## 5. システム構成

開発言語は未定。処理の役割だけ固定する。

Software List XML
        │
        ▼
   DAT Parser
        │
        ▼
  Logical Model
        │
        ├── Explorer（表示）
        ├── Properties
        ├── Search
        └── Extract
                │
                ▼
          CHD Extractor  ← 実 CHD はここだけ

- DAT Parser: XML を読み、論理モデルを返す。実ファイルを探さない
- Logical Model: メモリ上の正規化データ。Explorer の唯一の表示源
- Explorer: 論理モデルのツリー表示
- CHD Extractor: Extract 時のみ実 CHD を読む

---

## 6. 論理モデル

XML の入れ子を崩さない。Software 直下に ROM を置かない。Disk の下に CHD や iso を置かない。

SoftwareList
  name, description
  └── Software+
        name
        cloneof?
        supported: yes | partial | no   （省略時 yes）
        description, year, publisher
        notes?
        info*:        { name, value? }
        sharedfeat*:  { name, value? }
        └── Part+
              name
              interface
              feature*:     { name, value? }
              dipswitch*:   { name, tag, mask, values[] }
              dataarea*:
                name, size
                width?: 8 | 16 | 32 | 64     （省略時 8）
                endianness?: big | little    （省略時 little）
                rom*:
                  name?
                  size?, crc?, sha1?, offset?, value?
                  status: baddump | nodump | good   （省略時 good）
                  loadflag?
              diskarea*:
                name
                disk*:
                  name          ← CHD ベース名。拡張子なし
                  sha1?         ← nodump では欠ける
                  status: baddump | nodump | good
                  writeable: yes | no   （省略時 no）
                  ※ スペルは writeable（listxml の writable ではない）

### 6.1 実装が付与してよい派生値（XML に無いが、XML から一意に決まる）

| 派生値 | 決め方 |
|---|---|
| chdFileName | disk/@name + .chd |
| isFileRom | rom/@name が存在し、loadflag が未指定またはファイルロード系 |
| mediaKind | part/@interface から分類。§8.3 |

これらは Properties と Extract 分岐に使う。ツリーの子ノードにはしない。

### 6.2 XML に無いためモデルに持たないもの

- iso / cue / bin / hddimg のファイル名
- トラック一覧、セクタ幾何、ファイルシステム内のパス
- CHD バージョン、圧縮形式、hunk サイズ

### 6.3 0.289 で Parser が必ず許容すること

- Software List は 1 本ではない（リスト単位で開く）
- 1 Software に Part が複数ある（例: Saturn 11 枚、PC-98 フロッピー 48 枚）
- 1 Part に DataArea が複数ある（例: NES の prg と chr）
- ROM と Disk は通常別 Part。同じ Software が CD（Disk）とフロッピー（ROM）を同時に持つ
- フロッピーは CHD ではなく dataarea/rom であることが多い（例: pc98.xml）
- cloneof はフラット参照。XML 上は入れ子にならない
- year は 4 桁数字とは限らない
- status=nodump の ROM/Disk はハッシュを持たない
- 無名 ROM（loadflag=reload 等）がある
- supported は yes / partial / no

---

## 7. Parser

入力は次の2形式を別 Parser で受理する。

- MAME listxml（ルート `<mame>`）→ Arcade 論理モデル
- Software List XML（ルート `<softwarelist>`）→ SoftwareList 論理モデル

出力は共通 Logical Model に統合する。
実 ROM / CHD の探索・検証は Parser の責務ではない。

Parser は入力形式を自動判定してもよいが、`<mame>` と `<softwarelist>` を同一スキーマとして解釈しない。

受理条件:

- ルートが `<softwarelist>` または `<mame>` であること
- 各形式の必須属性が存在すること

拒否:

- ルートが `<datafile>`（Logiqx / ClrMamePro DAT）
- 整形式でない XML

## 8. MAME 入力環境

ユーザーは次の入力を個別に指定できる。

| 入力 | 内容 |
|---|---|
| MAME listxml | `<mame>` をルートとする XML。ファイルまたは生成済み XML |
| Software List XML | `hash/*.xml`。1 ファイル以上 |
| MAME 配布 ZIP / 本体 | MAME バージョンの識別・関連 XML/構成の参照に使用してよい |
| ROM Root | 実 ROM セットを探索するルート |
| CHD Root | 実 CHD を探索するルート |

MAME 本体／ZIP と ROM Root は独立して指定できる。
Explorer の論理ツリーは XML から構築し、実ファイル情報は別の実体検証レイヤーで付加する。

## 9. Explorer

### 9.1 ツリー（XML に存在するノードだけ）

Arcade
└── {machine/@description}
    ├── ROM
    └── Disk

Software Lists
└── {softwarelist/@description}          例: Sony PlayStation CD-ROMs
└── {software/description}           例: Enemy Zero (Japan)
    ├── {part/@name}  [{interface}]  例: cdrom  [cdrom]
    │   └── {disk/@name}.chd         葉。子は持たない
    ├── cdrom1 [cdrom]
    │   └── ….chd
    └── flop1 [floppy_3_5]
        └── {rom/@name}              ファイル ROM のみ。葉

DataArea は既定では折りたたみ、Part 直下にファイル ROM を並べる。同名 ROM が複数 DataArea にある場合のみ DataArea を挟む（NES の prg / chr）。

### 9.2 出さないもの

- game.iso 等の仮ファイル
- 「CD image」「HD image」を子ノードにしたプレースホルダ
- 論理 ROM（fill / reload 等）
- dipswitch / feature（Properties へ）

CHD ノードは展開できない。展開アイコンを出さない。媒体種別は Properties の interface / mediaKind で示す。

### 9.3 mediaKind（表示・Extract 用の分類）

interface の完全リストは版ごとに増える。初版は次の分類に落とす。未知は other。

| mediaKind | interface の目安 | ツリー上の実体 | Extract |
|---|---|---|---|
| cd | cdrom | Disk → .chd | 可 |
| harddisk | ide_hdd, scsi_hdd, sasi_hdd 等、名前に hdd / harddisk を含むもの | Disk → .chd | 可 |
| floppy_rom | floppy_3_5, floppy_5_25 等 | ファイル ROM | 初版は不可（CHD ではない） |
| cartridge | *_cart 等 | ファイル ROM | 不可 |
| other | 上記以外 | 存在する子に従う | Disk があれば可、方法は未定義として警告 |

### 9.4 表示上の付加（ノードは増やさない）

- cloneof がある Software はラベルに clone である旨を添えてよい
- supported=no / partial はバッジ
- status=nodump / baddump はバッジ
- Disk の writeable=yes はバッジ（HDD イメージで多い）

---

## 10. Properties

選択ノードの論理モデルをそのまま出す。実 CHD で補完しない。

| ノード | 主な項目 |
|---|---|
| MAME | version, build 等（XML に存在する項目のみ） |
| SoftwareList | name, description, Software 数 |
| Arcade Game | name, description, year, manufacturer, cloneof, ROM/Disk 定義 |
| Software | name, description, year, publisher, cloneof, supported, info, sharedfeat |
| Part | name, interface, mediaKind, feature |
| DataArea | name, size, width, endianness |
| ROM | name, size, crc, sha1, offset, status, loadflag, isFileRom |
| Disk | name, chdFileName, sha1, status, writeable, 親 Part の interface / mediaKind |

sha1 / crc が無い場合は「なし（nodump）」と出す。欠落を推測で埋めない。

---

## 11. Search

対象は論理モデルのみ。実 CHD を読まない。

初版の検索対象:

- Software: name, description, year, publisher
- info / sharedfeat の value
- Part: name, interface
- ファイル ROM: name, crc, sha1
- Disk: name, sha1, chdFileName
- Arcade Game: name, description, year, manufacturer, cloneof
- 実体検証結果: exists / hash OK / hash NG / unavailable（論理モデルとは分離）

結果は Software 単位でまとめ、ヒットした子へ辿れるようにする。

---

## 12. Extract

対象は Disk ノードだけ。ROM ノードの Extract は初版に含めない。

### 11.1 実行条件

1. 選択が Disk である
2. status が nodump でない
3. sha1 がある
4. 実 CHD が利用できる

実 CHD の特定:

- 既定ファイル名は chdFileName（{disk/@name}.chd）
- 照合は sha1。名前一致だけでは不足
- 探索パスは実装が持つ（設定・ダイアログ）。設計は「利用できる」ことだけを要求する

### 11.2 出力

出力パスとファイル名は実行時に利用者が決める。XML は出力名を持たない。

| mediaKind | 入力 | 出力の意味 | 備考 |
|---|---|---|---|
| cd | CHD | CD イメージ | 典型は cue + 1 本以上の bin。単一 iso とは限らない |
| harddisk | CHD | ハードディスクの raw イメージ | writeable=yes でも Extract は読み出し |
| other で Disk あり | CHD | 未定義 | 実行前に警告し、利用者が継続した場合のみ試みる |

ツールの実体（chdman 等）は言語未定のため本設計では固定しない。Extractor は次を満たせばよい。

- 入力 CHD の sha1 が Disk の sha1 と一致することを、可能な範囲で確認する
- 失敗時は XML を改変しない
- 成功しても論理モデルは更新しない（Explorer は XML のまま）

### 11.3 明示しないこと

Extract が「game.iso を CHD から取り出す」操作である、とは書かない。
CHD は書庫ではなくディスクイメージである。Extract はイメージ形式の変換・展開であり、名前付きメンバーの取り出しではない。

---

## 13. エラー処理

### 12.1 XML

| 事象 | 扱い |
|---|---|
| 読み込み失敗 | エラー。モデルを作らない |
| ルート形式が対象外 | エラー。-listxml / Logiqx を案内してよい |
| 必須属性欠落 | その Software または Part をスキップし、警告を残す |
| nodump / ハッシュ無し | 警告。表示はする。Extract は不可 |

### 12.2 Extract

| 事象 | 扱い |
|---|---|
| 対象が Disk でない | 不可。実行しない |
| 実 CHD が無い | エラー |
| sha1 不一致 | エラー。出力しない |
| nodump | 不可 |
| 出力先書き込み失敗 | エラー。途中ファイルの扱いは実装任せ（残さないことを推奨） |
| 未知の mediaKind | 警告のうえ、継続確認 |

---

## 14. 設計原則

1. 論理情報の情報源は MAME listxml と Software List XML であり、形式ごとに別 Parser で扱う
2. Explorer に出すノードは XML 要素に対応するものだけである
3. Disk が CHD である。CHD 用の子要素は作らない
4. XML に無いファイル名をプレースホルダとしてもツリーに出さない
5. 実 ROM / CHD は論理モデルとは別の実体検証レイヤーで扱い、Extract 時にも入力として使う
6. 実 ROM / CHD の内容で XML 由来の Properties やツリー構造を変更しない
7. arcade listxml と Software List は別 Parser とし、共通 Logical Model の上位で統合する

---

## 15. 未決定事項（初版では決めない）

- 開発言語、GUI ツールキット、配布形態
- Extract の具体コマンド（chdman の有無を含む）
- CHD 探索パスの UI
- 複数リストを開いたときのタブ / 単一ツリー
- clone を親の下にグループするか（データはフラットのまま）
- DataArea を常に見せるか（既定は §8.1）
- CHD ヘッダだけ読んでトラックを出す将来機能（やるなら原則 5 の例外として別節を起こす）

---

## 16. 今回の改訂

- `-listxml` の `<mame>` を正式な入力対象に追加
- Software List XML と MAME listxml を別 Parser として扱う
- Explorer を MAME 全体（Arcade + Software Lists）へ拡張
- MAME 本体／配布 ZIP と ROM Root を独立した入力として指定可能にする
- 実 ROM / CHD の存在・ハッシュ確認を論理モデルとは分離して追加

## 17. 旧案からの変更（初版で破棄したもの）

| 旧案 | 初版 |
|---|---|
| Software 直下に ROM と Part が兄弟 | ROM は必ず Part / DataArea の下 |
| Part → Disk → CHD → Extract Target | Part → Disk（葉）。Disk = CHD |
| game.chd の下に game.iso | 置かない。出力名は Extract 時に決める |
| CHD を 7-Zip 相当のアーカイブとして展開 | しない。ディスクイメージとして扱う |
| 用語「Game」 | description をラベルにし、型名は Software |
| DAT を単一ファイルとみなす記述 | リストは複数ファイル。識別は (list, software) |

---

## 16. 参照

- MAME 0.289 hash/softwarelist.dtd
- 公式 listxml（mame0289lx.zip）は本システムの入力ではない。Software List との混同禁止
- Disk 属性のスペルは Software List では writeable
